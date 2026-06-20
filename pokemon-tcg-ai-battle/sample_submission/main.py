import os
import random

from cg.api import to_observation_class
from agent.safety import safe_agent


def read_deck_csv() -> list[int]:
    """Read deck.csv and return a list of 60 card IDs.

    Looks next to this file first (works when packaged), then the Kaggle path.
    """
    candidates = [
        "deck.csv",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck.csv"),
        "/kaggle_simulations/agent/deck.csv",
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r") as file:
                csv = file.read().split("\n")
            return [int(csv[i]) for i in range(60)]
    raise FileNotFoundError("deck.csv not found in: " + ", ".join(candidates))


def _agent_impl(obs_dict: dict) -> list[int]:
    """Baseline policy (Phase 0): return the deck at setup, else a random legal move.

    Intentionally minimal. It is wrapped by ``safe_agent`` below, which guarantees
    a legal, non-crashing return value even if this function misbehaves or raises.
    """
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        # Initial deck selection: return 60 card IDs.
        return read_deck_csv()
    n = len(obs.select.option)
    k = obs.select.maxCount
    if n <= 0 or k <= 0:
        return []
    return random.sample(range(n), min(k, n))


# The exported agent. ``safe_agent`` enforces "never crash, always legal".
agent = safe_agent(_agent_impl, deck_provider=read_deck_csv)
