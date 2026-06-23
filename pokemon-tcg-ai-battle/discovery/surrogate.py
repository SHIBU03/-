"""Deck-fitness surrogate (DSA-ME): predict a deck's fitness cheaply so we only
spend real games on the most promising candidates.

Feature = normalized deck descriptor stats + hashed card-count buckets. Model =
the same tiny MLP as the value net (``model.network.ValueNet``), trained online
on the (deck, measured-fitness) pairs the QD loop accumulates.
"""
from __future__ import annotations

import numpy as np

from model.network import ValueNet
from discovery.descriptors import deck_stats

HASH_BUCKETS = 64
FEAT_DIM = 6 + HASH_BUCKETS


def deck_feature(deck) -> list:
    s = deck_stats(deck)
    base = [
        s["nPokemon"] / 30.0,
        s["nTrainer"] / 40.0,
        s["nEnergy"] / 30.0,
        s["nEx"] / 8.0,
        s["stageCentroid"] / 2.0,
        (s["primaryType"] + 1) / 12.0,
    ]
    buckets = [0.0] * HASH_BUCKETS
    for c in deck:
        buckets[c % HASH_BUCKETS] += 1.0
    return base + [b / 8.0 for b in buckets]


class DeckSurrogate:
    def __init__(self, min_train: int = 40, hidden: int = 32):
        self.X: list = []
        self.y: list = []
        self.net = None
        self.min_train = min_train
        self.hidden = hidden

    def add(self, deck, fitness: float):
        self.X.append(deck_feature(deck))
        self.y.append(2.0 * fitness - 1.0)            # [0,1] -> [-1,1] for tanh head

    def ready(self) -> bool:
        return self.net is not None

    def fit(self, epochs: int = 40) -> bool:
        if len(self.X) < self.min_train:
            return False
        X = np.asarray(self.X, dtype=np.float32)
        y = np.asarray(self.y, dtype=np.float32)
        net = ValueNet(in_dim=X.shape[1], hidden=self.hidden, seed=0)
        net.train(X, y, epochs=epochs)
        self.net = net
        return True

    def predict(self, decks) -> list:
        if self.net is None:
            return [0.5] * len(decks)
        X = np.asarray([deck_feature(d) for d in decks], dtype=np.float32)
        p = self.net.predict(X)
        return [(float(v) + 1.0) / 2.0 for v in p]    # back to [0,1]

    def screen(self, decks, k):
        """Return indices of the top-k decks by predicted fitness."""
        scores = self.predict(decks)
        return sorted(range(len(decks)), key=lambda i: -scores[i])[:max(1, k)]
