# Unity WebGL verification

**Result: playbench works end to end on a real Unity 6 WebGL build, at tier 2 under `page.clock`.** On the clean build, quick mode PASSes with stats. All three planted bugs FAIL as they should, overrides change the outcome, and tiers 0 and 1 are detected. Tested 2026-10-13 on Windows 11 with Python 3.11.0, Playwright Chromium (headless, SwiftShader) and `examples/dodge-unity`.

## Setup
- **Unity:** 6000.2.8f1 with WebGL support. It uses the legacy Input Manager (`activeInputHandler: 0`, the default for a new project). The package manifest is trimmed to `imgui` and `unitywebrequest`.
- **Game:** `Assets/Scripts/Dodge.cs` boots itself through `RuntimeInitializeOnLoadMethod` (the scene is empty), draws with IMGUI and reads `StreamingAssets/enemies.csv` with `UnityWebRequest`. Every frame it pushes `{over, won, paused, score, px, enemies:[[x,y]...]}` to JS.
- **Probe:** `Assets/Plugins/PlaybenchProbe.jslib`.
  - A `$PB__postset` defines `window.__game` when `framework.js` evaluates, before the first C# frame.
  - `state()` returns `{over:false, paused:true}` until C# pushes its first state, so the harness never reads `null` at boot. A `null` read would fix the tier at 0.
  - The seed and the `enemy_speed` knob come from `window.__playbench` (`PB_Seed`, `PB_Override`). The seed goes to `UnityEngine.Random.InitState`. The harness's seeded `Math.random` does **not** reach C#.
  - The bot returns `['Enter']` while the state is paused or over.
- **Build:** `Assets/Editor/BuildWebGL.cs` sets compression Disabled, decompression fallback off, data caching off and a 480x320 canvas.

## Commands and timings
| Step | Command | Wall time | Result |
|---|---|---|---|
| Create project | `Unity.exe -batchmode -nographics -quit -createProject examples\dodge-unity -logFile create.log` | 51 s | exit 0 |
| Build | `Unity.exe -batchmode -nographics -quit -projectPath examples\dodge-unity -buildTarget WebGL -executeMethod BuildWebGL.Build -logFile build.log` | 203 s (Unity reports 3:09) | `PLAYBENCH BUILD Succeeded in 00:03:09.38 (21365027 bytes)` on the first try. `Build.wasm` is 11.9 MB and `Build.data` is 3.8 MB |
| Quick playtest | `python scripts/playtest.py run examples/dodge-unity/Build --mode quick --seeds 3 --seconds 30 --out <scratch>` | 97-118 s | PASS, tier 2 |

The log also shows a licensing warning (`[Licensing::Module] Error: Access token is unavailable`). It does not affect the build.

## Playtest output (real)
```
PASS: boots, input works, no crashes, freezes or softlocks in 6 runs (tier 2)
`examples/dodge-unity/Build` | quick | web | tier 2
No findings.
relative difficulty under policy bot: 3 runs, win rate 0.67, time to over p10/p50/p90 10.36/20.6/20.6 s, deaths/min 1.22
```
The runs are real gameplay. Random runs die at 4.0, 5.1 and 10.3 s. The policy bot wins seeds 1 and 2 at 20.6 s and dies on seed 3. The screenshots show the rendered game.

| Run | Result |
|---|---|
| `?bug=crash` (C# `throw` in `Update`) | **FAIL**: `softlock at 5.6s ... state unchanged 5s`, plus WARN `console_error InvalidOperationException: planted crash at Dodge.Update ()` |
| `?bug=jscrash` (JS throw from a jslib call) | **FAIL**: `crash at 5.5s (seed 1, random): planted js crash`, plus WARN console errors `Uncaught exception from main loop:` and `Halting program.` |
| `?bug=softlock` | **FAIL**: `softlock at 8.6s` |
| `?noprobe` / `?nobot` | PASS at tier 0 / tier 1 |
| `--mode sweep --seeds 2 --seconds 20` | Baseline: no deaths. `--override enemy_speed=3`: p50 19.4 s, 1.52 deaths/min. `--override StreamingAssets/enemies.csv:bat.speed=6`: p50 10.5 s, 1.97 deaths/min |
| `--realtime` quick | WARN `nondeterministic` (expected in real time, so the dead-input check is skipped), tier 2, win rate 0.33. 107 s |

## What worked
- **`page.clock`:** Unity's main loop (emscripten `requestAnimationFrame`) and `Time.deltaTime` follow the faked clock. The idle replay matched, so the dead-input check ran ("input works").
  - Determinism is good but not perfect. Five of six runs replayed byte-identical across invocations.
  - Seed 3 under the policy bot drifted: it ended at 7.8 s in one invocation and at 13.1 or 13.2 s in later ones. 13.1 s repeated 3 of 4 times in one session.
  - The likely cause is real-time async work (the wasm instantiate, the `UnityWebRequest` completion) landing on a different faked frame. `--realtime` is not needed.
- **Boot timing:** the `networkidle` wait covers the wasm and data download. Unity was running before the harness's start press, at 1.5 s of faked time after the canvas appeared. The game unpauses at t=0.6 s in every run, after the CSV loads.
- **Canvas:** the canvas id is `unity-canvas`. The harness's `canvas` selector, click and screenshots all work, and WebGL renders under SwiftShader.
- **Keyboard:** no focus problems. Unity's legacy Input receives Playwright's `keyboard.down/up` with no extra focus step.
- **Overrides:** file overrides use the build-relative path `StreamingAssets/<file>`, and `page.route` intercepts the `UnityWebRequest` fetch. The data cache is disabled in the build.

## What failed or is fragile
1. **C# exceptions are only a WARN.** Unity catches managed exceptions and logs them through `console.error`, so they never reach `pageerror`. Here the FAIL came only from the softlock detector, because the exception aborted the state push. An exception in any other script would report only `console_error WARN`, and the verdict would be WARN.
2. **Multi-line console errors break the Markdown table.** Unity's console messages include stack traces with newlines (see `?bug=crash`).
3. **Screenshot names collide.** Two FAIL findings of the same kind and seed from different bots write the same `shots/<stamp>-<kind>-s<seed>.png`, and the second overwrites the first.
4. **The start press races the engine.** The canvas exists in Unity's `index.html` before the engine runs. The harness presses Enter after only 0.5 s + 1 s of faked time. That was enough here (21 MB build), but a larger build, or a slower machine where compiling the wasm outlasts `networkidle`, would miss the press.
   - The random bot never sends Enter, so every random run would stay on the title screen.
   - The dead-input replay would then see hold == idle and report a false `dead_input FAIL`.
   - The policy-bot workaround (`['Enter']` while paused) only covers T2.
5. **The `nondeterministic` hint is wrong under `--realtime`.** The message says "try --realtime" even when the run is already in real time.
6. **Quick mode takes longer than the docs say.** 3 seeds x 30 s took 97-118 s, against the "about a minute" in `docs/reference.md`. Two idle replays, two hold replays and 3x2 main runs, each a new page that reloads 15 MB of wasm and data.

## Recommended harness and doc changes (not applied; outside this folder)
- **`scripts/playtest.py`, `detect()` (failure 1):** promote Unity managed exceptions to a crash FAIL. Treat a console message as a crash when it matches `re.match(r"^[\w.]+Exception: ", m) and "\n  at " in m`, or contains `Uncaught exception from main loop` or `Halting program`. Record it as `add("crash", "FAIL", r, None, m.splitlines()[0])` instead of `console_error`.
- **`scripts/playtest.py`, `detect()` (failure 2):** use the first line only for `console_error` detail, `m.splitlines()[0][:200]` instead of `m[:200]`. Alternatively, `to_md()` can replace `\n` with a space in `detail`.
- **`scripts/playtest.py`, `write_reports()` (failure 3):** include the bot in the shot name: `f"shots/{stamp}-{f['kind']}-s{f['seed']}-{f['bot']}.png"`.
- **`scripts/playtest.py`, `web_session.play()` (failure 4), after the canvas wait:**
  1. Wait for readiness: keep `adv(500)` until `window.__playbench.read()` is non-null and the canvas screenshot has changed once, with a cap of about 20 s. Unity's template also exposes readiness: the `#unity-loading-bar` is hidden after `createUnityInstance` resolves.
  2. After the Enter/Space press, if the state is still `paused` after `adv(1000)`, press Enter again up to 3 times.
- **`scripts/playtest.py`, `detect()` (failure 5):** when the run is real time, drop "try --realtime" from the `nondeterministic` message. Pass `realtime` into `detect()`, or have `run()` skip the second idle replay under real time.
- **`docs/reference.md`, Probe contract, "Unity WebGL" paragraph:**
  - Expose `window.__game` from a `.jslib`, defined in a `$X__postset` so it exists before the first frame.
  - Return `{paused:true}` until the first C# state.
  - The seeded `Math.random` does not affect C#: read `window.__playbench.seed` and the overrides through jslib functions.
  - Build with compression Disabled. The harness server sends no `Content-Encoding`, so a Gzip or Brotli build needs the decompression fallback. This is untested here.
  - File overrides use `StreamingAssets/<file>`.
  - Unity logs C# exceptions as console errors, not page errors.
- **`docs/reference.md`, jam quickstart:** say "about 1-2 minutes" for quick mode, or note that wasm builds take longer.
- **README:** Unity WebGL is now verified, not just listed. The `examples/dodge-unity` sample can be linked.
