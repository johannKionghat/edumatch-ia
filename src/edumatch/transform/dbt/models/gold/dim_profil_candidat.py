"""Modèle dbt (Python) `dim_profil_candidat` (E16).

Seule dimension sans dépendance à `stg_parcoursup` dans le graphe de
lignage : ses six lignes (type de baccalauréat x boursier) ne viennent
d'aucune colonne source, elles sont portées par la structure du label
(ADR 0009) — voir le docstring de `edumatch.transform.etoile`. Un nœud
racine sans amont dans `dbt docs generate` est donc le reflet exact de la
réalité, pas un oubli de dépendance.
"""

from edumatch.transform.etoile import construire_dim_profil_candidat


def model(dbt, session):
    dbt.config(materialized="table")
    return construire_dim_profil_candidat()
