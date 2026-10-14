# playbench reference

Details behind the [README](../README.md).

## Requirements
- **Python 3.11+.** The scripts use the stdlib only.
- **For web playtests, balance sweeps and boot checks:** Playwright with Chromium. Install it with the exact line `status` prints, for example:
  `python -m pip install playwright && python -m playwright install chromium`
  The studio, design, `ship artgate` and `ship gate` features work without it.
- **Optional:** set `GODOT` to a Godot 4 editor executable for Godot native playtests (experimental), and install `butler` or `steamcmd` to upload. playbench only prints upload commands; you run them yourself.

## Who it's for
- **Game-jammer** (`jam`): a deadline countdown, a 3-seed quick playtest, gates `playable -> submitted`, a jam-ready itch zip and checklist. Steam stays hidden.
- **Solo hobbyist** (`hobby`): the must list is capped at hours/week × weeks, warnings fire at 5 commits without a bot playtest and 20 without a human one, and gates are `prototype -> slice -> release`.
- **Small indie team** (`team`): every gate box has an owner, every playtest is diffed against the last one, the Steam vdf and store-asset checks are included, and `ship gate` shows who ticked each box (git blame).
- **Low-code designer** (coding = 1, any context): Claude writes the probe adapter and the bot, moves tunables into data files, and reports each verdict in one plain line.
- **Student or educator** (`learn`): a course AI policy (`open`, `disclose` or `banned`), a rubric block on playtest reports, and under `banned` Claude only explains, reviews and runs checks.

## 60-second jam quickstart
1. Open Claude Code in your game folder and say **"set up playbench for a jam"**. The studio skill asks: kind of project, coding comfort, engine, target and deadline.
2. Say **"let's design it"**. You get 5 theme interpretations, a hook, a core loop and a must/cut list sized to the hours left. The result is `design/design.md`.
3. Build a feature, then say **"playtest it"**. Bots play 3 seeds × 30 s of your real build and report boot failures, crashes, softlocks and dead input.
4. Say **"ship to itch"**. playbench checks the itch limits, zips the build, boot-checks the zip and prints the `butler push … --dry-run` command. It gives you the real command only once the art is disclosed and you have ticked the gates.

## Probe contract (how bots read your game)
The state the game returns has this shape:

`{over: bool, won?: bool, score?: number, paused?: bool, ...gameplay fields}`

- `paused` covers menus, title screens and cutscenes.
- Keys starting with `_`, and the keys `t`, `time`, `frame`, `tick` and `elapsed`, are ignored when the state is hashed.

**Web.** The game may define `window.__game`:
- `state`: a function returning the state, or a plain object the game keeps updated.
- `bot(state) -> string[]` (optional): the `KeyboardEvent.key` values to hold for this step.
- `actions: string[]` (optional): defaults to `["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"," ","Enter"]`.

`window.render_game_to_text()` and `window.__GAME_STATE__` are also accepted. Before the game runs, the harness injects `window.__playbench = {seed, overrides}` and replaces `Math.random` with a seeded PRNG. Bundled tunables are read like this:

`(window.__playbench?.overrides ?? {}).<name> ?? <default>`

**Godot (experimental).** The main scene's root node may define `probe_state() -> Dictionary`, `probe_seed(seed)`, `probe_actions() -> Array[String]` and `probe_bot(state) -> Array[String]`.

**Tiers** are detected automatically:
- **T0** needs nothing. It finds boot failures, errors, a frozen canvas and dead input.
- **T1** needs a readable state. It adds softlock and state-based dead-input checks.
- **T2** needs a bot. It adds win rate and time-to-over, labelled *relative difficulty under policy bot*.

## Commands
| Skill | Scripts it runs |
|---|---|
| `/playbench:studio`: setup, status, what next | `studio.py detect`, `studio.py init --context jam\|hobby\|team\|learn …`, `studio.py status` |
| `/playbench:design`: one discussion, one page | none (it writes `design/design.md`) |
| `/playbench:playtest`: quick, milestone and final bot playtests | `playtest.py run <build> --mode quick\|milestone\|final --out playtests` |
| `/playbench:balance`: knob sweeps on the real build | `balance.py sweep . --knob <name> [--values a,b,c]` |
| `/playbench:ship`: release gates and uploads | `ship.py artgate\|gate\|itch\|steam\|web` |

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
