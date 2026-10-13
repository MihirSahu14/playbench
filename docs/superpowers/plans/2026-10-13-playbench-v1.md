# playbench v1: Implementation Plan

**Spec:** `docs/superpowers/specs/2026-10-13-playbench-design.md`. Read it first; it is the contract.
**Repo:** `C:\Users\mihir\Desktop\Projects\Game Design Plugin`. The plugin root is the repo root. The platform is Windows 11 with Git Bash and PowerShell.
**Style:** lazy and minimal.
- Use the stdlib only. `playwright` is the one exception, imported lazily in `playtest.py`.
- Use the fewest files possible, with no speculative abstractions.
- Every non-trivial script gets a `selftest` subcommand built from plain asserts. It prints `ok <name>` or `SKIP <name>: <reason>` and exits non-zero on failure.
- Do not git commit (the user decides).

## Environment facts
- `python` is 3.11.0 with playwright 1.59.0 and Chromium installed. `py -3` is 3.13.5 **without** playwright.
- `claude plugin validate <path> --strict` exists (Claude Code 2.1.286).
- godot, butler and steamcmd are **not** installed, and `$GODOT` is empty. Downloading Godot needs the user's explicit OK, so no package downloads it.

## Order
1. **Task 1, the spike (P1, first):** check `${CLAUDE_PLUGIN_ROOT}` substitution in SKILL `!` lines on Windows and which shell runs them; check `claude plugin validate . --strict`.
2. **Tasks 2-6, in parallel:** packages P1-P5 below. They own disjoint files and share only the contracts in the spec:
   - the probe contract
   - `playtest.run()` and its report JSON
   - the state files
   - the `status` output keys, defined in P1 and copied here
3. **Integration:**
   - Run `python scripts/selftest.py` from the repo root.
   - If the spike showed `${CLAUDE_PLUGIN_ROOT}` is not substituted, replace the dynamic-context line in all five SKILLs with the fallback recorded in README.md.
   - Run one end-to-end session on a copy of `examples/dodge-web`: init → status → quick playtest → `ship itch`.
4. **Report to the user:**
   - The selftest output.
   - Godot status, which stays experimental unless Godot is available. Ask the user before downloading the portable Godot 4 editor (about 82 MB, from github.com/godotengine/godot releases).
   - Anything that was cut.

## Shared conventions (every package follows these)
**Dynamic-context line.** Every `SKILL.md` body starts with this exact line, right after the frontmatter:
```
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playbench: no working Python 3 found"`
```

**Frontmatter:**
```
---
name: <skill>
description: <when to use; third person; mention game dev words users say>
allowed-tools: Bash(python:*), Bash(py:*), Read, Write, Edit, Glob, Grep
---
```

**`status` output.** Lines are `KEY=value` and SKILLs parse them:

| Key | Value |
|---|---|
| `RUN` | `python`, `py -3`, `python3` or `NONE` |
| `PLUGIN` | absolute plugin root |
| `PLAYWRIGHT` | `yes` or `no` |
| `INSTALL` | only when no |
| `GODOT` | path or `none` |
| `GAME` | cwd |
| `INIT` | `yes` or `no` |
| `CONTEXT`, `CODING`, `AI_POLICY`, `ENGINE`, `BUILD`, `PLATFORMS` | |
| `STAGE` | |
| `REQUIRED` | comma-separated modes |
| `SIZES` | `quick:3x30 milestone:8x60 final:8x60` |
| `DEBT_QUICK` | `n/limit[ WARN]` |
| `DEBT_HUMAN` | `n/limit[ WARN]` or `n/-` |
| `DEADLINE` | `<h>h left` or `-` |
| `BALANCE` | `on` or `off` |
| `ALLOWED` | only when ai_policy=banned: `explain,review,status,playtest-T0,artgate` |
| `UNTICKED:` | followed by indented box lines |
| `NEXT` | one-line suggestion |

Scripts are always invoked as `<RUN> "<PLUGIN>/scripts/<x>.py" …`.

**Rules for every SKILL:**
- Never write `[x]` into `gates.md`. Tell the human which box they can tick.
- Check `AI_POLICY`. If it is `banned` and the action is outside `ALLOWED`, refuse and list what is allowed.
- Word things by `CODING`:
  - 1: plain one-line verdicts. Claude writes adapters and bots.
  - 2: Claude writes and the human reviews.
  - 3: Claude explains the contract and reviews the human's code.
- Ask one question at a time, each with a default.
- Every SKILL body stays under about 120 lines.

## Packages
Each package below is self-contained. The same text is handed to the builder agents.

### P1: Core (plugin manifests, README, studio, design, selftest runner)
**Owns:**
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- `README.md`, `.gitignore`
- `scripts/studio.py`, `scripts/selftest.py`
- `skills/studio/SKILL.md`
- `skills/design/SKILL.md`, `skills/design/design-template.md`

### P2: Fixture games (`examples/dodge-web`, `examples/dodge-godot`)
**Owns:** `examples/**`

### P3: Playtest harness
**Owns:** `scripts/playtest.py`, `scripts/probe.gd`, `skills/playtest/SKILL.md`, `skills/playtest/sheet-template.md`

### P4: Balance sweep
**Owns:** `scripts/balance.py`, `skills/balance/SKILL.md`

### P5: Ship
**Owns:** `scripts/ship.py`, `skills/ship/SKILL.md`

The full build instructions and acceptance checks for each package are in the section below. Builders get the identical text.

## Package instructions

#### P1: Core (manifests, README, studio.py, studio and design skills, selftest runner)

**Repo:** `C:\Users\mihir\Desktop\Projects\Game Design Plugin` (Windows 11, Git Bash). The plugin root is the repo root. Read `docs/superpowers/specs/2026-10-13-playbench-design.md` first (sections: Goal, Segments, Architecture/Script invocation, State files, Gates, Errors, Testing) and the "Shared conventions" section of `docs/superpowers/plans/2026-10-13-playbench-v1.md`.

**Style:**
- Stdlib only, fewest files, no abstractions for one use.
- One `selftest` subcommand built from asserts.
- Do NOT git commit. Do NOT download anything.

**You own exactly these files:**
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `README.md`
- `.gitignore`
- `scripts/studio.py`
- `scripts/selftest.py`
- `skills/studio/SKILL.md`
- `skills/design/SKILL.md`
- `skills/design/design-template.md`

Other agents build `examples/`, `scripts/playtest.py`, `scripts/probe.gd`, `scripts/balance.py`, `scripts/ship.py` and the other skills in parallel. Do not create or edit those.

**Step 1: spike (do it first; record the results in README.md under "## Implementation notes")**
1. Write `.claude-plugin/plugin.json`:
   ```
   {"name":"playbench","version":"0.1.0","description":"Bots play your real game build after every feature, balance sweeps on the real build, and itch/Steam release gates that block undisclosed AI/placeholder art. Lean one-page design. Adapts to jam, hobby, team or classroom use.","author":{"name":"Mihir Sahu"},"license":"MIT","keywords":["gamedev","playtest","itch","steam","godot","balance"]}
   ```
   Write `.claude-plugin/marketplace.json`:
   ```
   {"name":"playbench","owner":{"name":"Mihir Sahu"},"plugins":[{"name":"playbench","source":"./","description":"<same as above>"}]}
   ```
   If `--strict` complains about a field, adjust it.
2. Create a throwaway skill at `skills/spike/SKILL.md`. Its frontmatter is name `spike` and a description. Its body is the line:
   ```
   !`echo "root=${CLAUDE_PLUGIN_ROOT} skill=${CLAUDE_SKILL_DIR} shell=$0"`
   ```
3. Run:
   ```
   claude -p "/playbench:spike reply with the exact text shown after root=" --plugin-dir "C:\Users\mihir\Desktop\Projects\Game Design Plugin"
   ```
   If `-p` is unavailable, use whatever non-interactive form `claude --help` shows. Record whether `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_SKILL_DIR}` were substituted and which shell ran the line.
4. Delete `skills/spike/` afterwards.
5. Run `claude plugin validate . --strict` and record the output.
6. If `${CLAUDE_PLUGIN_ROOT}` is not substituted, write the working replacement line in the README notes, for example using `${CLAUDE_SKILL_DIR}/../../scripts/studio.py`. Use that line in your own two SKILLs. The orchestrator will patch the other SKILLs.

**Step 2: `scripts/studio.py`.** This is a stdlib CLI using argparse with subcommands `detect`, `init`, `status` and `selftest`. Every command takes an optional game dir (default cwd).

**`PROFILE`, one dict keyed by context.** `coding` never selects a profile.
- `stages`:
  - jam: `["playable","submitted"]`
  - hobby: `["prototype","slice","release"]`
  - team: `["prototype","slice","alpha","beta","release"]`
  - learn: `["prototype","submitted"]`
- `sizes`: seeds and seconds per mode.
  - jam: quick (3,30), milestone (5,60), final (5,60).
  - Every other context: quick (3,30), milestone (8,60), final (8,60).
- `debt_quick`: jam 3, others 5.
- `debt_human`: jam None (shown, never warned), hobby 20, team 15, learn 20.
- `balance`: False for jam, True for the others.
- `targets`:
  - jam: `["itch","web"]`
  - hobby: `["itch","steam","web"]`
  - team: `["steam","itch","web"]`
  - learn: `["itch","web"]`
- `design`: the list of design-page sections. jam: `["hook","core_loop","must_cut","experience_goals","knobs"]`. Other contexts add `"pillars"` and `"decision"`.

**`REQUIRED`** modes per stage:
- prototype and playable: `["quick"]`
- slice and alpha: `["quick","milestone"]`
- beta and release: `["quick","milestone","final"]`
- submitted: `["quick","final"]`

**`BOXES`**, the box lines per stage (exact text):
- prototype / playable:
  - "Latest quick playtest is PASS"
  - "A human played it and saved playtests/<date>-human.md"
  - "Decision: GO is written in design/design.md". This box is omitted for jam.
- slice:
  - "Milestone playtest PASS or every WARN triaged"
  - "Every experience goal marked met or waived on a human sheet"
- alpha:
  - "Every must-list feature is in the build"
  - "Milestone playtest shows no new FAIL kinds"
- beta:
  - "art/PLACEHOLDERS.json is empty or every entry is covered by disclosure.md"
  - "Final playtest run on the packaged build"
- release / submitted:
  - "Final playtest is PASS"
  - "ship artgate passes"
  - "Store/itch page reviewed by a human"
  - "I approve this release"

**`detect`** prints `ENGINE=` and `TIER_HINT=`:
- `project.godot` in the dir gives `godot`.
- Otherwise web if any of these holds: `index.html` in the dir; `index.html` in `build/`, `dist/`, `export/`, `public/` or `web/`; or `package.json` mentioning phaser, three, pixi or kaboom. Web builds report BUILD as the first dir that contains `index.html`.
- Otherwise `unknown`.

**`init`** takes `--context {jam,hobby,team,learn}` (required) and these optional flags:
- `--coding {1,2,3}` (default 2)
- `--engine` (default: detected)
- `--build-dir` (default: detected or `.`)
- `--platforms` (comma list; default: the first profile target)
- `--deadline ISO8601`, `--hours N`, `--weeks N`
- `--ai-policy {open,disclose,banned}` (only for learn; default `disclose`)
- `--itch user/game`
- `--member "Name:owns:stage1,stage2"`, repeatable (team only)
- `--force`

What init does:
1. Writes `studio.json` with exactly the keys in the spec's State files table. Keys whose value is None are dropped.
2. Writes `gates.md` with:
   - the header `# Gates` and the line `Only humans tick these boxes. Claude never ticks them; ship gate shows who did.`
   - one `## <stage>` per profile stage, each followed by `- [ ] <box>` lines.
   - In team context, ` (owner: <name>)` appended to each box, using the member whose gates list contains that stage, or `(owner: unassigned)`.
3. Appends `playtests/shots/` to `.gitignore` in the game dir if it is missing.
4. Refuses (exit 1) if `studio.json` or `gates.md` exists, unless `--force` is given. **Init never writes `[x]`.**

**`status`** prints the KEY=value lines exactly as listed in the plan's Shared conventions:

| Key | How it is computed |
|---|---|
| `RUN` | Probe the candidates `["python"]`, `["py","-3"]` and `["python3"]` with `subprocess.run([...,"-c","import sys,importlib.util;print(sys.executable);print(importlib.util.find_spec('playwright') is not None)"], timeout=15)`. Ignore failures, timeouts and empty output (the WindowsApps stub). Choose the first that has playwright, else the first that works. Print the launcher as typed (e.g. `py -3`), never the absolute path. |
| `PLUGIN` | `Path(__file__).resolve().parents[1]` |
| `GODOT` | `$GODOT`, else `shutil.which("godot")`, else `none` |
| `INIT=no` | When there is no studio.json: print the detect output, then `NEXT=run studio init (the studio skill asks 4 short questions)` |
| `STAGE` | The first `## <stage>` with any `- [ ]`, or `shipped` |
| `DEBT_QUICK` | `git rev-list --count --since=<at> HEAD`, where `at` is taken from the newest `playtests/*-quick.json` by filename sort. With no reports, count all commits. |
| `DEBT_HUMAN` | The same, since the date prefix (`YYYY-MM-DD`) of the newest `playtests/*-human.md` |
| `DEADLINE` | Whole hours until `deadline_at` |

- If it isn't a git repo, print `DEBT_*=n/a (not a git repo)`.
- After `UNTICKED:`, print each unticked box of the current stage, indented.
- `NEXT` is a simple rule chain:
  1. not init → run init
  2. no `design/design.md` → design
  3. PLAYWRIGHT=no and engine=web → install
  4. quick debt over the limit → run a quick playtest
  5. any REQUIRED mode for this stage with no report since the last tick… Keep this simple: if the stage requires milestone and there is no milestone report, suggest it.
  6. otherwise "build the next must-list feature, then run a quick playtest"

**`selftest`** works in `tempfile.TemporaryDirectory()` dirs (do NOT depend on `examples/`) and checks:
- detect: a dir with `project.godot` gives godot; a dir with `build/index.html` gives web with BUILD=build.
- init: for every context × coding (12 combos), init writes valid JSON and a `gates.md` with zero `[x]` and the right stages. Team owner suffixes are present. A second init without `--force` exits 1.
- Stage derivation: tick boxes by editing text in the test only, then check that the stage advances and that all ticked gives `shipped`.
- Debt: `git init` a temp repo (set `user.name`/`user.email` with `-c` flags), make 3 commits, write `playtests/2000-01-01-0000-quick.json` with an old `at`, and assert DEBT_QUICK counts 3. Write one with a future `at` and assert 0.
- status prints every required key.

Finish with `print("ok studio")`.

**Step 3: `scripts/selftest.py`.**
1. For each of studio, playtest, balance and ship:
   - If `scripts/<x>.py` is missing, print `SKIP <x>: not built`.
   - Otherwise run `[sys.executable, path, "selftest"]` from the repo root and stream its output.
2. Then, if `shutil.which("claude")`, run `claude plugin validate . --strict`. Otherwise print SKIP.
3. Exit 1 if any run failed.

The whole file is under 40 lines.

**Step 4: `skills/studio/SKILL.md`** (name `studio`). The description: "Use when starting or resuming a game project, when the user asks what to do next, about project status, gates, playtest debt, jam deadline, or to set up playbench for jam/hobby/team/class use." The body covers:
1. The dynamic-context line, which comes first.
2. If `INIT=no`, ask one question at a time, each with a default:
   - context (jam / hobby / solo-but-commercial counts as hobby / team / learn)
   - coding comfort 1-3, described in plain words
   - engine (confirm the detected one)
   - target (itch / steam / web)
   - then, by context: jam asks the deadline; hobby asks hours/week and weeks; team asks the members and what each owns; learn asks the course AI policy.

   Then run `<RUN> "<PLUGIN>/scripts/studio.py" init …`.
3. Otherwise explain `status` in 3-5 plain lines, adapted to CONTEXT and CODING, and offer the `NEXT` step. Route to the other skills: `/playbench:design`, `/playbench:playtest`, `/playbench:balance` (only if BALANCE=on or the user asks), and `/playbench:ship`.
4. Hard rules:
   - Never tick gates.
   - Honor `ALLOWED` under banned.
   - When PLAYWRIGHT=no, show `INSTALL` and ask before running it.
   - Engines with no playwright path (native Unity/Unreal) get honest copy: playtests need a WebGL/HTML5 export. Godot native is experimental until verified.

**Step 5: `skills/design/SKILL.md`** (name `design`), prompt-only and the smallest skill. The description: "Use when the user wants to discuss a game idea, brainstorm (including jam themes), define the hook/core loop/scope, or write or update the one-page design."
- Run one conversation, one question at a time: idea, hook, core loop, then must/should/cut.
- When CONTEXT=jam, offer 5 theme interpretations first.
- Size the must list:
  - hobby: hours_per_week × weeks from studio.json. Each must item carries an hours estimate, and the sum must not exceed the budget.
  - jam: the hours left before the deadline.
- Write ONE experience goal per must feature.
- Write the knob table for every tunable number. Tell coding=1 users that Claude will move tunables into data files.
- Write `design/design.md` from `design-template.md`, dropping the sections not listed for the context (jam drops Pillars and Decision).
- Never write the Decision line's value; leave `Decision: ` for the human.
- Never more than one page (about 60 lines). On a re-run, edit in place.

**Step 6: `skills/design/design-template.md`.** Sections:
- `# <Title>`
- `## Hook` (one sentence)
- `## Pillars` (3 bullets; team/hobby/learn only)
- `## Core loop` (one line plus a 30s/5min arrow diagram)
- `## Scope`: a table `feature | must/should/cut | hours`, plus a `Budget: <h> h` line
- `## Experience goals`: `- <feature>: <what the player should feel or understand>`
- `## Knobs`: the table header exactly `| name | file | key | min | max |`, with a comment row explaining that file `-` means bundled and is read via `window.__playbench.overrides`. CSV keys are `<id>.<column>` or `*.<column>`; JSON keys are dotted paths.
- `## Decision`: the line `Decision: ` (human writes GO or KILL)

**Step 7: README.md.**
- What playbench is (the spec Goal, honest about web-first and Godot experimental).
- Install, using either:
  - `claude plugin marketplace add <repo path or URL>` then `claude plugin install playbench@playbench`, or
  - `--plugin-dir` for development.
- Requirements, with the exact Python/playwright install line.
- Who it's for: the 5 segments in one line each.
- The 60-second jam quickstart.
- The probe contract summary (copy the state shape and the `__game` API from the spec).
- Commands per skill.
- "What bots can't judge".
- The AI-art policy.
- "Use it in your next jam" (distribution).
- `## Implementation notes` with the spike results.

**Step 8: `.gitignore`.** Add `__pycache__/`, `*.pyc`, `examples/*/playtests/shots/`, `examples/*/build/` and `.venv/`.

**Acceptance checks (run all of them and paste the output in your final message):**
1. `python scripts/studio.py selftest` exits 0 and prints `ok studio`.
2. `py -3 scripts/studio.py selftest` exits 0 as well; the code must not need playwright.
3. `python scripts/studio.py status` in an empty temp dir prints `RUN=python`, `PLAYWRIGHT=yes` and `INIT=no`.
4. `python scripts/selftest.py` runs; the other scripts may SKIP if not built yet.
5. `claude plugin validate . --strict` passes, or report the exact errors that are caused by files you don't own.
6. `grep -n "\[x\]" scripts/studio.py` matches only parsing and selftest code.
7. README.md contains the spike results.

#### P2: Fixture games (`examples/dodge-web`, verified; `examples/dodge-godot`, experimental)

**Repo:** `C:\Users\mihir\Desktop\Projects\Game Design Plugin` (Windows 11). Read the "Probe contract" section of `docs/superpowers/specs/2026-10-13-playbench-design.md`. These two tiny games are the demo and the end-to-end test target for the playtest harness, the balance sweep and the ship checks, which other agents are building in parallel.

**Style:** plain JS with no build step and no dependencies; GDScript for Godot 4.3+. Keep each game file under about 200 lines. Do NOT git commit. Do NOT download Godot.

**You own:** everything under `examples/`. Nothing else.

**`examples/dodge-web/` files**
- `index.html`: contains `<canvas id="game" width="480" height="320">` and `<script src="game.js"></script>`. It uses only relative URLs, with no leading `/`.
- `game.js`
- `data/enemies.csv` with the header `id,speed,size,spawn_ms` and the rows `bat,2.0,12,900` and `slime,1.2,18,1400`.
- `art/hero_placeholder.png`: a 16×16 PNG generated once with a stdlib Python one-off (zlib + struct; don't commit the generator). It contains a `tEXt` chunk with key `parameters` and value `placeholder hero, pixel art`, so it is AI-tagged on purpose.
- `art/PLACEHOLDERS.json`: `{"placeholders":[{"path":"art/hero_placeholder.png","source":"ai","note":"temp hero sprite"}]}`
- `studio.json`: `{"context":"jam","coding":1,"engine":"web","build_dir":".","platforms":["itch"],"itch":"example/dodge-web"}`
- `design/design.md`: the one page, with Hook, Core loop, Scope, Experience goals and a `## Knobs` table with the exact header `| name | file | key | min | max |` and these rows:
  - `| bat_speed | data/enemies.csv | bat.speed | 1 | 4 |`
  - `| player_speed | - | player_speed | 2 | 6 |`
- Do NOT create `gates.md` or `disclosure.md`. The tests create them in temp copies.

**`game.js` behaviour (the contract the harness tests rely on)**
1. **Data:** on load, `fetch("data/enemies.csv")`, parse it, and start. Read the player speed from `(window.__playbench?.overrides ?? {}).player_speed ?? 4`, in pixels per frame at 60 fps (scale by dt).
2. **Title overlay:** the game starts behind an overlay reading "Press Enter or click to start". While the overlay is up, `paused` is true. Enter, Space or a canvas click starts the game. **Keys are listened for on `window` with `keydown`/`keyup`.**
3. **Loop:** a `requestAnimationFrame` loop that uses the rAF timestamp for dt (clamp dt to at most 50 ms). It uses only `Math.random()` for randomness and never `Date.now`.
4. **Gameplay:**
   - The player is a 16 px box (or the hero PNG if it loads) at the bottom and moves with ArrowLeft and ArrowRight.
   - Enemies spawn at random x, one timer per CSV row (`spawn_ms`), and fall at `speed` × 60 px/s. Each enemy's hitbox is a square `size` px wide.
   - Contact sets `over=true, won=false`.
   - Surviving 20 seconds of play sets `over=true, won=true`.
   - `score` = whole seconds survived.
   - After `over`, the loop stops updating but keeps drawing an end screen.
5. **The probe**, `window.__game`:
   - `state()` returns:
     - `{over, won, paused, score, px: Math.round(playerX), n: enemies.length, ey: Math.round(sum of enemy y), threats}`
     - `threats` is an array of `[dx, dy]`, rounded, for the 3 enemies nearest the player that are above it.
     - Do NOT include raw timers.
   - `actions` is `["ArrowLeft","ArrowRight","Enter"]`.
   - `bot(s)` is a heuristic dodger. If a threat has `|dx| < 30` and `dy < 140`, move away from it (the side with more room). Otherwise drift toward the centre. Return `[]`, `["ArrowLeft"]` or `["ArrowRight"]`. Tune it until the policy bot **wins in roughly 30-80% of seeds** at the default speeds and **clearly loses more** at `bat.speed=4`. Check this with the playwright snippet below.
6. **URL switches** (parse `location.search`):

| Switch | Behaviour |
|---|---|
| `?bug=softlock` | After 8 s of play, the update step stops changing anything: no movement, no spawns, no score. Drawing continues, `over` and `paused` stay false, and input is ignored. |
| `?bug=crash` | After 5 s of play, `throw new Error("planted crash")` inside the rAF callback. The loop dies, and the error is uncaught so it reaches `pageerror`. |
| `?bug=deadinput` | The key listeners ignore Arrow keys. Enter, Space and click still start the game. |
| `?noprobe` | Do not define `window.__game` at all (T0 only). |
| `?nobot` | Define `__game` without `bot` (T1). |

**Self-check.** This is a throwaway script in your scratchpad, not committed. Using `python` (which has playwright 1.59):
1. Serve `examples/dodge-web` with `http.server` on a thread.
2. `page.clock.install()`, then `goto`.
3. Click the canvas, then press Enter.
4. Loop `page.clock.run_for(100)`. Each step:
   - `s = page.evaluate("__game.state()")`
   - `keys = page.evaluate("__game.bot(__game.state())")`
   - hold those keys with `page.keyboard.down`/`up`
   - Before goto, inject the seed and a mulberry32 `Math.random` with `page.add_init_script`:
     ```
     window.__playbench={seed:N,overrides:{}};
     let a=N>>>0; Math.random=()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296};
     ```
   - Use Chromium headless with `args=["--use-angle=swiftshader"]`.
5. Confirm all of the following:
   - (a) Clean runs over seeds 1-8 end with a mix of wins and losses, and the state keeps changing.
   - (b) Two runs with the same seed and the idle bot (no keys) give the identical final `state()`, so the game is deterministic under page.clock.
   - (c) With the same seed, an idle run and a run holding ArrowLeft differ after 3 s.
   - (d) `?bug=deadinput`: idle and ArrowLeft give identical final state.
   - (e) `?bug=softlock`: the state is constant from about 8 s on, while not over.
   - (f) `?bug=crash` fires `pageerror`.
   - (g) Routing `**/data/enemies.csv` to a copy with bat speed 4 lowers the policy win rate.

**`examples/dodge-godot/` (experimental: Godot is not installed, so write it carefully and keep it minimal)**
- `project.godot`: `config_version=5`, `[application] config/name="dodge-godot"`, `run/main_scene="res://main.tscn"`, and `config/features=PackedStringArray("4.3")`. Use the built-in actions `ui_left`, `ui_right` and `ui_accept`, so no input map is needed.
- `main.tscn`: a single Node2D root named `Main` with `main.gd` attached. Use the minimal text-scene format `[gd_scene load_steps=2 format=3]`.
- `main.gd`: the same game as the web version.
  - Constants stand in for the CSV: bat 2.0/12/900 and slime 1.2/18/1400.
  - It uses a `RandomNumberGenerator` and runs in `_physics_process`, or in `_process` with fixed delta.
  - It draws with `_draw`, which works headless (no rendering).
  - It starts paused until `ui_accept`.
  - It reads the user args with `OS.get_cmdline_user_args()`. `bug=softlock` freezes after 8 s, and `bug=crash` calls an invalid method after 5 s to produce a SCRIPT ERROR.
  - Probe functions on the root:
    - `probe_seed(seed: int)` sets `rng.seed`.
    - `probe_state() -> Dictionary` returns the same keys as web.
    - `probe_actions() -> Array` returns `["ui_left","ui_right","ui_accept"]`.
    - `probe_bot(state: Dictionary) -> Array` mirrors the web bot.
  - Input is polled with `Input.is_action_pressed`, so both `parse_input_event` and `action_press` drive it.
- `export_presets.cfg`: one preset named `Web`, platform `Web`, export path `build/web/index.html`, with `variant/thread_support=false`.
- `README.md` (one paragraph): how to run it, `godot --path examples/dodge-godot`, and that it is experimental until verified with a real Godot binary.

**Acceptance checks (run them and paste the results):**
1. The scratchpad self-check above prints the outcomes for (a)-(g). All must hold. Report the clean policy win rate at default settings and at bat.speed=4.
2. `python -c "import json;json.load(open('examples/dodge-web/art/PLACEHOLDERS.json'));json.load(open('examples/dodge-web/studio.json'))"` succeeds.
3. A stdlib check that `art/hero_placeholder.png` starts with the PNG signature and contains `b"tEXtparameters"`.
4. `grep -rn "src=\"/\|href=\"/\|fetch(\"/" examples/dodge-web` finds nothing.
5. If `godot` happens to be on PATH or in `$GODOT`, run `godot --headless --path examples/dodge-godot --quit-after 120` and confirm there is no SCRIPT ERROR. Otherwise state "Godot not available: dodge-godot unverified".

#### P3: Playtest harness (web T0/T1/T2 verified; Godot native experimental)

**Repo:** `C:\Users\mihir\Desktop\Projects\Game Design Plugin` (Windows 11, Git Bash). Before you write code, read these sections of `docs/superpowers/specs/2026-10-13-playbench-design.md`: "Probe contract", "`playtest.run()`", "Report JSON", "Playtest cadence" and "Errors". Also read the "Shared conventions" section of `docs/superpowers/plans/2026-10-13-playbench-v1.md`. This is the plugin's headline feature.

**Style:**
- Stdlib, plus `playwright` imported lazily inside the web transport only. Use `python` (3.11, which has playwright 1.59 and Chromium).
- Keep it to one file plus probe.gd. The in-page probe JS is a string constant in playtest.py.
- No classes unless they earn their place. Aim for under about 450 lines.
- Do NOT git commit. Do NOT download anything; Godot is not installed.

**You own:**
- `scripts/playtest.py`
- `scripts/probe.gd`
- `skills/playtest/SKILL.md`
- `skills/playtest/sheet-template.md`

**Do not touch these, which other agents build in parallel:**
- `examples/dodge-web`: a plain-JS dodge game with `window.__game` and the URL switches `?bug=softlock|crash|deadinput`, `?noprobe` and `?nobot`.
- `examples/dodge-godot`
- `scripts/balance.py` and `scripts/ship.py`, which import `playtest.run`.

If `examples/dodge-web` is not there yet when you test, copy its contract (below) into a throwaway game in your scratchpad and test against that. Do not create files under `examples/`.

**The dodge-web contract, for your tests:**
- `index.html` plus `game.js`, which fetches `data/enemies.csv` (`id,speed,size,spawn_ms`; rows `bat,2.0,12,900` and `slime,1.2,18,1400`).
- A title overlay keeps `paused:true` until Enter, Space or a click.
- Arrow keys are read through `window` keydown and keyup.
- `__game.state()` returns `{over, won, paused, score, px, n, ey, threats}`.
- `__game.actions` is `["ArrowLeft","ArrowRight","Enter"]`.
- `__game.bot(s)` is a heuristic dodger.
- Surviving 20 s wins.
- The bundled knob is `(window.__playbench?.overrides??{}).player_speed ?? 4`.
- The bugs:
  - softlock freezes the state after 8 s of play, without being over or paused.
  - crash throws an uncaught error after 5 s.
  - deadinput ignores the Arrow keys.

**The public API (others depend on this exactly):**
```python
def run(build, mode="quick", bot=None, seeds=None, seconds=None, overrides=None,
        realtime=False, coop=False, out_dir=None) -> dict
```
It returns the report dict with exactly the keys of the spec's Report JSON:

`version, at, mode, engine, build, tier, verdict, summary, runs, findings, stats, overrides, regression, cannot_judge`

**Mode defaults (seeds, seconds):**

| Mode | Seeds | Seconds |
|---|---|---|
| quick | 3 | 30 |
| milestone | 8 | 60 |
| final | 8 | 60 |
| boot | 1 | 10 |
| sweep | 5 | 60 |

**Bot defaults:**
- quick, milestone and final: `random`, plus `policy` when T2 is available (one run per seed per bot).
- boot: `idle`.
- sweep: `policy`.

**CLI:**
```
playtest.py run <build> [--mode M] [--bot B] [--seeds N] [--seconds S] [--override SPEC]... [--realtime] [--coop] [--out DIR]
```
- It prints the `.md` report to stdout.
- It exits 0 on PASS or WARN, 1 on FAIL, and 2 on usage or environment errors.
- An override `SPEC` is either `path/to/file.csv:bat.speed=3` (the file form) or `player_speed=5` (the bundled form, where `file` is None and `name` = `key`). For the file form, `name` = `key`.

**Web transport, step by step**
1. **Build path.** If `build` ends in `.zip`, extract it to a temp dir with `zipfile` and use that as the build. The build dir must contain `index.html`; otherwise raise `SystemExit(2)` with a message saying what was looked for.
2. **Server.** `ThreadingHTTPServer` on `127.0.0.1:0`, with a `SimpleHTTPRequestHandler` subclass (`directory=build`) that silences logging. When `coop=True`, add `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp`.
3. **Playwright import.** `from playwright.sync_api import sync_playwright` sits inside a try block. On ImportError, raise `SystemExit(2)` with the message:

   `playwright not installed for <sys.executable>: run "<sys.executable>" -m pip install playwright && "<sys.executable>" -m playwright install chromium`
4. **One browser per `run()` call**, Chromium `headless=True, args=["--use-angle=swiftshader"]`, with **one new page per run (seed × bot)**. On each page:
   - (a) `page.clock.install()`, unless `realtime`.
   - (b) `add_init_script(PROBE_JS)`. PROBE_JS sets `window.__playbench={seed,overrides:{name:value...}}` and replaces `Math.random` with mulberry32 seeded from the seed:
     ```
     let a=seed>>>0; Math.random=()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296};
     ```
     It also defines `window.__playbench.read=()=>{...}`. That function returns a JSON-able state or null, trying in order:
     1. `__game.state` as a function
     2. `__game.state` as an object
     3. `JSON.parse(render_game_to_text())`
     4. `__GAME_STATE__`

     Wrap the read in try/catch and return `{"__error": msg}` on throw.
   - (c) For each override with a file, `page.route("**/" + file)`. The handler reads the file from disk, applies the override, and calls `route.fulfill(body=...)`:
     - **CSV:** open with `utf-8-sig`, find the delimiter with `csv.Sniffer().sniff(sample, ",;\t")`, falling back to `,`. A key `id.col` sets that cell in the row whose first column equals `id`. A key `*.col` sets that column in every row.
     - **JSON:** a dotted path, where digits index into lists.
     - Unknown row, column or path: raise `SystemExit(2)`.
   - (d) Listen for `pageerror` (a crash, FAIL) and for `console` messages of type error (`console_error`, WARN).
   - (e) `goto` the URL and wait for `domcontentloaded`. Then `run_for(500)` and check for a `canvas` element, polling up to 10 sim-s with `run_for(500)`. If there is still none, record a `boot` FAIL.
5. **Start sequence, identical for every bot including idle:**
   - click the canvas centre (`page.mouse.click`)
   - press Enter, then Space
   - `run_for(1000)`, or sleep 1 s if realtime
6. **Step loop**, until `seconds` of sim time or `state.over`:
   - Advance 100 ms with `run_for(100)` (or sleep when realtime).
   - Read the state.
   - Choose the keys:
     - `idle`: none.
     - `random`: re-pick every 300 ms. Choose a random subset of at most one key from `actions`, excluding Enter. Use Python's `random.Random(seed)`.
     - `policy`: `page.evaluate("s=>__game.bot(s)", state)`. On Godot, `probe_bot`.
   - Apply the key diff with `page.keyboard.down` and `up`.
   - Every 1 s of sim time, take `page.locator("canvas").first.screenshot()`, hash it with sha1, and keep the hash. **Note:** under page.clock the canvas only changes because `run_for` drives rAF, so the screenshots must be taken between `run_for` calls, never as a wait.
7. **The per-run record:**

   `{seed, bot, seconds: sim seconds actually run, over, won, time_to_over (sim s or None), timeline: [(t, state_hash, input_active)], shots: [(t, shot_hash, png_bytes_only_if_needed)], errors}`

   Keep only the PNG bytes of the latest shot in memory. Save a PNG only on a FAIL finding.

**State hash:** `sha1(json.dumps(filtered, sort_keys=True))`, where `filtered` drops keys that start with `_` and the keys `t`, `time`, `frame`, `tick` and `elapsed` (top level only).

**Tier:**
- 0 if `read()` returned null at the first post-start step.
- 2 if `typeof __game?.bot === "function"`; on Godot, if probe_bot exists.
- 1 otherwise.

**Detectors**, run over the run records:

| Finding | Rule |
|---|---|
| `boot` FAIL | No canvas, or goto failed. |
| `crash` FAIL | Any `pageerror`, or a state read that returned `__error`. On Godot, a stderr line containing `SCRIPT ERROR` or `ERROR:`, a nonzero exit, or a missing `PROBE_END`. |
| `console_error` WARN | One finding per distinct message, at most 5. |
| `softlock` FAIL (T1+) | The state hash is unchanged over a window of at least 5 sim-s, while input was active in that window, `over` is false and `paused` is false. Report the first occurrence per run. |
| `frozen` WARN (T0 only) | The screenshot hash is unchanged for 5 or more consecutive seconds while input is active. |
| `dead_input` | Deterministic replay, one extra pair of runs on seed 1, each for 3 sim-s after the start. |
| `nondeterministic` WARN | Raised by the determinism check below. |

For `dead_input`:
1. **Determinism check.** Run idle twice. If the final hashes differ, record `nondeterministic` and skip the dead-input check. The hash is the state hash at T1+, or the screenshot hash at T0.
2. **Idle versus input.** Run idle and a run holding each non-Enter action in turn for the whole 3 s, then compare each one's final hash with idle:
   - If every action matches idle, record `dead_input`: FAIL at T1+, WARN at T0 (T0 is noisy on turn-based, mouse-only and title-screen games).
   - In milestone and final, also add a per-action `dead_input` WARN for each action that matches idle when the others don't.
   - Quick runs only the first two non-Enter actions, to keep it fast.

**Stats:**
- T2 uses only the policy runs: `win_rate`, `tto_p10`, `tto_p50` and `tto_p90` over the runs that ended (use `statistics.quantiles(n=10)`, or the sorted values if there are fewer than 2 runs), and `deaths_per_min` = losses / total sim minutes. The label is `relative difficulty under policy bot`.
- T1 uses the same numbers from the random runs, with the label `random-input stats, not difficulty`.
- T0: `stats=None`.

**Verdict and summary:**
- The verdict is FAIL if any finding is FAIL, else WARN if any finding is WARN, else PASS.
- The summary is one plain line. Example: `PASS: boots, input works, no freezes or softlocks in 6 runs (tier 2)`. On FAIL: `FAIL: softlock at 8.0s (seed 2, random) — 1 more finding`.

**Regression.** When `out_dir` is set, find the newest earlier `*-<mode>.json` in it and set `regression = {prev, new_kinds, stat_shifts}`. Flag win-rate changes over 0.10 and p50 changes over 20%. With no earlier report, set it to None.

**Writing reports.** When `out_dir` is set:
1. Write `<out_dir>/<YYYY-MM-DD-HHMM>-<mode>.json` (`indent=1`) and `.md`.
2. Save FAIL screenshots to `<out_dir>/shots/<stamp>-<kind>-s<seed>.png`.
3. The `.md` contains, in order:
   - line 1 is the summary
   - a findings table
   - the stats with their label
   - regression
   - an `## Claude's review of anomaly screenshots` section with `(pending)` (milestone only)
   - the `cannot_judge` line
4. If `out_dir`'s parent (the game dir) has a `studio.json` with `context == "learn"`, append a rubric block: `## Rubric`, then Goal, Evidence (link the report), Met? (yes/no, filled by the student) and a Reflection prompt.
5. In milestone mode, also write `<out_dir>/<stamp>-sheet.md` from `skills/playtest/sheet-template.md`. Locate the template via `Path(__file__).parents[1]`, and fill `{{GOALS}}` with the bullet lines under `## Experience goals` in `<game>/design/design.md` (empty-safe).

**Godot transport** (experimental; implement it, and verify it only if Godot exists):
- Pick it when `project.godot` is in `build`.
- The binary is `os.environ.get("GODOT") or shutil.which("godot")`. If neither exists, raise `SystemExit(2)` with: `Godot not found: set GODOT to your Godot 4 editor executable (godot native is experimental)`.
- Each run is `subprocess.run([godot,"--headless","--path",build,"--script",PROBE_GD,"--fixed-fps","60","--quit-after",str(frames+120),"--","seed=N","bot=B","step=6","frames=F","hold=a,b"], capture_output=True, text=True, timeout=seconds*3+60)`.
- Parse the `PROBE {json}` lines into the same timeline. Godot runs have no screenshots, so the T0 frozen check is skipped. Use the same detectors and the same report.
- The Godot transport does not support overrides. If overrides are given, raise `SystemExit(2)` with "sweeps on Godot are not supported in v1".

**`scripts/probe.gd`** (Godot 4.3+, `extends SceneTree`):
1. In `_initialize()`:
   - Parse `OS.get_cmdline_user_args()` as `k=v`.
   - `var s = load(ProjectSettings.get_setting("application/run/main_scene")).instantiate(); root.add_child(s)`
   - Call `s.probe_seed(seed)` if it has that method.
   - Set `actions` from `s.probe_actions()`, or use `["ui_left","ui_right","ui_up","ui_down","ui_accept"]`.
2. In `_process(delta) -> bool`, count frames:
   - Frames 1-5 press `ui_accept`; this is the start sequence.
   - Every `step` frames, read `s.probe_state()` (or `{}`) and print `"PROBE " + JSON.stringify({"t": frame/60.0, "state": st})`.
   - Choose the keys: random uses a `RandomNumberGenerator` seeded with seed; policy uses `s.probe_bot(st)`; hold uses the `hold` list.
   - Apply each change as `var e = InputEventAction.new(); e.action = a; e.pressed = p; Input.parse_input_event(e)`.
   - When `st.get("over", false)` or `frame >= frames`, print `PROBE_END` and `return true`, which quits. Otherwise return false.
3. Add a comment `# ponytail: if actions don't register headless, switch to Input.action_press/action_release`.

**`skills/playtest/SKILL.md`** (name `playtest`; description: "Use after implementing any game feature, before ticking a gate, or when the user asks to playtest, smoke test, check for softlocks or crashes, or compare builds"). The body:
1. The dynamic-context line, which comes first.
2. Pick the mode:
   - **quick** after every feature: run it now, unprompted, after each feature you implement.
   - **milestone** when `REQUIRED` includes it and before ticking that stage's gates.
   - **final** on the packaged artifact, e.g. `build/itch.zip`.

   Use the sizes from `SIZES`.
3. Run `<RUN> "<PLUGIN>/scripts/playtest.py" run <BUILD> --mode <m> --seeds <n> --seconds <s> --out playtests`.
4. **Tier upgrade.** If the report is tier 0 or 1, explain what is missing.
   - At coding 1 or 2, offer to write the adapter: `window.__game = {state, actions, bot}`, or the Godot `probe_*` functions on the main scene. Keep it short, with no timers in state. Write the bot as a simple heuristic.
   - At coding 3, explain the contract and review the human's adapter.
   - Under `AI_POLICY=banned`, only T0 is allowed. Never write an adapter or bot.
5. **Triage.** For each FAIL, read the screenshot and the code path, and propose a fix. Consider whether a softlock is a menu that should set `paused`.
6. **Milestone extras.**
   - Read the FAIL shots (use a subagent if there are more than 5) and replace `(pending)` with "Claude's review of anomaly screenshots". Describe only what is visible; do not judge fun.
   - Point the human to the generated sheet. Tell them to play, fill it in, and save it as `playtests/<date>-human.md`.
7. Give the verdict line exactly as written, plus the `cannot_judge` line.
8. Never tick gates. Tell the human which box the result supports.
9. Notes:
   - Threaded web builds: use `--realtime`.
   - Godot 4 web exports should use no-threads.
   - Godot native is experimental.

**`skills/playtest/sheet-template.md`** is a one-page human observation sheet with these fields:
- tester (kleenex/repeat), build, date
- `{{GOALS}}`, each with `met / not met / waived` and evidence
- the moments they got stuck or confused (with timestamps)
- the moment they smiled or leaned in
- would they play again (1-5)
- one thing to cut
- a footer "Saved as playtests/<date>-human.md"

**`selftest` subcommand** (it uses `examples/dodge-web` if present, else prints `SKIP web: examples/dodge-web missing`; the copy goes in a temp dir; the whole thing should take under 4 minutes):

| Case | Expectation |
|---|---|
| (a) clean quick, 2 seeds × 25 s | verdict PASS or WARN without FAIL, tier 2, stats label policy, `runs` non-empty |
| (b) `?bug=softlock` | a softlock FAIL |
| (c) `?bug=crash` | a crash FAIL |
| (d) `?bug=deadinput` | a dead_input FAIL |
| (e) `?noprobe` | tier 0, `stats is None` |
| (f) `?nobot` | tier 1, label `random-input stats, not difficulty` |
| (g) a file override `data/enemies.csv:bat.speed=4` | `overrides` echoed, and the final states differ from a run without the override |
| (h) a zip of the build passed as `build` | boot mode PASS |
| (i) `out_dir` | the `.md` first line equals `summary`, and the JSON loads with all keys |
| (j) Godot | run dodge-godot clean and `bug=softlock` if Godot is found; else `SKIP godot: not installed (experimental)` |

How the URL switches reach the harness: let `run()` accept a build path with a query suffix, so that `examples/dodge-web?bug=crash` splits on `?` and the query is appended to the page URL. Keep this; ship and balance don't use it.

**Acceptance checks (run them and paste the output):**
1. `python scripts/playtest.py selftest` exits 0, with cases (a)-(i) ok and (j) SKIP or ok.
2. Time `python scripts/playtest.py run examples/dodge-web --mode quick --out <tmp>`: it takes under 90 s of wall time, and the first stdout line starts with PASS or WARN.
3. `py -3 scripts/playtest.py run examples/dodge-web` exits 2 with the install message, because py 3.13 lacks playwright.
4. `python -c "import sys;sys.path.insert(0,'scripts');import playtest;print(playtest.run.__doc__ is not None or True)"` imports without playwright being imported at module level. Check this with `'playwright' not in sys.modules` after the import.

#### P4: Balance sweep on the real build

**Repo:** `C:\Users\mihir\Desktop\Projects\Game Design Plugin` (Windows 11). Read the "Balance (v1: sweep)", "Probe contract", "`playtest.run()`" and "Report JSON" sections of `docs/superpowers/specs/2026-10-13-playbench-design.md`, and the "Shared conventions" section of `docs/superpowers/plans/2026-10-13-playbench-v1.md`.

**Style:** stdlib only, one file, under about 150 lines, with one `selftest`. Do NOT git commit.

**You own:** `scripts/balance.py` and `skills/balance/SKILL.md`. Nothing else.

`scripts/playtest.py` and `examples/dodge-web` are being built in parallel by other agents. Do not create them. Your selftest must pass without them, using an injected fake `run`, and must run the real integration case only when they exist and playwright imports.

**The `playtest.run` contract you call:**
```python
run(build, mode="sweep", bot="policy", seeds=None, seconds=None, overrides=[{"name":..,"file":..|None,"key":..,"value":..}], out_dir=None) -> dict
```
- The return value includes `tier` (0, 1 or 2) and `stats`: `{"label","runs","win_rate","tto_p10","tto_p50","tto_p90","deaths_per_min"}`, or None.
- A missing playwright or a bad build raises `SystemExit(2)`. Let it propagate.

**`scripts/balance.py`**
- **`parse_knobs(design_md_text) -> dict[name, {"file": str|None, "key", "min": float, "max": float}]`.** It finds the `## Knobs` heading and parses the markdown table that follows, whose header is `| name | file | key | min | max |`. It skips the separator row and any row whose first cell is empty or starts with `<!--`. A file of `-` becomes None.
- **`sweep(game_dir, knob, values=None, seeds=None, seconds=None, run=None) -> dict`:**
  1. Read `studio.json` for `build_dir` (default `.`), and read `design/design.md`.
  2. If the knob is unknown, raise `SystemExit(2)` and list the known knobs.
  3. If `values` is None, use 5 evenly spaced values from min to max, rounded to 3 decimal places.
  4. If `run` is None, import it lazily: `sys.path.insert(0, str(Path(__file__).parent)); from playtest import run`.
  5. For each value, call `run(os.path.join(game_dir, build_dir), mode="sweep", bot="policy", seeds=seeds, seconds=seconds, overrides=[{"name": knob, "file": k["file"], "key": k["key"], "value": v}])`.
  6. If any result has `tier < 2`, raise `SystemExit(2)` with: `sweep needs a policy bot (window.__game.bot or probe_bot); random-input sweeps are noise. Ask the playtest skill to add one.`
  7. Collect `{str(v): stats}`.
  8. Load `balance/last.json` (`{}` if it is missing). The previous entry is `last.get(knob)`. Write back `last[knob] = {"at": iso_now, "bot": "policy", "values": {...}}`, keeping the other knobs, with `indent=1`.
  9. Return `{"knob", "values", "prev"}`.
- **`table(result) -> str`** is a markdown table with the columns `value | win % | p50 s | p10 s | p90 s | deaths/min | Δ win % vs last`. The delta is blank when there is no previous entry for that value. The title line is: `Balance sweep: <knob> (relative difficulty under policy bot, not human difficulty)`.
- **CLI:**
  ```
  balance.py sweep <game_dir> --knob NAME [--values a,b,c] [--seeds N] [--seconds S]
  ```
  It prints the table and exits 0, or exits 2 on errors. `balance.py selftest` runs the selftest.
- Add a `# ponytail:` comment noting that costcurve and the Monte Carlo sim are v1.1.

**selftest:**
1. `parse_knobs` on an inline design.md string with two knobs, one CSV and one bundled `-`, plus a comment row. Check the parsed fields.
2. Sweep in a temp game dir (studio.json, design/design.md) with a **fake run**. Have it return `tier=2` and a win_rate that falls as the value rises. Check that:
   - the table has 5 rows when no values are given;
   - `balance/last.json` is written;
   - a second sweep shows a Δ column value;
   - a second knob merges into last.json without dropping the first.
3. A fake run returning `tier=1` raises SystemExit with code 2.
4. **Integration** (only if `scripts/playtest.py` and `examples/dodge-web` exist and `import playwright` works; else `SKIP integration`):
   - Copy `examples/dodge-web` to a temp dir.
   - Run `sweep(tmp, "bat_speed", values=[1.0, 4.0], seeds=3, seconds=25)`.
   - Assert that the win_rate at 1.0 is at least the win_rate at 4.0.

**`skills/balance/SKILL.md`** (name `balance`). Description: "Use when the user wants to tune game numbers, check difficulty, compare knob values, or asks whether something is too hard or too easy." Body:
1. The dynamic-context line, which comes first.
2. If `BALANCE=off` (jam), say that balance is off for jams and offer it only if the user insists.
3. Show the `## Knobs` table. If a tunable isn't in it, offer to move the number into a data file (CSV or JSON) the game fetches, and add a row. Bundled numbers use `window.__playbench.overrides.<name>` with a default.
   - At coding=1, Claude does this.
   - Under `AI_POLICY=banned`, the student writes the code. Claude only explains.
4. Run:
   ```
   <RUN> "<PLUGIN>/scripts/balance.py" sweep . --knob <name> [--values …] --seeds <n> --seconds <s>
   ```
5. Read the table back in plain words.
   - The numbers measure Claude's heuristic bot, not humans: use them for relative comparisons only.
   - Suggest a value, but the **human decides**, and a human playtest confirms it.
6. If it exits with the "needs a policy bot" error, route to the playtest skill to add `__game.bot`.
7. Mention v1 limits:
   - Sweeps are web-only. Godot data in the .pck can't be overridden in v1.
   - Spreadsheet economy sims and cost curves arrive in v1.1.

**Acceptance checks (run them and paste the output):**
1. `python scripts/balance.py selftest` exits 0. Integration may SKIP if the other packages aren't in yet. Say which.
2. `py -3 scripts/balance.py selftest` exits 0 too. The non-integration parts must need no playwright.
3. `python scripts/balance.py sweep <tmp-without-design> --knob x` exits 2 with a clear message.
4. If playtest.py and dodge-web exist, run `python scripts/balance.py sweep <copy of examples/dodge-web> --knob bat_speed --values 1,4 --seeds 3 --seconds 25` and paste the table.

#### P5: Ship (artgate, gate audit, itch, Steam, web)

**Repo:** `C:\Users\mihir\Desktop\Projects\Game Design Plugin` (Windows 11, Git Bash). Read these sections of `docs/superpowers/specs/2026-10-13-playbench-design.md`: "AI-art policy", "ship", "Gates", "State files", "Errors" and "Testing". Also read `docs/research/2026-10-13-playbench-research.md` for the verified store constants and sources, and the "Shared conventions" section of `docs/superpowers/plans/2026-10-13-playbench-v1.md`.

**Style:** stdlib only, one file, under about 350 lines, with one `selftest`. Never execute butler or steamcmd; only print the commands. Do NOT git commit, and do NOT download anything.

**You own:** `scripts/ship.py` and `skills/ship/SKILL.md`. Nothing else.

`scripts/playtest.py` and `examples/dodge-web` are being built in parallel. Do not create them. Import `playtest.run` lazily, and let the test inject a fake.

**The `playtest.run` contract:** `run(build, mode="boot") -> dict` with `verdict` (`PASS|WARN|FAIL`) and `summary`. It raises `SystemExit(2)` if playwright is missing. In that case, ship prints `boot check skipped: <msg>` as a WARN and continues, but the real upload command is then withheld.

**Config:** read `studio.json` from the game dir (arg, default cwd) for `build_dir`, `context`, `itch` (`user/game`) and `steam` (`{appid, depotid}`).

**Commands** (`ship.py <cmd> [game_dir] [flags]`; exit 0 = pass, 1 = blocked, 2 = usage/env error):

1. **`artgate [--dirs d1,d2]`.** The default dirs are `build_dir` and `store/` (if it exists). Walk the files and flag:
   - (a) A file whose basename equals the basename of any `path` in `art/PLACEHOLDERS.json` (`{"placeholders":[{"path","source","note"}]}`).
   - (b) A filename matching `re.compile(r"_(placeholder|ai|wip)(?=\.[^.]+$)", re.I)`.
   - (c) **PNG.** Iterate the chunks with struct: an 8-byte signature, then `>I4s` length/type, data, CRC. Flag `tEXt`, `iTXt` and `zTXt` chunks whose keyword (before `\0`) is in `{"parameters","prompt","workflow"}`, or whose text (decompress zTXt; for iTXt take the text after the language and translated-keyword fields) matches `GEN = re.compile(rb"midjourney|dall-?e|stable.?diffusion|novelai|firefly|comfyui", re.I)`. Also flag any `caBX` chunk (C2PA).
   - (d) **JPEG and WebP** (`.jpg`, `.jpeg`, `.webp`): flag when the first 65536 bytes contain `b"c2pa"` or match `GEN`.

   Each flag records `(relpath, reason)`. Pass if every flagged relpath matches, via `fnmatch` with forward slashes, at least one glob from the `disclosure.md` lines matching `^- (.+?):`. The output:
   - Print the flagged table, then `ARTGATE PASS` or `ARTGATE BLOCKED`.
   - On BLOCKED, print the exact lines to add to `disclosure.md`.
   - On PASS with flags, print the reminder: `Disclose on the store too: Steam Content Survey (AI-generated content), itch.io AI-generated tag.`
   - Always print: `Heuristic: stripped metadata is not detected. This is a safety net, not enforcement.`
   - Add a `# ponytail:` comment: store/ is scanned by policy; Steam's marketing-asset scope is unverified.

2. **`gate`.**
   - Read `gates.md` and find the **last** `## <stage>` section.
   - For each `- [x]` line (case-insensitive x), run `git blame --porcelain -L n,n -- gates.md` in the game dir and parse `author`, `author-time` and the sha.
     - A sha of all zeros means `WARN uncommitted tick (cannot attribute; commit gates.md)`.
     - If the file is untracked or the dir isn't a git repo (blame fails), print the WARN `gates.md is not tracked by git: ticks cannot be attributed`.
   - Print each ticked line with `author, date (YYYY-MM-DD), sha[:8]`.
   - List any `- [ ]` lines as `UNTICKED`.
   - Exit 0 only if there are no unticked boxes, no uncommitted ticks, and the file is tracked. Otherwise exit 1.
   - Never modify gates.md.

3. **`itch [--real]`**
   1. **Limits check** on `build_dir`. All of these are blocking:
      - `index.html` at the build root
      - at most 1000 files
      - at most 500 MB in total
      - at most 200 MB per file
      - every relative path at most 240 characters
      - no root-absolute URLs in `.html`, `.js` or `.css` files: the regex `(?:src|href)\s*=\s*["']/(?!/)|url\(\s*["']?/(?!/)|fetch\(\s*["']/(?!/)`
      - **case mismatch**: for every string literal in html/js/css that looks like a relative asset path (`["']([\w./-]+\.(?:png|jpe?g|webp|gif|svg|ogg|mp3|wav|json|csv|js|css|wasm|pck|html))["']`) and has no exact match on disk, report it as a case mismatch if a case-insensitive match exists.
   2. Put the limit constants in `STORE = {"itch": {...}, "steam": {...}, "AS_OF": "2026-10-13", "SOURCES": {"itch": "https://itch.io/docs/creators/html5", "butler": "https://itch.io/docs/butler/pushing.html", "steam_assets": "https://partner.steamgames.com/doc/store/assets/standard", "steampipe": "https://partner.steamgames.com/doc/sdk/uploading"}}`.
   3. Zip `build_dir` to `<game>/build/itch.zip` with `zipfile.ZIP_DEFLATED`. Use paths relative to `build_dir` with forward slashes, and exclude `build/`, `playtests/`, `.git/` and `steam/` when `build_dir` is `.`.
   4. **Boot check:** lazily `from playtest import run`, then `run(str(zip_path), mode="boot")`. Print its summary. A FAIL blocks.
   5. **Print:**
      - the butler dry-run: `butler push build/itch.zip <itch or user/game>:html5 --if-changed --dry-run`
      - if `shutil.which("butler")` is None: `install butler: https://itch.io/docs/butler/installing.html`
      - the manual steps: set Kind of project to HTML; tick "This file will be played in the browser"; set the viewport size; consider SharedArrayBuffer only for threaded builds; theme via Edit theme
      - a jam checklist when `context == "jam"`: submit to the jam page before the deadline, add a screenshot and cover, write controls in the description, and test the uploaded page in a private window
   6. **The real command.** Run `artgate` and `gate` internally. Only if both pass and the boot check passed, print `REAL UPLOAD (run it yourself): butler push build/itch.zip <user/game>:html5 --if-changed`. Otherwise print `Real upload command withheld: <reasons>`.

4. **`steam [--real]`**
   1. Exit 2 if `steam.appid` or `depotid` is missing, with a message saying which `studio.json` keys to add.
   2. Write `<game>/steam/app_build.vdf`:
      ```
      "AppBuild"
      {
       "AppID" "<appid>"
       "Desc" "playbench build"
       "Preview" "1"
       "ContentRoot" "<abs build_dir>"
       "BuildOutput" "<abs game>/steam/output/"
       "Depots"
       {
        "<depotid>"
        {
         "FileMapping" { "LocalPath" "*" "DepotPath" "." "recursive" "1" }
        }
       }
      }
      ```
   3. **IHDR checks.** Read the width and height with `struct.unpack(">II", data[16:24])` after verifying the signature. All checks are blocking:
      - `store/header_capsule.png` 920×430
      - `store/small_capsule.png` 462×174
      - `store/main_capsule.png` 1232×706
      - `store/vertical_capsule.png` 748×896
      - `store/screenshots/*.png`: at least 5 files, each at least 1920×1080, with an aspect ratio of 16:9 within 1%

      Report missing files as missing.
   4. Run artgate and gate. Only with `--real`, and only if everything passes:
      - rewrite the vdf with `Preview "0"`
      - print `REAL UPLOAD (run it yourself): steamcmd +login <your_steam_user> +run_app_build "<abs vdf>" +quit`

      Otherwise print the preview command (same form; Preview 1 uploads nothing) and the reasons the real one is withheld.

5. **`web`**
   - Check `index.html` and root-absolute URLs (shared helpers with itch).
   - Boot check on `build_dir`.
   - Print GitHub Pages steps (push the build dir to a `gh-pages` branch, or set Pages to `/docs`) and Netlify steps (`netlify deploy --dir <build> --prod`, printed, not executed).
   - Run artgate and print its result. A web deploy with undisclosed AI art is BLOCKED too.

**selftest** (temp dirs; inject a fake `run` that returns PASS, through a module-level `_run` override):
1. **artgate**
   - Build PNGs in code: a minimal valid 1×1 PNG writer (IHDR, IDAT via zlib, IEND, CRCs via `zlib.crc32`), plus optional extra chunks.
   - Assert that a PNG with `tEXt` `parameters` is flagged, that one with a `caBX` chunk is flagged, and that a clean one is not.
   - Assert that a `.jpg` file containing `c2pa` bytes is flagged, that a `_placeholder` filename is flagged, and that a PLACEHOLDERS.json basename match is flagged.
   - Assert BLOCKED (exit 1), then write `disclosure.md` covering them with globs and assert PASS (exit 0).
   - If `examples/dodge-web` exists, assert that artgate on a temp copy is BLOCKED because of `art/hero_placeholder.png`.
2. **itch limits.** Plant each violation separately and assert it is reported:
   - missing index.html
   - more than 1000 files (create 1001 tiny files)
   - a path over 240 characters (nested dirs; skip with SKIP if the OS rejects it)
   - an absolute `src="/x.js"`
   - a case mismatch: `Hero.png` on disk, `"hero.png"` referenced

   Check the 500 MB and 200 MB limits by monkeypatching `STORE` limits to small numbers. Do not write huge files.
3. **zip + boot.**
   - With the fake run, `itch` writes `build/itch.zip` containing `index.html` at the root, and prints a line containing `--dry-run`. With gates unticked, it prints `withheld` and no `REAL UPLOAD`.
   - If `examples/dodge-web`, `scripts/playtest.py` and playwright are all available, run the real boot check on a temp copy and assert PASS. Otherwise SKIP.
4. **steam.** The vdf contains `"Preview" "1"`. The IHDR reader returns the exact sizes for generated PNGs. Wrong sizes, and only 4 screenshots, are reported.
5. **gate.**
   - In a temp `git init` repo (`git -c user.name=t -c user.email=t@t commit`), write `gates.md` with a `## release` section containing 2 boxes. Commit it untouched.
   - Edit one box to `[x]` without committing: assert an uncommitted WARN and exit 1.
   - Commit, tick the other box and commit: assert exit 0 and that the author `t` is printed.
   - Assert that an untracked `gates.md` in a fresh non-repo dir gives the WARN and exit 1.
   - The real command appears only in the fully passing case, which combines a passing artgate and a passing gate in one temp game.

**`skills/ship/SKILL.md`** (name `ship`). Description: "Use when the user wants to release, upload, publish, or submit a game to itch.io, Steam or the web, check AI-art disclosure, prepare store assets, or audit release gates." Body:
1. The dynamic-context line, which comes first.
2. Order: `artgate`, then `gate`, then `itch`, `steam` or `web`, according to `PLATFORMS`. Steam is hidden for jam and learn unless the user asks.
3. Explain each block in plain words, at CODING-appropriate depth.
4. **Never tick a gate box.** If gates are unticked, list them and say who owns each (team), so the human ticks and commits.
5. **Never run butler or steamcmd.** Show the printed command, and tell the user to run it themselves.
6. AI art:
   - placeholders must be replaced, or disclosed in `disclosure.md` and on the store (Steam Content Survey; itch AI tag)
   - detection is heuristic
   - store assets are scanned by policy
7. **itch page theme (prose only).** On the itch page: Edit theme → background/text/link colors, banner image, and fonts; custom CSS works only if itch has enabled it for the account. Embed: set the viewport to the game canvas size, enable the fullscreen button, and disable scrollbars. Add 3-5 screenshots and a GIF, and put the controls in the first lines.
8. **Steam (team).**
   - Store asset sizes per the STORE dict.
   - The SteamPipe flow is preview first, then `--real`.
   - Library assets and Steam Playtest arrive in v1.1.
9. **Web.** GitHub Pages and Netlify steps.
10. Under `AI_POLICY=banned`, artgate is allowed. For everything else, explain and let the student run the commands.

**Acceptance checks (run them and paste the output):**
1. `python scripts/ship.py selftest` exits 0. Note which cases SKIPped.
2. `py -3 scripts/ship.py selftest` exits 0, with real-boot cases allowed to SKIP.
3. On a temp copy of `examples/dodge-web` (if present): `python scripts/ship.py artgate <copy>` exits 1, naming `art/hero_placeholder.png`. After adding `disclosure.md` with `- art/*_placeholder.png: AI placeholder hero sprite`, it exits 0.
4. `python scripts/ship.py itch <copy>` prints a `--dry-run` butler line and `withheld`, because there is no gates.md.
5. `grep -n "subprocess" scripts/ship.py` shows only git calls. No butler or steamcmd execution.

## Definition of done (integration)
- `python scripts/selftest.py` exits 0. Godot cases SKIP.
- `claude plugin validate . --strict` passes.
- A quick playtest on dodge-web takes under 90 s and detects the softlock, crash and dead-input bugs, with no FAIL on the clean build.
- `grep -rn "\[x\]" skills scripts` only matches parsing code, tests and docs. No code path writes a ticked box into a real `gates.md`.
- `ship itch` on dodge-web stops at artgate until `disclosure.md` exists, then prints the butler `--dry-run` command. It does not print the real command until the release gates are ticked and committed.
