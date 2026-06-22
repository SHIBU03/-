"""MAP-Elites deck discovery loop (serial, checkpointed, resumable).

Run on a PC:
    cd pokemon-tcg-ai-battle
    python -m discovery.run_qd --generations 300 --out runs/qd1            # MCTS pilot
    python -m discovery.run_qd --generations 300 --out runs/qd1 --resume   # continue
    python -m discovery.run_qd --generations 50 --pilot random --n-games 2 # fast smoke

Outputs (in --out): archive.json (resume), summary.json, best_deck.csv.
CPU only (no GPU). Each generation is checkpointed so it resumes cleanly.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random

from discovery.archive import Archive
from discovery.descriptors import deck_stats, card_name
from discovery.evaluate import deck_fitness, mcts_pilot_factory, random_pilot_factory
from discovery.variation import mutate, crossover
from env.game_api import read_deck


def _opponents(archive, seed_deck, rng, k=3):
    opp = archive.sample_decks(k, rng)
    opp.append(seed_deck)
    return opp


def run(generations, out_dir, *, seed=0, pilot="mcts", n_games=6, k_opp=3,
        p_cross=0.2, checkpoint_every=10, resume=False):
    os.makedirs(out_dir, exist_ok=True)
    arch_path = os.path.join(out_dir, "archive.json")
    rng = random.Random(seed)
    pilot_factory = mcts_pilot_factory() if pilot == "mcts" else random_pilot_factory()
    seed_deck = read_deck()

    if resume and os.path.exists(arch_path):
        archive = Archive.load(arch_path)
        print(f"resumed: coverage={archive.coverage()}")
    else:
        archive = Archive()
        f0 = deck_fitness(seed_deck, [seed_deck], pilot_factory=pilot_factory,
                          n_games=max(2, n_games // 2), seed=seed)
        archive.add(seed_deck, f0, deck_stats(seed_deck))
        print(f"seeded: fitness={f0:.2f} coverage={archive.coverage()}")

    for g in range(generations):
        vocab = archive.vocabulary()
        p1 = archive.random_elite(rng)["deck"]
        if rng.random() < p_cross and len(archive) > 1:
            p2 = archive.random_elite(rng)["deck"]
            child = crossover(p1, p2, rng)
        else:
            child = mutate(p1, vocab, rng)
        fit = deck_fitness(child, _opponents(archive, seed_deck, rng, k_opp),
                           pilot_factory=pilot_factory, n_games=n_games, seed=seed + g + 1)
        added = archive.add(child, fit, deck_stats(child))
        if added or (g % 25 == 0):
            b = archive.best()
            print(f"gen {g}: cov={archive.coverage()} added={added} "
                  f"childFit={fit:.2f} best={b['fitness']:.2f}")
        if (g + 1) % checkpoint_every == 0:
            archive.save(arch_path)

    archive.save(arch_path)
    _write_summary(archive, seed_deck, out_dir)
    b = archive.best()
    print(f"DONE coverage={archive.coverage()} best_fitness={b['fitness']:.2f}")
    return archive


def _write_summary(archive, seed_deck, out_dir):
    best = archive.best()
    seed_set = set(seed_deck)
    novel = sorted({c for c in archive.vocabulary() if c not in seed_set})
    summary = {
        "coverage": archive.coverage(),
        "best_fitness": best["fitness"],
        "best_stats": best["stats"],
        "n_novel_cards": len(novel),
        "novel_cards": [{"id": c, "name": card_name(c)} for c in novel[:60]],
        "top_cells": sorted(
            [{"cell": list(k), "fitness": v["fitness"], "stats": v["stats"]}
             for k, v in archive.cells.items()],
            key=lambda x: -x["fitness"])[:15],
    }
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    with open(os.path.join(out_dir, "best_deck.csv"), "w", newline="") as f:
        w = csv.writer(f)
        for cid in best["deck"]:
            w.writerow([cid])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", type=int, default=200)
    ap.add_argument("--out", default="runs/qd1")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--pilot", choices=["mcts", "random"], default="mcts")
    ap.add_argument("--n-games", type=int, default=6)
    ap.add_argument("--k-opp", type=int, default=3)
    ap.add_argument("--checkpoint-every", type=int, default=10)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    run(a.generations, a.out, seed=a.seed, pilot=a.pilot, n_games=a.n_games,
        k_opp=a.k_opp, checkpoint_every=a.checkpoint_every, resume=a.resume)


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    main()
