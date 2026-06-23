"""Synergy learning: which card pairs correlate with winning decks (combos).

For each evaluated deck we record (cards present, fitness). A pair's *lift* is
the mean fitness of decks containing BOTH minus the global mean fitness -- a
positive lift means the combo shows up in stronger decks. ``synergy_adder``
proposes a card to add that has high lift with (and/or embeds near) the cards
already in the deck, steering mutation toward combos.
"""
from __future__ import annotations

from itertools import combinations


class SynergyStats:
    def __init__(self, min_obs: int = 3):
        self.min_obs = min_obs
        self.n = 0
        self.fit_sum = 0.0
        self.card_n: dict = {}
        self.pair_fit: dict = {}
        self.pair_n: dict = {}

    def record(self, deck, fitness: float):
        self.n += 1
        self.fit_sum += fitness
        present = sorted(set(deck))
        for c in present:
            self.card_n[c] = self.card_n.get(c, 0) + 1
        for a, b in combinations(present, 2):
            k = (a, b)
            self.pair_fit[k] = self.pair_fit.get(k, 0.0) + fitness
            self.pair_n[k] = self.pair_n.get(k, 0) + 1

    def base(self) -> float:
        return self.fit_sum / self.n if self.n else 0.0

    def lift(self, a, b):
        k = (a, b) if a < b else (b, a)
        n = self.pair_n.get(k, 0)
        if n < self.min_obs:
            return None
        return self.pair_fit[k] / n - self.base()

    def top_pairs(self, n: int = 15):
        base = self.base()
        out = [((a, b), self.pair_fit[(a, b)] / cnt - base, cnt)
               for (a, b), cnt in self.pair_n.items() if cnt >= self.min_obs]
        out.sort(key=lambda x: -x[1])
        return out[:n]


def synergy_adder(stats: SynergyStats, emb, pool, all_ids):
    """Return add(deck, rng) -> card id biased toward synergy with the deck."""
    def add(deck, rng):
        cands = list(pool) if pool else list(all_ids)
        if not cands:
            return rng.choice(all_ids)
        subset = rng.sample(cands, min(len(cands), 40))
        deckcards = list(set(deck))[:20]
        best, best_score = None, -1e18
        for c in subset:
            tot, cnt = 0.0, 0
            for d in deckcards:
                lv = stats.lift(c, d)
                if lv is not None:
                    tot += lv
                    cnt += 1
            score = (tot / cnt) if cnt else 0.0
            if emb is not None and emb.has(c):
                score += 0.5 * emb.sim_to_set(c, deckcards)
            if score > best_score:
                best_score, best = score, c
        return best if best is not None else rng.choice(subset)
    return add
