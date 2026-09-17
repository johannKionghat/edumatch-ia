"""Modèle dbt (Python) `fait_admission` : la table de faits, pour le lignage.

Seul modèle gold qui dépend des trois autres (`dim_formation`,
`dim_territoire`, `dim_profil_candidat`) en plus de `stg_parcoursup` : le
graphe produit par `dbt docs generate` montre donc, sans intervention
manuelle, que la table de faits ne peut être construite qu'après ses trois
dimensions — exactement l'ordre que respecte
`edumatch.transform.etoile.construire_etoile` côté production.
"""

from edumatch.transform.etoile import base_exploitable, construire_fait_admission


def model(dbt, session):
    dbt.config(materialized="table")
    silver = dbt.ref("stg_parcoursup").df()
    base = base_exploitable(silver)
    dim_formation = dbt.ref("dim_formation").df()
    dim_territoire = dbt.ref("dim_territoire").df()
    dim_profil = dbt.ref("dim_profil_candidat").df()
    return construire_fait_admission(base, dim_formation, dim_territoire, dim_profil)
