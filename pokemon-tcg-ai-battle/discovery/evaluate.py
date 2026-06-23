"""Deck fitness = win rate of (MCTS pilot on the candidate deck) vs an opponent
*field* (a sample of archive elites + a baseline), with seats alternated.

Evaluating vs a diverse field (not one fixed strong deck) rewards robustness and
avoids rock-paper-scissors collapse (PSRO/PFSP idea). The pilot is configurable:
low-sim MCTS for real runs, random for fast tests.
"""
from __future__ import annotations

import random

from env.game_api import play_one_game, random_agent
from agent.mcts import make_mcts_agent


def mcts_pilot_factory(max_sims=8, deadline_s=0.03):
    return lambda: make_mcts_agent(max_sims=max_sims, deadline_s=deadline_s, seed=0)


def random_pilot_factory():
    return lambda: random_agent


def pfsp_opponent_sampler(k=3, eps=0.05):
    """Sample opponents from the archive weighted toward STRONG elites (face the
    decks that matter), plus the seed deck. PFSP-flavored (cf. league/pfsp)."""
    def sample(archive, seed_deck, rng):
        elites = archive.elites()
        if not elites:
            return [seed_deck]
        decks = [e["deck"] for e in elites]
        weights = [max(e["fitness"], eps) for e in elites]
        idx = rng.choices(range(len(decks)), weights=weights, k=min(k, len(decks)))
        return [decks[i] for i in idx] + [seed_deck]
    return sample


def deck_fitness(deck, opponents, *, pilot_factory, n_games=6, seed=0) -> float:
    if not opponents:
        return 0.0
    rng = random.Random(seed)
    random.seed(seed)
    pilot = pilot_factory()
    opp_pilot = pilot_factory()
    wins = 0
    for gi in range(n_games):
        opp = opponents[rng.randrange(len(opponents))]
        try:
            if gi % 2 == 0:
                r = play_one_game(deck, opp, pilot, opp_pilot)["result"]
                me = 0
            else:
                r = play_one_game(opp, deck, opp_pilot, pilot)["result"]
                me = 1
            if r == me:
                wins += 1
            elif r == 2:
                wins += 0.5                      # draw = half
        except Exception:
            pass                                  # crash-proof: count as loss
    return wins / n_games
