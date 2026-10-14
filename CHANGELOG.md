# Changelog

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
