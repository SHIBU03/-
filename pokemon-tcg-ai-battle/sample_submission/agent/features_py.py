"""Pure-python feature extraction for the SUBMITTED agent (no numpy).

Mirrors ``model/features.py`` exactly (same 37-dim layout) so a ValueNet trained
on dev features can run at MCTS leaves inside the bundle. A test asserts the two
implementations produce identical vectors. Works on both the live obs dict and
the Search API Observation dataclass.
"""
from __future__ import annotations

G_DIM = 9
P_DIM = 14
FEATURE_DIM = G_DIM + 2 * P_DIM


def _g(obj, key, default=None):
    if obj is None:
        return default
    v = obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)
    return default if v is None else v


def _player_vec(ps):
    active = _g(ps, "active", []) or []
    ap = active[0] if (active and active[0]) else None
    hp = _g(ap, "hp", 0) or 0
    maxhp = _g(ap, "maxHp", 0) or 0
    energy = len(_g(ap, "energies", []) or [])
    bench = _g(ps, "bench", []) or []
    hand = _g(ps, "hand", None)
    hand_count = _g(ps, "handCount", len(hand) if hand else 0)
    return [
        1.0 if ap else 0.0,
        (hp / maxhp) if maxhp else 0.0,
        (maxhp or 0) / 300.0,
        energy / 10.0,
        len(bench) / 5.0,
        (hand_count or 0) / 15.0,
        len(_g(ps, "prize", []) or []) / 6.0,
        (_g(ps, "deckCount", 0) or 0) / 60.0,
        len(_g(ps, "discard", []) or []) / 60.0,
        1.0 if _g(ps, "poisoned", False) else 0.0,
        1.0 if _g(ps, "burned", False) else 0.0,
        1.0 if _g(ps, "asleep", False) else 0.0,
        1.0 if _g(ps, "paralyzed", False) else 0.0,
        1.0 if _g(ps, "confused", False) else 0.0,
    ]


def _global_vec(cur):
    yi = _g(cur, "yourIndex", 0) or 0
    return [
        (_g(cur, "turn", 0) or 0) / 50.0,
        float(yi),
        1.0 if _g(cur, "firstPlayer", -1) == yi else 0.0,
        1.0 if _g(cur, "supporterPlayed", False) else 0.0,
        1.0 if _g(cur, "stadiumPlayed", False) else 0.0,
        1.0 if _g(cur, "energyAttached", False) else 0.0,
        1.0 if _g(cur, "retreated", False) else 0.0,
        (_g(cur, "turnActionCount", 0) or 0) / 20.0,
        1.0 if (_g(cur, "stadium", []) or []) else 0.0,
    ]


def vec_from_current(cur):
    if not cur:
        return [0.0] * FEATURE_DIM
    yi = _g(cur, "yourIndex", 0) or 0
    players = _g(cur, "players", []) or [{}, {}]
    me = players[yi] if yi < len(players) else {}
    opp = players[1 - yi] if (1 - yi) < len(players) else {}
    return _global_vec(cur) + _player_vec(me) + _player_vec(opp)


def featurize(obs) -> list:
    """From a live obs dict OR a Search Observation dataclass."""
    return vec_from_current(_g(obs, "current", None))
