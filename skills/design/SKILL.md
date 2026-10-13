---
name: design
description: Use when the user wants to discuss a game idea, brainstorm (including jam themes), define the hook/core loop/scope, or write or update the one-page design.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Read, Write, Edit, Glob, Grep
---
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playbench: no working Python 3 found"`

# playbench design: one discussion, one page

Output is exactly one file: `design/design.md`, built from `${CLAUDE_SKILL_DIR}/design-template.md`, about 60 lines at most. Never more docs. If `INIT=no`, suggest `/playbench:studio` first, but carry on if the user just wants to talk ideas (assume hobby).

If `design/design.md` exists, read it and **edit it in place**; ask only about what is changing.

## The conversation (one question at a time, each with a default)
1. **Idea.** "What's the game, in a sentence?" For `CONTEXT=jam`, first ask for the theme and offer **5 interpretations** of it (one literal, one mechanical, one twist, one tonal, one off-the-wall), each as a one-line game pitch; let them pick or remix.
2. **Hook.** Propose one sentence; let them edit it.
3. **Core loop.** The action repeated every few seconds, then the 30s and 5min arrows. Push back if the loop has no verb the player does.
4. **Scope: must / should / cut.** Propose a list; the user moves items.
   - Every must item gets an hours estimate.
   - hobby: the budget is `hours_per_week × weeks` from studio.json. The must total may not exceed it. If it does, ask what to move to should or cut.
   - jam: the budget is the hours in `DEADLINE`, minus about 25% for packaging and upload. Cut hard.
   - team and learn: ask for the budget in hours (default: skip the Budget line if they don't know).
5. **Pillars** (not jam): 3 short bullets. Offer drafts drawn from the hook.

## Then write the page
- **Experience goals:** exactly one per must feature: `- <feature>: <what the player should feel or understand>`. These feed the milestone human playtest sheet, so make each one something a tester can say "met" or "not met" to.
- **Knobs:** one row for every tunable number the must list implies (speeds, spawn rates, damage, timers, costs). Columns `name | file | key | min | max`; keep the comment row from the template.
  - Prefer numbers in data files the game loads (`data/*.csv` or `*.json`): key `<id>.<column>` or `*.<column>` for CSV, a dotted path for JSON.
  - A bundled number uses file `-` and is read in code as `(window.__playbench?.overrides ?? {}).<name> ?? <default>`.
  - `CODING=1`: tell the user Claude will move these tunables into data files while building. `CODING=3`: explain the table and let them choose. Under `AI_POLICY=banned`, explain only; the student writes the code.
- Drop the sections the context doesn't use: jam has Hook, Core loop, Scope, Experience goals, Knobs (no Pillars, no Decision).
- **Decision:** leave exactly `Decision: ` empty. Never write GO or KILL; the human decides after playing the prototype. Say so.

## Rules
- One page. If it passes about 60 lines, cut words, not sections.
- No lore bibles, no GDD chapters, no extra files. Art direction, story and marketing wait until a human has played the prototype.
- Never tick gates. After the page is written, the next step is building the first must feature, then `/playbench:playtest` quick.
