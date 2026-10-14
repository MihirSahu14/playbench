# Engine adapters (web exports)

The harness reads `window.__game` (spec: Probe contract). Export to HTML5, paste one snippet, rerun the quick playtest: tier 0 becomes tier 1. Rename the variables to yours; keep the state small, with no timers in it, and `paused: true` on menus.

## Construct 3
Add a script file (Project bar > Scripts > Add script, purpose: main script) and paste:
```js construct
runOnStartup(async runtime => {
  window.__game = {
    state: () => ({over: runtime.globalVars.GameOver, won: runtime.globalVars.Won,
                   score: runtime.globalVars.Score, paused: runtime.globalVars.Paused}),
    actions: ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", " "],
  };
});
```
`GameOver`, `Won`, `Score` and `Paused` are global variables in the event sheet.

## GDevelop
Add a JavaScript code event at the top of the first scene's events, under a "At the beginning of the scene" condition:
```js gdevelop
const v = runtimeScene.getGame().getVariables();
window.__game = {
  state: () => ({over: v.get('GameOver').getAsBoolean(), score: v.get('Score').getAsNumber(),
                 paused: v.get('Paused').getAsBoolean()}),
  actions: ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", " "],
};
```
`GameOver`, `Score` and `Paused` are global variables (Project manager > Global variables).

## Bot (tier 2)
Add `bot: s => [...keys to hold]` next to `state`: a simple heuristic, e.g. `s => s.x < s.goalX ? ["ArrowRight"] : ["ArrowLeft"]`. Expose the fields it needs in `state`.

## Knobs
A bundled knob reads `(window.__playbench?.overrides ?? {}).<name> ?? <default>`, e.g. at scene start: `runtime.globalVars.PlayerSpeed = (window.__playbench?.overrides ?? {}).player_speed ?? 200;` (Construct) or `v.get('PlayerSpeed').setNumber((window.__playbench?.overrides ?? {}).player_speed ?? 200);` (GDevelop). List it under `## Knobs` in `design/design.md`.

## Others
- **Unity WebGL:** a `.jslib` plugin sets `window.__game`; C# pushes state to it with a `[DllImport]` call each frame.
- **GameMaker (HTML5):** an extension JS file defines `window.__game`; GML updates it through an extension function on each step.
