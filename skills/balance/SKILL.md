---
name: balance
description: Use when the user wants to tune game numbers, check difficulty, compare knob values, price items or upgrades, simulate an economy, check unit matchups, or asks whether something is too hard, too easy or overpowered.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Read, Write, Edit, Glob, Grep
---
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playbench: no working Python 3 found"`

# Balance: compare numbers, the human picks

The status lines above give `RUN`, `PLUGIN`, `CODING`, `AI_POLICY`, `ENGINE`, `SIZES`, `BALANCE`, `ALLOWED`, `LOOP` and `NEXT`. Use them; don't ask for what they already say.

## 0. Preconditions
- `RUN=NONE` or the echo fallback: tell the user to install Python 3.11+ and stop.
- `AI_POLICY=banned`: sweep, costcurve, sim and matrix runs are not in `ALLOWED`. Refuse the run, list what is allowed, and offer to explain how the tool works so the student can run `balance.py` themselves.
- `BALANCE=off` (jam): say "Balance is off for jams; a quick playtest tells you more right now." Go on only if the user insists.

Pick the tool from the question (one question, default `sweep`):
| Question | Tool |
|---|---|
| "Is this too hard?" on the real build | `sweep` |
| "Is this item/upgrade priced right?" | `costcurve` |
| "Does the economy stall or explode?" | `sim` |
| "Is any unit or strategy always best?" | `matrix` |

Add `--out balance` to `costcurve`, `sim` and `matrix`: it writes `balance/<YYYY-MM-DD-HHMM>-<tool>.md` and prints `REPORT=<path>`.

## 1. Sweep: one knob on the real build
Read `design/design.md` and show its `## Knobs` table (`| name | file | key | min | max |`). Ask which knob to sweep (default: the one the user named, else the first row).

If the number isn't in the table, offer to make it a knob (one question, default yes):
- **Preferred:** move it into a data file the game reads (CSV or JSON), then add a row, e.g. `| bat_speed | data/enemies.csv | bat.speed | 1 | 5 |`. CSV keys are `<first-column value>.<column>` or `*.<column>`; JSON keys are dotted paths.
- **Bundled number (web):** read it as `(window.__playbench?.overrides ?? {}).<name> ?? <default>` and add a row with file `-`.
- Who writes it, by `CODING`: 1 Claude makes the change and says so in one line; 2 Claude makes it and asks the human to review the diff; 3 Claude explains the pattern and reviews the human's change. Under `AI_POLICY=banned` the student writes it.

Seeds and seconds come from `SIZES` (the `milestone` entry, `<seeds>x<seconds>`). Default values are 5 evenly spaced points from min to max.
```
<RUN> "<PLUGIN>/scripts/balance.py" sweep . --knob <name> [--values a,b,c] --seeds <n> --seconds <s>
```
Warn that each value takes a minute or more. Exit 0: a table, and `balance/last.json` updated. Exit 2 with "needs a policy bot": route to the **playtest** skill to add one (random-input sweeps are noise). Exit 2 with an install hint: show it and stop. "unknown knob" or "no design.md": fix the Knobs table or route to **design**.

**Godot sweeps (EXPERIMENTAL, unverified):** every knob reaches the game as a user arg `--<name>=<value>`, file-column knobs too, by name. The game applies them in `probe_knobs(knobs: Dictionary)` on its main scene root (called before `_ready`) or reads `OS.get_cmdline_user_args()`. Data inside the `.pck` is not patched; the game must apply the value itself.

## 2. Costcurve: are items priced fairly?
Needs a CSV with one row per item (at least 3, best 6+), an id column (first column, or `--id`), a `cost` column (or `--cost`) and benefit columns (default: every other numeric column, summed unweighted; pick with `--benefit atk,hp`).
```
<RUN> "<PLUGIN>/scripts/balance.py" costcurve data/items.csv [--cost price] [--benefit atk,hp] --out balance
```
It fits `cost = a x benefit + b` and flags items more than 2 sigma off the line as overpriced or underpriced. If benefits aren't comparable (1 hp is not 1 atk), say so and suggest a weighted column.

## 3. Sim: Monte Carlo economy model
1. If `balance/model.py` is missing, copy `${CLAUDE_PLUGIN_ROOT}/skills/balance/model-template.py` there. Fill it from the knobs and economy in `design/design.md`: at `CODING` 1-2 Claude writes it (2: the human reviews it); at `CODING=3` or `AI_POLICY=banned` the human writes it and Claude explains and reviews.
2. Say plainly: **the model file is the user's own code and `sim` executes it.** Read any model you didn't write before running it.
3. Run:
```
<RUN> "<PLUGIN>/scripts/balance.py" sim balance/model.py [--runs 1000] [--seed 1] [--knob income=2] --out balance
```
It reports each final metric (mean, p10, p50, p90, min, max), runs that ended early, **deadlocks** (state unchanged for `DEADLOCK_TICKS`) and **runaways** (a metric outside `LIMITS`, or NaN/inf), each with an example seed. Compare two `--knob` values by running twice. A model is only as true as its code: confirm anything surprising on the real build with a sweep or a playtest.

## 4. Matrix: unit matchups and RPS-like systems
A square CSV: header row = column strategies, first column = the same row strategies in the same order; each cell is the row strategy's payoff (win rate 0..1, or any number) against the column.
```
<RUN> "<PLUGIN>/scripts/balance.py" matrix design/matchups.csv --out balance
```
It flags dominated and dominant strategies and estimates the Nash mix. A strategy dominated or never picked at equilibrium is a design smell worth naming; the equilibrium is not how real players will play.

## 5. Read it back
Show the table, then say what it means in plain words (one or two lines at `CODING=1`):
- **Bot and model numbers compare values; they never predict human results.** Say "win rate drops sharply between 3 and 4", never "players will win 40% of the time".
- Point out the cliff (sweep), the outliers (costcurve), the deadlocks and runaways (sim) or the dominated strategies (matrix).
- `Δ win % vs last` compares with the previous sweep of the same knob; a change at the same value means the game changed.
- Suggest one value or change and why. **The human picks.** Don't edit data files unless they pick a value and ask.
- A human playtest confirms it: offer the playtest skill's human sheet. Never tick a gate box; tell the human which box they can tick.

## Next loop
End with one line `Next loop: <loop> (/playbench:<skill>)`. Default: `Next loop: iterate (/playbench:iterate)` when the results suggest a change, else `Next loop: build (/playbench:build)`. When unsure, run a fresh `status` and use its `LOOP` and `NEXT`.
