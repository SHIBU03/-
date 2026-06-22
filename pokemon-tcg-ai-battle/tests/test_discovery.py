"""Phase D1 tests: descriptors, MAP-Elites archive, variation, evaluation, and a
tiny end-to-end QD run (with resume).

Run: python3 tests/test_discovery.py     (exit 0 = all passed)
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

from discovery.descriptors import behavior, deck_stats          # noqa: E402
from discovery.archive import Archive, cell_of                  # noqa: E402
from discovery.variation import mutate, crossover, is_playable  # noqa: E402
from discovery.evaluate import deck_fitness, random_pilot_factory  # noqa: E402
from discovery.run_qd import run                                # noqa: E402
from env.game_api import read_deck                              # noqa: E402


def test_descriptors_deterministic():
    d = read_deck()
    assert behavior(d) == behavior(d)
    s = deck_stats(d)
    assert s["nPokemon"] + s["nTrainer"] + s["nEnergy"] <= 60
    assert cell_of(d) == cell_of(d)


def test_archive_add_elite_and_saveload():
    d = read_deck()
    a = Archive()
    assert a.add(d, 0.5)
    assert not a.add(d, 0.4)          # worse, same cell -> rejected
    assert a.add(d, 0.7)             # better, same cell -> replace
    assert a.best()["fitness"] == 0.7
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "a.json")
        a.save(p)
        b = Archive.load(p)
    assert b.coverage() == a.coverage()
    assert b.best()["fitness"] == 0.7


def test_variation_legal():
    d = read_deck()
    rng = random.Random(0)
    vocab = list(set(d))
    for _ in range(20):
        child = mutate(d, vocab, rng)
        assert len(child) == 60 and is_playable(child), child[:5]
    x = crossover(d, mutate(d, vocab, rng), rng)
    assert len(x) == 60 and is_playable(x)


def test_evaluate_runs():
    d = read_deck()
    f = deck_fitness(d, [d], pilot_factory=random_pilot_factory(), n_games=2, seed=0)
    assert 0.0 <= f <= 1.0


def test_qd_smoke_and_resume():
    with tempfile.TemporaryDirectory() as t:
        out = os.path.join(t, "qd")
        a = run(8, out, seed=0, pilot="random", n_games=2, checkpoint_every=3)
        assert a.coverage() >= 1
        assert os.path.exists(os.path.join(out, "archive.json"))
        assert os.path.exists(os.path.join(out, "summary.json"))
        # resume continues from saved archive
        a2 = run(4, out, seed=1, pilot="random", n_games=2, resume=True)
        assert a2.coverage() >= a.coverage()


ALL = [
    test_descriptors_deterministic,
    test_archive_add_elite_and_saveload,
    test_variation_legal,
    test_evaluate_runs,
    test_qd_smoke_and_resume,
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
