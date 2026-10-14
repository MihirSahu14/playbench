extends SceneTree
# playbench probe for native Godot 4 (EXPERIMENTAL: unverified until run on a real Godot binary).
# Launched by playtest.py:
#   godot --headless --path <proj> --script probe.gd --fixed-fps 60 --quit-after <n> -- seed=1 bot=random step=6
#         frames=600 hold= [script=<abs .json>] [shots=<dir>] [--<knob>=<value>]...
# bot: idle | random | policy | hold | mash | script. --windowed drops --headless and passes shots=<dir>.
# The main scene's root may define probe_knobs(knobs), probe_state(), probe_seed(seed), probe_actions(), probe_bot(state).
# Prints PROBE_INFO {...} once, PROBE {"t","state","keys"} every `step` frames, PROBE_SHOT <png> every 60 frames
# when shots= is set, then PROBE_END.
# ponytail: if actions don't register headless, switch to Input.action_press/action_release

var args := {}
var knobs := {}
var game  # untyped: probe_* are duck-typed calls on the user's script
var actions: Array = ["ui_left", "ui_right", "ui_up", "ui_down", "ui_accept"]
var steps_script: Array = []  # bot=script: [{"t": s, "keys": [...]}] sorted by t (playtest.py validated it)
var rng := RandomNumberGenerator.new()
var frame := 0
var steps := 0
var held: Array = []


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		var kv: PackedStringArray = a.split("=", true, 1)
		if kv.size() != 2:
			continue
		if a.begins_with("--"):  # a knob override: --name=value, JSON when it parses
			var j := JSON.new()  # JSON.new().parse() stays quiet on failure; the harness treats ERROR: as a crash
			knobs[kv[0].substr(2)] = kv[1]
			if j.parse(kv[1]) == OK:
				knobs[kv[0].substr(2)] = j.data
		else:
			args[kv[0]] = kv[1]
	var seed_value := String(args.get("seed", "1")).to_int()
	rng.seed = seed_value
	if args.get("bot", "") == "script":
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(args.get("script", "")))
		if parsed is Array:
			steps_script = parsed
	game = load(ProjectSettings.get_setting("application/run/main_scene")).instantiate()
	if game.has_method("probe_knobs"):  # before add_child, so _ready already sees the knobs
		game.call("probe_knobs", knobs)
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
	elif bot == "mash":  # a fresh random subset of every action each step, ui_accept included
		want = actions.filter(func(_a): return rng.randf() < 0.5)
	elif bot == "script":  # keys of the last entry with t <= now; the last entry's keys stay held
		for e in steps_script:
			if float(e["t"]) <= frame / 60.0:
				want = Array(e["keys"])
	steps += 1
	_apply(want)
	print("PROBE " + JSON.stringify({"t": frame / 60.0, "state": st, "keys": held}))
	if args.has("shots") and frame % 60 == 0:
		var path := String(args["shots"]).path_join("%d.png" % frame)
		if root.get_texture().get_image().save_png(path) == OK:
			print("PROBE_SHOT " + path)
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
