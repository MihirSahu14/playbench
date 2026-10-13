# playbench: Research Summary (2026-10-13)

This pulls together the research loop behind `playbench` and records the facts its blocking checks depend on. Earlier notes: [studio pipeline](2026-10-13-studio-pipeline.md), [playtesting cadence](2026-10-13-playtesting-cadence.md), [market fit](2026-10-13-market-fit.md).

## Product conclusion
- **Writing design docs is a commodity.** Claude Code Game Studios already does it for free, and it has 26k stars. Its own author found that the "30 docs before code" tier ranked last. playbench therefore keeps design to one discussion and one page.
- **The value is in harnesses that run things.** That means bots that play the real build after each feature, balance sweeps on the real build and data, and a ship step that blocks undisclosed placeholder or AI art and shows who ticked the release gate.
- **v1 is web-first and Godot-second.**
  - Every engine can export HTML5, and jams judge the browser build.
  - Godot native is the next transport: Godot is now the top jam engine.
  - Steam teams on native Unity or Unreal get the art gate, the gate audit and the Steam checks. They get bot playtests only if they have a WebGL export. The spec says this plainly.

## Verified facts (checked 2026-10-13)
| Fact | Used by | Source |
|---|---|---|
| itch HTML5 zip limits: `index.html` must be the entry point; at most 1,000 files after extraction; at most 500 MB in total; at most 200 MB per file; paths of at most 240 characters; file names are case-sensitive, and a reference with the wrong case fails on the server | `ship itch` limits check (blocking) | https://itch.io/docs/creators/html5 |
| `butler push <dir\|zip> user/game:channel` supports `--dry-run` and `--if-changed`. HTML5 is **not** auto-tagged: the uploader marks the file "playable in browser" and sets the page kind to HTML by hand | `ship itch` printed command and manual steps | https://itch.io/docs/butler/pushing.html |
| Steam store assets: header capsule 920×430, small capsule 462×174, main capsule 1232×706, vertical capsule 748×896, at least 5 screenshots at 1920×1080 or more in 16:9 | `ship steam` PNG-size check (blocking) | https://partner.steamgames.com/doc/store/assets/standard |
| Steam rewrote its AI disclosure in January 2026. It now covers AI-generated content players see (in the game or generated live). Dev tools such as code assistants are exempt | artgate + disclosure reminder | https://www.notebookcheck.net/Steam-updates-AI-disclosure-form-requiring-developers-to-report-visible-and-in-game-AI-but-not-background-tools.1206103.0.html, https://tech-insider.org/steam-ai-disclosure-2026 |
| **Unverified:** whether Steam's rule explicitly covers marketing and store assets | artgate still scans `store/` as a **policy choice** and says so; it does not cite a Steam rule | (no primary source found) |
| itch requires AI-generated tags/disclosure on asset pages (since November 2024) | disclosure reminder | https://80.lv/articles/asset-creators-on-itch-io-now-have-to-disclose-the-use-of-generative-ai/ |
| GMTK Game Jam 2026: 47% of entries used Godot (about 4.9k games) and 34% used Unity. In 2025 Godot had 39% | jam segment and Godot transport priority | https://gameworldobserver.com/2026/07/29/unity-is-no-longer-the-leader-godot-has-become-the-most-popular-engine-at-gmtk-game-jam-2026 |
| Godot 4.3+ supports single-threaded web export, which needs no SharedArrayBuffer or COOP/COEP headers. Threaded builds need cross-origin isolation | page.clock caveat; recommend no-threads exports | https://godotengine.org/article/progress-report-web-export-in-4-3/ |
| Playwright `clock.install` fakes Date, setTimeout/setInterval, requestAnimationFrame, requestIdleCallback and performance. `run_for(ms)` fires timers and animation frames. install is called before goto | deterministic, faster-than-real-time web runs | https://playwright.dev/python/docs/clock |
| OpenAI's `develop-web-game` skill has games expose `window.render_game_to_text()` and `window.advanceTime(ms)` for Playwright loops | accepted as a T1 state hook (avoids lock-in) | https://playbooks.com/skills/openai/skills/develop-web-game |
| Godot CLI: `--headless`, `--script`, `--fixed-fps`, `--quit-after`, and user args after `--` | Godot native transport | https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html |
| SteamPipe app build `.vdf` with `Preview "1"` checks a build without uploading it | `ship steam` | https://partner.steamgames.com/doc/sdk/uploading |

## Local environment (this machine, 2026-10-13)
- `python` is 3.11.0 and has playwright 1.59.0 installed. `py -3` is 3.13.5 and does **not** have playwright. Plugin scripts must find out which interpreter has playwright at run time and tell the SKILL.
- Claude Code is 2.1.286, and `claude plugin validate <path> --strict` is available.
- None of godot, butler or steamcmd is on PATH, and `$GODOT` is empty. Godot native stays **experimental** until the user approves downloading the portable editor and the spike passes.

## Competitors and adjacent tools
| Tool | What it does | playbench's angle |
|---|---|---|
| Claude Code Game Studios | 49 agents, document-heavy pipeline | One page of design. The effort goes into harnesses |
| develop-web-game (OpenAI), game-qa, game-creator (`__GAME_STATE__`) | Playwright loops for web games | We accept their hooks as T1. We add tiers, softlock and dead-input detectors that use deterministic replay, statistics reported only when a policy bot plays, real-build sweeps, and ship gates. (The game-creator hook name comes from earlier research; its repo URL has not been re-verified) |
| awesome-gamedev-agent-skills | butler and SteamPipe skills | Commodity. We wrap them behind artgate and the gate audit |
| nunu.ai, modl.ai | Enterprise AI QA | Self-serve and local, at no per-frame token cost |

## Distribution
Launch where jammers already gather. That means a README section titled "use it in your next jam", posts on GMTK Game Jam (July) and on itch jam community pages, r/gamedev and r/godot, plus a Claude Code plugin marketplace entry. Jams are timed events with about 10k entries, and they judge the HTML build, which is exactly what T0 covers.
