"""Service Wiki : assemble la page d'un joueur (texte éditable + résultats de tournois)."""
from __future__ import annotations

from ..domain.characters import character_key, character_label, has_icon
from ..domain.chronology import tournament_date
from ..domain.placements import band, place_label
from ..infrastructure.wiki_repository import WikiRepository
from .ranking_service import NotFound, RankingService

MAX_TEXT_LENGTH = 20_000


class InvalidText(ValueError):
    pass


def default_text(tag: str) -> str:
    return f"{tag} est un joueur de Super Smash Bros. Ultimate"


def _characters(names: tuple[str, ...]) -> list[dict]:
    out, seen = [], set()
    for name in names:
        key = character_key(name)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"key": key, "name": character_label(key, name), "icon": key if has_icon(key) else None})
    return out


class WikiService:
    def __init__(self, ranking: RankingService, repository: WikiRepository):
        self.ranking = ranking
        self.repository = repository

    def _latest_entry(self, player_id: str):
        result = self.ranking.result()
        for snap in reversed(result.snapshots):
            for e in snap.entries:
                if e.player_id == player_id:
                    return result, e
        raise NotFound("Joueur inconnu")

    def page(self, player_id: str) -> dict:
        result, latest = self._latest_entry(player_id)
        stored = self.repository.load(player_id)
        text = (stored or {}).get("text") or ""
        results = []
        for snap in result.snapshots:
            mine = next((e for e in snap.entries if e.player_id == player_id), None)
            if not mine or not mine.played_here:
                continue
            placement = snap.placements.get(player_id)
            row = {
                "index": snap.index, "tournament": snap.tournament.display_name, "date": tournament_date(snap.tournament),
                "url": snap.tournament.url, "elo": round(mine.elo), "elo_delta": round(mine.elo_delta, 1),
                "placement": None,
            }
            if placement:
                row["placement"] = {
                    "place": placement.place, "label": place_label(placement.place, placement.tied),
                    "band": band(placement.place),
                    "kind": "final" if placement.is_final else "elimination",
                    "reset": placement.is_final and "reset" in placement.round_text.lower(),
                    "round": placement.round_text, "score": placement.score,
                    "opponent": {"player_id": placement.opponent_id, "tag": placement.opponent_tag},
                    "opponent_characters": _characters(placement.opponent_characters),
                }
            results.append(row)
        results.reverse()  # le plus récent d'abord, comme sur Liquipedia

        main = latest.main_character
        return {
            "player_id": player_id, "tag": latest.tag,
            "text": text or default_text(latest.tag), "is_default": not text,
            "default_text": default_text(latest.tag),
            "updated_at": (stored or {}).get("updated_at"),
            "main_character": {**main, "icon": main["key"] if has_icon(main["key"]) else None} if main else None,
            "stats": {"rank": latest.rank, "elo": round(latest.elo), "wins": latest.wins, "losses": latest.losses,
                      "tournaments_played": latest.tournaments_played,
                      "tournaments_total": len(result.snapshots),
                      "best_place": min((r["placement"]["place"] for r in results if r["placement"]), default=None)},
            "results": results,
        }

    def save(self, player_id: str, text) -> dict:
        self._latest_entry(player_id)  # 404 si le joueur n'existe pas
        if not isinstance(text, str):
            raise InvalidText("Le texte doit être une chaîne de caractères")
        if len(text) > MAX_TEXT_LENGTH:
            raise InvalidText(f"Texte trop long ({MAX_TEXT_LENGTH} caractères maximum)")
        self.repository.save(player_id, text.replace("\r\n", "\n"))
        return self.page(player_id)
