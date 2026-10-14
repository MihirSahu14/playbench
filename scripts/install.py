#!/usr/bin/env python3
"""Install playbench's skills into any agent that reads SKILL.md folders.

  python scripts/install.py [--agent agents|claude|codex|cursor|gemini|copilot|opencode|windsurf|cline] [--project DIR] [--dest DIR] [--uninstall]
  python scripts/install.py list
  python scripts/install.py selftest

Claude Code and Codex can also install playbench as a plugin (see README); this script is for every other agent,
or for a plain skills install. Each skill is copied to <skills dir>/playbench-<name>/ (so 'build' or 'log' never
collides with your own skills) and pointed at this checkout's scripts/. Re-run after `git pull` to refresh.
"""
import argparse, os, re, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
# agent -> (user-level skills dir, project-level skills dir relative to --project)
TARGETS = {  # verified against each tool's docs, 2026-10-13
    "agents":   (HOME / ".agents" / "skills", ".agents/skills"),  # shared: Codex, Cursor, Gemini CLI, Copilot, OpenCode, Windsurf, Amp, Goose
    "claude":   (HOME / ".claude" / "skills", ".claude/skills"),
    "codex":    (HOME / ".agents" / "skills", ".agents/skills"),
    "cursor":   (HOME / ".cursor" / "skills", ".cursor/skills"),
    "gemini":   (HOME / ".gemini" / "skills", ".gemini/skills"),
    "copilot":  (HOME / ".copilot" / "skills", ".github/skills"),
    "opencode": (HOME / ".config" / "opencode" / "skills", ".opencode/skills"),
    "windsurf": (HOME / ".codeium" / "windsurf" / "skills", ".windsurf/skills"),
    "cline":    (HOME / ".cline" / "skills", ".cline/skills"),
}
MARK = ".playbench-install"  # only folders carrying this marker are ever removed or overwritten


def dest_of(a):
    if a.dest:
        return Path(a.dest)
    user, proj = TARGETS[a.agent]
    return Path(a.project) / proj if a.project else user


def install(dest):
    dest.mkdir(parents=True, exist_ok=True)
    scripts = (ROOT / "scripts" / "studio.py").as_posix()
    names = []
    for src in sorted((ROOT / "skills").glob("*/SKILL.md")):
        name, out = src.parent.name, dest / f"playbench-{src.parent.name}"
        if out.exists() and not (out / MARK).exists():
            sys.exit(f"ERROR {out} exists and was not installed by playbench; move it and re-run")
        shutil.rmtree(out, ignore_errors=True)
        shutil.copytree(src.parent, out)
        t = (out / "SKILL.md").read_text("utf-8")
        t = re.sub(r"(?m)^name: .*$", f"name: playbench-{name}", t, count=1)
        t = t.replace('"<SKILL_DIR>/../../scripts/studio.py"', f'"{scripts}"')  # copies no longer sit inside the repo
        (out / "SKILL.md").write_text(t, "utf-8")
        (out / MARK).write_text(str(ROOT), "utf-8")
        names.append(out.name)
    return names


def uninstall(dest):
    gone = [p.name for p in sorted(dest.glob("playbench-*")) if (p / MARK).exists()]
    for n in gone:
        shutil.rmtree(dest / n)
    return gone


def selftest():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "my skills"
        names = install(d)
        assert len(names) == len(list((ROOT / "skills").glob("*/SKILL.md"))) and "playbench-build" in names, names
        s = (d / "playbench-playtest" / "SKILL.md").read_text("utf-8")
        assert "name: playbench-playtest" in s and (ROOT / "scripts" / "studio.py").as_posix() in s, s[:400]
        assert "<SKILL_DIR>/../../scripts" not in s and (d / "playbench-design" / "design-template.md").exists()
        assert install(d) == names  # re-run refreshes in place
        (d / "playbench-mine").mkdir(); (d / "playbench-mine" / "SKILL.md").write_text("x")
        assert "playbench-mine" not in uninstall(d) and (d / "playbench-mine").exists()  # never touch unmarked folders
        assert not any((d / n).exists() for n in names)
        (d / "playbench-art").mkdir()  # an unmarked folder in the way is an error, not an overwrite
        try:
            install(d)
            raise AssertionError("overwrote an unmarked folder")
        except SystemExit as e:
            assert "was not installed by playbench" in str(e)
        a = argparse.Namespace(dest=None, agent="cursor", project=tmp)
        assert dest_of(a) == Path(tmp) / ".cursor/skills"
    print("ok install")


def main():
    if sys.argv[1:2] == ["selftest"]:
        return selftest()
    if sys.argv[1:2] == ["list"]:
        for k, (u, p) in TARGETS.items():
            print(f"{k:9} user: {u}   project: <project>/{p}")
        return
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--agent", default="agents", choices=sorted(TARGETS), help="default: agents (~/.agents/skills, read by most tools)")
    ap.add_argument("--project", help="install into this project instead of your user-level skills folder")
    ap.add_argument("--dest", help="explicit skills folder (overrides --agent paths)")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()
    d = dest_of(a)
    if a.uninstall:
        print(f"removed {len(uninstall(d))} playbench skills from {d}")
    else:
        n = install(d)
        print(f"installed {len(n)} skills into {d}: {', '.join(n)}")
        print('Next: open your agent in a game folder and say "set up playbench for a jam".')


if __name__ == "__main__":
    main()
