# EduMatch — Architecture de référence

Moteur de matching explicable candidats ↔ formations. Chaque composant
décrit ici est rattaché à un bloc du dossier de certification (RNCP 38777).

---

## 1. Vue d'ensemble — C4 niveau 1 (Contexte)

```
                          ┌─────────────────────────────┐
   Sources publiques      │          EDUMATCH           │      Utilisateurs
                          │                             │
 Parcoursup (MESR) ──────▶│  Pipeline ELT + Entrepôt    │◀───── Candidats (élèves,
 8 millésimes, 82 Mo      │  Modèle d'accessibilité     │       étudiants, reconversion)
                          │  Score à 3 termes           │
 Sirene (INSEE) ─────────▶│  API de matching            │◀───── Conseillers d'orientation
 43,9 M étab., 4,6 Go Pq  │  Écran de supervision       │       (contrôle humain, art. 14)
                          │  Chatbot RAG (secondaire)   │
 ONISEP / RNCP / IDEO ───▶│                             │◀───── DPO / Auditeurs
 référentiels, qq Mo      └─────────────────────────────┘       (journaux, registres)
```

Principe structurant : deux couches séparées par la sensibilité et le
volume. La couche de volume (Sirene, aucune donnée personnelle, plusieurs
Go) et la couche de décision (référentiels compacts + inférence, données
personnelles minimisées). Le calcul lourd s'exécute là où le risque RGPD
est structurellement nul.

---

## 2. C4 niveau 2 (Conteneurs) — cible de production

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        KUBERNETES MANAGÉ (Scaleway)                        │
│                                                                            │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────┐                   │
│  │  API FastAPI │   │   Airflow    │   │    MLflow     │                   │
│  │  2 réplicas  │   │  (scheduler  │   │  (tracking +  │                   │
│  │  + HPA       │   │  + webserver)│   │   registry)   │                   │
│  └──────┬───────┘   └──────┬───────┘   └───────┬───────┘                   │
│         │                  │                   │                           │
│  ┌──────┴───────┐   ┌──────┴───────────────────┴──────┐                    │
│  │ Écran        │   │      Prometheus + Grafana       │                    │
│  │ conseiller   │   │  (SLO p95 /matching < 300 ms)   │                    │
│  │ (HTML servi  │   └─────────────────────────────────┘                    │
│  │ par l'API)   │                                                          │
│  └──────────────┘                                                          │
└──────────┬──────────────────────────┬──────────────────────────────────────┘
           │                          │
┌──────────┴───────────┐   ┌──────────┴─────────────────┐
│  PostgreSQL managé   │   │  Stockage objet S3-compat. │
│  • schémas bronze /  │   │  • lac de données (bruts)  │
│    silver / gold     │   │  • artefacts MLflow        │
│  • transactionnel    │   │  • rapports de dérive PSI/KS│
│  • backend MLflow    │   │  • SHAP précalculés        │
└──────────────────────┘   └────────────────────────────┘
```

En local (J1 → J7), le même graphe tourne en Docker Compose avec trois
services (`postgres`, `mlflow`, `airflow`) et l'API lancée à la main. La
chaîne filmée à J8 est la même, provisionnée par Terraform.

---

## 3. Architecture de données — médaillon + étoile

```
        INGESTION (connecteurs idempotents, écriture atomique .part → rename)
              │
   ┌──────────┴──────────────────────────────────────────┐
   │                                                     │
   ▼                                                     ▼
CHAÎNE DE DÉCISION (mono-nœud)              CHAÎNE DE VOLUME (distribué)
Parcoursup 82 Mo (mesuré, E05) · référentiels           Sirene 4,6 Go Parquet
   │                                                     │
   ▼                                                     ▼
BRONZE  fichiers bruts, immuables           Lecture Spark : 9 colonnes / 54
   │    1 table / source / millésime        + predicate pushdown
   ▼    (contrôles qualité : GATE)         (actif · employeur · diffusible)
SILVER  8 millésimes réconciliés,                        │
   │    typés, harmonisés (Polars + dbt)                 ▼
   ▼                                        Agrégats (commune × NAF) :
GOLD    modèle en étoile                    densité, dynamique 10 ans,
   │                                        élargissement au bassin
   │                                                     │
   └───────────────┬─────────────────────────────────────┘
                   ▼
        TABLE NAF ↔ ROME ↔ FORMATION  (actif versionné, testé, couverture déclarée)
                   ▼
        TABLE DE VARIABLES (440 030 cellules × ~30 variables)
                   ▼
        ENTRAÎNEMENT → ÉVALUATION → [seuil] → PROMOTION MLflow → DÉPLOIEMENT
```

Modèle en étoile (gold) :

```
                     dim_formation
                          │
  dim_temps ──── fait_cellule_admission ──── dim_profil
                          │
                    dim_territoire ◀── agrégats Sirene rattachés ici
```

Les agrégats Sirene sont rattachés à `dim_territoire`, pas à la table de
faits : ça les rend réutilisables à la fois par le terme de débouchés et
par les variables du modèle sans duplication, et ça permet de retirer les
variables Sirene du modèle après ablation sans toucher au schéma.

---

## 4. Le système décisionnel

```
Requête candidat : { bac, mention, boursier, territoire, intérêts }   ← minimisation RGPD
        │
        ▼
┌──────────────────── POST /matching ────────────────────┐
│                                                        │
│  AFFINITÉ            ACCESSIBILITÉ         DÉBOUCHÉS   │
│  règles métier   ×   LightGBM          ×   agrégats    │
│  (déclaratif,        + SHAP précalculé     Sirene      │
│  rien de stocké)     par cellule           (lecture)   │
│                                                        │
│  score = 0 si l'un des termes = 0 (multiplicatif)      │
└────────────────────────┬───────────────────────────────┘
                         ▼
              Journalisation horodatée (art. 12)
                         ▼
        ┌────────────────┴────────────────┐
        ▼                                 ▼
  Réponse candidat                 Écran conseiller
  (fréquence observée,             revue · contexte · écarter
  facteurs SHAP,                   avec motif (art. 14)
  notice art. 13)                  POST /feedback
```

Sur la latence : les explications SHAP sont précalculées par cellule
(environ 77 000 par millésime, coût borné) et servies en lecture.
L'inférence LightGBM tient en mémoire. Le SLO p95 < 300 ms sur `/matching`
tient sans cache supplémentaire.

Le RAG (CamemBERT → FAISS → LangChain → Mistral-small) est une brique
secondaire, montée dans le même conteneur API : il restitue les sources
qui fondent une recommandation, il ne participe pas au score et n'est pas
dans le périmètre dérive/réentraînement.

---

## 5. Dépôt 1 — `edumatch-ia`

Structure inspirée de *Cookiecutter Data Science*, adaptée au projet.

```
edumatch-ia/
├── data/                          JAMAIS versionné, sauf samples/
│   ├── raw/                       brut, immuable          [= bronze]
│   ├── interim/                   nettoyé, réconcilié     [= silver]
│   ├── processed/                 prêt à modéliser        [= gold]
│   ├── external/                  référentiels tiers
│   └── samples/                   échantillons versionnés, font tourner les tests
│
├── notebooks/                     EDA uniquement — NN-initiales-sujet.ipynb
│                                  importe depuis src/, ne duplique pas
│
├── src/edumatch/
│   ├── config.py                  Pydantic Settings : chemins, seuils, DSN — zéro dur
│   ├── ingestion/
│   │   ├── parcoursup.py          API opendatasoft, 8 millésimes, idempotent
│   │   ├── sirene.py              catalogue data.gouv (URLs mensuelles), .part → rename
│   │   └── referentiels.py        ONISEP, RNCP, IDEO — téléchargement versionné
│   ├── quality/                   contrôles : schéma, complétude, cohérence, fraîcheur
│   ├── transform/                 projet dbt : bronze → silver → gold
│   │   ├── models/{bronze,silver,gold}/
│   │   └── schema.yml             tests not_null / unique / relationships → lignage
│   ├── spark/
│   │   └── sirene_agregats.py     job distribué : 9 col., filtre, agrégat, bassin
│   ├── referentiel/
│   │   └── naf_rome_formation.csv actif versionné + test de couverture dédié
│   ├── features/
│   │   ├── label.py               taux = prop_tot / nb_voe_pp, clip [0,1], pondération
│   │   └── build.py               variables N-1..N-3 uniquement (anti-fuite)
│   ├── models/
│   │   ├── baseline.py            taux N-1 de la même cellule — le plancher
│   │   ├── train.py               LightGBM pondéré + MLflow
│   │   ├── evaluate.py            MAE pondérée, ECE, courbe d'apprentissage
│   │   ├── explain.py             TreeSHAP exact, précalcul par cellule
│   │   ├── fairness.py            4 dimensions + ratio d'impact disparate
│   │   └── ablation.py            modèle A vs A+Sirene, même split, Δ chiffré
│   ├── matching/
│   │   ├── affinite.py            règles sur intérêts déclarés
│   │   ├── debouches.py           lecture des agrégats territoriaux
│   │   └── score.py               produit des trois termes
│   ├── rag/                       code existant repris tel quel
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/                /matching /explain /feedback /health
│   │   ├── audit.py               journalisation art. 12 (horodatage, pseudonymisation)
│   │   └── static/                écran conseiller HTML, RGAA
│   └── utils/
│
├── tests/
│   ├── unit/                      fonctions pures
│   ├── integration/               chaîne complète, base réelle
│   └── data/                      contrats de données, anti-fuite, idempotence
│
├── pipelines/
│   └── edumatch_pipeline.py       DAG : ingestion→GE→dbt→Spark→features→train→eval→promote
│
├── configs/                       base.yaml + dev / staging / prod
├── docker/                        Dockerfile.train, Dockerfile.serve
├── models/                        artefacts locaux — le registre MLflow fait foi
├── reports/figures/               figures pour le dossier et la soutenance
│
├── docs/sous-docs-projets/
│   ├── 00-vue-ensemble.md
│   ├── 01-donnees/ … 05-gouvernance/
│   ├── ARCHITECTURE_EduMatch.md   ce document
│   ├── adr/                       un ADR par décision, écrit le jour même
│   └── dossier/                   dossier de certification + son générateur
│
├── .github/workflows/             CI/CD (miroir du dépôt 2 pour les tests)
├── pyproject.toml   Makefile   docker-compose.yml
├── .gitignore   .gitattributes   .env.example
└── README.md
```

Le dossier de certification parle bronze / silver / gold ; le système de
fichiers suit la convention data science standard. `raw = bronze`,
`interim = silver`, `processed = gold` — l'équivalence est rappelée dans
le README.

Trois choix qui comptent pour la défense devant le jury :

- `config.py` centralisé — aucun seuil ni chemin en dur. Chaque seuil
  cité en ADR pointe vers une ligne de `configs/*.yaml`.
- `api/audit.py` isolé — la journalisation de l'article 12 est un
  composant nommé, pas un effet de bord dispersé dans les routes.
- `data/samples/` versionné — quelques centaines de lignes par source,
  qui permettent d'exécuter la suite de tests sans télécharger 4,6 Go.
  C'est ce qui rend la CI possible.

## 6. Dépôt 2 — `edumatch-cicd`

```
edumatch-cicd/
├── .github/workflows/
│   ├── ci.yml                     # ruff → pytest → couverture (déclenché par dépôt 1)
│   ├── build.yml                  # image Docker taguée hash de commit → registry
│   └── deploy.yml                 # terraform apply → kubectl apply → healthcheck
├── terraform/
│   ├── kubernetes.tf              # cluster managé Scaleway, 2 nœuds
│   ├── database.tf                # PostgreSQL managé
│   ├── storage.tf                 # objet S3-compatible (lac + artefacts MLflow)
│   └── network.tf                 # réseau privé, groupes de sécurité
├── k8s/
│   ├── api-deployment.yaml        # 2 réplicas, requests/limits explicites
│   ├── service.yaml + ingress.yaml# TLS
│   └── hpa.yaml                   # matérialise l'argument saisonnalité 1:6
└── monitoring/
    ├── prometheus/                # scrape API + Airflow
    ├── grafana/                   # 1 dashboard technique + 1 dashboard modèle
    └── derive/                    # PSI + KS calculés directement (ADR 0018), seuil documenté
```

La chaîne de traçabilité visée en soutenance : commit → image (tag =
hash) → modèle (version MLflow) → déploiement. Toute version en
production remonte à un commit et un modèle.

---

## 7. Flux MLOps — orchestration et boucle de dérive

```
        Airflow DAG (mensuel Sirene / annuel Parcoursup / sur publication référentiels)
        ┌────────────────────────────────────────────────────────────────┐
        │ ingestion → [GE: GATE] → dbt → Spark Sirene → features         │
        │     → train (MLflow) → evaluate ── seuil OK? ──▶ promote       │
        │                              └── non ──▶ alerte, pas de promo  │
        └────────────────────────────────────────────────────────────────┘
                                    ▲
        PSI + KS calculés directement (ADR 0018) ────────┘
        dérive données / concept / prédictions
        au-delà du seuil documenté → déclenchement du réentraînement
```

Trois propriétés du DAG, testées et filmées : idempotence (relance = même
résultat), reprise sur erreur (retries à temporisation croissante),
blocage qualité (un échec de contrôle qualité arrête tout, une donnée
corrompue n'atteint jamais le modèle).

---

## 8. Sécurité et conformité, mappées sur l'architecture

| Exigence | Composant qui la porte |
|---|---|
| Minimisation (RGPD) | Le contrat de l'API : 5 champs, rien de stocké côté affinité |
| Art. 22 / droit à explication | SHAP précalculé + restitution en fréquence observée |
| Art. 12 AI Act — journalisation | `api/audit.py`, durée définie puis pseudonymisation |
| Art. 14 — contrôle humain | Écran conseiller (`api/static/`) + route `/feedback` |
| Séparation entraînement / inférence | Aucune donnée personnelle en bronze/silver/gold |
| Souveraineté (mineurs) | Scaleway, hébergement UE, chiffrement, RBAC |
| Secrets | Variables d'env + secrets k8s ; incident Firebase documenté (Bloc 1) |
| Non-discrimination | Genre hors modèle, substituts testés, `fairness.py` 4 dimensions |

---

## 9. Les cinq arbitrages qui structurent cette architecture

1. **Distribué là où c'est nécessaire, seulement là.** Spark sur Sirene
   (jointure 43,9 M d'établissements × formations, mesuré en E06 par
   métadonnée Parquet), Polars + dbt sur Parcoursup (82 Mo, mesuré en
   E05). Le seuil est une règle mesurée, pas un principe général.
2. **Latence par précalcul, pas par cache.** L'espace des cellules est
   fini, donc SHAP et agrégats débouchés sont précalculés : le SLO est
   garanti par construction, sans Redis ni couche supplémentaire.
3. **Coût par élasticité.** HPA dimensionné sur la saisonnalité 1:6 ;
   local jusqu'à J7, cloud provisionné puis détruit par Terraform à J8.
4. **Conformité par construction.** La séparation volume/décision rend le
   périmètre RGPD minimal architecturalement, pas par une politique qu'il
   faudrait faire respecter à côté.
5. **Réversibilité mesurée.** L'ablation peut retirer les variables
   Sirene du modèle sans toucher au schéma (agrégats sur
   `dim_territoire`) ; la promotion du modèle est conditionnée à un
   seuil, le rollback est un re-tag MLflow.
