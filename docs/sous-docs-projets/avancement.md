# Avancement — les 46 étapes

Journal d'exécution. Je le tiens à jour à la fin de chaque étape.

Référence des étapes : le plan d'exécution du projet.

> **Le dépôt fait foi.** Si ce journal déclare une étape faite mais que le code
> ne le confirme pas, c'est ce journal qui est faux.

**État : 1 / 46 étapes validées.**

---

## Phase 0 — Fondations

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E01 | Architecture et dépôt local | ✅ validée | 2026-08-24 | `fb2eba3` |
| E02 | Dépôts distants et protection de `main` | ⬜ | | |

**E01 — ce qui a été vérifié**
`git check-ignore` sur des chemins réels : `data/raw/*.csv`, `*adminsdk*.json` et
`models/*.pkl` sont exclus, `data/samples/*` ne l'est pas. `make` affiche l'aide.
Arborescence complète avec 35 `.gitkeep`.

**E01 — décision prise** : ADR 0001, ELT plutôt qu'ETL.

---

## Phase 1 — Accès aux données

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E03 | Vérification des sources sur data.gouv | ⬜ | | |
| E04 | Configuration centralisée `config.py` | ⬜ | | |
| E05 | Connecteur Parcoursup | ⬜ | | |
| E06 | Connecteur Sirene | ⬜ | | |
| E07 | Connecteur référentiels | ⬜ | | |
| E08 | Échantillons versionnés | ⬜ | | |

## Phase 2 — Analyse exploratoire

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E09 | EDA — label et distributions | ⬜ | | |
| E10 | EDA — écarts et sélectivité | ⬜ | | |
| E11 | EDA — équité et substituts | ⬜ | | |
| E12 | EDA — stabilité inter-millésimes | ⬜ | | |
| E13 | Décision de variables (ADR) | ⬜ | | |

## Phase 3 — Qualité et transformation

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E14 | Contrôles qualité bloquants | ⬜ | | |
| E15 | dbt — bronze vers silver | ⬜ | | |
| E16 | dbt — modèle en étoile | ⬜ | | |
| E17 | Job Spark Sirene | ⬜ | | |
| E18 | Table NAF ↔ ROME ↔ formation | ⬜ | | |
| E19 | Calcul du label | ⬜ | | |
| E20 | Construction des variables | ⬜ | | |

## Phase 4 — Modèle

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E21 | Baseline | ⬜ | | |
| E22 | Entraînement LightGBM | ⬜ | | |
| E23 | Évaluation et calibration | ⬜ | | |
| E24 | Courbe d'apprentissage | ⬜ | | |
| E25 | Explicabilité SHAP | ⬜ | | |
| E26 | Audit d'équité | ⬜ | | |
| E27 | Ablation | ⬜ | | |

## Phase 5 — Service

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E28 | Score à trois termes | ⬜ | | |
| E29 | API | ⬜ | | |
| E30 | Journalisation article 12 | ⬜ | | |
| E31 | Écran conseiller RGAA | ⬜ | | |
| E32 | Assistant RAG réécrit | ⬜ | | |

## Phase 6 — Industrialisation

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E33 | DAG Airflow | ⬜ | | |
| E34 | Détection de dérive | ⬜ | | |
| E35 | Conteneurisation | ⬜ | | |
| E36 | CI/CD | ⬜ | | |
| E37 | Infrastructure Terraform et Kubernetes | ⬜ | | |
| E38 | Monitoring et SLO | ⬜ | | |
| E39 | Panne provoquée et reprise, filmée | ⬜ | | |

## Phase 7 — Gouvernance

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E40 | Registres traitements et sources | ⬜ | | |
| E41 | AIPD | ⬜ | | |
| E42 | Model Card | ⬜ | | |
| E43 | Correspondance AI Act | ⬜ | | |
| E44 | Plan de gouvernance et risques | ⬜ | | |

## Phase 8 — Restitution

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E45 | Diagrammes C4 et les 3 vidéos | ⬜ | | |
| E46 | Cohérence dossier ↔ dépôt, slides, répétition | ⬜ | | |

---

## Évaluations du jury

| Date | Verdict | Blocs | Rapport |
|---|---|---|---|
| — | *aucune évaluation à ce jour* | | |

---

## Légende

| Symbole | Sens |
|---|---|
| ✅ | Validée : livrable existant, critère vérifié, argumentaire rendu |
| 🟡 | En cours |
| ⬜ | Non commencée |
| ⛔ | Bloquée — dépendance non validée, ou blocage `dpo` / `security-reviewer` |
