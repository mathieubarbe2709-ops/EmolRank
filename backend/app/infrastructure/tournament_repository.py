"""Persistance des tournois récupérés (cache JSON : un fichier par tournoi)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..domain.models import SetPlayer, Tournament, TournamentSet


def _filename(key: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "__", key.lower()) + ".json"


def _to_dict(t: Tournament) -> dict:
    return {
        "key": t.key, "url": t.url, "slug": t.slug, "name": t.name, "event_name": t.event_name,
        "start_at": t.start_at, "completed": t.completed,
        "sets": [{
            "id": s.id, "round": s.round, "round_text": s.round_text, "completed_at": s.completed_at,
            "started_at": s.started_at, "winner_index": s.winner_index, "dq": s.dq,
            "phase_group": s.phase_group,
            "players": [{"player_id": p.player_id, "tag": p.tag, "score": p.score,
                         "characters": list(p.characters)} for p in s.players],
        } for s in t.sets],
    }


def _from_dict(d: dict) -> Tournament:
    sets = tuple(TournamentSet(
        id=str(s["id"]), round=int(s["round"]), round_text=s.get("round_text", ""),
        completed_at=s.get("completed_at"), started_at=s.get("started_at"),
        winner_index=s.get("winner_index"), dq=bool(s.get("dq")),
        phase_group=s.get("phase_group"),
        players=tuple(SetPlayer(str(p["player_id"]), p["tag"], p.get("score"),
                                tuple(p.get("characters", ()))) for p in s["players"]),
    ) for s in d["sets"])
    return Tournament(key=d["key"], url=d.get("url", ""), name=d["name"], event_name=d.get("event_name", ""),
                      start_at=d.get("start_at"), sets=sets, slug=d.get("slug", ""),
                      completed=d.get("completed", True))


class TournamentRepository:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    def path_for(self, key: str) -> Path:
        return self.cache_dir / _filename(key)

    def exists(self, key: str) -> bool:
        return self.path_for(key).is_file()

    def load(self, key: str) -> Tournament | None:
        path = self.path_for(key)
        if not path.is_file():
            return None
        return _from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, tournament: Tournament) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path_for(tournament.key).with_suffix(".tmp")
        tmp.write_text(json.dumps(_to_dict(tournament), ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path_for(tournament.key))

    def signature(self, keys: list[str]) -> tuple:
        """Empreinte légère (mtime) servant à invalider le calcul mis en cache."""
        sig = []
        for k in keys:
            p = self.path_for(k)
            sig.append((k, p.stat().st_mtime_ns if p.is_file() else None))
        return tuple(sig)
