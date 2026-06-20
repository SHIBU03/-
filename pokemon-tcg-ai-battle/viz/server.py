"""Local web visualizer for the cabt self-play virtual space.

Drives games through ``env.game_api.BattleSession`` (the crash-proof wrapper)
and serves a board UI + live metrics. Built to be driven by Playwright MCP for
the end-of-sprint debug gate, and also usable by hand in a browser.

Run:  python3 viz/server.py [--port 8000]      (or: bash tools/run_viz.sh)

Endpoints:
  GET  /                 -> board UI
  GET  /api/state        -> current interactive game snapshot
  GET  /api/metrics      -> auto-run metrics (crashes / finished / timing / RSS)
  POST /api/start {seed} -> start a new interactive game
  POST /api/step {action?} -> advance one step (agent picks if action omitted)
  POST /api/auto {n_games, seed, agent} -> run N games in the background
"""
import argparse
import json
import logging
import os
import random
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logging.disable(logging.CRITICAL)

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
for p in (_REPO, os.path.join(_REPO, "sample_submission")):
    if p not in sys.path:
        sys.path.insert(0, p)

from env.game_api import BattleSession, read_deck, random_agent  # noqa: E402
from cg.api import all_card_data  # noqa: E402
import main as submission  # the wrapped agent  # noqa: E402

DECK = read_deck()
CARD_NAME = {c.cardId: c.name for c in all_card_data()}
AGENTS = {"main": submission.agent, "random": random_agent}

# -- shared state --------------------------------------------------------
LOCK = threading.Lock()
CURRENT = None          # interactive BattleSession
RUNNING = False         # True while an auto-run thread is active

METRICS = {
    "running": False, "games": 0, "finished": 0, "crashes": 0,
    "p0": 0, "p1": 0, "draw": 0, "last_result": None,
    "max_move_ms": 0.0, "total_moves": 0,
    "rss_start_mb": None, "rss_mb": None, "elapsed_s": 0.0,
}


def _rss_mb():
    try:
        with open("/proc/self/statm") as f:
            pages = int(f.read().split()[1])
        return round(pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024), 1)
    except Exception:
        return None


# -- snapshot helpers ----------------------------------------------------
def _poke(p):
    if not p:
        return None
    return {
        "id": p.get("id"),
        "name": CARD_NAME.get(p.get("id"), str(p.get("id"))),
        "hp": p.get("hp"), "maxHp": p.get("maxHp"),
        "energy": len(p.get("energies") or []),
        "tools": len(p.get("tools") or []),
    }


def _player(ps):
    active = ps.get("active") or []
    return {
        "active": _poke(active[0]) if active else None,
        "bench": [_poke(b) for b in (ps.get("bench") or [])],
        "handCount": ps.get("handCount", len(ps.get("hand") or []) if ps.get("hand") else 0),
        "prize": len(ps.get("prize") or []),
        "deckCount": ps.get("deckCount"),
        "discard": len(ps.get("discard") or []),
        "status": [k for k in ("poisoned", "burned", "asleep", "paralyzed", "confused") if ps.get(k)],
    }


def _select(sel):
    if not sel:
        return None
    opts = sel.get("option") or []
    brief = []
    for i, o in enumerate(opts[:40]):
        brief.append({"i": i, "type": o.get("type"), "cardId": o.get("cardId"),
                      "name": CARD_NAME.get(o.get("cardId")) if o.get("cardId") else None})
    return {"type": sel.get("type"), "context": sel.get("context"),
            "minCount": sel.get("minCount"), "maxCount": sel.get("maxCount"),
            "nOptions": len(opts), "options": brief}


def current_snapshot():
    if CURRENT is None or CURRENT.obs is None:
        return {"active_game": False}
    obs = CURRENT.obs
    cur = obs.get("current") or {}
    players = cur.get("players") or [{}, {}]
    return {
        "active_game": True,
        "result": CURRENT.result,
        "turn": cur.get("turn"),
        "yourIndex": cur.get("yourIndex"),
        "players": [_player(players[0]), _player(players[1])],
        "select": _select(obs.get("select")),
        "logs": (obs.get("logs") or [])[:30],
    }


# -- interactive API -----------------------------------------------------
def api_start(body):
    global CURRENT
    if RUNNING:
        return {"error": "auto-run in progress"}
    random.seed(int(body.get("seed", 0)))
    if CURRENT is not None:
        CURRENT.finish()
        CURRENT = None
    s = BattleSession()
    s.start(DECK, DECK)
    CURRENT = s
    return current_snapshot()


def api_step(body):
    global CURRENT
    if RUNNING:
        return {"error": "auto-run in progress"}
    if CURRENT is None or not CURRENT.alive:
        return {"error": "no active game; call /api/start"}
    if CURRENT.result != -1:
        return current_snapshot()
    agent = AGENTS.get(body.get("agent", "main"), submission.agent)
    action = body.get("action")
    if not isinstance(action, list):
        action = agent(CURRENT.obs)
    CURRENT.select(action)
    snap = current_snapshot()
    if CURRENT.result != -1:
        CURRENT.finish()
    return snap


# -- auto-run (background) ------------------------------------------------
def _auto_worker(n_games, seed, agent_name):
    global RUNNING
    agent = AGENTS.get(agent_name, submission.agent)
    random.seed(seed)
    t0 = time.monotonic()
    METRICS.update({"running": True, "games": 0, "finished": 0, "crashes": 0,
                    "p0": 0, "p1": 0, "draw": 0, "last_result": None,
                    "max_move_ms": 0.0, "total_moves": 0,
                    "rss_start_mb": _rss_mb(), "rss_mb": _rss_mb(), "elapsed_s": 0.0})
    try:
        for _ in range(n_games):
            try:
                with BattleSession() as s:
                    s.start(DECK, DECK)
                    while s.result == -1:
                        tm = time.monotonic()
                        action = agent(s.obs)
                        METRICS["max_move_ms"] = max(METRICS["max_move_ms"],
                                                     (time.monotonic() - tm) * 1000.0)
                        METRICS["total_moves"] += 1
                        s.select(action)
                    r = s.result
                METRICS["games"] += 1
                if r in (0, 1, 2):
                    METRICS["finished"] += 1
                    METRICS[{0: "p0", 1: "p1", 2: "draw"}[r]] += 1
                METRICS["last_result"] = r
            except Exception:
                METRICS["crashes"] += 1
                traceback.print_exc()
            METRICS["rss_mb"] = _rss_mb()
            METRICS["elapsed_s"] = round(time.monotonic() - t0, 1)
    finally:
        METRICS["running"] = False
        RUNNING = False


def api_auto(body):
    global RUNNING, CURRENT
    if RUNNING:
        return {"error": "auto-run already in progress"}
    n = max(1, min(int(body.get("n_games", 100)), 5000))
    seed = int(body.get("seed", 0))
    agent_name = body.get("agent", "main")
    if CURRENT is not None:
        CURRENT.finish()
        CURRENT = None
    RUNNING = True
    threading.Thread(target=_auto_worker, args=(n, seed, agent_name), daemon=True).start()
    return {"started": True, "n_games": n, "seed": seed, "agent": agent_name}


# -- HTTP handler --------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj), "application/json")

    def _static(self, name, ctype):
        try:
            with open(os.path.join(_HERE, name), "rb") as f:
                self._send(200, f.read(), ctype)
        except FileNotFoundError:
            self._send(404, "not found", "text/plain")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._static("index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self._static("app.js", "application/javascript")
        if path == "/style.css":
            return self._static("style.css", "text/css")
        if path == "/api/state":
            with LOCK:
                return self._json(current_snapshot())
        if path == "/api/metrics":
            return self._json(METRICS)
        return self._send(404, "not found", "text/plain")

    def do_POST(self):
        path = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            body = json.loads(self.rfile.read(n)) if n else {}
        except Exception:
            body = {}
        try:
            if path == "/api/start":
                with LOCK:
                    return self._json(api_start(body))
            if path == "/api/step":
                with LOCK:
                    return self._json(api_step(body))
            if path == "/api/auto":
                return self._json(api_auto(body))
            return self._send(404, "not found", "text/plain")
        except Exception as e:
            traceback.print_exc()
            return self._json({"error": str(e)}, 500)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"viz server on http://{args.host}:{args.port}  (deck={len(DECK)} cards)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
