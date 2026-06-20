"""Self-play actors: generate training samples by playing games.

- ``collect_game`` plays one game (crash-proof via BattleSession) and records a
  sample at every decision point.
- ``parallel_selfplay`` runs many games across processes using the *spawn* start
  method (each worker loads its own libcg.so -> safe with the native singleton),
  with worker recycling to bound native memory.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import time

from env.game_api import BattleSession, read_deck, random_agent  # loads cg, adds paths
from model.features import featurize
import main as _submission  # the wrapped agent

AGENTS = {"main": _submission.agent, "random": random_agent}


def collect_game(agent, deck0, deck1, *, max_steps: int = 20000):
    """Play one game; return (samples, result).

    samples: list of (feat, action0, n_options, player).
    """
    samples = []
    with BattleSession() as s:
        s.start(deck0, deck1)
        steps = 0
        while s.result == -1 and steps < max_steps:
            obs = s.obs
            cur = obs.get("current") or {}
            player = cur.get("yourIndex", 0)
            sel = obs.get("select") or {}
            n_opt = len(sel.get("option") or [])
            feat = featurize(obs)
            action = agent(obs)
            action0 = action[0] if isinstance(action, list) and action else -1
            samples.append((feat, action0, n_opt, player))
            s.select(action)
            steps += 1
        return samples, s.result


def _worker_run(args):
    """Runs in a spawned child process."""
    n_games, seed, agent_name, out_path = args
    import random as _r
    from selfplay.replay_buffer import ReplayBuffer
    _r.seed(seed)
    agent = AGENTS.get(agent_name, _submission.agent)
    deck = read_deck()
    buf = ReplayBuffer()
    stats = {"games": 0, "finished": 0, "crashes": 0, "samples": 0}
    t0 = time.monotonic()
    for _ in range(n_games):
        try:
            samples, result = collect_game(agent, deck, deck)
            buf.add_game(samples, result)
            stats["games"] += 1
            stats["samples"] += len(samples)
            if result in (0, 1, 2):
                stats["finished"] += 1
        except Exception:
            stats["crashes"] += 1
    stats["elapsed"] = time.monotonic() - t0
    stats["pid"] = os.getpid()
    if out_path:
        buf.save(out_path)
        stats["shard"] = out_path
    return stats


def parallel_selfplay(total_games: int, n_workers: int = 4, *, agent_name: str = "random",
                      seed: int = 0, out_dir: str | None = None) -> dict:
    """Run total_games across n_workers spawned processes. Returns aggregate stats."""
    n_workers = max(1, min(n_workers, total_games))
    per = total_games // n_workers
    rem = total_games - per * n_workers
    args = []
    for w in range(n_workers):
        g = per + (1 if w < rem else 0)
        out = os.path.join(out_dir, f"shard_{w}.npz") if out_dir else None
        args.append((g, seed + w * 1000 + 1, agent_name, out))
    ctx = mp.get_context("spawn")
    t0 = time.monotonic()
    with ctx.Pool(n_workers, maxtasksperchild=1) as pool:
        results = pool.map(_worker_run, args)
    wall = time.monotonic() - t0
    agg = {"games": 0, "finished": 0, "crashes": 0, "samples": 0,
           "workers": n_workers, "wall_s": round(wall, 2)}
    for r in results:
        for k in ("games", "finished", "crashes", "samples"):
            agg[k] += r[k]
    agg["games_per_sec"] = round(agg["finished"] / wall, 1) if wall > 0 else 0.0
    return agg


if __name__ == "__main__":
    print(parallel_selfplay(40, n_workers=4, agent_name="random"))
