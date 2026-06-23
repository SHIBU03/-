"""Pure-python value network forward pass for the SUBMITTED agent (no numpy).

Loads JSON weights saved by ``model.network.ValueNet.save_json`` and evaluates
a board (Search Observation) at MCTS leaves. Tiny MLP (37->H->1, tanh), a few
thousand multiplies per leaf -- well within the per-move time budget.
"""
from __future__ import annotations

import json
import math
import os

from agent.features_py import featurize


def _tanh(x):
    return math.tanh(x)


class PyValueNet:
    def __init__(self, W1, b1, W2, b2):
        self.W1 = W1            # in x H
        self.b1 = b1            # H
        self.W2 = W2            # H x 1
        self.b2 = b2            # 1
        self.H = len(b1)

    @classmethod
    def load(cls, path):
        with open(path) as f:
            d = json.load(f)
        return cls(d["W1"], d["b1"], d["W2"], d["b2"])

    def predict(self, x) -> float:
        H = self.H
        W1, b1, W2, b2 = self.W1, self.b1, self.W2, self.b2
        h = [0.0] * H
        for j in range(H):
            s = b1[j]
            for i, xi in enumerate(x):
                s += xi * W1[i][j]
            h[j] = _tanh(s)
        o = b2[0]
        for j in range(H):
            o += h[j] * W2[j][0]
        return _tanh(o)


def make_value_fn(path):
    """Return value_fn(observation, root_player)->float, or None if no weights."""
    if not path or not os.path.exists(path):
        return None
    net = PyValueNet.load(path)

    def value_fn(observation, root_player):
        v = net.predict(featurize(observation))
        yi = getattr(getattr(observation, "current", None), "yourIndex", root_player)
        return v if yi == root_player else -v        # zero-sum -> root perspective

    return value_fn
