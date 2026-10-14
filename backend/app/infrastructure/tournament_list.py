"""Lecture du fichier texte listant les tournois (un lien start.gg par ligne)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:start|smash)\.gg/tournament/(?P<t>[^/?#\s]+)"
    r"(?:/events?/(?P<e>[^/?#\s]+))?", re.IGNORECASE)


class InvalidTournamentUrl(ValueError):
    pass


@dataclass(frozen=True)
class ListedTournament:
    url: str
    tournament_slug: str
    event_slug: str | None  # None : lien vers le tournoi, l'event Ultimate est alors déterminé via l'API

    @property
    def key(self) -> str:
        base = f"tournament/{self.tournament_slug}"
        return f"{base}/event/{self.event_slug}" if self.event_slug else base

    @property
    def api_slug(self) -> str:
        return self.key


def parse_url(line: str) -> ListedTournament:
    m = _URL_RE.match(line.strip())
    if not m:
        raise InvalidTournamentUrl("Lien start.gg non reconnu (attendu : https://www.start.gg/tournament/<nom>/event/<event>)")
    return ListedTournament(line.strip(), m["t"].lower(), m["e"].lower() if m["e"] else None)


@dataclass(frozen=True)
class TournamentList:
    entries: tuple[ListedTournament, ...]
    problems: tuple[str, ...]  # lignes invalides / doublons, avec leur numéro


def read_tournament_list(path: Path) -> TournamentList:
    if not path.is_file():
        return TournamentList((), (f"Fichier introuvable : {path}",))
    entries: list[ListedTournament] = []
    problems: list[str] = []
    seen: set[str] = set()
    for n, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        try:
            item = parse_url(line)
        except InvalidTournamentUrl as exc:
            problems.append(f"Ligne {n} : {exc} — « {line} »")
            continue
        if item.key in seen:
            problems.append(f"Ligne {n} : doublon ignoré — « {line} »")
            continue
        seen.add(item.key)
        entries.append(item)
    return TournamentList(tuple(entries), tuple(problems))
