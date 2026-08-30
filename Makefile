# EduMatch-IA — commandes courantes
# `make` sans argument affiche cette aide.

.DEFAULT_GOAL := help
.PHONY: help install up down config data quality transform transform-lignage gold sirene-agregats features baseline train evaluate api test lint fmt docs clean

help:  ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ─── Environnement ──────────────────────────────────────────────────
install:  ## Installe le paquet et ses dépendances de développement
	pip install -e ".[dev,rag]"

up:  ## Démarre PostgreSQL, MLflow et Airflow
	docker compose up -d

down:  ## Arrête tout et supprime les volumes
	docker compose down -v

config:  ## Affiche la configuration résolue pour EDUMATCH_ENV (secrets masqués)
	# SecretStr masque déjà ces champs par défaut dans son repr ; le pop()
	# ci-dessous est une défense en profondeur explicite pour du JSON exporté
	# tel quel (copié-collé, journal, ticket) — pas un doublon à retirer.
	PYTHONPATH=src python -c "\
import json; \
from edumatch.config import get_settings; \
s = get_settings(); \
d = s.model_dump(mode='json'); \
[d.pop(k, None) for k in ('postgres_password', 'mistral_api_key', 'scw_secret_key')]; \
print(json.dumps(d, indent=2, ensure_ascii=False))"

# ─── Données ────────────────────────────────────────────────────────
data:  ## Régénère TOUTES les données dérivées depuis data/raw
	python -m edumatch.ingestion.parcoursup
	python -m edumatch.ingestion.sirene
	$(MAKE) quality
	$(MAKE) transform
	$(MAKE) gold
	$(MAKE) sirene-agregats
	$(MAKE) features
	# naf-rome (E18) n'est pas enchaînée ici : elle suppose data/external/referentiels/
	# déjà peuplé par edumatch.ingestion.referentiels, qui n'a pas encore de cible
	# dédiée dans ce Makefile (gap antérieur à E18, pas corrigé ici). Lancer
	# `make naf-rome` séparément une fois les référentiels téléchargés.

quality:  ## Exécute les contrôles qualité (bloquants)
	python -m edumatch.quality.run

transform:  ## Réconcilie les huit millésimes Parcoursup (bronze -> silver, E15)
	python -m edumatch.transform.run

gold:  ## Construit le modèle en étoile (silver -> gold, E16) : faits et dimensions
	python -m edumatch.transform.run_etoile

transform-lignage:  ## Rejoue silver ET gold via dbt, génère le graphe de lignage complet (dbt docs)
	python -m edumatch.transform.run_dbt

sirene-agregats:  ## Agrège Sirene par commune x NAF (E17) : projection 9 colonnes, filtrage à la lecture
	python -m edumatch.spark.run_sirene_agregats

naf-rome:  ## Réconcilie NAF -> ROME -> formation (E18) : couverture mesurée et déclarée
	python -m edumatch.referentiel.naf_rome_formation

samples:  ## Régénère data/samples/ depuis data/raw et data/external (config prod)
	python -m edumatch.ingestion.echantillons

features:  ## Construit la table de variables
	python -m edumatch.features.build

# ─── Modèle ─────────────────────────────────────────────────────────
baseline:  ## Mesure la baseline (taux de la session précédente, E21) : le plancher à battre
	python -m edumatch.models.baseline

train:  ## Entraîne le modèle et enregistre l'exécution dans MLflow
	python -m edumatch.models.train

evaluate:  ## Évalue sur le jeu de test, produit calibration et équité
	python -m edumatch.models.evaluate

# ─── Service ────────────────────────────────────────────────────────
api:  ## Lance l'API en local
	uvicorn edumatch.api.main:app --reload --port 8000

# ─── Qualité du code ────────────────────────────────────────────────
test:  ## Lance la suite de tests
	PYTHONPATH=src python -m pytest -q

lint:  ## Vérifie le style et les erreurs statiques
	ruff check src tests

fmt:  ## Formate le code
	ruff format src tests

# ─── Documentation ──────────────────────────────────────────────────
docs:  ## Régénère le dossier de certification
	cd docs/sous-docs-projets/dossier && python _build_dossier.py

clean:  ## Supprime les artefacts d'exécution
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
