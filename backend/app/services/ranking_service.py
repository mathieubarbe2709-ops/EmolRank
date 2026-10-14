"""Service métier : orchestre liste, cache et moteur ELO, et expose des vues prêtes pour l'API."""
from __future__ import annotations

import time
from threading import Lock

from ..config import Config
from ..domain.characters import has_icon
from ..domain.chronology import tournament_date
from ..domain.elo import EloConfig
from ..domain.models import RankingResult
from ..domain.ranking_engine import compute_rankings
from ..infrastructure.tournament_list import read_tournament_list
from ..infrastructure.tournament_repository import TournamentRepository


class NotFound(LookupError):
    pass


def _char(c: dict | None) -> dict | None:
    if not c:
        return None
    return {**c, "icon": c["key"] if has_icon(c["key"]) else None}


class RankingService:
    def __init__(self, config: Config, repository: TournamentRepository):
        self.config = config
        self.repository = repository
        self.elo = EloConfig(config.elo_initial, config.elo_k, config.elo_losers_weight,
                           config.elo_loss_factor, config.elo_decay)
        self._lock = Lock()
        self._memo: tuple[tuple, RankingResult, list[str], list[str]] | None = None

    # -- calcul (mis en cache tant que le fichier texte et le cache ne changent pas)
    def _result(self) -> tuple[RankingResult, list[str], list[str]]:
        listing = read_tournament_list(self.config.tournaments_file)
        keys = [e.key for e in listing.entries]
        file_sig = self.config.tournaments_file.stat().st_mtime_ns if self.config.tournaments_file.is_file() else None
        signature = (file_sig, self.repository.signature(keys), self.elo)
        with self._lock:
            if self._memo and self._memo[0] == signature:
                return self._memo[1], self._memo[2], self._memo[3]
            loaded, missing = [], []
            for entry in listing.entries:
                t = self.repository.load(entry.key)
                (loaded if t else missing).append(t or entry.url)
            # La vérification chronologique est rejouée à chaque recalcul.
            result = compute_rankings(loaded, self.elo)
            self._memo = (signature, result, missing, list(listing.problems))
            return result, missing, list(listing.problems)

    def result(self) -> RankingResult:
        """Résultat complet du calcul (utilisé par le Wiki)."""
        return self._result()[0]

    # -- vues
    def overview(self) -> dict:
        result, missing, problems = self._result()
        issues = [i.__dict__ for i in result.issues]
        return {
            "rules": {
                "initial_elo": self.elo.initial, "k_factor": self.elo.k_factor,
                "losers_weight": self.elo.losers_weight,
                "loss_factor": self.elo.loss_factor, "decay": self.elo.decay_per_tournament,
            },
            "tournaments": [{
                "index": s.index, "name": s.tournament.display_name, "tournament": s.tournament.name,
                "event": s.tournament.event_name, "url": s.tournament.url,
                "date": tournament_date(s.tournament), "completed": s.tournament.completed,
                "participants": s.participants, "sets_counted": s.sets_counted,
                "sets_skipped": s.sets_skipped, "players_total": len(s.entries),
            } for s in result.snapshots],
            "chronology": {
                "ok": not any(i.level == "error" for i in result.issues),
                "issues": issues,
                "checked_at": int(time.time()),
            },
            "missing": missing,
            "problems": problems,
        }

    def ranking(self, index: int) -> dict:
        result, _, _ = self._result()
        if not result.snapshots:
            raise NotFound("Aucun tournoi disponible")
        if not -len(result.snapshots) <= index < len(result.snapshots):
            raise NotFound(f"Tournoi {index} inexistant")
        snap = result.snapshots[index]
        return {
            "index": snap.index,
            "tournament": {"name": snap.tournament.display_name, "date": tournament_date(snap.tournament),
                           "url": snap.tournament.url, "participants": snap.participants},
            "entries": [{
                "player_id": e.player_id, "tag": e.tag, "rank": e.rank, "previous_rank": e.previous_rank,
                "rank_change": (e.previous_rank - e.rank) if e.previous_rank else None,
                "is_new": e.previous_rank is None,
                "elo": round(e.elo), "elo_delta": round(e.elo_delta, 1), "played_here": e.played_here,
                "wins": e.wins, "losses": e.losses, "tournaments_played": e.tournaments_played,
                "sets_here": [e.sets_won_here, e.sets_lost_here],
                "main_character": _char(e.main_character),
            } for e in snap.entries],
        }

    def player(self, player_id: str) -> dict:
        result, _, _ = self._result()
        history, tag = [], None
        for snap in result.snapshots:
            entry = next((e for e in snap.entries if e.player_id == player_id), None)
            if not entry:
                continue
            tag = entry.tag
            history.append({
                "index": snap.index, "tournament": snap.tournament.display_name,
                "date": tournament_date(snap.tournament), "rank": entry.rank, "elo": round(entry.elo),
                "elo_delta": round(entry.elo_delta, 1), "played_here": entry.played_here,
                "matches": [{
                    "opponent": m.opponent_tag, "won": m.won, "score": m.score, "bracket": m.bracket,
                    "round": m.round_text, "weight": m.weight, "delta": round(m.delta, 1),
                } for m in snap.matches.get(player_id, [])],
            })
        if not history:
            raise NotFound("Joueur inconnu")
        return {"player_id": player_id, "tag": tag, "history": history}
