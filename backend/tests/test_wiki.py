import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app import create_app
from app.config import Config
from app.domain.models import SetPlayer, TournamentSet
from app.domain.placements import band, compute_placements, place_label
from app.infrastructure.wiki_repository import InvalidPlayerId, WikiRepository


def mkset(sid, a, b, winner, rnd, t, chars_b=()):
    return TournamentSet(id=str(sid), round=rnd, round_text=f"R{rnd}", completed_at=t, started_at=None,
                         winner_index=winner, dq=False, phase_group="1",
                         players=(SetPlayer(a, a.upper(), 2, ()), SetPlayer(b, b.upper(), 0, tuple(chars_b))))


def test_band_colors_follow_the_spec():
    expected = {1: "gold", 2: "silver", 3: "bronze", 4: "orange", 5: "lightblue", 6: "lightblue",
                7: "darkblue", 8: "darkblue", 9: "purple", 25: "purple"}
    assert {p: band(p) for p in expected} == expected
    assert place_label(1, 1) == "1er" and place_label(3, 1) == "3e" and place_label(5, 2) == "5-6e"


def test_placements_of_a_four_player_double_elimination():
    # a bat b, c bat d ; WF: a bat c ; LR1: d bat b ; LF: c bat d ; GF: a bat c
    sets = [mkset(1, "a", "b", 0, 1, 10), mkset(2, "c", "d", 0, 1, 20), mkset(3, "a", "c", 0, 2, 30),
            mkset(4, "d", "b", 0, -1, 40), mkset(5, "c", "d", 0, -2, 50), mkset(6, "a", "c", 0, 3, 60, ["Fox"])]
    pl = compute_placements(sets)
    assert {k: v.place for k, v in pl.items()} == {"a": 1, "c": 2, "d": 3, "b": 4}
    assert pl["a"].is_final and pl["a"].opponent_id == "c" and pl["a"].opponent_characters == ("Fox",)  # 1er : GF
    assert pl["b"].opponent_id == "d" and not pl["b"].is_final                                         # éliminé par d
    assert compute_placements(sets, completed=False) == {}


def test_tied_places_share_the_same_group():
    sets = [mkset(1, "a", "b", 0, 1, 10), mkset(2, "c", "d", 0, 1, 20), mkset(3, "e", "f", 0, 1, 30),
            mkset(4, "g", "h", 0, 1, 40)]
    sets += [mkset(5, "a", "c", 0, 2, 50), mkset(6, "e", "g", 0, 2, 60), mkset(7, "a", "e", 0, 3, 70),
             mkset(8, "a", "e", 0, 4, 80)]
    pl = compute_placements(sets)
    assert pl["a"].place == 1 and pl["e"].place == 2
    assert {pl[x].place for x in "cg"} == {3} and pl["c"].tied == 2     # éliminés au même round : ex æquo
    assert {pl[x].place for x in "bdfh"} == {5} and pl["b"].tied == 4


def test_wiki_repository_persists_and_rejects_unsafe_ids(tmp_path):
    repo = WikiRepository(tmp_path / "wiki")
    assert repo.load("p1") is None
    repo.save("p1", "Bonjour\néàü 日本")
    assert WikiRepository(tmp_path / "wiki").load("p1")["text"] == "Bonjour\néàü 日本"  # nouvelle instance = « redémarrage »
    repo.save("p1", "   ")
    assert repo.load("p1") is None
    for bad in ("../x", "a/b", "", "a" * 65, "p1.json"):
        with pytest.raises(InvalidPlayerId):
            repo.load(bad)


@pytest.fixture()
def wiki_config(tmp_path):
    return replace(Config.from_env().for_demo(), wiki_dir=tmp_path / "wiki", startgg_token="")


def test_wiki_api_default_edit_persist_reset(wiki_config):
    client = create_app(wiki_config).test_client()
    ranking = client.get("/api/rankings/7").get_json()["entries"]
    pid, tag = ranking[0]["player_id"], ranking[0]["tag"]

    page = client.get(f"/api/wiki/{pid}").get_json()
    assert page["text"] == f"{tag} est un joueur de Super Smash Bros. Ultimate" and page["is_default"]
    assert page["main_character"]["name"] and page["stats"]["rank"] == 1
    assert page["results"] and page["results"][0]["date"] >= page["results"][-1]["date"]  # récent d'abord
    won = [r for r in page["results"] if r["placement"] and r["placement"]["place"] == 1]
    for r in page["results"]:
        pl = r["placement"]
        assert pl["band"] and pl["opponent"]["player_id"] and pl["score"]
        assert (pl["kind"] == "final") == (pl["place"] <= 2)
    assert all(r["placement"]["kind"] == "final" for r in won)  # 1er : on affiche la grande finale

    saved = client.put(f"/api/wiki/{pid}", json={"text": "Mon texte\nligne 2"}).get_json()
    assert saved["text"] == "Mon texte\nligne 2" and not saved["is_default"] and saved["updated_at"]
    # « rafraîchissement » : application recréée, le texte est toujours là
    again = create_app(wiki_config).test_client().get(f"/api/wiki/{pid}").get_json()
    assert again["text"] == "Mon texte\nligne 2"
    # vider le texte rétablit le texte par défaut
    reset = client.put(f"/api/wiki/{pid}", json={"text": ""}).get_json()
    assert reset["is_default"] and reset["text"].endswith("Ultimate")


def test_wiki_api_validation(wiki_config):
    client = create_app(wiki_config).test_client()
    pid = client.get("/api/rankings/0").get_json()["entries"][0]["player_id"]
    assert client.get("/api/wiki/inconnu").status_code == 404
    assert client.put(f"/api/wiki/{pid}", json={}).status_code == 400
    assert client.put(f"/api/wiki/{pid}", json={"text": 5}).status_code == 400
    assert client.put(f"/api/wiki/{pid}", json={"text": "x" * 20_001}).status_code == 400
    assert client.get("/api/wiki/..%2Fsecret").status_code in (400, 404)
