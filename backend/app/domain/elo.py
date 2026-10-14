"""Système ELO pondéré par la nature du bracket, avec défaite adoucie et inactivité pénalisée."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EloConfig:
    initial: float = 1000.0
    k_factor: float = 32.0
    # Un set de Loser Bracket compte pour `losers_weight` d'un set de Winner Bracket.
    losers_weight: float = 0.6
    # Le perdant ne perd que `loss_factor` de ce que le calcul ELO lui retirerait (1 = ELO classique).
    # Le vainqueur gagne toujours le plein montant : perdre coûte moins que gagner ne rapporte.
    loss_factor: float = 0.7
    # Points retirés à chaque joueur déjà inscrit pour chaque tournoi auquel il ne participe pas.
    decay_per_tournament: float = 5.0


def expected_score(rating_a: float, rating_b: float) -> float:
    """Probabilité de victoire de A selon la formule ELO classique."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def bracket_weight(bracket: str, config: EloConfig) -> float:
    return config.losers_weight if bracket == "losers" else 1.0


def rating_change(rating_a: float, rating_b: float, a_won: bool, weight: float, config: EloConfig) -> float:
    """Variation ELO classique de A, symétrique (B reçoit l'opposé)."""
    score = 1.0 if a_won else 0.0
    return config.k_factor * weight * (score - expected_score(rating_a, rating_b))


def set_deltas(rating_a: float, rating_b: float, a_won: bool, weight: float,
               config: EloConfig) -> tuple[float, float]:
    """Variations (A, B) pour un set : le vainqueur reçoit le montant ELO plein, le perdant
    en perd `loss_factor` seulement."""
    gain = abs(rating_change(rating_a, rating_b, a_won, weight, config))
    # Le vainqueur gagne toujours >= 0 ; le perdant perd une fraction du même montant.
    winner_delta, loser_delta = gain, -gain * config.loss_factor
    return (winner_delta, loser_delta) if a_won else (loser_delta, winner_delta)
