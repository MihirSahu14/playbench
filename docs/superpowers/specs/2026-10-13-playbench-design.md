# playbench: Design Spec

**Date:** 2026-10-13. This spec replaces `2026-10-13-game-studio-v1-design.md`, which has been deleted.
**Research:** [playbench research](../../research/2026-10-13-playbench-research.md), [pipeline](../../research/2026-10-13-studio-pipeline.md), [cadence](../../research/2026-10-13-playtesting-cadence.md), [market](../../research/2026-10-13-market-fit.md)

## Goal
playbench is a Claude Code plugin that plays your real game build with bots. It works on any HTML5 export, and on native headless Godot in experimental form, through one engine-neutral probe contract. It sweeps balance knobs on that same build. It blocks itch and Steam releases until placeholder or AI art is disclosed and a human has ticked the release gate. Design stays at one discussion and one page. The flow adapts to jam, hobby, team or classroom use, and to how much the user codes.

v1 is **web-first, Godot-second**. The SKILL asks for a quick playtest after every feature, and `status` shows any gap. No hook runs it automatically in v1.

## Ownership
| Humans own | Claude and the scripts own |
|---|---|
| Judging fun, final art, the GO/KILL decision, **ticking every gate box** | Writing code, probe adapters and bots; running playtests and sweeps; checks; the printed upload commands |

Three invariants hold in every profile:
1. Claude never ticks a gate box, and `ship gate` shows who did.
2. `ship` blocks undisclosed placeholder or AI art, including store assets.
3. Outcome stats (win rate, time to game over) are reported as difficulty only when a goal-directed bot (T2) plays.

## User segments and how the plugin adapts
Four inputs drive adaptation:
- **context:** jam, hobby, team or learn.
- **coding:** 1 to 3.
- **engine/tier:** auto-detected.
- **stage:** derived from `gates.md`.

`studio.py` holds a single `PROFILE` dict keyed by context. Coding only changes who writes the adapter and bot and how verdicts are worded, so it lives in SKILL prose and never multiplies the profiles.

| Segment | context | What changes |
|---|---|---|
| Game-jammer: deadline, browser build, itch | `jam` | `status` shows a countdown to `deadline_at`. The design page covers the hook, core loop and must/cut list, with no pillars or GO line. Gates are `playable` and `submitted`. Quick playtest is 3 seeds × 30s. Balance is off unless asked. Human-playtest debt is shown but never warned about. `ship itch` runs the limits check, builds the zip, boot-checks the extracted zip, and prints the butler dry-run plus a jam checklist. Steam is hidden. |
| Solo hobbyist: little time, needs to finish | `hobby` | The must list is capped at `hours_per_week × weeks`. Gates are `prototype`, `slice` and `release`. `status` warns at 5 commits without a quick playtest and 20 without a human one. Art is placeholder-only and tracked in `art/PLACEHOLDERS.json`. itch is the default target and Steam is opt-in. |
| Small indie team, 2-5 people on Steam | `team` | `studio.json` is static config: members, what each owns, which gates each owns. Stage, debt and history are derived, so there are no merge conflicts. Gates are `prototype`, `slice`, `alpha`, `beta` and `release`, and each box names its owner. Every playtest diffs against the previous run of the same mode. `ship steam` writes the Preview vdf and checks store PNG sizes. `ship gate` shows git blame for every release tick. **Honest limit:** native Unity or Unreal builds get bot playtests only through a WebGL export. |
| Low-code designer ("vibe coder") | coding=1, any context | Claude writes the probe adapter and the T2 bot, and moves tunables into `data/*.csv` or `*.json` files listed in the knob table. Every verdict is one plain-English line, for example `PASS: boots, input works, no freezes in 6 runs`. At coding=2 Claude writes the adapter and the human reviews it. At coding=3 Claude explains the contract and reviews the human's adapter. |
| Student or educator | `learn` | `ai_policy` is `open`, `disclose` or `banned`. **banned** means the only allowed actions are explain, review, status, T0 playtest and artgate; Claude refuses to write game code, adapters, bots or models. **disclose** means Claude's commits keep the `Co-Authored-By` trailer. Gates are `prototype` and `submitted`, and playtest reports add a rubric block. Steam is hidden. |

## v1 scope
| Component | Runs something? |
|---|---|
| `studio` skill + `scripts/studio.py`: detect, init, status, selftest | yes |
| `design` skill + `design-template.md`: one discussion, one page | no (prompt-only, deliberately the smallest) |
| `playtest` skill + `scripts/playtest.py` + `scripts/probe.gd` + `sheet-template.md`: web T0/T1/T2, Godot native (experimental) | yes |
| `balance` skill + `scripts/balance.py`: `sweep` on the real web build | yes |
| `ship` skill + `scripts/ship.py`: `artgate`, `gate`, `itch`, `steam`, `web` | yes |
| `examples/dodge-web` (verified fixture), `examples/dodge-godot` (experimental fixture), `scripts/selftest.py`, plugin and marketplace manifests | yes |

## Roadmap
| Version | Adds |
|---|---|
| **v1** | Everything listed above |
| v1.1 | Godot native marked **verified**, once the user approves downloading the portable Godot 4.x editor (82 MB) and the spike passes. Also: `balance costcurve` (least squares and 2σ outliers), `balance sim` (seeded Monte Carlo from `model-template.py`), Steam library assets, a `studio aiuse` git-derived AI-use summary, `mash` and scripted-input bots, and a PreToolUse guard that blocks Claude's Edit/Write from ticking `gates.md`. Also an auto quick-playtest Stop hook, which waits until interpreter discovery is proven. |
| v1.2 | Godot balance sweeps through user args, screenshots from windowed Godot runs, tested Construct and GDevelop adapters, and Godot web export in the selftest when templates are cached |
| v2 | Art pipeline (Aseprite CLI atlas export, placeholder sprite generation), itch theme CSS generator, survey generator, GitHub Pages and Netlify automation |
| v3 | LLM agent that plays at decision points, persona commentary, payoff-matrix balance, telemetry ingestion, human feedback intake, postmortem, Steam Playtest app and Next Fest flow, running uploads, hosted runner |

Not planned: mobile-native, Roblox/UEFN and consoles. They have closed runtimes and no headless path.

## Architecture
```
.claude-plugin/plugin.json, marketplace.json
skills/studio/SKILL.md
skills/design/SKILL.md, design-template.md
skills/playtest/SKILL.md, sheet-template.md
skills/balance/SKILL.md
skills/ship/SKILL.md
scripts/studio.py playtest.py probe.gd balance.py ship.py selftest.py
examples/dodge-web/  examples/dodge-godot/
README.md
```
- There is no `agents/`, `hooks/` or `bin/` directory.
- The scripts use the stdlib only, except that `playtest.py` imports `playwright` lazily inside the web transport.
- `balance.py` and `ship.py` call `playtest.run()` directly; there is no subprocess layer.
- The in-page probe JavaScript is a string constant inside `playtest.py`, not a separate file.

### Script invocation and Python discovery
- Every SKILL starts with a dynamic-context line:
  `` !`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playbench: no working Python 3 found"` ``
  The paths are quoted because install paths contain spaces. Task 1 of the plan is a spike that confirms the substitution and the shell. If `${CLAUDE_PLUGIN_ROOT}` is not substituted, the line uses `${CLAUDE_SKILL_DIR}/../../scripts/`.
- `status` probes `python`, then `py -3`, then `python3`. It prints `RUN=<launcher>`, choosing the first launcher that can import playwright, or else the first one that works. Every later Bash command in a SKILL uses `<RUN> "<plugin>/scripts/x.py" …`.
- Each SKILL's `allowed-tools` lists `Bash(python:*)` and `Bash(py:*)`. These are static patterns that match both launchers, so playtests run without permission prompts. Absolute interpreter paths are never used.
- If playwright is missing, status prints the exact install line: `<RUN> -m pip install playwright && <RUN> -m playwright install chromium`.

### Probe contract (shared by all packages)
**State shape**, returned by the game:

`{over: bool, won?: bool, score?: number, paused?: bool, ...gameplay fields}`

- `paused` covers menus, title screens and cutscenes.
- For hashing, the harness ignores keys that start with `_` and the keys `t`, `time`, `frame`, `tick` and `elapsed`.

**Web.** The game may define `window.__game`:
- `state`: a function returning the state, or a plain object the game keeps updated. Godot-web pushes the object, because JavaScriptBridge returns null.
- `bot(state) -> string[]`: optional. Returns the `KeyboardEvent.key` values to hold this step.
- `actions: string[]`: optional. Defaults to `["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"," ","Enter"]`.

Hooks accepted as T1 fallbacks:
- `window.render_game_to_text()`, whose JSON string the harness parses (from develop-web-game).
- `window.__GAME_STATE__` (from game-creator).

Before any game script runs, the harness injects `window.__playbench = {seed, overrides: {<name>: value}}` and replaces `Math.random` with a mulberry32 PRNG seeded from `seed`. A game with bundled tunables reads them like this:

`(window.__playbench?.overrides ?? {}).<name> ?? <default>`

**Godot native.** The main scene's root node may define:
- `probe_state() -> Dictionary`
- `probe_seed(seed: int)`
- `probe_actions() -> Array[String]` (InputMap action names)
- `probe_bot(state) -> Array[String]`

`probe.gd` extends SceneTree and is launched as:

`godot --headless --path <proj> --script <plugin>/scripts/probe.gd --fixed-fps 60 --quit-after <frames> -- seed=<n> bot=<idle|random|policy> step=<frames> hold=<csv actions>`

- It loads `application/run/main_scene` and calls `probe_seed`.
- Every `step` frames it prints `PROBE {"t":<s>,"state":{...}}`.
- It applies keys with `Input.parse_input_event(InputEventAction)`. If the spike shows actions don't register headless, it falls back to `Input.action_press`/`action_release`.
- At exit it prints `PROBE_END`.
- `SCRIPT ERROR` or `ERROR:` on stderr, or an exit before `PROBE_END`, counts as a crash.

**Tiers** are detected automatically:
| Tier | Needs | Detects |
|---|---|---|
| T0 | nothing (works on any HTML5 export: Unity WebGL, GameMaker, Construct, GDevelop, Phaser, plain JS) | boot failure (FAIL), uncaught page errors (FAIL), console errors (WARN), frozen canvas (WARN), dead input by screenshot replay (WARN) |
| T1 | a readable state | the T0 checks, plus softlock (FAIL), dead input by state replay (FAIL), and per-action dead input in milestone and final (WARN). Stats are labelled `random-input stats, not difficulty` |
| T2 | `bot` / `probe_bot` | the T1 checks plus outcome stats: win rate, time-to-over p10/p50/p90, deaths per minute. They are labelled `relative difficulty under policy bot` |

**Web run mechanics**
1. Serve the build directory with stdlib `http.server`, on a thread and a free port. A `.zip` build is first extracted to a temporary dir. With `--coop`, add the COOP and COEP headers.
2. Launch Chromium headless with `--use-angle=swiftshader`, so WebGL is available without a GPU.
3. Call `page.clock.install()` before `goto`. `--realtime` skips this for threaded wasm builds, which page.clock can't drive.
4. Inject the probe with `add_init_script`.
5. **Start sequence**, identical in every run including idle: click the canvas centre, then press Enter and Space, then `run_for(1000)`.
6. **Step loop:** call `run_for(step_ms=100)`. Read the state. Ask the bot for keys and apply the diff with trusted `page.keyboard.down`/`up`. Every 1 sim-second, hash a canvas screenshot.
7. A run ends when the state reports `over`, or when the configured seconds have elapsed.

**Detectors**
- **Boot:** fails if there is no `<canvas>` within 10 sim-seconds, or if `goto` fails.
- **Softlock (T1):** fires when the state hash is unchanged for 5 or more sim-seconds while input is being sent and the game is neither `over` nor `paused`.
- **Frozen (T0):** fires when the screenshot hash is unchanged for 5 or more sim-seconds while input is being sent.
- **Dead input:** uses deterministic replay. Run the same seed twice, once with the idle bot and once with the random bot, for 3 sim-seconds after the start sequence. If both runs end in the same state hash (T1), or the same screenshot hash (T0), the input had no effect. In milestone and final, each action is replayed separately and compared with idle.
- **Determinism check:** the idle replay runs twice. If the two runs differ, the dead-input check is reported as skipped (`nondeterministic`, WARN).
- Every FAIL finding saves a screenshot to `shots/`.

**Bots:** `idle`, `random` (changes keys every 300 ms), and `policy` (`__game.bot`). The mash and scripted-input bots are deferred.

### `playtest.run()` (the API balance and ship call)
```python
run(build, mode="quick", bot=None, seeds=None, seconds=None, overrides=None,
    realtime=False, coop=False, out_dir=None) -> dict
```
- **`mode`** is one of `quick`, `milestone`, `final`, `boot` or `sweep`.
- **Defaults** for (seeds, seconds) by mode:

  | Mode | Seeds | Seconds |
  |---|---|---|
  | quick | 3 | 30 |
  | milestone | 8 | 60 |
  | final | 8 | 60 |
  | boot | 1 | 10 |
  | sweep | 5 | 60 |

  The SKILL passes the profile's values as `--seeds` and `--seconds`.
- **`bot`:** if it is `None`, quick, milestone and final run `random`, plus `policy` when T2 is available. boot runs `idle`, and sweep runs `policy`.
- **`overrides`** is a list of `{"name", "file"|None, "key", "value"}`. When `file` is set, `page.route` serves a modified copy of that file:
  - CSV files are read as `utf-8-sig`, with the delimiter found by `csv.Sniffer`. The key is either `<first-column value>.<column>` or `*.<column>`.
  - JSON files take a dotted path as the key.
  - Every override, with or without a file, is also exposed in `__playbench.overrides[name]`.
- **`out_dir`:** when it is set, the run writes `<out_dir>/<YYYY-MM-DD-HHMM>-<mode>.json` and `.md`, plus a `shots/` folder. When it is `None`, the run only returns the dict.
- **Engine:** if `project.godot` is in `build`, the run uses the Godot transport. The Godot binary comes from `$GODOT`, then from `godot` on PATH. If neither is found, the run raises `SystemExit(2)` with a hint.

CLI:

`playtest.py run <build> [--mode] [--bot] [--seeds] [--seconds] [--override F:K=V | NAME=V]... [--realtime] [--coop] [--out playtests]`

The command exits 0 on PASS or WARN and 1 on FAIL. `playtest.py selftest` runs the selftest.

**Report JSON**, which other packages and `status` depend on:
```json
{"version":1,"at":"2026-10-13T14:05:00","mode":"quick","engine":"web","build":"examples/dodge-web","tier":2,
 "verdict":"PASS","summary":"PASS: boots, input works, no freezes or softlocks in 6 runs",
 "runs":[{"seed":1,"bot":"policy","seconds":30.0,"over":true,"won":false,"time_to_over":21.3}],
 "findings":[{"kind":"softlock","severity":"FAIL","seed":2,"bot":"random","t":12.0,"detail":"state unchanged 5s","shot":"shots/…png"}],
 "stats":{"label":"relative difficulty under policy bot","runs":3,"win_rate":0.33,"tto_p10":9.1,"tto_p50":21.3,"tto_p90":30.0,"deaths_per_min":1.4},
 "overrides":[], "regression":{"prev":"2026-10-12-1010-quick.json","new_kinds":[],"stat_shifts":{}},
 "cannot_judge":"Bots cannot judge fun, clarity or feel. A human playtest is still required before any gate."}
```
- **`kind`** is one of `boot`, `crash`, `console_error`, `softlock`, `frozen`, `dead_input` or `nondeterministic`.
- **`stats`** is `null` at T0.
- **`verdict`:** FAIL if any finding is FAIL, else WARN if any finding is WARN, else PASS.
- **`regression`** compares against the newest earlier report of the same mode in `out_dir`. It records new finding kinds, win-rate shifts over 10 points, and p50 shifts over 20%.
- **The `.md` report:**
  - Its first line is `summary`.
  - It then has a findings table, the stats with their label, the `cannot_judge` line, and the regression.
  - A milestone report also has an empty `## Claude's review of anomaly screenshots` section.
  - When `studio.json` has `context=learn`, the report gets a rubric block (goal, evidence, met or not, reflection prompt).

## State files (in the game's repo, never in the plugin)
| File | Owner | Content |
|---|---|---|
| `studio.json` | human (written by init) | `{context, coding, engine, build_dir, platforms:[itch\|steam\|web], deadline_at?, hours_per_week?, weeks?, team?:[{name, owns, gates:[stage]}], ai_policy?, itch?:"user/game", steam?:{appid, depotid}}` |
| `gates.md` | humans tick; scripts only parse | per-stage `## <stage>` checklists |
| `design/design.md` | human, drafted by Claude | the one page, including `## Experience goals` and `## Knobs` |
| `art/PLACEHOLDERS.json` | Claude appends, human removes | `{"placeholders":[{"path":"art/hero_placeholder.png","source":"ai\|wip\|stock","note":"…"}]}` |
| `disclosure.md` | human | lines of the form `- <path or glob>: <what AI or placeholder content it is>` |
| `playtests/*.json`, `*.md` | scripts (**commit them**; `shots/` is gitignored by init) | reports; `*-human.md` holds human sessions |
| `balance/last.json` | script | the last sweep results per knob |
| `steam/app_build.vdf`, `build/itch.zip` | script | ship outputs |

Some state is **derived**, so no counters are stored:
- **Stage:** the first `## stage` in `gates.md` that has an unticked box. If every box is ticked, the stage is `shipped`.
- **Quick debt:** `git rev-list --count --since=<at of newest playtests/*-quick.json> HEAD`.
- **Human debt:** the same count, since the date prefix of the newest `playtests/*-human.md`.
- **Regression:** a diff against the previous report of the same mode.
- **Balance drift:** a diff against `balance/last.json`.

Routine runs never rewrite a shared file, so there are no team merge conflicts.

## Gates
`studio.py init` writes `gates.md` with **every box unticked** and this header:

`Only humans tick these boxes. Claude never ticks them; ship gate shows who did.`

In `team` context each box ends with `(owner: <name>)`.

| context | stages |
|---|---|
| jam | playable, submitted |
| hobby | prototype, slice, release |
| team | prototype, slice, alpha, beta, release |
| learn | prototype, submitted |

| Stage | Boxes |
|---|---|
| prototype / playable | latest quick playtest PASS; a human played it and wrote `playtests/*-human.md`; `Decision: GO` in design.md (not in jam) |
| slice | milestone playtest PASS or WARN, with each WARN triaged; every experience goal marked met or waived on a human sheet |
| alpha | must list complete; milestone playtest with no new FAIL kinds |
| beta | no entries left in PLACEHOLDERS.json, or every remaining one disclosed; final playtest on the packaged build |
| release / submitted | final playtest PASS; `ship artgate` passes; store or itch page reviewed by a human; "I approve this release" |

Required playtest modes by stage:
- prototype and playable need quick.
- slice and alpha also need milestone.
- beta, release and submitted also need final.

## Playtest cadence
1. **Per feature (micro):** a quick playtest, about 60s of wall time, which the SKILL asks for after each feature. `status` shows the commits since the last one and warns past the profile limit.
2. **Milestone:** when a stage requires it, and before any of that stage's boxes are ticked.
   - The run uses more seeds and per-action dead-input checks, and diffs against the previous milestone report.
   - Claude reads the FAIL screenshots, using a subagent if there are more than 5, and fills in "Claude's review of anomaly screenshots".
   - A human sheet is written to `playtests/<stamp>-sheet.md` from `sheet-template.md`, filled with the experience goals from design.md. The human saves the completed sheet as `<date>-human.md`.
3. **Final:** a milestone-sized run against the packaged artifact (`run build/itch.zip --mode final`).

Every report states what bots cannot judge.

## AI-art policy
- AI art is used only as clearly marked placeholders. Each one gets a `_placeholder` filename tag and an entry in `art/PLACEHOLDERS.json`.
- `ship artgate [--dirs …]` scans `build_dir` and `store/`, which it treats as policy because Steam's marketing scope is unverified. It flags:
  - (a) files whose basename matches a PLACEHOLDERS entry;
  - (b) filenames matching `_(placeholder|ai|wip)` before the extension;
  - (c) PNG `tEXt`, `iTXt` or `zTXt` chunks whose key is `parameters`, `prompt` or `workflow`, or whose value mentions Midjourney, DALL-E, Stable Diffusion, NovelAI, Firefly or ComfyUI;
  - (d) the PNG `caBX` chunk, which holds C2PA data;
  - (e) the bytes `c2pa` or those generator names in the first 64 KB of JPEG and WebP files.
- artgate exits 1 unless every flagged path matches a glob in `disclosure.md`. On a pass it reminds the user to fill in Steam's AI content survey and the itch AI tag.
- The SKILL says plainly that detection is heuristic, so stripped metadata gets through. It is a safety net for honest users, not enforcement.

## ship
| Command | Does |
|---|---|
| `gate` | Parses the last stage in `gates.md` and runs `git blame --porcelain -L n,n` on each `- [x]` line. It prints the author, commit and date. It warns when a tick is not committed yet (zero sha) or the file is untracked. It exits 1 if any box is unticked or any tick is uncommitted. |
| `itch` | Runs the limits check on `build_dir`, all blocking: `index.html` at the root, at most 1000 files, at most 500 MB in total, at most 200 MB per file, paths of at most 240 characters, no root-absolute URLs (`src="/…"`, `href="/…"`, `url(/…)`, `fetch("/…")`) in html, js or css, and no referenced relative path that matches an existing file only case-insensitively. It then zips the build to `build/itch.zip` and calls `playtest.run(zip, mode="boot")`, then prints `butler push build/itch.zip <itch>:html5 --if-changed --dry-run` along with the manual steps: set the kind to HTML, tick "played in the browser", and set the viewport. It ends with a jam checklist when context=jam. |
| `steam` | Writes `steam/app_build.vdf` with `Preview "1"`, taking the appid and depotid from studio.json and exiting 2 if they are missing. It checks the `store/` PNG sizes from IHDR: `header_capsule.png` 920×430, `small_capsule.png` 462×174, `main_capsule.png` 1232×706, `vertical_capsule.png` 748×896, and `store/screenshots/*.png` (at least 5, each at least 1920×1080 and 16:9). All constants live in one `STORE` dict with source URLs and `AS_OF="2026-10-13"`. |
| `web` | Checks for `index.html` and root-absolute URLs, runs a boot check, and prints hosting steps (GitHub Pages, Netlify). |

`ship itch`, `ship steam` and `ship web` print a **real** upload command only when `artgate` passes and `gate` passes. The itch command is butler without `--dry-run`. The Steam command is `steamcmd +login <user> +run_app_build "<abs>/steam/app_build.vdf" +quit`, printed after rewriting the vdf with `Preview "0"` when `--real` is given. A command is never executed; the user runs it.

## Balance (v1: sweep)
`balance.py sweep <game_dir> --knob <name> [--values a,b,c] [--seeds] [--seconds]`
1. Reads the `## Knobs` table in `design/design.md`, which has the columns `name | file | key | min | max`. A `file` of `-` means the value is bundled and reached only through `__playbench.overrides`.
2. If no values are given, it uses 5 evenly spaced values from min to max.
3. For each value it calls `playtest.run(build, mode="sweep", bot="policy", overrides=[…])`.
4. It refuses to run, with exit 2, unless the result is tier 2, because random-input sweeps are noise.
5. It prints a markdown table (value | win% | p50 | p10 | p90 | deaths/min), labelled `relative difficulty under policy bot`.
6. It writes `balance/last.json` as `{knob: {at, values: {v: stats}}}`, merging with other knobs, and prints the deltas against the previous entry for that knob.

Balance is off for jam unless the user asks for it. Under learn+banned, the bot must be written by the student.

## Errors
| Situation | Behavior |
|---|---|
| No Python 3 found | The `!` line falls through to `echo`. The SKILL tells the user to install Python 3.11+ |
| playwright missing | Web commands exit 2 and print `<RUN> -m pip install playwright && <RUN> -m playwright install chromium`. studio, ship artgate/gate and the Godot transport still work |
| Godot not found | Exit 2 with "set GODOT=<path to Godot 4 editor>". Godot stays labelled experimental |
| No `studio.json` | `status` prints the detected engine and "run init". Other commands use defaults |
| Build has no `index.html` or `project.godot` | Exit 2 with what was looked for |
| T2 needed (sweep) but no bot | Exit 2: "sweep needs a policy bot (`__game.bot`); random sweeps are noise" |
| Nondeterministic game | Dead-input check skipped with a WARN. Suggest `--realtime` and no-threads exports |
| `ai_policy=banned` and the request is outside the allow-list | The SKILL refuses and names the allowed actions |
| Unticked gate or uncommitted tick at ship | Exit 1, listing the boxes. The real command is not printed |

## Testing
- Each script has a `selftest` subcommand built from asserts. It needs no framework and prints `ok <name>` or `SKIP <name>: <why>`.
- `scripts/selftest.py` runs all of them, then runs `claude plugin validate . --strict` (SKIP if `claude` is not on PATH). It exits non-zero on any failure.

| Script | Selftest cases |
|---|---|
| studio | detect on both fixtures; init for every context × coding combination produces valid JSON and a gates.md with zero `[x]`; stage derivation; debt in a temporary git repo |
| playtest web | dodge-web clean, giving PASS, T2 and stats; `?bug=softlock`, giving FAIL softlock; `?bug=crash`, giving FAIL crash; `?bug=deadinput`, giving FAIL dead_input; `?noprobe`, giving T0 with stats null; `?nobot`, giving T1 with the random-input label; an override that changes CSV enemy speed so the state differs |
| playtest godot | dodge-godot clean and `bug=softlock`. These run only when Godot is found, and otherwise SKIP |
| balance | the knob-table parser; a sweep with an injected fake `run` that checks the table, the last.json merge and the diff; a real two-value sweep on dodge-web when playwright is present |
| ship | artgate blocks the fixture and passes once disclosure.md exists; PNG tEXt and caBX detection on generated PNGs; each itch limit violation planted in a temp dir; zip plus boot check; the vdf contains `Preview "1"`; IHDR sizes; gate blame warns on an uncommitted tick in a temp git repo |

## Success criteria
1. `python scripts/selftest.py` passes on this Windows machine (Godot cases SKIP), and `claude plugin validate . --strict` passes.
2. On dodge-web, `playtest run --mode quick` finishes in under 90 s of wall time and detects all three planted bugs, with no false FAIL on the clean build.
3. A user can go from an empty folder to `studio init`, then `design/design.md`, then a quick playtest, then `ship itch` printing a dry-run command, all without leaving Claude Code. No script or SKILL ever writes `[x]` into `gates.md`.
4. `ship` refuses to print a real upload command while artgate or gate fails.
5. Each of the 4 contexts produces a different gates.md and different status advice, with no code branch per coding level.
