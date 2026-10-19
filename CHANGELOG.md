# Changelog

## 0.3.3 (2026-10-18)
Fixes found by playtesting a real game (Haunt):
- **Agent replays are deterministic.** The same script and seed could end in different states on Haunt (Kid fear 72 vs 92 at the same moment). The harness called Playwright's `clock.install()` and then `clock.pause_at()`; on page load Playwright replays those calls and counts the real milliseconds between them into `performance.now()`, so every run started a few ms off (5-7 ms measured, more on a busy machine). That shifted the game's 16 ms frames against the harness's 100 ms steps, and inputs landed a frame apart. The harness now calls `pause_at()` alone, so `performance.now()` starts at exactly 0.
- **Lost taps are named.** Bots step every 0.1 s, so a script entry held for less than a step was silently never pressed. The harness now prints a `WARN` naming such entries; the 0.1 s grid is documented.
- **Longer agent runs.** `playtest.py agent --seconds` now defaults to the script's last `t` + 300 s instead of 60 s.
- **Filmstrips don't overwrite each other.** Frames are saved as `shots/<stamp>-<mode>-film-<n>.png`, and they come from the policy bot's run when one played, instead of the random bot's.
- **Mash runs aren't the quick baseline.** A run with an explicit non-policy bot is saved as `<stamp>-<mode>-<bot>.json`, so it no longer becomes the next regression baseline or clears quick playtest debt. FAIL screenshots of script bots no longer have a `:` in their file name.
- **Sweep reports.** `balance.py sweep` writes `balance/<stamp>-sweep-<knob>.md` (`--out` to change it), and integer knob values stay integers (`19`, not `19.0`).

## 0.3.2 (2026-10-18)
- **The start key no longer acts in-game.** The harness pressed Enter and then Space to start every game. In games where Space is an action (Haunt: haunt), every run began with a free move, which skewed bot and persona results. Space is now pressed only while the game still reads as paused, or when there is no state to ask (tier 0). Found by AI persona playtests of Haunt.

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
