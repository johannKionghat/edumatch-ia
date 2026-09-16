---
marp: true
paginate: true
---

# EduMatch-IA

Moteur de matching explicable entre candidats et formations

Certification Architecte en Intelligence Artificielle — RNCP38777

KIONGHAT Johann Guewol

---

## Le problème et le cas d'usage

Un lycéen de terminale construit sa liste de vœux Parcoursup sans repère
chiffré sur ses chances réelles d'admission, ni sur les débouchés de chaque
formation sur son territoire.

Le système assiste un **conseiller d'orientation**, jamais le candidat seul.

Public concerné : lycéens de terminale, **majoritairement mineurs**.
→ analyse d'impact obligatoire dès la conception (RGPD art. 35).

---

## Un score à trois termes, un seul appris

```
score = affinité  ×  accessibilité  ×  débouchés
        règles       MODÈLE APPRIS    agrégats Sirene
        (requête)    (Parcoursup)     (aucun apprentissage)
```

Multiplicatif : un terme nul supprime la recommandation.

Un seul composant demande un modèle : **l'accessibilité**. Les deux autres
sont des règles et des dénombrements, pas d'opacité là où elle n'apporte
rien.

---

## Les données : cinq sources publiques, mesurées

| Source | Volumétrie mesurée | Licence |
|---|---|---|
| Parcoursup (MESR) | 104 274 formation-années, 118 colonnes en 2025, 82 Mo | Licence Ouverte v2.0 |
| Sirene (INSEE) | 43 896 818 établissements, 6,44 Go compressés (stock 01/08/2026) | Licence Ouverte v2.0 |
| ONISEP / IDÉO | 5 869 formations, 1 534 métiers | **ODbL**, partage à l'identique |
| RNCP (France Compétences) | 30 484 fiches, dont 7 000 actives | Licence Ouverte v2.0 |
| France Travail (table ROME↔NAF) | référentiel de correspondance | Licence Ouverte v2.0 |

Chaque chiffre se reproduit par une commande (`scripts/verifier_sources.sh`).

---

## L'architecture : ELT, médaillon, entrepôt en étoile

- **ELT** plutôt qu'ETL : lignage brut conservé, retransformation sans
  re-téléchargement
- **Bronze → silver → gold** (`raw` → `interim` → `processed`)
- Entrepôt en étoile (dbt) : grain à la maille cellule
  `(session, formation, type de bac, boursier)` : **440 030 lignes**,
  26 nœuds dbt, tous verts
- Détail complet : `02-architecture/c4-contexte.md`,
  `c4-conteneurs.md`, `modele-etoile.md`

---

## Le volume : Polars contre Spark, mesuré

Sur le fichier Sirene complet (43 896 818 lignes, 54 colonnes), 9 colonnes
lues, mêmes règles métier, même résultat vérifié ligne à ligne :

| Moteur | Temps mesuré |
|---|---|
| Polars | **18,2 s** |
| PySpark (local) | 87,0 s (18,0 s démarrage JVM + 69,0 s calcul) |

**Spark 4,8× plus lent** sur ce volume. Retenu quand même en second moteur,
branché et testé, pour un seuil de bascule écrit : fusion de plusieurs
fichiers Sirene, ou calcul qui dépasse la mémoire d'un poste de
développement.

---

## La qualité et le pipeline

- Contrôles bloquants (Pandera) : schéma, complétude, cohérence, fraîcheur
- Démontré, pas affirmé : `python -m edumatch.quality.run` sur les données
  réelles → **code de sortie 1** : 5 établissements Sirene portent une date
  de création en 2054 à 5015, bloqués ; 10 613 immatriculations anticipées
  légitimes, seulement averties
- Le DAG d'orchestration porte cette même chaîne, avec reprise sur erreur

---

## Le modèle : le résultat tel qu'il est

Baseline sans apprentissage : taux de la même cellule à la session
précédente.

| | Modèle appris (LightGBM) | Baseline |
|---|---:|---:|
| MAE pondérée, validation 2024 | **0,0690** | 0,0727 |
| MAE pondérée, **test 2025** | 0,0758 | **0,0701** |
| ECE, validation 2024 | **0,0030** | 0,0141 |
| ECE, **test 2025** | 0,0371 | **0,0322** |

**Le modèle bat la baseline en validation. Il la perd en test, en
précision comme en calibration.** Résultat rapporté tel quel, il n'a pas
été atténué.

---

## Pourquoi : dérive temporelle, pas manque de données

Deux mesures indépendantes convergent :

- **Courbe d'apprentissage** : gain marginal divisé par deux à chaque
  doublement du volume (0,0035 → 0,0018 → 0,0007). Ajouter des données ne
  comblerait pas l'écart.
- **Non-stationnarité de la cible** : moyenne des taux par formation
  0,491 → 0,534 (2024) → 0,522 (2025), pendant que le taux agrégé baisse.

Le modèle a appris ce que 2020-2023 pouvait apprendre. Ce que 2025 apporte
de nouveau, il ne l'a pas vu.

---

## Explicabilité : SHAP

TreeSHAP, valeurs de Shapley exactes. Axiome d'efficacité vérifié à
2,1 × 10⁻¹⁵ près sur le modèle réel.

| Variable | Part de l'explication globale |
|---|---:|
| Taux de la session précédente | 33,5 % |
| Nombre de vœux, session précédente | 9,1 % |
| Filière | 8,4 % |
| Département | 7,5 % |

Précalcul complet sur 440 030 cellules : 8,3 minutes, 99,8 Mo. L'API lit
un précalcul, elle ne recalcule jamais SHAP en direct.

---

## Équité : un ratio sous le seuil légal

Le genre n'entre **jamais** dans le modèle (vérifié par mutation de code).
Il sert uniquement à l'audit, a posteriori.

- Substituts du genre (filière, sélectivité, territoire) : **14,2 %** de
  l'explication SHAP, alors que le genre n'est jamais en entrée
- Sur les formations à plus de 80 % de candidates : ratio d'impact
  disparate **0,76**, sous le seuil légal des quatre cinquièmes (0,80),
  même s'il améliore le 0,63 de la baseline
- Sur la calibration par groupe (définition d'équité retenue **avant**
  la mesure), le modèle sur-annonce sur ce groupe (ECE 0,066 contre
  0,032-0,034 ailleurs) : la baseline y est mieux calibrée

Retirer les substituts ne répare pas l'équité (+0,0006 de MAE, ratio
dégradé de 0,66 à 0,62) : l'exclusion de variables ne peut pas être le
seul levier.

---

## La gouvernance : un avis scindé

AIPD, Model Card (format Mitchell), correspondance AI Act, tenues à jour.

**L'avis du délégué à la protection des données se scinde**, parce que les
mesures ne pointent pas toutes dans la même direction :

- **Défavorable** à la restitution de l'estimation du modèle appris à des
  candidats réels : il échoue au test de nécessité, une règle sans
  apprentissage, déjà construite, fait mieux sur la session la plus
  récente
- **Favorable sous réserves** au reste du dispositif : affinité, écran de
  supervision, journalisation, purge
- **Favorable sans réserve** à l'exploitation en environnement de
  démonstration et d'évaluation, sans restitution à des candidats mineurs
  réels, le périmètre de cette certification

Cinq motifs de blocage documentés avant toute mise en service réelle
(contrôle d'accès absent, notice candidat absente, entre autres).

---

## Le service

- API FastAPI, 6 routeurs (`matching`, `explain`, `feedback`, `assistant`,
  `ecran`, `health`)
- Écran conseiller : écartement d'une recommandation **bloqué côté client
  et côté serveur** tant qu'aucun motif n'est saisi : contrôle humain
  effectif, pas cosmétique
- Journalisation article 12 : trois paliers de conservation (12 / 36 mois
  puis agrégats), purge testée et idempotente
- Assistant RAG réécrit, jamais repris de l'ancien prototype : citation
  garantie par construction

---

## L'industrialisation

- Conteneurs construits : `Dockerfile.train`, `Dockerfile.serve`,
  `Dockerfile.airflow`
- Deux dépôts distincts créés : `edumatch-ia` (solution) et
  `edumatch-cicd`
- CI/CD, Kubernetes, Terraform, monitoring Prometheus/Grafana,
  déploiement Scaleway : en cours de construction à la date de cette
  présentation **[À CONFIRMER APRÈS DÉPLOIEMENT]**
- Hébergement souverain retenu par principe (données de mineurs), pas
  encore vérifié en production **[À CONFIRMER APRÈS DÉPLOIEMENT]**

---

## Limites assumées, et ce que je ferais ensuite

- Le modèle appris ne bat pas encore sa baseline sur la session la plus
  récente : je ne le déploierais pas en l'état face à de vrais candidats
- Le terme débouchés ne couvre que 1,4 % du catalogue : la chaîne de
  nomenclatures NAF↔ROME↔formation ne relie aucune formation Parcoursup
  par identifiant
- Prochaine étape écrite avant la mesure : un modèle réentraîné qui passe
  sous 0,0701 de MAE **et** sous 0,0322 d'ECE sur une session de test non
  consultée, avec l'écart de calibration du groupe féminisé refermé

---

# Questions

