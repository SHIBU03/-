"""Prioritized Fictitious Self-Play (PFSP) opponent weighting.

Given the main agent's win rate vs each candidate opponent, weight opponents so
training focuses where it matters (AlphaStar). ``hard`` prioritizes tough
opponents f(x)=(1-x)^2; ``even`` prioritizes similar-strength f(x)=x(1-x).
"""
from __future__ import annotations

import random


def pfsp_weights(winrates, mode: str = "hard") -> list[float]:
    ws = []
    for x in winrates:
        x = min(max(float(x), 0.0), 1.0)
        if mode == "hard":
            w = (1.0 - x) ** 2
        elif mode == "even":
            w = x * (1.0 - x)
        else:                       # uniform
            w = 1.0
        ws.append(max(w, 1e-6))
    s = sum(ws)
    return [w / s for w in ws]


def sample_opponent(n: int, winrates, mode: str = "hard", rng=random) -> int:
    if n <= 0:
        raise ValueError("no opponents")
    w = pfsp_weights(winrates, mode)
    return rng.choices(range(n), weights=w, k=1)[0]
