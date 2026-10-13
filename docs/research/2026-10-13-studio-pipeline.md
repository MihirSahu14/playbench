# Game Studio Pipeline: Research Notes (2026-10-13)

Studios disagree on exact phase names and gates. They agree on the order.

## Phases

| Phase | Goal | Deliverables | Exit gate |
|---|---|---|---|
| Ideation | Many cheap ideas | Idea list, one-line hooks, mood boards | One idea with a clear hook + audience |
| Concept | Define what the game is | One-page design (Librande), pillars, core loop, comparable titles | Pillars + core loop agreed |
| Pitch / greenlight | Approval / funding | Pitch deck, scope + budget estimate, risk list | Go / no-go |
| Pre-production | Remove the big risks (fun, tech, art) | Living GDD, tech design doc, art style guide, core-loop prototype, first balance sheets | Prototype proves the loop is fun (Supercell kills most projects here) |
| Vertical slice | Prove final quality is achievable | One polished level, asset cost per minute of content | Content cost known, approved |
| Production | Build all features + content | Milestone builds, asset backlog, playtest reports | All GDD features exist |
| Alpha | Feature complete | Alpha build, bug DB | Playable start to finish, no sev-1 bugs |
| Beta | Content complete, polish | Beta build, crash metrics, store assets | No placeholder art, crash rate below threshold |
| Gold / cert | Release candidate | Gold master, store listing, trailer | Sev-1/2 bugs closed, cert passed |
| Launch | Release (soft launch first on mobile) | Launch build, KPI dashboard | KPIs met |
| Live ops + post-mortem | Retain players + learn | Patches, events, post-mortem | Ongoing |

## Disciplines and their artifacts
- **Design:** pillars, core loop, mechanics/system specs, economy (sources/sinks), progression curves, balance sheets, level docs. Prefer one-page designs over a giant GDD.
- **Narrative:** story bible, characters, dialogue (Ink/Yarn), quest flowcharts.
- **Art:** mood board, style guide (palette, proportions, pixel density), asset tracker, sprite/animation specs.
- **Audio:** SFX list mapped to events, music cue sheet.
- **Engineering:** tech design doc, prototype, data-driven configs, build/CI.
- **QA / playtest:** test plan, bug severities, playtest scripts + surveys, reports.
- **Production:** scope/cut list, milestones, backlog, risk register.
- **UX:** user flows, wireframes, onboarding (FTUE), accessibility checklist.

## Balancing loop
formula → spreadsheet → simulation → playtest → telemetry → adjust data (not code).
- Cost curves: price every effect in one currency and look for outliers (Schreiber & Romero, *Game Balance*, 2021).
- Rock-paper-scissors balance: payoff matrices.
- Spreadsheet sims of economy/loot (GDC Tools Summit spreadsheet microtalks).
- Machinations-style Monte Carlo runs to find deadlocks and runaway economies.
- Explicit tuning knobs per unit (Riot).
- Telemetry: failure heatmaps, win rates per mode (Ubisoft's tools for Assassin's Creed).

## 2D sprite pipeline
style guide → character sheet → animation list (states, frame counts, FPS) → Aseprite with tags/slices → CLI batch export to atlas PNG + JSON (`aseprite -b --sheet-pack --trim`) → engine importer builds clips. Rules: 1–2 px padding, atlas ≤ 2048², one atlas per character or scene, strict naming.

## Where AI helps vs. where humans are needed
**AI:** structured docs (one-pagers, GDD, TDD, pitch, checklists), idea volume + critique with Schell's lenses, balance math + Python sims, prototype code, asset-pipeline scripts + placeholder sprites, dialogue drafts, test + telemetry analysis, backlog/scope planning.
**Human:** judging fun and game feel, final art direction and art, music, real playtesters, greenlight/kill calls, platform cert, community, final say on balance intent.

## Sources
- https://gdcvault.com/play/1012356/One-Page
- https://www.gamedeveloper.com/design/video-one-page-designs
- https://mobilegamer.biz/why-supercell-greenlights-teams-not-games-and-is-now-open-to-external-pitches/
- https://gamesbeat.com/?p=130961
- https://www.routledge.com/9781498799577
- https://gdcvault.com/play/1035550/Tools-Summit-A-Series-of
- https://www.gamedeveloper.com/design/game-telemetry-with-dna-tracking-on-assassin-s-creed
- https://afkgaming.com/esports/news/riot-games-reveals-how-it-validates-gameplay-and-plans-for-champion-releases
- https://www.aseprite.org/cli/
- https://kb.heathen.group/guides/fundamentals/development-phases
