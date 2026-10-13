# playloop

A Claude Code plugin where bots play your **real game build** after every feature. It also sweeps balance knobs on that same build, and it blocks itch and Steam releases until placeholder or AI art is disclosed and a human has ticked the release gate. Design stays at one conversation and one page. The flow adapts to jam, hobby, team or classroom use, and to how much you want to code.

**What actually works in v1:**
- **Web is first-class.** Any HTML5 export works: plain JS, Phaser, Godot web, Unity WebGL, GameMaker, Construct and GDevelop. It runs through headless Chromium with a virtual clock.
- **Godot native is experimental.** It goes headless through `probe.gd`, and stays unverified until it has been run against a real Godot 4 binary.
- **Native Unity and Unreal builds** get bot playtests only through a WebGL export.

## Install
```
claude plugin marketplace add <path-or-git-URL-of-this-repo>
claude plugin install playloop@playloop
```
For development, load it straight from a checkout: `claude --plugin-dir "<path to this repo>"`.

## Requirements
- **Python 3.11+.** The scripts use the stdlib only.
- **For web playtests, balance sweeps and boot checks:** Playwright with Chromium. Install it with the exact line `status` prints, for example:
  `python -m pip install playwright && python -m playwright install chromium`
  The studio, design, `ship artgate` and `ship gate` features work without it.
- **Optional:** set `GODOT` to a Godot 4 editor executable for Godot native playtests (experimental), and install `butler` or `steamcmd` to upload. playloop only prints upload commands; you run them yourself.

## Who it's for
- **Game-jammer** (`jam`): a deadline countdown, a 3-seed quick playtest, gates `playable -> submitted`, a jam-ready itch zip and checklist. Steam stays hidden.
- **Solo hobbyist** (`hobby`): the must list is capped at hours/week × weeks, warnings fire at 5 commits without a bot playtest and 20 without a human one, and gates are `prototype -> slice -> release`.
- **Small indie team** (`team`): every gate box has an owner, every playtest is diffed against the last one, the Steam vdf and store-asset checks are included, and `ship gate` shows who ticked each box (git blame).
- **Low-code designer** (coding = 1, any context): Claude writes the probe adapter and the bot, moves tunables into data files, and reports each verdict in one plain line.
- **Student or educator** (`learn`): a course AI policy (`open`, `disclose` or `banned`), a rubric block on playtest reports, and under `banned` Claude only explains, reviews and runs checks.

## 60-second jam quickstart
1. Open Claude Code in your game folder and say **"set up playloop for a jam"**. The studio skill asks: kind of project, coding comfort, engine, target and deadline.
2. Say **"let's design it"**. You get 5 theme interpretations, a hook, a core loop and a must/cut list sized to the hours left. The result is `design/design.md`.
3. Build a feature, then say **"playtest it"**. Bots play 3 seeds × 30 s of your real build and report boot failures, crashes, softlocks and dead input.
4. Say **"ship to itch"**. playloop checks the itch limits, zips the build, boot-checks the zip and prints the `butler push … --dry-run` command. It gives you the real command only once the art is disclosed and you have ticked the gates.

## Probe contract (how bots read your game)
The state the game returns has this shape:

`{over: bool, won?: bool, score?: number, paused?: bool, ...gameplay fields}`

- `paused` covers menus, title screens and cutscenes.
- Keys starting with `_`, and the keys `t`, `time`, `frame`, `tick` and `elapsed`, are ignored when the state is hashed.

**Web.** The game may define `window.__game`:
- `state`: a function returning the state, or a plain object the game keeps updated.
- `bot(state) -> string[]` (optional): the `KeyboardEvent.key` values to hold for this step.
- `actions: string[]` (optional): defaults to `["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"," ","Enter"]`.

`window.render_game_to_text()` and `window.__GAME_STATE__` are also accepted. Before the game runs, the harness injects `window.__playloop = {seed, overrides}` and replaces `Math.random` with a seeded PRNG. Bundled tunables are read like this:

`(window.__playloop?.overrides ?? {}).<name> ?? <default>`

**Godot (experimental).** The main scene's root node may define `probe_state() -> Dictionary`, `probe_seed(seed)`, `probe_actions() -> Array[String]` and `probe_bot(state) -> Array[String]`.

**Tiers** are detected automatically:
- **T0** needs nothing. It finds boot failures, errors, a frozen canvas and dead input.
- **T1** needs a readable state. It adds softlock and state-based dead-input checks.
- **T2** needs a bot. It adds win rate and time-to-over, labelled *relative difficulty under policy bot*.

## Commands
| Skill | Scripts it runs |
|---|---|
| `/playloop:studio`: setup, status, what next | `studio.py detect`, `studio.py init --context jam\|hobby\|team\|learn …`, `studio.py status` |
| `/playloop:design`: one discussion, one page | none (it writes `design/design.md`) |
| `/playloop:playtest`: quick, milestone and final bot playtests | `playtest.py run <build> --mode quick\|milestone\|final --out playtests` |
| `/playloop:balance`: knob sweeps on the real build | `balance.py sweep . --knob <name> [--values a,b,c]` |
| `/playloop:ship`: release gates and uploads | `ship.py artgate\|gate\|itch\|steam\|web` |

Every script has a `selftest`. Run them all with `python scripts/selftest.py`, which also runs `claude plugin validate . --strict`.

State lives as plain files in your game repo: `studio.json`, `gates.md`, `design/design.md`, `art/PLACEHOLDERS.json`, `disclosure.md`, `playtests/`, `balance/last.json`. There is no database. Stage and playtest debt are derived from git and the files, so team members don't get merge conflicts.

## What bots can't judge
Bots find crashes, softlocks, dead input, frozen screens and relative difficulty shifts. They cannot judge **fun, clarity, feel or art**. A human playtest (`playtests/<date>-human.md`, from the milestone sheet) is required before gates. **Only humans tick gate boxes**: Claude never writes `[x]`, and `ship gate` shows who ticked each box with git blame.

## AI-art policy
- AI art is only for clearly marked placeholders: a `_placeholder` filename and an entry in `art/PLACEHOLDERS.json`.
- `ship artgate` scans the build and `store/`. It flags placeholder names, PNG generator metadata (`parameters`, `prompt` or `workflow` chunks, and generator names), C2PA (`caBX`) and JPEG/WebP generator bytes. It blocks unless every flagged file is covered by a line in `disclosure.md`.
- On a pass it reminds you to fill in Steam's AI content survey and itch's AI tag.
- Detection is heuristic, so stripped metadata gets through. It is a safety net for honest developers, not enforcement.

## Use it in your next jam
- Install it before the jam starts, and run `studio init --context jam --deadline <ISO>` in an empty folder.
- Keep the quick playtest after every feature: 3 seeds × 30 s, about a minute. It catches the "broke the title screen at hour 40" bug.
- Run `ship itch` early, on day one. It catches root-absolute URLs, case-mismatched asset paths and the 1000-file limit while there is still time to fix them.
- After the jam, share your `playtests/*.md` and what the bots missed. Issues and PRs are welcome.

## Implementation notes
**Spike (Task 1, 2026-10-13, Claude Code 2.1.286, Windows 11):**
- **Live run blocked.** `claude -p "/playloop:spike …" --plugin-dir "<repo>"` exited 1 with `Failed to authenticate: OAuth session expired and could not be refreshed`. The live substitution check could not run in this environment. Rerun it after `claude /login` with a throwaway `skills/spike/SKILL.md` whose body is `` !`echo "root=${CLAUDE_PLUGIN_ROOT} skill=${CLAUDE_SKILL_DIR} shell=$0"` ``.
- **Static check of the installed 2.1.286 binary** (the plugin skill loader, `getPromptForCommand`):
  - **Substitution happens before the `!` lines run.** Plugin skill content has `${CLAUDE_PLUGIN_ROOT}` replaced with the plugin path, with backslashes converted to forward slashes. `${CLAUDE_PROJECT_DIR}`, `${CLAUDE_PLUGIN_DATA}` and (for skills) `${CLAUDE_SKILL_DIR}` are replaced too.
  - **Which shell runs them.** The frontmatter `shell:` key takes `bash` or `powershell`. When it is absent, the commands run through the Bash tool's shell, which is **Git Bash** on Windows when it is installed, and PowerShell otherwise.
  - **Permissions.** Each command goes through the normal permission check, so `allowed-tools: Bash(python:*), Bash(py:*)` covers the status line.
- **Decision.** The SKILLs keep the planned line, which uses `${CLAUDE_PLUGIN_ROOT}` with quoted paths (the install path contains spaces). If a future version stops substituting it, this fallback works in the same position:
  `` !`python "${CLAUDE_SKILL_DIR}/../../scripts/studio.py" status || py -3 "${CLAUDE_SKILL_DIR}/../../scripts/studio.py" status || echo "playloop: no working Python 3 found"` ``
- **`claude plugin validate . --strict`.** It first warned `No marketplace description provided`. Fixed by adding `metadata.description` to `marketplace.json`, after which it printed `✔ Validation passed`. `claude plugin validate .claude-plugin/plugin.json --strict` passes as well.

**Small deliberate choices:**
- **Debt is counted for the game folder only.** `status` counts debt with `git rev-list --count --since=<at> HEAD -- .`. The `-- .` limits the count to commits touching the game folder, so a game nested inside a bigger repo (like `examples/`) isn't charged for unrelated commits.
- **Git date limit.** Git's date parser rejects years after 2099. The selftest uses 2099 for its "future report" case.
- **`status` always exits 0**, even when `studio.json` is broken. Otherwise the SKILL's `||` chain would fall through and wrongly report "no working Python".
