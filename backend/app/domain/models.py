"""Modèles du domaine : indépendants de start.gg, de Flask et du stockage."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SetPlayer:
    """Un joueur dans un set."""

    player_id: str
    tag: str
    score: int | None = None
    # Un personnage par game jouée (vide si l'info n'a pas été renseignée).
    characters: tuple[str, ...] = ()


@dataclass(frozen=True)
class TournamentSet:
    id: str
    round: int  # > 0 : Winner Bracket (ou poules) ; < 0 : Loser Bracket
    round_text: str
    completed_at: int | None  # epoch (secondes)
    started_at: int | None
    winner_index: int | None  # 0 ou 1, None si inconnu
    dq: bool
    players: tuple[SetPlayer, SetPlayer]
    phase_group: str | None = None

    @property
    def bracket(self) -> str:
        return "losers" if self.round < 0 else "winners"


@dataclass(frozen=True)
class Tournament:
    key: str  # clé telle que listée dans tournaments.txt (ex. tournament/x/event/y)
    url: str
    name: str
    event_name: str
    start_at: int | None
    sets: tuple[TournamentSet, ...]
    slug: str = ""  # slug de l'event réellement résolu
    completed: bool = True

    @property
    def display_name(self) -> str:
        if self.event_name and self.event_name.lower() not in self.name.lower():
            return f"{self.name} — {self.event_name}"
        return self.name


@dataclass(frozen=True)
class Issue:
    """Anomalie détectée par la vérification chronologique."""

    level: str  # "error" | "warning"
    code: str
    message: str
    tournament: str | None = None


@dataclass
class MatchRecord:
    opponent_id: str
    opponent_tag: str
    won: bool
    score: str
    bracket: str
    round_text: str
    weight: float
    delta: float
    elo_after: float


@dataclass
class PlayerEntry:
    player_id: str
    tag: str
    rank: int
    previous_rank: int | None
    elo: float
    elo_before: float
    elo_delta: float
    wins: int
    losses: int
    tournaments_played: int
    played_here: bool
    sets_won_here: int
    sets_lost_here: int
    main_character: dict | None  # {"key","name","games"}


@dataclass
class Snapshot:
    index: int
    tournament: Tournament
    entries: list[PlayerEntry]
    matches: dict[str, list[MatchRecord]] = field(default_factory=dict)
    participants: int = 0
    placements: dict = field(default_factory=dict)  # player_id -> Placement (vide si tournoi en cours)
    sets_counted: int = 0
    sets_skipped: int = 0


@dataclass
class RankingResult:
    snapshots: list[Snapshot]
    issues: list[Issue]
