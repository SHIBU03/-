"""Phase D2 tests: card2vec embeddings, synergy lift, synergy-guided mutation,
and run_qd combo reporting.

Run: python3 tests/test_synergy.py     (exit 0 = all passed)
"""
import os
import random
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
for p in (_REPO, os.path.join(_REPO, "sample_submission")):
    if p not in sys.path:
        sys.path.insert(0, p)

from discovery.embeddings import train_card2vec               # noqa: E402
from discovery.synergy import SynergyStats, synergy_adder      # noqa: E402
from discovery.variation import mutate, is_playable, ALL_IDS   # noqa: E402
from discovery.run_qd import run                               # noqa: E402
from env.game_api import read_deck                             # noqa: E402
import json                                                    # noqa: E402


def test_card2vec_clusters():
    A, B = [101, 102, 103], [201, 202, 203]   # two clean clusters, no shared cards
    corpus = [list(A) for _ in range(6)] + [list(B) for _ in range(6)]
    emb = train_card2vec(corpus, dim=8)
    assert emb is not None and emb.has(101)
    top = [c for c, _ in emb.nearest(101, k=2)]
    assert set(top).issubset({102, 103}), top          # same-cluster cards are nearest


def test_synergy_lift_and_top():
    st = SynergyStats(min_obs=2)
    for i in range(5):
        st.record([10, 11, 100 + i, 200 + i], 1.0)     # strong combo (distinct fillers)
    for i in range(5):
        st.record([20, 21, 300 + i, 400 + i], 0.0)     # weak pair
    assert st.lift(10, 11) > st.lift(20, 21)
    assert st.top_pairs(1)[0][0] == (10, 11)            # uniquely strongest pair


def test_synergy_adder_and_mutation_legal():
    st = SynergyStats(min_obs=2)
    for _ in range(4):
        st.record([10, 11, 1, 2], 1.0)
    add = synergy_adder(st, None, [11, 99, 20, 21], ALL_IDS)
    c = add([10, 1, 2], random.Random(0))
    assert isinstance(c, int)
    # mutation using a synergy adder stays legal/playable
    d = read_deck()
    syn = synergy_adder(SynergyStats(), None, list(set(d)), ALL_IDS)
    rng = random.Random(1)
    for _ in range(10):
        child = mutate(d, list(set(d)), rng, p_syn=0.5, synergy_fn=syn)
        assert len(child) == 60 and is_playable(child)


def test_run_qd_reports_combos():
    with tempfile.TemporaryDirectory() as t:
        out = os.path.join(t, "qd")
        run(12, out, seed=0, pilot="random", n_games=2, p_syn=0.5, emb_every=5,
            checkpoint_every=4)
        with open(os.path.join(out, "summary.json")) as f:
            s = json.load(f)
        assert "discovered_combos" in s and isinstance(s["discovered_combos"], list)
        assert s["coverage"] >= 1


ALL = [
    test_card2vec_clusters,
    test_synergy_lift_and_top,
    test_synergy_adder_and_mutation_legal,
    test_run_qd_reports_combos,
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
