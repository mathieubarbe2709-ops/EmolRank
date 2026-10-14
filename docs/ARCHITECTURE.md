# Architecture N-tiers

| Tier | Dossier | Rôle |
|---|---|---|
| Présentation | `frontend/` | HTML/CSS/JS sans build. Aucune règle métier : affiche ce que l'API renvoie. |
| API | `backend/app/api/` | Routes Flask (JSON). Traduit HTTP ⇄ services. |
| Services | `backend/app/services/` | `RankingService` (vues du classement, calcul mis en cache), `SyncService` (téléchargement). |
| Domaine | `backend/app/domain/` | ELO, moteur de classement, vérification chronologique, personnages. Python pur, sans I/O. |
| Accès aux données | `backend/app/infrastructure/` | Client GraphQL start.gg, lecture de `tournaments.txt`, cache JSON des tournois. |

Dépendances : présentation → API → services → domaine ; services → infrastructure. Le domaine ne dépend de rien.

## Flux
`tournaments.txt` → (sync) start.gg → cache `data/cache/*.json` → vérification chronologique + rejeu ELO (recalculé si les fichiers changent) → un instantané par tournoi → API → front.

## Règles de calcul
- Joueur inscrit à 1000 ELO dès son premier set dans un des tournois listés.
- ELO standard (échelle 400), mis à jour **par set** : montant M = K × poids × |résultat − attendu|, K = 32.
- **Défaite adoucie** : le vainqueur gagne M, le perdant ne perd que 70 % de M (`ELO_LOSS_FACTOR`, 1 = ELO classique).
- **Decay** : −5 points (`ELO_DECAY`) à chaque tournoi manqué, uniquement pour un joueur déjà classé ; pas de plancher.
- Poids : Winner Bracket / poules / Grand Final = 1 ; Loser Bracket (round < 0) = 0,6 (`ELO_LOSERS_WEIGHT`).
- Sets DQ, byes et sets sans vainqueur : ignorés pour l'ELO.
- Personnage le plus joué : games par personnage, cumulées jusqu'au tournoi affiché.

## Vérification chronologique (rejouée à chaque calcul)
Tournois triés par date de début (`TOURNAMENT_FILE_ORDER` si l'ordre du fichier diffère, `TOURNAMENT_OVERLAP` si deux tournois se chevauchent) ;
sets triés par heure de fin, égalités départagées par progression dans le bracket. Contrôles : horodatage absent / inversé / futur,
set antérieur à l'event, joueur dont les rounds « reculent » (`PLAYER_ROUND_REGRESSION`). Résultat affiché dans le panneau
« Vérification chronologique » ; `python run.py check` renvoie le code 1 en cas d'erreur.

## Wiki joueur
- `GET /api/wiki/<id>` : texte (par défaut « <pseudo> est un joueur de Super Smash Bros. Ultimate »), fiche, personnage principal et résultats ;
  `PUT /api/wiki/<id>` `{"text": "..."}` : enregistre le texte (vide = retour au texte par défaut ; 20 000 caractères max).
- Les textes sont stockés dans `data/wiki/<id>.json` (`WIKI_DIR`), un fichier par joueur : ils survivent aux rafraîchissements et aux redémarrages.
  **Pensez à sauvegarder ce dossier** : contrairement à `data/cache`, il ne peut pas être reconstruit depuis start.gg.
- Place finale (`domain/placements.py`) : déduite de la structure du bracket — vainqueur/finaliste via le dernier set, les autres selon le round
  où ils ont perdu (3e, 4e, 5-6e, 7-8e, 9-12e…). Tournois non terminés : pas de place. Pour le 1er, le tableau affiche la grande finale.
- Couleurs : 1er jaune, 2e gris, 3e marron, 4e orange, 5-6e bleu clair, 7-8e bleu foncé, 9e et + violet (`domain/placements.py:band`, classes `.pl-*` du CSS).
