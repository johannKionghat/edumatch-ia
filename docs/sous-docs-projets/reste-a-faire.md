# Reste à faire

Feuille de route vivante. Je la tiens à jour au fil du projet et des
évaluations du jury.

**État au démarrage** : l'architecture est en place, le dépôt est initialisé,
**aucun code métier n'est écrit**. Tout ce qui suit est à construire.

---

## Ce qui est fait

| Élément | État |
|---|---|
| Arborescence normée | ✅ |
| Dépôt Git, `.gitignore` vérifié, `.gitattributes` | ✅ |
| `Makefile` auto-documenté, cible `make data` | ✅ |
| `configs/` — base, dev, staging, prod | ✅ |
| `pyproject.toml`, `docker-compose.yml`, `.env.example` | ✅ |
| `README` — structure commentée, démarrage | ✅ |
| Architecture de référence, C4 niveaux 1 et 2 | ✅ |
| ADR 0001 — ELT plutôt qu'ETL | ✅ |

**Reste sur l'infrastructure** : créer les deux dépôts distants, protéger `main`.

---

## Priorités du jury

*Aucune évaluation à ce jour. Lancer `/jury` une fois les premières briques
posées.*

---

## Bloc 1 — Gouvernance des données

- [ ] Plan de gouvernance : classification, rôles, règles d'usage
- [ ] Registre des traitements
- [ ] Registre des sources et de leurs licences
- [ ] AIPD — obligatoire, profilage de mineurs
- [ ] Model Card
- [ ] Matrice de risques
- [ ] Correspondance AI Act, articles 9 à 15
- [ ] Politique de gestion des secrets, avec l'incident documenté
- [ ] Procédure d'audit annuelle
- [ ] Slides de présentation, 15 min

## Bloc 2 — Architecture de données

- [ ] `config.py` — Pydantic Settings, chargement des YAML par environnement
- [ ] Modèle en étoile — schéma dbt, grain écrit
- [ ] Diagrammes C4 exportés en image pour le dossier
- [ ] `docker/Dockerfile.train`, `docker/Dockerfile.serve`
- [ ] Terraform — cluster, base, stockage objet, réseau *(dépôt 2)*
- [ ] Manifestes Kubernetes, dont le HPA *(dépôt 2)*
- [ ] Prometheus et Grafana *(dépôt 2)*
- [ ] Vidéo de l'infrastructure en production

## Bloc 3 — Pipelines

- [ ] `ingestion/parcoursup.py` — 8 millésimes, idempotent, écriture atomique
- [ ] `ingestion/sirene.py` — catalogue mensuel, Parquet
- [ ] `ingestion/referentiels.py` — ONISEP, RNCP, IDEO
- [ ] `quality/expectations/` — schéma, complétude, cohérence, fraîcheur, **bloquantes**
- [ ] `transform/` — projet dbt, bronze → silver → gold, tests et lignage
- [ ] `spark/sirene_agregats.py` — 9 colonnes, filtres, agrégats commune × NAF, bassin
- [ ] `referentiel/naf_rome_formation.csv` — actif versionné, **taux de couverture mesuré**
- [ ] `features/label.py` — taux d'admission par cellule, pondération
- [ ] `features/build.py` — variables N-1 à N-3 uniquement, **anti-fuite**
- [ ] `pipelines/edumatch_pipeline.py` — DAG complet, reprise, blocage qualité
- [ ] Tests : idempotence, anti-fuite, contrats de données
- [ ] Vidéo du pipeline, **avec panne provoquée et reprise**

## Bloc 4 — Déploiement

- [ ] `models/baseline.py` — taux de la session précédente, **à mesurer en premier**
- [ ] `models/train.py` — LightGBM pondéré, MLflow
- [ ] `models/evaluate.py` — MAE pondérée, calibration, ECE, courbe d'apprentissage
- [ ] `models/explain.py` — TreeSHAP, précalcul par cellule
- [ ] `models/fairness.py` — 4 dimensions, ratio d'impact disparate
- [ ] `models/ablation.py` — apport de Sirene mesuré, pas postulé
- [ ] `matching/affinite.py`, `debouches.py`, `score.py`
- [ ] `api/main.py`, `routes/`, schémas Pydantic
- [ ] `api/audit.py` — journalisation article 12
- [ ] `api/static/` — écran conseiller, **conforme RGAA**
- [ ] `rag/` — assistant, brique secondaire, **réécrit** et non repris du MVP
- [ ] CI/CD — trois workflows *(dépôt 2)*
- [ ] Evidently — dérive, seuil documenté en ADR
- [ ] Vidéo de la solution en production

---

## EDA — préalable au Bloc 4

- [ ] `notebooks/01-jgk-eda-label.ipynb` — distribution du label par cellule
- [ ] Écart entre types de baccalauréat, variation par filière
- [ ] Taux de féminisation par filière, concentration de la ségrégation
- [ ] Sélectivité par filière
- [ ] Stabilité inter-millésimes 2018-2025
- [ ] Corrélations — **les substituts du genre**

> Journée à faire soi-même. C'est la seule source de matière personnelle pour la
> soutenance.

---

## ⚠️ Incohérences relevées

*Aucune.*

> Toute divergence entre le code, la documentation et le dossier de
> certification est inscrite ici sous cette mention, et remontée. Elle n'est
> jamais corrigée silencieusement.
