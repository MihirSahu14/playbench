extends SceneTree
# playloop probe for native Godot 4 (experimental until verified on a real Godot binary).
# Launched by playtest.py:
#   godot --headless --path <proj> --script probe.gd --fixed-fps 60 --quit-after <n> -- seed=1 bot=random step=6 frames=600 hold=
# The main scene's root may define probe_state(), probe_seed(seed), probe_actions() and probe_bot(state).
# Prints PROBE_INFO {...} once, PROBE {"t","state","keys"} every `step` frames, then PROBE_END.
# ponytail: if actions don't register headless, switch to Input.action_press/action_release

var args := {}
var game  # untyped: probe_* are duck-typed calls on the user's script
var actions: Array = ["ui_left", "ui_right", "ui_up", "ui_down", "ui_accept"]
var rng := RandomNumberGenerator.new()
var frame := 0
var steps := 0
var held: Array = []


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		var kv: PackedStringArray = a.split("=", true, 1)
		if kv.size() == 2:
			args[kv[0]] = kv[1]
	var seed_value := String(args.get("seed", "1")).to_int()
	rng.seed = seed_value
	game = load(ProjectSettings.get_setting("application/run/main_scene")).instantiate()
	root.add_child(game)
	if game.has_method("probe_seed"):
		game.call("probe_seed", seed_value)
	if game.has_method("probe_actions"):
		actions = Array(game.call("probe_actions"))
	print("PROBE_INFO " + JSON.stringify({"bot": game.has_method("probe_bot"), "actions": actions}))


func _process(_delta: float) -> bool:
	frame += 1
	var step := String(args.get("step", "6")).to_int()
	var frames := String(args.get("frames", "600")).to_int()
	if frame <= 5:  # start sequence: hold ui_accept for frames 1-4, release on 5
		_apply(["ui_accept"] if frame < 5 else [])
		return false
	if frame % step != 0 and frame < frames:
		return false
	var st: Dictionary = game.call("probe_state") if game.has_method("probe_state") else {}
	var bot: String = args.get("bot", "random")
	var want: Array = []
	if bot == "policy" and game.has_method("probe_bot"):
		want = Array(game.call("probe_bot", st))
	elif bot == "hold":
		want = Array(String(args.get("hold", "")).split(",", false))
	elif bot == "random":
		want = held
		if steps % 3 == 0:  # re-pick every 3 steps (300 ms at step=6): nothing or one non-accept action
			var moves := actions.filter(func(a): return a != "ui_accept")
			var i := rng.randi_range(-1, moves.size() - 1)
			want = [] if i < 0 else [moves[i]]
	steps += 1
	_apply(want)
	print("PROBE " + JSON.stringify({"t": frame / 60.0, "state": st, "keys": held}))
	if st.get("over", false) or frame >= frames:
		print("PROBE_END")
		return true
	return false


func _apply(want: Array) -> void:
	for a in held:
		if not want.has(a):
			_send(a, false)
	for a in want:
		if not held.has(a):
			_send(a, true)
	held = want.duplicate()


func _send(action: String, pressed: bool) -> void:
	var e := InputEventAction.new()
	e.action = action
	e.pressed = pressed
	Input.parse_input_event(e)
