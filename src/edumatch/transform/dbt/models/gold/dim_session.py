"""Modèle dbt (Python) `dim_session` (E16) : le lignage bronze -> silver -> gold.

Comme `../silver/stg_parcoursup.py`, ce fichier ne recalcule rien : il
délègue à `edumatch.transform.etoile`, la même fonction qu'utilise
`edumatch.transform.run_etoile` (le chemin de production, sans dbt). Ce
qui change n'est jamais le calcul, seulement le moteur qui a chargé la
table amont (`dbt.ref("stg_parcoursup")` ici, un Parquet lu directement
par `run_etoile.py` en production).

Ce module existe uniquement pour que `dbt docs generate` restitue la
dépendance `stg_parcoursup -> dim_session` dans le graphe de lignage
(critère 3.8), sans qu'un lecteur du graphe n'ait à deviner que gold dépend
de silver qui dépend de bronze.
"""

from edumatch.transform.etoile import base_exploitable, construire_dim_session


def model(dbt, session):
    dbt.config(materialized="table")
    silver = dbt.ref("stg_parcoursup").df()
    base = base_exploitable(silver)
    return construire_dim_session(silver, base)
