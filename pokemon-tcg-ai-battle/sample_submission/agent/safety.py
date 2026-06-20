"""Crash-proofing for the *submitted* agent (the one that runs on the ladder).

The Kaggle harness calls ``agent(obs_dict) -> list[int]``. The agent must:
  - NEVER raise (any exception = crash = loss),
  - ALWAYS return a legal selection:
      * length in [minCount, maxCount],
      * each index in [0, len(option)),
      * no duplicates,
  - at the initial deck-selection phase (``obs["select"]`` is None) return a list
    of 60 card IDs instead.

``safe_agent`` wraps any policy function with these guarantees.
"""
from __future__ import annotations

import functools
import sys
import traceback


def _counts(sel):
    """Return (min_count, max_count, n_options) from a SelectData dict/object."""
    if sel is None:
        return 0, 0, 0
    if isinstance(sel, dict):
        n = len(sel.get("option") or [])
        return int(sel.get("minCount", 0) or 0), int(sel.get("maxCount", 0) or 0), n
    opt = getattr(sel, "option", None) or []
    return int(getattr(sel, "minCount", 0) or 0), int(getattr(sel, "maxCount", 0) or 0), len(opt)


def normalize_selection(sel_list, min_count, max_count, n_options):
    """Coerce an arbitrary selection into a legal one (in-range, unique, sized)."""
    if n_options <= 0 or max_count <= 0:
        return []
    seen = set()
    cleaned = []
    for x in (sel_list or []):
        if isinstance(x, bool):           # bool is an int subclass; reject it
            continue
        if isinstance(x, int) and 0 <= x < n_options and x not in seen:
            seen.add(x)
            cleaned.append(x)
            if len(cleaned) >= max_count:
                break
    if len(cleaned) < min_count:          # pad with unused indices to reach min
        for i in range(n_options):
            if i not in seen:
                cleaned.append(i)
                seen.add(i)
                if len(cleaned) >= min_count:
                    break
    return cleaned


def legal_fallback(sel):
    """A guaranteed-legal selection for the given SelectData (dict or object)."""
    min_count, max_count, n = _counts(sel)
    if n <= 0 or max_count <= 0:
        return []
    k = max(min_count, 1)                  # do *something* rather than nothing
    k = min(k, max_count, n)
    return list(range(k))


def safe_agent(agent_fn, deck_provider=None):
    """Wrap a policy so it never raises and always returns a legal selection."""

    @functools.wraps(agent_fn)
    def wrapped(obs_dict):
        sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None

        # Deck-selection phase: must return 60 card IDs.
        if sel is None:
            try:
                result = agent_fn(obs_dict)
                if (isinstance(result, list) and len(result) == 60
                        and all(isinstance(x, int) and not isinstance(x, bool) for x in result)):
                    return result
            except Exception:
                traceback.print_exc(file=sys.stderr)
            if deck_provider is not None:
                try:
                    return deck_provider()
                except Exception:
                    traceback.print_exc(file=sys.stderr)
            return []

        # Normal selection phase.
        min_c, max_c, n = _counts(sel)
        try:
            result = agent_fn(obs_dict)
            norm = normalize_selection(result, min_c, max_c, n)
            if (min_c <= len(norm) <= max_c
                    and all(0 <= x < n for x in norm)
                    and len(set(norm)) == len(norm)):
                return norm
        except Exception:
            traceback.print_exc(file=sys.stderr)
        return legal_fallback(sel)

    return wrapped
