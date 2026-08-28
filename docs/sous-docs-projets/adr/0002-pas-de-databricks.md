# ADR 0002 — Pas de Databricks : Spark local, sur Sirene uniquement

**Date** : 2026-08-28 · **Statut** : accepté

## Contexte

Le projet ne comporte **qu'un seul traitement distribué** : l'agrégation Sirene (E17).
`StockEtablissement`, stock du 01/08/2026, pèse 2,20 Go en Parquet (4,63 Go pour les 4
fichiers retenus) et porte 54 colonnes dont 9 utiles — les 45 autres ne sont jamais
chargées, par projection colonnaire. Le job tourne mensuellement en quelques minutes et
sort des agrégats commune × NAF de quelques dizaines de Mo. Parcoursup (104 274
formation-années, ~100 Mo) reste en Polars et dbt sur un seul nœud.

## Options envisagées

1. **Databricks** — Spark managé, Delta Lake, Unity Catalog, notebooks, ordonnanceur.
2. **Spark local (PySpark), sur Sirene uniquement** — une brique, un job.
3. **Renoncer à Spark, tout en Polars/DuckDB** — écartée : 36 millions d'établissements
   joints au catalogue, et le critère 2.4 attend une structure démontrée adaptée au volume.

## Décision

Option 2 : PySpark local, appliqué à Sirene et à rien d'autre.

1. **Souveraineté.** Le système profile des mineurs, ce qui justifie l'hébergement Scaleway
   (E37) ; Databricks tourne sur AWS, Azure ou GCP. Le retenir détruirait cet argument.
2. **Proportionnalité.** Un cluster managé facturé à l'unité de calcul, pour un job
   mensuel de quelques minutes sur 2,20 Go dont on lit 9 colonnes sur 54.
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
