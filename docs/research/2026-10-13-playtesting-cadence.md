# Playtesting Cadence: Research Notes (2026-10-13)

**Verdict: playtest continuously, not only at the end.** Valve (GDC 2009): "Get data early, get data often. Iterate constantly." Fullerton's playcentric method: test with target players through every phase. The common indie failure is waiting until the game feels "ready", by which point features sit on a flawed core loop.

## Cadence by phase
| Phase | Cadence | What the tests check |
|---|---|---|
| Prototype | Self-test after every change; friends several times a week | Is the core loop fun (Supercell kills games that aren't fun enough) |
| Vertical slice | One internal round per hook (Riot's champion rounds) | Hook, play pattern, clarity |
| Production | Internal builds plus fresh testers at milestones | First-time experience (FTUE), comprehension, difficulty |
| Alpha / beta | Closed playtests, more testers | Bugs, balance, performance (Steam Playtest = separate app ID) |
| Early access / post-launch | Weekly to every few months, plus telemetry | Balance, game feel, quality of life (Hades, Slay the Spire) |

## Tester types
Self · internal team · friends (too encouraging) · kleenex (one-time, fresh) testers (the only true read on FTUE; pair them with repeat testers) · Discord / r/playmygame / itch · Steam Playtest / demos · early access · telemetry.

## Indie examples
- **Slay the Spire:** daily builds to a tester Slack, a bot logging bugs/feedback/ideas (about 2,800 items), and a metrics server for win and pick rates.
- **Celeste:** friends played chapters before there was any art; hot-reloading let levels change mid-session.
- **Balatro:** demos plus a feedback Discord shaped the game.
- **Vampire Survivors:** itch build first, then early access with small, frequent patches.

## Automated / AI playtesting today
- **King:** imitation-learning bots predict level difficulty (95% fewer manual tweaks).
- **EA SEED:** RL agents in regression testing and map coverage.
- **modl.ai:** screen-based QA bots in CI.
- **Unity ML-Agents:** toolkit only; you build and train the agents yourself.
- **Limits:** bots handle regressions, crashes, reachability, difficulty and balance estimates. They **cannot** judge fun, confusion or emotion. AI playtesting adds to human testing; it does not replace it.

## Recommendation for the plugin
1. **Per feature (minutes):** AI checks (build, smoke/regression bots, sims) plus a 2–3 question self-test tied to the feature's experience goal. Log the results.
2. **Per iteration:** friend or team session with a generated observation sheet and a short survey.
3. **Milestone gates** (prototype / slice / alpha / beta): kleenex plus repeat testers, with a protocol generated from the GDD experience goals. Each goal is marked met or waived.
4. **Final / early access:** Steam Playtest or demo checklist, feedback-intake bot, telemetry, beta branch.
5. **Playtest debt counter:** warn when N features have shipped without a human test.

## Sources
- https://cdn.fastly.steamstatic.com/apps/valve/2009/GDC2009_ValvesApproachToPlaytesting.pdf
- https://gamedeveloper.com/design/book-excerpt-game-design-workshop
- https://seattleindies.org/seattle-indies-spotlight-mega-crit-games/
- https://www.infoq.com/articles/candy-crush-qa-ai-saga/
- https://www.ea.com/seed/news/seed-ml-research-aaa-game-testing
- https://partner.steamgames.com/doc/store/testing
- https://gamedeveloper.com/design/overcoming-struggles-in-playtesting
- https://gtstu.com/playtest-indie-game-solo-developer/
