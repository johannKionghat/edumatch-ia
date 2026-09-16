# ADR 0015 — Modèle en étoile de la couche gold : grain, SCD 2 et moteur

Statut : accepté (2026-08-30) · complète l'ADR 0001 (ELT), s'appuie sur
l'ADR 0009 (label) et l'ADR 0012 (six sessions exploitables)

## Contexte

La couche silver (`stg_parcoursup`) est une table unique de 104 274 lignes
et 128 colonnes, une ligne par formation-session. Elle est réconciliée et
typée, mais pas modélisée pour l'entraînement, l'analyse ou la supervision.
Trois contraintes commandent la couche gold (E16) : le label est un taux par
cellule (formation × session × type de bac × boursier), une ligne silver se
déplie en jusqu'à six cellules ; les attributs d'une formation changent
d'une session à l'autre (capacité, filière, sélectivité) ; et la volumétrie
est petite (440 030 cellules de faits, 43 858 versions de formations) — ce
n'est pas une échelle qui impose un entrepôt distribué.

## Décision

1. **Le grain de la table de faits est la cellule**
   `(session, cod_aff_form, type_bac, boursier)`, portée après résolution
   des dimensions par `(session, sk_formation, sk_profil)` — vérifié unique
   sur les 440 030 lignes.
2. **Une étoile** : une table de faits, quatre dimensions, clés de
   substitution entières.
3. **SCD 2 sur `dim_formation`** : une nouvelle version naît dès qu'un des
   huit attributs suivis change (`fili`, `form_lib_voe_acc`,
   `fil_lib_voe_acc`, `select_form`, `contrat_etab`, `tri`, `capa_fin`,
   `cod_uai`). Résultat mesuré : 43 858 versions pour 16 618 formations,
   2,6 versions en moyenne, 6 au maximum. `dim_territoire` reste en SCD 1 :
   l'affectation département-académie-région ne varie pas dans les données
   observées.
4. **Pas de `dim_etablissement` séparée** : aucune formation ne change
   d'établissement gérant d'une session à l'autre dans les données
   observées, donc `cod_uai` reste un attribut de `dim_formation`, suivi en
   SCD 2 comme les autres et jamais une variable du modèle (ADR 0011,
   ADR 0013).
5. **DuckDB comme moteur, Parquet comme format d'échange** : les tables
   gold sont matérialisées en Parquet dans `data/processed/parcoursup/`,
   rejouées dans une base DuckDB locale par dbt pour le lignage et les
   tests.
6. **2018 et 2019 filtrées par la disponibilité de la donnée, pas par un
   millésime en dur** : la condition d'exploitabilité (dénominateur
   renseigné et positif, numérateur renseigné) exclut d'elle-même les deux
   sessions. Elles restent présentes dans `dim_session`, avec
   `label_disponible` à `False`.

## Alternatives écartées

- Le grain formation-session (celui de silver) : obligerait à porter six
  couples de mesures par ligne, les profils deviendraient des colonnes et
  l'ajout d'un septième serait une migration de schéma.
- La ligne dépliée par genre : ferait entrer le genre dans la table que lit
  l'entraînement, interdit par l'ADR 0011.
- La table plate dénormalisée : redondance des attributs recopiés jusqu'à
  six fois par session, impossibilité d'historiser proprement, et moins
  lisible pour le critère 2.1 qui demande une modélisation justifiée. Elle
  reste disponible en aval, comme produit de la construction des variables.
- Le flocon (sous-dimensions du département) : économise quelques
  kilo-octets et coûte deux jointures de plus, pour une table de 1 448
  lignes — un non-sujet.
- SCD 1 sur `dim_formation` : écraserait l'historique, la capacité 2025
  serait attribuée à la cellule 2020 — une fuite de données rétrospective.
- PostgreSQL comme entrepôt gold : la table de faits pèse 3,85 Mo,
  reconstruite en totalité à chaque exécution, jamais mise à jour ligne à
  ligne, sans accès concurrent — un serveur et une migration pour ça
  seraient hors de proportion.
- Un entrepôt distant managé (BigQuery, Snowflake) : hors sujet à cette
  volumétrie, et contraire à la contrainte de souveraineté déjà arbitrée.
- Un filtre `session >= 2020` explicite : deviendrait faux le jour où le
  ministère republierait ces deux millésimes, ou si une session future
  présentait la même lacune.

## Conséquences

La couche gold compte cinq tables : `fait_admission` (440 030 lignes, 9
colonnes), `dim_formation` (43 858/12), `dim_territoire` (1 448/6),
`dim_profil_candidat` (6/4), `dim_session` (8/2). Le grain est unique et
aucune cellule ne porte un taux hors de [0,1], vérifié à la construction et
rejoué comme test dbt. Le label est calculé une seule fois, dans la table de
faits. `dbt run` puis `dbt test` : 26 nœuds, 26 succès ; la suite du dépôt
compte 260 tests, 260 succès. Coût assumé : le calcul de `dim_formation`
parcourt les versions en Python plutôt qu'en SQL ensembliste — négligeable à
16 618 formations, à réécrire en fonction de fenêtre à un ordre de grandeur
de plus.

Je reviendrais sur le grain si le ministère publiait une ventilation
supplémentaire du numérateur. Je reviendrais sur SCD 2 si aucun des huit
attributs suivis n'entrait ni dans le modèle ni dans l'écran de supervision.
Je reviendrais sur DuckDB/Parquet si la couche gold dépassait quelques
dizaines de gigaoctets, si plusieurs services devaient lire la même table en
concurrence, ou si un besoin de mise à jour transactionnelle apparaissait.

Reproduit par `make gold` et `make transform-lignage`, sur
`data/interim/parcoursup/silver.parquet`. Détail dans
`docs/sous-docs-projets/02-architecture/modele-etoile.md`.
