"""Phase D4 tests: deck-fitness surrogate (DSA-ME), parallel evaluation, and a
batched/parallel/surrogate QD run.

Run: python3 tests/test_surrogate.py     (exit 0 = all passed)
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

from discovery.surrogate import DeckSurrogate, deck_feature, FEAT_DIM   # noqa: E402
from discovery.evaluate import parallel_eval                           # noqa: E402
from discovery.variation import mutate                                 # noqa: E402
from discovery.run_qd import run                                       # noqa: E402
from env.game_api import read_deck                                     # noqa: E402


def _distinct_decks():
    a = read_deck()
    rng = random.Random(0)
    b = a
    for _ in range(10):
        b = mutate(b, list(set(b)), rng, k_max=2, p_new=0.5)
    return a, b


def test_deck_feature_shape():
    f = deck_feature(read_deck())
    assert len(f) == FEAT_DIM and all(isinstance(x, float) for x in f)


def test_surrogate_learns_separation():
    a, b = _distinct_decks()
    s = DeckSurrogate(min_train=40)
    for _ in range(30):
        s.add(a, 1.0)
        s.add(b, 0.0)
    assert s.fit(epochs=80)
    pa, pb = s.predict([a, b])
    assert pa > pb, (pa, pb)


def test_screen_returns_k():
    a, b = _distinct_decks()
    s = DeckSurrogate(min_train=2)
    s.add(a, 1.0); s.add(b, 0.0); s.fit(epochs=20)
    idx = s.screen([a, b, a, b], 2)
    assert len(idx) == 2 and all(0 <= i < 4 for i in idx)


def test_parallel_eval():
    decks = [read_deck() for _ in range(3)]
    fits = parallel_eval(decks, [read_deck()], {"pilot": "random"},
                         n_games=2, seed=0, workers=2)
    assert len(fits) == 3 and all(0.0 <= f <= 1.0 for f in fits)


def test_run_qd_batch_parallel_surrogate():
    with tempfile.TemporaryDirectory() as t:
        out = os.path.join(t, "qd")
        a = run(3, out, seed=0, pilot="random", n_games=2, batch=2, workers=2,
                surrogate=True, screen_k=1, checkpoint_every=2)
        assert a.coverage() >= 1
        assert os.path.exists(os.path.join(out, "summary.json"))


ALL = [
    test_deck_feature_shape,
    test_surrogate_learns_separation,
    test_screen_returns_k,
    test_parallel_eval,
    test_run_qd_batch_parallel_surrogate,
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
