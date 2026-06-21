"""Determinized search (PIMC) over the cabt Search API.

For a single-choice decision (minCount==maxCount==1, i.e. every MAIN turn:
play / attach / evolve / attack / retreat / end), evaluate each root option by
flat Monte-Carlo over determinized worlds:

  for each simulation (until a time/sim budget):
    - pick a root option by UCB1,
    - sample one determinized world and build it with search_begin,
    - apply the root option, then random-rollout to a depth cap or terminal,
    - score the leaf with a heuristic (prize lead + board), backprop to the option.
  choose the most-visited root option.

Multi-select / complex contexts fall back to a base agent. Everything is wrapped
so the agent NEVER raises and always returns a legal selection. Bundle-safe:
depends only on cg/ and the local agent package (no dev-only ``env``).
"""
from __future__ import annotations

import math
import random
import time

from cg.api import (to_observation_class, search_begin, search_step,
                    search_end, search_release)
from agent.base import read_deck, random_agent
from agent.determinize import sample_world
from agent.time_budget import GLOBAL

ROLLOUT_CAP = 24

# Lightweight diagnostics (search_begin success/failure under the live engine).
STATS = {"sims": 0, "sb_ok": 0, "sb_err": 0}


def heuristic_value(observation, root_player: int) -> float:
    """Value in [-1, 1] for ``root_player`` from a search-world Observation."""
    cur = observation.current
    if cur is None:
        return 0.0
    if cur.result != -1:
        if cur.result == 2:
            return 0.0
        return 1.0 if cur.result == root_player else -1.0
    me = cur.players[root_player]
    opp = cur.players[1 - root_player]
    val = (len(opp.prize) - len(me.prize)) / 6.0          # fewer of MY prizes left = winning

    def hp_ratio(ps):
        a = ps.active
        if a and a[0] is not None:
            mh = a[0].maxHp or 0
            return (a[0].hp or 0) / mh if mh else 0.0
        return 0.0

    val += 0.15 * (hp_ratio(me) - hp_ratio(opp))
    val += 0.05 * (len(me.bench) - len(opp.bench)) / 5.0
    return max(-1.0, min(1.0, val))


def _rollout_action(observation, rng: random.Random):
    sel = observation.select
    if sel is None:
        return []
    n = len(sel.option or [])
    if n == 0:
        return []
    if sel.maxCount == 1 and sel.minCount >= 1:
        return [rng.randrange(n)]
    k = sel.minCount if sel.minCount > 0 else min(1, sel.maxCount)
    k = min(k, sel.maxCount, n)
    return rng.sample(range(n), k) if k > 0 else []


def _ucb_select(visits, values, c: float) -> int:
    total = sum(visits)
    for i, v in enumerate(visits):
        if v == 0:
            return i
    log_t = math.log(total)
    return max(range(len(visits)),
               key=lambda i: values[i] / visits[i] + c * math.sqrt(log_t / visits[i]))


def search_action(obs_dict, *, pool, rng, base_agent, deadline_s=0.15,
                  max_sims=48, c=1.2, value_fn=None):
    sel = obs_dict.get("select")
    if not sel or not (sel.get("minCount") == 1 and sel.get("maxCount") == 1):
        return base_agent(obs_dict)
    n = len(sel.get("option") or [])
    if n <= 1:
        return [0] if n == 1 else base_agent(obs_dict)

    o = to_observation_class(obs_dict)
    root_player = o.current.yourIndex
    visits = [0] * n
    values = [0.0] * n
    t0 = time.monotonic()
    sims = 0
    while sims < max_sims and (time.monotonic() - t0) < deadline_s:
        opt = _ucb_select(visits, values, c)
        v = None
        sid = None
        try:
            w = sample_world(o, pool, rng)
            ss = search_begin(o, w["your_deck"], w["your_prize"], w["opponent_deck"],
                              w["opponent_prize"], w["opponent_hand"], w["opponent_active"])
            sid = ss.searchId
            STATS["sb_ok"] += 1
            ss = search_step(sid, [opt])
            depth = 0
            while True:
                cur = ss.observation.current
                if cur is None or cur.result != -1 or depth >= ROLLOUT_CAP:
                    break
                if ss.observation.select is None:
                    break
                ss = search_step(sid, _rollout_action(ss.observation, rng))
                depth += 1
            leaf_cur = ss.observation.current
            if value_fn is not None and leaf_cur is not None and leaf_cur.result == -1:
                v = value_fn(ss.observation, root_player)   # NN value at non-terminal leaf
            else:
                v = heuristic_value(ss.observation, root_player)
        except Exception:
            v = None
            if sid is None:
                STATS["sb_err"] += 1
        finally:
            if sid is not None:
                try:
                    search_release(sid)
                except Exception:
                    pass
        if v is not None:
            visits[opt] += 1
            values[opt] += v
        sims += 1
        STATS["sims"] += 1
    try:
        search_end()
    except Exception:
        pass

    if sum(visits) == 0:
        return base_agent(obs_dict)
    best = max(range(n), key=lambda i: (visits[i], values[i] / visits[i] if visits[i] else -9.0))
    return [best]


def make_mcts_agent(pool=None, *, deadline_s=0.15, max_sims=48, base_agent=None,
                    seed=None, use_global_budget=False, value_fn=None):
    """Return an agent(obs_dict)->list[int] backed by determinized search.

    ``value_fn(observation, root_player)->float`` optionally replaces the
    heuristic leaf evaluation (e.g. a learned value network). Default None keeps
    the bundle-safe heuristic.
    """
    pool = pool or read_deck()
    base_agent = base_agent or random_agent
    rng = random.Random(seed)

    def agent(obs_dict):
        try:
            dl = deadline_s
            t0 = time.monotonic()
            if use_global_budget:
                dl = max(0.02, min(deadline_s, GLOBAL.move_deadline(cap_s=deadline_s)))
            action = search_action(obs_dict, pool=pool, rng=rng, base_agent=base_agent,
                                   deadline_s=dl, max_sims=max_sims, value_fn=value_fn)
            if use_global_budget:
                GLOBAL.record(time.monotonic() - t0)
            return action
        except Exception:
            try:
                return base_agent(obs_dict)
            except Exception:
                sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
                if sel is None:
                    return read_deck()
                n = len(sel.get("option") or [])
                return [0] if n else []

    return agent
