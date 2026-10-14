# dodge-godot (EXPERIMENTAL, unverified)

A Godot 4.3+ port of `examples/dodge-web` for the playbench harness's Godot transport: the same 20-second dodge game, with the enemy table as constants in `main.gd` instead of a CSV, seeded through `probe_seed`, readable through `probe_state` / `probe_actions` / `probe_bot` on the root node, and the planted bugs selected with user args (`godot --path examples/dodge-godot -- bug=softlock` or `-- bug=crash`). Run it with `godot --path examples/dodge-godot` (Enter or Space starts, arrow keys move); the `Web` preset in `export_presets.cfg` exports a non-threaded build to `build/web/index.html`.

| Try | Command (`GODOT` = your Godot 4 editor) |
|---|---|
| Knobs (`probe_knobs`) | `playtest.py run examples/dodge-godot --mode sweep --override player_speed=5 --override bat_speed=3` (each becomes `--name=value` after `--`) |
| Screenshots | `playtest.py run examples/dodge-godot --windowed` (opens a window; frames feed the frozen and dead-input checks) |
| Bots | `--bot mash` or `--bot script:walk.json` (a list of `{"t": seconds, "keys": ["ui_right"]}`) |

It was written without a Godot binary on hand, and playbench's own tests only drive a fake `godot` stub, so treat it as experimental until `godot --headless --path examples/dodge-godot --quit-after 120` has been run with a real Godot 4.3+ binary and shows no `SCRIPT ERROR`.
