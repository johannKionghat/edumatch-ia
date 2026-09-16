# EduMatch-IA — commandes courantes
# `make` sans argument affiche cette aide.

.DEFAULT_GOAL := help
.PHONY: help install up verifier-pile down config data quality transform transform-lignage gold sirene-agregats features baseline train evaluate explain api audit-purge audit-purge-appliquer ecran-verifier assistant-exemple test lint fmt docs clean up-prod down-prod demo-panne-qualite demo-restaurer-qualite verifier-idempotence-capturer verifier-idempotence-comparer

help:  ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ─── Environnement ──────────────────────────────────────────────────
install:  ## Installe le paquet et ses dépendances de développement
	pip install -e ".[dev,rag]"

# Séquence complète de la pile locale (E35) : lever, vérifier, arrêter.
#   1. make up             -> construit les images et démarre PostgreSQL, MLflow, Airflow,
#                              un entraînement unique (train), puis l'API
#   2. make verifier-pile  -> interroge chaque sonde, affiche un état lisible
#   3. make down           -> arrête tout et supprime les volumes
up:  ## Démarre la pile complète : PostgreSQL, MLflow, Airflow (DAG chargés), entraînement puis API
	# Les deux sous-dossiers d'écriture de l'API (journal d'audit article 12, écran conseiller)
	# doivent exister et être ouverts en écriture à l'utilisateur non-root du conteneur (uid
	# 10001, voir docker/Dockerfile.serve) AVANT le montage : sinon Docker crée le point de
	# montage appartenant à root sur un hôte Linux, et l'écriture échouerait quand même.
	mkdir -p data/processed/audit data/processed/supervision
	chmod -R 0777 data/processed/audit data/processed/supervision
	docker compose up -d --build

verifier-pile:  ## Interroge la sonde de chaque brique (api, mlflow, airflow, postgres, train) — état lisible
	bash scripts/verifier_pile.sh

down:  ## Arrête tout et supprime les volumes
	docker compose down -v

# ─── Production Airflow — instance dédiée (E33, ADR 0019) ─────────────
# À exécuter SUR L'INSTANCE Scaleway provisionnée par terraform/airflow.tf
# (edumatch-cicd), jamais sur le poste de développement : ces cibles
# supposent /srv/edumatch/data déjà monté (voir le cloud-init de l'instance)
# et un .env positionné avec les variables listées dans .env.example, section
# « Airflow en production ». Voir docs/sous-docs-projets/03-pipeline/
# orchestration.md pour la séquence complète, panne comprise.
up-prod:  ## Démarre la pile Airflow de production (LocalExecutor, PostgreSQL dédié, image du registre)
	docker compose -f docker-compose.prod.yml up -d

down-prod:  ## Arrête la pile Airflow de production (conserve les volumes de données)
	docker compose -f docker-compose.prod.yml down

demo-panne-qualite:  ## Panne filmée (3.12) : injecte un contrôle qualité bloquant sur le millésime Parcoursup le plus récent
	bash scripts/demo_panne_qualite.sh declencher

demo-restaurer-qualite:  ## Restaure l'injection ci-dessus, vérifiée par empreinte SHA-256 contre le manifeste
	bash scripts/demo_panne_qualite.sh restaurer

verifier-idempotence-capturer:  ## Idempotence (3.6), étape 1 : capture l'état courant des sorties avant de rejouer le pipeline
	PYTHONPATH=src python scripts/verifier_idempotence.py capturer

verifier-idempotence-comparer:  ## Idempotence (3.6), étape 2 : compare le CONTENU des sorties après le second passage
	PYTHONPATH=src python scripts/verifier_idempotence.py comparer

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

explain:  ## Explicabilité TreeSHAP (E25) : importance globale, exemples locaux, précalcul par cellule
	python -m edumatch.models.explain

ablation:  ## Ablation (E27) : apport de chaque source de variables, écart mesuré même s'il est nul
	python -m edumatch.models.ablation

derive:  ## Dérive (E34) : PSI/KS variables, cible et prédictions, seuil de réentraînement (ADR 0018)
	python -m edumatch.models.derive

register-model:  ## Enregistre la dernière exécution d'entraînement au registre de modèles (4.10)
	python -m edumatch.models.registre

# ─── Matching ───────────────────────────────────────────────────────
debouches:  ## Terme de débouchés (E28) : agrégat Sirene département x NAF k-anonymisé, correspondance formation -> IDÉO
	python -m edumatch.matching.debouches

matching-exemple:  ## Score à trois termes (E28) : exemple de bout en bout sur données réelles, pour un profil donné
	python -m edumatch.matching.exemple

# ─── Service ────────────────────────────────────────────────────────
api:  ## Lance l'API en local
	uvicorn edumatch.api.main:app --reload --port 8000

audit-purge:  ## Purge du journal d'inférence (E30, article 12) : SIMULATION, rien n'est modifié
	PYTHONPATH=src python -m edumatch.api.audit_purge

audit-purge-appliquer:  ## Purge du journal d'inférence : exécution RÉELLE (journal réécrit, agrégats mis à jour)
	PYTHONPATH=src python -m edumatch.api.audit_purge --appliquer

ecran-verifier:  ## Vérifie la syntaxe de l'écran conseiller (E31) : `node --check` sur app.js
	node --check src/edumatch/api/static/app.js

assistant-exemple:  ## Assistant documentaire (E32) : question d'exemple sur le corpus IDÉO réel, réponse et citations
	python -m edumatch.rag.exemple

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
