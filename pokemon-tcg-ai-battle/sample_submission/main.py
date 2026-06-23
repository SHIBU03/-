import os

from agent.base import random_agent
from agent.mcts import make_mcts_agent
from agent.safety import safe_agent
from agent.time_budget import reset_global
from agent.value_net import make_value_fn

_HERE = os.path.dirname(os.path.abspath(__file__))
# Optional learned value network (pure-python, no numpy). Falls back to the
# heuristic leaf eval when value.json is absent.
_VALUE_FN = make_value_fn(os.path.join(_HERE, "value.json"))


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


# Determinized-search policy (PIMC). Bundled inside the submission; degrades to a
# random legal move if the Search API is unavailable. Time-capped per move.
_search_agent = make_mcts_agent(deadline_s=0.2, max_sims=64, base_agent=random_agent,
                                use_global_budget=True, value_fn=_VALUE_FN)


def _agent_impl(obs_dict: dict) -> list[int]:
    if obs_dict.get("select") is None:
        # Initial deck-selection phase: reset the per-match time budget and
        # return the 60-card deck.
        reset_global(600.0)
        return read_deck_csv()
    return _search_agent(obs_dict)


# The exported agent. ``safe_agent`` enforces "never crash, always legal".
agent = safe_agent(_agent_impl, deck_provider=read_deck_csv)
