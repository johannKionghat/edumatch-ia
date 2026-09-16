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

**39 étapes sur 46 sont validées.** L'ingestion, la qualité, l'entrepôt en
étoile, l'agrégat Sirene, la chaîne de nomenclatures, le modèle
(entraînement, calibration, explicabilité, équité, ablation), le service
(score, API, écran de supervision, assistant documentaire), le DAG Airflow et
la détection de dérive sont construits et testés. La gouvernance (registres,
AIPD, Model Card, correspondance AI Act, plan de gouvernance et risques) est
complète. Restent la conteneurisation, l'infrastructure Terraform et
Kubernetes, le monitoring, la panne filmée, les trois vidéos et la relecture
finale — voir [`reste-a-faire.md`](reste-a-faire.md) pour le détail et
[`avancement.md`](avancement.md) pour le journal étape par étape.

| Bloc | Avancement |
|---|---|
| 1 — Gouvernance | registres, AIPD, Model Card, correspondance AI Act et plan de gouvernance produits (`05-gouvernance/`) ; slides à faire |
| 2 — Architecture | modèle en étoile, diagrammes C4 niveaux 1 et 2 livrés (`02-architecture/`) ; conteneurisation, Terraform, Kubernetes, monitoring à construire |
| 3 — Pipeline | connecteurs, contrôles qualité bloquants, dbt bronze→silver→gold, agrégat Sirene, chaîne NAF↔ROME↔formation, DAG Airflow avec reprise et blocage qualité testés, détection de dérive sans Evidently (ADR 0018) ; panne filmée à faire |
| 4 — Déploiement | modèle entraîné, évalué, expliqué (SHAP), audité pour l'équité et l'ablation ; score à trois termes, API, écran de supervision, assistant RAG en service ; réentraînement et évaluation dans le DAG Airflow, derrière une porte de promotion qui refuse aujourd'hui de publier ; une version enregistrée au registre de modèles, sans stade ni alias ; CI/CD et monitoring de production à construire |

**Point à connaître avant toute présentation du bloc 4** : l'analyse d'impact
(`05-gouvernance/aipd.md`) rend un avis scindé, pas favorable sans réserve. Le
test de nécessité, refait sur les mesures d'équité ventilées, montre que le
modèle appris est battu par la règle de dénombrement simple dans 23 des 27
sous-populations auditées. L'avis est **défavorable à la restitution du terme
appris à des candidats réels** en l'état, favorable au reste du dispositif
sous réserves, favorable sans réserve à une démonstration encadrée. Ce n'est
pas une réserve mineure à minimiser : c'est le résultat qui doit être
présenté tel quel devant le jury, avec l'AIPD et la Model Card
(`05-gouvernance/model-card.md`) qui le documentent.

Dernière évaluation du jury : *aucune*. Lancer `/jury`.

## Démarrage

```bash
cp .env.example .env
make install
make up
```

| Service | Adresse |
|---|---|
| API | http://localhost:8000/docs |
| MLflow | http://localhost:5000 |
| Airflow | http://localhost:8080 |

## Navigation

| Dossier | Contenu |
|---|---|
| `01-donnees/` | Sources, label, qualité |
| `02-architecture/` | [`c4-contexte.md`](02-architecture/c4-contexte.md) (niveau 1), [`c4-conteneurs.md`](02-architecture/c4-conteneurs.md) (niveau 2), modèle en étoile, infrastructure |
| `03-pipeline/` | Ingestion, transformation, nomenclatures, [`diagramme-pipeline.md`](03-pipeline/diagramme-pipeline.md), orchestration (DAG Airflow, reprise, blocage qualité) |
| `04-modele/` | Spécification, évaluation, explicabilité, équité, ablation |
| `05-gouvernance/` | Registres, AIPD, [`model-card.md`](05-gouvernance/model-card.md), risques, [`ai-act.md`](05-gouvernance/ai-act.md) |
| `06-service/` | Score à trois termes, API, journalisation et purge, écran conseiller, assistant documentaire |
| `adr/` | Une décision d'architecture par fichier |
| `jury/` | Les évaluations successives du jury |

---
*Mise à jour : 2026-09-15, commit `30ace9e`.*
