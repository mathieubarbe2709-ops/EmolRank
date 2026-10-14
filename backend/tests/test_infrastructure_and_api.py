import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app import create_app
from app.config import Config, ROOT
from app.infrastructure.startgg_client import (NotUltimateError, StartGGClient, StartGGError,
                                               parse_set)
from app.infrastructure.tournament_list import InvalidTournamentUrl, parse_url, read_tournament_list


def test_url_parsing():
    a = parse_url("https://www.start.gg/tournament/My-Cup-12/event/ultimate-singles/brackets/1/2")
    assert a.key == "tournament/my-cup-12/event/ultimate-singles"
    b = parse_url("start.gg/tournament/my-cup-12")
    assert b.event_slug is None and b.key == "tournament/my-cup-12"
    assert parse_url("https://smash.gg/tournament/x/events/y").key == "tournament/x/event/y"
    with pytest.raises(InvalidTournamentUrl):
        parse_url("https://example.com/foo")


def test_list_reader_ignores_comments_and_reports_problems(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("# commentaire\n\nhttps://www.start.gg/tournament/a/event/b # note\n"
                 "https://www.start.gg/tournament/a/event/b/overview\nnimporte quoi\n", encoding="utf-8")
    r = read_tournament_list(f)
    assert [e.key for e in r.entries] == ["tournament/a/event/b"]
    assert len(r.problems) == 2


def node(sid, rnd, winner, a=(11, 101, "Alice"), b=(12, 102, "Bob"), scores=(2, 1), state=3, games=True):
    def slot(e, s):
        return {"entrant": {"id": e[0], "name": e[2], "participants": [{"player": {"id": e[1], "gamerTag": e[2]}}]},
                "standing": {"stats": {"score": {"value": s}}}}
    chars = [("Fox", "Marth"), ("Fox", "Marth"), ("Falco", "Marth")]
    return {"id": sid, "round": rnd, "fullRoundText": "Winners Round 1", "state": state,
            "completedAt": 1000 + sid, "startedAt": 900 + sid, "winnerId": winner, "displayScore": "A 2 - B 1",
            "phaseGroup": {"id": 77}, "slots": [slot(a, scores[0]), slot(b, scores[1])],
            "games": [{"orderNum": i + 1, "selections": [
                {"selectionType": "CHARACTER", "selectionValue": 1, "character": {"name": c[0]}, "entrant": {"id": a[0]}},
                {"selectionType": "CHARACTER", "selectionValue": 2, "character": {"name": c[1]}, "entrant": {"id": b[0]}}]}
                for i, c in enumerate(chars)] if games else []}


def test_parse_set_extracts_players_winner_and_characters():
    s = parse_set(node(1, 1, 11))
    assert s.players[0].player_id == "p101" and s.players[0].tag == "Alice"
    assert s.winner_index == 0 and s.bracket == "winners" and not s.dq
    assert s.players[0].characters == ("Fox", "Fox", "Falco") and s.players[1].characters == ("Marth",) * 3
    assert s.phase_group == "77"
    assert parse_set(node(2, -3, 12)).bracket == "losers"


def test_parse_set_skips_unfinished_bye_and_flags_dq():
    assert parse_set(node(3, 1, None, state=2)) is None
    assert parse_set({"id": 4, "round": 1, "state": 3, "slots": [{"entrant": None}, {"entrant": {"id": 1}}]}) is None
    assert parse_set(node(5, 1, 11, scores=(0, -1))).dq is True


class FakeResp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload


class FakeSession:
    """Rejoue des réponses start.gg ; vérifie pagination et repli sans champ `character`."""

    def __init__(self, reject_character=False):
        self.calls, self.reject_character = [], reject_character

    def post(self, url, json=None, headers=None, timeout=None):
        q, v = json["query"], json["variables"]
        self.calls.append(q.split("{")[0].strip() + str(v))
        assert headers["Authorization"] == "Bearer tok"
        if "event(slug" in q:
            return FakeResp({"data": {"event": {"id": 5, "name": "Ultimate Singles", "slug": "tournament/x/event/y",
                                                "startAt": 1000, "state": "COMPLETED", "numEntrants": 4,
                                                "videogame": {"id": 1386}, "teamRosterSize": None,
                                                "tournament": {"name": "Cup X"}}}})
        if self.reject_character and "character" in q:
            return FakeResp({"errors": [{"message": 'Cannot query field "character" on type "GameSelection"'}]})
        nodes = [node(v["page"] * 10 + i, 1, 11) for i in range(2)]
        return FakeResp({"data": {"event": {"sets": {"pageInfo": {"total": 4, "totalPages": 2}, "nodes": nodes}}}})


def listed(url="https://www.start.gg/tournament/x/event/y"):
    return parse_url(url)


def test_client_paginates_and_builds_tournament():
    client = StartGGClient("tok", session=FakeSession(), sleep=lambda s: None)
    t = client.fetch_tournament(listed())
    assert t.name == "Cup X" and t.completed and len(t.sets) == 4 and t.start_at == 1000
    assert t.sets[0].players[0].characters


def test_client_falls_back_when_character_field_is_unknown():
    client = StartGGClient("tok", session=FakeSession(reject_character=True), sleep=lambda s: None)
    t = client.fetch_tournament(listed())
    assert len(t.sets) == 4  # le tournoi est quand même récupéré


def test_client_rejects_other_games_and_missing_token():
    class Other(FakeSession):
        def post(self, *a, **k):
            r = super().post(*a, **k)
            r.payload["data"]["event"]["videogame"]["id"] = 1
            return r
    with pytest.raises(NotUltimateError):
        StartGGClient("tok", session=Other(), sleep=lambda s: None).fetch_tournament(listed())
    with pytest.raises(StartGGError):
        StartGGClient("", session=FakeSession(), sleep=lambda s: None).fetch_tournament(listed())


# --------------------------------------------------------------- API sur les données de démo

@pytest.fixture()
def client():
    app = create_app(Config.from_env().for_demo())
    return app.test_client()


def test_api_overview_and_rankings(client):
    ov = client.get("/api/overview").get_json()
    assert len(ov["tournaments"]) == 8 and ov["chronology"]["ok"] is True
    assert ov["rules"]["losers_weight"] < 1
    dates = [t["date"] for t in ov["tournaments"]]
    assert dates == sorted(dates)
    first = client.get("/api/rankings/0").get_json()
    assert all(e["elo"] != 0 for e in first["entries"]) and first["entries"][0]["rank"] == 1
    assert sum(e["elo_delta"] for e in first["entries"]) > 0  # défaite adoucie : plus de gains que de pertes
    assert ov["rules"]["decay"] == 5 and ov["rules"]["loss_factor"] == 0.7
    last = client.get("/api/rankings/7").get_json()
    assert len(last["entries"]) >= len(first["entries"])
    assert any(e["main_character"] for e in last["entries"])
    pid = last["entries"][0]["player_id"]
    detail = client.get(f"/api/players/{pid}").get_json()
    assert detail["history"][-1]["rank"] == 1
    assert client.get("/api/rankings/99").status_code == 404
    assert client.get("/api/players/nope").status_code == 404


def test_frontend_is_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/assets/characters/fox.png").status_code == 200
