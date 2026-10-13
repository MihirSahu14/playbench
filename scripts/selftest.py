#!/usr/bin/env python3
"""Run every playloop script's selftest, then `claude plugin validate . --strict`. Exit 1 on any failure."""
import shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
failed = []
for name in ("studio", "playtest", "balance", "ship"):
    script = ROOT / "scripts" / f"{name}.py"
    if not script.exists():
        print(f"SKIP {name}: not built")
        continue
    print(f"== {name}", flush=True)
    if subprocess.run([sys.executable, str(script), "selftest"], cwd=ROOT).returncode:
        failed.append(name)

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
