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
from discovery.evaluate import (deck_fitness, mcts_pilot_factory,
                                random_pilot_factory, parallel_eval)
from discovery.variation import mutate, crossover, ALL_IDS
from discovery.embeddings import train_card2vec
from discovery.synergy import SynergyStats, synergy_adder
from discovery.surrogate import DeckSurrogate
from env.game_api import read_deck


def _opponents(archive, seed_deck, rng, k=3):
    opp = archive.sample_decks(k, rng)
    opp.append(seed_deck)
    return opp


def run(generations, out_dir, *, seed=0, pilot="mcts", n_games=6, k_opp=3,
        p_cross=0.2, p_syn=0.3, emb_every=30, checkpoint_every=10, resume=False,
        pilot_factory=None, opponent_sampler=None,
        batch=1, workers=1, surrogate=False, screen_k=None, value_path=None,
        surrogate_every=10):
    os.makedirs(out_dir, exist_ok=True)
    arch_path = os.path.join(out_dir, "archive.json")
    rng = random.Random(seed)
    if pilot_factory is None:
        pilot_factory = mcts_pilot_factory() if pilot == "mcts" else random_pilot_factory()
    cfg = {"pilot": pilot, "value_path": value_path}     # picklable for workers
    seed_deck = read_deck()
    stats = SynergyStats()
    emb = None
    surro = DeckSurrogate() if surrogate else None

    if resume and os.path.exists(arch_path):
        archive = Archive.load(arch_path)
        print(f"resumed: coverage={archive.coverage()}")
    else:
        archive = Archive()
        f0 = deck_fitness(seed_deck, [seed_deck], pilot_factory=pilot_factory,
                          n_games=max(2, n_games // 2), seed=seed)
        archive.add(seed_deck, f0, deck_stats(seed_deck))
        stats.record(seed_deck, f0)
        if surro is not None:
            surro.add(seed_deck, f0)
        print(f"seeded: fitness={f0:.2f} coverage={archive.coverage()}")

    ev = 0
    for g in range(generations):
        vocab = archive.vocabulary()
        if emb_every and g % emb_every == 0 and archive.coverage() >= 5:
            emb = train_card2vec([e["deck"] for e in archive.elites()]) or emb
        syn = synergy_adder(stats, emb, vocab, ALL_IDS)
        cands = []
        for _ in range(max(1, batch)):
            p1 = archive.random_elite(rng)["deck"]
            if rng.random() < p_cross and len(archive) > 1:
                cands.append(crossover(p1, archive.random_elite(rng)["deck"], rng))
            else:
                cands.append(mutate(p1, vocab, rng, p_syn=p_syn, synergy_fn=syn))
        if surro is not None and surro.ready() and screen_k:     # DSA-ME screening
            cands = [cands[i] for i in surro.screen(cands, screen_k)]
        opps = (opponent_sampler(archive, seed_deck, rng) if opponent_sampler
                else _opponents(archive, seed_deck, rng, k_opp))
        if workers > 1:
            fits = parallel_eval(cands, opps, cfg, n_games=n_games,
                                 seed=seed + ev + 1, workers=workers)
        else:
            fits = [deck_fitness(d, opps, pilot_factory=pilot_factory,
                                 n_games=n_games, seed=seed + ev + i + 1)
                    for i, d in enumerate(cands)]
        for d, f in zip(cands, fits):
            archive.add(d, f, deck_stats(d))
            stats.record(d, f)
            if surro is not None:
                surro.add(d, f)
            ev += 1
        if surro is not None and g % surrogate_every == 0:
            surro.fit()
        if g % 25 == 0:
            b = archive.best()
            print(f"gen {g}: cov={archive.coverage()} evals={ev} best={b['fitness']:.2f}")
        if (g + 1) % checkpoint_every == 0:
            archive.save(arch_path)

    archive.save(arch_path)
    _write_summary(archive, seed_deck, out_dir, stats)
    b = archive.best()
    print(f"DONE coverage={archive.coverage()} best_fitness={b['fitness']:.2f} "
          f"evals={ev} combos={len(stats.top_pairs(15))}")
    return archive


def _write_summary(archive, seed_deck, out_dir, stats=None):
    best = archive.best()
    seed_set = set(seed_deck)
    novel = sorted({c for c in archive.vocabulary() if c not in seed_set})
    combos = []
    if stats is not None:
        for (a, b), lift, cnt in stats.top_pairs(15):
            combos.append({"a": a, "b": b, "name_a": card_name(a), "name_b": card_name(b),
                           "lift": round(lift, 3), "count": cnt})
    summary = {
        "coverage": archive.coverage(),
        "best_fitness": best["fitness"],
        "best_stats": best["stats"],
        "n_novel_cards": len(novel),
        "novel_cards": [{"id": c, "name": card_name(c)} for c in novel[:60]],
        "discovered_combos": combos,
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
    ap.add_argument("--p-syn", type=float, default=0.3, help="prob. of synergy-guided swap")
    ap.add_argument("--emb-every", type=int, default=30, help="retrain card2vec every N gens")
    ap.add_argument("--batch", type=int, default=1, help="candidates generated per generation")
    ap.add_argument("--workers", type=int, default=1, help="parallel eval processes (spawn)")
    ap.add_argument("--surrogate", action="store_true", help="DSA-ME surrogate screening")
    ap.add_argument("--screen-k", type=int, default=None, help="real-eval only top-k of batch")
    ap.add_argument("--value-path", default=None, help="value.json for value-guided pilot")
    ap.add_argument("--checkpoint-every", type=int, default=10)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    run(a.generations, a.out, seed=a.seed, pilot=a.pilot, n_games=a.n_games,
        k_opp=a.k_opp, p_syn=a.p_syn, emb_every=a.emb_every, batch=a.batch,
        workers=a.workers, surrogate=a.surrogate, screen_k=a.screen_k,
        value_path=a.value_path, checkpoint_every=a.checkpoint_every, resume=a.resume)


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    main()
