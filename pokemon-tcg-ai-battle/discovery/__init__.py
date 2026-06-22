"""Deck-discovery virtual space (Quality-Diversity / MAP-Elites over decks).

Dev-only. Evolves an *archive* of diverse, high-performing decks: each
behavioral niche keeps its champion, so strong-in-a-niche "weak" cards are not
buried (the answer to greedy meta-collapse). Builds on the self-play engine,
the MCTS pilot, and the deck-legality checker.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
for _p in (_REPO, os.path.join(_REPO, "sample_submission")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
