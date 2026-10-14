# playbench roadmap round (v1.1 to v3 + loops): Implementation Plan

**Spec:** `docs/superpowers/specs/2026-10-13-playbench-design.md`, section *Roadmap round*. Read it first.
**Repo:** `C:\Users\mihir\Desktop\Projects\Game Design Plugin` (Windows 11, Git Bash + PowerShell, branch main).
**Goal (the user's words):** "the plugin should help in all loops. design, build, testing, balancing, reiterations, human logging, ship".

## Rules for every package
- Stdlib first. Pillow only in `scripts/art.py` (lazy import). Playwright only where it is already used (`playtest.py`).
- Fewest files, no speculative abstractions, match the existing style: terse code, `ponytail:` comments on deliberate shortcuts, `KEY=value` status lines, exit codes 0 pass / 1 blocked or FAIL / 2 usage or environment.
- Every non-trivial script has a `selftest` subcommand of plain asserts that prints `ok <name>` or `SKIP <name>: <why>`; `scripts/selftest.py` runs them all.
- Claude never ticks gate boxes; humans own fun, final art, GO/KILL, release approval.
- AI art = clearly marked placeholders only (`_placeholder` names, `art/PLACEHOLDERS.json`); `ship artgate` keeps blocking undisclosed ones.
- Never download binaries or large files (no Godot, Aseprite, export templates), never install anything globally, never use real credentials, never run real uploads, never `git commit`/`git push` in this repo. Temp git repos inside a selftest are fine.
- godot, aseprite, butler, steamcmd and netlify are tested only against fake stub executables in a temp dir (see *Stub helper*) and SKIP cleanly when the real binary is absent. A selftest must never be able to reach a real binary on the user's machine for an upload.
- Package owners edit only the files they own. README.md and docs/reference.md belong to a later docs pass.

## Environment facts
- `python` is 3.11.0 with playwright and Chromium, and Pillow 12.3.0. `py -3` is 3.13 without playwright.
- godot, aseprite, butler, steamcmd and netlify are not installed. `gh` is installed (never used for pushes).
- `CLAUDE_PLUGIN_DATA` is not set in a plain shell; plugin skills and hooks receive it from Claude Code.

## Waves
| Wave | Package | Items | Owns |
|---|---|---|---|
| 1 | **W1-STUDIO** studio core | 6, 8, 26 | `scripts/studio.py`, `skills/studio/SKILL.md` |
| 1 | **W1-HOOKS** hooks + selftest runner | 1, 2 | `hooks/hooks.json`, `scripts/hooks.py`, `scripts/selftest.py` |
| 1 | **W1-BALANCE** | 3, 4, 17, 9 (balance part) | `scripts/balance.py`, `skills/balance/SKILL.md`, `skills/balance/model-template.py` |
| 1 | **W1-SHIP** | 5, 12, 14, 21, 22 | `scripts/ship.py`, `skills/ship/SKILL.md` |
| 1 | **W1-ART** | 11 | `scripts/art.py`, `skills/art/SKILL.md`, `skills/art/bible-template.md` |
| 1 | **W1-PLAYTEST** bots, Godot, adapters | 7, 9 (harness part), 10 | `scripts/playtest.py`, `scripts/probe.gd`, `skills/playtest/SKILL.md`, `skills/playtest/adapters.md`, `examples/dodge-godot/main.gd`, `examples/dodge-godot/README.md` |
| 2 | **W2-AGENT** agent, personas, sheet + survey | 15, 16, 13 | `scripts/playtest.py`, `skills/playtest/SKILL.md` |
| 2 | **W2-TELEMETRY** | 18 | `scripts/telemetry.py` |
| 2 | **W2-BUILD-ITERATE** | 23, 24 | `skills/build/SKILL.md`, `skills/iterate/SKILL.md` |
| 2 | **W2-HUMAN** log, feedback, postmortem | 25, 19, 20 | `skills/log/SKILL.md`, `skills/feedback/SKILL.md`, `skills/postmortem/SKILL.md`, `skills/playtest/sheet-template.md` |
| 2 | **W2-WIRING** design skill, manifests, skill lint | 26 (design skill, lint) | `skills/design/SKILL.md`, `skills/design/design-template.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `scripts/selftest.py` |
| 3 | docs pass (not in this plan) | - | `README.md`, `docs/reference.md`, `docs/implementation-notes.md` |

Within a wave, file ownership is disjoint. Wave 2 builds on wave 1 (`script:` bots, `LOOP`, the art bible contract). Each package's full instructions live in the workflow output; the contracts below are shared by all of them.

## Contracts

### C1. `studio.py status` additions (W1-STUDIO defines, everyone reads)
| Key | Value |
|---|---|
| `LOOP` | one of `design build test balance iterate log ship` |
| `LOOPMAP` | `design > build > [test] > balance > iterate > log > ship` (current loop in brackets) |
| `AUTO_PLAYTEST` | `on` or `off` (`studio.json` `"auto_playtest": false` turns it off; default on) |
| `ITERATION` | `<n> <YYYY-MM-DD>` of the highest `design/iterations/<n>.md`, or `none` |
| `SINCE_ITERATION` | `playtests:<a> human:<b> feedback:<c> balance:<d> telemetry:<e>`: files whose `YYYY-MM-DD` name prefix is after the ITERATION date, or on it when the iteration record doesn't name the file (all files when `none`) in `playtests/*.json`, `playtests/*-human.md`, `feedback/*.md`, `balance/*.md`, `telemetry/*-report.md` |
| `RUN` | as before, or a double-quoted absolute interpreter path when the venv fallback is used |
| `VENV` | printed only when the venv fallback is suggested or used: its directory |

`LOOP` is derived, first match wins (no stored counters):
1. `INIT=no` or no `design/design.md`: `design`.
2. `STAGE=shipped`: `ship` (NEXT also offers `/playbench:postmortem`).
3. `DEBT_QUICK` has WARN: `test`. The newest `playtests/*-quick.json` has verdict FAIL: `build` (NEXT: fix the FAIL, then rerun quick).
4. A mode in `REQUIRED` has no report yet: `test`.
5. `DEBT_HUMAN` has WARN, or there is no `playtests/*-human.md` at all and an `UNTICKED` box mentions "human": `log`.
6. `SINCE_ITERATION` has `human` + `feedback` >= 1: `iterate`.
7. `BALANCE=on`, the `## Knobs` table has a data row, `balance/` has no results, and the stage is not the profile's first stage: `balance`.
8. The stage is the profile's last stage: `ship`.
9. Otherwise `build`.

`NEXT` names the skill for `LOOP`: design `/playbench:design`, build `/playbench:build`, test `/playbench:playtest`, balance `/playbench:balance`, iterate `/playbench:iterate`, log `/playbench:log`, ship `/playbench:ship`. Under `AI_POLICY=banned` the build NEXT says the student writes the feature and runs a T0 quick playtest.

### C2. State files added this round (in the game repo)
| Path | Written by | Format |
|---|---|---|
| `art/bible.md` | art skill (human approves) | see C6 |
| `design/build-log.md` | build skill | one line per slice: `- <YYYY-MM-DD> <slice> (must: <item>) quick: <verdict> <report file>` |
| `design/journal.md` | log skill | `## <YYYY-MM-DD>` entries of dev notes |
| `design/iterations/<n>.md` | iterate skill | first line `# Iteration <n> (<YYYY-MM-DD>)`, then evidence, ranked changes, what the user picked |
| `design/postmortem.md` | postmortem skill | went right / went wrong / numbers / next time |
| `playtests/<YYYY-MM-DD>-<HHMM>-human.md` | log skill | structured human session; matches the existing `*-human.md` debt glob |
| `playtests/<stamp>-sheet.md`, `playtests/<stamp>-survey.md` | `playtest.py sheet` / `survey` | printable sheet; survey markdown + Google-Forms paste block |
| `playtests/agent/<name>.json` | agent loop | scripted inputs (commit it: it replays) |
| `playtests/shots/agent-<NN>.png`, `.json` | `playtest.py agent` | decision point screenshot and state (gitignored with shots/) |
| `balance/<YYYY-MM-DD-HHMM>-<costcurve\|sim\|matrix>.md`, `balance/model.py` | balance.py `--out balance`; user model from the template | reports |
| `feedback/<YYYY-MM-DD>-<source>.md` | feedback skill | ranked, deduped issues |
| `telemetry/*.jsonl`, `telemetry/<YYYY-MM-DD-HHMM>-report.md` | game snippet; `telemetry.py report` | events (C9) and their aggregate |
| `store/itch-theme.md`, `store/itch-theme.html`, `store/itch-custom.css` (optional) | `ship.py theme` | itch page theme |
| `netlify.toml` | `ship.py web --host netlify` (only if absent) | `[build] publish = "<build_dir>"` |

`ship.py` keeps `feedback/`, `telemetry/`, `art/bible.md` and `*.ase`/`*.aseprite` out of uploads when `build_dir` is the game root (`design/` is already excluded).

### C3. Skill shape
- Frontmatter `name`, `description` (when to use, in words users say), `allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Read, Write, Edit, Glob, Grep` (postmortem may add `Bash(git log:*)`).
- The first body line is the existing dynamic-context line:
  `` !`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playbench: no working Python 3 found"` ``
- Under about 120 lines. One question at a time, each with a default. Word by `CODING` (1 plain, 2 write + review, 3 explain + review). Respect `AI_POLICY=banned` / `ALLOWED`. Never write `[x]` into `gates.md`.
- The last section is exactly `## Next loop`, telling Claude to end with one line `Next loop: <loop> (/playbench:<skill>)`, with this skill's default next loop, and to use `LOOP`/`NEXT` from a fresh `status` when unsure.

### C4. Bots and agent (W1-PLAYTEST, W2-AGENT)
- `--bot idle|random|policy|mash|script:<path.json>`. `mash`: every 100 ms step, hold a fresh random subset (seeded by the run seed) of all actions including start keys. `script`: a JSON list `[{"t": 0.0, "keys": ["ArrowRight"]}, {"t": 1.5, "keys": []}]`, sorted by `t`, each entry held from its `t` until the next; after the last entry the last keys stay held. `runs[].bot` records the name as given. Godot supports both (probe.gd args `bot=mash`, `bot=script script=<abs path>`).
- `playtest.py agent <build> --script <path.json> [--seed 1] [--seconds 60] [--then pause|idle|random|policy] [--out playtests]` (web only). Plays the script, then the `--then` bot (default `pause`: stop as soon as the script ends). It pauses at the first decision point after the script's last `t`: the state has a non-empty `choices` list or `decision: true`; the state hash is unchanged for 2 s while keys are held and the game is neither over nor paused; a page error; or the script ended under `pause`. On a pause it writes `<out>/shots/agent-<NN>.png` and `agent-<NN>.json` = `{"t", "reason", "state", "actions", "script", "seed"}`, prints `DECISION=<json path>` and exits 3. When the run ends (over or time up) it prints `AGENT_DONE over=<bool> won=<bool> t=<s>` and exits 0. Claude appends entries with `t` >= the decision `t` and reruns; the fake clock makes the replay identical.

### C5. Godot (W1-PLAYTEST; balance only passes overrides)
- Overrides become user args after `--`: `--<name>=<value>` (file overrides too, by knob name). probe.gd collects every `--name=value` arg into a `knobs` Dictionary and calls `probe_knobs(knobs)` on the scene root **before** `add_child`, so `_ready` sees them.
- `playtest.py run ... --windowed` (Godot only) drops `--headless` and passes `shots=<tmp dir>`; probe.gd saves the viewport image every 60 frames as `<dir>/<frame>.png` and prints `PROBE_SHOT <path>`; the harness hashes them into the T0 frozen and dead-input checks.
- Godot stays labelled EXPERIMENTAL / unverified everywhere.

### C6. Art bible (`art/bible.md`, W1-ART writes, W1-SHIP reads)
```
# Art bible: <game>
## Palette
- bg: #1b1b2f
- text: #f5f5f5
- link: #ffcc00
- button: #e94560
- <other name>: #rrggbb
## Fonts
- heading: <Google font name>
- body: <Google font name>
## Pixel density
- tile: 16
- scale: 3
## Proportions
- <one line per rule, e.g. hero: 1 tile wide, 1.5 tiles tall>
## Animations
| sprite | anim | frames | fps |
|---|---|---|---|
| hero | run | 4 | 10 |
```
Roles `bg`, `text`, `link`, `button` are required; parsers match `- <name>: #rrggbb` lines under `## Palette` case-insensitively and ignore everything else.

### C7. Stub helper (copy into each selftest that needs one; no shared module)
```python
def stub(dirpath, name, body):
    """Fake executable `name` in dirpath that runs python source `body` with this interpreter."""
    py = dirpath / f"{name}_stub.py"
    py.write_text(body, "utf-8")
    if os.name == "nt":
        exe = dirpath / f"{name}.cmd"
        exe.write_text(f'@"{sys.executable}" "{py}" %*\n', "utf-8")
    else:
        exe = dirpath / name
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{py}" "$@"\n', "utf-8")
        exe.chmod(0o755)
    return exe
```
Scripts resolve binaries through one module-level resolver (`shutil.which` or an env var such as `GODOT`, `ASEPRITE`) and run the resolved path, never a bare name (Windows `CreateProcess` ignores `PATHEXT`). Selftests swap that resolver to return only the stub, and restore it in `finally`.

### C8. New CLI surface
| Command | Package |
|---|---|
| `studio.py aiuse [dir] [--md]` | W1-STUDIO |
| `hooks.py gates` / `hooks.py stop` / `hooks.py selftest` (stdin: hook JSON) | W1-HOOKS |
| `balance.py costcurve <csv> [--cost COL] [--benefit a,b] [--out balance]`, `balance.py sim <model.py> [--runs N] [--seed S] [--knob k=v]... [--out balance]`, `balance.py matrix <csv> [--out balance]` | W1-BALANCE |
| `ship.py steam` (+ library assets), `ship.py theme [--css]`, `ship.py web [--host pages\|netlify] [--real]`, `ship.py demo`, `ship.py itch\|steam --real` | W1-SHIP |
| `art.py placeholder\|placeholders\|pack\|aseprite\|lint\|selftest` | W1-ART |
| `playtest.py run --bot mash\|script:<f> [--windowed]` | W1-PLAYTEST |
| `playtest.py agent ...`, `playtest.py sheet <game> [--out playtests]`, `playtest.py survey <game> [--out playtests]` | W2-AGENT |
| `telemetry.py snippet web\|godot`, `telemetry.py report <file\|dir>... [--out telemetry]` | W2-TELEMETRY |

### C9. Telemetry events
JSON lines: `{"ts": <ms since epoch>, "session": "<id>", "event": "start|level|death|win|quit|<custom>", "level": <name or number, optional>, ...}`. Local only: the web snippet keeps them in `localStorage` and exports `telemetry.jsonl` on demand; the Godot snippet appends to `user://telemetry.jsonl`. Nothing is sent over the network.

### C10. Hooks
`hooks/hooks.json` commands use `python "${CLAUDE_PLUGIN_ROOT}/scripts/hooks.py" <cmd> || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/hooks.py" <cmd> || true`, with a 10 s timeout. `hooks.py` always exits 0 and expresses decisions as JSON on stdout (PreToolUse `hookSpecificOutput.permissionDecision: "deny"`; Stop `{"decision": "block", "reason": ...}`), so the `||` chain falls through only when an interpreter is missing (the Windows Store `python` stub exits non-zero without reading stdin).

## Definition of done (after wave 2, before the docs pass)
1. `python scripts/selftest.py` prints `ok selftest` on this machine; Godot, Aseprite, butler, steamcmd and netlify real-binary steps print SKIP, and their stub steps print ok.
2. `claude plugin validate . --strict` and `claude plugin validate .claude-plugin/plugin.json --strict` pass (or SKIP if `claude` is missing).
3. On a temp copy of `examples/dodge-web` inside a temp git repo: `status` prints every C1 key; the PreToolUse hook denies an Edit that ticks a `gates.md` box; the Stop hook blocks once when debt is over the limit and stays quiet with `stop_hook_active` or `"auto_playtest": false`.
4. Every `skills/*/SKILL.md` has the dynamic-context line and ends with `## Next loop`; none contains `- [x]`.
5. No binary was downloaded, nothing was installed, no upload ran, nothing was committed.
