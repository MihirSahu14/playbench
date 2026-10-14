# Art bible: <game>
<!-- One page. The human approves it and owns final art; generated sprites are placeholders only. -->

## Palette
<!-- bg, text, link, button are required (ship.py theme reads them). Add named colors as `- name: #rrggbb`. -->
- bg: #1b1b2f
- text: #f5f5f5
- link: #ffcc00
- button: #e94560
- hero: #4fa3ff
- enemy: #8bd450

## Fonts
<!-- Google Fonts names; heading can be a pixel font, body must stay readable. -->
- heading: Press Start 2P
- body: Inter

## Pixel density
<!-- tile = sprite grid in px (placeholders use it); scale = integer upscale on screen. -->
- tile: 16
- scale: 3

## Proportions
<!-- One line per rule, measured in tiles. -->
- hero: 1 tile wide, 1 tile tall
- enemies: never larger than 2 tiles

## Animations
<!-- One row per sprite animation; `art.py placeholders .` draws one sheet per row. -->
| sprite | anim | frames | fps |
|---|---|---|---|
| hero | idle | 2 | 4 |
| hero | run | 4 | 10 |
