"""playbench playtest harness: bots play the real build (web via Playwright, Godot native experimental).

    playtest.py run <build> [--mode M] [--bot idle|random|policy|mash|script:F.json] [--seeds N] [--seconds S]
                            [--override F:K=V | NAME=V]... [--realtime] [--coop] [--windowed] [--out DIR]
    playtest.py selftest [game_dir]

Library: run(build, ...) -> report dict (spec: Report JSON). Stdlib only; playwright is imported lazily.
A build is a dir, a .zip, or either with a ?query suffix that is passed to the game (?bug=crash).
"""
import argparse, csv, hashlib, io, json, os, random, shutil, statistics, subprocess, sys, tempfile, threading, time, zipfile
from contextlib import contextmanager, redirect_stderr
from datetime import datetime, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE_GD, SHEET = HERE / "probe.gd", HERE.parent / "skills" / "playtest" / "sheet-template.md"
MODES = {"quick": (3, 30), "milestone": (8, 60), "final": (8, 60), "boot": (1, 10), "sweep": (5, 60)}
WEB_ACTIONS = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", " ", "Enter"]
GODOT_ACTIONS = ["ui_left", "ui_right", "ui_up", "ui_down", "ui_accept"]
START_KEYS = ("Enter", "ui_accept")
SKIP_KEYS = {"t", "time", "frame", "tick", "elapsed"}
LABELS = {2: "relative difficulty under policy bot", 1: "random-input stats, not difficulty"}
KEYS = ["version", "at", "mode", "engine", "build", "tier", "verdict", "summary", "runs", "findings", "stats",
        "overrides", "regression", "cannot_judge"]
CANNOT_JUDGE = "Bots cannot judge fun, clarity or feel. A human playtest is still required before any gate."
REPLAY_S, EPOCH = 3, datetime(2026, 1, 1)
BOTS = ("idle", "random", "policy", "mash")
SCRIPT_EX = '[{"t": 0, "keys": ["ArrowRight"]}, {"t": 1.5, "keys": []}]'

# Injected before any game script: seed, overrides, seeded Math.random (mulberry32) and the state reader.
PROBE_JS = """(()=>{const P=window.__playbench=__CFG__;let a=P.seed>>>0;
Math.random=()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296};
P.read=()=>{try{const g=window.__game;
 if(g&&typeof g.state==='function')return g.state();
 if(g&&g.state&&typeof g.state==='object')return g.state;
 if(typeof window.render_game_to_text==='function')return JSON.parse(window.render_game_to_text());
 if(window.__GAME_STATE__!==undefined)return window.__GAME_STATE__;
 return null}catch(e){return {__error:String(e&&e.message||e)}}};})();"""
STEP_JS = """b=>{let s=window.__playbench.read(),k=null;
if(b&&s&&!s.__error)try{k=window.__game.bot(s)}catch(e){s={__error:'bot(): '+(e&&e.message||e)}}return [s,k]}"""


def die(msg):
    """SystemExit(2) whose str() is the message (ship/balance show it); printed too, for bare propagation."""
    print(msg, file=sys.stderr)
    e = SystemExit(msg)
    e.code = 2
    raise e


def shash(s):
    if isinstance(s, dict):
        s = {k: v for k, v in s.items() if not (k.startswith("_") or k in SKIP_KEYS)}
    return hashlib.sha1(json.dumps(s, sort_keys=True).encode()).hexdigest()[:12]


def check_bot(bot):
    """Validate a bot name; returns the steps [{t, keys}] of 'script:<path.json>', else []. die(2) when bad."""
    if bot in BOTS or bot.startswith("hold:"):
        return []
    if not bot.startswith("script:"):
        die(f"unknown bot {bot!r}: use idle, random, policy, mash or script:<path.json>")
    f = Path(bot[7:])
    if not f.is_file():
        die(f"bot script not found: {f}")
    try:
        steps = json.loads(f.read_text("utf-8-sig"))
    except ValueError:
        steps = None
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0
    if not (isinstance(steps, list) and steps and all(
            isinstance(e, dict) and num(e.get("t")) and isinstance(e.get("keys"), list)
            and all(isinstance(k, str) for k in e["keys"]) for e in steps)
            and [e["t"] for e in steps] == sorted(e["t"] for e in steps)):
        die(f'bad bot script {f}: need a JSON list of {{"t": seconds, "keys": [...]}} sorted by t, e.g. {SCRIPT_EX}')
    return steps


def new_rec(seed, bot, actions):
    bot = "script:" + Path(bot[7:]).name if bot.startswith("script:") else bot
    return dict(seed=seed, bot=bot, seconds=0.0, over=False, won=False, time_to_over=None, timeline=[], shots=[],
                errors=[], console=[], boot=None, tier=None, actions=actions, final=None, shot=None, png=None)


def err(rec, t, msg):
    msg = (str(msg).strip().splitlines() or ["?"])[0].removeprefix("Clock.run_for: ").removeprefix("Error: ")
    if all(m != msg for _, m in rec["errors"]):
        rec["errors"].append((t, msg[:200]))


def record_step(rec, t, s, held, hasbot):
    """Fold one state read into the run record; returns True when the game is over."""
    d = s if isinstance(s, dict) else {}
    if rec["tier"] is None:
        rec["tier"] = 0 if s is None else 2 if hasbot else 1
    if d.get("__error"):
        err(rec, t, d["__error"])
    over = bool(d.get("over"))
    rec["final"], rec["seconds"] = shash(s), t
    rec["timeline"].append((t, rec["final"], bool(held), over, bool(d.get("paused"))))
    if over:
        rec.update(over=True, won=bool(d.get("won")), time_to_over=t)
    return over


def patch_files(root, overrides):
    """{file: patched text} for overrides that target a data file (CSV id.col or *.col; JSON dotted path)."""
    out = {}
    for o in (o for o in overrides if o.get("file")):
        f = o["file"].replace("\\", "/").removeprefix("./")
        if not (root / f).is_file():
            die(f"override file not found: {root / f}")
        text, key, val = out.get(f) or (root / f).read_text("utf-8-sig"), str(o["key"]), o["value"]
        if f.lower().endswith(".json"):
            data = cur = json.loads(text)
            parts = key.split(".")
            try:
                for k in parts[:-1]:
                    cur = cur[int(k)] if isinstance(cur, list) else cur[k]
                last = int(parts[-1]) if isinstance(cur, list) else parts[-1]
                cur[last]  # must already exist: a typo should fail loudly, not add a dead key
                cur[last] = val
            except (KeyError, IndexError, ValueError, TypeError):
                die(f"override path {key!r} not found in {f}")
            out[f] = json.dumps(data)
            continue
        try:
            delim = csv.Sniffer().sniff(text[:4096], ",;\t").delimiter
        except csv.Error:
            delim = ","
        rows = list(csv.reader(io.StringIO(text), delimiter=delim))
        rid, _, col = key.rpartition(".")
        if not rows or col not in rows[0]:
            die(f"override column {col!r} not in {f} (columns: {rows[0] if rows else []})")
        hit = [r for r in rows[1:] if r and (rid == "*" or r[0] == rid)]
        if not hit:
            die(f"override row {rid!r} not in {f}")
        for r in hit:
            r[rows[0].index(col)] = str(val)
        buf = io.StringIO()
        csv.writer(buf, delimiter=delim, lineterminator="\n").writerows(rows)
        out[f] = buf.getvalue()
    return out


# ---------- web transport ----------
class Quiet(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript",
                      ".mjs": "text/javascript", ".wasm": "application/wasm", ".csv": "text/csv"}

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        if self.server.coop:
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        super().end_headers()


def snap(target):
    try:
        return target.screenshot(timeout=5000)
    except Exception:
        return None


@contextmanager
def web_session(root, query, overrides, realtime, coop):
    x = sys.executable
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        die(f'playwright not installed for {x}: run "{x}" -m pip install playwright && "{x}" -m playwright install chromium')
    patched, ovr = patch_files(root, overrides), {o["name"]: o["value"] for o in overrides}
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(root)))
    srv.coop, srv.handle_error = coop, lambda *a: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/index.html" + (f"?{query}" if query else "")
    try:
        with sync_playwright() as pw:
            try:
                br = pw.chromium.launch(headless=True, args=["--use-angle=swiftshader"])
            except Exception as e:
                die(f'chromium failed to launch ({str(e).splitlines()[0]}): run "{x}" -m playwright install chromium')

            def play(seed, bot, secs):
                rec, now, pg, steps = new_rec(seed, bot, WEB_ACTIONS), [0.0], br.new_page(), check_bot(bot)
                pg.on("pageerror", lambda e: err(rec, now[0], e))
                pg.on("console", lambda m: m.type == "error" and rec["console"].append(m.text))
                if not realtime:  # fixed epoch, paused: time moves only inside run_for, so runs replay exactly
                    pg.clock.install(time=EPOCH)
                    pg.clock.pause_at(EPOCH + timedelta(seconds=1))
                pg.add_init_script(PROBE_JS.replace("__CFG__", json.dumps({"seed": seed, "overrides": ovr})))
                for f, body in patched.items():
                    pg.route("**/" + f, lambda r, *_, b=body: r.fulfill(body=b, content_type="text/plain"))

                def adv(ms):  # an uncaught game error inside run_for is re-raised here: record the crash, keep going
                    try:
                        pg.wait_for_timeout(ms) if realtime else pg.clock.run_for(ms)
                    except Exception as e:
                        err(rec, now[0], e)
                try:
                    pg.goto(url, wait_until="load")
                    try:  # data fetches land before the fake clock moves; a game that never idles still boots
                        pg.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    for _ in range(20):
                        adv(500)
                        if pg.query_selector("canvas"):
                            break
                    else:
                        rec["boot"] = "no <canvas> within 10 s"
                except Exception as e:
                    rec["boot"] = f"page load failed: {str(e).splitlines()[0]}"
                if rec["boot"]:
                    rec["png"] = snap(pg)
                    pg.close()
                    return rec
                cv = pg.locator("canvas").first
                if box := cv.bounding_box():
                    pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                pg.keyboard.press("Enter")
                pg.keyboard.press("Space")
                adv(1000)
                hasbot, acts = pg.evaluate("()=>[typeof window.__game?.bot==='function', window.__game?.actions]")
                rec["actions"] = acts if isinstance(acts, list) and acts else WEB_ACTIONS
                moves = [a for a in rec["actions"] if a not in START_KEYS]
                rng, held, act_since = random.Random(seed), set(), False
                for i in range(1, round(secs * 10) + 1):
                    adv(100)
                    t = now[0] = round(i / 10, 1)
                    s, k = pg.evaluate(STEP_JS, bot == "policy" and hasbot)
                    if bot == "policy":
                        want = set(map(str, k or []))
                    elif bot.startswith("hold:"):
                        want = {bot[5:]}
                    elif bot == "random":  # re-picks every 300 ms: nothing or one move
                        want = set(rng.choice([[]] + [[a] for a in moves])) if i % 3 == 1 else held
                    elif bot == "mash":  # a fresh random subset of every action each step, start keys included
                        want = {a for a in rec["actions"] if rng.random() < 0.5}
                    else:  # script: keys of the last entry with t <= now (the last one stays held); idle: none
                        want = set(next((e["keys"] for e in reversed(steps) if e["t"] <= t), []))
                    try:
                        for key in held - want:
                            pg.keyboard.up("Space" if key == " " else key)
                        for key in want - held:
                            pg.keyboard.down("Space" if key == " " else key)
                    except Exception as e:
                        if steps:  # the human's script, not the game, named the key: a setup error (exit 2)
                            die(f"bad key in bot script {bot[7:]}: {str(e).splitlines()[0]} (web keys: {WEB_ACTIONS})")
                        err(rec, t, f"bot sent a key the browser does not know: {e}")
                        want = set()
                    held, act_since = want, act_since or bool(want)
                    over = record_step(rec, t, s, held, hasbot)
                    if i % 10 == 0 or over:  # under page.clock the canvas only changes inside run_for
                        rec["png"] = snap(cv)
                        rec["shot"] = rec["png"] and hashlib.sha1(rec["png"]).hexdigest()[:12]
                        rec["shots"].append((t, rec["shot"], act_since))
                        act_since = False
                    if over:
                        break
                pg.close()
                return rec

            try:
                yield play
            finally:
                br.close()
    finally:
        srv.shutdown()


# ---------- godot transport (experimental) ----------
def godot_exe():
    """GODOT (a path or a name on PATH) or `godot`, only if it really resolves to an executable."""
    return shutil.which(os.environ.get("GODOT") or "godot")


@contextmanager
def godot_session(root, query, overrides, windowed=False):
    exe = godot_exe()
    if not exe:
        die(f"Godot not found{' at GODOT=' + os.environ['GODOT'] if os.environ.get('GODOT') else ''}: "
            "set GODOT to your Godot 4 editor executable (godot native is experimental)")
    # every override (file ones too, by knob name) is a user arg probe.gd hands to probe_knobs()
    knobs = [f"--{o['name']}={v if isinstance(v := o['value'], str) else json.dumps(v)}" for o in overrides]

    def play(seed, bot, secs):
        rec, frames, hasbot, act = new_rec(seed, bot, GODOT_ACTIONS), int(secs * 60), False, False
        kind, _, arg = bot.partition(":")  # hold:<action>, script:<path.json>
        check_bot(bot)
        with tempfile.TemporaryDirectory() as shots:
            cmd = [exe, *([] if windowed else ["--headless"]), "--path", str(root), "--script", str(PROBE_GD),
                   "--fixed-fps", "60", "--quit-after", str(frames + 120), "--", f"seed={seed}", f"bot={kind}",
                   "step=6", f"frames={frames}", f"hold={arg if kind == 'hold' else ''}",
                   *([f"script={Path(arg).resolve()}"] if kind == "script" else []),
                   *([f"shots={shots}"] if windowed else []), *knobs, *filter(None, query.split("&"))]
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=secs * 3 + 60)
                out, stderr, code = p.stdout, p.stderr, p.returncode
            except subprocess.TimeoutExpired:
                out, stderr, code = "", "ERROR: godot timed out", -1
            for line in out.splitlines():
                if line.startswith("PROBE_INFO "):
                    info = json.loads(line[11:])
                    rec["actions"], hasbot = info.get("actions") or GODOT_ACTIONS, info.get("bot")
                elif line.startswith("PROBE_SHOT "):  # --windowed: hashed like web shots (T0 checks, FAIL shots)
                    try:
                        rec["png"] = Path(line[11:].strip()).read_bytes()
                    except OSError:
                        continue
                    rec["shot"] = hashlib.sha1(rec["png"]).hexdigest()[:12]
                    rec["shots"].append((rec["seconds"], rec["shot"], act))
                    act = False
                elif line.startswith("PROBE "):
                    d = json.loads(line[6:])
                    act = act or bool(d.get("keys"))
                    if record_step(rec, round(d["t"], 2), d.get("state") or None, d.get("keys"), hasbot):
                        break
        for line in (stderr + "\n" + out).splitlines():
            if "SCRIPT ERROR" in line or "ERROR:" in line:
                err(rec, rec["seconds"], line)
        if code or "PROBE_END" not in out:
            err(rec, rec["seconds"], f"godot exited {code} without PROBE_END")
        return rec

    yield play


# ---------- detectors and report ----------
def stuck(seq, span=5.0):
    """First t where the hash stays unchanged >= span s, with input sent in that window and the game not blocked."""
    start = prev = None
    for t, h, act, blocked in seq:
        if h != prev or blocked or start is None:
            start, prev, active = t, h, act
        elif (active := active or act) and t - start >= span:
            return start
    return None


def detect(main, replay, tier, mode):
    out, extra = [], replay[0] + replay[1] if replay else []
    add = lambda kind, sev, r, t, detail: out.append(
        dict(kind=kind, severity=sev, seed=r["seed"], bot=r["bot"], t=t, detail=detail, _png=r["png"]))
    if boot := next((r for r in extra + main if r["boot"]), None):
        add("boot", "FAIL", boot, None, boot["boot"])
    seen, msgs = set(), {}
    for r in extra + main:
        for t, m in r["errors"]:
            if m not in seen:
                seen.add(m)
                add("crash", "FAIL", r, t, m)
        for m in r["console"]:
            msgs.setdefault(m, r)
    for m, r in list(msgs.items())[:5]:
        add("console_error", "WARN", r, None, m[:200])
    for r in main:
        if r["errors"]:
            continue  # the crash already explains the stall
        if tier and (at := stuck([(t, h, a, o or p) for t, h, a, o, p in r["timeline"]])) is not None:
            add("softlock", "FAIL", r, at, "state unchanged 5s while input was sent (not over, not paused)")
        if not tier and (at := stuck([(t, h, a, False) for t, h, a in r["shots"] if h])) is not None:
            add("frozen", "WARN", r, at, "canvas unchanged 5s while input was sent")
    if replay and len(replay[0]) == 2 and replay[0][0][replay[2]] is not None:  # no shots on Godot T0: skip
        (idle, again), holds, key = replay
        if idle[key] != again[key]:
            add("nondeterministic", "WARN", again, None,
                "two idle runs on seed 1 differ; dead-input check skipped (try --realtime, or a no-threads export)")
        elif holds and all(h[key] == idle[key] for h in holds):
            add("dead_input", "FAIL" if tier else "WARN", holds[0], REPLAY_S,
                f"holding {', '.join(h['bot'][5:] for h in holds)} for {REPLAY_S}s ends identical to idle")
        elif mode in ("milestone", "final"):
            for h in (h for h in holds if h[key] == idle[key]):
                add("dead_input", "WARN", h, REPLAY_S, f"action {h['bot'][5:]!r} had no effect in {REPLAY_S}s")
    return out


def stats_for(runs, tier):
    if not tier or not runs:
        return None
    pol = [r for r in runs if r["bot"] == "policy"]  # difficulty only when the goal-directed bot played
    pick, label = (pol, LABELS[2]) if tier == 2 and pol else ([r for r in runs if r["bot"] == "random"] or runs, LABELS[1])
    tto = sorted(r["time_to_over"] for r in pick if r["over"])
    q = statistics.quantiles(tto, n=10, method="inclusive") if len(tto) > 1 else tto * 9 or [None] * 9
    mins, losses = sum(r["seconds"] for r in pick) / 60, sum(r["over"] and not r["won"] for r in pick)
    r2 = lambda v: None if v is None else round(v, 2)
    return {"label": label, "runs": len(pick), "win_rate": r2(sum(r["won"] for r in pick) / len(pick)),
            "tto_p10": r2(q[0]), "tto_p50": r2(q[4]), "tto_p90": r2(q[8]), "deaths_per_min": r2(losses / mins if mins else 0)}


def summarize(verdict, findings, n, tier, checked_input):
    if verdict == "PASS":
        works = ", input works" if checked_input else ""
        return f"PASS: boots{works}, no crashes, freezes or softlocks in {n} run{'s' * (n != 1)} (tier {tier})"
    f, more = next(x for x in findings if x["severity"] == verdict), len(findings) - 1
    where = f" at {f['t']}s" if f["t"] is not None else ""
    return (f"{verdict}: {f['kind']}{where} (seed {f['seed']}, {f['bot']}): {f['detail'][:80]}"
            + (f" - {more} more finding{'s' * (more > 1)}" if more else "") + f" (tier {tier})")


def regression(out, name, rep):
    prev = sorted(p for p in out.glob(f"*-{rep['mode']}.json") if p.name < name)
    if not prev:
        return None
    old = json.loads(prev[-1].read_text("utf-8"))
    a, b, shifts = old.get("stats") or {}, rep["stats"] or {}, {}
    if None not in (a.get("win_rate"), b.get("win_rate")) and abs(a["win_rate"] - b["win_rate"]) > 0.10:
        shifts["win_rate"] = [a["win_rate"], b["win_rate"]]
    if a.get("tto_p50") and b.get("tto_p50") is not None and abs(b["tto_p50"] / a["tto_p50"] - 1) > 0.20:
        shifts["tto_p50"] = [a["tto_p50"], b["tto_p50"]]
    kinds = {f["kind"] for f in rep["findings"]} - {f["kind"] for f in old.get("findings", [])}
    return {"prev": prev[-1].name, "new_kinds": sorted(kinds), "stat_shifts": shifts}


def to_md(rep, game_dir=None):
    L = [rep["summary"], "", f"`{rep['build']}` | {rep['mode']} | {rep['engine']} | tier {rep['tier']} | {rep['at']}", ""]
    L += ["| severity | kind | seed | bot | t (s) | detail | shot |", "|---|---|---|---|---|---|---|"] + [
        f"| {f['severity']} | {f['kind']} | {f['seed']} | {f['bot']} | {f['t']} | {f['detail'].replace('|', '/')} | {f.get('shot') or ''} |"
        for f in rep["findings"]] if rep["findings"] else ["No findings."]
    s, g = rep["stats"], rep["regression"]
    L += ["", "## Stats", f"{s['label']}: {s['runs']} runs, win rate {s['win_rate']}, time to over p10/p50/p90 "
          f"{s['tto_p10']}/{s['tto_p50']}/{s['tto_p90']} s, deaths/min {s['deaths_per_min']}" if s else
          "None at tier 0 (no readable state). Add window.__game.state to get softlock checks and stats."]
    L += ["", "## Regression", f"vs {g['prev']}: new finding kinds {g['new_kinds'] or 'none'}, stat shifts "
          f"{g['stat_shifts'] or 'none'}" if g else f"No earlier {rep['mode']} report to compare."]
    if rep["mode"] == "milestone":
        L += ["", "## Claude's review of anomaly screenshots", "(pending)"]
    L += ["", rep["cannot_judge"]]
    try:
        learn = json.loads((game_dir / "studio.json").read_text("utf-8")).get("context") == "learn"
    except (OSError, ValueError, TypeError):
        learn = False
    if learn:
        L += ["", "## Rubric", "- Goal: <which experience goal or feature this playtest checks>",
              f"- Evidence: this report ({rep['verdict']}) and its findings", "- Met? (yes/no, the student fills this in):",
              "- Reflection: what did the bots catch that you missed, and what can only a human judge here?"]
    return "\n".join(L) + "\n"


def write_reports(rep, out_dir):
    out, stamp = Path(out_dir), time.strftime("%Y-%m-%d-%H%M")
    if (out / f"{stamp}-{rep['mode']}.json").exists():  # same minute: add seconds, which still sorts after it
        stamp = time.strftime("%Y-%m-%d-%H%M%S")
    game, base = out.resolve().parent, f"{stamp}-{rep['mode']}"
    out.mkdir(parents=True, exist_ok=True)
    rep["regression"] = regression(out, base + ".json", rep)
    for f in rep["findings"]:
        if f["severity"] == "FAIL" and f["_png"]:
            (out / "shots").mkdir(exist_ok=True)
            f["shot"] = f"shots/{stamp}-{f['kind']}-s{f['seed']}.png"
            (out / f["shot"]).write_bytes(f["_png"])
        del f["_png"]
    (out / f"{base}.json").write_text(json.dumps(rep, indent=1), "utf-8")
    (out / f"{base}.md").write_text(to_md(rep, game), "utf-8")
    if rep["mode"] == "milestone" and SHEET.is_file():
        try:
            sec = (game / "design" / "design.md").read_text("utf-8").split("## Experience goals", 1)[1].split("\n## ")[0]
        except (OSError, IndexError):
            sec = ""
        goals = "\n".join(f"{l.strip()}\n  - [ ] met  [ ] not met  [ ] waived. Evidence:"
                          for l in sec.splitlines() if l.strip().startswith("- "))
        sheet = SHEET.read_text("utf-8").replace("{{GOALS}}", goals or "- (no experience goals found in design/design.md)")
        (out / f"{stamp}-sheet.md").write_text(sheet.replace("{{BUILD}}", rep["build"]).replace("{{DATE}}", stamp[:10]), "utf-8")


# ---------- public API ----------
def run(build, mode="quick", bot=None, seeds=None, seconds=None, overrides=None,
        realtime=False, coop=False, out_dir=None, windowed=False):
    """Play `build` with bots; return the report dict. Raises SystemExit(2) on usage/environment errors.
    bot: idle|random|policy|mash|script:<path.json>. windowed (Godot only): screenshots instead of --headless."""
    if mode not in MODES:
        die(f"unknown mode {mode!r}: use one of {', '.join(MODES)}")
    if bot:
        check_bot(bot)
    seeds, seconds, overrides = seeds or MODES[mode][0], seconds or MODES[mode][1], list(overrides or [])
    path, _, query = str(build).partition("?")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(path)
        if root.suffix.lower() == ".zip" and root.is_file():
            zipfile.ZipFile(root).extractall(tmp)
            root = Path(tmp)
        if (root / "project.godot").is_file():
            engine, sess = "godot", godot_session(root, query, overrides, windowed)
        elif (root / "index.html").is_file():
            engine, sess = "web", web_session(root, query, overrides, realtime, coop)
        else:
            die(f"no index.html or project.godot in {path} (looked for a web export at its root, or a Godot project)")
        with sess as play:
            replay, main = None, []
            if mode not in ("boot", "sweep"):  # deterministic replay first: it also tells us the tier
                idle = [play(1, "idle", REPLAY_S)]
                replay = (idle, [], "final" if idle[0]["tier"] else "shot")
                if not idle[0]["boot"]:
                    idle.append(play(1, "idle", REPLAY_S))
                    if idle[0][replay[2]] is not None and idle[0][replay[2]] == idle[1][replay[2]]:
                        moves = [a for a in idle[0]["actions"] if a not in START_KEYS]
                        replay[1].extend(play(1, "hold:" + a, REPLAY_S) for a in moves[:2 if mode == "quick" else None])
            tier = replay and replay[0][0]["tier"]
            if not (replay and replay[0][0]["boot"]):
                bots = [bot] if bot else ["idle"] if mode == "boot" else ["policy"] if mode == "sweep" else \
                    ["random"] + (["policy"] if tier == 2 else [])
                main = [play(s, b, seconds) for s in range(1, seeds + 1) for b in bots]
                main = main[:1] if main[0]["boot"] else main
                tier = tier if replay else main[0]["tier"]
    tier = tier or 0
    findings = detect(main, replay, tier, mode)
    verdict = "FAIL" if any(f["severity"] == "FAIL" for f in findings) else "WARN" if findings else "PASS"
    runs = [{k: r[k] for k in ("seed", "bot", "seconds", "over", "won", "time_to_over", "final")} for r in main if not r["boot"]]
    rep = {"version": 1, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": mode, "engine": engine, "build": str(build),
           "tier": tier, "verdict": verdict, "summary": summarize(verdict, findings, len(runs), tier, bool(replay and replay[1])),
           "runs": runs, "findings": findings, "stats": stats_for(runs, tier), "overrides": overrides,
           "regression": None, "cannot_judge": CANNOT_JUDGE}
    if out_dir:
        write_reports(rep, out_dir)
    for f in findings:
        f.pop("_png", None)
    return rep


# ---------- CLI ----------
def parse_override(spec):
    """'data/enemies.csv:bat.speed=4' (file form) or 'player_speed=5' (bundled form). Values parse as JSON if they can."""
    lhs, eq, val = spec.partition("=")
    if not eq or not lhs:
        die(f"bad --override {spec!r}: use FILE:KEY=VALUE or NAME=VALUE")
    file, _, key = lhs.rpartition(":")
    try:
        val = json.loads(val)
    except ValueError:
        pass
    return {"name": key, "file": file or None, "key": key, "value": val}


def stub(dirpath, name, body):
    """Fake executable `name` in dirpath that runs python source `body` with this interpreter (roadmap C7)."""
    py = dirpath / f"{name}_stub.py"
    py.write_text(body, "utf-8")
    if os.name == "nt":
        exe = dirpath / f"{name}.cmd"
        exe.write_text(f'@"{sys.executable}" "{py}" %*\n', "utf-8")
    else:
        exe = dirpath / name
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{py}" "$@"\n', "utf-8")
        exe.chmod(0o755)
    return exe


# Fake godot: logs its argv, speaks the probe protocol (x moves by the player_speed knob), and writes a tiny
# PNG per step plus PROBE_SHOT when shots= is given.
GODOT_STUB = r'''import json, struct, sys, zlib
from pathlib import Path
a = sys.argv[1:]
with open(Path(__file__).with_name("argv.jsonl"), "a") as f:
    f.write(json.dumps(a) + "\n")
u = dict(x.lstrip("-").split("=", 1) for x in a[a.index("--") + 1:] if "=" in x)
def png(v):
    ch = lambda k, d: struct.pack(">I", len(d)) + k + d + struct.pack(">I", zlib.crc32(k + d))
    return (b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + ch(b"IDAT", zlib.compress(bytes([0, v % 256, 0, 0]))) + ch(b"IEND", b""))
print("PROBE_INFO " + json.dumps({"bot": True, "actions": ["ui_left", "ui_right", "ui_accept"]}))
for i in range(1, int(u["frames"]) // 30 + 1):
    t = i / 2
    print("PROBE " + json.dumps({"t": t, "state": {"over": False, "x": t * float(u.get("player_speed", 1))}, "keys": []}))
    if u.get("shots"):
        p = Path(u["shots"]) / f"{i * 30}.png"
        p.write_bytes(png(i))
        print(f"PROBE_SHOT {p}")
print("PROBE_END")
'''


def selftest_godot_stub():
    """Godot transport against a fake godot: always runs, never touches a real binary."""
    with tempfile.TemporaryDirectory() as tmp:
        d, old = Path(tmp), os.environ.get("GODOT")
        (d / "project.godot").write_text("config_version=5\n", "utf-8")
        os.environ["GODOT"] = str(stub(d, "godot", GODOT_STUB))
        argv = lambda: json.loads((d / "argv.jsonl").read_text("utf-8").splitlines()[-1])
        try:
            r = run(str(d), mode="sweep", seeds=1, seconds=2, overrides=[parse_override("player_speed=5")])
            a = argv()
            assert "--headless" in a and "--player_speed=5" in a and r["tier"] == 2 and r["verdict"] == "PASS", (a, r)
            run(str(d), mode="sweep", seeds=1, seconds=2, windowed=True)
            a = argv()
            assert "--headless" not in a and any(x.startswith("shots=") for x in a), a
            with godot_session(d, "", [], windowed=True) as play:
                rec = play(1, "random", 2)
            assert len(rec["shots"]) == 4 and rec["png"][:4] == b"\x89PNG" and rec["shot"], rec["shots"]
            run(str(d), mode="sweep", bot="mash", seeds=1, seconds=1)
            assert "bot=mash" in argv(), argv()
            sc = d / "walk.json"
            sc.write_text(json.dumps([{"t": 0, "keys": ["ui_right"]}]), "utf-8")
            r = run(str(d), mode="sweep", bot=f"script:{sc}", seeds=1, seconds=1)
            a = argv()
            assert "bot=script" in a and f"script={sc.resolve()}" in a and r["runs"][0]["bot"] == "script:walk.json", a
            os.environ["GODOT"] = str(d / "missing" / "godot.exe")  # a stale GODOT: exit 2, not a traceback
            try:
                with redirect_stderr(io.StringIO()):
                    run(str(d), mode="boot")
                raise AssertionError("missing GODOT accepted")
            except SystemExit as e:
                assert e.code == 2
        finally:
            if old is None:
                os.environ.pop("GODOT", None)
            else:
                os.environ["GODOT"] = old
    print("ok (m) godot stub: knobs as --name=value, --windowed shots, mash and script bots reach probe.gd")


# Fake Construct/GDevelop runtimes around the real adapters.md snippets: arrows move the score.
ADAPTER_PAGE = """<!doctype html><canvas id=c width=200 height=100></canvas><script>
const V = {GameOver: false, Won: false, Score: 0, Paused: false}, keys = {};
addEventListener('keydown', e => { keys[e.key] = true; }); addEventListener('keyup', e => { keys[e.key] = false; });
(function f() { V.Score += (keys.ArrowRight ? 1 : 0) - (keys.ArrowLeft ? 1 : 0); const g = c.getContext('2d');
  g.fillStyle = '#000'; g.fillRect(0, 0, 200, 100); g.fillStyle = '#fff'; g.fillRect(100 + V.Score % 90, 45, 9, 9);
  requestAnimationFrame(f); })();
globalThis.runOnStartup = cb => cb({globalVars: V});
const runtimeScene = {getGame: () => ({getVariables: () => ({get: n => ({getAsBoolean: () => !!V[n], getAsNumber: () => +V[n]})})})};
</script><script>
__SNIPPET__
</script>"""


def selftest_adapters(have_pw):
    """Run the Construct and GDevelop snippets from adapters.md in a fake engine page (no fixture needed)."""
    if not have_pw:
        print(f"SKIP adapters: playwright not installed for {sys.executable}")
        return
    md = (HERE.parent / "skills" / "playtest" / "adapters.md").read_text("utf-8")
    for tag in ("construct", "gdevelop"):
        with tempfile.TemporaryDirectory() as tmp:
            snippet = md.split(f"```js {tag}\n", 1)[1].split("```", 1)[0]
            (Path(tmp) / "index.html").write_text(ADAPTER_PAGE.replace("__SNIPPET__", snippet), "utf-8")
            r = run(tmp, mode="quick", seeds=1, seconds=4, bot="random")
            assert r["tier"] >= 1 and r["verdict"] != "FAIL", (tag, r["summary"], r["findings"])
            print(f"ok (n) {tag} adapter: {r['summary']}")


def selftest(game=None):
    game = Path(game or HERE.parent / "examples" / "dodge-web")
    try:
        import playwright  # noqa: F401
        have_pw, why = True, None if (game / "index.html").is_file() else f"{game} missing"
    except ImportError:
        have_pw, why = False, f"playwright not installed for {sys.executable}"
    if why:
        print(f"SKIP web: {why}")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            g, t0 = Path(tmp) / "game", time.time()
            shutil.copytree(game, g, ignore=shutil.ignore_patterns("playtests", "build"))
            kinds = lambda r: {f["kind"]: f["severity"] for f in r["findings"]}

            def ok(name, cond, r):
                assert cond, (name, r["summary"], r["findings"])
                print(f"ok {name}: {r['summary']}")
            r = run(str(g), seeds=2, seconds=25, out_dir=g / "playtests")
            ok("(a) clean", "FAIL" not in kinds(r).values() and r["tier"] == 2 and r["runs"] and list(r) == KEYS
               and r["stats"]["label"] == LABELS[2], r)
            md = next((g / "playtests").glob("*-quick.md")).read_text("utf-8")
            js = json.loads(next((g / "playtests").glob("*-quick.json")).read_text("utf-8"))
            ok("(i) out_dir", md.splitlines()[0] == r["summary"] and list(js) == KEYS, r)
            calm = [parse_override("data/enemies.csv:*.spawn_ms=999999")]  # nothing spawns, so nothing dies before 8 s
            r = run(f"{g}?bug=softlock", bot="random", seeds=1, seconds=15, overrides=calm)
            ok("(b) softlock", kinds(r).get("softlock") == "FAIL", r)
            r = run(f"{g}?bug=crash", bot="random", seeds=1, seconds=8)
            ok("(c) crash", kinds(r).get("crash") == "FAIL", r)
            r = run(f"{g}?bug=deadinput", bot="random", seeds=1, seconds=3)
            ok("(d) deadinput", kinds(r).get("dead_input") == "FAIL", r)
            r = run(f"{g}?noprobe", bot="random", seeds=1, seconds=4)
            ok("(e) noprobe", r["tier"] == 0 and r["stats"] is None, r)
            r = run(f"{g}?nobot", seeds=1, seconds=4)
            ok("(f) nobot", r["tier"] == 1 and r["stats"]["label"] == LABELS[1], r)
            ov = [parse_override("data/enemies.csv:bat.speed=4")]
            a, r = run(str(g), mode="sweep", seeds=1, seconds=6), run(str(g), mode="sweep", seeds=1, seconds=6, overrides=ov)
            ok("(g) csv override", r["overrides"] == ov and a["runs"][0]["final"] != r["runs"][0]["final"], r)
            z = Path(tmp) / "game.zip"
            with zipfile.ZipFile(z, "w") as zf:
                for f in g.rglob("*"):
                    if f.is_file() and "playtests" not in f.parts:
                        zf.write(f, f.relative_to(g).as_posix())
            r = run(str(z), mode="boot")
            ok(f"(h) zip boot [{time.time() - t0:.0f}s]", r["verdict"] == "PASS", r)
            r = run(str(g), bot="mash", seeds=1, seconds=5)
            ok("(k) mash", r["verdict"] != "FAIL" and r["runs"][0]["bot"] == "mash", r)
            for side in ("Left", "Right"):
                (Path(tmp) / f"{side}.json").write_text(json.dumps([{"t": 0, "keys": [f"Arrow{side}"]}]), "utf-8")
            a, r = (run(str(g), mode="sweep", bot=f"script:{Path(tmp) / f'{s}.json'}", seeds=1, seconds=3)
                    for s in ("Left", "Right"))
            ok(f"(l) script [{time.time() - t0:.0f}s]", a["runs"][0]["final"] != r["runs"][0]["final"]
               and r["runs"][0]["bot"] == "script:Right.json", r)
            (Path(tmp) / "godot-keys.json").write_text('[{"t": 0, "keys": ["ui_right"]}]', "utf-8")
            try:  # a typo in the human's script is exit 2, never a crash FAIL blamed on the game
                with redirect_stderr(io.StringIO()):
                    run(str(g), mode="sweep", bot=f"script:{Path(tmp) / 'godot-keys.json'}", seeds=1, seconds=1)
                raise AssertionError("unknown script key accepted")
            except SystemExit as e:
                assert e.code == 2
    selftest_adapters(have_pw)
    selftest_godot_stub()
    gd = HERE.parent / "examples" / "dodge-godot"
    if not godot_exe() or not (gd / "project.godot").is_file():
        print("SKIP godot: not installed (experimental)")
    else:
        r = run(str(gd), bot="random", seeds=1, seconds=10)
        assert r["verdict"] != "FAIL" and r["tier"] >= 1, r["summary"]
        r2 = run(f"{gd}?bug=softlock", bot="random", seeds=1, seconds=15)
        assert any(f["kind"] == "softlock" for f in r2["findings"]), r2["summary"]
        print(f"ok (j) godot: {r['summary']} / {r2['summary']}")
    bases = [Path(p) / "Godot" for p in [os.environ.get("APPDATA")] if p] + [
        Path.home() / ".local/share/godot", Path.home() / "Library/Application Support/Godot"]
    if not (godot_exe() and have_pw and (gd / "project.godot").is_file()
            and any(b.glob("export_templates/*/web_nothreads_release.zip") for b in bases)):
        print("SKIP godot web export: no godot binary or cached web templates")
    else:
        with tempfile.TemporaryDirectory() as tmp:  # copy first: the export writes .godot/ into the project
            proj, web = Path(tmp) / "proj", Path(tmp) / "web"
            shutil.copytree(gd, proj, ignore=shutil.ignore_patterns(".godot", "build"))
            web.mkdir()
            subprocess.run([godot_exe(), "--headless", "--path", str(proj), "--export-release", "Web",
                            str(web / "index.html")], capture_output=True, timeout=600)
            r = run(str(web), mode="boot")
            assert r["verdict"] == "PASS", r["summary"]
            print(f"ok (o) godot web export: {r['summary']}")
    with redirect_stderr(io.StringIO()):  # die() also prints; keep the selftest output clean
        for bad in ('{"t": 0}', '[{"t": 2, "keys": []}, {"t": 1, "keys": []}]', '[{"t": 0, "keys": "Enter"}]', "nope"):
            f = Path(tempfile.gettempdir()) / "playbench-bad-script.json"
            f.write_text(bad, "utf-8")
            try:
                check_bot(f"script:{f}")
                raise AssertionError(f"bad script accepted: {bad}")
            except SystemExit as e:
                assert e.code == 2
            finally:
                f.unlink()
        try:
            run(".", bot="dance")
            raise AssertionError("bad bot accepted")
        except SystemExit as e:
            assert e.code == 2
    assert stuck([(0, "a", 1, 0), (3, "a", 0, 0), (5.1, "a", 0, 0)]) == 0
    fake = [dict(bot="policy", over=True, won=False, time_to_over=t, seconds=t) for t in (3, 21)]
    assert stats_for(fake, 2)["tto_p10"] >= 3 and stats_for(fake, 2)["tto_p90"] <= 21
    assert stuck([(0, "a", 1, 1), (6, "a", 1, 1)]) is None and stuck([(0, "a", 0, 0), (6, "a", 0, 0)]) is None
    print("ok playtest")


def main(argv=None):
    sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(prog="playtest.py", description="Bots play your real game build.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="playtest a build: a dir or .zip with index.html, or a Godot project")
    r.add_argument("build")
    r.add_argument("--mode", choices=list(MODES), default="quick")
    r.add_argument("--bot", help="idle, random, policy, mash or script:<path.json> (default: by mode)")
    r.add_argument("--seeds", type=int)
    r.add_argument("--seconds", type=float)
    r.add_argument("--override", action="append", default=[], metavar="F:K=V|NAME=V")
    r.add_argument("--realtime", action="store_true", help="real time instead of page.clock (threaded wasm builds)")
    r.add_argument("--coop", action="store_true", help="send COOP/COEP headers (SharedArrayBuffer builds)")
    r.add_argument("--windowed", action="store_true", help="Godot only: run with a window so screenshots are taken")
    r.add_argument("--out", help="write <stamp>-<mode>.json/.md and shots/ here (use playtests)")
    sub.add_parser("selftest").add_argument("game", nargs="?")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return selftest(a.game)
    rep = run(a.build, a.mode, a.bot, a.seeds, a.seconds, [parse_override(o) for o in a.override], a.realtime, a.coop, a.out, a.windowed)
    print(to_md(rep, Path(a.out).resolve().parent if a.out else None), end="")
    return 1 if rep["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
