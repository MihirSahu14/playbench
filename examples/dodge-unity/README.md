# dodge-unity

A Unity 6 WebGL twin of `examples/dodge-web`, used to verify playbench on a real Unity build (see `docs/unity-verification.md`). Arrow keys move, Enter or a click starts and restarts, and you win by surviving 20 s. Enemy kinds come from `Assets/StreamingAssets/enemies.csv`.

- `Assets/Scripts/Dodge.cs`: the whole game. It boots itself, so the scene is empty. It draws with IMGUI and uses the legacy Input Manager.
- `Assets/Plugins/PlaybenchProbe.jslib`: the probe. It defines `window.__game` (`state`, `actions`, a greedy `bot`) when the framework loads, and reads `window.__playbench` for the seed and the `enemy_speed` knob.
- `Assets/Editor/BuildWebGL.cs`: an uncompressed WebGL build to `Build/`.

## Build (about 3.5 min)

```
"C:\Program Files\Unity\Hub\Editor\6000.2.8f1\Editor\Unity.exe" -batchmode -nographics -quit ^
  -projectPath examples/dodge-unity -buildTarget WebGL -executeMethod BuildWebGL.Build -logFile build.log
```

When the build succeeds, the log contains `PLAYBENCH BUILD Succeeded`.

## Playtest

```
python scripts/playtest.py run examples/dodge-unity/Build --mode quick --out playtests
python scripts/playtest.py run "examples/dodge-unity/Build?bug=crash" --seeds 1 --seconds 15
python scripts/playtest.py run examples/dodge-unity/Build --mode sweep --override enemy_speed=3
python scripts/playtest.py run examples/dodge-unity/Build --mode sweep --override StreamingAssets/enemies.csv:bat.speed=6
```

These URL switches plant bugs or remove parts of the probe:

| Switch | Effect |
|---|---|
| `?bug=crash` | C# throws in `Update` from 5 s |
| `?bug=jscrash` | JS throws from 5 s |
| `?bug=softlock` | The world freezes at 8 s |
| `?noprobe` | No probe (tier 0) |
| `?nobot` | Probe without a bot (tier 1) |
