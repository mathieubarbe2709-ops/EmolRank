import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.domain.characters import character_key, character_label
from app.domain.elo import EloConfig, expected_score, rating_change, set_deltas
from app.domain.models import SetPlayer, Tournament, TournamentSet
from app.domain.ranking_engine import compute_rankings

# Configuration « ELO classique » (sans adoucissement ni decay) pour les tests historiques.
CFG = EloConfig(initial=1000, k_factor=32, losers_weight=0.5, loss_factor=1.0, decay_per_tournament=0.0)
NEW = EloConfig(initial=1000, k_factor=32, losers_weight=0.5, loss_factor=0.7, decay_per_tournament=5.0)


def mkset(sid, a, b, winner, rnd=1, t=None, chars_a=(), chars_b=(), dq=False, pg="1", started=None):
    return TournamentSet(
        id=str(sid), round=rnd, round_text=f"R{rnd}", completed_at=t, started_at=started,
        winner_index=winner, dq=dq, phase_group=pg,
        players=(SetPlayer(a, a.upper(), 2, tuple(chars_a)), SetPlayer(b, b.upper(), 0, tuple(chars_b))))


def mkt(key, start, sets):
    return Tournament(key=key, url=f"https://start.gg/{key}", name=key, event_name="", start_at=start,
                      sets=tuple(sets), slug=key)


def test_elo_is_zero_sum_and_symmetric_at_equal_rating():
    assert expected_score(1000, 1000) == pytest.approx(0.5)
    assert rating_change(1000, 1000, True, 1.0, CFG) == pytest.approx(16)
    assert rating_change(1000, 1000, False, 1.0, CFG) == pytest.approx(-16)


def test_losers_bracket_is_worth_less():
    win = rating_change(1000, 1000, True, 1.0, CFG)
    lose = rating_change(1000, 1000, True, CFG.losers_weight, CFG)
    assert lose == pytest.approx(win * 0.5)


def test_new_players_start_at_1000_and_first_set_applies_weight():
    t = mkt("t1", 100, [mkset(1, "a", "b", 0, rnd=1, t=110), mkset(2, "c", "d", 0, rnd=-1, t=120)])
    res = compute_rankings([t], CFG)
    by = {e.player_id: e for e in res.snapshots[0].entries}
    assert by["a"].elo == pytest.approx(1016) and by["b"].elo == pytest.approx(984)
    assert by["c"].elo == pytest.approx(1008) and by["d"].elo == pytest.approx(992)  # LB : poids 0.5
    assert all(e.tournaments_played == 1 for e in by.values())
    assert res.issues == []


def test_ratings_carry_over_and_only_participants_are_registered():
    t1 = mkt("t1", 100, [mkset(1, "a", "b", 0, t=110)])
    t2 = mkt("t2", 200, [mkset(2, "a", "c", 1, t=210)])
    res = compute_rankings([t1, t2], CFG)
    assert {e.player_id for e in res.snapshots[0].entries} == {"a", "b"}  # c n'existe pas encore
    s2 = {e.player_id: e for e in res.snapshots[1].entries}
    assert s2["c"].elo > 1000 and s2["a"].elo < 1016
    assert s2["a"].previous_rank == 1 and s2["c"].previous_rank is None
    assert s2["b"].played_here is False and s2["b"].elo == pytest.approx(984)


def test_sets_are_replayed_in_chronological_order_not_file_order():
    # Même sets dans deux ordres d'entrée : le résultat doit être identique.
    s1 = mkset(1, "a", "b", 0, t=100)
    s2 = mkset(2, "a", "c", 1, t=200)
    r1 = compute_rankings([mkt("t", 50, [s1, s2])], CFG)
    r2 = compute_rankings([mkt("t", 50, [s2, s1])], CFG)
    e1 = {e.player_id: e.elo for e in r1.snapshots[0].entries}
    e2 = {e.player_id: e.elo for e in r2.snapshots[0].entries}
    assert e1 == pytest.approx(e2)
    assert r1.issues == r2.issues == []


def test_tournaments_are_sorted_by_date_with_warning():
    t_late = mkt("late", 2000, [mkset(1, "a", "b", 0, t=2010)])
    t_early = mkt("early", 1000, [mkset(2, "a", "b", 1, t=1010)])
    res = compute_rankings([t_late, t_early], CFG)
    assert [s.tournament.key for s in res.snapshots] == ["early", "late"]
    assert any(i.code == "TOURNAMENT_FILE_ORDER" for i in res.issues)


def test_overlapping_tournaments_raise_error():
    t1 = mkt("t1", 1000, [mkset(1, "a", "b", 0, t=5000)])
    t2 = mkt("t2", 1001, [mkset(2, "a", "b", 0, t=3000)])
    res = compute_rankings([t1, t2], CFG)
    assert any(i.code == "TOURNAMENT_OVERLAP" and i.level == "error" for i in res.issues)


def test_player_round_regression_is_flagged():
    sets = [mkset(1, "a", "b", 0, rnd=2, t=100), mkset(2, "a", "c", 0, rnd=1, t=200)]
    res = compute_rankings([mkt("t", 50, sets)], CFG)
    assert any(i.code == "PLAYER_ROUND_REGRESSION" for i in res.issues)


def test_equal_timestamps_fall_back_on_bracket_progress():
    # Horodatages identiques (saisie groupée) : WR1 avant WR2 malgré l'ordre d'entrée.
    sets = [mkset(2, "a", "c", 0, rnd=2, t=100), mkset(1, "a", "b", 0, rnd=1, t=100)]
    res = compute_rankings([mkt("t", 50, sets)], CFG)
    assert not any(i.code == "PLAYER_ROUND_REGRESSION" for i in res.issues)


def test_missing_and_inverted_timestamps_are_reported():
    sets = [mkset(1, "a", "b", 0, t=None), mkset(2, "c", "d", 0, t=100, started=500)]
    res = compute_rankings([mkt("t", 50, sets)], CFG)
    codes = {i.code for i in res.issues}
    assert {"SET_NO_TIMESTAMP", "SET_TIMESTAMP_INVERTED"} <= codes


def test_dq_sets_do_not_move_elo_but_register_players():
    res = compute_rankings([mkt("t", 50, [mkset(1, "a", "b", 0, t=100, dq=True)])], CFG)
    snap = res.snapshots[0]
    assert snap.sets_skipped == 1 and snap.participants == 2
    assert all(e.elo == 1000 for e in snap.entries)


def test_main_character_is_cumulative_most_played():
    t1 = mkt("t1", 100, [mkset(1, "a", "b", 0, t=110, chars_a=["Fox", "Fox", "Marth"], chars_b=["Pikachu"])])
    t2 = mkt("t2", 200, [mkset(2, "a", "b", 0, t=210, chars_a=["Marth", "Marth", "Marth"], chars_b=["Pikachu"])])
    res = compute_rankings([t1, t2], CFG)
    a1 = next(e for e in res.snapshots[0].entries if e.player_id == "a")
    a2 = next(e for e in res.snapshots[1].entries if e.player_id == "a")
    assert a1.main_character["key"] == "fox" and a1.main_character["games"] == 2
    assert a2.main_character["key"] == "marth" and a2.main_character["games"] == 4


def test_character_name_normalisation():
    assert character_key("Pokémon Trainer") == "pokemon_trainer"
    assert character_key("Mii Gunner") == "mii_fighter"
    assert character_key("Pyra/Mythra") == "homura"
    assert character_key("R.O.B.") == "rob"
    assert character_key("Terry Bogard") == "terry"
    assert character_key("Banjo & Kazooie") == "banjo_and_kazooie"
    assert character_key("Hero") == "dq_hero"
    assert character_key("") is None
    assert character_label("fox") == "Fox"


def test_defeat_costs_less_than_victory_pays():
    a, b = set_deltas(1000, 1000, True, 1.0, NEW)
    assert a == pytest.approx(16) and b == pytest.approx(-11.2)
    # le sens est respecté quand B gagne, et pour un upset
    a, b = set_deltas(1000, 1000, False, 1.0, NEW)
    assert a == pytest.approx(-11.2) and b == pytest.approx(16)
    fav, under = set_deltas(1200, 1000, False, 1.0, NEW)  # l'outsider gagne
    assert under > 16 and fav == pytest.approx(-under * 0.7)
    assert set_deltas(1000, 1000, True, 1.0, CFG) == (pytest.approx(16), pytest.approx(-16))


def test_decay_applies_only_to_registered_players_who_miss_a_tournament():
    t1 = mkt("t1", 100, [mkset(1, "a", "b", 0, t=110)])
    t2 = mkt("t2", 200, [mkset(2, "a", "c", 0, t=210)])        # b absent
    t3 = mkt("t3", 300, [mkset(3, "a", "c", 0, t=310)])        # b absent encore, d inconnu
    res = compute_rankings([t1, t2, t3], NEW)
    b = [next(e for e in s.entries if e.player_id == "b") for s in res.snapshots]
    assert b[0].elo == pytest.approx(1000 - 11.2) and b[0].elo_delta == pytest.approx(-11.2)
    assert b[1].elo == pytest.approx(b[0].elo - 5) and b[1].elo_delta == pytest.approx(-5) and not b[1].played_here
    assert b[2].elo == pytest.approx(b[0].elo - 10)
    c = next(e for e in res.snapshots[1].entries if e.player_id == "c")
    assert c.elo_delta < 0 and c.played_here  # nouveau joueur : pas de decay avant son 1er tournoi
    assert all(e.player_id != "c" for e in res.snapshots[0].entries)
