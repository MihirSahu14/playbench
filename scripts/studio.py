#!/usr/bin/env python3
"""playbench studio: detect the engine, init studio.json + gates.md, print status.

Usage: studio.py detect|init|status|selftest [game_dir] [flags]
Stdlib only. Never writes a ticked box into gates.md.
"""
import argparse, contextlib, functools, io, json, os, re, shutil, subprocess, sys, tempfile
from datetime import datetime
from pathlib import Path

PROFILE = {
    "jam": {"stages": ["playable", "submitted"],
            "sizes": {"quick": (3, 30), "milestone": (5, 60), "final": (5, 60)},
            "debt_quick": 3, "debt_human": None, "balance": False, "targets": ["itch", "web"]},
    "hobby": {"stages": ["prototype", "slice", "release"], "debt_human": 20, "targets": ["itch", "steam", "web"]},
    "team": {"stages": ["prototype", "slice", "alpha", "beta", "release"], "debt_human": 15,
             "targets": ["steam", "itch", "web"]},
    "learn": {"stages": ["prototype", "submitted"], "debt_human": 20, "targets": ["itch", "web"]},
}
for _c in ("hobby", "team", "learn"):  # ponytail: shared non-jam defaults, filled once
    PROFILE[_c].update(sizes={"quick": (3, 30), "milestone": (8, 60), "final": (8, 60)}, debt_quick=5, balance=True)

REQUIRED = {"prototype": ["quick"], "playable": ["quick"], "slice": ["quick", "milestone"],
            "alpha": ["quick", "milestone"], "beta": ["quick", "milestone", "final"],
            "release": ["quick", "milestone", "final"], "submitted": ["quick", "final"]}

_PROTO = ["Latest quick playtest is PASS", "A human played it and saved playtests/<date>-human.md"]
_SHIP = ["Final playtest is PASS", "ship artgate passes", "Store/itch page reviewed by a human", "I approve this release"]
BOXES = {
    "prototype": _PROTO + ["Decision: GO is written in design/design.md"],
    "playable": _PROTO,  # jam only, so no Decision box
    "slice": ["Milestone playtest PASS or every WARN triaged",
              "Every experience goal marked met or waived on a human sheet"],
    "alpha": ["Every must-list feature is in the build", "Milestone playtest shows no new FAIL kinds"],
    "beta": ["art/PLACEHOLDERS.json is empty or every entry is covered by disclosure.md",
             "Final playtest run on the packaged build"],
    "release": _SHIP, "submitted": _SHIP,
}
GATES_NOTE = "Only humans tick these boxes. Claude never ticks them; ship gate shows who did."
ALLOWED = "explain,review,status,playtest-T0,artgate"
PROBE_PY = "import sys,importlib.util;print(sys.executable);print(importlib.util.find_spec('playwright') is not None)"


def detect(d):
    d = Path(d)
    if (d / "project.godot").exists():
        return "godot", "."
    for sub in (".", "build", "dist", "export", "public", "web"):
        if (d / sub / "index.html").exists():
            return "web", sub
    pkg = d / "package.json"
    if pkg.exists() and re.search(r'"(phaser|three|pixi\.js|@pixi/[\w-]+|kaboom)"', pkg.read_text("utf-8", "ignore")):
        return "web", "."
    return "unknown", "."


def parse_gates(text):
    """[(stage, [(ticked, box)])] in file order."""
    out = []
    for line in text.splitlines():
        m = re.match(r"##\s+(\S+)", line)
        if m:
            out.append((m[1], []))
            continue
        m = re.match(r"\s*- \[([ xX])\]\s*(.*)", line)
        if m and out:
            out[-1][1].append((m[1] != " ", m[2].strip()))
    return out


def current_stage(text):
    for stage, boxes in parse_gates(text):
        unticked = [b for ticked, b in boxes if not ticked]
        if unticked:
            return stage, unticked
    return "shipped", []


@functools.lru_cache(None)
def find_run():
    """(launcher as typed, has_playwright). First launcher with playwright wins, else first that works."""
    works = []
    for cand in (["python"], ["py", "-3"], ["python3"]):
        try:
            r = subprocess.run(cand + ["-c", PROBE_PY], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            continue
        lines = r.stdout.strip().splitlines()
        if r.returncode or len(lines) < 2:  # WindowsApps stub prints nothing
            continue
        if lines[-1].strip() == "True":
            return " ".join(cand), True
        works.append(" ".join(cand))
    return (works[0] if works else "NONE"), False


def commits_since(d, since):
    """Commits touching the game dir since `since` (all if None); None when not a git repo."""
    if subprocess.run(["git", "-C", str(d), "rev-parse", "--git-dir"], capture_output=True).returncode:
        return None
    cmd = ["git", "-C", str(d), "rev-list", "--count"] + ([f"--since={since}"] if since else []) + ["HEAD", "--", "."]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return int(r.stdout) if r.returncode == 0 and r.stdout.strip().isdigit() else 0  # no HEAD yet = 0


def debt(d, pattern, limit, since_of):
    files = sorted((Path(d) / "playtests").glob(pattern))
    since = None
    if files:
        try:
            since = since_of(files[-1])
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
    n = commits_since(d, since)
    if n is None:
        return "n/a (not a git repo)", False
    if limit is None:
        return f"{n}/-", False
    over = n >= limit
    return f"{n}/{limit}" + (" WARN" if over else ""), over


def hours_left(iso):
    dl = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    h = int((dl - datetime.now(dl.tzinfo)).total_seconds() // 3600)
    return f"{h}h left" + (" (passed)" if h < 0 else "")


def status(d):
    d = Path(d).resolve()
    run, pw = find_run()
    print(f"RUN={run}")
    print(f"PLUGIN={Path(__file__).resolve().parents[1]}")
    print(f"PLAYWRIGHT={'yes' if pw else 'no'}")
    install = (f"{run} -m pip install playwright && {run} -m playwright install chromium" if run != "NONE"
               else "install Python 3.11+ from python.org, then rerun status")
    if not pw:
        print(f"INSTALL={install}")
    print(f"GODOT={os.environ.get('GODOT') or shutil.which('godot') or 'none'}")
    print(f"GAME={d}")
    sj = d / "studio.json"
    if not sj.exists():
        engine, build = detect(d)
        print(f"INIT=no\nENGINE={engine}\nBUILD={build}")
        print("NEXT=run studio init (the studio skill asks a few short questions)")
        return 0
    try:
        cfg = json.loads(sj.read_text("utf-8"))
        p = PROFILE[cfg["context"]]
    except (ValueError, KeyError, TypeError) as e:
        print(f"INIT=broken\nNEXT=fix studio.json ({e!r}) or rerun init --force")
        return 0  # exit 0 so the SKILL `||` chain does not fall through to "no Python"
    gates = d / "gates.md"
    stage, unticked = current_stage(gates.read_text("utf-8")) if gates.exists() else ("unknown", [])
    req = REQUIRED.get(stage, [])
    dq, dq_over = debt(d, "*-quick.json", p["debt_quick"],
                       lambda f: json.loads(f.read_text("utf-8"))["at"])
    dh, _ = debt(d, "*-human.md", p["debt_human"],
                 lambda f: re.match(r"\d{4}-\d{2}-\d{2}", f.name)[0])
    print("INIT=yes")
    print(f"CONTEXT={cfg['context']}\nCODING={cfg.get('coding', 2)}\nAI_POLICY={cfg.get('ai_policy', '-')}")
    print(f"ENGINE={cfg.get('engine', 'unknown')}\nBUILD={cfg.get('build_dir', '.')}")
    print(f"PLATFORMS={','.join(cfg.get('platforms', []))}")
    print(f"STAGE={stage}\nREQUIRED={','.join(req) or '-'}")
    print("SIZES=" + " ".join(f"{m}:{s}x{t}" for m, (s, t) in p["sizes"].items()))
    print(f"DEBT_QUICK={dq}\nDEBT_HUMAN={dh}")
    try:
        print(f"DEADLINE={hours_left(cfg['deadline_at']) if cfg.get('deadline_at') else '-'}")
    except (ValueError, TypeError, AttributeError):  # hand-edited studio.json must not crash status
        print("DEADLINE=unreadable deadline_at")
    print(f"BALANCE={'on' if p['balance'] else 'off'}")
    if cfg.get("ai_policy") == "banned":
        print(f"ALLOWED={ALLOWED}")
    print("UNTICKED:")
    for b in unticked:
        print(f"  - {b}")
    missing = [m for m in req[1:] if not list((d / "playtests").glob(f"*-{m}.json"))]
    if not gates.exists():
        nxt = "gates.md is missing: rerun studio init --force"
    elif stage == "shipped":
        nxt = "every gate is ticked: run /playbench:ship for the upload command"
    elif not (d / "design" / "design.md").exists():
        nxt = "run /playbench:design to write the one-page design"
    elif not pw and cfg.get("engine") == "web":
        nxt = f"install playwright (ask first): {install}"
    elif dq_over:
        nxt = "run a quick playtest (/playbench:playtest) before building more"
    elif missing:
        nxt = f"run a {missing[0]} playtest (/playbench:playtest) before ticking {stage} boxes"
    else:
        nxt = "build the next must-list feature, then run a quick playtest"
    print(f"NEXT={nxt}")
    return 0


def init(a):
    d = Path(a.dir)
    sj, gm = d / "studio.json", d / "gates.md"
    if not a.force and (sj.exists() or gm.exists()):
        print(f"refusing: {'studio.json' if sj.exists() else 'gates.md'} exists in {d}; pass --force to overwrite")
        return 1
    p = PROFILE[a.context]
    if a.ai_policy and a.context != "learn":
        sys.exit("--ai-policy is only for --context learn")
    if a.member and a.context != "team":
        sys.exit("--member is only for --context team")
    plats = a.platforms.split(",") if a.platforms else p["targets"][:1]
    if set(plats) - set(p["targets"]):  # Steam is hidden for jam and learn
        sys.exit(f"--platforms for {a.context} must be from {','.join(p['targets'])}, got {a.platforms}")
    try:
        a.deadline and hours_left(a.deadline)
    except ValueError:
        sys.exit(f"--deadline must be ISO 8601 like 2026-10-20T18:00, got {a.deadline}")
    team = []
    for m in a.member or []:
        name, owns, stages = (m.split(":", 2) + ["", ""])[:3]
        st = [s for s in stages.split(",") if s]
        if not name or set(st) - set(p["stages"]):
            sys.exit(f"bad --member {m!r}: use Name:owns:stage1,stage2 with stages from {','.join(p['stages'])}")
        team.append({"name": name, "owns": owns, "gates": st})
    engine, build = detect(d)
    cfg = {"context": a.context, "coding": a.coding, "engine": a.engine or engine,
           "build_dir": a.build_dir or build, "platforms": plats, "deadline_at": a.deadline,
           "hours_per_week": a.hours, "weeks": a.weeks, "team": team or None,
           "ai_policy": (a.ai_policy or "disclose") if a.context == "learn" else None, "itch": a.itch}
    cfg = {k: v for k, v in cfg.items() if v is not None}
    lines = ["# Gates", "", GATES_NOTE]
    for stage in p["stages"]:
        owner = ""
        if a.context == "team":
            owner = f" (owner: {', '.join(t['name'] for t in team if stage in t['gates']) or 'unassigned'})"
        lines += ["", f"## {stage}"] + [f"- [ ] {b}{owner}" for b in BOXES[stage]]
    d.mkdir(parents=True, exist_ok=True)
    sj.write_text(json.dumps(cfg, indent=1) + "\n", "utf-8", newline="\n")
    gm.write_text("\n".join(lines) + "\n", "utf-8", newline="\n")
    gi = d / ".gitignore"
    old = gi.read_text("utf-8") if gi.exists() else ""
    if "playtests/shots/" not in old.splitlines():
        gi.write_text(old + ("" if old.endswith("\n") or not old else "\n") + "playtests/shots/\n", "utf-8", newline="\n")
    print(f"wrote {sj} and {gm} ({a.context}: {' -> '.join(p['stages'])}). Next: /playbench:design")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="studio.py", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("detect", "init", "status", "selftest"):
        sp = sub.add_parser(name)
        sp.add_argument("dir", nargs="?", default=".")
        if name == "init":
            sp.add_argument("--context", required=True, choices=list(PROFILE))
            sp.add_argument("--coding", type=int, default=2, choices=[1, 2, 3])
            sp.add_argument("--engine")
            sp.add_argument("--build-dir")
            sp.add_argument("--platforms", help="comma list of itch,steam,web")
            sp.add_argument("--deadline", help="ISO 8601, e.g. 2026-10-20T18:00")
            sp.add_argument("--hours", type=float, help="hours per week")
            sp.add_argument("--weeks", type=float)
            sp.add_argument("--ai-policy", choices=["open", "disclose", "banned"])
            sp.add_argument("--itch", help="user/game")
            sp.add_argument("--member", action="append", help='"Name:owns:stage1,stage2" (repeatable)')
            sp.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "detect":
        engine, build = detect(a.dir)
        print(f"ENGINE={engine}\nBUILD={build}")
        return 0
    if a.cmd == "init":
        return init(a)
    if a.cmd == "status":
        return status(a.dir)
    return selftest()


def selftest():
    def call(*argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(list(argv))
        return code, buf.getvalue()

    def kv(out):
        return dict(l.split("=", 1) for l in out.splitlines() if "=" in l and not l.startswith(" "))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # detect
        (tmp / "g").mkdir(); (tmp / "g" / "project.godot").write_text("config_version=5\n")
        (tmp / "w" / "build").mkdir(parents=True); (tmp / "w" / "build" / "index.html").write_text("<canvas>")
        assert kv(call("detect", str(tmp / "g"))[1])["ENGINE"] == "godot"
        assert kv(call("detect", str(tmp / "w"))[1]) == {"ENGINE": "web", "BUILD": "build"}
        assert detect(tmp) == ("unknown", ".")
        ex = Path(__file__).resolve().parents[1] / "examples"
        if (ex / "dodge-web" / "index.html").exists():
            assert detect(ex / "dodge-web")[0] == "web"
        if (ex / "dodge-godot" / "project.godot").exists():
            assert detect(ex / "dodge-godot") == ("godot", ".")

        # init: every context x coding
        for ctx, p in PROFILE.items():
            for coding in (1, 2, 3):
                d = tmp / f"{ctx}{coding}"
                extra = {"jam": ["--deadline", "2099-01-01T18:00"], "hobby": ["--hours", "5", "--weeks", "8"],
                         "team": ["--member", "Ana:code:prototype,slice", "--member", "Bo:art:release"],
                         "learn": ["--ai-policy", "banned"]}[ctx]
                code, _ = call("init", str(d), "--context", ctx, "--coding", str(coding), *extra)
                assert code == 0, (ctx, coding)
                cfg = json.loads((d / "studio.json").read_text("utf-8"))
                assert cfg["context"] == ctx and cfg["coding"] == coding and None not in cfg.values()
                assert set(cfg) <= {"context", "coding", "engine", "build_dir", "platforms", "deadline_at",
                                    "hours_per_week", "weeks", "team", "ai_policy", "itch", "steam"}
                g = (d / "gates.md").read_text("utf-8")
                assert "[x]" not in g.lower() and GATES_NOTE in g
                assert [s for s, _ in parse_gates(g)] == p["stages"], (ctx, g)
                assert ("Decision: GO" in g) == (ctx != "jam")
                if ctx == "team":
                    assert "(owner: Ana)" in g and "(owner: Bo)" in g and "(owner: unassigned)" in g
                    assert all("(owner: " in l for l in g.splitlines() if l.startswith("- ["))
                assert "playtests/shots/" in (d / ".gitignore").read_text("utf-8")
        assert call("init", str(tmp / "jam1"), "--context", "jam")[0] == 1
        assert call("init", str(tmp / "jam1"), "--context", "jam", "--force")[0] == 0
        assert (tmp / "jam1" / ".gitignore").read_text("utf-8").count("playtests/shots/") == 1
        for ctx in ("jam", "learn"):  # Steam hidden
            try:
                call("init", str(tmp / "nosteam"), "--context", ctx, "--platforms", "itch,steam")
                raise AssertionError(f"{ctx} accepted steam")
            except SystemExit:
                pass
        cfg = json.loads((tmp / "jam2" / "studio.json").read_text("utf-8"))
        (tmp / "jam2" / "studio.json").write_text(json.dumps(dict(cfg, deadline_at=5)), "utf-8")
        assert kv(call("status", str(tmp / "jam2"))[1])["DEADLINE"] == "unreadable deadline_at"
        (tmp / "jam2" / "studio.json").write_text(json.dumps(cfg), "utf-8")

        # stage derivation by editing text, as a human would
        g = (tmp / "hobby1" / "gates.md").read_text("utf-8")
        assert current_stage(g)[0] == "prototype" and len(current_stage(g)[1]) == 3
        head, rest = g.split("## slice")
        g2 = head.replace("- [ ]", "- [x]") + "## slice" + rest
        assert current_stage(g2) == ("slice", BOXES["slice"])
        assert current_stage(g.replace("- [ ]", "- [X]")) == ("shipped", [])

        # status: every key, ALLOWED only under banned, debt n/a outside git
        keys = ["RUN", "PLUGIN", "PLAYWRIGHT", "GODOT", "GAME", "INIT", "CONTEXT", "CODING", "AI_POLICY", "ENGINE",
                "BUILD", "PLATFORMS", "STAGE", "REQUIRED", "SIZES", "DEBT_QUICK", "DEBT_HUMAN", "DEADLINE",
                "BALANCE", "NEXT"]
        outside_git = commits_since(tmp, None) is None  # temp dir must not sit inside a repo
        for ctx in PROFILE:
            out = call("status", str(tmp / f"{ctx}2"))[1]
            st = kv(out)
            assert all(k in st for k in keys) and "UNTICKED:" in out, (ctx, out)
            assert st["RUN"] in ("python", "py -3", "python3", "NONE") and ("INSTALL" in st) == (st["PLAYWRIGHT"] == "no")
            assert ("ALLOWED" in st) == (ctx == "learn") and st["STAGE"] == PROFILE[ctx]["stages"][0]
            assert "run /playbench:design" in st["NEXT"]
            if outside_git:
                assert st["DEBT_QUICK"].startswith("n/a")
        assert kv(call("status", str(tmp / "jam2"))[1])["DEADLINE"].endswith("h left")
        assert kv(call("status", str(tmp / "jam2"))[1])["SIZES"] == "quick:3x30 milestone:5x60 final:5x60"
        empty = kv(call("status", str(tmp / "w"))[1])
        assert empty["INIT"] == "no" and empty["ENGINE"] == "web" and "init" in empty["NEXT"]

        # debt in a real temp git repo
        if shutil.which("git") and outside_git:
            r = tmp / "repo"
            call("init", str(r), "--context", "hobby")
            (r / "design").mkdir(); (r / "design" / "design.md").write_text("# x\n")
            git = ["git", "-C", str(r), "-c", "user.name=t", "-c", "user.email=t@t"]
            subprocess.run(git + ["init", "-q"], check=True)
            for i in range(3):
                (r / f"f{i}.txt").write_text(str(i))
                subprocess.run(git + ["add", "-A"], check=True)
                subprocess.run(git + ["commit", "-qm", f"c{i}"], check=True)
            assert kv(call("status", str(r))[1])["DEBT_QUICK"] == "3/5"
            (r / "playtests").mkdir()
            (r / "playtests" / "2000-01-01-0000-quick.json").write_text('{"at":"2000-01-01T00:00:00"}')
            st = kv(call("status", str(r))[1])
            assert st["DEBT_QUICK"] == "3/5" and st["DEBT_HUMAN"] == "3/20", st
            (r / "playtests" / "2099-01-01-0000-quick.json").write_text('{"at":"2099-01-01T00:00:00"}')
            (r / "playtests" / "2099-01-01-human.md").write_text("ok")
            st = kv(call("status", str(r))[1])
            assert st["DEBT_QUICK"] == "0/5" and st["DEBT_HUMAN"] == "0/20", st
            assert "build the next must-list feature" in st["NEXT"], st
        else:
            print("SKIP debt: git missing or temp dir inside a repo")
    print("ok studio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
