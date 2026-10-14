---
name: studio
description: Use when starting or resuming a game project, when the user asks what to do next, about project status, gates, playtest debt, jam deadline, or to set up playbench for jam/hobby/team/class use.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Read, Write, Edit, Glob, Grep
---
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playbench: no working Python 3 found"`
> **Any agent:** Claude Code runs the line above for you. If no `KEY=value` status block appears above, run `python "<SKILL_DIR>/../../scripts/studio.py" status` yourself (`py -3` on Windows, `python3` elsewhere) and treat its output as the status block. `<SKILL_DIR>` is the folder holding this SKILL.md; `<PLUGIN>` is the `PLUGIN` value from status. Names like `/playbench:build` mean "the playbench build skill" on any agent.

# playbench studio

The block above is `status` output for the current folder (the game repo), as `KEY=value` lines. Read it before you say anything. Scripts run as `<RUN> "<PLUGIN>/scripts/<x>.py" ...`, using the `RUN` and `PLUGIN` values exactly as printed, with the path in quotes.

If the block says `playbench: no working Python 3 found` (or `RUN=NONE`), tell the user to install Python 3.11+ from python.org and stop.

## If INIT=no: set up in a few short questions

Ask **one question at a time**, each with a default the user can accept with "ok". Use plain words.

1. **What kind of project?** Default from the folder: `jam` if they mention a jam or deadline, otherwise `hobby`.
   - jam: game jam with a deadline
   - hobby: solo, spare time (solo-but-commercial counts as hobby)
   - team: 2-5 people shipping together, usually on Steam
   - learn: a course or class project
2. **How much do you want to code?** Default 2.
   - 1: "I mostly describe; you write the code, the test adapter and the bot."
   - 2: "You write, I review."
   - 3: "I write it myself; explain the contract and review my code."
3. **Engine.** Confirm the detected `ENGINE` and `BUILD` ("I see a web build in `build/`, right?"). If unknown, ask. Be honest:
   - Any HTML5 export works (plain JS, Phaser, Godot web, Unity WebGL, GameMaker, Construct, GDevelop).
   - Native Unity or Unreal builds can be playtested only through a WebGL/HTML5 export.
   - Godot native playtests are **experimental** until verified with a real Godot binary.
4. **Where will it ship?** Default: jam/learn `itch`, hobby `itch`, team `steam,itch`. Options: itch, steam, web (jam and learn: itch, web only; init refuses steam there).
5. **One context extra:**
   - jam: the submission deadline (ISO date and time, e.g. `2026-10-20T18:00`).
   - hobby: hours per week and number of weeks (this caps the must list).
   - team: each member, what they own, and which stages they sign off, as `Name:owns:stage1,stage2`. Stages are prototype, slice, alpha, beta, release.
   - learn: the course AI policy: `open`, `disclose` (default; commits keep the Co-Authored-By trailer) or `banned`.
   - Ask for the itch `user/game` slug only if they ship to itch and know it; it can be added to studio.json later.

Then run, from the game folder:

`<RUN> "<PLUGIN>/scripts/studio.py" init --context <c> --coding <n> --engine <e> --build-dir <dir> --platforms <list> [--deadline ISO] [--hours N --weeks N] [--member "Name:owns:stages"]... [--ai-policy P] [--itch user/game]`

If it refuses because files exist, show the message and ask before adding `--force`. Then rerun `status` and continue below.

## If INIT=yes: explain where they are

Say it in 3-5 plain lines, adapted to `CONTEXT` and `CODING`:
- **Stage** (`STAGE`) and the open boxes under `UNTICKED:`. Say which box the human can tick next and what evidence supports it. In team context, name the owner on each box.
- **Playtest debt:** `DEBT_QUICK` is commits since the last quick bot playtest; `WARN` means run one now. `DEBT_HUMAN` is commits since a human last played (jam shows it but never warns).
- **Jam:** lead with `DEADLINE`. Push to cut scope when it gets tight.
- **Learn:** mention `AI_POLICY` once.
- CODING 1: no jargon, one-line verdicts. CODING 3: you may name the scripts and files.

Then show `LOOPMAP` as is and offer `NEXT` as a one-line question ("Want me to do that now?").

## The loop
- Every project cycles design > build > test > balance > iterate > log > ship. `LOOP` is where this one is now, worked out from its files and git (nothing to keep up to date by hand); `LOOPMAP` shows it in brackets.
- build makes one small slice, test runs a bot playtest, log turns a human session into notes, iterate ranks changes from everything since `ITERATION` (counts in `SINCE_ITERATION`).
- Debt, a FAIL, a missing report or new human evidence pulls the loop back; skipping a loop is fine when the user says why.

## Routing
- Idea, theme, scope, the one-page design: `/playbench:design`.
- The next must-list feature as one small slice: `/playbench:build`. Placeholder art, art bible, sprite sheets: `/playbench:art`.
- After every feature, before ticking a gate, or when something feels broken: `/playbench:playtest` (quick after each feature; milestone or final when `REQUIRED` lists them; sizes from `SIZES`).
- Tuning numbers or difficulty: `/playbench:balance`, only if `BALANCE=on` or the user asks for it (jams have it off).
- A human played it (notes, observation sheet): `/playbench:log`. Comments from Discord, itch, Steam or a survey: `/playbench:feedback`.
- Deciding what to change next from playtests and feedback: `/playbench:iterate`.
- Release, itch/Steam/web, AI-art disclosure, gate audit: `/playbench:ship`. After shipping: `/playbench:postmortem`.

## Plugin hooks
- A guard stops Claude from ticking boxes in `gates.md`; humans tick them by hand.
- When quick playtest debt is over the limit, a Stop hook reminds Claude to run a quick playtest. `AUTO_PLAYTEST` shows it; `"auto_playtest": false` in `studio.json` turns it off.

## Hard rules
- **Never tick a gate box.** Never write `[x]` into `gates.md`, not even when asked. Tell the human which box they can tick, and say to commit `gates.md` so `ship gate` can show who ticked it.
- If `ALLOWED` is printed (`AI_POLICY=banned`), do only those actions: explain, review, status, T0 playtest, artgate. Refuse to write game code, adapters, bots or models, and list what is allowed.
- `CONTEXT=learn`: for course reports, offer `<RUN> "<PLUGIN>/scripts/studio.py" aiuse . --md` (an AI-use summary from git; it only sees commits with a Co-Authored-By: Claude trailer).
- If `PLAYWRIGHT=no`, show the `INSTALL` line and **ask before running it**. studio, ship artgate/gate and Godot still work without it.
- If `INSTALL` contains `-m venv`, this Python refuses pip installs (it is "externally managed"), so playbench makes its own virtual environment in `VENV` and installs Playwright there. Say that in one line and ask first. Afterwards `RUN` is that venv's quoted path, and each command with it may ask for permission.
- `GODOT=none` with a Godot project: say playtests need `GODOT` set to a Godot 4 editor executable, and that Godot native is experimental. Do not download Godot without explicit permission.
- Never edit `studio.json` for team members silently; it is the team's shared config. Propose the change and let them commit it.

## Next loop
End with one line `Next loop: <loop> (/playbench:<skill>)`. Default: the `LOOP` value, with skill `playtest` for `test` and the loop name otherwise. When unsure, rerun `status` and use its `LOOP` and `NEXT`.
