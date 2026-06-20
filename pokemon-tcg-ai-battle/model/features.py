"""Structured feature extraction from a cabt observation.

``featurize(obs_dict)`` returns a fixed-length ``np.float32`` vector describing
the board from the to-move player's perspective (global flags + my player + the
opponent's visible state). It is intentionally compact and robust to missing /
face-down fields; the richer card-embedding features come in Sprint 3.
"""
from __future__ import annotations

import numpy as np

G_DIM = 9          # global features
P_DIM = 14         # per-player features
FEATURE_DIM = G_DIM + 2 * P_DIM


def _player_vec(ps: dict) -> list[float]:
    ps = ps or {}
    active = ps.get("active") or []
    ap = active[0] if (active and active[0]) else None
    hp = (ap or {}).get("hp", 0) or 0
    maxhp = (ap or {}).get("maxHp", 0) or 0
    energy = len((ap or {}).get("energies") or [])
    bench = ps.get("bench") or []
    hand_count = ps.get("handCount")
    if hand_count is None:
        hand_count = len(ps.get("hand") or [])
    return [
        1.0 if ap else 0.0,
        (hp / maxhp) if maxhp else 0.0,
        (maxhp or 0) / 300.0,
        energy / 10.0,
        len(bench) / 5.0,
        (hand_count or 0) / 15.0,
        len(ps.get("prize") or []) / 6.0,
        (ps.get("deckCount") or 0) / 60.0,
        len(ps.get("discard") or []) / 60.0,
        1.0 if ps.get("poisoned") else 0.0,
        1.0 if ps.get("burned") else 0.0,
        1.0 if ps.get("asleep") else 0.0,
        1.0 if ps.get("paralyzed") else 0.0,
        1.0 if ps.get("confused") else 0.0,
    ]


def _global_vec(cur: dict) -> list[float]:
    yi = cur.get("yourIndex", 0)
    return [
        (cur.get("turn") or 0) / 50.0,
        float(yi),
        1.0 if cur.get("firstPlayer") == yi else 0.0,
        1.0 if cur.get("supporterPlayed") else 0.0,
        1.0 if cur.get("stadiumPlayed") else 0.0,
        1.0 if cur.get("energyAttached") else 0.0,
        1.0 if cur.get("retreated") else 0.0,
        (cur.get("turnActionCount") or 0) / 20.0,
        1.0 if (cur.get("stadium")) else 0.0,
    ]


def featurize(obs_dict: dict) -> np.ndarray:
    """Fixed-length float32 vector (length FEATURE_DIM)."""
    cur = (obs_dict or {}).get("current")
    if not cur:
        return np.zeros(FEATURE_DIM, dtype=np.float32)
    yi = cur.get("yourIndex", 0)
    players = cur.get("players") or [{}, {}]
    me = players[yi] if yi < len(players) else {}
    opp = players[1 - yi] if (1 - yi) < len(players) else {}
    vec = _global_vec(cur) + _player_vec(me) + _player_vec(opp)
    return np.asarray(vec, dtype=np.float32)
