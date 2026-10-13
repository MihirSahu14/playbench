---
name: balance
description: Use when the user wants to tune game numbers, check difficulty, compare knob values, or asks whether something is too hard or too easy.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Read, Write, Edit, Glob, Grep
---
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playloop: no working Python 3 found"`

# Balance: sweep one knob on the real build

The status lines above give `RUN`, `PLUGIN`, `CODING`, `AI_POLICY`, `ENGINE`, `SIZES`, `BALANCE` and `ALLOWED`. Use them; don't ask for what they already say.

## 0. Preconditions
- `RUN=NONE` or the echo fallback: tell the user to install Python 3.11+ and stop.
- `AI_POLICY=banned`: running a sweep is not in `ALLOWED`. Refuse the run, list what is allowed, and offer to explain how a sweep works so the student can run `balance.py` themselves.
- `BALANCE=off` (jam): say "Balance is off for jams; a quick playtest tells you more right now." Go on only if the user insists.
- `ENGINE=godot`: v1 sweeps are web-only, because Godot data inside the `.pck` can't be overridden. Offer a web export of the same project, or hand-tuning plus a playtest.

## 1. Pick the knob
Read `design/design.md` and show its `## Knobs` table (`| name | file | key | min | max |`). Ask which knob to sweep (default: the one the user named, else the first row).

If the number they care about isn't in the table, offer to make it a knob (one question, default yes):
- **Preferred:** move it into a data file the game fetches (CSV or JSON), then add a row, e.g. `| bat_speed | data/enemies.csv | bat.speed | 1 | 5 |`. CSV keys are `<first-column value>.<column>` or `*.<column>`; JSON keys are dotted paths.
- **Bundled number:** read it as `(window.__playloop?.overrides ?? {}).<name> ?? <default>` and add a row with file `-`.
- Who writes it, by `CODING`:
  - 1: Claude makes the change and says so in one line.
  - 2: Claude makes the change and asks the human to review the diff.
  - 3: Claude explains the pattern and reviews the human's change.
  - `AI_POLICY=banned`: the student writes the code; Claude only explains.

## 2. Run the sweep
Take seeds and seconds from `SIZES` (use the `milestone` entry, `<seeds>x<seconds>`). Default values are 5 evenly spaced points from min to max; pass `--values` when the user names specific ones.

```
<RUN> "<PLUGIN>/scripts/balance.py" sweep . --knob <name> [--values a,b,c] --seeds <n> --seconds <s>
```

Each value is a full set of bot runs, so warn that it takes a minute or more per value.

Exit codes:
- 0: a table is printed and `balance/last.json` is updated (other knobs kept).
- 2 with "needs a policy bot": the game has no `window.__game.bot`. Random-input sweeps are noise, so route to the **playtest** skill to add a policy bot, then come back. Under `AI_POLICY=banned` the student writes the bot.
- 2 with an install hint: show the hint (`<RUN> -m pip install playwright && <RUN> -m playwright install chromium`) and stop.
- 2 with "unknown knob" or "no design.md": fix the Knobs table (step 1) or route to the **design** skill.

## 3. Read it back
Show the table, then say what it means in plain words (one or two lines at `CODING=1`):
- **These numbers measure Claude's heuristic bot, not humans.** Use them only to compare values with each other ("win rate drops sharply between 3 and 4"), never as "players will win 40% of the time".
- Point out the cliff: the value range where win % or p50 time changes most.
- `Δ win % vs last` compares with the previous sweep of the same knob. A change there with the same value means the game itself changed.
- Suggest one value and why, e.g. "3 keeps the bot losing about half its runs at around 20 s".
- **The human decides.** Don't edit the data file unless they pick a value and ask.
- A human playtest confirms it: offer the playtest skill's human sheet. Never tick a gate box; tell the human which box they can tick.

## v1 limits (say them if relevant)
- Web builds only; Godot `.pck` data can't be overridden yet.
- One knob per sweep. Spreadsheet economy sims and cost curves arrive in v1.1.
