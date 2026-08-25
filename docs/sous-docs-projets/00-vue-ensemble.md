# EduMatch-IA — vue d'ensemble

> Cette page décrit **l'état réel du dépôt**, pas les intentions.
> Ce qui est prévu mais non construit est dans [`reste-a-faire.md`](reste-a-faire.md).

## Le système

Moteur de matching explicable entre candidats et formations.

```
score = affinité  ×  accessibilité  ×  débouchés
        règles       MODÈLE APPRIS    agrégats Sirene
```

| Terme | Question | Source | Nature |
|---|---|---|---|
| **Affinité** | Cela correspond-il aux centres d'intérêt ? | Requête | Règles, aucun apprentissage |
| **Accessibilité** | Une chance d'être admis ? | Parcoursup ×8 | **LightGBM + SHAP** |
| **Débouchés** | Cela mène-t-il à un emploi atteignable ? | Sirene | Agrégats, aucun apprentissage |

Multiplicatif : si un terme s'annule, la recommandation disparaît.

## État d'avancement

**L'architecture est en place ; aucun code métier n'est encore écrit.** Le dépôt
part d'une base propre, sans reprise de l'ancien MVP.

| Bloc | Avancement |
|---|---|
| 1 — Gouvernance | à démarrer |
| 2 — Architecture | structure et outillage posés, infrastructure à construire |
| 3 — Pipeline | à démarrer |
| 4 — Déploiement | à démarrer |

Le détail de ce qui reste est dans [`reste-a-faire.md`](reste-a-faire.md).
Dernière évaluation du jury : *aucune*. Lancer `/jury`.

## Démarrage

```bash
cp .env.example .env
make install
make up
```

Les commandes `make data`, `make train` et `make api` deviendront disponibles au
fur et à mesure que les modules correspondants seront écrits.

| Service | Adresse |
|---|---|
| API | http://localhost:8000/docs |
| MLflow | http://localhost:5000 |
| Airflow | http://localhost:8080 |

## Navigation

| Dossier | Contenu |
|---|---|
| `01-donnees/` | Sources, label, qualité |
| `02-architecture/` | C4, modèle en étoile, infrastructure |
| `03-pipeline/` | Ingestion, transformation, nomenclatures, orchestration |
| `04-modele/` | Spécification, évaluation, explicabilité, équité, ablation |
| `05-gouvernance/` | Registres, AIPD, Model Card, risques, AI Act |
| `adr/` | Une décision d'architecture par fichier |
| `jury/` | Les évaluations successives du jury |

---
*Mise à jour : à la création du dossier de documentation.*
