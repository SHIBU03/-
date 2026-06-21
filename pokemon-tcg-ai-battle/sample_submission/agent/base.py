"""Bundle-safe helpers for the submitted agent.

These have NO dependency on the dev-only ``env`` package, so they work both in
the repo (dev) and inside the submission tarball (main.py + agent/ + cg/).
"""
from __future__ import annotations

import os
import random as _random


def read_deck() -> list[int]:
    """Read the 60-card deck.csv (next to main.py, or the Kaggle path)."""
    here = os.path.dirname(os.path.abspath(__file__))           # .../agent
    sub = os.path.dirname(here)                                 # .../ (submission root)
    for path in ("deck.csv", os.path.join(sub, "deck.csv"),
                 "/kaggle_simulations/agent/deck.csv"):
        if os.path.exists(path):
            with open(path) as f:
                lines = f.read().split("\n")
            return [int(lines[i]) for i in range(60)]
    raise FileNotFoundError("deck.csv not found")


def random_agent(obs_dict, rng=_random) -> list[int]:
    """Trivial legal agent (baseline / rollout fallback)."""
    sel = obs_dict.get("select")
    if sel is None:
        return read_deck()
    n = len(sel.get("option") or [])
    if n == 0:
        return []
    max_c = sel.get("maxCount", 0) or 0
    min_c = sel.get("minCount", 0) or 0
    k = max_c if max_c > 0 else min_c
    k = min(k, n)
    return rng.sample(range(n), k) if k > 0 else []
