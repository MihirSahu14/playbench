# playbench reference

Details behind the [README](../README.md).

## Platforms
One repo, packaged for each agent:

| File | Read by |
|---|---|
| `.claude-plugin/plugin.json`, `marketplace.json`, `hooks/hooks.json` | Claude Code |
| `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`, `hooks/hooks.json` | Codex |
| `plugin.json` (open [Agent Plugins](https://agent-plugins.org) 1.0.0 format) | Codex, Cursor, GitHub Copilot CLI |
| `gemini-extension.json` | Gemini CLI |
| `scripts/install.py` | Anything that reads `SKILL.md` folders (`~/.agents/skills` by default) |

**Portable skills.** Each skill's first line is Claude Code's auto-run status line. The next line tells any other agent to run `studio.py status` itself, using a path relative to the skill folder. Paths in the skills use `<SKILL_DIR>` and `<PLUGIN>`, never a `${CLAUDE_…}` variable, and the selftest enforces this. Persona playtests use subagents where the agent has them, and one persona after another where it doesn't.

**Hooks.** `hooks.py` reads Claude Code and Codex events alike. It also understands Codex's `apply_patch` and shell tools, and blocks Codex with exit 2. Agents without hooks get the same rules from the skill text: never tick a gate box, and run a quick playtest after each feature.

**Data folder.** Claude Code passes `CLAUDE_PLUGIN_DATA`. Other agents use `PLAYBENCH_DATA`, or `~/.playbench` by default.

## Requirements
- **Python 3.11+.** The scripts use the stdlib only.
- **For web playtests, balance sweeps and boot checks:** Playwright with Chromium. Install it with the exact line `status` prints, for example:
  `python -m pip install playwright && python -m playwright install chromium`
  The studio, design, `ship artgate` and `ship gate` features work without it.
- **If pip refuses** (PEP 668 "externally managed"), `status` prints a venv recipe instead (`INSTALL=` and `VENV=`). The venv lives in the plugin's data folder (`CLAUDE_PLUGIN_DATA`); once it has Playwright, `RUN` becomes its quoted interpreter path.
- **Rendering:** playtests use the real GPU on Windows and macOS. That's much faster for heavy canvas games. Set `PLAYBENCH_GPU=0` to force software rendering (SwiftShader), which Linux and CI use by default.
- **For `art`:** Pillow (`python -m pip install pillow`), only for the commands that draw or pack.
- **Optional binaries**, never downloaded by playbench:
  - `GODOT`: a Godot 4 editor executable, for Godot native playtests and sweeps (experimental).
  - `ASEPRITE` (or `aseprite` on PATH): for `art.py aseprite`.
  - `butler`, `steamcmd`, `netlify`: for uploads. playbench prints upload commands; it runs them only with `--real` (see [Ship](#ship)).

## Who it's for
- **Game-jammer** (`jam`): a deadline countdown, a 3-seed quick playtest, gates `playable -> submitted`, a jam-ready itch zip and checklist. Steam stays hidden.
- **Solo hobbyist** (`hobby`): the must list is capped at hours/week × weeks, warnings fire at 5 commits without a bot playtest and 20 without a human one, and gates are `prototype -> slice -> release`.
- **Small indie team** (`team`): every gate box has an owner, every playtest is diffed against the last one, the Steam vdf and store-asset checks are included, and `ship gate` shows who ticked each box (git blame).
- **Low-code designer** (coding = 1, any context): Claude writes the probe adapter and the bot, moves tunables into data files, and reports each verdict in one plain line.
- **Student or educator** (`learn`): a course AI policy (`open`, `disclose` or `banned`), a rubric block on playtest reports, and under `banned` Claude only explains, reviews and runs checks.

## 60-second jam quickstart
1. Open your agent (Claude Code, Codex, Cursor, …) in your game folder and say **"set up playbench for a jam"**. The studio skill asks: kind of project, coding comfort, engine, target and deadline.
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

**Decision points** (for [agent playtests](#agent-playtests)): a state with a non-empty `choices` list or `decision: true` tells the agent to stop and choose.

**Unity WebGL (verified on Unity 6000.2.8f1, see [examples/dodge-unity](../examples/dodge-unity) and [docs/unity-verification.md](unity-verification.md)).**
- Define `window.__game` in a `.jslib` (a `$X__postset`), so it exists before the first C# frame. Return `{paused:true}` until C# pushes its first state.
- C# can't see the harness's seeded `Math.random`, so read the seed and overrides from `window.__playbench` through jslib functions. File overrides use the path `StreamingAssets/<file>`.
- Build with compression **Disabled**. The harness's static server sends no `Content-Encoding` header.
- Unity only logs C# exceptions to the console. The harness reports them as a `crash` FAIL.
- Quick mode takes about 1–2 minutes on wasm builds, against about 40 s for plain JS.

**Godot (experimental, tested against a stub only).** The main scene's root node may define `probe_state() -> Dictionary`, `probe_seed(seed)`, `probe_actions() -> Array[String]`, `probe_bot(state) -> Array[String]` and `probe_knobs(knobs: Dictionary)`.
- Overrides reach the game as user args `--<name>=<value>`; `probe.gd` collects them and calls `probe_knobs` before the scene's `_ready`, so balance sweeps work on Godot too.
- `playtest.py run ... --windowed` drops `--headless` and saves a frame every second, so frozen-screen and dead-input checks and FAIL screenshots work.

**Tiers** are detected automatically:
- **T0** needs nothing. It finds boot failures, errors, a frozen canvas and dead input.
- **T1** needs a readable state. It adds softlock and state-based dead-input checks.
- **T2** needs a bot. It adds win rate and time-to-over, labelled *relative difficulty under policy bot*.

## Commands
| Skill | Scripts it runs |
|---|---|
| `/playbench:studio`: setup, status, what next | `studio.py detect`, `studio.py init --context jam\|hobby\|team\|learn …`, `studio.py status` |
| `/playbench:design`: one discussion, one page | none (it writes `design/design.md`) |
| `/playbench:build`: one small slice, then a quick playtest | `playtest.py run <build> --mode quick --out playtests` |
| `/playbench:art`: art bible, labelled placeholders, atlases | `art.py placeholder\|placeholders\|pack\|aseprite\|lint` |
| `/playbench:playtest`: quick, milestone and final bot playtests | `playtest.py run <build> --mode quick\|milestone\|final [--bot mash\|script:<file>] --out playtests`, `playtest.py agent\|sheet\|survey` |
| `/playbench:balance`: knobs, prices, economies, matchups | `balance.py sweep\|costcurve\|sim\|matrix` |
| `/playbench:log`: human sessions and the dev journal | `playtest.py sheet\|survey`, `telemetry.py snippet\|report` |
| `/playbench:feedback`: player comments into one ranked list | none (it writes `feedback/<date>-<source>.md`) |
| `/playbench:iterate`: one ranked change list from the evidence | none (it writes `design/iterations/<n>.md`) |
| `/playbench:ship`: release gates and uploads | `ship.py artgate\|gate\|itch\|steam\|web\|theme\|demo [--real]` |
| `/playbench:postmortem`: what happened, with evidence | `studio.py aiuse . --md`, `ship.py gate` |

Every script has a `selftest`. Run them all with `python scripts/selftest.py`, which also lints every `skills/*/SKILL.md` and runs `claude plugin validate . --strict`. Scripts print `KEY=value` lines and exit 0 pass, 1 blocked or FAIL, 2 usage or environment error.

### Loops and `status`
Each loop has one skill, and every skill ends with one line `Next loop: <loop> (/playbench:<skill>)`. `studio.py status` derives the current loop from files and git; nothing is counted or stored.

| Key | Meaning |
|---|---|
| `LOOP` | one of `design build test balance iterate log ship` |
| `LOOPMAP` | `design > build > [test] > balance > iterate > log > ship`, current loop in brackets |
| `NEXT` | the skill to run for `LOOP` |
| `AUTO_PLAYTEST` | `on`, or `off` when `studio.json` has `"auto_playtest": false` |
| `ITERATION` | `<n> <date>` of the newest `design/iterations/<n>.md`, or `none` |
| `SINCE_ITERATION` | new evidence since then: `playtests:<a> human:<b> feedback:<c> balance:<d> telemetry:<e>` |

`LOOP` picks the first that applies: no design yet (`design`); shipped (`ship`, then `/playbench:postmortem`); quick debt over the limit (`test`); the newest quick playtest FAILs (`build`); a required playtest is missing (`test`); human debt, or a gate wants a human playtest that has none (`log`); human notes or feedback since the last iteration (`iterate`); knobs listed but never balanced past the first stage (`balance`); the last stage (`ship`); otherwise `build`.

`studio.py aiuse [dir] [--md]` summarizes AI use from git: a commit counts as Claude's when a `Co-Authored-By` trailer names Claude. It prints `AI_COMMITS`, `HUMAN_COMMITS`, `AI_LINES`, `HUMAN_LINES`, `AI_SHARE`, `AI_FILES` and `AI_FILES_HUMAN_EDITED`; `--md` adds a block for course reports and postmortems. Squash merges and uncredited pastes are invisible to it.

### Plugin hooks
`hooks/hooks.json` runs `scripts/hooks.py` in every session, but it acts only in a folder (or up to 3 parents) with `studio.json`. It is stdlib only, typically well under a second, always exits 0 (an error lets the action through), and falls back from `python` to `py -3` when `python` is the Windows Store stub.
- **Gate guard (PreToolUse** on Edit, Write, MultiEdit, Bash, PowerShell): denies any edit that raises the number of ticked boxes in a `gates.md` next to `studio.json`, and any shell command that names `gates.md` with a tick pattern and a writer (`>`, `sed`, `Set-Content`, ...). Reading `gates.md` stays allowed. Humans tick by hand.
- **Auto-playtest reminder (Stop):** when game files changed during the turn and commits since the last quick playtest reach the profile's limit, it blocks the stop once and asks Claude to run a quick playtest. It never runs the playtest itself, never loops (`stop_hook_active`), reminds once per burst of changes, ignores playbench's own records and `.md` files, and is off with `"auto_playtest": false`.

### Bots
`playtest.py run <build> --bot <name>` picks the bot (default: by mode and tier):

| Bot | Plays |
|---|---|
| `idle` | nothing (the baseline for dead-input checks) |
| `random` | random actions |
| `policy` | the game's own `bot(state)` / `probe_bot` |
| `mash` | every 100 ms a fresh random set of keys, start keys included (seeded) |
| `script:<file.json>` | `[{"t": 0.0, "keys": ["ArrowRight"]}, {"t": 1.5, "keys": []}]`: each entry held from its `t` until the next; the last keys stay held |

**The 0.1 s grid.** Bots act on a fixed 100 ms step (web and Godot): at each step the harness reads the state, then presses the keys of the last script entry with `t` at or before that step. An entry held for less than one step (e.g. a tap at `1.21` released at `1.25`) is never pressed, and the harness prints a `WARN` naming it. Keep entries at least 0.1 s apart; a tap is a press at `t` and a release at `t + 0.1`. Web runs use Playwright's fake clock, paused at a fixed epoch with `performance.now()` starting at 0, so the same script and seed replay exactly.

Other `run` flags: `--seeds N`, `--seconds S`, `--override FILE:KEY=V` or `NAME=V` (repeatable), `--realtime` (threaded builds), `--coop` (COOP/COEP headers), `--windowed` (Godot), `--out playtests`.

Reports are named `<stamp>-<mode>.json/.md`. A run with an explicit bot other than `policy` (`--bot mash`, `random`, `idle`, `script:…`) is named `<stamp>-<mode>-<bot>.json/.md` instead: it is compared only with earlier runs of that bot, and it never becomes the `<mode>` regression baseline or clears quick playtest debt in `status`.

### Agent playtests
For menus, puzzles and choice-driven games (web only; not under `AI_POLICY=banned`):

`playtest.py agent <build> --script playtests/agent/<name>.json [--seed 1] [--seconds S] [--then pause|idle|random|policy] [--out playtests]`

- It plays the script (created as `[]` if missing), then the `--then` bot (default `pause`: stop where the script ends). `--seconds` caps the whole run; the default is the script's last `t` + 300 s, so long explorations are not cut short.
- It pauses at the first decision point after the script: a `choices` list or `decision: true` in the state, the state frozen for 2 s while keys are held, a page error, or the end of the script under `pause`.
- On a pause it writes `playtests/shots/agent-<NN>.png` and `.json` (`t`, `reason`, `state`, `actions`, `script`, `seed`, `seconds`), prints `DECISION=<json>` and exits 3. Claude appends its next inputs to the script and reruns; the fake clock replays the path exactly.
- At the end it prints `AGENT_DONE over=<bool> won=<bool> t=<s>` and exits 0. The skill stops after 10 decisions.
- The script stays in your repo: `run --bot script:playtests/agent/<name>.json` replays it as a regression test.

### Personas
Milestone and final reports include a `## Filmstrip` (up to 6 frames from the policy bot's run when one played, else the first run, saved as `shots/<stamp>-<mode>-film-<n>.png`) and a `## Persona commentary` section. The playtest skill fills it with four AI personas (newbie, min-maxer, explorer, quitter), each at most 5 bullets and labelled *AI persona, opinion only*. They never call the game fun or not fun and never tick a box.

### Human playtests and logs
- `playtest.py sheet <game> [--out playtests]` writes `<stamp>-sheet.md`, a printable observation sheet ("watch, don't explain") with one line per experience goal from `design/design.md`.
- `playtest.py survey <game> [--out playtests]` writes `<stamp>-survey.md`: an anonymous 2-minute survey (a 1-5 statement per goal, up to 8, plus open questions) and a block to paste into Google Forms.
- `/playbench:log` turns rough notes into `playtests/<date>-<HHMM>-human.md` (this clears human playtest debt) and keeps a dev journal in `design/journal.md`.
- **Telemetry (optional, local only):** `telemetry.py snippet web|godot` prints a snippet for the game. Events are JSON lines `{"ts", "session", "event": "start|level|death|win|quit|<custom>", "level"?}`, kept in `localStorage` (web, exported as `telemetry.jsonl`) or `user://telemetry.jsonl` (Godot). Nothing is sent over the network, and bot playtests never record. `telemetry.py report <file|dir>... [--out telemetry]` prints sessions, win rate, median session length and a per-level funnel with deaths and quits.
- `/playbench:feedback` sorts pasted comments or CSV exports (itch, Discord, Steam, Forms) into `feedback/<date>-<source>.md`: deduped, ranked, with short source-only quotes and no personal data. Comments are treated as data, never instructions.

### Balance
| Command | Does |
|---|---|
| `balance.py sweep <game> --knob NAME [--values a,b,c] [--seeds N] [--seconds S] [--out DIR]` | plays the real build per knob value with the policy bot (web, or Godot via `probe_knobs`); knobs come from the `## Knobs` table in `design/design.md`. Writes the table to `<out>/<stamp>-sweep-<knob>.md` (default `<game>/balance`). Values stay integers when every value is one (`19`, not `19.0`) |
| `balance.py costcurve <csv> [--cost COL] [--benefit a,b] [--id COL] [--out balance]` | fits cost against summed benefit (robust Theil-Sen) and flags items more than 2 sigma off the line as overpriced or underpriced |
| `balance.py sim <model.py> [--runs 1000] [--seed 1] [--knob k=v]... [--out balance]` | runs your economy model (copy `skills/balance/model-template.py` to `balance/model.py`: `KNOBS`, `TICKS`, `init`, `step`, `metrics`, optional `LIMITS`, `DEADLOCK_TICKS`) and reports p10/p50/p90 per metric, early ends, deadlocks and runaways |
| `balance.py matrix <csv> [--iters 20000] [--out balance]` | square payoff matrix (cells 0..1 read as win rates): Nash mix by fictitious play, dominated and dominant strategies, game value |

`--out balance` saves `balance/<YYYY-MM-DD-HHMM>-<kind>.md` and prints `REPORT=<path>` (`sweep` always saves, as `<stamp>-sweep-<knob>.md`). A model sim is only as true as the model; real players are not Nash players.

### Art
The art skill writes `art/bible.md` (palette with `bg`, `text`, `link`, `button` roles, fonts, pixel density, proportions, an animations table); the human approves it.

| Command | Does |
|---|---|
| `art.py placeholder <game> --name hero [--anim run] [--frames 4] [--size 16x16] [--color <palette name or #rrggbb>]` | one hatched, numbered sprite sheet `art/hero_run_placeholder.png` |
| `art.py placeholders <game>` | one sheet per `## Animations` row, skipping sprites that already have final art |
| `art.py pack <pngs or dirs>... --out <base> [--padding 2] [--pot]` | atlas `<base>.png` + `<base>.json` (TexturePacker JSON hash); a placeholder input makes a `_placeholder` atlas |
| `art.py aseprite <file.aseprite> --out <base>` | runs Aseprite in batch mode to a sheet + json-hash data |
| `art.py lint <game>` | lowercase `a-z 0-9 _` names, `_placeholder` last, every placeholder listed in `art/PLACEHOLDERS.json` and every listed file present, no case-only duplicates |

Every generated image gets a `_placeholder` name, PNG metadata naming playbench, and an entry in `art/PLACEHOLDERS.json` (`source: "generated"`), so `ship artgate` blocks it until it is replaced or disclosed.

### Ship
| Command | Does |
|---|---|
| `ship.py artgate [game] [--dirs a,b]` | the [AI-art](#ai-art-policy) scan of the build and `store/` |
| `ship.py gate [game]` | which gate boxes are ticked, committed and tracked, and who ticked them (git blame) |
| `ship.py itch [game] [--real]` | itch limits, `build/itch.zip`, a boot check of the zip, `butler push ... --dry-run`, the dashboard steps and a jam checklist |
| `ship.py steam [game] [--real]` | `steam/app_build.vdf` (Preview on), store capsules, library assets (`library_capsule`, `library_header`, `library_hero`, a transparent `library_logo`) and 5+ 16:9 screenshots in `store/` |
| `ship.py web [game] [--host pages\|netlify] [--real]` | URL checks and a boot check, GitHub Pages steps (you push), a Netlify draft deploy and `netlify.toml` (written only if absent) |
| `ship.py theme [game] [--css]` | itch page theme from `art/bible.md`: `store/itch-theme.md` checklist with WCAG contrast checks, an offline `store/itch-theme.html` preview, optional `store/itch-custom.css` |
| `ship.py demo [game]` | Steam Playtest and Next Fest checklist; with `steam.demo_appid` and `demo_depotid` in `studio.json`, a `steam/demo_build.vdf` |

**`--real`** (itch, steam, web `--host netlify`) runs `butler`, `steamcmd` or `netlify` only when artgate passes, every stage in `gates.md` is ticked, committed and tracked, and the boot check passes; otherwise it prints why the upload was withheld. It never runs `git push`. When `build_dir` is the game root, uploads use a staged copy in `build/upload/` without playtests, design notes, feedback, telemetry, the art bible or Aseprite sources.

### State files
Everything lives as plain files in your game repo. There is no database. Stage, debt and loop are derived from git and the files, so team members don't get merge conflicts.

| Path | Written by |
|---|---|
| `studio.json`, `gates.md` | `studio init` (only humans tick `gates.md`) |
| `design/design.md`, `design/build-log.md`, `design/iterations/<n>.md`, `design/journal.md`, `design/postmortem.md` | design, build, iterate, log, postmortem skills |
| `art/bible.md`, `art/*_placeholder.png`, `art/PLACEHOLDERS.json`, `disclosure.md` | art skill and `art.py`; `disclosure.md` by you |
| `playtests/<stamp>-<mode>[-<bot>].json/.md`, `playtests/shots/`, `playtests/agent/<name>.json` | `playtest.py run` and `agent` |
| `playtests/<stamp>-sheet.md`, `-survey.md`, `<date>-<HHMM>-human.md` | `playtest.py sheet`/`survey`, log skill |
| `balance/last.json`, `balance/<stamp>-<kind>.md`, `balance/model.py` | `balance.py`; the model is your code |
| `feedback/<date>-<source>.md` | feedback skill |
| `telemetry/*.jsonl`, `telemetry/<stamp>-report.md` | the game snippet; `telemetry.py report` |
| `store/`, `steam/*.vdf`, `build/itch.zip`, `build/upload/`, `netlify.toml` | `ship.py` |

## What bots can't judge
Bots find crashes, softlocks, dead input, frozen screens and relative difficulty shifts. They cannot judge **fun, clarity, feel or art**. A human playtest (`playtests/<date>-<HHMM>-human.md`, from the observation sheet, logged with `/playbench:log`) is required before gates. **Only humans tick gate boxes**: Claude never writes `[x]`, and `ship gate` shows who ticked each box with git blame.

## AI-art policy
- AI art is only for clearly marked placeholders: a `_placeholder` filename and an entry in `art/PLACEHOLDERS.json`.
- `ship artgate` scans the build and `store/`. It flags placeholder names, PNG generator metadata (`parameters`, `prompt` or `workflow` chunks, and generator names), C2PA (`caBX`) and JPEG/WebP generator bytes. It blocks unless every flagged file is covered by a line in `disclosure.md`.
- On a pass it reminds you to fill in Steam's AI content survey and itch's AI tag.
- Detection is heuristic, so stripped metadata gets through. It is a safety net for honest developers, not enforcement.

## Use it in your next jam
- Install it before the jam starts, and run `studio init --context jam --deadline <ISO>` in an empty folder.
- Keep the quick playtest after every feature: 3 seeds × 30 s: about 40 s for plain JS, 1–2 minutes for Unity/wasm. It catches the "broke the title screen at hour 40" bug.
- Run `ship itch` early, on day one. It catches root-absolute URLs, case-mismatched asset paths and the 1000-file limit while there is still time to fix them.
- After the jam, share your `playtests/*.md` and what the bots missed. Issues and PRs are welcome.
