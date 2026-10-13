# Market Fit: Research Notes (2026-10-13)

**Verdict:** a full pipeline that only writes documents already exists for free. The opening is in the parts that **run** things: AI playtesting of real builds, balance simulations against real data, and shipping.

## Competitors
| Product | Covers | Gap |
|---|---|---|
| **Claude Code Game Studios** (Donchitos), 26.3k stars (verified) | 49 agents, ~74 skills: brainstorm, GDD, balance-check, art-bible, playtest-report, release/launch checklists; Godot/Unity/Unreal | Mostly writes documents; nothing confirmed to run builds or sims; no itch/Steam tooling. The author's own finding: the 30-docs-before-code tier "ranked last" in blind reviews |
| awesome-gamedev-agent-skills, 1.5k stars | `itch-publish` (butler), `steam-publish` (SteamPipe) | No GDD, balance or playtest skills |
| Unity official Claude plugin (Sep 2026) | 29 engine skills + editor MCP | Engine work only |
| Godot / Unreal / Blender MCP servers | Engine control | Commodity |
| PixelLab, Scenario, Aseprite MCP servers | Sprites | Commodity |
| Ludo.ai (~$20/mo), Machinations | Ideation/GDD; economy sims | Balance model isn't code next to the game's data |
| nunu.ai, modl.ai | AI playtesting | Enterprise only; nothing self-serve for solo devs |
| Astrocade, Rosebud | No-code AI games | Different user (non-coders) |

## Market signals
- Steam: ~19–20.5k releases in 2025; about half get fewer than 10 reviews.
- GMTK Jam 2025: 37k participants, ~9.6k games. A reachable launch channel.
- GDC 2026 survey: 36% of devs use generative AI (brainstorming 81%, code 47%, prototyping 35%). **52% say AI harms the industry**; artists are the most negative (64%).
- AI disclosure is now normal: 30.8% of 2026 Steam releases disclose AI use; itch.io requires AI tags (since Nov 2024).
- Backlash: Indie Game Awards stripped Clair Obscur's awards over AI placeholder textures that shipped.

## Pain points that aren't well served
1. Being found: store page, capsule art, tags, starting marketing too late.
2. Playtesting: no cheap, self-serve way for solo devs to test regularly.
3. Scope and finishing (strong anecdotes; the circulating survey numbers are unverified).

## Positioning
- **Commodity:** ideation/GDD writing, engine dev, sprite generation, butler commands.
- **Differentiated:** (1) AI playtest loop on real builds (web via Playwright, Godot headless); (2) balance-as-code that reads the game's data files; (3) one-command shipping plus an AI-disclosure helper that blocks AI placeholder art from releases.
- **Risks:** prompt-only skills get copied fast, so the value has to live in working scripts; agents can't judge fun; willingness to pay is unproven (open source + a paid hosted runner is the likely model).

## Sources
- https://github.com/Donchitos/Claude-Code-Game-Studios
- https://github.com/gamedev-skills/awesome-gamedev-agent-skills
- https://www.pocketgamer.biz/unity-launches-official-claude-code-plugin-with-29-built-in-engine-skills/
- https://gdconf.com/article/gdc-2026-state-of-the-game-industry-reveals-impact-of-layoffs-generative-ai-and-more/
- https://howtomarketagame.com/2026/01/08/how-many-games-were-released-in-2025/
- https://gamemakerstoolkit.com/jam
- https://80.lv/articles/asset-creators-on-itch-io-now-have-to-disclose-the-use-of-generative-ai/
- https://www.techloy.com/indie-game-awards-disqualify-clair-obscur-expedition-33-after-undisclosed-use-of-generative-ai/
- https://nunu.ai
- https://ludo.ai/pricing
