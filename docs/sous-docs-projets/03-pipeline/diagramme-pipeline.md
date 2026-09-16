# Le diagramme du pipeline

**Étape** : E45 · **Blocs servis** : 3, critères 3.11 (diagramme du pipeline),
3.1 (système par lots adapté aux contraintes) et 3.5 (contrôle qualité :
détection, validation, blocage) · **Code** : `pipelines/edumatch_pipeline.py`,
`src/edumatch/orchestration/` · **Amont** :
[C4 niveau 2](../02-architecture/c4-conteneurs.md)

Ce document montre le chemin d'une donnée, de son producteur public jusqu'à
l'écran du conseiller, et l'endroit exact où la chaîne s'arrête si la donnée
n'est pas conforme. Les documents voisins détaillent chaque étape :
[ingestion](ingestion.md), [qualité](qualite.md),
[transformation](transformation.md), [agrégats Sirene](agregats-sirene.md),
[réconciliation NAF ↔ ROME](reconciliation-naf-rome.md).

---

## Vue d'ensemble : bronze, silver, gold, puis le modèle

Les points marqués **STOP** sont bloquants : la tâche échoue, et aucune
tâche placée après elle ne s'exécute.

```mermaid
flowchart TB
    subgraph PROD["Producteurs publics"]
        direction LR
        P1["MESR<br/>Parcoursup"]
        P2["INSEE<br/>Sirene"]
        P3["ONISEP · France Compétences<br/>France Travail"]
    end

    subgraph BRONZE["<b>BRONZE</b> — data/raw · immuable"]
        direction LR
        B1[("Exports Parcoursup<br/>8 millésimes, CSV")]
        B2[("Stock Sirene<br/>Parquet")]
        B3[("Référentiels<br/>CSV, XLSX")]
    end

    Q1{{"<b>STOP — contrôles qualité</b><br/>schéma · complétude · cohérence · fraîcheur<br/>Pandera, par source"}}

    subgraph SILVER["<b>SILVER</b> — data/interim · réconcilié"]
        S1[("8 millésimes harmonisés<br/>fichier DuckDB, via dbt")]
    end

    subgraph GOLD["<b>GOLD</b> — data/processed · prêt à modéliser"]
        direction TB
        G1[("Étoile : 1 table de faits<br/>+ 4 dimensions<br/>Parquet")]
        G2[("Agrégats Sirene<br/>commune x NAF")]
        G3[("Chaîne NAF ↔ ROME ↔ formation<br/>couverture mesurée")]
        G4[("Table de variables<br/>+ label + pondération")]
    end

    Q2{{"<b>STOP — contrat anti-fuite</b><br/>liste blanche des colonnes<br/>de la session prédite ;<br/>tout le reste décalé d'une session"}}

    subgraph MODELE["Modèle"]
        direction TB
        M0["Baseline<br/>taux de la session précédente"]
        M1["Entraînement LightGBM<br/>split temporel strict"]
        M2["Évaluation, calibration,<br/>équité, ablation"]
        M3["Précalcul TreeSHAP<br/>par cellule"]
        M4["Dérive<br/>PSI médian, seuil 0,20"]
    end

    subgraph SERVICE["Service"]
        direction TB
        SC["Score à trois termes<br/>affinité x accessibilité x débouchés"]
        API["Service de matching<br/>+ écran conseiller"]
        JOURNAL[("Journal d'inférence<br/>article 12, purge par paliers")]
    end

    MLFLOW["Registre d'expériences<br/>paramètres, métriques, empreinte du commit"]

    P1 --> B1
    P2 --> B2
    P3 --> B3
    B1 --> Q1
    B2 --> Q1
    B3 --> Q1
    Q1 -->|"conforme"| S1
    Q1 -->|"conforme"| G2
    Q1 -->|"conforme"| G3
    Q1 -.->|"<b>non conforme :<br/>la chaîne s'arrête ici</b>"| ARRET["Échec de tâche<br/>diagnostic écrit, aucune reprise :<br/>un schéma cassé ne se répare pas<br/>en retentant"]
    S1 --> G1
    G1 --> Q2
    Q2 --> G4
    G4 --> M0
    G4 --> M1
    M0 --> M2
    M1 --> M2
    M1 --> M3
    G4 --> M4
    M1 --> MLFLOW
    M2 --> MLFLOW
    M1 --> SC
    G2 --> SC
    G3 --> SC
    M3 --> API
    SC --> API
    API --> JOURNAL

    classDef bronze fill:#8c6239,stroke:#5e4126,color:#fff
    classDef silver fill:#9aa0a6,stroke:#6b7075,color:#fff
    classDef gold fill:#c99700,stroke:#8f6c00,color:#fff
    classDef stop fill:#c0392b,stroke:#8b271c,color:#fff
    classDef calcul fill:#438dd5,stroke:#2e6295,color:#fff
    classDef externe fill:#8a8a8a,stroke:#5c5c5c,color:#fff
    class B1,B2,B3 bronze
    class S1 silver
    class G1,G2,G3,G4 gold
    class Q1,Q2,ARRET stop
    class M0,M1,M2,M3,M4,SC,API,MLFLOW,JOURNAL calcul
    class P1,P2,P3 externe
```

---

## Quatre chaînes, quatre cadences — et pourquoi pas une seule

Le pipeline n'est pas un graphe unique, mais quatre graphes indépendants, un
par cadence réelle de publication.

```mermaid
flowchart LR
    subgraph D1["DAG parcoursup — annuel"]
        direction LR
        A1["ingérer"] --> A2["<b>qualité</b>"] --> A3["silver"] --> A4["gold"] --> A5["variables"] --> A6["dérive"] --> A7["réentraîner"] --> A8["évaluer"]
    end
    subgraph D2["DAG sirene — mensuel"]
        direction LR
        B1["ingérer"] --> B2["<b>qualité</b>"] --> B3["agrégats commune x NAF"]
    end
    subgraph D3["DAG référentiels — quotidien"]
        direction LR
        C1["ingérer"] --> C2["<b>qualité</b>"] --> C3["NAF vers ROME vers formation"]
    end
    subgraph D4["DAG purge du journal — quotidien"]
        direction LR
        E1["purger le journal d'inférence"]
    end

    classDef t fill:#438dd5,stroke:#2e6295,color:#fff
    classDef q fill:#c0392b,stroke:#8b271c,color:#fff
    class A1,A3,A4,A5,A6,A7,A8,B1,B3,C1,C3,E1 t
    class A2,B2,C2 q
```

Un DAG unique cadencé sur la source la plus fréquente aurait retéléchargé
Parcoursup et Sirene tous les jours. L'idempotence de l'ingestion l'aurait
absorbé sans rien casser (un fichier déjà présent et intact n'est pas
retéléchargé), mais la chaîne aurait rejoué les contrôles qualité et occupé
un créneau d'ordonnancement pour rien 29 jours sur 30 côté Sirene, 364 sur
365 côté Parcoursup. Aligner la cadence sur la publication réelle de la
source évite ce gaspillage.

Les cadences ne sont pas écrites dans le code, elles sont dans
`configs/base.yaml`, section `orchestration.planification`.

---

## Les trois propriétés que ce pipeline doit tenir

### Le blocage qualité, et pourquoi il est placé juste après l'ingestion

Les contrôles s'exécutent entre le brut et toute transformation, le seul
endroit où ils servent : plus loin, une donnée non conforme aurait déjà
contaminé les couches suivantes.

Un échec lève une erreur rangée du côté définitif. Deux conséquences
enchaînées : la reprise ne se déclenche pas (retenter un schéma cassé ne le
répare pas), et la règle de déclenchement par défaut d'Airflow, qui exige
que toutes les tâches amont aient réussi, empêche d'elle-même l'exécution de
tout ce qui suit. Le blocage est donc obtenu par un mécanisme natif, sans
code supplémentaire dans le graphe.

Ce point distingue un contrôle qui bloque d'un contrôle qui journalise : le
second laisse une donnée corrompue atteindre le modèle, et le problème se
découvre trois semaines plus tard dans une métrique inexplicable.

→ [ADR 0014](../adr/0014-pandera-plutot-que-great-expectations.md) pour le
choix de l'outil, [`qualite.md`](qualite.md) pour les quatre familles de
contrôle.

### Le contrat anti-fuite, entre gold et les variables

C'est le second point d'arrêt, et le plus discret. Construire une variable à
partir d'une colonne qui n'existe qu'après la décision que l'on prétend
prédire produit un modèle excellent en test et inutile en service : c'est la
fuite de données.

Le mécanisme est une liste blanche. Seules les colonnes explicitement
autorisées peuvent être lues sur la session prédite ; toutes les autres sont
décalées d'une session. Une colonne non déclarée fait échouer la
construction, au lieu d'entrer silencieusement dans la table. Un test dédié
le démontre plutôt que de l'affirmer.

→ [ADR 0010](../adr/0010-fuite-fonctionnelle-tension-et-decalage-temporel.md),
[ADR 0013](../adr/0013-decision-des-variables.md).

### L'idempotence et la reprise

Rejouer une tâche doit produire le même état, pas un doublon. L'ingestion
écrit un fichier temporaire qu'elle renomme à la fin : jamais de fichier
tronqué que la suite croirait complet. Un fichier déjà présent et conforme
à son manifeste n'est pas retéléchargé.

La reprise distingue deux natures d'échec : transitoire (coupure réseau,
quota momentané), que l'on retente avec une temporisation croissante (trois
tentatives, 60 s puis 120 s), et définitive (schéma changé, contrôle
qualité en échec), que l'on fait remonter immédiatement. Confondre les
deux, c'est soit marteler un service déjà saturé, soit masquer une panne
réelle derrière des reprises inutiles.

→ [ADR 0006](../adr/0006-vocabulaire-commun-erreur-transitoire-definitive.md),
[ADR 0004](../adr/0004-primitives-partagees-et-quarantaine-manifeste.md).

---

## Les décisions que ce diagramme matérialise

| Ce que le diagramme montre | Décision correspondante |
|---|---|
| Bronze conservé intact, transformations en aval | [ADR 0001](../adr/0001-elt-plutot-que-etl.md) — ELT |
| Silver en DuckDB, gold en étoile Parquet | [ADR 0015](../adr/0015-modele-en-etoile-grain-et-scd2.md) |
| Agrégats Sirene en un seul bloc, deux moteurs possibles | [ADR 0016](../adr/0016-polars-en-execution-courante-spark-branche-en-mode-cluster.md) |
| Définition et bornage du label | [ADR 0009](../adr/0009-definition-et-bornage-du-label.md) |
| Six sessions exploitables, pas huit | [ADR 0012](../adr/0012-revision-protocole-evaluation-et-conservation-2020.md) |
| Chaîne NAF ↔ ROME ↔ formation, et son manque déclaré | [ADR 0017](../adr/0017-chaine-naf-rome-formation-trois-sources-manque-parcoursup-declare.md) |
| Dérive : PSI médian, seuil de réentraînement | [ADR 0018](../adr/0018-detection-de-derive-seuil-et-agregation.md) |
| Aucune variable de genre en entrée, substituts surveillés | [ADR 0011](../adr/0011-substituts-du-genre-et-dispositif-a-trois-niveaux.md) |

---

## Les limites que ce diagramme ne masque pas

- **Deux millésimes sur huit ne produisent aucun fait.** Le numérateur
  ventilé par type de baccalauréat n'existe pas avant 2020 : le label n'est
  calculable que sur six sessions. C'est une limite de la source, pas du
  modèle, et la chaîne l'écarte par une règle générale plutôt qu'en nommant
  des années dans le code.
- **La chaîne NAF ↔ ROME ↔ formation ne rejoint pas Parcoursup par une
  clé.** Aucun millésime ne porte de code RNCP, NSF ou ROME. Le
  rapprochement se fait par appariement de libellés, et sa couverture est
  mesurée et déclarée plutôt que supposée, voir l'ADR 0017 et
  [`reconciliation-naf-rome.md`](reconciliation-naf-rome.md).
- **Le modèle n'a pas encore battu sa baseline.** Le diagramme montre les
  deux branches, entraînement et plancher, parce que la comparaison est
  rapportée telle qu'elle est mesurée.
- **La surveillance d'exécution reste locale.** La dérive est calculée et
  écrite ; aucune alerte n'est encore routée vers un système
  d'observabilité, prévu mais non construit. C'est dit de la même façon
  dans le [C4 niveau 2](../02-architecture/c4-conteneurs.md).

---
*Étape E45 · vérifié le 2026-09-16 contre `pipelines/edumatch_pipeline.py`
(4 DAG, dont un DAG annuel Parcoursup à huit tâches qui se termine par le
réentraînement et son évaluation), `src/edumatch/orchestration/taches.py`
(13 tâches) et `configs/base.yaml` (cadences et seuils).*
