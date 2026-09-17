"""Modèle dbt (Python) `dim_formation` : SCD 2 sur `cod_aff_form`, pour le lignage.

Même principe que `dim_session.py` : aucune logique ici, seulement l'appel
à `edumatch.transform.etoile.construire_dim_formation`, la fonction déjà
testée par `tests/data/test_transform_etoile.py`, pour que `dbt docs
generate` déclare la dépendance à `stg_parcoursup` (critère 3.8).
"""

from edumatch.transform.etoile import base_exploitable, construire_dim_formation


def model(dbt, session):
    dbt.config(materialized="table")
    silver = dbt.ref("stg_parcoursup").df()
    base = base_exploitable(silver)
    return construire_dim_formation(base)
