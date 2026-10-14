"""Client de l'API GraphQL start.gg (tier d'accès aux données externes)."""
from __future__ import annotations

import time
from typing import Any, Callable

import requests

from ..domain.models import SetPlayer, Tournament, TournamentSet
from .tournament_list import ListedTournament

API_URL = "https://api.start.gg/gql/alpha"
ULTIMATE_VIDEOGAME_ID = 1386
EVENT_FIELDS = """id name slug startAt state numEntrants
  videogame { id name } teamRosterSize { maxPlayers } tournament { name }"""

EVENT_BY_SLUG = "query($slug: String){ event(slug: $slug){ %s } }" % EVENT_FIELDS
TOURNAMENT_EVENTS = """query($slug: String){ tournament(slug: $slug){ name
  events { id name slug startAt state numEntrants videogame { id name } teamRosterSize { maxPlayers } } } }"""


def _sets_query(with_character: bool) -> str:
    character = "character { name }" if with_character else ""
    return """query($id: ID, $page: Int!, $perPage: Int!){ event(id: $id){ sets(page: $page, perPage: $perPage){
  pageInfo { total totalPages }
  nodes { id round fullRoundText state completedAt startedAt winnerId displayScore phaseGroup { id }
    slots { entrant { id name participants { player { id gamerTag } } }
            standing { stats { score { value } } } }
    games { orderNum selections { selectionType selectionValue %s entrant { id } } } } } } }""" % character


class StartGGError(RuntimeError):
    pass


class StartGGAuthError(StartGGError):
    pass


class NotUltimateError(StartGGError):
    pass


# ----------------------------------------------------------------- parsing (pur, testable)

def parse_set(node: dict[str, Any]) -> TournamentSet | None:
    """Convertit un noeud GraphQL en TournamentSet ; None si le set n'est pas exploitable
    (non terminé, bye, entrant manquant)."""
    slots = node.get("slots") or []
    if len(slots) != 2 or any(not s or not s.get("entrant") for s in slots):
        return None
    if node.get("state") not in (3, "3") and not node.get("winnerId"):
        return None

    players: list[SetPlayer] = []
    entrant_ids: list[Any] = []
    games = node.get("games") or []
    for slot in slots:
        entrant = slot["entrant"]
        entrant_ids.append(entrant["id"])
        participants = entrant.get("participants") or []
        player = (participants[0] or {}).get("player") if participants else None
        player_id = f"p{player['id']}" if player and player.get("id") else f"e{entrant['id']}"
        tag = (player or {}).get("gamerTag") or entrant.get("name") or player_id
        score = ((((slot.get("standing") or {}).get("stats") or {}).get("score") or {}).get("value"))
        chars: list[str] = []
        for game in sorted(games, key=lambda g: g.get("orderNum") or 0):
            for sel in game.get("selections") or []:
                if (sel.get("entrant") or {}).get("id") != entrant["id"]:
                    continue
                if str(sel.get("selectionType", "CHARACTER")).upper() != "CHARACTER":
                    continue
                name = (sel.get("character") or {}).get("name")
                if name:
                    chars.append(name)
        players.append(SetPlayer(player_id, tag, score if isinstance(score, int) else None, tuple(chars)))

    winner_id = node.get("winnerId")
    winner_index = entrant_ids.index(winner_id) if winner_id in entrant_ids else None
    scores = [p.score for p in players]
    display = str(node.get("displayScore") or "")
    dq = any(s == -1 for s in scores) or "DQ" in display.upper()

    return TournamentSet(
        id=str(node["id"]), round=int(node.get("round") or 0), round_text=node.get("fullRoundText") or "",
        completed_at=node.get("completedAt"), started_at=node.get("startedAt"),
        winner_index=winner_index, dq=dq, players=(players[0], players[1]),
        phase_group=str(node["phaseGroup"]["id"]) if node.get("phaseGroup") else None)


# ----------------------------------------------------------------- client HTTP

class StartGGClient:
    def __init__(self, token: str, *, session: requests.Session | None = None, pause: float = 0.9,
                 sleep: Callable[[float], None] = time.sleep):
        self.token = token
        self.session = session or requests.Session()
        self.pause = pause  # l'API limite à 80 requêtes / 60 s
        self._sleep = sleep
        self._with_character = True

    # -- bas niveau
    def _post(self, query: str, variables: dict) -> dict:
        if not self.token:
            raise StartGGAuthError("Jeton start.gg absent : définissez STARTGG_TOKEN (voir README).")
        for attempt in range(5):
            try:
                resp = self.session.post(API_URL, json={"query": query, "variables": variables}, timeout=30,
                                         headers={"Authorization": f"Bearer {self.token}"})
            except requests.RequestException as exc:
                if attempt == 4:
                    raise StartGGError(f"Réseau indisponible : {exc}") from exc
                self._sleep(2 ** attempt)
                continue
            if resp.status_code in (401, 403):
                raise StartGGAuthError("Jeton start.gg refusé (HTTP %d)." % resp.status_code)
            if resp.status_code == 429 or resp.status_code >= 500:
                self._sleep(5 * (attempt + 1))
                continue
            try:
                payload = resp.json()
            except ValueError as exc:
                raise StartGGError(f"Réponse non JSON (HTTP {resp.status_code})") from exc
            if payload.get("errors"):
                raise StartGGError("; ".join(str(e.get("message")) for e in payload["errors"]))
            return payload["data"]
        raise StartGGError("start.gg ne répond pas (limite de requêtes ou erreur serveur).")

    # -- événement
    def _event_from_listed(self, listed: ListedTournament) -> dict:
        if listed.event_slug:
            event = self._post(EVENT_BY_SLUG, {"slug": listed.api_slug})["event"]
            if not event:
                raise StartGGError(f"Event introuvable : {listed.url}")
            return event
        tournament = self._post(TOURNAMENT_EVENTS, {"slug": listed.api_slug})["tournament"]
        if not tournament:
            raise StartGGError(f"Tournoi introuvable : {listed.url}")
        candidates = [
            e for e in tournament["events"] or []
            if (e.get("videogame") or {}).get("id") == ULTIMATE_VIDEOGAME_ID
            and not ((e.get("teamRosterSize") or {}).get("maxPlayers") or 1) > 1]
        if not candidates:
            raise NotUltimateError(f"Aucun event Super Smash Bros. Ultimate en simple dans {listed.url}")
        best = max(candidates, key=lambda e: e.get("numEntrants") or 0)
        best["tournament"] = {"name": tournament["name"]}
        return best

    def fetch_tournament(self, listed: ListedTournament) -> Tournament:
        event = self._event_from_listed(listed)
        if (event.get("videogame") or {}).get("id") != ULTIMATE_VIDEOGAME_ID:
            raise NotUltimateError(f"Cet event n'est pas Super Smash Bros. Ultimate : {listed.url}")
        if ((event.get("teamRosterSize") or {}).get("maxPlayers") or 1) > 1:
            raise NotUltimateError(f"Event en équipe (doubles) non pris en charge : {listed.url}")

        sets: dict[str, TournamentSet] = {}
        page, per_page, total_pages = 1, 30, 1
        while page <= total_pages:
            try:
                data = self._post(_sets_query(self._with_character),
                                  {"id": event["id"], "page": page, "perPage": per_page})
            except StartGGError as exc:
                msg = str(exc).lower()
                if "complexity" in msg and per_page > 5:
                    per_page = max(5, per_page // 2)
                    page, total_pages = 1, 1
                    sets.clear()
                    continue
                if self._with_character and "character" in msg:
                    self._with_character = False  # schéma sans le champ : pas d'info personnage
                    continue
                raise
            block = (data.get("event") or {}).get("sets") or {}
            total_pages = (block.get("pageInfo") or {}).get("totalPages") or 1
            for node in block.get("nodes") or []:
                parsed = parse_set(node)
                if parsed:
                    sets[parsed.id] = parsed
            page += 1
            self._sleep(self.pause)

        return Tournament(
            key=listed.key, url=listed.url, slug=event.get("slug") or listed.api_slug,
            name=(event.get("tournament") or {}).get("name") or listed.tournament_slug,
            event_name=event.get("name") or "", start_at=event.get("startAt"),
            sets=tuple(sets.values()), completed=str(event.get("state")) == "COMPLETED")
