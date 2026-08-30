"""Modèle dbt (Python) `dim_territoire` (E16) : pour le lignage — voir `dim_session.py`."""

from edumatch.transform.etoile import base_exploitable, construire_dim_territoire


def model(dbt, session):
    dbt.config(materialized="table")
    silver = dbt.ref("stg_parcoursup").df()
    base = base_exploitable(silver)
    return construire_dim_territoire(base)
