"""Lightweight value network (numpy MLP) for the value head.

Input: FEATURE_DIM features -> hidden (tanh) -> scalar value in (-1, 1).
Trained on self-play (features -> z, MSE). No GPU / torch needed; tiny by design
so inference stays well within the per-move time budget. Weights are stored as
JSON so a pure-python forward pass can run inside the submission later.
"""
from __future__ import annotations

import json

import numpy as np

from model.features import FEATURE_DIM


class ValueNet:
    def __init__(self, in_dim: int = FEATURE_DIM, hidden: int = 64, seed: int = 0):
        rng = np.random.default_rng(seed)
        self.W1 = (rng.standard_normal((in_dim, hidden)) * (1.0 / np.sqrt(in_dim))).astype(np.float32)
        self.b1 = np.zeros(hidden, dtype=np.float32)
        self.W2 = (rng.standard_normal((hidden, 1)) * (1.0 / np.sqrt(hidden))).astype(np.float32)
        self.b2 = np.zeros(1, dtype=np.float32)

    def forward(self, X):
        z1 = X @ self.W1 + self.b1
        a1 = np.tanh(z1)
        z2 = a1 @ self.W2 + self.b2
        out = np.tanh(z2)
        return out, (X, z1, a1, z2, out)

    def predict(self, X) -> np.ndarray:
        X = np.atleast_2d(np.asarray(X, dtype=np.float32))
        return self.forward(X)[0].ravel()

    def train(self, X, y, *, epochs: int = 30, lr: float = 0.05, batch: int = 256,
              seed: int = 0) -> dict:
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32).reshape(-1, 1)
        n = len(X)
        rng = np.random.default_rng(seed)
        history = []
        for _ in range(epochs):
            idx = rng.permutation(n)
            for s in range(0, n, batch):
                bi = idx[s:s + batch]
                xb, yb = X[bi], y[bi]
                out, (xb_, z1, a1, z2, o) = self.forward(xb)
                m = len(xb)
                # MSE dL/dout
                d_out = (out - yb) * (2.0 / m)
                d_z2 = d_out * (1 - o ** 2)               # tanh'
                dW2 = a1.T @ d_z2
                db2 = d_z2.sum(axis=0)
                d_a1 = d_z2 @ self.W2.T
                d_z1 = d_a1 * (1 - a1 ** 2)
                dW1 = xb_.T @ d_z1
                db1 = d_z1.sum(axis=0)
                self.W2 -= lr * dW2; self.b2 -= lr * db2
                self.W1 -= lr * dW1; self.b1 -= lr * db1
            pred = self.predict(X)
            history.append(float(np.mean((pred - y.ravel()) ** 2)))
        return {"final_mse": history[-1], "history": history}

    def save_json(self, path: str):
        with open(path, "w") as f:
            json.dump({"W1": self.W1.tolist(), "b1": self.b1.tolist(),
                       "W2": self.W2.tolist(), "b2": self.b2.tolist()}, f)

    @classmethod
    def load_json(cls, path: str) -> "ValueNet":
        with open(path) as f:
            d = json.load(f)
        net = cls(in_dim=len(d["W1"]), hidden=len(d["W1"][0]))
        net.W1 = np.asarray(d["W1"], np.float32); net.b1 = np.asarray(d["b1"], np.float32)
        net.W2 = np.asarray(d["W2"], np.float32); net.b2 = np.asarray(d["b2"], np.float32)
        return net
