---
name: art
description: Use when the user asks about art style, an art bible, a palette or fonts, sprites, animations, a sprite sheet or texture atlas, placeholder art, Aseprite exports, or asset naming.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), Read, Write, Edit, Glob, Grep
---
!`python "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/studio.py" status || echo "playbench: no working Python 3 found"`

# Art: a one-page bible, labelled placeholders, atlases

The status lines above give `RUN`, `PLUGIN`, `CONTEXT`, `CODING`, `AI_POLICY`, `ENGINE` and `ALLOWED`. Use them; don't ask for what they already say. Every command is `<RUN> "<PLUGIN>/scripts/art.py" <cmd> ...`. Exit codes: 0 ok, 1 problems, 2 setup (the message says what to fix).

## Hard rules
- **Humans own final art.** Never present a generated image as final art. Everything art.py draws is a `_placeholder` file recorded in `art/PLACEHOLDERS.json` (`source: "generated"`), with a `playbench=placeholder` PNG text chunk.
- AI image generation, if the user brings one in, only as `art/<name>_placeholder.png` with an entry `{"path": ..., "source": "ai", "note": ...}` in `art/PLACEHOLDERS.json`. Never strip metadata from any image.
- `ship artgate` blocks undisclosed placeholders: each one is replaced with human-made art or disclosed before release.
- **Never tick a gate box.** Never write `[x]` into `gates.md`.
- `AI_POLICY=banned`: explain each step and give the exact command; the student writes the bible and runs the commands. Don't generate images.

## 0. Preconditions
- `RUN=NONE` or the echo fallback: tell the user to install Python 3.11+ and stop.
- Exit 2 with `Pillow not installed for <exe>`: show the printed `pip install pillow` command and **ask before running it**. lint and aseprite don't need Pillow.
- `INIT=no`: carry on in the current folder; suggest `/playbench:studio` once at the end.

Ask one question at a time, each with a default. Skip steps the user doesn't need (a jam may stop after step 3).

## 1. Art bible (`art/bible.md`)
If it exists, read it and edit in place. Otherwise read `design/design.md` (hook and pillars) and draft from `${CLAUDE_SKILL_DIR}/bible-template.md`, keeping its exact shape (`ship.py` parses `## Palette` and `## Fonts`):
1. **Palette.** Offer 2-3 palettes drawn from the hook, each as a hex list with roles, e.g. `A) bg #1b1b2f, text #f5f5f5, link #ffcc00, button #e94560, hero #4fa3ff`. Default: A. `bg`, `text`, `link` and `button` are required; other colors get names (`hero`, `enemy`, `pickup`).
2. **Fonts.** Two Google Fonts: heading and body (default: Press Start 2P / Inter for pixel art, Fredoka / Inter otherwise).
3. **Pixel density.** Tile size and screen scale (default `tile: 16`, `scale: 3`; non-pixel art: `tile: 64`, `scale: 1`).
4. **Proportions.** One line per rule in tiles (default: hero 1 tile, enemies at most 2).

Write the page, then say: "This is your art direction; change anything. You approve it and own the final art."

## 2. Animation list
From the must features in `design/design.md`, propose rows for `## Animations` (`| sprite | anim | frames | fps |`): only what the must list needs (e.g. hero idle 2/4, hero run 4/10, enemy move 2/6, pickup spin 4/8). The user edits; write the table. Names are lowercase snake_case.

## 3. Placeholders
```
<RUN> "<PLUGIN>/scripts/art.py" placeholders .
```
One hatched, outlined sheet per row (frames side by side, frame number as pixels in the top-left), `tile` x `tile` per frame, colors from the palette. A row is skipped when final art `art/<sprite>_<anim>.png` exists. One-off: `placeholder . --name hero --anim run --frames 4 --size 16x16 --color hero`.

Tell the user plainly: these are labelled placeholders, recorded in `art/PLACEHOLDERS.json`; ship's artgate blocks them until each is **replaced** (then remove its entry) or **disclosed** in `disclosure.md`.

Who wires them into the game, by `CODING`: 1 Claude does it and says so; 2 Claude does it and asks for a review; 3 Claude explains and reviews the user's change.

## 4. Atlas for the engine
```
<RUN> "<PLUGIN>/scripts/art.py" pack art --out art/atlas [--padding 2] [--pot]
```
Writes `<out>.png` + `<out>.json` (TexturePacker JSON hash, frames named by file stem). Placeholder inputs rename the output to `*_placeholder` and record it.
- **Phaser:** `this.load.atlas('art', 'art/atlas.png', 'art/atlas.json')`; a single sheet strip also loads with `load.spritesheet(key, url, {frameWidth: <tile>})`.
- **Godot:** import the individual PNGs (or an AtlasTexture region per frame); use `--pot` only if a target needs power-of-two textures.
- Other web engines: any loader that reads TexturePacker JSON hash.

## 5. Aseprite (only if they own it)
```
<RUN> "<PLUGIN>/scripts/art.py" aseprite art/src/hero.aseprite --out art/hero
```
Runs Aseprite in batch mode to a packed sheet + json-hash data with tags. Exit 2 `Aseprite not found`: tell them to set `ASEPRITE=<path to the aseprite executable>`. Never download or install it.

## 6. Lint before ship
```
<RUN> "<PLUGIN>/scripts/art.py" lint .
```
Checks names under `art/`: lowercase `[a-z0-9_]` stems and extensions, no spaces, `_placeholder` only at the end, every placeholder listed and every listed file present, no names that differ only by case (itch's server is case-sensitive), every atlas JSON's image present. Explain each problem line and offer the rename; renames also need the code references updated.

## 7. Store page
`/playbench:ship` theme builds the itch page colors and fonts from this bible's `## Palette` and `## Fonts`, so keep those lines in shape.

## Next loop
End with one line `Next loop: <loop> (/playbench:<skill>)`. Default: `Next loop: build (/playbench:build)`, since the placeholders now need wiring into the game. When unsure, run a fresh `status` and use its `LOOP` and `NEXT`.
