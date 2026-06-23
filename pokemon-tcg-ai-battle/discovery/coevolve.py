"""Deck <-> agent coevolution (autocurriculum).

Alternates, for M iterations:
  (A) Agent step: self-play on the current deck archive -> train the value net
      (selfplay.learner.train_value) -> value.json.
  (B) Deck step:  QD (run_qd) piloted by the value-guided MCTS, evaluating each
      candidate against a PFSP sample of the archive (strong, diverse field).

Both the archive (archive.json) and the agent (value.json) improve against an
ever-shifting opponent distribution. Resumable across iterations.

Run on a PC:
    python -m discovery.coevolve --iters 5 --gens-per-iter 60 --selfplay-games 100 --out runs/co1
    python -m discovery.coevolve --iters 5 --out runs/co1 --resume
"""
from __future__ import annotations

import argparse
import json
import os
import random

from discovery.archive import Archive
from discovery.evaluate import pfsp_opponent_sampler
from discovery.run_qd import run
from env.game_api import read_deck, random_agent
from selfplay.actor import collect_game
from selfplay.replay_buffer import ReplayBuffer
from selfplay.learner import train_value
from agent.mcts import make_mcts_agent
from agent.value_net import make_value_fn


def _pilot_factory(value_path, pilot):
    if pilot == "random":
        return lambda: random_agent
    vfn = make_value_fn(value_path)                 # None until value.json exists
    return lambda: make_mcts_agent(value_fn=vfn, max_sims=8, deadline_s=0.03, seed=0)


def collect_archive_dataset(archive, n_games, agent, seed, seed_deck):
    rng = random.Random(seed)
    random.seed(seed)
    decks = ([e["deck"] for e in archive.elites()] if archive else []) + [seed_deck]
    buf = ReplayBuffer()
    for _ in range(n_games):
        d0, d1 = rng.choice(decks), rng.choice(decks)
        try:
            samples, result = collect_game(agent, d0, d1)
            buf.add_game(samples, result)
        except Exception:
            pass
    return buf


def coevolve(out_dir, *, iters=3, gens_per_iter=40, selfplay_games=60, seed=0,
             pilot="mcts", n_games=4, epochs=30, resume=False):
    os.makedirs(out_dir, exist_ok=True)
    value_path = os.path.join(out_dir, "value.json")
    arch_path = os.path.join(out_dir, "archive.json")
    state_path = os.path.join(out_dir, "coevolve_state.json")
    seed_deck = read_deck()

    start = 0
    if resume and os.path.exists(state_path):
        start = json.load(open(state_path)).get("iter", 0)
        print(f"resume coevolve at iter {start}")

    for it in range(start, iters):
        # (A) Agent step: self-play on the archive -> value net
        archive = Archive.load(arch_path) if os.path.exists(arch_path) else None
        agent = _pilot_factory(value_path, pilot)()
        buf = collect_archive_dataset(archive, selfplay_games, agent, seed + it, seed_deck)
        if len(buf) > 50:
            net, m = train_value(buf, epochs=epochs, seed=seed)
            net.save_json(value_path)
            print(f"iter {it} agent: samples={len(buf)} val_mse={m['val_mse']:.3f} "
                  f"(baseline {m['val_baseline_mse']:.3f})")
        else:
            print(f"iter {it} agent: insufficient data ({len(buf)})")

        # (B) Deck step: QD piloted by value-guided MCTS vs PFSP opponents
        run(gens_per_iter, out_dir, seed=seed + it, pilot=pilot, n_games=n_games,
            pilot_factory=_pilot_factory(value_path, pilot),
            opponent_sampler=pfsp_opponent_sampler(3), resume=True)

        json.dump({"iter": it + 1}, open(state_path, "w"))
        print(f"iter {it} done -> {arch_path}, {value_path}")

    print(f"coevolve DONE iters={iters} out={out_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/coevolve")
    ap.add_argument("--iters", type=int, default=3)
    ap.add_argument("--gens-per-iter", type=int, default=40)
    ap.add_argument("--selfplay-games", type=int, default=60)
    ap.add_argument("--n-games", type=int, default=4)
    ap.add_argument("--pilot", choices=["mcts", "random"], default="mcts")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    coevolve(a.out, iters=a.iters, gens_per_iter=a.gens_per_iter,
             selfplay_games=a.selfplay_games, seed=a.seed, pilot=a.pilot,
             n_games=a.n_games, epochs=a.epochs, resume=a.resume)


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    main()
