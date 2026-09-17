"""Transformation bronze vers silver : réconciliation des huit millésimes Parcoursup.

Bronze (`data/raw/parcoursup/`) est huit fichiers CSV hétérogènes — de 85
colonnes (2018) à 118 (2021-2025), 128 colonnes vues au moins une fois,
83 communes aux huit sessions (ADR 0013). Silver (`data/interim/parcoursup/`)
est une seule table, un schéma stable, un type par colonne, le grain
`(session, cod_aff_form)` documenté et vérifié.

Deux points d'entrée :

- `reconciliation.py` porte la logique pure — chargement, reconstruction de
  la clé, harmonisation du schéma, typage — testable sans aucun outil externe,
  sur `data/samples/` comme sur les fichiers complets.
- `run.py` est le point d'entrée `make transform` : il résout les chemins
  depuis la configuration, appelle `reconciliation.py` et écrit le résultat.

Le lignage (critère 3.8) est produit par un projet dbt (`dbt/`) qui rejoue la
même logique — il importe `reconciliation.py`, il ne la duplique pas — mais
déclare explicitement les huit sources bronze et le modèle silver comme des
nœuds d'un graphe, pour que `dbt docs generate` produise le graphe sans
intervention manuelle. Voir `dbt/README` dans le docstring de
`dbt/models/silver/stg_parcoursup.py` pour l'arbitrage complet (DuckDB plutôt
que PostgreSQL, alternative écartée et seuil de bascule).
"""
