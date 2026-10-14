"""playbench telemetry: local-only event snippets for the game, plus a report over the exported JSON lines.

telemetry.py snippet web|godot
telemetry.py report <file|dir>... [--out DIR]
telemetry.py selftest

Events (contract C9), one JSON object per line:
{"ts": <ms since epoch>, "session": "<id>", "event": "start|level|death|win|quit|<custom>", "level": <optional>, ...}
"""
import argparse, contextlib, io, json, math, statistics, sys, tempfile, time
from pathlib import Path

WEB = """\
// playbench telemetry (local only). Nothing is sent anywhere: events stay in this browser's
// localStorage until the player exports them. Tell your players you record play events,
// and never record personal data (names, emails, free text).
// Use: pbTrack('start'); pbTrack('level', {level: 2}); pbTrack('death', {level: 2});
//      pbTrack('win'); pbTrack('quit', {level: 3}); pbTrack.export(); pbTrack.clear();
(function () {
  var KEY = 'playbench_telemetry', MAX = 5000;
  var session = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  function pbTrack(event, data) {
    if (window.__playbench) return; // bot playtests never pollute player data
    try {
      var line = JSON.stringify(Object.assign({}, data, {ts: Date.now(), session: session, event: event}));
      var lines = (localStorage.getItem(KEY) || '').split('\\n').filter(Boolean);
      lines.push(line);
      localStorage.setItem(KEY, lines.slice(-MAX).join('\\n'));
    } catch (e) {} // private mode or full storage must never break the game
  }
  pbTrack.export = function () {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([(localStorage.getItem(KEY) || '') + '\\n'], {type: 'application/x-ndjson'}));
    a.download = 'telemetry.jsonl';
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  };
  pbTrack.clear = function () { try { localStorage.removeItem(KEY); } catch (e) {} };
  window.pbTrack = pbTrack;
})();
"""

GODOT = """\
# playbench telemetry (local only). Nothing is sent anywhere: events are appended to
# user://telemetry.jsonl on the player's machine. Tell your players you record play events,
# and never record personal data (names, emails, free text).
# Add it: Project > Project Settings > Autoload, path res://telemetry.gd, name Telemetry.
# Use: Telemetry.track("start"); Telemetry.track("level", {"level": 2}); Telemetry.track("win")
# user:// lives in (with the default project settings):
#   Windows: %APPDATA%\\Godot\\app_userdata\\<project name>\\
#   macOS:   ~/Library/Application Support/Godot/app_userdata/<project name>/
#   Linux:   ~/.local/share/godot/app_userdata/<project name>/
# Players send you that telemetry.jsonl; run: telemetry.py report telemetry.jsonl
extends Node

const PATH := "user://telemetry.jsonl"
var session := ""

func _ready() -> void:
	randomize()
	session = "%x%04x" % [int(Time.get_unix_time_from_system() * 1000), randi() % 65536]

func track(event: String, data := {}) -> void:
	var row := {"ts": int(Time.get_unix_time_from_system() * 1000), "session": session, "event": event}
	row.merge(data)
	var f: FileAccess
	if FileAccess.file_exists(PATH):
		f = FileAccess.open(PATH, FileAccess.READ_WRITE)
		if f:
			f.seek_end()
	else:
		f = FileAccess.open(PATH, FileAccess.WRITE)
	if f:  # ponytail: a failed open drops the event; telemetry must never crash the game
		f.store_line(JSON.stringify(row))
		f.close()
"""

FOOTER = "Telemetry shows what players did, not why. Pair it with a human session (/playbench:log)."


def die(msg):
    print(f"telemetry: {msg}", file=sys.stderr)
    raise SystemExit(2)


def load(paths):
    """-> (events, files_read, bad_lines). Dirs contribute their *.jsonl and *.json-lines files."""
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(p.glob("*.jsonl")) + sorted(p.glob("*.json-lines"))
        elif p.is_file():
            files.append(p)
        else:
            die(f"no such file or directory: {p}")
    events, bad = [], 0
    for f in files:
        for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
                ok = (isinstance(e, dict) and isinstance(e.get("event"), str) and "session" in e
                      and isinstance(e.get("ts"), (int, float)) and not isinstance(e.get("ts"), bool)
                      and math.isfinite(e["ts"]))
            except ValueError:
                ok = False
            if ok:
                events.append(e)
            else:
                bad += 1
    return events, len(files), bad


def lvl(e):
    return None if e.get("level") in (None, "") else str(e["level"])


def report(paths):
    events, nfiles, bad = load(paths)
    if not events:
        die(f"no events in {', '.join(map(str, paths))} ({bad} bad lines). Export telemetry.jsonl from the game first.")
    sessions = {}
    for e in events:
        sessions.setdefault(str(e["session"]), []).append(e)
    n = len(sessions)
    wins = sum(any(e["event"] == "win" for e in s) for s in sessions.values())
    length = statistics.median((max(e["ts"] for e in s) - min(e["ts"] for e in s)) / 1000 for s in sessions.values())

    levels = list(dict.fromkeys(l for e in sorted(events, key=lambda e: e["ts"]) if (l := lvl(e)) is not None))
    try:
        levels.sort(key=float)  # all numeric -> numeric order, else first-seen order
    except ValueError:
        pass
    def per_level(event):
        c = {}
        for e in events:
            if e["event"] == event:
                c[lvl(e) or "?"] = c.get(lvl(e) or "?", 0) + 1
        return c
    deaths, quits = per_level("death"), per_level("quit")

    L = [f"Telemetry: {n} sessions from {nfiles} files ({bad} bad lines skipped)", "",
         f"- Sessions: {n}", f"- Win rate: {round(100 * wins / n)}% ({wins}/{n} sessions with a win)",
         f"- Median session length: {length:.1f} s", ""]
    if levels:
        L += ["## Funnel", "", "| level | sessions | drop-off | deaths | quits |", "|---|---|---|---|---|"]
        prev = None
        for l in levels:
            reached = sum(any(lvl(e) == l for e in s) for s in sessions.values())
            drop = f"{round(100 * (prev - reached) / prev)}%" if prev else ""
            L.append(f"| {l} | {reached} | {drop} | {deaths.get(l, 0)} | {quits.get(l, 0)} |")
            prev = reached
        L.append("")
    if "?" in deaths or "?" in quits:
        L += [f"Without a level: {deaths.get('?', 0)} deaths, {quits.get('?', 0)} quits.", ""]
    return "\n".join(L + [FOOTER])


def save(text, out):
    out, stamp = Path(out), time.strftime("%Y-%m-%d-%H%M")
    if (out / f"{stamp}-report.md").exists():  # same minute: add seconds, which still sorts after it
        stamp = time.strftime("%Y-%m-%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stamp}-report.md").write_text(text + "\n", "utf-8")
    return out / f"{stamp}-report.md"


def selftest():
    for bad in ("fetch(", "XMLHttpRequest", "sendBeacon", "WebSocket"):
        assert bad not in WEB, bad
    assert "localStorage" in WEB and "__playbench" in WEB and "user://telemetry.jsonl" in GODOT
    print("ok snippets")

    def ev(s, t, event, level=None):
        return json.dumps({"ts": 1_700_000_000_000 + t * 1000, "session": s, "event": event,
                           **({} if level is None else {"level": level})})
    rows = [ev("s1", 0, "start"), ev("s1", 1, "level", 1), ev("s1", 5, "death", 1), ev("s1", 6, "level", 1),
            ev("s1", 20, "level", 2), ev("s1", 40, "win"),
            ev("s2", 0, "start"), ev("s2", 2, "level", 1), ev("s2", 8, "death", 1), ev("s2", 10, "quit", 1),
            ev("s3", 0, "start"), ev("s3", 1, "level", 1), ev("s3", 15, "level", 2), ev("s3", 25, "death", 2),
            ev("s3", 30, "quit", 2), "{not json", '{"ts": NaN, "session": "s4", "event": "win"}']
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "a.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
        r = report([t / "a.jsonl"])
        assert r.startswith("Telemetry: 3 sessions from 1 files (2 bad lines skipped)"), r
        assert "Win rate: 33%" in r and "Median session length: 30.0 s" in r, r
        assert "| 1 | 3 |  | 2 | 1 |" in r and "| 2 | 2 | 33% | 1 | 1 |" in r, r
        assert r.endswith(FOOTER)
        print("ok report")
        assert report([t]) == r
        f = save(r, t / "telemetry")
        assert f.name.endswith("-report.md") and f.read_text("utf-8").startswith("Telemetry: 3 sessions")
        print("ok out")
        (t / "empty.jsonl").write_text("", encoding="utf-8")
        for args in ([t / "empty.jsonl"], [t / "nope.jsonl"]):
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    report(args)
                raise AssertionError(f"{args} should exit 2")
            except SystemExit as e:
                assert e.code == 2
        print("ok no_data")
    print("ok telemetry")


def main():
    ap = argparse.ArgumentParser(description="playbench telemetry (local only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snippet").add_argument("kind", choices=["web", "godot"])
    rp = sub.add_parser("report")
    rp.add_argument("paths", nargs="+")
    rp.add_argument("--out")
    sub.add_parser("selftest")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # level names may be any unicode; cp1252 consoles crash
    if a.cmd == "snippet":
        sys.stdout.write(WEB if a.kind == "web" else GODOT)
    elif a.cmd == "report":
        text = report(a.paths)
        print(text)
        if a.out:
            print(f"REPORT={save(text, a.out)}")
    else:
        selftest()


if __name__ == "__main__":
    main()
