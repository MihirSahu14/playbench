"""playbench balance model: a tiny stand-in for your game's economy, run by `balance.py sim`.

This file is YOUR code and `balance.py sim` executes it. Copy it to balance/model.py and replace the
example (an idle/RPG economy: earn gold, buy levels, win at level 10) with your game's numbers from
design/design.md. Keep it small: a model compares knob values; it is not a second copy of the game.
Stdlib only. Use the `rng` you are given, never `random.*`, so every run replays from its seed.
"""
# The numbers you want to compare. Override per run: balance.py sim balance/model.py --knob income=3
KNOBS = {"income": 1.0, "cost_base": 10.0, "cost_growth": 1.6, "crit_chance": 0.1}

TICKS = 600  # max ticks per run (say 1 tick = 1 second of play)

# Optional: a metric outside (lo, hi) at any tick is a runaway (e.g. an infinite-gold loop).
LIMITS = {"gold": (0, 100000)}

# Optional: the whole state unchanged this many ticks in a row is a deadlock (default 20).
# So don't keep a tick counter in the state: it would hide every deadlock.
DEADLOCK_TICKS = 20

WIN_LEVEL = 10


def init(rng, knobs):
    """Starting state: a dict of plain values (numbers, strings, lists, dicts)."""
    return {"gold": 0.0, "level": 1, "crits": 0}


def step(state, rng, knobs):
    """One tick: return the new state, or None when the run ends (here: the player has won)."""
    if state["level"] >= WIN_LEVEL:
        return None
    s = dict(state)
    gain = knobs["income"] * s["level"]  # income scales with level
    if rng.random() < knobs["crit_chance"]:  # a lucky tick pays double
        gain *= 2
        s["crits"] += 1
    s["gold"] += gain
    cost = knobs["cost_base"] * knobs["cost_growth"] ** (s["level"] - 1)  # each level costs more
    if s["gold"] >= cost:  # greedy player: buy the next level as soon as it is affordable
        s["gold"] -= cost
        s["level"] += 1
    return s


def metrics(state):
    """Numbers reported for each run's final state, and checked against LIMITS every tick."""
    return {"level": state["level"], "gold": state["gold"], "crits": state["crits"]}
