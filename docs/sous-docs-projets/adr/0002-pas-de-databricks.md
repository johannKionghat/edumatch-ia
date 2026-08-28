# ADR 0002 — Pas de Databricks : Spark local, sur Sirene uniquement

**Date** : 2026-08-28 · **Statut** : accepté

## Contexte

Le projet ne comporte **qu'un seul traitement distribué** : l'agrégation Sirene (E17).
`StockEtablissement`, stock du 01/08/2026, pèse 2,20 Go en Parquet (4,63 Go pour les 4
fichiers retenus) et porte 54 colonnes dont 9 utiles — les 45 autres ne sont jamais
chargées, par projection colonnaire. Compté par métadonnée Parquet le 28/08/2026 (E06,
`python -c "import pyarrow.parquet as pq; print(pq.ParquetFile('data/raw/sirene/StockEtablissement.parquet').metadata.num_rows)"`) :
**43 896 818 lignes** — chiffre corrigé, l'ordre de grandeur retenu jusqu'ici
(« 36 millions ») n'avait jamais été recalculé depuis sa première mesure. Sur ces
43 896 818 lignes, les filtres du projet (actif, employeur, diffusible) n'en retiennent
que **2 436 624 (5,6 %)** — mais c'est la **lecture** des 43,9 M de lignes, pas le
résultat filtré, qui dimensionne le job : il faut les parcourir pour savoir lesquelles
passent le filtre. Lecture mesurée de 2 colonnes sur 54 : **35,4 secondes** sur un poste
ordinaire (voir `03-pipeline/ingestion.md`). Le job tourne mensuellement en quelques
minutes et sort des agrégats commune × NAF de quelques dizaines de Mo. Parcoursup (104 274
formation-années, **82 Mo mesurés sur disque le 28/08/2026** — `du -sh
data/raw/parcoursup/`, corrigé depuis l'estimation « ~100 Mo » retenue avant
que les 8 fichiers ne soient réellement téléchargés) reste en Polars et dbt sur
un seul nœud.

## Options envisagées

1. **Databricks** — Spark managé, Delta Lake, Unity Catalog, notebooks, ordonnanceur.
2. **Spark local (PySpark), sur Sirene uniquement** — une brique, un job.
3. **Renoncer à Spark, tout en Polars/DuckDB** — écartée : 43,9 millions d'établissements
   joints au catalogue, et le critère 2.4 attend une structure démontrée adaptée au volume.

## Décision

Option 2 : PySpark local, appliqué à Sirene et à rien d'autre.

1. **Souveraineté.** Le système profile des mineurs, ce qui justifie l'hébergement Scaleway
   (E37) ; Databricks tourne sur AWS, Azure ou GCP. Le retenir détruirait cet argument.
2. **Proportionnalité.** Un cluster managé facturé à l'unité de calcul, pour un job
   mensuel de quelques minutes sur 2,20 Go dont on lit 9 colonnes sur 54. Mesuré sur ce
   poste, hors Spark : parcourir et filtrer 2 colonnes des 43,9 M de lignes prend 35,4
   secondes. Le job réel (E17) fait plus — jointure au catalogue de formations,
   agrégation commune × NAF sur les 9 colonnes utiles — mais cette mesure prouve que
   **PySpark en local, sans cluster managé**, aborde un volume que la machine traite déjà
   sans peine sur sa seule partie lecture : la distribution locale reste largement
   dimensionnée pour l'étape suivante, un service facturé à l'unité de calcul ne
   s'imposerait que si le job réel révélait un besoin que ce chiffre ne montre pas.
3. **Cohérence de la pile.** Databricks remplacerait d'un coup Spark local, PostgreSQL,
   une partie d'Airflow, MLflow et le lignage dbt — briques déjà arbitrées, servant
   chacune un critère d'évaluation identifié.

## Conséquences

- **Pas d'Unity Catalog** : le lignage est produit par `dbt docs` (critère 3.8).
- **Pas de cluster managé** : mémoire, partitionnement et réglage de Spark sont à ma charge
  — un travail réel, à mener en E17.
- **Pas de Delta Lake** : ni voyage dans le temps ni transactions ACID sur les tables ;
  on s'appuie sur du Parquet immuable en couche bronze et sur PostgreSQL.

**Ce qui ferait reconsidérer** : une jointure intermédiaire dépassant la mémoire d'un nœud
— **à mesurer en E17, pas à supposer**, et la réponse serait alors de partitionner et de
projeter davantage, pas d'acheter une plateforme ; un collectif travaillant sur les mêmes
données, avec droits et lignage centralisés ; un passage de quelques Go à plusieurs
centaines ; un besoin de flux à grande échelle.
