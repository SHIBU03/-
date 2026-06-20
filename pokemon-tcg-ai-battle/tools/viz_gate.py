"""End-of-sprint debug gate (automated judgment over HTTP).

Drives the running visualizer server like Playwright would, but headlessly:
  - interactive smoke: start a game + a few steps,
  - auto-run N games, poll metrics until done,
  - assert crashes == 0, finished == N, RSS does not balloon.

Usage: python3 tools/viz_gate.py [N] [base_url]   (exit 0 = PASS)
The Playwright MCP browser pass is the same flow against the same UI.
"""
import json
import sys
import time
import urllib.request

N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"


def _post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(req, timeout=60))


def _get(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=60))


def main():
    # 1) interactive smoke
    s = _post("/api/start", {"seed": 1})
    assert s.get("active_game"), s
    for _ in range(5):
        s = _post("/api/step", {"agent": "main"})
    print("interactive: turn=%s result=%s" % (s.get("turn"), s.get("result")))

    # 2) auto-run gate
    r = _post("/api/auto", {"n_games": N, "seed": 0, "agent": "main"})
    assert r.get("started"), r
    while True:
        time.sleep(0.5)
        m = _get("/api/metrics")
        if not m["running"]:
            break
    print("auto metrics:", json.dumps(m))

    rss_growth = None
    if m["rss_start_mb"] and m["rss_mb"]:
        rss_growth = round(m["rss_mb"] - m["rss_start_mb"], 1)
    ok = (m["crashes"] == 0 and m["finished"] == N and (rss_growth is None or rss_growth < 64))
    print("GATE %s (crashes=%d finished=%d/%d rss_growth=%s max_move_ms=%.1f)"
          % ("PASS" if ok else "FAIL", m["crashes"], m["finished"], N, rss_growth, m["max_move_ms"]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
