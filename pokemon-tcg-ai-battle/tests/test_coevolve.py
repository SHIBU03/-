"""Phase D3 test: deck<->agent coevolution runs and resumes, producing both an
archive and a learned value net.

Run: python3 tests/test_coevolve.py     (exit 0 = all passed)
"""
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
for p in (_REPO, os.path.join(_REPO, "sample_submission")):
    if p not in sys.path:
        sys.path.insert(0, p)

from discovery.coevolve import coevolve, _pilot_factory, collect_archive_dataset  # noqa: E402
from discovery.evaluate import pfsp_opponent_sampler                             # noqa: E402
from discovery.archive import Archive                                            # noqa: E402
from env.game_api import read_deck, random_agent                                 # noqa: E402


def test_pfsp_sampler():
    a = Archive()
    a.add(read_deck(), 0.9)
    sampler = pfsp_opponent_sampler(2)
    import random
    opp = sampler(a, read_deck(), random.Random(0))
    assert len(opp) >= 1 and all(len(d) == 60 for d in opp)


def test_collect_dataset():
    buf = collect_archive_dataset(None, 4, random_agent, 0, read_deck())
    assert len(buf) > 0


def test_coevolve_and_resume():
    with tempfile.TemporaryDirectory() as t:
        out = os.path.join(t, "co")
        coevolve(out, iters=1, gens_per_iter=6, selfplay_games=30, pilot="random",
                 n_games=2, epochs=8)
        assert os.path.exists(os.path.join(out, "value.json"))
        assert os.path.exists(os.path.join(out, "archive.json"))
        st = json.load(open(os.path.join(out, "coevolve_state.json")))
        assert st["iter"] == 1
        cov1 = Archive.load(os.path.join(out, "archive.json")).coverage()
        # resume one more iteration
        coevolve(out, iters=2, gens_per_iter=6, selfplay_games=30, pilot="random",
                 n_games=2, epochs=8, resume=True)
        st2 = json.load(open(os.path.join(out, "coevolve_state.json")))
        assert st2["iter"] == 2
        cov2 = Archive.load(os.path.join(out, "archive.json")).coverage()
        assert cov2 >= cov1


ALL = [test_pfsp_sampler, test_collect_dataset, test_coevolve_and_resume]


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
