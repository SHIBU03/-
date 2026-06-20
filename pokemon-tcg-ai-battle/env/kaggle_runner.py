"""Official cabt runner wrapper: kaggle_environments make('cabt') + env.run.

This is the *production-equivalent* verification path (slower than the dev Game
API). Decks are returned by each agent at the deck-selection phase (obs.select
is None) -> the env calls battle_start with those 60-card lists. Reward is
win=+1 / lose=-1 / draw=0; each player has a 600s overage budget.

The cabt env bundles its OWN cg engine; our submission's cg/ is used only by the
dev self-play harness. To avoid loading libcg.so twice, prefer running this in a
process that does NOT import ``env.game_api``.

Install: pip install --ignore-installed blinker kaggle-environments==1.30.1
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_SUBMISSION = os.path.join(_REPO, "sample_submission")


def run_match(agent0=None, agent1=None, *, debug: bool = False) -> dict:
    """Run one cabt match. Agents default to the submission's ``main.agent``."""
    if _SUBMISSION not in sys.path:
        sys.path.insert(0, _SUBMISSION)
    if agent0 is None or agent1 is None:
        import main  # the submission's wrapped agent
        agent0 = agent0 or main.agent
        agent1 = agent1 or main.agent
    import kaggle_environments as ke
    env = ke.make("cabt", debug=debug)
    env.run([agent0, agent1])
    last = env.steps[-1]
    return {
        "steps": len(env.steps),
        "statuses": [s.status for s in last],
        "rewards": [s.reward for s in last],
        "done": env.done,
    }


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    print(run_match(debug=True))
