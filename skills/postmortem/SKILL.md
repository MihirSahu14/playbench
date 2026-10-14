---
name: postmortem
description: Use when a release, demo or jam is over, or when the user asks for a postmortem, retrospective, retro, "what went right and wrong", or lessons for the next game.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Bash(git log:*), Bash(git shortlog:*), Read, Write, Edit, Glob, Grep
---
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playbench: no working Python 3 found"`

# playbench postmortem: what happened, with evidence

The status block above gives `RUN`, `PLUGIN`, `CONTEXT`, `CODING`, `AI_POLICY`, `STAGE` and `ITERATION`. Scripts run as `<RUN> "<PLUGIN>/scripts/<x>.py" ...`, with the values exactly as printed. Run everything from the game folder.

Output is one file: `design/postmortem.md`. If it exists, ask: "Update the existing postmortem or start a new one for this release? (default: update)"; a new one moves the old text under `## Earlier postmortems` at the end.

## 1. The user's voice first
Ask **one** question before you look at anything: "In your own words, what's the one thing that went right, and the one that went wrong? (default: skip, I'll start from the evidence)". Their answers lead their sections, quoted as they said them. Evidence may support or complicate them; it never overrules them.

## 2. Gather the evidence
Read only what exists; skip missing sources and say which were missing. Tally, don't judge.
- **Git:** `git log --reverse --format="%ad %s" --date=short -- .` and `git shortlog -sn HEAD -- .` (keep `HEAD`: without it shortlog waits on stdin) for the game folder: span in days, commits, contributors (counts only in solo projects; names only for `team`, as in studio.json).
- **AI use:** `<RUN> "<PLUGIN>/scripts/studio.py" aiuse . --md`. Keep its block as printed.
- **Bot playtests:** `playtests/*.json`: counts by `mode` (quick / milestone / final), verdicts, and the finding kinds of each FAIL over time (did crashes stop? did softlocks come back?).
- **Human sessions:** `playtests/*-human.md`: how many, tester types, and experience goals met / not met / unclear in the first vs the last session.
- **Balance:** `balance/*.md` and `balance/last.json`: what was swept and what changed.
- **Gates:** `<RUN> "<PLUGIN>/scripts/ship.py" gate .` audits the last `## <stage>` (the release stage) only: who ticked each box, and when; `git log --format="%ad %an %s" --date=short -- gates.md` gives the earlier stages' tick history. Read them; never change `gates.md`.
- **Feedback:** `feedback/*.md`: the top issues, and for each whether a later commit, iteration or playtest shows it resolved (`resolved`, `open`, or `unknown` when nothing shows either).
- **Iterations and build log:** `design/iterations/*.md` and `design/build-log.md` against `## Scope` in `design/design.md`: must items planned vs done, and the hours budget vs the time actually spent (calendar days from git; hours only if the build log or journal records them).
- **Journal:** `design/journal.md` for blockers and mood in the user's own words.
- **Telemetry:** the latest `telemetry/*-report.md`, if any.

## 3. Write design/postmortem.md

```
# Postmortem: <game title from design.md> (<YYYY-MM-DD>)

## Numbers
| what | value | source |
|---|---|---|
| days, commits, contributors | ... | git |
| AI share of added lines | ...% | aiuse |
| bot playtests (quick / milestone / final) | ... | playtests/*.json |
| human sessions, goals met first -> last | ... | playtests/*-human.md |
| must items done / planned | ... | design.md, build-log.md |
| hours budget vs reality | ... | design.md, journal / git |
| feedback issues resolved / open | ... | feedback/ |

## Went right
- <3-5 items; the user's own item first> (evidence: <file>)

## Went wrong
- <3-5 items; the user's own item first> (evidence: <file>)

## What bots caught vs what only humans caught
| bots caught | only humans caught |
|---|---|
| <crash/softlock/dead input, with report file> | <confusion, fun, feel, with session file> |

## Next time
1. <a concrete rule, e.g. "Run a human session before the slice gate, not after">
2. ...
3. ...

## AI use (git-derived)
<the aiuse block, as printed>
```

- Every Went right / Went wrong item names one evidence file. If you have no evidence for a point, it does not go in, unless it is the user's own; then mark it `(the user's view)`.
- **Next time:** exactly 3 rules, each something the user can check next project (a number, a moment, a habit). No vague advice like "test more".
- Never write whether the game is fun or good; quote what humans said in the sessions and feedback instead.
- In `team` context, write about systems and process, never blame a person.

## 4. Report back
Word it by `CODING`: 1, the 3 Next time rules in plain words; 2, also the Numbers table, and ask the user to edit anything that reads wrong; 3, also say where each number came from. Say the file is theirs to edit, and that `CONTEXT=learn` courses often want the AI use block in the report.

## Policy
- `AI_POLICY=banned` (`ALLOWED` printed): you may run `aiuse` and `ship.py gate`, and gather the numbers. Do not write the reflection: give the student the template above with the Numbers filled in, and let them write the rest.
- **Never tick a gate box**, and never write `[x]` into `gates.md`. A postmortem is not a release approval.

## Next loop
End your reply with one line `Next loop: <loop> (/playbench:<skill>)`. Default: `design` (`/playbench:design`) to start the next project with the Next time rules; `log` (`/playbench:log`) when the game is still live and post-launch sessions or feedback keep coming. When unsure, use `LOOP`/`NEXT` from a fresh `studio.py status`.
