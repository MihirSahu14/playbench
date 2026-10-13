extends Node2D
# dodge-godot: experimental mirror of examples/dodge-web (unverified: written without a Godot binary).
# User args (after --): bug=softlock freezes after 8 s of play, bug=crash makes a SCRIPT ERROR after 5 s.

const W := 480.0
const H := 320.0
const PW := 16.0
const PY := H - PW - 4.0
const PCY := PY + PW / 2.0
const WIN_S := 20.0
const STEP := 1.0 / 60.0 # fixed step, independent of real frame time
const PLAYER_SPEED := 4.0 # px per frame at 60 fps
const KINDS := [ # stands in for dodge-web's data/enemies.csv
	{"id": "bat", "speed": 2.0, "size": 12.0, "spawn_ms": 900.0},
	{"id": "slime", "speed": 1.2, "size": 18.0, "spawn_ms": 1400.0},
]
const REACTION_S := 0.8

var rng := RandomNumberGenerator.new()
var bug := ""
var started := false
var over := false
var won := false
var crashed := false
var play_t := 0.0
var clock_t := 0.0 # sim time since boot, used for the bot's reaction delay
var px := W / 2.0
var enemies: Array = []
var timers := [0.0, 0.0]
var seen: Array = [] # [time, state] pairs for probe_bot


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("bug="):
			bug = a.substr(4)


func probe_seed(value: int) -> void:
	rng.seed = value


func probe_actions() -> Array:
	return ["ui_left", "ui_right", "ui_accept"]


func _physics_process(_delta: float) -> void:
	clock_t += STEP
	if not started and Input.is_action_pressed("ui_accept"):
		started = true
	if started and not over and not crashed:
		_update(STEP)
	queue_redraw()


func _update(dt: float) -> void:
	if bug == "softlock" and play_t >= 8.0:
		return # planted: world freezes, input ignored, never over
	if bug == "crash" and play_t >= 5.0:
		crashed = true # the loop dies after this one error
		var nothing: Variant = null
		nothing.planted_crash() # planted: SCRIPT ERROR (call on a null instance)
		return
	play_t += dt
	var dir := 0.0
	if Input.is_action_pressed("ui_right"):
		dir += 1.0
	if Input.is_action_pressed("ui_left"):
		dir -= 1.0
	px = clampf(px + dir * PLAYER_SPEED * 60.0 * dt, PW / 2.0, W - PW / 2.0)
	for i in KINDS.size():
		var k: Dictionary = KINDS[i]
		timers[i] += dt * 1000.0
		if timers[i] >= k["spawn_ms"]:
			timers[i] -= k["spawn_ms"]
			var s: float = k["size"]
			enemies.append({"x": s / 2.0 + rng.randf() * (W - s), "y": -s / 2.0, "k": k})
	var kept: Array = []
	for e in enemies:
		e["y"] += e["k"]["speed"] * 60.0 * dt
		if e["y"] - e["k"]["size"] / 2.0 < H:
			kept.append(e)
	enemies = kept
	for e in enemies:
		var r: float = (e["k"]["size"] + PW) / 2.0
		if absf(e["x"] - px) < r and absf(e["y"] - PCY) < r:
			over = true
			won = false
			return
	if play_t >= WIN_S:
		over = true
		won = true


func _score() -> int:
	return int(floor(minf(play_t, WIN_S)))


func probe_state() -> Dictionary:
	var threats: Array = []
	var ey := 0.0
	for e in enemies:
		ey += e["y"]
		if e["y"] - e["k"]["size"] / 2.0 < PY + PW: # not yet fallen past the player
			threats.append([roundi(e["x"] - px), roundi(PCY - e["y"])])
	threats.sort_custom(func(a, b): return Vector2(a[0], a[1]).length() < Vector2(b[0], b[1]).length())
	return {"over": over, "won": won, "paused": not started, "score": _score(), "px": roundi(px),
		"n": enemies.size(), "ey": roundi(ey), "threats": threats.slice(0, 3)}


# Mirrors dodge-web's bot: sees enemies where they were REACTION_S ago, knows where it is now.
func probe_bot(s: Dictionary) -> Array:
	seen.append([clock_t, s])
	while seen.size() > 1 and seen[1][0] <= clock_t - REACTION_S:
		seen.pop_front()
	var o: Dictionary = seen[0][1]
	var th: Array = []
	for t in o["threats"]:
		th.append([t[0] + o["px"] - s["px"], t[1]])
	var hit = null
	for t in th:
		if absf(t[0]) < 30 and t[1] < 140:
			hit = t
			break
	if hit != null:
		var left: bool = hit[0] > 0 if hit[0] != 0 else s["px"] > W / 2.0 # away from it...
		if left and (s["px"] < 40 or _blocked(th, -1)): # ...unless that side has less room
			left = false
		elif not left and (s["px"] > W - 40 or _blocked(th, 1)):
			left = true
		return ["ui_left"] if left else ["ui_right"]
	var d: float = W / 2.0 - s["px"]
	if absf(d) < 8:
		return []
	for t in th:
		if t[1] < 140 and absf(t[0]) < 60 and signf(t[0]) == signf(d):
			return []
	return ["ui_right"] if d > 0 else ["ui_left"]


func _blocked(th: Array, side: int) -> bool:
	for t in th:
		if t[1] < 40 and signf(t[0]) == side and absf(t[0]) >= 14 and absf(t[0]) < 40:
			return true
	return false


func _draw() -> void:
	draw_rect(Rect2(0, 0, W, H), Color(0.07, 0.07, 0.07))
	for e in enemies:
		var s: float = e["k"]["size"]
		var c: Color = Color(0.85, 0.33, 0.33) if e["k"]["id"] == "bat" else Color(0.33, 0.8, 0.33)
		draw_rect(Rect2(e["x"] - s / 2.0, e["y"] - s / 2.0, s, s), c)
	draw_rect(Rect2(px - PW / 2.0, PY, PW, PW), Color(0.33, 0.67, 1.0))
	var font := ThemeDB.fallback_font
	draw_string(font, Vector2(0, 20), "score %d" % _score(), HORIZONTAL_ALIGNMENT_CENTER, W, 16)
	var msg := ""
	if not started:
		msg = "Press Enter or Space to start"
	elif over:
		msg = ("You survived! " if won else "Hit! ") + "Score %d" % _score()
	if msg != "":
		draw_string(font, Vector2(0, H / 2.0), msg, HORIZONTAL_ALIGNMENT_CENTER, W, 16)
