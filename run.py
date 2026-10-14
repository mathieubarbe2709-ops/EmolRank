#!/usr/bin/env python3
"""Point d'entrée : serveur web et commandes utilitaires.

  python run.py serve [--demo]       lance le site (http://127.0.0.1:5000)
  python run.py sync [--refresh]     télécharge depuis start.gg les tournois de tournaments.txt
  python run.py check [--demo]       calcule et affiche la vérification chronologique
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app import build_container, create_app  # noqa: E402
from app.config import Config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")
    serve = sub.add_parser("serve")
    serve.add_argument("--demo", action="store_true", help="utilise les données fictives du dossier demo/")
    sync = sub.add_parser("sync")
    sync.add_argument("--refresh", action="store_true", help="retélécharge aussi les tournois déjà en cache")
    check = sub.add_parser("check")
    check.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    config = Config.from_env()
    if getattr(args, "demo", False):
        config = config.for_demo()

    if args.cmd == "sync":
        report = build_container(config).sync.sync(refresh=args.refresh)
        print(f"Téléchargés : {len(report.fetched)} | déjà en cache : {len(report.cached)}")
        for line in report.problems + report.errors:
            print(" !", line)
        return 1 if report.errors else 0

    if args.cmd == "check":
        overview = build_container(config).ranking.overview()
        for t in overview["tournaments"]:
            print(f"[{t['index']}] {t['name']} — {t['participants']} joueurs, {t['sets_counted']} sets comptés")
        for i in overview["chronology"]["issues"]:
            print(f" {i['level'].upper():7} {i['code']}: {i['message']}")
        for m in overview["missing"]:
            print(" ABSENT  non synchronisé :", m)
        print("Chronologie :", "OK" if overview["chronology"]["ok"] else "ANOMALIES")
        return 0 if overview["chronology"]["ok"] else 1

    app = create_app(config)
    print(f"→ http://{config.host}:{config.port}")
    app.run(host=config.host, port=config.port, debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
