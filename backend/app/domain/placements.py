"""Place finale de chaque joueur, déduite de la structure du bracket.

start.gg ne nous donne ici que les sets : on retrouve donc le classement final par élimination.
- Vainqueur / finaliste : gagnant / perdant du dernier set (grande finale ou son reset).
- Les autres sont classés selon le round où ils ont été éliminés (dernier set perdu) : plus ce round est
  tardif, meilleure est la place. Les joueurs éliminés au même round sont ex æquo (5-6e, 7-8e, 9-12e…),
  ce qui reproduit le classement standard d'une double élimination.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .chronology import progress_index
from .models import TournamentSet


@dataclass(frozen=True)
class Placement:
    place: int  # meilleure place du groupe (5 pour un 5-6e)
    tied: int  # nombre de joueurs ex æquo (1 si seul)
    opponent_id: str | None  # adversaire du set d'élimination (ou de la grande finale pour le vainqueur)
    opponent_tag: str | None
    opponent_characters: tuple[str, ...]  # personnages de l'adversaire dans ce set, du plus joué au moins joué
    score: str  # score du set vu par le joueur (« 1-3 », « 3-1 », « DQ », « — »)
    is_final: bool  # True pour le vainqueur : le set décrit est la grande finale
    round_text: str


def set_winner(s: TournamentSet) -> int | None:
    if s.winner_index in (0, 1):
        return s.winner_index
    a, b = s.players
    if a.score is not None and b.score is not None and a.score >= 0 and b.score >= 0 and a.score != b.score:
        return 0 if a.score > b.score else 1
    return None


def _score(s: TournamentSet, idx: int) -> str:
    a, b = s.players
    if s.dq or any(p.score is not None and p.score < 0 for p in s.players):
        return "DQ"
    if a.score is None or b.score is None:
        return "—"
    return f"{a.score}-{b.score}" if idx == 0 else f"{b.score}-{a.score}"


def _characters(player) -> tuple[str, ...]:
    return tuple(name for name, _ in Counter(player.characters).most_common(3))


def _placement(place: int, tied: int, s: TournamentSet, idx: int, is_final: bool) -> Placement:
    opp = s.players[1 - idx]
    return Placement(place, tied, opp.player_id, opp.tag, _characters(opp), _score(s, idx), is_final, s.round_text)


def compute_placements(sets: list[TournamentSet], completed: bool = True) -> dict[str, Placement]:
    """`sets` doit être trié chronologiquement. Retourne {} si le tournoi n'est pas terminé
    ou si le dernier set n'a pas de vainqueur identifiable."""
    if not sets or not completed:
        return {}
    final = sets[-1]
    winner = set_winner(final)
    if winner is None:
        return {}

    result: dict[str, Placement] = {}
    result[final.players[winner].player_id] = _placement(1, 1, final, winner, True)
    result[final.players[1 - winner].player_id] = _placement(2, 1, final, 1 - winner, False)

    # Dernier set de chaque autre joueur : (set, index du joueur, a-t-il gagné ce set ?)
    last: dict[str, tuple[TournamentSet, int, bool]] = {}
    for s in sets[:-1]:
        w = set_winner(s)
        for i, p in enumerate(s.players):
            last[p.player_id] = (s, i, w == i)
    # Joueurs absents du dernier tour : on retire champion et finaliste.
    for pid in list(last):
        if pid in result:
            del last[pid]

    # Clé d'élimination : un joueur éliminé (set perdu) à un round donné ; celui dont le dernier set est une
    # victoire (abandon, données incomplètes) est classé juste au-dessus des perdants de ce round.
    groups: dict[float, list[str]] = {}
    for pid, (s, _, won) in last.items():
        groups.setdefault(progress_index(s.round) + (0.5 if won else 0.0), []).append(pid)

    place = 3
    for key in sorted(groups, reverse=True):
        members = groups[key]
        for pid in members:
            s, idx, _ = last[pid]
            result[pid] = _placement(place, len(members), s, idx, False)
        place += len(members)
    return result


def band(place: int) -> str:
    """Couleur associée à une place (classe CSS)."""
    if place <= 3:
        return ("gold", "silver", "bronze")[place - 1]
    if place == 4:
        return "orange"
    if place <= 6:
        return "lightblue"
    if place <= 8:
        return "darkblue"
    return "purple"


def place_label(place: int, tied: int) -> str:
    def ordinal(n: int) -> str:
        return "1er" if n == 1 else f"{n}e"

    return ordinal(place) if tied <= 1 else f"{place}-{place + tied - 1}e"
