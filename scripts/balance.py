"""playbench balance: sweep one knob on the real build with the policy bot.

balance.py sweep <game_dir> --knob NAME [--values a,b,c] [--seeds N] [--seconds S]
balance.py selftest
"""
# ponytail: sweep only; costcurve and the Monte Carlo economy sim are v1.1.
import argparse, datetime, json, os, shutil, sys, tempfile
from pathlib import Path

NEEDS_BOT = ("sweep needs a policy bot (window.__game.bot or probe_bot); "
             "random-input sweeps are noise. Ask the playtest skill to add one.")


def die(msg):
    print(f"balance: {msg}", file=sys.stderr)
    raise SystemExit(2)


def parse_knobs(text):
    """`## Knobs` table (| name | file | key | min | max |) -> {name: {file, key, min, max}}."""
    knobs, inside = {}, False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            inside = s.lstrip("#").strip().lower() == "knobs"
            continue
        if not inside or not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if (len(cells) < 5 or not cells[0] or cells[0].startswith("<!--") or cells[0].lower() == "name"
                or set("".join(cells)) <= set("-: ")):
            continue
        name, file, key, lo, hi = cells[:5]
        knobs[name] = {"file": None if file in ("-", "") else file, "key": key, "min": num(lo), "max": num(hi)}
    return knobs


def num(cell):
    try:
        return float(cell)
    except ValueError:
        return None  # placeholder like "?" or "<min>"; only matters if this knob is swept without --values


def sweep(game_dir, knob, values=None, seeds=None, seconds=None, run=None):
    game = Path(game_dir)
    cfg = game / "studio.json"
    build_dir = json.loads(cfg.read_text(encoding="utf-8-sig")).get("build_dir", ".") if cfg.exists() else "."
    design = game / "design" / "design.md"
    if not design.exists():
        die(f"no {design} found. Add a '## Knobs' table (| name | file | key | min | max |); the design skill makes one.")
    knobs = parse_knobs(design.read_text(encoding="utf-8-sig"))
    if knob not in knobs:
        die(f"unknown knob '{knob}'. Known knobs in design/design.md: {', '.join(knobs) or '(none: the ## Knobs table is empty)'}")
    k = knobs[knob]
    if values is None:
        if k["min"] is None or k["max"] is None:
            die(f"knob '{knob}' needs numeric min and max in design/design.md, or pass --values a,b,c")
        values = [round(k["min"] + (k["max"] - k["min"]) * i / 4, 3) for i in range(5)]
    build = os.path.join(str(game), build_dir)
    if os.path.exists(os.path.join(build, "project.godot")):
        die("sweeps are web-only in v1: Godot data inside the .pck can't be overridden. Export to web and sweep that.")
    if run is None:
        sys.path.insert(0, str(Path(__file__).parent))
        from playtest import run
    out = {}
    for v in values:
        r = run(build, mode="sweep", bot="policy", seeds=seeds, seconds=seconds,
                overrides=[{"name": knob, "file": k["file"], "key": k["key"], "value": v}])
        if r.get("tier", 0) < 2:
            die(NEEDS_BOT)
        out[str(v)] = r.get("stats")
    path = game / "balance" / "last.json"
    last = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    prev = last.get(knob)
    last[knob] = {"at": datetime.datetime.now().isoformat(timespec="seconds"), "bot": "policy", "values": out}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(last, indent=1), encoding="utf-8")
    return {"knob": knob, "values": out, "prev": prev}


def table(result):
    f = lambda x: "-" if x is None else f"{x:.1f}"
    prev = (result.get("prev") or {}).get("values", {})
    lines = [f"Balance sweep: {result['knob']} (relative difficulty under policy bot, not human difficulty)", "",
             "| value | win % | p50 s | p10 s | p90 s | deaths/min | Δ win % vs last |",
             "|---|---|---|---|---|---|---|"]
    for v, s in result["values"].items():
        s = s or {}
        w, pw = s.get("win_rate"), (prev.get(v) or {}).get("win_rate")
        delta = f"{(w - pw) * 100:+.0f}" if w is not None and pw is not None else ""
        cells = [v, "-" if w is None else f"{w * 100:.0f}", f(s.get("tto_p50")), f(s.get("tto_p10")),
                 f(s.get("tto_p90")), f(s.get("deaths_per_min")), delta]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


DESIGN = """# Dodge
## Knobs
| name | file | key | min | max |
|---|---|---|---|---|
| <!-- name a number players feel --> | | | | |
| bat_speed | data/enemies.csv | bat.speed | 1 | 5 |
| spawn_every | - | spawn_every | 0.5 | 2.5 |
| hp | - | hp | ? | <max> |

## Notes
| not | a | knob | 1 | 2 |
"""


def selftest():
    k = parse_knobs(DESIGN)
    assert k == {"bat_speed": {"file": "data/enemies.csv", "key": "bat.speed", "min": 1.0, "max": 5.0},
                 "spawn_every": {"file": None, "key": "spawn_every", "min": 0.5, "max": 2.5},
                 "hp": {"file": None, "key": "hp", "min": None, "max": None}}, k
    print("ok parse_knobs")

    calls = []
    def fake(shift=0.0, tier=2):
        def run(build, mode, bot, seeds, seconds, overrides):
            assert mode == "sweep" and bot == "policy" and len(overrides) == 1
            calls.append(overrides[0])
            v = overrides[0]["value"]
            return {"tier": tier, "stats": {"label": "relative difficulty under policy bot", "runs": 5,
                    "win_rate": max(0.0, 1 - v / 6 + shift), "tto_p10": 5.0, "tto_p50": 20 - v, "tto_p90": 30.0,
                    "deaths_per_min": v / 2}}
        return run
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "design").mkdir()
        (Path(tmp) / "design" / "design.md").write_text(DESIGN, encoding="utf-8")
        (Path(tmp) / "studio.json").write_text('{"build_dir": "."}', encoding="utf-8")
        r = sweep(tmp, "bat_speed", run=fake())
        rows = table(r).splitlines()[4:]
        assert len(rows) == 5 and [c["value"] for c in calls] == [1.0, 2.0, 3.0, 4.0, 5.0], rows
        assert calls[0]["file"] == "data/enemies.csv" and calls[0]["key"] == "bat.speed"
        assert all(row.endswith("|  |") for row in rows), rows  # no previous run -> blank delta
        wins = [r["values"][v]["win_rate"] for v in r["values"]]
        assert wins == sorted(wins, reverse=True)
        last = Path(tmp) / "balance" / "last.json"
        assert json.loads(last.read_text())["bat_speed"]["bot"] == "policy"
        r2 = sweep(tmp, "bat_speed", run=fake(shift=-0.1))
        assert r2["prev"] and all(row.endswith("| -10 |") for row in table(r2).splitlines()[4:]), table(r2)
        sweep(tmp, "spawn_every", values=[1.0], run=fake())
        assert set(json.loads(last.read_text())) == {"bat_speed", "spawn_every"}
        print("ok sweep_fake")
        try:
            sweep(tmp, "bat_speed", values=[1.0], run=fake(tier=1))
            raise AssertionError("tier 1 should exit 2")
        except SystemExit as e:
            assert e.code == 2
        try:
            sweep(tmp, "hp", run=fake())
            raise AssertionError("non-numeric min/max without --values should exit 2")
        except SystemExit as e:
            assert e.code == 2
        print("ok tier_gate")

    root = Path(__file__).resolve().parent.parent
    web = root / "examples" / "dodge-web"
    try:
        import playwright  # noqa: F401
        why = None if (root / "scripts" / "playtest.py").exists() and web.exists() else "playtest.py or dodge-web missing"
    except ImportError:
        why = "playwright not importable"
    if why:
        return print(f"SKIP integration: {why}")
    with tempfile.TemporaryDirectory() as tmp:
        g = Path(tmp) / "dodge"
        shutil.copytree(web, g)
        r = sweep(g, "bat_speed", values=[1.0, 4.0], seeds=3, seconds=25)
        print(table(r))
        assert r["values"]["1.0"]["win_rate"] >= r["values"]["4.0"]["win_rate"], r
    print("ok integration")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="balance.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sweep")
    s.add_argument("game_dir")
    s.add_argument("--knob", required=True)
    s.add_argument("--values", type=lambda t: [float(x) for x in t.split(",")])
    s.add_argument("--seeds", type=int)
    s.add_argument("--seconds", type=float)
    sub.add_parser("selftest")
    a = p.parse_args()
    if a.cmd == "selftest":
        return selftest()
    print(table(sweep(a.game_dir, a.knob, a.values, a.seeds, a.seconds)))


if __name__ == "__main__":
    main()
