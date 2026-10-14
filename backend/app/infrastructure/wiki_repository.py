"""Persistance des textes du Wiki : un fichier JSON par joueur dans `wiki_dir` (survit aux redémarrages)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from threading import Lock

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class InvalidPlayerId(ValueError):
    pass


class WikiRepository:
    def __init__(self, wiki_dir: Path):
        self.wiki_dir = wiki_dir
        self._lock = Lock()

    def _path(self, player_id: str) -> Path:
        if not _SAFE_ID.match(player_id):
            raise InvalidPlayerId("Identifiant de joueur invalide")
        return self.wiki_dir / f"{player_id}.json"

    def load(self, player_id: str) -> dict | None:
        path = self._path(player_id)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def save(self, player_id: str, text: str) -> dict:
        """Enregistre le texte (écriture atomique). Un texte vide supprime la page personnalisée."""
        path = self._path(player_id)
        with self._lock:
            if not text.strip():
                path.unlink(missing_ok=True)
                return {"player_id": player_id, "text": "", "updated_at": None}
            self.wiki_dir.mkdir(parents=True, exist_ok=True)
            record = {"player_id": player_id, "text": text, "updated_at": int(time.time())}
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(path)
            return record
