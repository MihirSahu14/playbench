#!/usr/bin/env python3
"""Run every playbench script's selftest, lint skills/*/SKILL.md and hooks.json, then `claude plugin validate . --strict`. Exit 1 on any failure."""
import json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
failed = []
for name in ("studio", "playtest", "balance", "ship", "hooks", "art", "telemetry"):
    script = ROOT / "scripts" / f"{name}.py"
    if not script.exists():
        print(f"SKIP {name}: not built")
        continue
    print(f"== {name}", flush=True)
    if subprocess.run([sys.executable, str(script), "selftest"], cwd=ROOT).returncode:
        failed.append(name)

CTX = ('!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status'
       ' || echo "playbench: no working Python 3 found"`')
print("== skills lint", flush=True)
skills = sorted(ROOT.glob("skills/*/SKILL.md"))
n = len(failed)
for f in skills:
    lines = f.read_text("utf-8").splitlines()
    end = lines.index("---", 1) if lines[:1] == ["---"] and "---" in lines[1:] else 0
    meta = dict(l.split(":", 1) for l in lines[1:end] if ":" in l)
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    heads = [l for l in lines if l.startswith("## ")]
    for bad, why in ((meta.get("name") != f.parent.name, "name != folder"),
                     (not meta.get("description"), "no description"), (not meta.get("allowed-tools"), "no allowed-tools"),
                     (lines[end + 1:end + 2] != [CTX], "first body line is not the status line"),
                     (heads[-1:] != ["## Next loop"], "last ## heading is not ## Next loop"),
                     (any(re.match(r"\s*- \[[xX]\]", l) for l in lines), "ticked box"), (len(lines) > 160, ">160 lines")):
        if bad:
            failed.append(f"skill {f.parent.name}: {why}")
hj = ROOT / "hooks" / "hooks.json"
if hj.exists():
    try:
        json.loads(hj.read_text("utf-8"))
    except ValueError as e:
        failed.append(f"hooks.json: {e}")
if len(failed) == n:
    print(f"ok skills lint ({len(skills)} skills)")
else:
    print("\n".join(f"FAIL {x}" for x in failed[n:]))

claude = shutil.which("claude")
if claude:
    for target in (".", ".claude-plugin/plugin.json"):  # "." alone validates only marketplace.json
        print(f"== claude plugin validate {target} --strict", flush=True)
        if subprocess.run([claude, "plugin", "validate", target, "--strict"], cwd=ROOT).returncode:
            failed.append(f"validate {target}")
else:
    print("SKIP validate: claude not on PATH")

print(f"FAILED: {', '.join(failed)}" if failed else "ok selftest")
sys.exit(1 if failed else 0)
