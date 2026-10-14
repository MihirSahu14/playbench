#!/usr/bin/env python3
"""playbench plugin hooks: gates.md tick guard (PreToolUse) and quick-playtest reminder (Stop).

Usage: hooks.py gates|stop|selftest   (hook JSON on stdin)
Runs in every session of every user: always exits 0, prints nothing but a decision JSON,
and acts only in folders that contain studio.json. Stdlib only.
"""
import json, os, re, subprocess, sys, time
from pathlib import Path

TICK_LINE = re.compile(r"^\s*[-*] \[[xX]\]", re.M)
TICK_TOKEN = re.compile(r"\[\s*[xX]\s*\]|\\\[[xX]\\\]")
GATES_ARG = re.compile(r"""["']([^"']*gates\.md)|([^\s"'<>|;&]*gates\.md)""", re.I)  # quoted or bare path
# ponytail: heuristic, blocks shell tick writes 'where detectable'; read-only greps stay allowed
WRITER = re.compile(r"(?<!\d)>|\bsed\b|\bperl\b|\bawk\b|\btee\b|python|\bpy |\bnode\b|Set-Content|Add-Content"
                    r"|Out-File|-replace|WriteAll", re.I)
DENY = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": "playbench: only humans tick gates.md boxes. Tell the user which box the "
                                    "evidence supports and let them tick and commit it."}}


def ticks(text):
    return len(TICK_LINE.findall(text or ""))


def find_game(cwd):
    """cwd or the nearest of up to 3 parents that holds studio.json, else None."""
    d = Path(cwd).resolve()
    for p in [d, *d.parents][:4]:
        if (p / "studio.json").is_file():
            return p
    return None


def gates(ev):
    tool, ti, cwd = ev.get("tool_name"), ev.get("tool_input") or {}, ev.get("cwd") or os.getcwd()
    if tool in ("Bash", "PowerShell"):
        cmd = ti.get("command") or ""
        if "gates.md" in cmd.lower() and TICK_TOKEN.search(cmd) and WRITER.search(cmd) and (find_game(cwd) or any(
                (Path(cwd) / (a or b).strip()).parent.joinpath("studio.json").is_file() for a, b in GATES_ARG.findall(cmd))):
            return DENY
        return None
    if tool not in ("Edit", "Write", "MultiEdit") or not ti.get("file_path"):
        return None
    f = Path(cwd) / ti["file_path"]
    if f.name.lower() != "gates.md" or not (f.parent / "studio.json").is_file():
        return None
    old = new = f.read_text("utf-8", "replace") if f.is_file() else ""
    if tool == "Write":
        new = ti.get("content") or ""
    # apply edits to the whole file: a snippet like "[ ] A" -> "[x] A" has no line-start "- " to count
    for e in ti.get("edits") or [] if tool == "MultiEdit" else [ti] if tool == "Edit" else []:
        new = new.replace(e.get("old_string") or "", e.get("new_string") or "", -1 if e.get("replace_all") else 1)
    return DENY if ticks(new) > ticks(old) else None


def git(d, *args):
    return subprocess.run(["git", "-C", str(d), *args], capture_output=True, timeout=5)


def stop(ev):
    # ponytail: the hook prompts instead of running the playtest because a ~60 s run is far over the hook budget
    if ev.get("stop_hook_active"):
        return None  # never loop
    d = find_game(ev.get("cwd") or os.getcwd())
    if not d:
        return None
    cfg = json.loads((d / "studio.json").read_text("utf-8"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import studio  # lazy: only the stop path pays for it
    if cfg.get("auto_playtest") is False or cfg.get("context") not in studio.PROFILE:
        return None
    # ponytail: repo root = nearest dir with .git (saves a ~150 ms git spawn); a GIT_DIR override just stays quiet
    root = next((p for p in (d, *d.parents) if (p / ".git").exists()), None)
    st = git(d, "status", "--porcelain", "-z", "-uall", "--", ".") if root else None
    if not st or st.returncode:
        return None
    prefix = d.relative_to(root).as_posix() + "/" if d != root else ""
    entries, dirty, skip = st.stdout.decode("utf-8", "replace").split("\0"), [], False
    for e in entries:  # -z: paths are repo-root relative; a rename/copy entry is followed by its old path
        if skip or len(e) < 4:
            skip = False
            continue
        skip = "R" in e[:2] or "C" in e[:2]
        rel = e[3:].removeprefix(prefix)
        if rel.startswith(studio.NOT_GAME) or rel in studio.NOT_GAME_FILES or rel.endswith(".md"):
            continue
        dirty.append(root / e[3:])
    if not dirty:
        return None
    quick = sorted((d / "playtests").glob("*-quick.json"))
    # remind once per change burst: a per-session temp marker stops re-nagging every turn over the same dirty files
    import tempfile
    mark = Path(tempfile.gettempdir()) / ("playbench-stop-" + re.sub(r"\W", "", str(ev.get("session_id", ""))))
    last = max(quick[-1].stat().st_mtime if quick else 0, mark.stat().st_mtime if mark.exists() else 0)
    if not any(f.exists() and f.stat().st_mtime > last for f in dirty):
        return None
    since = None
    if quick:
        try:
            since = json.loads(quick[-1].read_text("utf-8"))["at"]
        except Exception:
            pass
    n = (studio.commits_since(d, since) or 0) + 1
    limit = studio.PROFILE[cfg["context"]]["debt_quick"]
    if n < limit:
        return None
    mark.touch()
    return {"decision": "block", "reason": f"playbench: {n} game changes since the last quick bot playtest (limit {limit})."
            " Run the playtest skill's quick playtest now (about a minute), report its verdict line, then stop."
            ' To turn these reminders off, set "auto_playtest": false in studio.json.'}


def selftest():
    import shutil, tempfile
    me, worst = str(Path(__file__).resolve()), 0.0

    def run(cmd, ev):
        nonlocal worst
        data = ev if isinstance(ev, bytes) else json.dumps(ev).encode()
        t = time.perf_counter()
        r = subprocess.run([sys.executable, me, cmd], input=data, capture_output=True, timeout=30)
        worst = max(worst, time.perf_counter() - t)
        assert r.returncode == 0, r
        return json.loads(r.stdout) if r.stdout.strip() else None

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        g, bare = tmp / "my repo" / "game", tmp / "bare"  # space in the path on purpose
        g.mkdir(parents=True); bare.mkdir()
        (g / "studio.json").write_text('{"context": "hobby"}')
        for x in (g, bare):
            (x / "gates.md").write_text("## prototype\n- [ ] A\n- [ ] B\n")
        deny = lambda r: r and r["hookSpecificOutput"]["permissionDecision"] == "deny"
        edit = lambda d, f, o, n: {"tool_name": "Edit", "cwd": str(d), "tool_input": {"file_path": f, "old_string": o, "new_string": n}}
        assert deny(run("gates", edit(tmp, str(g / "gates.md"), "- [ ] A", "- [x] A")))
        assert run("gates", edit(g, "gates.md", "- [x] A", "- [ ] A")) is None
        assert run("gates", edit(bare, "gates.md", "- [ ] A", "- [x] A")) is None
        assert run("gates", edit(g, "notes.md", "- [ ] A", "- [x] A")) is None
        wr = lambda c: {"tool_name": "Write", "cwd": str(g), "tool_input": {"file_path": "GATES.md", "content": c}}
        assert deny(run("gates", wr("## prototype\n- [x] A\n- [ ] B\n")))
        assert run("gates", wr("## prototype\n- [ ] A\n- [ ] B\n- [ ] C\n")) is None
        me_ = {"tool_name": "MultiEdit", "cwd": str(g), "tool_input": {"file_path": "gates.md", "edits": [
            {"old_string": "- [ ] A", "new_string": "- [x] A"}, {"old_string": "B", "new_string": "B2"}]}}
        assert deny(run("gates", me_))
        assert deny(run("gates", edit(g, "gates.md", "[ ] A", "[x] A")))  # snippet without "- "
        ra = edit(g, "gates.md", "[ ]", "[x]")
        ra["tool_input"]["replace_all"] = True
        assert deny(run("gates", ra))
        sh = lambda t, c: {"tool_name": t, "cwd": str(g), "tool_input": {"command": c}}
        assert deny(run("gates", sh("Bash", r"sed -i 's/- \[ \]/- [x]/' gates.md")))
        assert run("gates", sh("Bash", r'grep -n "\[x\]" gates.md')) is None
        assert deny(run("gates", sh("PowerShell", r"(Get-Content gates.md) -replace '\[ \]','[x]' | Set-Content gates.md")))
        assert run("gates", {**sh("Bash", r"sed -i 's/- \[ \]/- [x]/' gates.md"), "cwd": str(bare)}) is None
        sed = r"sed -i 's/- \[ \]/- [x]/' "
        assert deny(run("gates", {**sh("Bash", sed + "game/gates.md"), "cwd": str(g.parent)}))  # from repo root
        assert deny(run("gates", {**sh("Bash", sed + f'"{g / "gates.md"}"'), "cwd": str(tmp)}))  # quoted, spaces
        for cmd in ("gates", "stop"):
            assert run(cmd, b"not json {") is None and run(cmd, b"") is None

        if not shutil.which("git"):
            print("SKIP hooks stop: git not on PATH")
        else:
            gi = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-C", str(g)]
            subprocess.run(gi[:-2] + ["init", "-q", str(g.parent)], check=True)
            for i in range(5):
                (g / "game.js").write_text(f"// v{i}\n")
                subprocess.run(gi + ["add", "-A"], check=True)
                subprocess.run(gi + ["commit", "-qm", f"c{i}"], check=True)
            touch = lambda: os.utime(g / "game.js", (time.time() + 5,) * 2)  # a fresh edit, clear of the marker
            (g / "game.js").write_text("// dirty\n")
            os.utime(g / "game.js", (time.time() - 30,) * 2)  # edited before the reminder below
            ev = {"cwd": str(g), "stop_hook_active": False, "session_id": "selftest-" + tmp.name}
            mark = Path(tempfile.gettempdir()) / ("playbench-stop-" + re.sub(r"\W", "", ev["session_id"]))
            r = run("stop", ev)
            assert r and r["decision"] == "block" and "6 game changes" in r["reason"] and "limit 5" in r["reason"], r
            assert run("stop", ev) is None  # already reminded, nothing changed since
            touch()
            assert run("stop", {**ev, "stop_hook_active": True}) is None
            (g / "studio.json").write_text('{"context": "hobby", "auto_playtest": false}')
            assert run("stop", ev) is None
            (g / "studio.json").write_text('{"context": "hobby"}')
            assert run("stop", ev)  # back on
            mark.unlink()
            (g / "playtests").mkdir()
            old = time.time() - 60
            os.utime(g / "game.js", (old, old))
            from datetime import datetime
            (g / "playtests" / "2026-10-13-1200-quick.json").write_text(json.dumps({"at": datetime.now().isoformat(timespec="seconds")}))
            assert run("stop", ev) is None
            assert run("stop", {**ev, "cwd": str(bare)}) is None

    hj = json.loads((Path(me).parents[1] / "hooks" / "hooks.json").read_text("utf-8"))["hooks"]
    assert {"PreToolUse", "Stop"} <= set(hj)
    for groups in hj.values():
        for h in (h for grp in groups for h in grp["hooks"]):
            c = h["command"]
            assert "hooks.py" in c and "${CLAUDE_PLUGIN_ROOT}" in c and c.endswith("|| true") and h["timeout"] <= 10, c
    assert worst < 1.5, worst
    print(f"max hook call {worst:.2f}s")
    print("ok hooks")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "selftest":
        selftest()
        return
    try:
        ev = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
        out = {"gates": gates, "stop": stop}[cmd](ev) if isinstance(ev, dict) else None
        if out:
            print(json.dumps(out))
    except BaseException:
        pass  # fail open: a broken hook must never block a session
    sys.exit(0)


if __name__ == "__main__":
    main()
