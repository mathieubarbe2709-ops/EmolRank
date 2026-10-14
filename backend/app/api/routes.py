"""Tier API : routes HTTP/JSON. Aucune logique métier ici."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..infrastructure.wiki_repository import InvalidPlayerId
from ..services.ranking_service import NotFound
from ..services.wiki_service import InvalidText
from ..infrastructure.startgg_client import StartGGError

api = Blueprint("api", __name__, url_prefix="/api")


def _c():
    return current_app.extensions["container"]


@api.get("/health")
def health():
    return jsonify(status="ok")


@api.get("/overview")
def overview():
    return jsonify(_c().ranking.overview())


@api.get("/rankings/<int:index>")
def ranking(index: int):
    return jsonify(_c().ranking.ranking(index))


@api.get("/players/<player_id>")
def player(player_id: str):
    return jsonify(_c().ranking.player(player_id))


@api.get("/wiki/<player_id>")
def wiki_page(player_id: str):
    return jsonify(_c().wiki.page(player_id))


@api.put("/wiki/<player_id>")
def wiki_save(player_id: str):
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or "text" not in body:
        return jsonify(error="Corps JSON attendu : {\"text\": \"...\"}"), 400
    return jsonify(_c().wiki.save(player_id, body["text"]))


@api.post("/sync")
def sync():
    refresh = bool((request.get_json(silent=True) or {}).get("refresh"))
    report = _c().sync.sync(refresh=refresh)
    return jsonify(report.to_dict())


@api.errorhandler(NotFound)
def _not_found(exc):
    return jsonify(error=str(exc)), 404


@api.errorhandler(InvalidText)
@api.errorhandler(InvalidPlayerId)
def _bad_request(exc):
    return jsonify(error=str(exc)), 400


@api.errorhandler(StartGGError)
def _upstream(exc):
    return jsonify(error=str(exc)), 502
