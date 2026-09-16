# ADR 0002 — Pas de Databricks : Spark local, sur Sirene uniquement

Statut : accepté (2026-08-28)

## Contexte

Le projet ne comporte qu'un seul traitement distribué : l'agrégation Sirene
(E17). `StockEtablissement`, stock du 01/08/2026, pèse 2,20 Go en Parquet
(4,63 Go pour les 4 fichiers retenus) et porte 54 colonnes dont 9 utiles —
les autres ne sont jamais chargées, par projection colonnaire. Compté par
métadonnée Parquet le 28/08/2026 : 43 896 818 lignes (chiffre corrigé,
l'ordre de grandeur « 36 millions » n'avait jamais été recalculé). Les
filtres du projet (actif, employeur, diffusible) n'en retiennent que
2 436 624 (5,6 %), mais c'est la lecture des 43,9 M de lignes qui dimensionne
le job, pas le résultat filtré : il faut les parcourir pour savoir lesquelles
passent. Lecture mesurée de 2 colonnes sur 54 : 35,4 secondes sur un poste
ordinaire. Le job tourne mensuellement en quelques minutes et sort des
agrégats commune × NAF de quelques dizaines de Mo. Parcoursup (104 274
formation-années, 82 Mo mesurés sur disque) reste en Polars et dbt sur un
seul nœud.

## Décision

PySpark local, appliqué à Sirene et à rien d'autre. Pas de Databricks.

## Alternatives écartées

- Databricks (Spark managé, Delta Lake, Unity Catalog) : tourne sur AWS,
  Azure ou GCP, ce qui contredirait l'hébergement Scaleway retenu pour la
  souveraineté (le système profile des mineurs). Un cluster managé facturé à
  l'unité de calcul est en outre disproportionné pour un job mensuel de
  quelques minutes sur 2,20 Go.
- Tout en Polars/DuckDB, sans Spark : 43,9 millions d'établissements joints
  au catalogue, et le critère 2.4 attend une structure démontrée adaptée au
  volume, pas seulement une promesse.

## Conséquences

Pas d'Unity Catalog : le lignage est produit par `dbt docs` (critère 3.8).
Pas de cluster managé : mémoire et partitionnement Spark restent à ma charge,
un travail réel mené en E17. Pas de Delta Lake : je m'appuie sur du Parquet
immuable en couche bronze et sur PostgreSQL.

Je reviendrais sur ce choix si une jointure intermédiaire dépassait la
mémoire d'un nœud (à mesurer en E17, pas à supposer — la réponse serait alors
de partitionner davantage, pas d'acheter une plateforme), si plusieurs
personnes devaient travailler sur les mêmes données avec droits et lignage
centralisés, ou si le volume passait de quelques Go à plusieurs centaines.
