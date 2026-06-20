"""Regression tests for the cabt native lifecycle crashes (Sprint 0A).

The native engine aborts the whole process on use-after-free / double-free /
NULL deref. These tests verify that ``BattleSession`` turns those into clean
Python exceptions, that long self-play runs without crashing, and that the
submitted ``main.agent`` never raises and always returns a legal move.

Run directly (no pytest needed):
    python3 tests/test_lifecycle.py     # exit code 0 = all passed
"""
import os
import random
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)  # pokemon-tcg-ai-battle/
for p in (_REPO, os.path.join(_REPO, "sample_submission")):
    if p not in sys.path:
        sys.path.insert(0, p)

from env.game_api import (  # noqa: E402
    BattleSession, BattleError, read_deck, random_agent, play_one_game, selfplay_batch,
)


def _rss_mb():
    """Resident set size in MB (Linux); None if unavailable."""
    try:
        with open("/proc/self/statm") as f:
            pages = int(f.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)
    except Exception:
        return None


def test_select_after_finish_raises():
    deck = read_deck()
    s = BattleSession()
    s.start(deck, deck)
    s.finish()
    try:
        s.select([0])           # would SIGABRT without the guard
    except BattleError:
        return                  # clean exception, process alive
    raise AssertionError("expected BattleError after finish")


def test_double_finish_ok():
    deck = read_deck()
    s = BattleSession()
    s.start(deck, deck)
    s.finish()
    s.finish()                  # would double-free without the guard


def test_double_start_raises():
    deck = read_deck()
    s1 = BattleSession()
    s1.start(deck, deck)
    try:
        s2 = BattleSession()
        try:
            s2.start(deck, deck)
        except BattleError:
            return
        raise AssertionError("expected BattleError on second concurrent start")
    finally:
        s1.finish()


def test_selfplay_no_crash_and_no_leak():
    """200 self-play games: no crash, every game finishes, RSS does not balloon."""
    random.seed(0)
    deck = read_deck()
    n_games = 200
    finished = errors = 0
    rss_warm = None
    for g in range(n_games):
        try:
            r = play_one_game(deck, deck, random_agent)
            if r["result"] in (0, 1, 2):
                finished += 1
        except Exception:
            errors += 1
        if g == 20:                      # baseline after warm-up
            rss_warm = _rss_mb()
    rss_end = _rss_mb()
    assert errors == 0, ("self-play raised", errors)
    assert finished == n_games, ("not all games finished", finished)
    if rss_warm is not None and rss_end is not None:
        growth = rss_end - rss_warm
        assert growth < 64, ("RSS grew %.1f MB over %d games (possible leak)"
                             % (growth, n_games - 20))


def test_main_agent_fuzz():
    """The submitted agent must never raise and always return a legal move."""
    import main  # the wrapped agent
    cases = [
        {"select": None, "logs": [], "current": None},                      # deck phase
        {"select": {"minCount": 1, "maxCount": 1, "option": [{}, {}, {}]}, "logs": [], "current": {"yourIndex": 0}},
        {"select": {"minCount": 0, "maxCount": 0, "option": []}, "logs": [], "current": {}},
        {"select": {"minCount": 2, "maxCount": 3, "option": [{}, {}, {}, {}]}, "logs": [], "current": {}},
        {"select": {"minCount": 0, "maxCount": 2, "option": [{}, {}]}, "logs": [], "current": {}},
    ]
    for c in cases:
        out = main.agent(c)
        assert isinstance(out, list), c
        sel = c["select"]
        if sel is None:
            assert len(out) == 60, ("deck must be 60", out[:5])
        else:
            n = len(sel["option"]); mn = sel["minCount"]; mx = sel["maxCount"]
            assert mn <= len(out) <= mx, (c, out)
            assert all(isinstance(x, int) and 0 <= x < n for x in out), (c, out)
            assert len(set(out)) == len(out), (c, out)


_SUBPROC_CODE = """
import sys
sys.path.insert(0, {repo!r})
import env.game_api as G
d = G.read_deck()
s = G.BattleSession()
s.start(d, d)
s.finish()
try:
    s.select([0])
except G.BattleError:
    print('clean')
""".format(repo=_REPO)


def test_no_abort_subprocess():
    """Misuse, when wrapped, exits cleanly (0) -- not SIGABRT(134)/SIGSEGV(139)."""
    p = subprocess.run([sys.executable, "-c", _SUBPROC_CODE],
                       capture_output=True, text=True)
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    assert "clean" in p.stdout, p.stdout


ALL = [
    test_select_after_finish_raises,
    test_double_finish_ok,
    test_double_start_raises,
    test_selfplay_no_crash_and_no_leak,
    test_main_agent_fuzz,
    test_no_abort_subprocess,
]


def _run():
    failed = 0
    for t in ALL:
        try:
            t()
            print("PASS", t.__name__)
        except Exception as e:
            failed += 1
            print("FAIL", t.__name__, "->", repr(e))
    print("\n%d/%d passed" % (len(ALL) - failed, len(ALL)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
