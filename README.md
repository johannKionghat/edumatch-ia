# EduMatch-IA

Moteur de matching explicable entre candidats et formations : chances
d'admission et débouchés territoriaux.

Projet de certification Architecte en Intelligence Artificielle
(RNCP38777, niveau 7) — KIONGHAT Johann Guewol.

---

## Le système

```
score = affinité  ×  accessibilité  ×  débouchés
        règles       MODÈLE APPRIS    agrégats Sirene
```

| Terme | Question | Source | Nature |
|---|---|---|---|
| Affinité | Cela correspond-il aux centres d'intérêt ? | Requête utilisateur | Règles, aucun apprentissage |
| Accessibilité | Une chance d'être admis ? | Parcoursup 2018-2025 | LightGBM + SHAP |
| Débouchés | Cela mène-t-il à un emploi atteignable ? | Base Sirene | Agrégats, aucun apprentissage |

Le score est un produit des trois termes : si l'un s'annule, la
recommandation disparaît. Un seul des trois termes est appris, les deux
autres sont des règles et des dénombrements.

---

## Démarrage

```bash
cp .env.example .env          # puis renseigner les valeurs
make install                  # installe le paquet et les dépendances
make data                     # télécharge et prépare les données (une fois, hors conteneur)
```

### La pile locale

Une commande lève PostgreSQL, MLflow, Airflow (avec ses quatre DAG, voir
`docker/Dockerfile.airflow`), un entraînement, puis l'API. L'API ne
réentraîne jamais elle-même au démarrage (`src/edumatch/api/state.py`).

```bash
make up               # construit les images et lève la pile
make verifier-pile     # interroge chaque service, affiche l'état
make down              # arrête tout, supprime les volumes
```

`make` seul affiche toutes les commandes disponibles.

| Service | Adresse | Rôle |
|---|---|---|
| API | http://localhost:8000/docs | Matching, explicabilité, écran conseiller |
| MLflow | http://localhost:5000 | Suivi d'expériences, registre de modèles |
| Airflow | http://localhost:8080 | Orchestration des quatre DAG |
| PostgreSQL | localhost:5432 | Backend MLflow |

---

## Structure

```
edumatch-ia/
│
├── data/                      jamais versionné, sauf samples/
│   ├── raw/                   brut, immuable, lecture seule      [bronze]
│   ├── interim/                nettoyé, typé, réconcilié          [silver]
│   ├── processed/              prêt pour la modélisation          [gold]
│   ├── external/                référentiels tiers
│   └── samples/                échantillons versionnés, pour les tests
│
├── notebooks/                 EDA et exploration uniquement
│                              convention : NN-initiales-sujet.ipynb
│
├── src/edumatch/               code de production
│   ├── config.py               configuration centralisée, typée
│   ├── ingestion/              connecteurs Parcoursup, Sirene, référentiels
│   ├── quality/                contrôles Great Expectations
│   ├── transform/              projet dbt
│   ├── spark/                  agrégation Sirene distribuée
│   ├── features/               variables et calcul du label
│   ├── models/                 baseline, entraînement, SHAP, équité, ablation
│   ├── matching/                affinité × accessibilité × débouchés
│   ├── rag/                     assistant, brique secondaire
│   ├── api/                     FastAPI, schémas, écran conseiller
│   └── utils/
│
├── tests/
│   ├── unit/                   fonctions pures
│   ├── integration/            chaîne complète
│   └── data/                   contrats de données, non-régression du label
│
├── pipelines/                  DAG Airflow
├── models/                     artefacts locaux — le registre MLflow fait foi
├── configs/                    YAML par environnement : dev, staging, prod
├── docker/                     Dockerfile.train, Dockerfile.serve, Dockerfile.airflow
├── reports/                    figures et audit d'accessibilité
├── docs/sous-docs-projets/     documentation du projet
│
├── pyproject.toml              dépendances et configuration des outils
├── Makefile                    commandes courantes
├── docker-compose.yml          environnement local
├── .env.example
└── .gitignore
```

Le dossier de certification parle de bronze, silver et gold. Le système de
fichiers suit la convention data science habituelle : `raw = bronze`,
`interim = silver`, `processed = gold`.

---

## Les six principes

1. **Les notebooks ne sont pas de la production.** Dès qu'un bout de code
   se stabilise, il migre dans `src/` sous forme de fonctions testables, et
   le notebook importe depuis `src/`.

2. **Les données brutes sont immuables.** `data/raw/` ne se modifie
   jamais. Le test : je dois pouvoir tout supprimer sauf `raw/` et
   régénérer par `make data`.

3. **La configuration est externalisée.** Aucun chemin ni hyperparamètre
   en dur. Tout passe par `configs/` ; les secrets passent par
   l'environnement.

4. **Le suivi d'expériences commence dès la première expérience.** MLflow
   est branché avant le premier entraînement, sinon on finit avec un
   `model_final_v2.pkl` dont personne ne sait plus s'il est le bon.

5. **Les données se valident comme du code.** Great Expectations à
   l'entrée de chaque étape. Un échec bloque la chaîne : c'est ce qui
   casse le plus souvent en production, avant même le modèle.

6. **Tout est traçable.** Chaque artefact déployé remonte à un commit, un
   jeu de données daté et une exécution enregistrée.

---

## Les données

| Source | Volumétrie vérifiée | Licence |
|---|---|---|
| Parcoursup 2018-2025 (MESR) | 104 274 formation-années, 118 colonnes | Licence Ouverte v2.0 |
| Base Sirene (INSEE) | 43 896 818 établissements (dont 2 436 624 actifs et employeurs), 4,63 Go en Parquet (4 fichiers retenus, stock du 01/08/2026) | Licence Ouverte v2.0 |
| ONISEP, IDEO, RNCP | référentiels | Licence Ouverte |

Le label est le taux d'admission observé par cellule
`(formation × session × type de bac × boursier)` :

```
taux = prop_tot_{bg|bt|bp}[_brs] / nb_voe_pp_{bg|bt|bp}[_brs]
```

C'est un taux publié, ni simulé ni dérivé d'un indicateur de substitution.
77 159 cellules par millésime, 560 000 à 625 000 sur huit sessions.

---

## Contribuer

| Règle | Détail |
|---|---|
| Branche | `main` protégée, pull request obligatoire, CI verte requise |
| Commit | `type(portée): description` — `feat`, `fix`, `docs`, `test`, `refactor`, `chore` |
| Bloc concerné | À indiquer quand la tâche sert un critère : `feat(ingestion): connecteur Sirene [B3]` |
| Avant de pousser | `make lint && make test` |

Toute correction de bug embarque un test qui reproduit le bug.

---

## Documentation

`docs/sous-docs-projets/` contient la documentation, tenue à jour au fil du
développement.

| Dossier | Contenu |
|---|---|
| `ARCHITECTURE_EduMatch.md` | L'architecture d'ensemble |
| `01-donnees/` … `05-gouvernance/` | Par domaine |
| `adr/` | Une décision d'architecture par fichier |
