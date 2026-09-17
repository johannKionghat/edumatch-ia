"""Modèle dbt (Python) de la couche silver Parcoursup : `dbt run`.

## L'arbitrage d'outillage : DuckDB plutôt que PostgreSQL

Le projet a arbitré PostgreSQL comme base de l'entrepôt (voir la
configuration du service `postgres` de `docker-compose.yml`, au même titre
que MLflow). dbt a besoin d'un moteur pour s'exécuter, et le premier réflexe
serait de le brancher sur ce PostgreSQL déjà décidé.

**Ce qui a été vérifié avant de trancher**, sur ce poste, au moment d'écrire
cette étape : le PostgreSQL du projet (`docker compose up -d`, service
`postgres`) n'est **pas démarré**, et le port 5432 par défaut est déjà
occupé par le PostgreSQL d'un tout autre projet local — un `docker compose
up` échouerait sur un conflit de port avant même que dbt s'exécute. Brancher
dbt sur un service qui doit d'abord être démarré, sur un port qu'il faudrait
d'abord renégocier, pour réconcilier 104 274 lignes et 128 colonnes (16 Mo en
Parquet), est une charge d'exploitation sans rapport avec le volume réel.

DuckDB, retenu à la place, apporte exactement ce qu'exige cette étape et rien
de plus : il s'intègre nativement à dbt (`dbt-duckdb`), lit `data/raw/*.csv`
directement sans étape de chargement, ne demande aucun serveur, aucun port,
aucun identifiant — le fichier `.duckdb` local est le seul état, reconstruit
à chaque exécution depuis bronze, jamais un artefact à sauvegarder.

**Le seuil qui ferait revenir à PostgreSQL** : plusieurs pipelines
concurrents doivent lire ou écrire le même entrepôt en même temps (DuckDB
verrouille le fichier en écriture, un seul processus écrivain à la fois), ou
l'entrepôt doit rester interrogeable en continu par un service tiers (API,
tableau de bord branché en direct) plutôt que reconstruit à la demande. Aucun
des deux ne s'applique à cette étape : la réconciliation est un job batch,
exécuté par un DAG, pas un service.

**Ce que je ne tranche pas moi-même** : PostgreSQL reste la base retenue pour
tout ce qui n'est pas de la transformation par lots — le modèle en étoile
final, le stockage des scores servis par l'API. Le choix ci-dessus ne
porte que sur le moteur d'exécution de *cette* transformation, et mérite
d'être revu si le projet décide un jour de servir silver directement, sans
passer par le modèle en étoile de gold.

## Ce que fait ce modèle

Aucune logique de réconciliation n'est écrite ici : ce fichier appelle
`edumatch.transform.reconciliation.reconcilier_dataframes`, la même fonction
que `edumatch.transform.run` (le point d'entrée sans dbt). Ce qui change
n'est jamais le calcul, seulement le moteur qui a chargé chaque millésime —
`pandas.read_csv` pour `run.py`, `duckdb.read_csv` pour dbt — la fonction ne
connaît que le DataFrame qui en résulte. Deux moteurs, une seule vérité.

Ce module ne fait donc qu'une chose que `run.py` ne fait pas : déclarer,
via `dbt.source(...)`, la dépendance explicite aux huit sources bronze
(`../bronze/_sources.yml`), pour que `dbt docs generate` la restitue dans le
graphe de lignage (critère 3.8) sans intervention manuelle.

## Pourquoi les huit appels sont écrits en toutes lettres

dbt analyse statiquement (`ast.literal_eval`) les arguments de `dbt.source()`
pour construire son graphe de dépendances *avant* d'exécuter une seule ligne
de ce fichier : un appel construit dynamiquement (`f"parcoursup_{annee}"`
dans une boucle) échoue à l'analyse, avec une erreur de parsing, avant même
d'atteindre l'exécution. Les huit appels ci-dessous sont donc écrits
explicitement, un par millésime — une troisième occurrence de cette liste,
après `configs/base.yaml` et `_sources.yml`, couverte par le même test de
contrat que la seconde (`tests/unit/test_transform_dbt_sources.py`).
"""

import os

from edumatch.config import load_settings
from edumatch.transform.reconciliation import reconcilier_dataframes


def model(dbt, session):
    dbt.config(materialized="table")

    settings = load_settings(os.environ.get("EDUMATCH_ENV", "prod"))

    # Un appel littéral par millésime : voir le docstring du module pour la
    # contrainte qui l'impose (analyse statique de dbt.source()).
    sources = {
        2018: dbt.source("bronze_parcoursup", "parcoursup_2018"),
        2019: dbt.source("bronze_parcoursup", "parcoursup_2019"),
        2020: dbt.source("bronze_parcoursup", "parcoursup_2020"),
        2021: dbt.source("bronze_parcoursup", "parcoursup_2021"),
        2022: dbt.source("bronze_parcoursup", "parcoursup_2022"),
        2023: dbt.source("bronze_parcoursup", "parcoursup_2023"),
        2024: dbt.source("bronze_parcoursup", "parcoursup_2024"),
        2025: dbt.source("bronze_parcoursup", "parcoursup_2025"),
    }
    bruts = {
        millesime: sources[millesime].df()
        for millesime in settings.donnees.parcoursup.millesimes
        if millesime in sources
    }
    table, _ = reconcilier_dataframes(bruts, settings.modele.variables)
    return table
