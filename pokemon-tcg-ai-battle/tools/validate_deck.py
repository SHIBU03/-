"""Validate a 60-card deck against basic Pokémon TCG construction rules.

Checks: exactly 60 cards; all card IDs known to the engine; <=4 copies of any
non-basic-energy card; at most 1 ACE SPEC total.

Usage:
    python3 tools/validate_deck.py [path/to/deck.csv]
Exit 0 = valid, 1 = invalid.
"""
import logging
import os
import sys
from collections import Counter

logging.disable(logging.CRITICAL)

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_SUBMISSION = os.path.join(_REPO, "sample_submission")
if _SUBMISSION not in sys.path:
    sys.path.insert(0, _SUBMISSION)

from cg.api import all_card_data, CardType  # noqa: E402


def load_deck(path: str) -> list[int]:
    with open(path) as f:
        lines = [x.strip() for x in f.read().split("\n") if x.strip() != ""]
    return [int(x) for x in lines]


def validate(deck: list[int]) -> list[str]:
    errors: list[str] = []
    cards = {c.cardId: c for c in all_card_data()}

    if len(deck) != 60:
        errors.append(f"deck has {len(deck)} cards, expected 60")

    unknown = sorted({cid for cid in deck if cid not in cards})
    if unknown:
        errors.append(f"unknown card IDs: {unknown}")

    ace_total = 0
    for cid, k in Counter(deck).items():
        c = cards.get(cid)
        if c is None:
            continue
        if c.cardType != CardType.BASIC_ENERGY and k > 4:
            errors.append(f"{c.name} (id {cid}) x{k} exceeds 4-copy limit")
        if getattr(c, "aceSpec", False):
            ace_total += k
    if ace_total > 1:
        errors.append(f"ACE SPEC total {ace_total} exceeds 1")

    return errors


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_SUBMISSION, "deck.csv")
    deck = load_deck(path)
    errors = validate(deck)
    if errors:
        print(f"INVALID deck: {path}")
        for e in errors:
            print("  -", e)
        return 1
    print(f"VALID deck: {path} (60 cards)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
