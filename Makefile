# EduMatch-IA — commandes courantes
# `make` sans argument affiche cette aide.

.DEFAULT_GOAL := help
.PHONY: help install up down data quality features train evaluate api test lint fmt docs clean

help:  ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ─── Environnement ──────────────────────────────────────────────────
install:  ## Installe le paquet et ses dépendances de développement
	pip install -e ".[dev,rag]"

up:  ## Démarre PostgreSQL, MLflow et Airflow
	docker compose up -d

down:  ## Arrête tout et supprime les volumes
	docker compose down -v

# ─── Données ────────────────────────────────────────────────────────
data:  ## Régénère TOUTES les données dérivées depuis data/raw
	python -m edumatch.ingestion.parcoursup
	python -m edumatch.ingestion.sirene
	$(MAKE) quality
	$(MAKE) features

quality:  ## Exécute les contrôles qualité (bloquants)
	python -m edumatch.quality.run

features:  ## Construit la table de variables
	python -m edumatch.features.build

# ─── Modèle ─────────────────────────────────────────────────────────
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
