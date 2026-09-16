# L'orchestration en production

**Étape** : E33 (graphe), amendement ADR 0019 (instance dédiée) · **Blocs
servis** : 3, critères 3.1 (système par lots adapté), 3.3 (automatisation sans
intervention manuelle), 3.4 (reprise sur erreur), 3.6 (idempotence), 3.12
(vidéo du pipeline, panne et reprise) · **Code** :
`pipelines/edumatch_pipeline.py`, `src/edumatch/orchestration/`,
`docker-compose.prod.yml`, `scripts/demo_panne_qualite.sh`,
`scripts/verifier_idempotence.py` · **Amont** :
[le diagramme du pipeline](diagramme-pipeline.md),
[ADR 0019](../adr/0019-airflow-en-production-sur-instance-dediee.md)

Ce document répond à une question précise : **où tourne Airflow en
production, et comment le prouver devant la caméra ?** Le graphe lui-même —
quatre DAG, onze tâches — est déjà décrit dans
[`diagramme-pipeline.md`](diagramme-pipeline.md) ; ce qui suit porte
l'infrastructure qui l'exécute réellement et la procédure de démonstration.

---

## Les quatre DAG et leurs cadences

| DAG | Cadence | Tâches, dans l'ordre |
|---|---|---|
| `edumatch_parcoursup` | `@yearly` | `ingerer_parcoursup` → `controler_qualite` → `transformer_silver` → `construire_gold` → `construire_variables` → `detecter_derive` |
| `edumatch_sirene` | `@monthly` | `ingerer_sirene` → `controler_qualite` → `agreger_sirene` |
| `edumatch_referentiels` | `@daily` | `ingerer_referentiels` → `controler_qualite` → `reconcilier_naf_rome` |
| `edumatch_audit_purge` | `@daily` | `purger_audit` |

Chaque cadence suit la fraîcheur réelle de sa source (Parcoursup publie une
campagne par an, Sirene republie son stock chaque mois, l'export RNCP est
quotidien) — pas une préférence, une mesure. Un DAG unique cadencé sur la
source la plus fréquente aurait retéléchargé Parcoursup et Sirene tous les
jours ; l'idempotence de l'ingestion l'aurait absorbé sans rien casser (un
fichier déjà présent et intact n'est pas retéléchargé), mais la chaîne aurait
rejoué les contrôles qualité et consommé un créneau d'ordonnancement pour rien
364 jours sur 365 côté Parcoursup. Les cadences sont dans
`configs/base.yaml`, section `orchestration.planification`, jamais dans le
code Python — les changer ne redéploie pas le graphe, seulement la
configuration qu'il lit.

---

## Où tourne Airflow en production, et pourquoi

**Sur une instance Scaleway DEV1-L dédiée, pas sur le cluster Kapsule qui
héberge l'API.** La décision complète — les chiffres de mémoire qui l'ont
emportée, les options écartées et pourquoi — est dans
[ADR 0019](../adr/0019-airflow-en-production-sur-instance-dediee.md). En
résumé, deux plans d'exécution, chacun à sa place :

- **Le cluster Kapsule** héberge l'API, dont la charge suit la campagne de
  vœux avec un rapport de 1 à 6 — c'est ce qui justifie un cluster élastique
  et le HPA.
- **L'instance dédiée** exécute le pipeline, dont la charge suit la cadence de
  publication des sources (annuelle, mensuelle, quotidienne) et n'a aucun pic
  concurrent à absorber. Un cluster Kubernetes élastique n'y ajouterait que de
  la complexité : la pile Airflow de référence exige déjà 4 Go de mémoire à
  elle seule, et le pool Kapsule n'a pas cette marge une fois l'API et le
  monitoring déjà réservés — voir le détail chiffré dans l'ADR.

Sur cette instance, `docker-compose.prod.yml` lève une pile en trois services
durables :

- **`postgres`** — base de métadonnées Airflow, **dédiée** : distincte de la
  base qui sert de backend au registre MLflow (celle-ci tourne sur le cluster
  Kapsule, une autre machine). `docker/postgres/init-airflow.sql`, exécuté une
  seule fois par l'image officielle au premier démarrage, crée explicitement
  le rôle et la base applicatifs à partir des identifiants fournis par
  l'environnement — jamais un secret en dur dans ce fichier.
- **`airflow-scheduler`** — l'ordonnanceur, en `LocalExecutor` : contrairement
  au mode `standalone` (SQLite, une tâche à la fois) de la pile de
  développement, plusieurs tâches peuvent s'exécuter en parallèle sur une base
  persistante.
- **`airflow-webserver`** — la seule interface de cette pile, et son port
  (`127.0.0.1:8080`) n'est **jamais exposé publiquement** : le groupe de
  sécurité Terraform (`edumatch-cicd/terraform/airflow.tf`) n'ouvre que le
  port 22, et l'interface web ne s'atteint que par un tunnel SSH
  (`ssh -L 8080:127.0.0.1:8080 …`, voir `terraform/outputs.tf`).

L'image `${EDUMATCH_AIRFLOW_IMAGE}` est tirée du registre privé, jamais
construite sur place : c'est le graphe du commit étiqueté qui tourne, pas un
DAG monté depuis un poste de développement. `docker/Dockerfile.airflow`
l'explique en détail, y compris l'incident réel qui a fait écarter PySpark de
cette image (conflit de version SQLAlchemy avec le cœur d'Airflow 2.9.3) — la
tâche `agreger_sirene` y passe donc par Polars, pas par un exécuteur Spark, ce
que confirme `configs/prod.yaml` (`execution.moteur_volume: local`).

Ni MLflow, ni l'entraînement, ni l'API ne tournent sur cette instance : elle
n'exécute que l'orchestrateur du pipeline de données. C'est délibéré, pas un
oubli — voir « Ce que je ne revendique pas » dans l'ADR 0019.

---

## La reprise : transitoire contre définitive

La reprise n'est **pas** confiée au mécanisme natif de retry d'Airflow.
`ARGUMENTS_PAR_DEFAUT["retries"] = 0` dans
`pipelines/edumatch_pipeline.py` le pose explicitement : le retry natif
d'Airflow retenterait aveuglément n'importe quelle exception, y compris un
schéma cassé ou un contrôle qualité bloquant — exactement ce qu'il ne faut
jamais retenter. La décision est prise dans le code Python, par
`edumatch.orchestration.reprise.executer_avec_reprise`, à partir d'un
vocabulaire commun à tous les connecteurs (`ErreurTransitoire` /
`ErreurDefinitive`, `edumatch.ingestion._flux`) :

| Nature | Exemple | Comportement |
|---|---|---|
| **Transitoire** | Coupure réseau, délai dépassé, HTTP 5xx | Retentée jusqu'à `tentatives_max` fois (3), avec une temporisation croissante : 60 s puis 120 s (`delai_reprise_secondes`, `facteur_backoff`, `configs/base.yaml`) |
| **Définitive** | Schéma Parcoursup cassé, `ErreurQualiteBloquante`, millésime non configuré | Aucune reprise : la tâche échoue au premier essai, un humain doit intervenir |

`ErreurQualiteBloquante` (`quality/_diagnostic.py`) hérite explicitement
d'`ErreurDefinitive` — c'est cette classification, pas un test supplémentaire
dans le graphe, qui fait qu'un contrôle qualité en échec n'est jamais
retenté : retenter un schéma cassé ne le répare pas.

### Où regarder la reprise, puisqu'elle ne se voit pas dans l'interface

Avec `retries=0`, une tâche Airflow **ne passe jamais** par l'état
`up_for_retry` de l'interface, même quand le code retente en interne trois
fois de suite : du point de vue d'Airflow, la tâche a réussi — ou a échoué une
seule fois — sans qu'aucun état intermédiaire ne s'affiche.

**C'est le journal de la tâche qu'il faut ouvrir** (l'onglet « Log » d'une
instance de tâche dans l'interface, ou `docker compose -f
docker-compose.prod.yml logs -f airflow-scheduler` en ligne de commande) : les
trois tentatives et la temporisation y apparaissent, écrites par
`executer_avec_reprise` :

```
WARNING ... : échec transitoire (tentative 1/3) — <cause>. Nouvelle tentative dans 60 s.
WARNING ... : échec transitoire (tentative 2/3) — <cause>. Nouvelle tentative dans 120 s.
```

Sans ouvrir ce journal, une reprise réussie et une exécution sans incident
sont indiscernables à l'écran. C'est le geste précis à filmer.

---

## Le blocage qualité

Les contrôles qualité (`controler_qualite`, exécutée entre l'ingestion et
toute transformation, dans les trois DAG qui en ont un) s'appuient sur la
règle de déclenchement par défaut d'un opérateur Airflow (`trigger_rule:
all_success`) : une tâche en échec définitif empêche mécaniquement
l'exécution de tout ce qui suit dans le DAG, sans code supplémentaire écrit
pour cela. Le détail des quatre familles de contrôle (schéma, complétude,
cohérence, fraîcheur) et de la frontière entre bloquer et avertir est dans
[`qualite.md`](qualite.md).

---

## Démonstration de la panne et de la reprise

Deux scénarios distincts, correspondant aux deux natures d'échec ci-dessus.

### 1. Panne transitoire — coupure réseau pendant l'ingestion Sirene

Décrite en détail dans l'ADR 0019, section « Comment la panne sera montrée » :
couper le trafic sortant des conteneurs pendant le téléchargement
(`iptables -I DOCKER-USER -p tcp --dport 443 -j REJECT --reject-with
tcp-reset`, chaîne `DOCKER-USER` pour ne pas couper la session SSH de
tournage), rétablir avant la fin de la temporisation de 60 s, observer dans le
journal de la tâche `ingerer_sirene` la tentative 1 en échec puis la
tentative 2 en succès.

### 2. Arrêt définitif — contrôle qualité bloquant sur Parcoursup

C'est le scénario porté par `scripts/demo_panne_qualite.sh`, qui rejoue en
production ce que
`tests/integration/test_pipeline_enchainement.py::test_panne_qualite_arrete_la_chaine_avant_la_transformation`
démontre déjà sur des échantillons.

```bash
# Sur l'instance, dans edumatch-ia, une fois la pile de production levée
# (make up-prod) et le DAG edumatch_parcoursup ingéré au moins une fois :

# 1. Injecter la panne : sauvegarde le millésime Parcoursup le plus récent,
#    vérifie son empreinte contre le manifeste, puis retire la colonne 'fili'
#    (liste blanche session_courante, protection anti-fuite, configs/base.yaml).
make demo-panne-qualite

# 2. Déclencher le DAG et FILMER l'échec :
#    - controler_qualite échoue, ErreurQualiteBloquante dans son journal,
#      aucune reprise (retries=0, erreur définitive) ;
#    - transformer_silver, construire_gold, construire_variables et
#      detecter_derive passent en upstream_failed ;
#    - interim/parcoursup/silver.parquet ne bouge pas (date de modification
#      inchangée) — la panne est arrêtée AVANT toute transformation.
docker compose -f docker-compose.prod.yml exec airflow-scheduler \
  airflow dags trigger edumatch_parcoursup

# 3. Restaurer, ANNONCER à l'écran qu'il s'agit d'une injection volontaire,
#    et FILMER la vérification par empreinte SHA-256 contre le manifeste —
#    pas une simple copie de fichier supposée correcte.
make demo-restaurer-qualite

# 4. Relancer la chaîne (« Clear » sur l'exécution en échec dans l'interface,
#    ou un nouveau 'airflow dags trigger') : elle va cette fois jusqu'au bout.
```

`scripts/demo_panne_qualite.sh` refuse d'aller plus loin si l'état de départ
ne correspond pas déjà au manifeste (pas de point de comparaison fiable), et
refuse d'annoncer une restauration réussie si l'empreinte recalculée ne
coïncide pas avec celle du manifeste — dans les deux cas, il s'arrête
bruyamment (message sur la sortie d'erreur, code de sortie non nul), jamais un
succès supposé.

### 3. Idempotence — rejouer sans rien changer

```bash
# Avant de rejouer le pipeline :
make verifier-idempotence-capturer

# ... déclencher à nouveau le ou les DAG concernés, sans modifier data/raw ...

# Après la seconde exécution :
make verifier-idempotence-comparer
```

`scripts/verifier_idempotence.py` compare le **contenu** de quatre sorties
(`silver.parquet`, `fait_admission.parquet`, `variables.parquet`, l'agrégat
Sirene) avec `pandas.testing.assert_frame_equal`, pas leur empreinte binaire :
un fichier Parquet réécrit par le même code, sur les mêmes données, n'est pas
garanti identique octet pour octet (métadonnées internes d'écriture,
compression), et ce n'est pas ce qu'« idempotent » signifie ici. Ce qui compte
est démontré par ailleurs, sur des échantillons, dans
`tests/integration/test_pipeline_enchainement.py::test_enchainement_silver_gold_variables_est_idempotent` ;
ce script applique la même vérification aux sorties réelles produites en
production.

---

## Ce que cette page ne couvre pas

- **La construction de l'instance elle-même** (Terraform, cloud-init, coût,
  séquence provisionner/détruire) est dans `edumatch-cicd/terraform/airflow.tf`
  et son `README.md` — ce document les référence, il ne les duplique pas.
- **Le monitoring de cette instance** n'est pas traité ici : elle n'est pas
  collectée par le Prometheus du cluster Kapsule. C'est un point ouvert,
  déclaré tel quel dans l'ADR 0019.
- **Le détail des quatre familles de contrôle qualité** est dans
  [`qualite.md`](qualite.md) ; **le contrat anti-fuite** entre gold et les
  variables est décrit dans [`diagramme-pipeline.md`](diagramme-pipeline.md).

---
*Étape E33 / amendement ADR 0019 · vérifié le 2026-09-16 contre
`pipelines/edumatch_pipeline.py`, `src/edumatch/orchestration/reprise.py`,
`docker-compose.prod.yml`, `docker/postgres/init-airflow.sql`,
`scripts/demo_panne_qualite.sh` et `scripts/verifier_idempotence.py`.*
