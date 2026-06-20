"""Replay buffer for self-play samples.

A sample is (features, action0, n_options, player, z) where:
  - features : np.float32[FEATURE_DIM]   board state at decision time
  - action0  : int   the first chosen option index (-1 if none)   (policy target;
               upgraded to a visit-count distribution in Sprint 2)
  - n_options: int   number of legal options at that decision
  - player   : int   the to-move player index (0/1) at that step
  - z        : float outcome from that player's view (+1 win / -1 loss / 0 draw)
"""
from __future__ import annotations

import numpy as np

from model.features import FEATURE_DIM


def result_to_z(result: int, player: int) -> float:
    if result == 2:
        return 0.0
    return 1.0 if result == player else -1.0


class ReplayBuffer:
    def __init__(self, capacity: int = 200_000):
        self.capacity = capacity
        self.feats: list[np.ndarray] = []
        self.actions: list[int] = []
        self.nopts: list[int] = []
        self.players: list[int] = []
        self.z: list[float] = []

    def __len__(self) -> int:
        return len(self.feats)

    def add(self, feat, action0, n_options, player, z):
        self.feats.append(np.asarray(feat, dtype=np.float32))
        self.actions.append(int(action0))
        self.nopts.append(int(n_options))
        self.players.append(int(player))
        self.z.append(float(z))
        if len(self.feats) > self.capacity:        # drop oldest (ring)
            for lst in (self.feats, self.actions, self.nopts, self.players, self.z):
                del lst[0]

    def add_game(self, samples, result: int):
        """samples: list of (feat, action0, n_options, player)."""
        for feat, action0, n_opt, player in samples:
            self.add(feat, action0, n_opt, player, result_to_z(result, player))

    def sample(self, batch_size: int, rng: np.random.Generator | None = None) -> dict:
        rng = rng or np.random.default_rng()
        n = len(self.feats)
        idx = rng.integers(0, n, size=min(batch_size, n))
        return {
            "feats": np.stack([self.feats[i] for i in idx]),
            "actions": np.asarray([self.actions[i] for i in idx], dtype=np.int32),
            "nopts": np.asarray([self.nopts[i] for i in idx], dtype=np.int32),
            "players": np.asarray([self.players[i] for i in idx], dtype=np.int8),
            "z": np.asarray([self.z[i] for i in idx], dtype=np.float32),
        }

    def as_arrays(self) -> dict:
        if not self.feats:
            return {"feats": np.zeros((0, FEATURE_DIM), np.float32),
                    "actions": np.zeros(0, np.int32), "nopts": np.zeros(0, np.int32),
                    "players": np.zeros(0, np.int8), "z": np.zeros(0, np.float32)}
        return {
            "feats": np.stack(self.feats),
            "actions": np.asarray(self.actions, dtype=np.int32),
            "nopts": np.asarray(self.nopts, dtype=np.int32),
            "players": np.asarray(self.players, dtype=np.int8),
            "z": np.asarray(self.z, dtype=np.float32),
        }

    def save(self, path: str):
        np.savez_compressed(path, **self.as_arrays())

    @classmethod
    def load(cls, path: str) -> "ReplayBuffer":
        d = np.load(path)
        buf = cls()
        buf.feats = list(d["feats"].astype(np.float32))
        buf.actions = list(map(int, d["actions"]))
        buf.nopts = list(map(int, d["nopts"]))
        buf.players = list(map(int, d["players"]))
        buf.z = list(map(float, d["z"]))
        return buf
