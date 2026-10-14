---
name: ship
description: Use when the user wants to release, upload, publish, or submit a game to itch.io, Steam, GitHub Pages or Netlify, check AI-art disclosure, prepare store or library assets, theme an itch page, plan a Steam demo, Playtest or Next Fest, or audit release gates.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Read, Write, Edit, Glob, Grep
---
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playbench: no working Python 3 found"`

# Ship: release checks, printed (or gated) upload commands

The status lines above give `RUN`, `PLUGIN`, `CONTEXT`, `CODING`, `AI_POLICY`, `PLATFORMS`, `STAGE`, `UNTICKED:` and `ALLOWED`. Use them; don't ask for what they already say. Every command is `<RUN> "<PLUGIN>/scripts/ship.py" <cmd> . [flags]`. Exit codes: 0 pass, 1 blocked, 2 setup problem (the message says what to fix).

## Hard rules
- **Never tick a gate box.** Never write `[x]` into `gates.md`, even if asked. Humans tick and commit their own boxes; `ship gate` shows who did.
- **Never run butler, steamcmd or netlify yourself**, and never run any `--real` command on your own. Only when the user explicitly asks in chat for this specific release may you run `--real`, and even then prefer handing them the command to run in their own terminal (steamcmd may prompt for a password or Steam Guard code).
- ship.py never runs `git push`. GitHub Pages steps are always printed for the user to run.

## 0. Preconditions
- `RUN=NONE` or the echo fallback: tell the user to install Python 3.11+ and stop.
- `AI_POLICY=banned`: only `artgate` is allowed here (see `ALLOWED`). Run it if asked. For gate, itch, steam and web, explain what each checks and give the exact command so the student runs it.
- `INIT=no`: the commands still work with defaults, but suggest the studio skill's init first so `gates.md` exists.

## 1. Order
Run these in order and explain each result before the next:
1. `artgate`: undisclosed placeholder/AI art.
2. `gate`: who ticked the current stage's boxes.
3. One command per entry in `PLATFORMS`: `itch`, `steam` and/or `web`. Optional extras: `theme` (itch page), `demo` (Steam Playtest / Next Fest).

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

**itch page theme:** `ship.py theme . [--css]` reads the palette and fonts from `art/bible.md` (written by `/playbench:art`; exit 2 says so if it's missing, or names a missing `bg`/`text`/`link`/`button` color). It writes `store/itch-theme.md` (the **Edit theme** values to enter, with WCAG contrast; `WARN` under 4.5:1 means hard-to-read text, suggest a lighter or darker color) and `store/itch-theme.html`, an offline preview to open in a browser. `--css` also writes `store/itch-custom.css`: optional, and only usable once itch support enables custom CSS for the account. Also: embed viewport = canvas size, fullscreen button on, scrollbars off; 3-5 screenshots and a GIF; controls in the first lines of the description.

## 5. Steam (team, or when asked)
`ship.py steam .` needs `"steam": {"appid": ..., "depotid": ...}` in `studio.json` (exit 2 names the missing keys; ask the human for the numbers from Steamworks). It writes `steam/app_build.vdf` with `Preview "1"` and checks store PNG sizes by their header (sizes come from the `STORE` dict in ship.py, as of 2026-10-13):
- `store/header_capsule.png` 920x430, `small_capsule.png` 462x174, `main_capsule.png` 1232x706, `vertical_capsule.png` 748x896
- `store/screenshots/*.png`: at least 5, each at least 1920x1080, 16:9
- library: `library_capsule.png` 600x900, `library_header.png` 920x430, `library_hero.png` 3840x1240, and `library_logo.png` 1280 wide or 720 tall (neither larger) with transparency (RGBA PNG)

Flow: run the printed **preview** steamcmd command first (it uploads nothing). When it's clean and everything passes, hand the user `ship.py steam . --real` to run themselves: it rewrites the vdf with `Preview "0"` and, when `steam.builder` is set and steamcmd is on PATH, **runs the upload** (section 7); otherwise it prints the real command. Then the human sets the build live on a branch in Steamworks.

**Demo / Playtest:** `ship.py demo .` prints the Steam Playtest and Next Fest checklists (dates change: it links the Next Fest page). It reports which of `steam.playtest_appid`, `demo_appid`, `demo_depotid` are set in `studio.json`; with both demo ids it writes `steam/demo_build.vdf` (`Preview "1"`) and prints its preview command. Nothing contacts Steamworks.

## 6. Web
`ship.py web . [--host pages|netlify]` (default: both, dry run) checks `index.html` and root-absolute URLs, boot-checks the build, runs artgate and gate, and prints the steps:
- **pages:** (a) `git subtree push --prefix <build> origin gh-pages`, then Settings > Pages > gh-pages; or (b) copy the build into `docs/` and pick main /docs. The user runs these.
- **netlify:** writes `netlify.toml` (`publish = "<build>"`) only if absent, never overwriting theirs; prints `netlify deploy --dir <build>` for a draft URL, then the `--prod` command when everything passes.

## 7. --real (gated upload)
`itch`, `steam` and `web --host netlify` accept `--real`. It runs the upload only when artgate passes, **every** `## <stage>` in `gates.md` is fully ticked, committed and tracked, and the boot check passes (itch/web). It prints `RAN <cmd>` and `UPLOAD_EXIT=<code>` and exits with the tool's code. Otherwise `Real upload command withheld: <reasons>` (exit 1, nothing ran). If the tool isn't on PATH it prints the command and `<tool> not found on PATH, so nothing ran`. Steam needs `steam.builder` (the Steam build account) in `studio.json` to run; without it the command is printed with `<your_steam_user>`. Remember the hard rule: hand the user the command by default.

## 8. Before the real upload
The release gate needs a final playtest of the packaged build. If there isn't one, offer the `playtest` skill (`run build/itch.zip --mode final`), then tell the human which release box they can tick themselves.

## Next loop
End with one line `Next loop: <loop> (/playbench:<skill>)`. Default after a release: `Next loop: postmortem (/playbench:postmortem)`. If the user keeps running human sessions on the released build: `Next loop: log (/playbench:log)`. When unsure, use `LOOP`/`NEXT` from a fresh `studio.py status`.
