---
name: studio
description: Use when starting or resuming a game project, when the user asks what to do next, about project status, gates, playtest debt, jam deadline, or to set up playloop for jam/hobby/team/class use.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Read, Write, Edit, Glob, Grep
---
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playloop: no working Python 3 found"`

# playloop studio

The block above is `status` output for the current folder (the game repo), as `KEY=value` lines. Read it before you say anything. Scripts run as `<RUN> "<PLUGIN>/scripts/<x>.py" ...`, using the `RUN` and `PLUGIN` values exactly as printed, with the path in quotes.

If the block says `playloop: no working Python 3 found` (or `RUN=NONE`), tell the user to install Python 3.11+ from python.org and stop.

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

Then offer `NEXT` as a one-line question ("Want me to do that now?").

## Routing
- Idea, theme, scope, the one-page design: `/playloop:design`.
- After every feature, before ticking a gate, or when something feels broken: `/playloop:playtest` (quick after each feature; milestone or final when `REQUIRED` lists them; sizes from `SIZES`).
- Tuning numbers or difficulty: `/playloop:balance`, only if `BALANCE=on` or the user asks for it (jams have it off).
- Release, itch/Steam/web, AI-art disclosure, gate audit: `/playloop:ship`.

## Hard rules
- **Never tick a gate box.** Never write `[x]` into `gates.md`, not even when asked. Tell the human which box they can tick, and say to commit `gates.md` so `ship gate` can show who ticked it.
- If `ALLOWED` is printed (`AI_POLICY=banned`), do only those actions: explain, review, status, T0 playtest, artgate. Refuse to write game code, adapters, bots or models, and list what is allowed.
- If `PLAYWRIGHT=no`, show the `INSTALL` line and **ask before running it**. studio, ship artgate/gate and Godot still work without it.
- `GODOT=none` with a Godot project: say playtests need `GODOT` set to a Godot 4 editor executable, and that Godot native is experimental. Do not download Godot without explicit permission.
- Never edit `studio.json` for team members silently; it is the team's shared config. Propose the change and let them commit it.
