---
name: playtest
description: Use after implementing any game feature, before ticking a gate, or when the user asks to playtest, smoke test, check for softlocks or crashes, or compare builds
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Read, Write, Edit, Glob, Grep
---
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playbench: no working Python 3 found"`

# Playtest: bots play the real build

The status block above gives `RUN`, `PLUGIN`, `BUILD`, `ENGINE`, `CODING`, `AI_POLICY`, `STAGE`, `REQUIRED` and `SIZES`.
- If it says no working Python, ask the user to install Python 3.11+ and stop.
- If `PLAYWRIGHT=no` and the engine is web, show the `INSTALL` line and ask before running it.
- If `INIT=no`, use `BUILD` from detect (or `.`) and the default sizes. Suggest `/playbench:studio` once, after the run.

## 1. Pick the mode
| Mode | When | Size |
|---|---|---|
| **quick** | After **every** feature you implement. Run it now, unprompted; don't ask. | `SIZES` quick (e.g. 3x30 = 3 seeds x 30 s) |
| **milestone** | When `REQUIRED` lists it for the current `STAGE`, and before any box of that stage is ticked | `SIZES` milestone |
| **final** | On the packaged artifact, e.g. `build/itch.zip` after `ship itch` | `SIZES` final |

## 2. Run it
```
<RUN> "<PLUGIN>/scripts/playtest.py" run <BUILD> --mode <m> --seeds <n> --seconds <s> --out playtests
```
- Run it from the game folder, so reports land in `playtests/` and get committed with the game.
- Exit 0 means PASS or WARN, 1 means FAIL, and 2 means a setup problem (the message says what to fix).
- Extra flags: `--override data/x.csv:id.col=V` or `--override name=V` (bundled knob), `--realtime`, `--coop`.
- Bots (`--bot`): `idle`, `random`, `policy` (the game's own `bot`), plus:
  - `mash`: holds a fresh random set of every action (start keys too) each 100 ms. Input-spam robustness; run it before a milestone.
  - `script:<path.json>`: a reproducible path such as "walk to the boss door", e.g. `[{"t": 0, "keys": ["ArrowRight"]}, {"t": 2.5, "keys": ["ArrowUp"]}]`. At each step it holds the keys of the last entry with `t <= now`; the last entry's keys stay held. Keep these files in `playtests/scripts/`: later loops replay them.

## 3. Report back
- Quote the verdict line (the first line of the report) exactly as printed.
- Quote the `cannot_judge` line.
- Word it by `CODING`:
  - 1: the verdict line plus one plain sentence on what to do next. No jargon.
  - 2: add the findings table and your proposed fix.
  - 3: add the tier, the stats label, and which detector fired.
- If `## Regression` lists new finding kinds or stat shifts against the previous run of the same mode, say so in one line (in `team` context, name who owns the area).
- Stats are difficulty only when the label says `relative difficulty under policy bot`. Never call `random-input stats` difficulty.

## 4. Triage findings
For each FAIL, read the screenshot in `playtests/shots/` and the code path behind it, then propose a fix.
- **crash:** find the throw in the detail line and fix it.
- **softlock:** the state stopped changing while keys were sent. If it is a menu, pause screen or cutscene, the real fix may be to set `paused: true` in the state while it shows.
- **dead_input:** check the key listeners (on `window`, keydown/keyup) and that `actions` lists keys the game reads.
- **frozen** (tier 0): the canvas stopped changing. Upgrade the tier to tell a softlock from a still screen.
- **nondeterministic:** the game reads real time (`Date.now`, unseeded RNG, threads). Use `Math.random` (the harness seeds it), or `--realtime` for threaded builds.
- **boot:** no `<canvas>` appeared, or the page failed to load. Check `index.html` and relative paths.
- **console_error:** a WARN. Triage it, but don't block on it.

## 5. Tier upgrade (when the report says tier 0 or 1)
Tier 0 sees only the screen. **Construct 3 / GDevelop / Unity WebGL / GameMaker:** paste the matching snippet from `${CLAUDE_SKILL_DIR}/adapters.md`. Tier 1 reads state (softlock, real dead-input checks). Tier 2 adds a goal-directed bot (difficulty stats, balance sweeps). Explain what is missing in one line, then:
- **`AI_POLICY=banned`:** T0 only. Never write an adapter or a bot. Explain the contract if asked.
- **coding 1-2:** offer to write the adapter yourself. At coding 2 the human reviews it.
  - Web: `window.__game = { state: () => ({over, won, paused, score, ...gameplay fields}), actions: [...KeyboardEvent.key values], bot: s => [...keys to hold] }`
  - Godot: `probe_state()`, `probe_seed(seed)`, `probe_actions()` and `probe_bot(state)` on the main scene's root.
  - Keep the state small. **No timers or clocks in state**, so it can freeze when the game does. `paused` must be true on title screens, menus and cutscenes.
  - The bot is a simple heuristic (move away from the nearest threat, toward the goal). It does not need to be good, just goal-directed.
  - Move tunable numbers into `data/*.csv` or `*.json` and list them in `design/design.md` under `## Knobs`, so balance sweeps can reach them. Bundled ones read `(window.__playbench?.overrides ?? {}).<name> ?? <default>`.
- **coding 3:** explain this contract and review the human's adapter. Don't write it.

Rerun the same quick playtest after the upgrade and report the new tier.

## 6. Agent playtest (decision points, web only)
When: menus, puzzles, choice-driven games, or when a quick run stalls at a choice the random bot can't make. Not under `AI_POLICY=banned` (only T0 playtests are allowed there).
1. The script is `playtests/agent/<name>.json`; it starts as `[]` (created if missing).
2. Run `<RUN> "<PLUGIN>/scripts/playtest.py" agent <BUILD> --script playtests/agent/<name>.json --out playtests` (`--then idle|random|policy` keeps playing after the script; default `pause`).
3. Exit 3 prints `DECISION=<json>`: read it (`t`, `reason` choices|stuck|crash|script_end, `state`, `actions`) and its `.png`. A crash also prints `ERROR=` lines: triage it like a crash FAIL.
4. Choose inputs as a first-time player would, and explain each choice in one line. Append entries with `t` >= the decision `t`; end with an entry like `{"t": <when to look again>, "keys": []}`. Use only `actions` keys.
5. Rerun (the fake clock replays identically). Exit 0 prints `AGENT_DONE over=... won=... t=...`.
6. At most 10 decisions per session, then summarize what the path showed. Keep the script: `run <BUILD> --bot script:playtests/agent/<name>.json` replays it as a regression check.

## 7. Milestone extras
- Read the FAIL screenshots listed in the report. If there are more than 5, hand them to a subagent.
- Replace `(pending)` under `## Claude's review of anomaly screenshots` in the milestone `.md`. Describe only what is visible (what is on screen, what looks stuck or broken). Do not judge fun.
- **Persona commentary:** dispatch 4 subagents in parallel, each given the `## Filmstrip` PNGs, the report `.md`/`.json`, any `playtests/shots/agent-*` shots and the experience goals from `design/design.md`:
  - **Newbie:** first time, reads nothing. **Min-maxer:** optimal play and exploits. **Explorer:** edges, boundaries, secrets. **Quitter:** when and why they would stop.
  - Each returns at most 5 bullets. Replace `(pending)` under `## Persona commentary` with `### <Persona> (AI persona, opinion only)` sections.
  - Never phrase it as fun / not fun, never tick a box. Humans decide.
- Point the human to `playtests/<stamp>-sheet.md`: play the game with a real person, fill in the sheet, then log it with `/playbench:log` (it writes `playtests/<date>-<HHMM>-human.md`). Only a human sheet can mark experience goals met.
- `playtest.py sheet <game> --out playtests` prints a fresh sheet any time; write-ups go through `/playbench:log`.
- `playtest.py survey <game> --out playtests` writes a 2-minute anonymous survey (one 1-5 statement per experience goal, plus a Google Forms paste block). Responses go through `/playbench:log`.

## 8. Gates
Never tick a gate box, and never write `[x]` into `gates.md`. Name the box the result supports instead, for example: "This supports *Latest quick playtest is PASS* in `## prototype`. Tick it yourself if you agree." A WARN supports a box only once each WARN is triaged.

## Notes
- **Threaded web builds** (SharedArrayBuffer, pthreads) can't run under the fake clock. Use `--realtime`, plus `--coop` if they need COOP/COEP headers.
- **Godot 4 web exports** should use the no-threads variant.
- **Godot native** (`project.godot` in the build) is **EXPERIMENTAL** (tested only against a fake `godot`). It needs `GODOT` set to a Godot 4 editor.
  - Knobs: each `--override name=V` reaches the game as the user arg `--name=V`; define `probe_knobs(knobs: Dictionary)` on the main scene's root (called before `_ready`).
  - `--windowed` opens a real window instead of `--headless` and saves a frame every second, so frozen/dead-input checks and FAIL screenshots work.
- **Native Unity or Unreal** builds can only be bot-tested through a WebGL/HTML5 export.
- Bots can't judge fun, clarity or feel. Say so every time; the human sheet covers it.

## Next loop
End your reply with one line `Next loop: <loop> (/playbench:<skill>)`. Default: `build` after a FAIL (fix it), `balance` when tier 2 and `BALANCE=on` past the first stage, `iterate` when findings need a decision, `log` when `DEBT_HUMAN` warns. When unsure, use `LOOP`/`NEXT` from a fresh `studio.py status`.
