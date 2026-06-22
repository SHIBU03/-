"""Behavioral descriptors (BCs) for a deck = the diversity axes of the archive.

Chosen to be Pokémon-TCG-meaningful so distinct strategies land in distinct
niches: #Pokémon, #Energy, and #(ex/megaEx) (single- vs multi-prize identity).
More axes (energy type, evolution depth) can be added later.
"""
from __future__ import annotations

from collections import Counter

from cg.api import all_card_data, CardType

CARDS = {c.cardId: c for c in all_card_data()}

_TRAINER = {CardType.ITEM, CardType.TOOL, CardType.SUPPORTER, CardType.STADIUM}
_ENERGY = {CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY}


def deck_stats(deck) -> dict:
    cs = [CARDS.get(c) for c in deck]
    cs = [c for c in cs if c]
    pokemon = [c for c in cs if c.cardType == CardType.POKEMON]
    stages = [2 if c.stage2 else 1 if c.stage1 else 0 for c in pokemon]
    primary = Counter(c.energyType for c in pokemon).most_common(1)
    return {
        "nPokemon": sum(1 for c in cs if c.cardType == CardType.POKEMON),
        "nTrainer": sum(1 for c in cs if c.cardType in _TRAINER),
        "nEnergy": sum(1 for c in cs if c.cardType in _ENERGY),
        "nEx": sum(1 for c in cs if getattr(c, "ex", False) or getattr(c, "megaEx", False)),
        "stageCentroid": (sum(stages) / len(stages)) if stages else 0.0,
        "primaryType": int(primary[0][0]) if primary else -1,
    }


def behavior(deck) -> tuple:
    """The BC tuple the archive bins on: (#Pokémon, #Energy, #ex)."""
    s = deck_stats(deck)
    return (s["nPokemon"], s["nEnergy"], s["nEx"])


def card_name(cid) -> str:
    c = CARDS.get(cid)
    return c.name if c else str(cid)
