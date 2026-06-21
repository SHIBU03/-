"""Sprint 2 tests: determinization, Search API forward model, and the PIMC agent.

Run: python3 tests/test_search.py     (exit 0 = all passed)
"""
import contextlib
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
for p in (_REPO, os.path.join(_REPO, "sample_submission")):
    if p not in sys.path:
        sys.path.insert(0, p)

from cg.api import to_observation_class, search_begin, search_step, search_end, search_release  # noqa: E402
from agent.determinize import sample_world                       # noqa: E402
from agent.mcts import make_mcts_agent                           # noqa: E402
from env.game_api import BattleSession, read_deck, random_agent  # noqa: E402
from eval.cabt_eval import evaluate                              # noqa: E402


@contextlib.contextmanager
def decision_session(steps=6, seed=0):
    random.seed(seed)
    s = BattleSession()
    s.start(read_deck(), read_deck())
    try:
        for _ in range(steps):
            if s.result != -1:
                break
            s.select(random_agent(s.obs))
        yield s
    finally:
        s.finish()


def test_determinize_counts():
    with decision_session() as s:
        o = to_observation_class(s.obs)
        w = sample_world(o, read_deck(), random.Random(0))
        cur = o.current
        yi = cur.yourIndex
        me = cur.players[yi]
        opp = cur.players[1 - yi]
        assert len(w["your_deck"]) == me.deckCount, w
        assert len(w["your_prize"]) == len(me.prize)
        assert len(w["opponent_deck"]) == opp.deckCount
        assert len(w["opponent_prize"]) == len(opp.prize)
        assert len(w["opponent_hand"]) == opp.handCount


def test_search_forward_model():
    with decision_session() as s:
        o = to_observation_class(s.obs)
        w = sample_world(o, read_deck(), random.Random(1))
        ss = search_begin(o, w["your_deck"], w["your_prize"], w["opponent_deck"],
                          w["opponent_prize"], w["opponent_hand"], w["opponent_active"])
        assert ss.observation.current is not None
        sid = ss.searchId
        ss2 = search_step(sid, [0])
        assert ss2.observation is not None
        search_release(sid)
        search_end()


def test_mcts_returns_legal():
    agent = make_mcts_agent(deadline_s=0.05, max_sims=8, seed=0)
    with decision_session() as s:
        obs = s.obs
        a = agent(obs)
        sel = obs["select"]
        n = len(sel["option"])
        assert sel["minCount"] <= len(a) <= sel["maxCount"], (a, sel)
        assert all(0 <= x < n for x in a)
        assert len(set(a)) == len(a)


def test_mcts_beats_random():
    mcts = make_mcts_agent(deadline_s=0.06, max_sims=16, seed=1)
    out = evaluate(mcts, random_agent, 16, seed=5)
    assert out["A_win"] > out["B_win"], out
    assert out["A_winrate"] >= 0.55, out
    print("mcts vs random:", out)


ALL = [
    test_determinize_counts,
    test_search_forward_model,
    test_mcts_returns_legal,
    test_mcts_beats_random,
]


def _run():
    failed = 0
    for t in ALL:
        try:
            t()
            print("PASS", t.__name__)
        except Exception as e:
            failed += 1
            import traceback
            traceback.print_exc()
            print("FAIL", t.__name__, "->", repr(e))
    print("\n%d/%d passed" % (len(ALL) - failed, len(ALL)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
