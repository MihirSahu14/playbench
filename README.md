<div align="center">

# playbench

**Bots playtest your game after every feature. You stay in charge of the fun.**

A Claude Code plugin for game developers: design, playtest, balance, ship.

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-d97757)
![Engines](https://img.shields.io/badge/works%20with-any%20HTML5%20export-blue)

<img src="docs/assets/demo.gif" width="720" alt="A playbench bot playing the Dodge sample game while checks pass live">

<sub>A playbench bot playing the real build of the sample game. No human hands.</sub>

</div>

---

## Why

Most indie games die the same way: a bug from hour 2 gets found at hour 40, nobody playtests until it "feels ready", and the release goes out with placeholder art still in it.

playbench catches each of those early:

- 🤖 **After every feature**, bots play your real build and catch crashes, freezes, softlocks and dead controls.
- 📊 **Balance on the real game.** It sweeps a value such as enemy speed and shows you where the difficulty falls off a cliff.
- 🚦 **Ship with gates.** Undisclosed AI or placeholder art is blocked, and nothing uploads until *you* tick the release gates.

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/flow-dark.svg">
  <img src="docs/assets/flow-light.svg" width="100%" alt="Design, build, bot playtest (FAIL loops back to build), balance, human playtest, ship once you tick the gates">
</picture>

## See it work

<img src="docs/assets/showcase.png" width="100%" alt="Four steps: ask what's next, bots playtest every feature, balance on the real build, ship only when you say so">

<sub>Every screen above is real output from the bundled <code>examples/dodge-web</code> game.</sub>

## Install

Run these in Claude Code:

```
/plugin marketplace add MihirSahu14/playbench
/plugin install playbench@playbench
```

Requires Python 3.11 or newer. For browser playtests you also need Playwright; playbench prints the exact install line when you first need it.

## Try it in 60 seconds

Open Claude Code in your game folder and just talk:

1. **"Set up playbench for a jam."** A few quick questions: what kind of project, how much you code, engine, deadline.
2. **"Let's design it."** You get a hook, a core loop and a must/cut list on one page.
3. **"Playtest it."** after each feature.
4. **"Ship to itch."** when you're ready.

## Made for

| You are… | playbench gives you… |
|---|---|
| 🏃 **Game-jammer** | A deadline countdown, a one-minute playtest after each feature, and an itch zip that's been boot-checked |
| 🌙 **Solo hobbyist** | Scope that fits your hours, and a nudge when you've gone too long without testing |
| 👥 **Small team** | Gate owners, playtest regressions between runs, Steam build config, and who-approved-what from git |
| 🎨 **Designer who codes a little** | Claude writes the test hooks and bots; you tune numbers in data files |
| 🎓 **Student** | A course AI policy (open, disclose or banned) and an honest record of AI use |

**Engines:** any HTML5 export (plain JS, Phaser, Godot web, Unity WebGL, GameMaker, Construct, GDevelop). Godot native is experimental.

## What bots can't do

Bots find what's broken. They can't tell you whether the game is **fun**. playbench asks for a human playtest before every gate, and only humans tick gates.

## Learn more

- [Reference](docs/reference.md): commands, the probe contract (how bots read your game), the AI-art policy, state files
- [Design spec and roadmap](docs/superpowers/specs/2026-10-13-playbench-design.md)
- **Coming next:** auto-playtest hooks, balance for bundled data and Godot, a sprite pipeline, itch page themes

## Contributing

Issues and PRs are welcome. Run `python scripts/selftest.py` before opening a PR; it should print `ok selftest`.

## License

[MIT](LICENSE) © 2026 Mihir Sahu
