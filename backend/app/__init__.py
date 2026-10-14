"""Fabrique de l'application Flask et composition des tiers (injection de dépendances)."""
from __future__ import annotations

from dataclasses import dataclass

from flask import Flask, send_from_directory

from .config import Config
from .infrastructure.startgg_client import StartGGClient
from .infrastructure.tournament_repository import TournamentRepository
from .services.ranking_service import RankingService
from .services.sync_service import SyncService
from .services.wiki_service import WikiService
from .infrastructure.wiki_repository import WikiRepository


@dataclass
class Container:
    ranking: RankingService
    sync: SyncService
    wiki: WikiService


def build_container(config: Config, client: StartGGClient | None = None) -> Container:
    repository = TournamentRepository(config.cache_dir)
    client = client or StartGGClient(config.startgg_token)
    ranking = RankingService(config, repository)
    return Container(ranking, SyncService(config.tournaments_file, repository, client),
                     WikiService(ranking, WikiRepository(config.wiki_dir)))


def create_app(config: Config | None = None, client: StartGGClient | None = None) -> Flask:
    from .api.routes import api

    config = config or Config.from_env()
    app = Flask(__name__, static_folder=None)
    app.extensions["container"] = build_container(config, client)
    app.register_blueprint(api)

    frontend = config.frontend_dir

    @app.get("/")
    def index():
        return send_from_directory(frontend, "index.html")

    @app.get("/<path:path>")
    def static_files(path: str):
        return send_from_directory(frontend, path)

    return app
