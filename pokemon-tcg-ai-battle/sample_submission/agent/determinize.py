"""Determinization: fill hidden information with plausible card IDs so that
``search_begin`` can build one complete-information world.

Unknown to the to-move player: opponent hand/deck/prize contents, own deck/prize
order, face-down opponent active. We sample these from a card-ID pool (by default
our own deck list -- a reasonable prior for self-play; swap for a meta
distribution later). Counts must match the engine's expectations exactly.
"""
from __future__ import annotations

import random

from cg.api import all_card_data, CardType

_CARDS = {c.cardId: c for c in all_card_data()}


def basic_pokemon_id(pool: list[int]) -> int:
    """A valid Basic Pokémon card ID (for face-down active guesses)."""
    for cid in pool:
        c = _CARDS.get(cid)
        if c and c.basic and c.cardType == CardType.POKEMON:
            return cid
    for cid, c in _CARDS.items():
        if c.basic and c.cardType == CardType.POKEMON:
            return cid
    return pool[0] if pool else 1


def sample_world(o, pool: list[int], rng: random.Random) -> dict:
    """Return kwargs for ``search_begin`` for one determinized world.

    ``o`` is the Observation object given to the agent (has search_begin_input).
    """
    cur = o.current
    yi = cur.yourIndex
    me = cur.players[yi]
    opp = cur.players[1 - yi]
    bpoke = basic_pokemon_id(pool)

    def fill(n):
        return [rng.choice(pool) for _ in range(max(0, n))]

    opp_deck = fill(opp.deckCount)
    if opp_deck:                       # ensure >=1 basic Pokémon (required at setup)
        opp_deck[0] = bpoke

    opp_active = []
    if len(opp.active) > 0 and opp.active[0] is None:
        opp_active = [bpoke]

    return {
        "your_deck": fill(me.deckCount),
        "your_prize": fill(len(me.prize)),
        "opponent_deck": opp_deck,
        "opponent_prize": fill(len(opp.prize)),
        "opponent_hand": fill(opp.handCount),
        "opponent_active": opp_active,
    }
