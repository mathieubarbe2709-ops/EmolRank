"""Service de synchronisation : récupère sur start.gg les tournois listés et les met en cache."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..infrastructure.startgg_client import StartGGClient, StartGGError
from ..infrastructure.tournament_list import read_tournament_list
from ..infrastructure.tournament_repository import TournamentRepository


@dataclass
class SyncReport:
    fetched: list[str] = field(default_factory=list)
    cached: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class SyncService:
    def __init__(self, list_path, repository: TournamentRepository, client: StartGGClient):
        self.list_path = list_path
        self.repository = repository
        self.client = client

    def sync(self, refresh: bool = False) -> SyncReport:
        listing = read_tournament_list(self.list_path)
        report = SyncReport(problems=list(listing.problems))
        for listed in listing.entries:
            cached = self.repository.load(listed.key)
            # Un event terminé ne change plus : on ne le retélécharge que sur demande.
            if cached and cached.completed and not refresh:
                report.cached.append(listed.key)
                continue
            try:
                tournament = self.client.fetch_tournament(listed)
            except StartGGError as exc:
                report.errors.append(f"{listed.url} : {exc}")
                continue
            self.repository.save(tournament)
            report.fetched.append(listed.key)
        return report
