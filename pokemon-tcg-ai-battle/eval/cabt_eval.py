"""Head-to-head evaluation between two agents (local proxy metric).

Seats are alternated so neither agent gets a permanent first-/second-player
advantage. Returns A's win/loss/draw counts and win rate. Note: local win rate
is a development proxy only -- final decisions use the production ladder.
"""
from __future__ import annotations

import random

from env.game_api import play_one_game, read_deck, random_agent


def evaluate(agent_a, agent_b, n_games: int = 50, *, seed: int = 0,
             deck_a=None, deck_b=None) -> dict:
    random.seed(seed)
    deck_a = deck_a or read_deck()
    deck_b = deck_b or read_deck()
    a_win = b_win = draw = 0
    for g in range(n_games):
        a_is_p0 = (g % 2 == 0)
        if a_is_p0:
            res = play_one_game(deck_a, deck_b, agent_a, agent_b)["result"]
            a_seat = 0
        else:
            res = play_one_game(deck_b, deck_a, agent_b, agent_a)["result"]
            a_seat = 1
        if res == 2:
            draw += 1
        elif res == a_seat:
            a_win += 1
        else:
            b_win += 1
    return {
        "A_win": a_win, "B_win": b_win, "draw": draw, "n": n_games,
        "A_winrate": round(a_win / max(1, n_games), 3),
    }


if __name__ == "__main__":
    print(evaluate(random_agent, random_agent, 30))
