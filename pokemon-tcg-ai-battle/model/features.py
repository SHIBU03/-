"""Structured feature extraction from a cabt observation.

``featurize(obs_dict)`` (dict, from the live agent) and
``featurize_search_obs(observation)`` (dataclass, from the Search API) both
return the SAME fixed-length ``np.float32`` vector describing the board from the
to-move player's perspective. Robust to missing / face-down fields.
"""
from __future__ import annotations

import numpy as np

G_DIM = 9          # global features
P_DIM = 14         # per-player features
FEATURE_DIM = G_DIM + 2 * P_DIM


def _g(obj, key, default=None):
    """Get attribute from a dict OR a dataclass."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        v = obj.get(key, default)
    else:
        v = getattr(obj, key, default)
    return default if v is None else v


def _player_vec(ps) -> list[float]:
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


def _global_vec(cur) -> list[float]:
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


def _vec_from_current(cur) -> np.ndarray:
    if not cur:
        return np.zeros(FEATURE_DIM, dtype=np.float32)
    yi = _g(cur, "yourIndex", 0) or 0
    players = _g(cur, "players", []) or [{}, {}]
    me = players[yi] if yi < len(players) else {}
    opp = players[1 - yi] if (1 - yi) < len(players) else {}
    vec = _global_vec(cur) + _player_vec(me) + _player_vec(opp)
    return np.asarray(vec, dtype=np.float32)


def featurize(obs_dict: dict) -> np.ndarray:
    """From the live agent's obs dict."""
    return _vec_from_current((obs_dict or {}).get("current"))


def featurize_search_obs(observation) -> np.ndarray:
    """From a Search API Observation dataclass."""
    return _vec_from_current(getattr(observation, "current", None))
