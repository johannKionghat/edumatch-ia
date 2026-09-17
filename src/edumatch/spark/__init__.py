"""Agrégation Sirene commune x NAF.

Deux implémentations, un seul jeu de règles métier partagé
(`definitions.py`) :

- `sirene_agregats_polars.py` — le moteur réellement emprunté en local
  (`execution.moteur_volume: local`), mesuré plus rapide sur le volume
  actuel.
- `sirene_agregats.py` — le job PySpark exigé par le critère « structures
  adaptées au volume » et retenu pour le cluster de production
  (`execution.moteur_volume: cluster`).

`run_sirene_agregats.py` choisit entre les deux selon la configuration et
constitue le seul point d'entrée (`make sirene-agregats`).
"""

from __future__ import annotations
