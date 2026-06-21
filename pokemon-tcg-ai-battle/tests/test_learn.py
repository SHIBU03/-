"""Sprint 3 tests: value network learning, value_fn + MCTS integration, PFSP/league.

Run: python3 tests/test_learn.py     (exit 0 = all passed)
"""
import contextlib
import os
import random
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
for p in (_REPO, os.path.join(_REPO, "sample_submission")):
    if p not in sys.path:
        sys.path.insert(0, p)

from cg.api import to_observation_class                          # noqa: E402
from model.network import ValueNet                              # noqa: E402
from selfplay.learner import collect_dataset, train_value, make_value_fn  # noqa: E402
from league.pfsp import pfsp_weights, sample_opponent           # noqa: E402
from league.league import ModelPool                             # noqa: E402
from agent.mcts import make_mcts_agent                          # noqa: E402
from env.game_api import BattleSession, read_deck, random_agent  # noqa: E402


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


def test_valuenet_fits_synthetic():
    rng = np.random.default_rng(0)
    X = rng.standard_normal((400, 37)).astype(np.float32)
    y = np.tanh(X[:, 0] * 2.0).astype(np.float32)        # learnable signal
    net = ValueNet(seed=0)
    h = net.train(X, y, epochs=60, lr=0.1)
    assert h["history"][-1] < h["history"][0] * 0.5, h["history"][:1] + h["history"][-1:]


def test_value_training_on_selfplay():
    buf = collect_dataset(40, seed=1)
    assert len(buf) > 100
    net, m = train_value(buf, epochs=25, seed=1)
    print("value train metrics:", m)
    assert np.isfinite(m["val_mse"])
    assert m["epochN_mse"] < m["epoch0_mse"], m          # training reduced loss


def test_value_fn_range_and_mcts():
    net = ValueNet(seed=2)
    vf = make_value_fn(net)
    with decision_session() as s:
        o = to_observation_class(s.obs)
        v = vf(o, o.current.yourIndex)
        assert -1.0 <= v <= 1.0, v
    # NN-guided MCTS returns a legal action
    agent = make_mcts_agent(deadline_s=0.05, max_sims=8, seed=0, value_fn=vf)
    with decision_session(seed=3) as s:
        obs = s.obs
        a = agent(obs)
        sel = obs["select"]
        n = len(sel["option"])
        assert sel["minCount"] <= len(a) <= sel["maxCount"]
        assert all(0 <= x < n for x in a) and len(set(a)) == len(a)


def test_pfsp_weights():
    w = pfsp_weights([0.1, 0.5, 0.9], mode="hard")
    assert abs(sum(w) - 1.0) < 1e-9
    assert w[0] > w[2]                                    # tougher (lower winrate) prioritized
    even = pfsp_weights([0.0, 0.5, 1.0], mode="even")
    assert even[1] == max(even)                           # similar-strength prioritized
    i = sample_opponent(3, [0.1, 0.5, 0.9], rng=random.Random(0))
    assert 0 <= i < 3


def test_model_pool():
    pool = ModelPool()
    pool.add("random", lambda: random_agent)
    pool.add("mcts", lambda: make_mcts_agent(max_sims=4))
    pool.record(0, True); pool.record(0, False); pool.record(1, False)
    assert pool.winrate(0) == 0.5 and pool.winrate(1) == 0.0
    assert 0 <= pool.sample(rng=random.Random(0)) < 2
    assert callable(pool.make(0))


ALL = [
    test_valuenet_fits_synthetic,
    test_value_training_on_selfplay,
    test_value_fn_range_and_mcts,
    test_pfsp_weights,
    test_model_pool,
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
