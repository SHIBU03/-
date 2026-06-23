"""Value-guided submission tests: dev/bundle feature parity, pure-python value
net matches numpy, value-guided MCTS stays legal, and the bundle is numpy-free.

Run: python3 tests/test_value_submission.py     (exit 0 = all passed)
"""
import contextlib
import json
import os
import random
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_SUB = os.path.join(_REPO, "sample_submission")
for p in (_REPO, _SUB):
    if p not in sys.path:
        sys.path.insert(0, p)

from model.features import featurize as np_featurize           # noqa: E402
from model.network import ValueNet                             # noqa: E402
from agent.features_py import featurize as py_featurize, FEATURE_DIM  # noqa: E402
from agent.value_net import PyValueNet, make_value_fn          # noqa: E402
from agent.mcts import make_mcts_agent                         # noqa: E402
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


def test_feature_parity():
    with decision_session() as s:
        a = np_featurize(s.obs).tolist()
        b = py_featurize(s.obs)
        assert len(b) == FEATURE_DIM
        assert all(abs(x - y) < 1e-4 for x, y in zip(a, b)), list(zip(a, b))[:5]


def test_pyvaluenet_matches_numpy():
    net = ValueNet(seed=3)
    with tempfile.TemporaryDirectory() as t:
        path = os.path.join(t, "value.json")
        net.save_json(path)
        py = PyValueNet.load(path)
    with decision_session(seed=1) as s:
        feat = py_featurize(s.obs)
        v_np = float(net.predict(np.asarray(feat, dtype=np.float32))[0])
        v_py = py.predict(feat)
    assert abs(v_np - v_py) < 1e-3, (v_np, v_py)


def test_value_guided_mcts_legal():
    net = ValueNet(seed=5)
    with tempfile.TemporaryDirectory() as t:
        path = os.path.join(t, "value.json")
        net.save_json(path)
        vfn = make_value_fn(path)
        assert vfn is not None
        agent = make_mcts_agent(deadline_s=0.05, max_sims=8, seed=0, value_fn=vfn)
        with decision_session(seed=2) as s:
            obs = s.obs
            act = agent(obs)
            sel = obs["select"]
            n = len(sel["option"])
            assert sel["minCount"] <= len(act) <= sel["maxCount"]
            assert all(0 <= x < n for x in act) and len(set(act)) == len(act)
    assert make_value_fn(os.path.join("definitely", "missing.json")) is None


def test_bundle_is_numpy_free():
    import glob
    bad = []
    for f in glob.glob(os.path.join(_SUB, "agent", "*.py")):
        src = open(f).read()
        if "import numpy" in src or "import np" in src:
            bad.append(os.path.basename(f))
    assert not bad, ("numpy in bundle:", bad)


ALL = [
    test_feature_parity,
    test_pyvaluenet_matches_numpy,
    test_value_guided_mcts_legal,
    test_bundle_is_numpy_free,
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
    import logging
    logging.disable(logging.CRITICAL)
    sys.exit(_run())
