---
name: build
description: Use when the user wants to build, code or implement the next feature, asks "what should I make next", wants to add a mechanic, enemy, level or menu, or says "let's make the game".
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Read, Write, Edit, Glob, Grep
---
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playbench: no working Python 3 found"`

# Build: one small slice, then a quick playtest

The status lines above give `RUN`, `PLUGIN`, `BUILD`, `ENGINE`, `CODING`, `AI_POLICY`, `ALLOWED`, `SIZES`, `DEBT_QUICK`, `DEBT_HUMAN`, `AUTO_PLAYTEST`, `LOOP` and `NEXT`. Use them; don't ask for what they already say. Ask one question at a time, each with a default.

## 0. Preconditions
- `RUN=NONE` or the echo fallback: tell the user to install Python 3.11+ and stop.
- No `design/design.md`: say the slice needs a must list first and route to `/playbench:design`.
- `AI_POLICY=banned`: Claude writes no game code. Help pick and slice, explain the engine pattern, review the student's code against the slice, then run a T0 quick playtest (it is in `ALLOWED`). Never write adapters, bots or data-file code.
- The newest quick report is FAIL: fix that first; it is the slice.

## 1. Pick the must item
Read the `## Scope` table in `design/design.md` and `design/build-log.md` (if present). Propose the first `must` item with no `(must: <item>)` line in the log: "Next up: *<item>* (<h> h). OK?" Default: that item. All musts logged: say so, offer a `should` item or `/playbench:iterate`.

## 2. Slice it
Cut the item into **one** feature of about 1-2 hours that is:
- **visible** in the build (the player sees or does something new),
- **checkable by a bot** (it changes the probe state, or at least the screen),
- written as **verb + feedback**, e.g. "jump: the hero rises and lands, a puff on landing".

Ask once: "Slice: *<verb + feedback>*. OK?" (default: yes). Too big for 2 hours: offer the smaller half.

## 3. Implement, engine-aware
Detect the engine from `ENGINE` and the files:
| Engine | Detect | How |
|---|---|---|
| plain JS | `ENGINE=web`, no framework | edit the game scripts directly |
| Phaser | `phaser` in `package.json` or a `<script>` tag | scenes, `this.input.keyboard`, `this.load` |
| Godot | `ENGINE=godot` (`project.godot`) | GDScript on the main scene; harness is **EXPERIMENTAL** |
| Unity / GameMaker / Construct / GDevelop HTML5 exports | export files only | Claude edits only scripts it can reach and guides editor steps in short numbered lines; probe adapters in `${CLAUDE_PLUGIN_ROOT}/skills/playtest/adapters.md` |

Who writes it, by `CODING`:
- **1:** Claude writes it, then says what changed in one plain line.
- **2:** Claude writes it, then asks the user to review the diff, naming the 2-3 key lines.
- **3:** the user writes it; Claude reviews against the slice and the probe contract (below). No rewriting; point at lines and say why.

## 4. Tunables: no new magic numbers
Every new number a player feels (speed, damage, timer, cost, spawn rate) goes into a data file and the `## Knobs` table of `design/design.md`:
- **Preferred:** `data/*.csv` or `*.json`, e.g. row `| jump_height | data/player.json | jump.height | 2 | 6 |`.
- **Bundled (web):** `(window.__playbench?.overrides ?? {}).<name> ?? <default>` with file `-`.
- **Godot:** read it in `probe_knobs(knobs: Dictionary)` (called before `_ready`) or from the data file.

## 5. Keep the probe contract working
- `window.__game.state` (Godot: `probe_state()`) still reports `over`, `won`, `paused` and any new state that matters to the slice (no timers or clocks in state).
- A new menu, pause screen or cutscene sets `paused: true` while it shows.
- New keys go into `actions`; update the `bot` if the slice changes how to survive or win.
- New sprites: placeholders via `/playbench:art` (`_placeholder` files, recorded in `art/PLACEHOLDERS.json`). Never present them as final art.

## 6. Quick playtest, right away
Sizes from `SIZES` (the `quick` entry, `<seeds>x<seconds>`). Run from the game folder, without asking:
```
<RUN> "<PLUGIN>/scripts/playtest.py" run "<BUILD>" --mode quick --seeds <n> --seconds <s> --out playtests
```
- Quote the verdict line and the `cannot_judge` line exactly.
- **FAIL:** read the screenshot and the code path, fix it, rerun. Stay in this loop until PASS or WARN; after 3 failed fixes, stop and ask (at `CODING=3` or `AI_POLICY=banned` the user fixes; Claude explains the finding).
- Exit 2: show the setup message (e.g. the `INSTALL` line) and ask before running anything it suggests.

## 7. Log it
Append one line to `design/build-log.md` (create it with `# Build log` first):
```
- <YYYY-MM-DD> <slice> (must: <item>) quick: <verdict> <report file>
```
Then name the gate box the result supports, e.g. "This supports *Latest quick playtest is PASS*; tick it yourself if you agree." **Never tick a gate box**; never write `[x]` into `gates.md` (a plugin hook blocks it anyway).

Mention once per session, when `AUTO_PLAYTEST=on`: a Stop hook may remind Claude to run a quick playtest when commits pile up without one.

## Next loop
End with one line `Next loop: <loop> (/playbench:<skill>)`. Default: `Next loop: build (/playbench:build)` for the next slice. Use `log (/playbench:log)` when `DEBT_HUMAN` warns, and `iterate (/playbench:iterate)` when `LOOP` says so. When unsure, run a fresh `status` and use its `LOOP` and `NEXT`.
