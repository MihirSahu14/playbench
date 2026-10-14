# Changelog

## 0.3.1 (2026-10-14)
Fixes found by running playbench on a real game (Haunt, a 5,600-line canvas horror game):
- **Playtests about 6× faster on heavy games.** Headless Chromium now uses the real GPU on Windows (d3d11) and macOS (metal). Haunt's quick playtest dropped from 14 min to 2 min. `PLAYBENCH_GPU=0` forces software rendering.
- **Fewer false "nondeterministic" warnings.** Games timed by Web Audio now follow the fake clock (`AudioContext.currentTime`). When the two idle replays disagree, one tie-break run decides 2 of 3, so the dead-input check runs instead of being skipped.
- **Right build folder.** `studio init` now prefers `dist/`, `build/`, `export/` or `release/*/` over a root `index.html`, which is often the dev page. `ship itch` warns when the upload contains dev folders (`src/`, `tools/`, `docs/`, …). On Haunt the zip went from 41 files and 8.9 MB to one 214 KB file.

## 0.3.0 (2026-10-13)
- **Works on any agent.** Packaged for Claude Code, Codex (verified live: studio and a full quick playtest), the open Agent Plugins format (Cursor, GitHub Copilot CLI), and Gemini CLI. `scripts/install.py` installs the skills for anything else that reads `SKILL.md` folders.
- **Portable skills.** Each skill tells non-Claude agents to run `studio.py status` themselves. No `${CLAUDE_*}` paths remain outside Claude Code's auto-run line, and the selftest enforces this.
- **Hooks on Codex.** The gate guard understands Codex's `apply_patch` and shell tools, and blocks with exit 2.
- **Anthropic directory fields.** Adds `displayName`, `icon`, `documentationUrl` and `supportUrl`, plus marketplace `category` and `tags`.

## 0.2.0 (2026-10-13)
- **Every loop covered.** New skills: `build`, `iterate`, `log`, `art`, `feedback`, `postmortem` (11 in total).
- **Hooks.** A gate guard (the agent can't tick `gates.md`) and an auto quick-playtest reminder.
- **Playtest.** Mash and scripted bots, decision-point agent playtests, persona commentary, survey and telemetry.
- **Balance.** Cost curves, Monte Carlo sims and payoff matrices.
- **Ship.** itch theme, Steam library assets, Pages/Netlify, a Next Fest checklist, and gated `--real` uploads. Uploads come from a filtered copy, so private notes are never shipped.
- **Unity 6 WebGL verified.** C# exceptions are now reported as crashes.

## 0.1.0 (2026-10-13)
- First release: `studio`, `design`, `playtest`, `balance` and `ship`.
- Bot playtests on real web builds, balance sweeps, and itch/Steam gates that block undisclosed AI art.
