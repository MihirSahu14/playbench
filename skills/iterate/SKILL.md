---
name: iterate
description: Use when the user asks what to change next, wants to act on playtest results or feedback, says "players found it confusing", "time to iterate", "what should we fix", or wants to revise the design after testing.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Read, Write, Edit, Glob, Grep
---
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playbench: no working Python 3 found"`
> **Any agent:** Claude Code runs the line above for you. If no `KEY=value` status block appears above, run `python "<SKILL_DIR>/../../scripts/studio.py" status` yourself (`py -3` on Windows, `python3` elsewhere) and treat its output as the status block. `<SKILL_DIR>` is the folder holding this SKILL.md; `<PLUGIN>` is the `PLUGIN` value from status. Names like `/playbench:build` mean "the playbench build skill" on any agent.

# Iterate: one ranked change list, the human picks

The status lines above give `CONTEXT`, `CODING`, `AI_POLICY`, `ITERATION`, `SINCE_ITERATION`, `BALANCE`, `LOOP` and `NEXT`. Use them; don't ask for what they already say. Ask one question at a time, each with a default. **Never auto-apply a change.**

## 0. Preconditions
- No `design/design.md`: route to `/playbench:design`.
- `SINCE_ITERATION` all zero: say there is no new evidence; suggest `/playbench:playtest` or `/playbench:log` first. Go on only if the user insists.
- `AI_POLICY=banned`: Claude gathers and explains the evidence and the table; the student picks and edits every file.

## 1. Gather everything since the last iteration
The cut-off is the date in `ITERATION` (`none`: everything). Read files whose `YYYY-MM-DD` name prefix is on or after it, skipping any already listed under `## Evidence` in the previous `design/iterations/<n>.md` (`SINCE_ITERATION` skips those too):
| Source | What to pull |
|---|---|
| `playtests/*.json` (bot reports) | `verdict`, `findings`, `regression.new_kinds`, `regression.stat_shifts` |
| `playtests/*-human.md` | experience goals met / not met, confusion and quit points, quotes |
| `feedback/*.md` | the ranked issues |
| `balance/*.md`, `balance/last.json` (entries with `at` on or after the cut-off) | cliffs, cost-curve outliers, dominated strategies, deadlocks, runaways |
| `telemetry/*-report.md` | funnel drop-offs (where players quit) |
| `design/journal.md` | `## <YYYY-MM-DD>` entries on or after the cut-off |

Also read `design/design.md` (pillars, experience goals, scope, knobs) and `design/build-log.md`.

## 2. Build ONE ranked change list (at most 7 rows)
```
| # | change | evidence (file) | serves | cost (h) | kind |
|---|---|---|---|---|---|
| 1 | Show a 1 s warning before bats fall | playtests/2026-10-12-1400-human.md (3 of 4 "hit from nowhere") | goal: every hit feels fair | 1 | fix |
```
- **serves:** the pillar, system or experience goal it helps. A change that serves none is flagged `consider cutting`.
- **kind:** `fix`, `tune`, `cut` or `add`.
- **Rank** by evidence strength (humans > telemetry > bots) x impact on experience goals / cost. Several sources agreeing beats one loud one.
- Bot evidence compares builds and values; it never predicts what humans feel. Say so if a row rests only on bots.
- `CODING=1`: plain words, one line under the table. `CODING=3`: name the detector or metric behind each row.

Ask: "Which ones? (default: 1-<top 2 or 3>)". Picking none is fine; still write the record (step 4).

## 3. Apply only the picks
- **Design edits** go into `design/design.md` in place. Move the replaced text under a final `## History` section as `### Iteration <n> (<YYYY-MM-DD>)` (create `## History` if missing). Never use a `Knobs` or `Experience goals` heading inside History, so parsers ignore it. The page above History stays about 60 lines.
- **Knob values** go into the data files the `## Knobs` table names. The human chooses the value; show the balance results that bear on it (`BALANCE=on`: offer a `/playbench:balance` sweep first).
- **Scope moves** (must / should / cut): re-check the hours budget (`hours_per_week x weeks` in `studio.json` when set; jam: the hours left in `DEADLINE`). Over budget: ask what to move out.
- **Code changes** are not made here: each becomes a build slice.
- **Team context:** a change in another member's area (their `owns` in `studio.json`) is proposed to them in one line, not applied.
- By `CODING`: 1 Claude edits and says what changed in one line; 2 Claude edits and asks for a review of the diff; 3 Claude shows the exact edit and the user makes it.

## 4. Write the record
`<n>` is the `ITERATION` number + 1 (1 when `none`). Write `design/iterations/<n>.md`:
```
# Iteration <n> (<YYYY-MM-DD>)
## Evidence
- [playtests/<file>](../../playtests/<file>): <one line>
## Changes
<the ranked table>
## Picked
- #1, #3
## Not picked
- #2: <one-line why>
## Expected effect
- #1: <what should change> - verify with <quick playtest / human goal "<goal>">
```
This file moves `ITERATION` forward, so the next round only counts newer evidence. List every file you used under `## Evidence`: a same-day file it doesn't name still counts as new.

## Rules
- **Never tick a gate box**; never write `[x]` into `gates.md`. Name the box the evidence supports instead.
- Humans own fun and the GO/KILL line; an iteration never fills in `Decision:`.
- Keep it to one change list per iteration; leftovers wait for the next round.

## Next loop
End with one line `Next loop: <loop> (/playbench:<skill>)`. Default: `Next loop: build (/playbench:build)`, with the first picked change as the next slice. When unsure, run a fresh `status` and use its `LOOP` and `NEXT`.
