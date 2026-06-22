"""MAP-Elites archive: a grid of behavioral niches, each holding its champion.

Diversity is preserved structurally -- a deck only needs to be the best *in its
niche* to survive, so unusual/"weak" cards that shine in some niche are kept.
"""
from __future__ import annotations

import json
import random

from discovery.descriptors import behavior

# BC spec: (name, lo, hi, nbins) for each axis of behavior().
BC_SPEC = [("nPokemon", 0, 30, 10), ("nEnergy", 0, 30, 10), ("nEx", 0, 8, 9)]


def _bin(val, lo, hi, nbins):
    if val <= lo:
        return 0
    if val >= hi:
        return nbins - 1
    return int((val - lo) / (hi - lo) * nbins)


def cell_of(deck) -> tuple:
    bc = behavior(deck)
    return tuple(_bin(bc[i], *BC_SPEC[i][1:]) for i in range(len(BC_SPEC)))


class Archive:
    def __init__(self):
        self.cells = {}   # cell tuple -> {"deck", "fitness", "stats"}

    def __len__(self):
        return len(self.cells)

    def add(self, deck, fitness, stats=None) -> bool:
        """Insert if the cell is empty or this deck beats the incumbent."""
        cell = cell_of(deck)
        cur = self.cells.get(cell)
        if cur is None or fitness > cur["fitness"]:
            self.cells[cell] = {"deck": list(deck), "fitness": float(fitness),
                                "stats": stats or {}}
            return True
        return False

    def elites(self):
        return list(self.cells.values())

    def best(self):
        return max(self.cells.values(), key=lambda e: e["fitness"]) if self.cells else None

    def random_elite(self, rng: random.Random):
        return rng.choice(list(self.cells.values())) if self.cells else None

    def sample_decks(self, k, rng: random.Random):
        es = self.elites()
        if not es:
            return []
        rng.shuffle(es)
        return [e["deck"] for e in es[:k]]

    def vocabulary(self) -> list:
        v = set()
        for e in self.cells.values():
            v.update(e["deck"])
        return list(v)

    def coverage(self) -> int:
        return len(self.cells)

    def save(self, path):
        data = {"bc_spec": BC_SPEC,
                "cells": [{"cell": list(c), **e} for c, e in self.cells.items()]}
        with open(path, "w") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, path) -> "Archive":
        with open(path) as f:
            data = json.load(f)
        a = cls()
        for e in data["cells"]:
            a.cells[tuple(e["cell"])] = {"deck": e["deck"], "fitness": e["fitness"],
                                         "stats": e.get("stats", {})}
        return a
