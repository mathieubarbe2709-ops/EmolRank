"""Configuration (variables d'environnement, fichier .env facultatif)."""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Config:
    startgg_token: str = ""
    tournaments_file: Path = ROOT / "tournaments.txt"
    cache_dir: Path = ROOT / "data" / "cache"
    wiki_dir: Path = ROOT / "data" / "wiki"
    frontend_dir: Path = ROOT / "frontend"
    elo_initial: float = 1000.0
    elo_k: float = 32.0
    elo_losers_weight: float = 0.6
    elo_loss_factor: float = 0.7
    elo_decay: float = 5.0
    host: str = "127.0.0.1"
    port: int = 5000

    @classmethod
    def from_env(cls) -> "Config":
        _load_dotenv(ROOT / ".env")
        env = os.environ
        return cls(
            startgg_token=env.get("STARTGG_TOKEN", ""),
            tournaments_file=Path(env.get("TOURNAMENTS_FILE", ROOT / "tournaments.txt")),
            cache_dir=Path(env.get("CACHE_DIR", ROOT / "data" / "cache")),
            wiki_dir=Path(env.get("WIKI_DIR", ROOT / "data" / "wiki")),
            elo_initial=float(env.get("ELO_INITIAL", 1000)),
            elo_k=float(env.get("ELO_K", 32)),
            elo_losers_weight=float(env.get("ELO_LOSERS_WEIGHT", 0.6)),
            elo_loss_factor=float(env.get("ELO_LOSS_FACTOR", 0.7)),
            elo_decay=float(env.get("ELO_DECAY", 5)),
            host=env.get("HOST", "127.0.0.1"),
            port=int(env.get("PORT", 5000)),
        )

    def for_demo(self) -> "Config":
        return replace(self, tournaments_file=ROOT / "demo" / "tournaments.txt",
                       cache_dir=ROOT / "demo" / "cache", wiki_dir=ROOT / "demo" / "wiki")
