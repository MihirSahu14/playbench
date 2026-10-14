"""playbench balance: knob sweeps on the real build, plus cost curves, model sims and payoff matrices.

balance.py sweep <game_dir> --knob NAME [--values a,b,c] [--seeds N] [--seconds S]
balance.py costcurve <csv> [--cost COL] [--benefit a,b,c] [--id COL] [--out DIR]
balance.py sim <model.py> [--runs 1000] [--seed 1] [--knob name=value]... [--out DIR]
balance.py matrix <csv> [--iters 20000] [--out DIR]
balance.py selftest
"""
import argparse, csv, datetime, importlib.util, io, json, math, os, random, shutil, statistics, sys, tempfile, time
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
    build = os.path.join(str(game), build_dir)  # Godot too: playtest.run turns overrides into --name=value user args
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


def read_csv(path):
    if not Path(path).is_file():
        die(f"no such file: {path}")
    text = Path(path).read_text("utf-8-sig")
    try:
        delim = csv.Sniffer().sniff(text[:4096], ",;\t").delimiter
    except csv.Error:
        delim = ","
    rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), delimiter=delim) if any(c.strip() for c in r)]
    if len(rows) < 2:
        die(f"{path} needs a header row and at least one data row")
    return rows


def fin(cell):
    v = float(cell)
    if not math.isfinite(v):
        raise ValueError(cell)  # "nan"/"inf" parse as floats but poison every fit
    return v


def g(x):
    return f"{x:.3g}" if abs(x) < 1000 else f"{x:.0f}"


def costcurve(path, cost=None, benefit=None, id_col=None):
    rows = read_csv(path)
    head, data = rows[0], rows[1:]
    def col(name):
        hit = [i for i, h in enumerate(head) if h.lower() == name.lower()]
        if not hit:
            die(f"no column {name!r} in {path} (columns: {', '.join(head)})")
        return hit[0]
    def nums(i):
        try:
            return [fin(r[i]) for r in data]
        except (ValueError, IndexError):
            return None
    ic, cc = col(id_col) if id_col else 0, col(cost or "cost")
    cols = [col(b) for b in benefit] if benefit else [i for i in range(len(head)) if i not in (ic, cc) and nums(i)]
    if not cols:
        die(f"no numeric benefit columns in {path}; pass --benefit a,b,c")
    if nums(cc) is None or any(nums(i) is None for i in cols):
        die(f"cost and benefit columns must be numbers in every row of {path}")
    if len(data) < 3:
        die(f"a cost curve needs at least 3 items; {path} has {len(data)}")
    costs = nums(cc)
    bens = [sum(v) for v in zip(*(nums(i) for i in cols))]  # ponytail: unweighted sum; weight columns by hand if one matters more
    try:
        a, b = statistics.linear_regression(bens, costs)
    except statistics.StatisticsError:
        die("every item has the same benefit, so there is no curve to fit")
    res = [c - (a * x + b) for c, x in zip(costs, bens)]
    sigma = statistics.pstdev(res)
    L = [f"Cost curve: cost = {g(a)} x benefit {'-' if b < 0 else '+'} {g(abs(b))} (least squares, {len(data)} items)",
         f"Benefit = {' + '.join(head[i] for i in cols)}", "",
         "| item | cost | benefit | fair cost | residual | flag |", "|---|---|---|---|---|---|"]
    out = []
    for r, c, x, e in zip(data, costs, bens, res):
        flag = "" if sigma == 0 or abs(e) <= 2 * sigma else "overpriced" if e > 0 else "underpriced (too strong for its cost)"
        if flag:
            out.append(f"{r[ic]} ({flag})")
        L.append(f"| {r[ic]} | {g(c)} | {g(x)} | {g(a * x + b)} | {e:+.3g} | {flag} |")
    L += ["", f"Outliers beyond 2 sigma ({g(2 * sigma)}): {', '.join(out)}" if out else "No outliers beyond 2 sigma"
          + (" (with under 6 items one outlier can't reach 2 sigma)" if len(data) < 6 else ""),
          "", "A cost curve only says which items are off the line; whether the line itself is fun is a human call."]
    return "\n".join(L)


def load_model(path):
    if not Path(path).is_file():
        die(f"no such model: {path} (copy skills/balance/model-template.py to balance/model.py)")
    spec = importlib.util.spec_from_file_location("playbench_model", path)
    if spec is None:
        die(f"{path} must be a .py file")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # the user's own code: their traceback is the useful error
    missing = [a for a in ("KNOBS", "TICKS", "init", "step", "metrics") if not hasattr(m, a)]
    if missing:
        die(f"{path} is missing {', '.join(missing)} (see skills/balance/model-template.py)")
    return m


def sim(path, runs=1000, seed=1, knobs=None):
    m = load_model(path)
    k = dict(m.KNOBS)
    for kv in knobs or []:
        name, eq, val = kv.partition("=")
        if not eq or name not in m.KNOBS:
            die(f"unknown knob {kv!r}: use name=value with a name from KNOBS ({', '.join(m.KNOBS)})")
        try:
            k[name] = json.loads(val)
        except ValueError:
            k[name] = val
    limits, dl = getattr(m, "LIMITS", {}) or {}, getattr(m, "DEADLOCK_TICKS", 20)
    finals, ends, dead, wild = {}, [], [], []
    for i in range(runs):
        rng = random.Random(seed + i)
        state = m.init(rng, k)
        prev, same = json.dumps(state, sort_keys=True, default=str), 0
        for t in range(1, m.TICKS + 1):
            nxt = m.step(state, rng, k)
            if nxt is None:
                ends.append(t)
                break
            state, snap = nxt, json.dumps(nxt, sort_keys=True, default=str)
            same, prev = same + 1 if snap == prev else 0, snap
            mt = m.metrics(state)
            if not all(isinstance(v, (int, float)) for v in mt.values()):
                die(f"metrics() must return numbers only, got {mt!r}")
            bad = [(n, v) for n, v in mt.items()
                   if not math.isfinite(v) or (n in limits and not limits[n][0] <= v <= limits[n][1])]
            if bad:
                wild.append((seed + i, t, *bad[0]))
                break
            if same >= dl:
                dead.append((seed + i, t))
                break
        for n, v in m.metrics(state).items():
            finals.setdefault(n, []).append(v)
    shown = ", ".join(f"{n}={v}" for n, v in k.items())
    L = [f"Model sim: {Path(path).name}, {runs} runs x up to {m.TICKS} ticks, seed {seed}, knobs: {shown}",
         f"Model output, not the real game: it is only as true as {Path(path).as_posix()}.", "",
         "| metric (final) | mean | p10 | p50 | p90 | min | max |", "|---|---|---|---|---|---|---|"]
    for n, vals in finals.items():
        v = [x for x in vals if math.isfinite(x)]
        q = statistics.quantiles(v, n=10, method="inclusive") if len(v) > 1 else v * 9
        L.append(f"| {n} | " + (" | ".join(g(x) for x in (statistics.fmean(v), q[0], q[4], q[8], min(v), max(v)))
                               if v else "- | - | - | - | - | -") + " |")
    L += ["", f"Ended early (step returned None): {len(ends)}/{runs}"
          + (f", p50 end tick {g(statistics.median(ends))}" if ends else ""),
          f"Deadlocks (state unchanged {dl} ticks): {len(dead)}/{runs}"
          + (f", e.g. seed {dead[0][0]} at tick {dead[0][1]}" if dead else ""),
          f"Runaways (outside LIMITS or NaN/inf): {len(wild)}/{runs}"
          + (f", e.g. seed {wild[0][0]} at tick {wild[0][1]}: {wild[0][2]}={g(wild[0][3])}" if wild else "")]
    return "\n".join(L)


def matrix(path, iters=20000):
    rows = read_csv(path)
    cols, labels = rows[0][1:], [r[0] for r in rows[1:]]
    if len(cols) < 2 or labels != cols or any(len(r) != len(cols) + 1 for r in rows[1:]):
        die(f"{path} must be square with at least 2 strategies: the header row and the first column list the same strategies in the same order")
    try:
        M = [[fin(c) for c in r[1:]] for r in rows[1:]]
    except ValueError:
        die(f"every cell in {path} must be a finite number")
    shift = 0.5 if all(0 <= c <= 1 for r in M for c in r) else 0.0
    M = [[c - shift for c in r] for r in M]  # ponytail: 0..1 cells read as win rates, so 0.5 is even and the game is zero-sum
    n = len(M)
    ge = lambda j, i: all(a >= b for a, b in zip(M[j], M[i])) and M[j] != M[i]
    dom = {i: next((cols[j] for j in range(n) if j != i and ge(j, i)), None) for i in range(n)}
    # fictitious play: each side best-responds to the other's empirical mix; converges in zero-sum games
    rp, cp, rc, cc = [0.0] * n, [0.0] * n, [0] * n, [0] * n
    r = c = 0
    for _ in range(iters):
        rc[r] += 1
        cc[c] += 1
        for i in range(n):
            rp[i] += M[i][c]
            cp[i] += M[r][i]
        r, c = max(range(n), key=rp.__getitem__), min(range(n), key=cp.__getitem__)
    value = (max(rp) + min(cp)) / 2 / iters + shift
    L = [f"Payoff matrix: {n} strategies, Nash mix by fictitious play ({iters} rounds)",
         "Equilibrium of the matrix you gave; real players are not Nash players.", "",
         "| strategy | Nash weight % | flags |", "|---|---|---|"]
    for i in range(n):
        w = rc[i] / iters
        flags = ([f"dominated by {dom[i]}"] if dom[i] else []) + \
                (["dominant"] if all(ge(i, j) for j in range(n) if j != i) else []) + \
                (["never picked at equilibrium (<1%)"] if w < 0.01 else [])
        L.append(f"| {cols[i]} | {w * 100:.1f} | {', '.join(flags)} |")
    L += ["", f"Game value for the row player: {value:.3f}" + (" (0.5 = even)" if shift else " (0 = even)")]
    return "\n".join(L)


def save(text, out, kind):
    out, stamp = Path(out), time.strftime("%Y-%m-%d-%H%M")
    if (out / f"{stamp}-{kind}.md").exists():  # same minute: add seconds, which still sorts after it
        stamp = time.strftime("%Y-%m-%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stamp}-{kind}.md").write_text(text + "\n", "utf-8")
    return out / f"{stamp}-{kind}.md"


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
        (Path(tmp) / "godot").mkdir()
        (Path(tmp) / "godot" / "project.godot").write_text("", encoding="utf-8")
        (Path(tmp) / "studio.json").write_text('{"build_dir": "godot"}', encoding="utf-8")
        calls.clear()
        sweep(tmp, "spawn_every", values=[0.75], run=fake())
        assert calls == [{"name": "spawn_every", "file": None, "key": "spawn_every", "value": 0.75}], calls
        print("ok godot_passthrough")

    def exits2(f, *a):
        try:
            f(*a)
        except SystemExit as e:
            return e.code == 2
        return False
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        line = [("sword", 1), ("axe", 2), ("bow", 3), ("staff", 5), ("dagger", 6), ("spear", 7)]
        (t / "items.csv").write_text("name;Cost;atk;def\n" + "".join(f"{n};{10 * b + 5};{b};0\n" for n, b in line)
                                     + "gem_sword;95;3;1\n", encoding="utf-8")
        cc = costcurve(t / "items.csv")
        flagged = [l for l in cc.splitlines() if l.startswith("| ") and l.rstrip(" |").endswith(("overpriced", "cost)"))]
        assert len(flagged) == 1 and flagged[0].startswith("| gem_sword |") and "overpriced" in flagged[0], cc
        assert "fun is a human call" in cc and "Outliers beyond 2 sigma" in cc
        assert exits2(costcurve, t / "items.csv", "price") and exits2(costcurve, t / "nope.csv")
        print("ok costcurve")

        tpl = Path(__file__).resolve().parent.parent / "skills" / "balance" / "model-template.py"
        a, b = sim(tpl, runs=200), sim(tpl, runs=200)
        assert a == b and "| level |" in a and "Model output, not the real game" in a, a
        assert "Ended early (step returned None): 200/200" in a and "Deadlocks (state unchanged 20 ticks): 0/200" in a, a
        assert exits2(sim, tpl, 10, 1, ["nope=1"])
        assert "Deadlocks (state unchanged 20 ticks): 50/50" in sim(tpl, 50, 1, ["income=0"])
        stuck = "KNOBS={}\nTICKS=100\ndef init(rng, k): return {'gold': 1}\ndef step(s, rng, k): return s\ndef metrics(s): return dict(s)\n"
        (t / "stuck.py").write_text(stuck, encoding="utf-8")
        assert "Deadlocks (state unchanged 20 ticks): 30/30, e.g. seed 1 at tick 20" in sim(t / "stuck.py", runs=30)
        (t / "boom.py").write_text(stuck.replace("return s\n", "return {'gold': s['gold'] * 2}\n")
                                   + "LIMITS={'gold': (0, 1000)}\n", encoding="utf-8")
        boom = sim(t / "boom.py", runs=5)
        assert "Runaways (outside LIMITS or NaN/inf): 5/5, e.g. seed 1 at tick 10: gold=1024" in boom, boom
        (t / "half.py").write_text("KNOBS={}\n", encoding="utf-8")
        assert exits2(sim, t / "half.py")
        (t / "str.py").write_text(stuck.replace("dict(s)", "{'g': 'x'}"), encoding="utf-8")
        (t / "m.txt").write_text(stuck, encoding="utf-8")
        assert exits2(sim, t / "str.py") and exits2(sim, t / "m.txt")
        print("ok sim")

        (t / "rps.csv").write_text(",rock,paper,scissors\nrock,0.5,0,1\npaper,1,0.5,0\nscissors,0,1,0.5\n", encoding="utf-8")
        rps = matrix(t / "rps.csv")
        rows = [l.split("|") for l in rps.splitlines() if l.startswith("| ") and "Nash" not in l]
        assert len(rows) == 3 and all(30 <= float(r[2]) <= 37 and not r[3].strip() for r in rows), rps
        (t / "rpsd.csv").write_text(",R,P,S,D\nR,0.5,0,1,1\nP,1,0.5,0,1\nS,0,1,0.5,1\nD,0,0,0,0.5\n", encoding="utf-8")
        d = [l.split("|") for l in matrix(t / "rpsd.csv").splitlines() if l.startswith("| D ")][0]
        assert "dominated by R" in d[3] and float(d[2]) < 1, d
        (t / "bad.csv").write_text(",a,b\na,0.5,1\n", encoding="utf-8")
        assert exits2(matrix, t / "bad.csv")
        (t / "nan.csv").write_text(",a,b\na,0.5,nan\nb,0.5,0.5\n", encoding="utf-8")
        assert exits2(matrix, t / "nan.csv")
        print("ok matrix")

        f = save(rps, t / "balance", "matrix")
        assert f.name.endswith("-matrix.md") and f.read_text("utf-8").startswith("Payoff matrix")
        print("ok out")

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
    c = sub.add_parser("costcurve")
    c.add_argument("csv")
    c.add_argument("--cost")
    c.add_argument("--benefit", type=lambda t: [x.strip() for x in t.split(",")])
    c.add_argument("--id")
    m = sub.add_parser("sim")
    m.add_argument("model")
    m.add_argument("--runs", type=int, default=1000)
    m.add_argument("--seed", type=int, default=1)
    m.add_argument("--knob", action="append")
    x = sub.add_parser("matrix")
    x.add_argument("csv")
    x.add_argument("--iters", type=int, default=20000)
    for q in (c, m, x):
        q.add_argument("--out")
    sub.add_parser("selftest")
    a = p.parse_args()
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "sweep":
        return print(table(sweep(a.game_dir, a.knob, a.values, a.seeds, a.seconds)))
    if getattr(a, "runs", 1) < 1 or getattr(a, "iters", 1) < 1:
        die("--runs and --iters must be at least 1")
    text = (costcurve(a.csv, a.cost, a.benefit, a.id) if a.cmd == "costcurve" else
            sim(a.model, a.runs, a.seed, a.knob) if a.cmd == "sim" else matrix(a.csv, a.iters))
    print(text)
    if a.out:
        print(f"REPORT={save(text, a.out, a.cmd)}")


if __name__ == "__main__":
    main()
