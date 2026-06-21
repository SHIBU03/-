"""Model pool with PFSP opponent selection (AlphaStar-style league scaffold).

Holds named checkpoints (agent factories) and the main agent's win/games stats
against each, and samples the next opponent via PFSP. The full league training
orchestration (main / main-exploiter / league-exploiter, periodic resets) builds
on top of this; here we provide the pool + sampling primitives.
"""
from __future__ import annotations

import random

from league.pfsp import sample_opponent


class ModelPool:
    def __init__(self):
        self.entries = []   # {"name", "factory", "wins", "games"}

    def __len__(self):
        return len(self.entries)

    def add(self, name: str, factory):
        self.entries.append({"name": name, "factory": factory, "wins": 0, "games": 0})

    def winrate(self, i: int) -> float:
        e = self.entries[i]
        return e["wins"] / e["games"] if e["games"] else 0.5

    def record(self, i: int, main_won: bool):
        e = self.entries[i]
        e["games"] += 1
        e["wins"] += 1 if main_won else 0

    def sample(self, mode: str = "hard", rng=random) -> int:
        if not self.entries:
            raise ValueError("empty pool")
        wr = [self.winrate(i) for i in range(len(self.entries))]
        return sample_opponent(len(self.entries), wr, mode, rng)

    def make(self, i: int):
        return self.entries[i]["factory"]()
