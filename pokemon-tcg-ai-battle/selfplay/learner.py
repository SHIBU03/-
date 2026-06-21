"""Learner: train the value network on self-play data (AlphaZero value骨格).

Pipeline: self-play (actor) -> replay buffer (features, z) -> ValueNet (MSE on
the to-move player's final outcome) -> a ``value_fn`` usable as the MCTS leaf
evaluator. Policy targets (visit-count π) are future work; this establishes the
value learning loop.
"""
from __future__ import annotations

import random

import numpy as np

from env.game_api import read_deck, random_agent
from selfplay.actor import collect_game
from selfplay.replay_buffer import ReplayBuffer
from model.network import ValueNet
from model.features import featurize_search_obs


def collect_dataset(n_games: int, agent=None, *, seed: int = 0) -> ReplayBuffer:
    random.seed(seed)
    agent = agent or random_agent
    deck = read_deck()
    buf = ReplayBuffer()
    for _ in range(n_games):
        samples, result = collect_game(agent, deck, deck)
        buf.add_game(samples, result)
    return buf


def train_value(buf: ReplayBuffer, *, epochs: int = 30, hidden: int = 64,
                seed: int = 0, val_frac: float = 0.15):
    arr = buf.as_arrays()
    X, y = arr["feats"], arr["z"]
    n = len(X)
    idx = np.random.default_rng(seed).permutation(n)
    nval = max(1, int(n * val_frac))
    vi, ti = idx[:nval], idx[nval:]
    net = ValueNet(hidden=hidden, seed=seed)
    hist = net.train(X[ti], y[ti], epochs=epochs, seed=seed)

    def mse(I):
        p = net.predict(X[I])
        return float(np.mean((p - y[I]) ** 2))

    mu = float(np.mean(y[ti]))
    metrics = {
        "n": int(n),
        "train_mse": mse(ti),
        "val_mse": mse(vi),
        "val_baseline_mse": float(np.mean((mu - y[vi]) ** 2)),
        "epoch0_mse": hist["history"][0],
        "epochN_mse": hist["history"][-1],
    }
    return net, metrics


def make_value_fn(net: ValueNet):
    """value_fn(observation, root_player)->float in [-1,1] for the MCTS leaf."""
    def value_fn(observation, root_player):
        feat = featurize_search_obs(observation)
        v = float(net.predict(feat)[0])
        yi = observation.current.yourIndex            # features are to-move perspective
        return v if yi == root_player else -v          # zero-sum -> root perspective
    return value_fn
