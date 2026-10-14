#!/usr/bin/env python3
"""Génère des tournois FICTIFS (double élimination réaliste) dans demo/cache, pour tester le site
sans accès à start.gg. Joueurs et résultats sont inventés."""
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.infrastructure.tournament_repository import TournamentRepository  # noqa: E402
from app.domain.models import SetPlayer, Tournament, TournamentSet  # noqa: E402

RNG = random.Random(2709)
TAGS = ["Zephyr", "Kaito", "Nova", "Rhino", "Mistral", "Echo", "Blaze", "Orion", "Sakura", "Titan",
        "Pixel", "Vortex", "Lynx", "Ember", "Quartz", "Draco", "Nimbus", "Falcon", "Onyx", "Jinx",
        "Cobalt", "Sable", "Atlas", "Wisp", "Raven", "Comet", "Bishop", "Tango"]
CHARS = ["Mario", "Fox", "Marth", "Pikachu", "Link", "Kirby", "Steve", "Joker", "Sephiroth", "Hero",
         "Pyra/Mythra", "Mii Swordfighter", "Pokémon Trainer", "Min Min", "Snake", "Sonic", "Ryu",
         "Palutena", "R.O.B.", "Incineroar", "Piranha Plant", "Rosalina & Luma", "Bowser", "Wolf",
         "Peach", "Ness", "Roy", "Terry Bogard"]
SKILL = {t: RNG.gauss(0, 220) for t in TAGS}
MAINS = {t: (CHARS[i % len(CHARS)], RNG.choice(CHARS)) for i, t in enumerate(TAGS)}
PID = {t: str(1000 + i) for i, t in enumerate(TAGS)}


def p_win(a, b):
    return 1 / (1 + 10 ** ((SKILL[b] - SKILL[a]) / 400))


def play_set(a, b, bo=3):
    need = bo // 2 + 1
    wa = wb = 0
    chars = {a: [], b: []}
    while wa < need and wb < need:
        for t in (a, b):
            chars[t].append(MAINS[t][0] if RNG.random() < .8 else MAINS[t][1])
        if RNG.random() < p_win(a, b) * 0.9 + 0.05:
            wa += 1
        else:
            wb += 1
    return (a if wa > wb else b), (wa, wb), chars


class Clock:
    def __init__(self, start):
        self.t = start

    def tick(self):
        self.t += RNG.randint(8, 22) * 60
        return self.t


def pair(lst_a, lst_b=None):
    if lst_b is None:
        return [(lst_a[i], lst_a[i + 1]) for i in range(0, len(lst_a), 2)]
    return list(zip(lst_a, lst_b))


def make_tournament(n, name, start_ts, entrants):
    clock = Clock(start_ts)
    sets, counter = [], [n * 1000]

    def run(matches, rnd, text):
        winners, losers = [], []
        for a, b in matches:
            if a is None or b is None:
                winners.append(a or b)
                losers.append(None)
                continue
            w, sc, chars = play_set(a, b)
            lo = b if w == a else a
            counter[0] += 1
            t = clock.tick()
            sets.append(TournamentSet(
                id=str(counter[0]), round=rnd, round_text=text, completed_at=t, started_at=t - 15 * 60,
                winner_index=0 if w == a else 1, dq=False, phase_group=str(n * 10),
                players=tuple(SetPlayer(PID[x], x, sc[0] if x == a else sc[1], tuple(chars[x]))
                              for x in (a, b))))
            winners.append(w)
            losers.append(lo)
        return winners, losers

    seeds = sorted(entrants, key=lambda t: -(SKILL[t] + RNG.gauss(0, 120)))
    size = 1
    while size < len(seeds):
        size *= 2
    # seeding classique simplifié (1 vs dernier...), les byes vont aux meilleures têtes de série
    seeds += [None] * (size - len(seeds))
    order = []
    half = [seeds[i] for i in range(size // 2)]
    other = [seeds[size - 1 - i] for i in range(size // 2)]
    for a, b in zip(half, other):
        order.append((a, b))
    wb = order
    k = size.bit_length() - 1
    lb = []
    wb_players = None
    for r in range(1, k + 1):
        text = {k: "Winners Final", k - 1: "Winners Semi-Final"}.get(r, f"Winners Round {r}")
        w, l = run(wb, r, text)
        wb_players = w
        if r < k:
            wb = pair(w)
        if r == 1:
            lw, _ = run(pair(l), -1, "Losers Round 1")
            lb = lw
        else:
            lr = 2 * r - 2
            lw, _ = run(pair(lb, l[::-1]), -lr, f"Losers Round {lr}")
            lb = lw
            if r < k:
                lw, _ = run(pair(lb), -(lr + 1), f"Losers Round {lr + 1}")
                lb = lw
    wb_champ, lb_champ = wb_players[0], lb[0]
    w, _ = run([(wb_champ, lb_champ)], k + 1, "Grand Final")
    if w[0] == lb_champ:
        run([(wb_champ, lb_champ)], k + 2, "Grand Final Reset")
    return Tournament(
        key=f"tournament/{name}/event/ultimate-singles",
        url=f"https://www.start.gg/tournament/{name}/event/ultimate-singles",
        slug=f"tournament/{name}/event/ultimate-singles",
        name=name.replace("-", " ").title(), event_name="Ultimate Singles", start_at=start_ts,
        sets=tuple(sets), completed=True)


def main():
    repo = TournamentRepository(ROOT / "demo" / "cache")
    first = int(datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc).timestamp())
    lines = ["# Données FICTIVES de démonstration (lancées par : python run.py serve --demo)"]
    for n in range(1, 9):
        pool = TAGS[:20] if n < 4 else TAGS  # de nouveaux joueurs arrivent au fil du temps
        size = RNG.randint(14, 22) if n < 8 else 24
        entrants = RNG.sample(pool, min(size, len(pool)))
        name = f"demo-weekly-{n}"
        t = make_tournament(n, name, first + (n - 1) * 7 * 86400, entrants)
        repo.save(t)
        lines.append(t.url)
        print(name, len(entrants), "joueurs,", len(t.sets), "sets")
    (ROOT / "demo" / "tournaments.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
