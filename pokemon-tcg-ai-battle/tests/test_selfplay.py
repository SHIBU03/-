"""Sprint 1 tests: features, replay buffer, self-play collection, parallel
self-play (process-isolated), and head-to-head evaluation.

Run: python3 tests/test_selfplay.py     (exit 0 = all passed)
"""
import os
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
for p in (_REPO, os.path.join(_REPO, "sample_submission")):
    if p not in sys.path:
        sys.path.insert(0, p)

from model.features import featurize, FEATURE_DIM             # noqa: E402
from selfplay.replay_buffer import ReplayBuffer, result_to_z  # noqa: E402
from selfplay.actor import collect_game, parallel_selfplay    # noqa: E402
from eval.cabt_eval import evaluate                            # noqa: E402
from env.game_api import read_deck, random_agent              # noqa: E402


def test_features_shape_and_finite():
    samples, result = collect_game(random_agent, read_deck(), read_deck())
    assert len(samples) > 0
    feat = samples[0][0]
    assert feat.shape == (FEATURE_DIM,), feat.shape
    assert np.all(np.isfinite(feat))
    assert result in (0, 1, 2)


def test_result_to_z():
    assert result_to_z(0, 0) == 1.0 and result_to_z(0, 1) == -1.0
    assert result_to_z(1, 1) == 1.0 and result_to_z(2, 0) == 0.0


def test_buffer_roundtrip():
    buf = ReplayBuffer()
    samples, result = collect_game(random_agent, read_deck(), read_deck())
    buf.add_game(samples, result)
    assert len(buf) == len(samples)
    batch = buf.sample(8)
    assert batch["feats"].shape[1] == FEATURE_DIM
    assert set(np.unique(batch["z"]).tolist()).issubset({-1.0, 0.0, 1.0})
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "buf.npz")
        buf.save(path)
        buf2 = ReplayBuffer.load(path)
    assert len(buf2) == len(buf)
    np.testing.assert_allclose(buf2.as_arrays()["feats"], buf.as_arrays()["feats"])


def test_parallel_selfplay_no_crash():
    agg = parallel_selfplay(40, n_workers=4, agent_name="random", seed=1)
    assert agg["crashes"] == 0, agg
    assert agg["finished"] == 40, agg
    assert agg["games_per_sec"] > 0, agg
    print("parallel:", agg)


def test_eval_runs():
    out = evaluate(random_agent, random_agent, 20, seed=3)
    assert out["A_win"] + out["B_win"] + out["draw"] == 20, out
    print("eval:", out)


ALL = [
    test_features_shape_and_finite,
    test_result_to_z,
    test_buffer_roundtrip,
    test_parallel_selfplay_no_crash,
    test_eval_runs,
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
