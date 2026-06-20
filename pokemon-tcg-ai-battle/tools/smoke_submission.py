"""Smoke test: extract submission.tar.gz to a temp dir and run one self-contained
game using ONLY the packaged files (main.py + agent/ + cg/ + deck.csv).

This proves the submission bundle is self-contained and runs end-to-end.
Usage: python3 tools/smoke_submission.py   (exit 0 = pass)
"""
import os
import subprocess
import sys
import tarfile
import tempfile
import textwrap

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
TAR = os.path.join(_REPO, "submission.tar.gz")

_GAME = textwrap.dedent(
    """
    import sys, logging
    sys.path.insert(0, ".")
    logging.disable(logging.CRITICAL)
    import main
    from cg.game import battle_start, battle_select, battle_finish
    deck = main.read_deck_csv()
    obs, sd = battle_start(deck, deck)
    steps = 0
    while (obs is not None and obs["current"] is not None
           and obs["current"]["result"] == -1 and steps < 20000):
        obs = battle_select(main.agent(obs))
        steps += 1
    res = obs["current"]["result"]
    battle_finish()
    print("SMOKE_OK steps=%d result=%d" % (steps, res))
    """
)


def main() -> int:
    if not os.path.exists(TAR):
        print("missing", TAR, "(run tools/make_submission.sh first)")
        return 1
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(TAR) as t:
            t.extractall(d)
        p = subprocess.run([sys.executable, "-c", _GAME], cwd=d,
                           capture_output=True, text=True)
        tail = (p.stdout + p.stderr).strip().splitlines()[-5:]
        print("\n".join(tail))
        ok = p.returncode == 0 and "SMOKE_OK" in p.stdout
        print("SMOKE", "PASS" if ok else "FAIL", "(exit %d)" % p.returncode)
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
