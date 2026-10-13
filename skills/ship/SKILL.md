---
name: ship
description: Use when the user wants to release, upload, publish, or submit a game to itch.io, Steam or the web, check AI-art disclosure, prepare store assets, or audit release gates.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Read, Write, Edit, Glob, Grep
---
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playloop: no working Python 3 found"`

# Ship: release checks, printed upload commands

The status lines above give `RUN`, `PLUGIN`, `CONTEXT`, `CODING`, `AI_POLICY`, `PLATFORMS`, `STAGE`, `UNTICKED:` and `ALLOWED`. Use them; don't ask for what they already say. Every command is `<RUN> "<PLUGIN>/scripts/ship.py" <cmd> . [flags]`. Exit codes: 0 pass, 1 blocked, 2 setup problem (the message says what to fix).

## Two hard rules
- **Never tick a gate box.** Never write `[x]` into `gates.md`, even if asked. Humans tick and commit their own boxes; `ship gate` shows who did.
- **Never run butler or steamcmd** (or `netlify deploy --prod`). ship.py only prints them. Show the printed command and tell the user to run it in their own terminal.

## 0. Preconditions
- `RUN=NONE` or the echo fallback: tell the user to install Python 3.11+ and stop.
- `AI_POLICY=banned`: only `artgate` is allowed here (see `ALLOWED`). Run it if asked. For gate, itch, steam and web, explain what each checks and give the exact command so the student runs it.
- `INIT=no`: the commands still work with defaults, but suggest the studio skill's init first so `gates.md` exists.

## 1. Order
Run these in order and explain each result before the next:
1. `artgate`: undisclosed placeholder/AI art.
2. `gate`: who ticked the current stage's boxes.
3. One command per entry in `PLATFORMS`: `itch`, `steam` and/or `web`.

By `ENGINE`: itch and web need an HTML5 export as `build_dir` (Godot: the Web export preset; Unity/Unreal: a WebGL export). Native builds go to Steam only.

Steam is hidden for `CONTEXT=jam` and `CONTEXT=learn`: don't offer it unless the user asks. Default target for jam and hobby is itch.

How to explain, by `CODING`:
- 1: one plain line per block ("Blocked: 1 placeholder sprite isn't disclosed. Add this line to disclosure.md: ...").
- 2: the verdict plus the file and line that caused it.
- 3: the verdict, the rule behind it (itch limit, IHDR size, blame sha), and let them fix it.

## 2. artgate (AI and placeholder art)
`ship.py artgate . [--dirs build,store]` scans `build_dir` and `store/`. It flags files listed in `art/PLACEHOLDERS.json`, `_placeholder`/`_ai`/`_wip` filenames, PNG generator metadata (`parameters`, `prompt`, `workflow`, Midjourney/DALL-E/Stable Diffusion/NovelAI/Firefly/ComfyUI, C2PA `caBX`), and C2PA or generator strings in JPEG/WebP headers.

When BLOCKED, the fix is one of:
- **Replace** the file with final human-made art, and remove its `PLACEHOLDERS.json` entry.
- **Disclose** it: the output prints the exact `disclosure.md` lines. The human fills in what each file is (globs work, e.g. `- art/*_placeholder.png: AI placeholder hero sprite`). A line still holding the `<...>` template text does not count. Claude may draft these lines; the human confirms the wording.

On PASS with flags, remind them to also disclose on the store: Steam's Content Survey (AI-generated content) and the itch.io AI-generated tag.

Say plainly: detection is heuristic. Stripped metadata gets through, so it is a safety net for honest users, not enforcement. `store/` is scanned as a policy choice, because Steam's rule for marketing assets isn't verified.

## 3. gate (human sign-off)
`ship.py gate .` audits the last `## <stage>` in `gates.md`. Each ticked box shows author, date and commit from `git blame`.
- `UNTICKED`: list each box and who owns it (in `team`, the `(owner: <name>)` suffix). Tell that person to tick it and commit `gates.md`.
- `WARN uncommitted tick`: the box is ticked but not committed, so nobody can be credited. The human commits `gates.md`.
- `WARN not tracked by git`: the game folder isn't a repo or `gates.md` isn't committed. Suggest `git init` / `git add gates.md` and a commit by the human.

## 4. itch
`ship.py itch .` checks itch's HTML5 limits on `build_dir` (all blocking): `index.html` at the root, at most 1000 files, 500 MB total, 200 MB per file, paths of at most 240 characters, no root-absolute URLs (`src="/x.js"` breaks on itch's sub-path; make it `src="x.js"`), and no file-name case mismatches (itch's server is case-sensitive, Windows isn't). It then writes `build/itch.zip`, boot-checks that zip with a bot, and prints:
- the `butler ... --dry-run` command (and the butler install link if butler isn't on PATH);
- the manual dashboard steps; and for jam a submission checklist;
- `REAL UPLOAD (run it yourself): butler push ...` only when artgate, gate and the boot check all pass. Otherwise `Real upload command withheld: <reasons>`: walk through each reason.

If the boot check is skipped (no playwright), the real command stays withheld. Show the install hint from the output.

**itch page theme** (advice only; nothing is automated): on the game page, **Edit theme** sets background, text and link colors, the banner image and fonts. Custom CSS works only if itch has enabled it for the account. In the embed settings, set the viewport to the game's canvas size, enable the fullscreen button and disable scrollbars. Add 3-5 screenshots and a GIF, and put the controls in the first lines of the description.

## 5. Steam (team, or when asked)
`ship.py steam .` needs `"steam": {"appid": ..., "depotid": ...}` in `studio.json` (exit 2 names the missing keys; ask the human for the numbers from Steamworks). It writes `steam/app_build.vdf` with `Preview "1"` and checks store PNG sizes by their header (sizes come from the `STORE` dict in ship.py, as of 2026-10-13):
- `store/header_capsule.png` 920x430, `small_capsule.png` 462x174, `main_capsule.png` 1232x706, `vertical_capsule.png` 748x896
- `store/screenshots/*.png`: at least 5, each at least 1920x1080, 16:9

Flow: run the printed **preview** steamcmd command first (it uploads nothing). When it's clean and everything passes, `ship.py steam . --real` rewrites the vdf with `Preview "0"` and prints the real command; the human runs it, then sets the build live on a branch in Steamworks. Library assets and Steam Playtest arrive in v1.1.

## 6. Web
`ship.py web .` checks `index.html` and root-absolute URLs, boot-checks the build, runs artgate and gate, and prints the steps:
- **GitHub Pages:** push the repo and set Settings > Pages to main / (root), or `git subtree push --prefix <build> origin gh-pages` and pick the gh-pages branch, or copy the build into `/docs`.
- **Netlify:** `netlify deploy --dir <build>` for a draft URL, then `--prod` (printed only when everything passes).

## 7. Before the real upload
The release gate needs a final playtest of the packaged build. If there isn't one, offer the `playtest` skill (`run build/itch.zip --mode final`), then tell the human which release box they can tick themselves.
