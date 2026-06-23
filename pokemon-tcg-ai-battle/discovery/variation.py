"""Variation operators: legal deck mutation & crossover.

Mutations swap a few cards, mostly drawing from the evolving *vocabulary* of
viable cards (exploitation) but occasionally introducing ANY legal card
(exploration) -- this is how novel/"buried" cards enter play. Every result is
checked for basic legality + playability (>=1 Basic Pokémon).
"""
from __future__ import annotations

import random
from collections import Counter

from cg.api import CardType
from discovery.descriptors import CARDS

ALL_IDS = list(CARDS.keys())
BASIC_POKEMON = [cid for cid, c in CARDS.items()
                 if c.basic and c.cardType == CardType.POKEMON]


def is_playable(deck) -> bool:
    if len(deck) != 60:
        return False
    cnt = Counter(deck)
    has_basic = False
    ace = 0
    for cid, k in cnt.items():
        c = CARDS.get(cid)
        if c is None:
            return False
        if c.basic and c.cardType == CardType.POKEMON:
            has_basic = True
        if c.cardType != CardType.BASIC_ENERGY and k > 4:
            return False
        if getattr(c, "aceSpec", False):
            ace += k
    return has_basic and ace <= 1


def mutate(deck, vocab, rng: random.Random, *, k_max=2, p_new=0.25, p_syn=0.0,
           synergy_fn=None, tries=25):
    pool = vocab if vocab else list(deck)
    for _ in range(tries):
        d = list(deck)
        for _ in range(rng.randint(1, k_max)):
            d.pop(rng.randrange(len(d)))
            u = rng.random()
            if synergy_fn is not None and u < p_syn:
                c = synergy_fn(d, rng)                   # combo: synergy-guided add
                d.append(c if c is not None else rng.choice(pool))
            elif u < p_syn + p_new:
                d.append(rng.choice(ALL_IDS))           # explore: any legal card
            else:
                d.append(rng.choice(pool))              # exploit: known-viable card
        if is_playable(d):
            return d
    return list(deck)


def crossover(d1, d2, rng: random.Random, *, tries=25):
    for _ in range(tries):
        half = rng.sample(d1, 30) + rng.sample(d2, 30)
        if len(half) == 60 and is_playable(half):
            return half
    return list(d1)
