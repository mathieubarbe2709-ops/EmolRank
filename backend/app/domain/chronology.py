"""Ordre chronologique et vérification de cohérence.

Les calculs ELO dépendent de l'ordre : on trie d'abord (tournois puis sets) et on
contrôle systématiquement la cohérence des dates à chaque calcul.
"""
from __future__ import annotations

import time
from collections import defaultdict

from .models import Issue, Tournament, TournamentSet

DAY = 86400
MAX_ISSUES_PER_CODE = 15


def tournament_date(t: Tournament) -> int | None:
    """Date de référence : début de l'event, sinon premier set terminé."""
    if t.start_at:
        return t.start_at
    times = [s.completed_at for s in t.sets if s.completed_at]
    return min(times) if times else None


def _fmt(ts: int | None) -> str:
    return time.strftime("%d/%m/%Y %H:%M", time.gmtime(ts)) + " UTC" if ts else "?"


def sort_tournaments(tournaments: list[Tournament]) -> tuple[list[Tournament], list[Issue]]:
    """Trie les tournois par date réelle (et non selon l'ordre du fichier texte)."""
    issues: list[Issue] = []
    indexed = list(enumerate(tournaments))
    far_future = 1 << 62

    for _, t in indexed:
        if tournament_date(t) is None:
            issues.append(Issue("error", "TOURNAMENT_NO_DATE",
                                "Aucune date exploitable : le tournoi est placé en dernier.", t.display_name))

    ordered = [t for _, t in sorted(indexed, key=lambda it: (tournament_date(it[1]) or far_future, it[0]))]

    if [t.key for t in ordered] != [t.key for t in tournaments]:
        issues.append(Issue("warning", "TOURNAMENT_FILE_ORDER",
                            "L'ordre du fichier texte ne correspond pas à l'ordre chronologique : "
                            "les tournois sont classés par date de début."))

    for a, b in zip(ordered, ordered[1:]):
        da, db = tournament_date(a), tournament_date(b)
        if da is not None and da == db:
            issues.append(Issue("warning", "TOURNAMENT_SAME_DATE",
                                f"« {a.display_name} » et « {b.display_name} » ont la même date de début ; "
                                "l'ordre du fichier est utilisé pour les départager.", b.display_name))

    # Un tournoi ne doit pas commencer (premier set) avant la fin du précédent.
    for prev, cur in zip(ordered, ordered[1:]):
        prev_end = max((s.completed_at for s in prev.sets if s.completed_at), default=None)
        cur_begin = min((s.completed_at for s in cur.sets if s.completed_at), default=None)
        if prev_end and cur_begin and cur_begin < prev_end:
            issues.append(Issue("error", "TOURNAMENT_OVERLAP",
                                f"Des sets de « {cur.display_name} » ({_fmt(cur_begin)}) sont antérieurs à la fin de "
                                f"« {prev.display_name} » ({_fmt(prev_end)}) : les tournois se chevauchent.",
                                cur.display_name))
    return ordered, issues


def progress_index(rnd: int) -> int:
    """Position théorique d'un round dans une double élimination (départage des égalités).

    Séquence : WR1, LR1, WR2, LR2, LR3, WR3, LR4, LR5, WR4, ...
    """
    if rnd < 0:
        n = -rnd
        return n + n // 2
    return max(0, 3 * rnd - 4)


def sort_sets(t: Tournament) -> tuple[list[TournamentSet], list[Issue]]:
    """Trie les sets d'un tournoi et signale les incohérences."""
    issues: list[Issue] = []
    name = t.display_name
    sets = list(t.sets)
    now = int(time.time())

    def key(item: tuple[int, TournamentSet]):
        pos, s = item
        ts = s.completed_at
        return (ts is None, ts or 0, progress_index(s.round), s.started_at or 0, pos)

    ordered = [s for _, s in sorted(enumerate(sets), key=key)]

    def report(level: str, code: str, subset: list[str], text: str) -> None:
        if not subset:
            return
        shown = ", ".join(subset[:MAX_ISSUES_PER_CODE])
        more = f" (+{len(subset) - MAX_ISSUES_PER_CODE})" if len(subset) > MAX_ISSUES_PER_CODE else ""
        issues.append(Issue(level, code, f"{text} : {shown}{more}", name))

    report("warning", "SET_NO_TIMESTAMP", [str(s.id) for s in sets if s.completed_at is None],
           "Sets sans horodatage de fin (classés selon leur round)")
    report("error", "SET_TIMESTAMP_INVERTED",
           [str(s.id) for s in sets if s.completed_at and s.started_at and s.completed_at < s.started_at],
           "Sets terminés avant d'avoir commencé")
    report("error", "SET_TIMESTAMP_FUTURE",
           [str(s.id) for s in sets if s.completed_at and s.completed_at > now + DAY],
           "Sets datés dans le futur")
    if t.start_at:
        report("warning", "SET_BEFORE_EVENT",
               [str(s.id) for s in sets if s.completed_at and s.completed_at < t.start_at - DAY],
               "Sets terminés plus d'un jour avant le début de l'event")

    # Régression de round : un joueur ne peut pas jouer un round antérieur après un round plus avancé
    # dans la même phase (un WB ne « recule » pas, un LB non plus).
    last_wb: dict[tuple[str, str | None], int] = defaultdict(int)
    last_lb: dict[tuple[str, str | None], int] = defaultdict(int)
    regressions: list[str] = []
    for s in ordered:
        for p in s.players:
            k = (p.player_id, s.phase_group)
            if s.round >= 0:
                if s.round < last_wb[k]:
                    regressions.append(f"{p.tag} (set {s.id})")
                last_wb[k] = max(last_wb[k], s.round)
            else:
                r = -s.round
                if r < last_lb[k]:
                    regressions.append(f"{p.tag} (set {s.id})")
                last_lb[k] = max(last_lb[k], r)
    report("error", "PLAYER_ROUND_REGRESSION", regressions,
           "Ordre des matchs incohérent avec les rounds du bracket")
    return ordered, issues
