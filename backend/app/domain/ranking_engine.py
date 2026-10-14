"""Moteur de classement : rejoue les tournois dans l'ordre chronologique et produit
un instantané du classement après chacun d'eux."""
from __future__ import annotations

from collections import Counter

from .characters import character_key, character_label
from .chronology import sort_sets, sort_tournaments
from .elo import EloConfig, bracket_weight, set_deltas
from .placements import compute_placements
from .models import (Issue, MatchRecord, PlayerEntry, RankingResult, Snapshot,
                     Tournament, TournamentSet)


class _PlayerState:
    __slots__ = ("player_id", "tag", "elo", "wins", "losses", "tournaments", "chars", "char_names")

    def __init__(self, player_id: str, tag: str, elo: float):
        self.player_id = player_id
        self.tag = tag
        self.elo = elo
        self.wins = 0
        self.losses = 0
        self.tournaments = 0
        self.chars: Counter[str] = Counter()
        self.char_names: dict[str, str] = {}


def _usable(s: TournamentSet) -> tuple[bool, int | None]:
    """Un set compte s'il est terminé, sans DQ, avec deux joueurs distincts et un vainqueur."""
    a, b = s.players
    if s.dq or not a.player_id or not b.player_id or a.player_id == b.player_id:
        return False, None
    winner = s.winner_index
    if winner is None and a.score is not None and b.score is not None and a.score != b.score:
        winner = 0 if a.score > b.score else 1
    return winner in (0, 1), winner


def _score_text(s: TournamentSet, idx: int) -> str:
    a, b = s.players
    if a.score is None or b.score is None or a.score < 0 or b.score < 0:
        return "—"
    return f"{a.score}-{b.score}" if idx == 0 else f"{b.score}-{a.score}"


def compute_rankings(tournaments: list[Tournament], config: EloConfig) -> RankingResult:
    ordered, issues = sort_tournaments(tournaments)
    players: dict[str, _PlayerState] = {}
    snapshots: list[Snapshot] = []
    previous_rank: dict[str, int] = {}

    for index, tournament in enumerate(ordered):
        sets, set_issues = sort_sets(tournament)
        issues.extend(set_issues)

        # Tout joueur apparaissant dans le tournoi est inscrit avec l'ELO initial.
        elo_before: dict[str, float] = {}
        participants: set[str] = set()
        for s in sets:
            for p in s.players:
                if not p.player_id:
                    continue
                state = players.get(p.player_id)
                if state is None:
                    state = players[p.player_id] = _PlayerState(p.player_id, p.tag, config.initial)
                state.tag = p.tag or state.tag  # pseudo le plus récent
                if p.player_id not in participants:
                    participants.add(p.player_id)
                    elo_before[p.player_id] = state.elo
                    state.tournaments += 1

        matches: dict[str, list[MatchRecord]] = {pid: [] for pid in participants}
        wins_here: Counter[str] = Counter()
        losses_here: Counter[str] = Counter()
        counted = skipped = 0

        for s in sets:
            # Les personnages sont comptés même si le set n'entre pas dans l'ELO.
            for p in s.players:
                if p.player_id in players:
                    for name in p.characters:
                        key = character_key(name)
                        if key:
                            players[p.player_id].chars[key] += 1
                            players[p.player_id].char_names.setdefault(key, name)

            ok, winner = _usable(s)
            if not ok:
                skipped += 1
                continue
            counted += 1
            a, b = s.players
            sa, sb = players[a.player_id], players[b.player_id]
            weight = bracket_weight(s.bracket, config)
            delta_a, delta_b = set_deltas(sa.elo, sb.elo, winner == 0, weight, config)
            sa.elo += delta_a
            sb.elo += delta_b
            winner_p, loser_p = (a, b) if winner == 0 else (b, a)
            players[winner_p.player_id].wins += 1
            players[loser_p.player_id].losses += 1
            wins_here[winner_p.player_id] += 1
            losses_here[loser_p.player_id] += 1
            for idx, (me, opp, st, d) in enumerate(((a, b, sa, delta_a), (b, a, sb, delta_b))):
                matches[me.player_id].append(MatchRecord(
                    opponent_id=opp.player_id, opponent_tag=opp.tag, won=(winner == idx),
                    score=_score_text(s, idx), bracket=s.bracket, round_text=s.round_text,
                    weight=weight, delta=d, elo_after=st.elo))

        # Inactivité : chaque joueur déjà inscrit qui a manqué ce tournoi perd `decay_per_tournament`.
        for pid, st in players.items():
            if pid not in participants:
                elo_before[pid] = st.elo
                st.elo -= config.decay_per_tournament

        snapshots.append(_snapshot(index, tournament, players, previous_rank, elo_before,
                                   participants, wins_here, losses_here, matches, counted, skipped))
        snapshots[-1].placements = compute_placements(sets, tournament.completed)
        previous_rank = {e.player_id: e.rank for e in snapshots[-1].entries}

    return RankingResult(snapshots, issues)


def _main_character(state: _PlayerState) -> dict | None:
    if not state.chars:
        return None
    key, games = state.chars.most_common(1)[0]
    return {"key": key, "name": character_label(key, state.char_names.get(key)), "games": games}


def _snapshot(index, tournament, players, previous_rank, elo_before, participants,
              wins_here, losses_here, matches, counted, skipped) -> Snapshot:
    ranked = sorted(players.values(), key=lambda p: (-p.elo, p.tag.lower(), p.player_id))
    entries: list[PlayerEntry] = []
    for rank, st in enumerate(ranked, start=1):
        before = elo_before.get(st.player_id, st.elo)
        entries.append(PlayerEntry(
            player_id=st.player_id, tag=st.tag, rank=rank,
            previous_rank=previous_rank.get(st.player_id),
            elo=st.elo, elo_before=before, elo_delta=st.elo - before,
            wins=st.wins, losses=st.losses, tournaments_played=st.tournaments,
            played_here=st.player_id in participants,
            sets_won_here=wins_here[st.player_id], sets_lost_here=losses_here[st.player_id],
            main_character=_main_character(st)))
    return Snapshot(index=index, tournament=tournament, entries=entries, matches=matches,
                    participants=len(participants), sets_counted=counted, sets_skipped=skipped)
