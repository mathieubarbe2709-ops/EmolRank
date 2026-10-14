# Smash Ranking — classement ELO Super Smash Bros. Ultimate

Site web qui calcule un classement ELO à partir d'une liste de tournois start.gg et permet de naviguer tournoi par tournoi.
Back-end Python (Flask), front-end HTML/CSS/JS sans build, architecture N-tiers (voir `docs/ARCHITECTURE.md`).

## Démarrage rapide
```bash
pip install -r requirements.txt
python run.py serve --demo      # données fictives -> http://127.0.0.1:5000
```

Autres commandes : `python run.py check` (rapport chronologique), `python run.py sync --refresh` (tout retélécharger).
Tests : `pip install -r requirements-dev.txt && cd backend && python -m pytest`.

## Wiki des joueurs
Dans le classement, cliquez sur un joueur puis sur **Voir la page Wiki** (ou ouvrez `#wiki=<id>`). La page affiche le personnage principal à gauche,
un texte modifiable (bouton **Modifier**, Ctrl+Entrée pour enregistrer) et le tableau des résultats ; **Retour au classement** est en haut à droite.
Les textes sont enregistrés dans `data/wiki/` : sauvegardez ce dossier avec `tournaments.txt` et `.env`.

## Limites connues
- La place d'un joueur est déduite des sets (start.gg ne la fournit pas ici) ; elle suit la double élimination standard. Un tournoi qui n'est pas en double élimination peut donner des places approximatives.
- Seuls les events Ultimate en simple sont acceptés.
- Un joueur est identifié par son compte start.gg ; le même joueur sous deux comptes serait compté deux fois.
