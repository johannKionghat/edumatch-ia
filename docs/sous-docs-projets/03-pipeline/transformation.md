# Transformation — bronze vers silver, silver vers gold

**Étapes** : E15 (bronze → silver) et E16 (silver → gold) · **Blocs servis** :
3, critères 3.2 (ELT entre sources hétérogènes), 3.6 (idempotence), 3.8
(lignage), 3.9 (réconciliation) ; 2, critère 2.1 (modélisation en étoile
justifiée) · **Code** : `src/edumatch/transform/`

Cette page couvre les deux transformations qui suivent l'ingestion
(`ingestion.md`) et les contrôles qualité (`qualite.md`) : la réconciliation
des huit millésimes Parcoursup en une table silver unique, puis la
construction du modèle en étoile gold à partir de cette table. Le modèle
dimensionnel lui-même — grain, tables, schéma logique et physique — est décrit
dans `02-architecture/modele-etoile.md` et argumenté dans l'ADR 0015 : je n'y
reviens pas ici, j'y renvoie. Cette page traite ce qui relève du pipeline :
l'hétérogénéité amont, l'enchaînement des deux étapes, les tests qui bloquent,
le lignage et la reproductibilité.

## Ce qui existe

| Fichier | Rôle |
|---|---|
| `src/edumatch/transform/reconciliation.py` | Réconciliation bronze → silver : reconstruction de clé, harmonisation de schéma, typage générique |
| `src/edumatch/transform/run.py` | Point d'entrée du chemin de production silver (`make transform`) |
| `src/edumatch/transform/etoile.py` | Construction des cinq tables gold à partir de silver |
| `src/edumatch/transform/run_etoile.py` | Point d'entrée du chemin de production gold (`make gold`) |
| `src/edumatch/transform/run_dbt.py` | Rejeu par dbt de silver et gold, tests, lignage (`make transform-lignage`) |
| `src/edumatch/transform/dbt/` | Projet dbt : sources bronze, modèle silver, modèles gold, tests |

## Bronze vers silver (E15)

### Ce que les huit millésimes avaient d'hétérogène

Les huit fichiers Parcoursup ne partagent ni le même schéma ni la même clé :

- **Le nombre de colonnes dérive dans le temps** : 85 en 2018, 92 en 2019, 115
  en 2020, stable à 118 à partir de 2021 (mesuré et déclaré dans
  `ingestion.md`). Ce n'est pas une anomalie : le MESR a ajouté des champs au
  fil des sessions.
- **La clé de formation `cod_aff_form` n'existe pas en 2018 et 2019.** Elle se
  retrouve dans le paramètre `g_ta_cod` de l'URL portée par `lien_form_psup`
  (ADR 0010), vérifiée exacte partout où les deux coexistent. Couverture
  mesurée par reconstruction : **92,4 % en 2018, 94,6 % en 2019** — le reste
  garde une clé manquante, ce qui n'est pas un défaut du code, c'est un fait
  de la source.

### Comment le schéma a été harmonisé

Les 128 colonnes classées par l'ADR 0013 (`modele.variables`, section
`configs/base.yaml`) forment la référence : chaque colonne apparaît dans le
résultat, qu'elle existe ou non dans le millésime traité. Une colonne absente
d'un millésime donné devient une colonne de valeurs manquantes, jamais une
colonne absente du schéma final — c'est ce qui permet d'empiler les huit
millésimes en un seul bloc malgré leurs 85 à 118 colonnes respectives.

Le typage est générique plutôt qu'une table de correspondance à tenir à jour à
la main : une colonne devient numérique seulement si sa conversion ne perd
aucune valeur sur l'ensemble des huit millésimes (entière si toutes ses
valeurs non nulles sont des entiers, décimale sinon) ; toute autre colonne
reste texte. Les clés et les attributs de catalogue de la liste blanche
(`session_courante`) sont forcés en texte indépendamment de cette règle : ce
sont des codes, jamais des quantités, même quand ils ressemblent à des
nombres pour un millésime donné — le cas déjà rencontré ailleurs dans le
projet (`edumatch.quality.parcoursup`) est `dep`, qui porte `2A` et `2B` pour
la Corse.

### Ce que la réconciliation garantit

- **Le grain `(session, cod_aff_form)` est vérifié unique** à la construction :
  une clé dupliquée au sein d'une même session lève une erreur définitive
  plutôt que de produire une table silver silencieusement fausse.
- **Idempotence et écriture atomique.** `ecrire_silver` réutilise la même
  primitive que les connecteurs d'ingestion (`edumatch.ingestion._flux.ecriture_atomique`) :
  la table est écrite sous un nom temporaire puis renommée une fois complète.
  Une interruption au milieu de l'écriture laisse un fichier temporaire
  orphelin, jamais un `silver.parquet` tronqué que la couche gold prendrait
  pour valide.
- **La couverture de reconstruction de clé est mesurée et journalisée**, pas
  supposée : `RapportReconciliation` porte, par session, le nombre de lignes,
  les colonnes non encore publiées et le taux de clé reconstruite.

### Volumétrie obtenue

| Mesure | Valeur |
|---|---:|
| Lignes silver | 104 274 |
| Colonnes silver | 128 |
| `silver.parquet` | 16 247 456 o |
| `silver.duckdb` (base de travail dbt) | 22 294 528 o |

Le format Parquet est retenu pour silver comme pour bronze Sirene (E06) :
colonnaire, typé, compressé — silver est déjà destiné à être relu par
colonnes (par la construction gold, par la construction des variables), jamais
réécrit ligne à ligne.

### Reproduire

```bash
make transform
```

Exécute `python -m edumatch.transform.run`. Résout les millésimes réellement
présents sur `data/raw/parcoursup/` depuis la configuration
(`donnees.parcoursup.millesimes`), délègue la réconciliation, écrit
`data/interim/parcoursup/silver.parquet`. Un millésime configuré mais pas
encore téléchargé n'est pas une erreur de cette étape — l'ingestion (E05) est
responsable de la présence des fichiers.

## Silver vers gold (E16)

Le modèle dimensionnel produit — le grain de la table de faits, les cinq
tables, leur schéma logique et physique, les chiffres de volumétrie — est
décrit dans `02-architecture/modele-etoile.md`. Ce qui suit couvre
l'ordonnancement, les garanties de pipeline et la reproductibilité, pas le
modèle lui-même.

### Ordonnancement, et ce qui bloque s'il est violé

`run_etoile.py` exige que `data/interim/parcoursup/silver.parquet` existe : à
défaut, il s'arrête avec `ErreurEtoileSourceAbsente` et un message qui indique
d'exécuter `make transform` d'abord, plutôt que d'échouer obscurément plus
loin sur une lecture de fichier absent. La dépendance E15 → E16 est donc
vérifiée à l'exécution, pas seulement déclarée dans le plan d'exécution du
projet.

À l'intérieur de la construction gold elle-même, trois familles de contrôle
bloquent avant l'écriture :

- **Grain violé** : une clé `(session, sk_formation, sk_profil)` dupliquée
  lève `ErreurEtoile`.
- **Dimension orpheline ou fait orphelin** : une cellule sans version de
  formation ou sans territoire résolu lève une erreur, plutôt que de laisser
  une clé de substitution manquante silencieusement.
- **Jointure qui gonfle** : chaque jointure de dimension compare le nombre de
  lignes avant et après ; si une dimension propose deux versions candidates
  pour une même clé naturelle (le signe d'une plage de validité SCD 2 qui se
  recouvre), la jointure est rejetée avant même de vérifier le grain final —
  un simple contrôle « pas de doublon sur le grain » ne l'aurait pas détecté,
  puisque les lignes fabriquées en trop porteraient par construction des clés
  de substitution différentes.

### Les tests dbt qui bloquent

Le projet dbt (`src/edumatch/transform/dbt/`) matérialise silver et les cinq
tables gold dans DuckDB et exécute, en plus des tests de colonne déclarés dans
`models/silver/schema.yml` et `models/gold/schema.yml` (`unique`, `not_null`,
`accepted_values`), deux tests singuliers :

- `tests/assert_grain_unique.sql` — grain `(session, cod_aff_form)` de silver
- `tests/assert_grain_unique_fait_admission.sql` — grain
  `(session, sk_formation, sk_profil)` de `fait_admission`

Les deux sont redondants avec la vérification déjà faite côté Python
(`reconciliation.py` et `etoile.py` lèveraient avant même que le modèle dbt ne
se matérialise) : ils sont gardés malgré cette redondance parce que le critère
3.5/3.8 exige des **tests dbt verts**, pas seulement une garantie invisible
depuis `dbt test`. Dernière exécution vérifiée : **26 nœuds exécutés, 26
succès** (`dbt run` puis `dbt test`).

### Reproductibilité : deux chemins, une seule logique

Deux points d'entrée existent, et c'est un choix délibéré, pas une
duplication :

| Chemin | Commande | Rôle |
|---|---|---|
| Production | `make transform` puis `make gold` | Pandas d'un bout à l'autre, sans dépendance à dbt |
| Lignage | `make transform-lignage` | Rejoue silver **et** gold dans DuckDB via dbt, exécute les tests, génère `dbt docs` |

Les deux chemins appellent **les mêmes fonctions** de `reconciliation.py` et
`etoile.py`. Ce qui change entre eux n'est jamais le calcul, seulement le
moteur qui a chargé la table amont : un `dbt.ref()` côté lignage, une lecture
Parquet directe côté production. Les modèles dbt de `models/gold/` ne
contiennent aucune logique propre — ils existent pour que le graphe de
dépendances soit produit automatiquement par `dbt docs generate`, pas pour
réécrire en SQL une logique déjà écrite et testée en Python.

### Lignage — où le lire

```bash
make transform-lignage
cd src/edumatch/transform/dbt
python -m dbt.cli.main docs serve --project-dir . --profiles-dir .
```

`dbt docs generate` produit le catalogue sur **6 nœuds** : `stg_parcoursup`
(silver) et les cinq tables gold. Le graphe montre la chaîne complète : les
huit sources bronze déclarées dans `models/bronze/_sources.yml` →
`stg_parcoursup` → les trois dimensions issues de silver → `fait_admission`,
seul modèle qui dépend à la fois de silver et de ses trois dimensions. Cet
ordre n'est pas déclaré à la main : il est déduit des `ref()` du projet dbt,
et c'est exactement l'ordre que respecte le chemin de production.
`dim_profil_candidat` apparaît sans amont dans le graphe — c'est un constat
exact, pas un oubli de dépendance : ses six lignes sont portées par la
structure du label (ADR 0009), pas par une colonne source.

### Reproduire

```bash
make transform            # bronze -> silver (E15)
make gold                 # silver -> gold (E16), chemin de production
make transform-lignage    # rejeu dbt : matérialise silver ET gold, teste, génère le lignage
```

`make gold` exécute `python -m edumatch.transform.run_etoile` et journalise
les volumétries obtenues, à confronter aux chiffres de
`02-architecture/modele-etoile.md`. `make transform-lignage` exécute
`python -m edumatch.transform.run_dbt`, qui enchaîne `dbt run`, `dbt test`
puis `dbt docs generate` dans un seul appel, sur un environnement où
`EDUMATCH_RAW_PARCOURSUP_DIR` et `EDUMATCH_DBT_DUCKDB_PATH` sont injectés
depuis `Settings`, jamais codés en dur dans le projet dbt.

La suite de tests complète du dépôt : `python -m pytest -q` → **260 passed**.

## Ce que le pipeline garantit, à ce stade

| Propriété | Comment |
|---|---|
| Reprise correcte après erreur amont | `run_etoile.py` refuse de démarrer si silver est absent, avec un message qui nomme la commande à relancer |
| Idempotence | Écriture atomique aux deux étapes (fichier temporaire renommé) ; relancer `make transform` puis `make gold` sur les mêmes fichiers bronze reproduit les mêmes fichiers silver et gold |
| Blocage sur donnée invalide | Grain, orphelins et jointures qui gonflent lèvent une erreur avant l'écriture, aux deux étapes |
| Lignage sans mention manuelle | Le graphe de dépendances est déduit des `ref()` dbt, pas recopié à la main dans la documentation |
| Reproductibilité par les mêmes fonctions | Le chemin de production et le chemin de lignage appellent le même code Python — aucune divergence possible entre « ce qui tourne en production » et « ce que le lignage documente » |

## Limites assumées

- **Aucune orchestration Airflow à ce stade.** `make transform`, `make gold`
  et `make transform-lignage` s'exécutent manuellement, dans l'ordre. Le DAG
  (E33) reprendra ces mêmes points d'entrée sans changer leur logique.
- **La reprise sur erreur est vérifiée au niveau du code** (erreurs
  définitives qui interrompent la chaîne), pas encore démontrée par une panne
  provoquée sur une orchestration réelle — ce sera l'objet d'E33 et de la
  panne filmée d'E39.
- **`silver.duckdb` et les artefacts de compilation dbt (`target/`) ne sont
  pas versionnés** : ils se régénèrent entièrement depuis `data/raw/`, seule
  couche immuable du projet.
- **Le job d'agrégation Sirene (E17) n'est pas encore raccordé** à cette
  couche gold : les agrégats territoriaux ne sont pas encore une table de
  faits de cette étoile.

---
*Étapes E15 et E16 · dernière mise à jour : 2026-08-30.*
