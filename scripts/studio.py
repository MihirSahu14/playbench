#!/usr/bin/env python3
"""playbench studio: detect the engine, init studio.json + gates.md, print status.

Usage: studio.py detect|init|status|aiuse|selftest [game_dir] [flags]
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
PROBE_PY = ("import os,sys,sysconfig,importlib.util;print(sys.executable);print(sys.version_info>=(3,11));"
            "print(os.path.exists(os.path.join(sysconfig.get_path('stdlib'),'EXTERNALLY-MANAGED')));"
            "print(importlib.util.find_spec('playwright') is not None)")
# ponytail: Claude Code sets CLAUDE_PLUGIN_DATA for plugins; PLAYBENCH_DATA or ~/.playbench covers every other agent
DATA = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or os.environ.get("PLAYBENCH_DATA") or Path.home() / ".playbench")
VENV = DATA / "venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
LOOPS = ["design", "build", "test", "balance", "iterate", "log", "ship"]
SINCE = {"playtests": "playtests/*.json", "human": "playtests/*-human.md", "feedback": "feedback/*.md",
         "balance": "balance/*.md", "telemetry": "telemetry/*-report.md"}
# playbench's own records and any .md are not game changes: committing a report or a session log adds no debt
NOT_GAME = ("playtests/", "balance/", "design/", "feedback/", "telemetry/", "store/", "steam/", "build/upload/")
NOT_GAME_FILES = ("studio.json", "art/PLACEHOLDERS.json", ".gitignore", "build/.gitignore", "build/itch.zip", "netlify.toml")


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
def probe(*cmd):
    """(works, externally_managed, has_playwright) for one interpreter command. Cached, so status reuses it."""
    exe = shutil.which(cmd[0])  # PATH like the user's shell; bare CreateProcess would try our own python's folder first
    if not exe:
        return False, False, False
    try:
        r = subprocess.run([exe, *cmd[1:], "-c", PROBE_PY], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False, False, False
    lines = [l.strip() for l in r.stdout.strip().splitlines()]
    if r.returncode or len(lines) < 4 or lines[-3] != "True":  # WindowsApps stub prints nothing; < 3.11 skipped
        return False, False, False
    return True, lines[-2] == "True", lines[-1] == "True"


@functools.lru_cache(None)
def find_run():
    """(launcher as typed, has_playwright). First launcher with playwright wins, then the plugin venv, else first that works."""
    works = []
    for cand in (["python"], ["py", "-3"], ["python3"]):
        ok, _, pw = probe(*cand)
        if ok and pw:
            return " ".join(cand), True
        if ok:
            works.append(" ".join(cand))
    # ponytail: an absolute RUN path does not match the SKILLs' Bash(python:*) allowed-tools, so venv users get permission prompts
    if VENV_PY.exists() and probe(str(VENV_PY))[2]:
        return f'"{VENV_PY.as_posix()}"', True
    return (works[0] if works else "NONE"), False


def install_line(run, managed, venv_py):
    """The INSTALL text: a pip line, or a venv recipe when pip refuses (PEP 668 externally managed)."""
    if run == "NONE":
        return "install Python 3.11+ from python.org, then rerun status"
    if not managed:
        return f"{run} -m pip install playwright && {run} -m playwright install chromium"
    v = Path(venv_py)
    q = f'"{v.as_posix()}"'
    return f'{run} -m venv "{v.parents[1].as_posix()}" && {q} -m pip install playwright && {q} -m playwright install chromium'


def commits_since(d, since):
    """Commits touching game files in the game dir since `since` (all if None); None when not a git repo or git is missing."""
    if not shutil.which("git") or subprocess.run(["git", "-C", str(d), "rev-parse", "--git-dir"],
                                                 capture_output=True).returncode:
        return None
    cmd = ["git", "-C", str(d), "rev-list", "--count"] + ([f"--since={since}"] if since else []) + [
        "HEAD", "--", ".", *(f":(exclude){p}" for p in NOT_GAME + NOT_GAME_FILES), ":(exclude,glob)**/*.md"]
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


def iteration(d):
    """(ITERATION value, its YYYY-MM-DD or None, record text) from the highest design/iterations/<n>.md."""
    its = [(int(f.stem), f) for f in (d / "design" / "iterations").glob("*.md") if f.stem.isdigit()]
    if not its:
        return "none", None, ""
    n, f = max(its)
    text = f.read_text("utf-8", "ignore")
    m = re.match(r"#\s*Iteration\s+\d+\s*\((\d{4}-\d{2}-\d{2})\)", text)
    return f"{n} {m[1] if m else '?'}", m and m[1], text  # ponytail: an unreadable date counts every file as new


def since_counts(d, date, record):
    """Files dated after the iteration, plus same-day ones its record does not already name as evidence."""
    return {k: sum(1 for f in d.glob(pat) if date is None or ((m := re.match(r"\d{4}-\d{2}-\d{2}", f.name))
                                                              and (m[0] > date or m[0] == date and f.name not in record)))
            for k, pat in SINCE.items()}


def loopmap(loop):
    return " > ".join(f"[{l}]" if l == loop else l for l in LOOPS)


def has_knobs(design_text):
    """True when the ## Knobs table has a real data row (template placeholder rows start with '<')."""
    sec = design_text.split("## Knobs", 1)[1].split("\n## ", 1)[0] if "## Knobs" in design_text else ""
    return bool(re.search(r"^\|\s*(?!name\s*\|)[A-Za-z_][\w.-]*\s*\|", sec, re.M))


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
    managed = not pw and run != "NONE" and probe(*run.split())[1]  # cached probe, no new subprocess
    install = install_line(run, managed, VENV_PY)
    if not pw:
        print(f"INSTALL={install}")
    if run.startswith('"') or managed:
        print(f"VENV={VENV}")
    print(f"GODOT={os.environ.get('GODOT') or shutil.which('godot') or 'none'}")
    print(f"GAME={d}")
    sj = d / "studio.json"
    if not sj.exists():
        engine, build = detect(d)
        print(f"INIT=no\nENGINE={engine}\nBUILD={build}")
        print("NEXT=run studio init (the studio skill asks a few short questions)")
        print(f"LOOP=design\nLOOPMAP={loopmap('design')}")
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
    dh, dh_over = debt(d, "*-human.md", p["debt_human"],
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
    it, it_date, record = iteration(d)
    sc = since_counts(d, it_date, record)
    print(f"AUTO_PLAYTEST={'off' if cfg.get('auto_playtest') is False else 'on'}")
    print(f"ITERATION={it}\nSINCE_ITERATION={' '.join(f'{k}:{v}' for k, v in sc.items())}")
    # LOOP: first match wins, from files and git only (plan contract C1)
    pt = d / "playtests"
    missing = [m for m in req if not list(pt.glob(f"*-{m}.json"))]
    quick = sorted(pt.glob("*-quick.json"))
    try:
        failed = bool(quick) and json.loads(quick[-1].read_text("utf-8")).get("verdict") == "FAIL"
    except (OSError, ValueError, AttributeError):
        failed = False
    design = d / "design" / "design.md"
    if not design.exists():
        loop, nxt = "design", "run /playbench:design to write the one-page design"
    elif stage == "shipped":
        loop, nxt = "ship", "every gate is ticked: run /playbench:ship for the upload command, then /playbench:postmortem"
    elif dq_over:
        loop, nxt = "test", "run a quick playtest (/playbench:playtest) before building more"
    elif failed:
        loop, nxt = "build", f"fix the FAIL in playtests/{quick[-1].name} (/playbench:build), then rerun a quick playtest"
    elif missing:
        loop, nxt = "test", f"run a {missing[0]} playtest (/playbench:playtest) before ticking {stage} boxes"
    elif dh_over or (not list(pt.glob("*-human.md")) and any("human" in b.lower() for b in unticked)):
        loop, nxt = "log", "watch a human play without explaining, then turn the notes into a session with /playbench:log"
    elif sc["human"] + sc["feedback"]:
        loop, nxt = "iterate", (f"{sc['human']} human session(s) and {sc['feedback']} feedback file(s) since the last "
                                "iteration: rank the changes with /playbench:iterate")
    elif (p["balance"] and stage != p["stages"][0] and not list((d / "balance").glob("*.md"))
          and has_knobs(design.read_text("utf-8", "ignore"))):
        loop, nxt = "balance", "tune the ## Knobs before the next gate with /playbench:balance"
    elif stage == p["stages"][-1]:
        loop, nxt = "ship", f"last stage ({stage}): prepare the release with /playbench:ship"
    elif cfg.get("ai_policy") == "banned":
        loop, nxt = "build", "the student writes the next must-list feature (/playbench:build reviews it), then a T0 quick playtest"
    else:
        loop, nxt = "build", "build the next must-list feature with /playbench:build, then run a quick playtest"
    print(f"LOOP={loop}\nLOOPMAP={loopmap(loop)}")
    print("UNTICKED:")
    for b in unticked:
        print(f"  - {b}")
    if not gates.exists():
        nxt = "gates.md is missing: rerun studio init --force"
    elif not pw and cfg.get("engine") == "web" and loop != "design" and stage != "shipped":
        nxt = f"install playwright (ask first): {install}"
    print(f"NEXT={nxt}")
    return 0


def aiuse(d, md=False):
    """AI-use summary from git for the game dir: a commit is Claude's when a Co-Authored-By trailer names it."""
    if commits_since(d, None) is None:
        print("AIUSE=n/a (not a git repo)")
        return 0
    r = subprocess.run(["git", "-C", str(d), "log", "--reverse", "--numstat", "--format=%x01%H%x02%B%x03", "--", "."],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    n, added = {True: 0, False: 0}, {True: 0, False: 0}
    first, edited = {}, set()  # ponytail: "first added" = first commit touching the path; a rename counts as new
    for chunk in r.stdout.split("\x01")[1:]:
        body, _, stat = chunk.partition("\x02")[2].partition("\x03")
        ai = bool(re.search(r"^co-authored-by:.*(claude|noreply@anthropic\.com)", body, re.I | re.M))
        n[ai] += 1
        for row in stat.splitlines():
            parts = row.split("\t")
            if len(parts) != 3 or not parts[0].isdigit():  # binary rows are '-'
                continue
            added[ai] += int(parts[0])
            if parts[2] not in first:
                first[parts[2]] = ai
            elif first[parts[2]] and not ai:
                edited.add(parts[2])
    total = added[True] + added[False]
    share = round(100 * added[True] / total) if total else 0
    ai_files = sum(first.values())
    print(f"AI_COMMITS={n[True]}\nHUMAN_COMMITS={n[False]}\nAI_LINES={added[True]}\nHUMAN_LINES={added[False]}")
    print(f"AI_SHARE={share}\nAI_FILES={ai_files}\nAI_FILES_HUMAN_EDITED={len(edited)}/{ai_files}")
    if md:
        print(f"\n## AI use (git-derived)\n- Commits: {n[True]} credited to Claude, {n[False]} by humans."
              f"\n- Added lines: {added[True]} in Claude commits, {added[False]} in human commits ({share}% AI)."
              f"\n- Files first added by Claude: {ai_files}; later changed by a human: {len(edited)}/{ai_files}."
              "\n- Limit: only commits with a Co-Authored-By: Claude trailer count; squash merges and uncredited"
              " pastes are invisible.")
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
    for name in ("detect", "init", "status", "aiuse", "selftest"):
        sp = sub.add_parser(name)
        sp.add_argument("dir", nargs="?", default=".")
        if name == "aiuse":
            sp.add_argument("--md", action="store_true", help="also print a markdown block for course reports")
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
    if a.cmd == "aiuse":
        return aiuse(a.dir, a.md)
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
                "BALANCE", "NEXT", "LOOP", "LOOPMAP", "AUTO_PLAYTEST", "ITERATION", "SINCE_ITERATION"]
        outside_git = commits_since(tmp, None) is None  # temp dir must not sit inside a repo
        old_path, os.environ["PATH"] = os.environ.get("PATH", ""), ""
        try:
            assert commits_since(Path(__file__).parent, None) is None  # no git on PATH: n/a, no crash
        finally:
            os.environ["PATH"] = old_path
        for ctx in PROFILE:
            out = call("status", str(tmp / f"{ctx}2"))[1]
            st = kv(out)
            assert all(k in st for k in keys) and "UNTICKED:" in out, (ctx, out)
            assert (st["RUN"] in ("python", "py -3", "python3", "NONE") or st["RUN"].startswith('"')) \
                and ("INSTALL" in st) == (st["PLAYWRIGHT"] == "no")
            assert ("ALLOWED" in st) == (ctx == "learn") and st["STAGE"] == PROFILE[ctx]["stages"][0]
            assert "run /playbench:design" in st["NEXT"] and st["LOOP"] == "design", st
            assert st["LOOPMAP"].count("[") == 1 and "[design]" in st["LOOPMAP"] and st["AUTO_PLAYTEST"] == "on"
            assert st["ITERATION"] == "none" and st["SINCE_ITERATION"].startswith("playtests:0 human:0")
            if outside_git:
                assert st["DEBT_QUICK"].startswith("n/a")
        sj2 = tmp / "hobby2" / "studio.json"
        sj2.write_text(json.dumps(dict(json.loads(sj2.read_text("utf-8")), auto_playtest=False)), "utf-8")
        assert kv(call("status", str(tmp / "hobby2"))[1])["AUTO_PLAYTEST"] == "off"
        # INSTALL: pip line, venv recipe under PEP 668, no-Python text
        vp = Path("/d/venv/bin/python")
        assert install_line("python", False, vp) == "python -m pip install playwright && python -m playwright install chromium"
        assert install_line("python3", True, vp) == ('python3 -m venv "/d/venv" && "/d/venv/bin/python" -m pip install '
                                                     'playwright && "/d/venv/bin/python" -m playwright install chromium')
        assert "python.org" in install_line("NONE", False, vp)
        assert has_knobs("## Knobs\n| name | file |\n|---|---|\n| bat_speed | - |\n")
        assert not has_knobs("## Knobs\n| name | file |\n|---|---|\n| <knob_name> | - |\n## Decision\n| x | y |\n")
        assert kv(call("status", str(tmp / "jam2"))[1])["DEADLINE"].endswith("h left")
        assert kv(call("status", str(tmp / "jam2"))[1])["SIZES"] == "quick:3x30 milestone:5x60 final:5x60"
        empty = kv(call("status", str(tmp / "w"))[1])
        assert empty["INIT"] == "no" and empty["ENGINE"] == "web" and "init" in empty["NEXT"]
        assert empty["LOOP"] == "design" and empty["LOOPMAP"].count("[") == 1

        # debt and loops in a real temp git repo
        if shutil.which("git") and outside_git:
            r = tmp / "repo"
            call("init", str(r), "--context", "hobby")
            (r / "design").mkdir(); (r / "design" / "design.md").write_text("# x\n")
            def commit(repo, name, text, msg):
                git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
                (repo / name).write_text(text)
                subprocess.run(git + ["add", "-A"], check=True)
                subprocess.run(git + ["commit", "-qm", msg], check=True)
            subprocess.run(["git", "-C", str(r), "init", "-q"], check=True)
            for i in range(3):
                commit(r, f"f{i}.txt", str(i), f"c{i}")
            pt = r / "playtests"
            pt.mkdir()
            commit(r, "notes.md", "n", "notes"); commit(r, "playtests/x-human.txt", "h", "log")  # records, not game changes
            assert kv(call("status", str(r))[1])["DEBT_QUICK"] == "3/5"
            (pt / "2000-01-01-0000-quick.json").write_text('{"at":"2000-01-01T00:00:00"}')
            st = kv(call("status", str(r))[1])
            assert st["DEBT_QUICK"] == "3/5" and st["DEBT_HUMAN"] == "3/20", st
            assert st["LOOP"] == "log" and "/playbench:log" in st["NEXT"], st  # no human session yet
            (pt / "2099-01-01-0000-quick.json").write_text('{"at":"2099-01-01T00:00:00"}')
            (pt / "2099-01-01-human.md").write_text("ok")
            st = kv(call("status", str(r))[1])
            assert st["DEBT_QUICK"] == "0/5" and st["DEBT_HUMAN"] == "0/20", st
            assert st["LOOP"] == "iterate" and "human:1" in st["SINCE_ITERATION"], st  # no iteration yet
            it = r / "design" / "iterations"
            it.mkdir()
            (it / "1.md").write_text("# Iteration 1 (2099-01-02)\n")
            st = kv(call("status", str(r))[1])
            assert st["ITERATION"] == "1 2099-01-02" and st["LOOP"] == "build", st
            assert "build the next must-list feature" in st["NEXT"] and "/playbench:build" in st["NEXT"], st
            commit(r, "f3.txt", "3", "c3"); commit(r, "f4.txt", "4", "c4")
            (pt / "2099-01-02-0000-quick.json").write_text('{"at":"2000-01-01T00:00:00","verdict":"PASS"}')
            st = kv(call("status", str(r))[1])
            assert st["DEBT_QUICK"] == "5/5 WARN" and st["LOOP"] == "test", st
            (pt / "2099-01-03-0000-quick.json").write_text('{"at":"2099-01-03T00:00:00","verdict":"FAIL"}')
            st = kv(call("status", str(r))[1])
            assert st["LOOP"] == "build" and "2099-01-03-0000-quick.json" in st["NEXT"], st
            (pt / "2099-01-04-0000-quick.json").write_text('{"at":"2099-01-04T00:00:00","verdict":"PASS"}')
            (it / "1.md").write_text("# Iteration 1 (2000-01-01)\n")
            (r / "feedback").mkdir(); (r / "feedback" / "2099-01-01-discord.md").write_text("- too hard\n")
            st = kv(call("status", str(r))[1])
            assert st["LOOP"] == "iterate" and "feedback:1" in st["SINCE_ITERATION"], st
            # a same-day iteration that lists them as evidence has used them up
            (it / "1.md").write_text("# Iteration 1 (2099-01-01)\n## Evidence\n- feedback/2099-01-01-discord.md\n"
                                     "- playtests/2099-01-01-human.md\n")
            st = kv(call("status", str(r))[1])
            assert "human:0 feedback:0" in st["SINCE_ITERATION"] and st["LOOP"] == "build", st
            (it / "2.md").write_text("# Iteration 2 (2099-01-05)\n")
            for m in ("milestone", "final"):
                (pt / f"2099-01-05-0000-{m}.json").write_text('{"verdict":"PASS"}')
            g = (r / "gates.md").read_text("utf-8")
            head, rest = g.split("## release")
            (r / "gates.md").write_text(head.replace("- [ ]", "- [x]") + "## release" + rest, "utf-8")
            st = kv(call("status", str(r))[1])
            assert st["STAGE"] == "release" and st["LOOP"] == "ship" and "[ship]" in st["LOOPMAP"], st
            (r / "gates.md").write_text(g.replace("- [ ]", "- [x]"), "utf-8")
            st = kv(call("status", str(r))[1])
            assert st["STAGE"] == "shipped" and st["LOOP"] == "ship" and "postmortem" in st["NEXT"], st

            # aiuse: human 2 lines, Claude adds a 3-line file, human edits it
            a = tmp / "ai"
            a.mkdir()
            subprocess.run(["git", "-C", str(a), "init", "-q"], check=True)
            commit(a, "h.txt", "1\n2\n", "human")
            commit(a, "c.txt", "a\nb\nc\n", "feat\n\nCo-Authored-By: Claude Opus <noreply@anthropic.com>")
            commit(a, "c.txt", "a\nB\nc\n", "tweak")
            st = kv(call("aiuse", str(a))[1])
            assert st["AI_COMMITS"] == "1" and st["HUMAN_COMMITS"] == "2" and st["AI_LINES"] == "3", st
            assert st["HUMAN_LINES"] == "3" and st["AI_SHARE"] == "50" and st["AI_FILES_HUMAN_EDITED"] == "1/1", st
            assert "## AI use (git-derived)" in call("aiuse", str(a), "--md")[1]
            assert call("aiuse", str(tmp / "w")) == (0, "AIUSE=n/a (not a git repo)\n")
        else:
            print("SKIP debt: git missing or temp dir inside a repo")
    print("ok studio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
