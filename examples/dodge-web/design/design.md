# Dodge

## Hook
Twenty seconds. Things fall. Don't get hit.

## Core loop
Watch the sky, slide left or right to dodge falling bats and slimes, survive until the 20-second timer runs out.

## Scope
| feature | must/should/cut | hours |
|---|---|---|
| dodge left/right, lose on first hit, win at 20 s | must | 2 |
| two enemy types from `data/enemies.csv` | must | 1 |
| placeholder hero sprite (`art/hero_placeholder.png`, AI) | should | 0.5 |
| menus, audio, upgrades | cut | - |

Budget: 4 h (must total: 3 h)

## Experience goals
- Tense but readable: every hit should feel like the player's fault.
- A first-time player wins roughly half the time.
- A full run takes under 30 seconds, so "one more try" is cheap.

## Knobs
| name | file | key | min | max |
|---|---|---|---|---|
| bat_speed | data/enemies.csv | bat.speed | 1 | 4 |
| player_speed | - | player_speed | 2 | 6 |
