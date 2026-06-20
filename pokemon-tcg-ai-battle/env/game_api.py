"""Safe lifecycle wrapper around the cabt Game API + self-play helpers.

WHY THIS EXISTS
---------------
The native engine (libcg.so / cg.dll) exposes a *process-global* battle pointer
(``cg.sim.Battle.battle_ptr``) and does NOT guard against:
  - use-after-free : calling battle_select/visualize_data after battle_finish()
  - double-free    : calling battle_finish() twice
  - NULL deref     : the pointer left dangling (None) after finish
Any of these aborts the whole Python process (SIGABRT 134 / SIGSEGV 139). These
were reproduced on this repo; see ``docs/PLAN_v1.2.md`` section 1.

``BattleSession`` makes the lifecycle safe *from Python* by:
  - tracking an ``alive`` flag and NEVER calling a native function once a battle
    has ended (NULL-ing the pointer is not enough; passing NULL still segfaults,
    so the call itself must be suppressed),
  - making ``finish()`` idempotent,
  - allowing only one live session per process (the native pointer is a
    singleton). Sequential reuse (start -> finish -> start ...) is fine; parallel
    self-play must use separate processes (Sprint 1).
"""
from __future__ import annotations

import os
import random
import sys

# Make the submission's ``cg`` package importable from anywhere.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)  # pokemon-tcg-ai-battle/
_SUBMISSION = os.path.join(_REPO, "sample_submission")
if _SUBMISSION not in sys.path:
    sys.path.insert(0, _SUBMISSION)

from cg import game as _game             # noqa: E402
from cg.sim import Battle                # noqa: E402
from cg.api import to_observation_class  # noqa: E402

DEFAULT_DECK_PATH = os.path.join(_SUBMISSION, "deck.csv")


class BattleError(RuntimeError):
    """Raised on Game API misuse or engine-reported start failure."""


def read_deck(path: str = DEFAULT_DECK_PATH) -> list[int]:
    """Read a 60-card deck (list of card IDs) from a csv of one ID per line."""
    with open(path, "r") as f:
        lines = f.read().split("\n")
    return [int(lines[i]) for i in range(60)]


class BattleSession:
    """Context-managed, crash-proof wrapper for one cabt battle."""

    _live = False  # process-global guard (native ptr is a singleton)

    def __init__(self) -> None:
        self.alive = False
        self._finished = False
        self.obs: dict | None = None
        self.start_data = None

    # -- lifecycle -------------------------------------------------------
    def start(self, deck0: list[int], deck1: list[int]) -> dict:
        if BattleSession._live:
            raise BattleError("Another BattleSession is already live in this process.")
        obs, start_data = _game.battle_start(deck0, deck1)
        self.start_data = start_data
        if obs is None:
            raise BattleError(
                "battle_start failed (errorPlayer=%s errorType=%s)."
                % (getattr(start_data, "errorPlayer", None),
                   getattr(start_data, "errorType", None))
            )
        self.alive = True
        self._finished = False
        BattleSession._live = True
        self.obs = obs
        return obs

    def select(self, select_list: list[int]) -> dict:
        if not self.alive:
            raise BattleError("select() on a non-live session (battle already finished).")
        self.obs = _game.battle_select(select_list)
        return self.obs

    def visualize(self) -> str:
        if not self.alive:
            raise BattleError("visualize() on a non-live session.")
        return _game.visualize_data()

    def finish(self) -> None:
        """Free native resources. Idempotent and crash-proof."""
        if self._finished:
            return
        if self.alive:
            try:
                _game.battle_finish()
            finally:
                # Drop the dangling pointer and refuse further native calls.
                Battle.battle_ptr = None
                self.alive = False
                BattleSession._live = False
        self._finished = True

    # -- helpers ---------------------------------------------------------
    @property
    def result(self) -> int | None:
        """-1 = ongoing, 0 = p0 win, 1 = p1 win, 2 = draw, None = no current."""
        if self.obs is None or self.obs.get("current") is None:
            return None
        return self.obs["current"]["result"]

    def observation(self):
        if self.obs is None:
            raise BattleError("No observation yet; call start() first.")
        return to_observation_class(self.obs)

    def __enter__(self) -> "BattleSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.finish()
        return False

    def __del__(self):
        try:
            self.finish()
        except Exception:
            pass


# -- self-play utilities -------------------------------------------------

def random_agent(obs_dict: dict, rng: random.Random = random) -> list[int]:
    """A trivial *legal* agent for self-play/testing (not strong)."""
    sel = obs_dict.get("select")
    if sel is None:                       # deck-selection phase (kaggle contract)
        return read_deck()
    n = len(sel.get("option") or [])
    if n == 0:
        return []
    max_c = sel.get("maxCount", 0) or 0
    min_c = sel.get("minCount", 0) or 0
    k = max_c if max_c > 0 else min_c
    k = min(k, n)
    if k <= 0:
        return []
    return rng.sample(range(n), k)


def play_one_game(deck0, deck1, agent0, agent1=None, *, max_steps: int = 20000) -> dict:
    """Play one game to completion via BattleSession. Returns {'result','steps'}."""
    if agent1 is None:
        agent1 = agent0
    with BattleSession() as s:
        obs = s.start(deck0, deck1)
        steps = 0
        while s.result == -1 and steps < max_steps:
            cur = obs.get("current")
            yi = cur.get("yourIndex", 0) if cur else 0
            action = (agent0 if yi == 0 else agent1)(obs)
            obs = s.select(action)
            steps += 1
        return {"result": s.result, "steps": steps}


def selfplay_batch(n_games: int, agent0, agent1=None, *, deck=None, seed: int = 0) -> dict:
    """Run ``n_games`` sequentially; collect results and a (caught) crash count."""
    if deck is None:
        deck = read_deck()
    counts = {"p0": 0, "p1": 0, "draw": 0, "other": 0, "error": 0}
    total_steps = 0
    for _ in range(n_games):
        try:
            r = play_one_game(deck, deck, agent0, agent1)
            total_steps += r["steps"]
            counts[{0: "p0", 1: "p1", 2: "draw"}.get(r["result"], "other")] += 1
        except Exception:
            counts["error"] += 1
    return {"counts": counts, "total_steps": total_steps, "n_games": n_games}
