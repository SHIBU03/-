"""Time-budget manager for the 10-minute (600s) per-player match limit.

Allocate each move a soft deadline from the remaining budget and an estimate of
moves left, capped so one move never overspends. Search loops check
``time.monotonic()`` against the deadline and stop with the best action so far.
"""
from __future__ import annotations


class TimeBudget:
    def __init__(self, total_s: float = 600.0, reserve_s: float = 30.0):
        self.total = total_s
        self.reserve = reserve_s
        self.used = 0.0

    def reset(self):
        self.used = 0.0

    def remaining(self) -> float:
        return max(0.0, self.total - self.reserve - self.used)

    def move_deadline(self, est_moves_left: int = 40, cap_s: float = 0.25) -> float:
        per = self.remaining() / max(1, est_moves_left)
        return max(0.0, min(cap_s, per))

    def record(self, dt: float):
        self.used += max(0.0, dt)


# Module-global budget for the live (submitted) agent.
GLOBAL = TimeBudget()


def reset_global(total_s: float = 600.0):
    GLOBAL.total = total_s
    GLOBAL.reset()
