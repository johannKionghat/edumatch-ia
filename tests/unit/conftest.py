"""Fixtures partagées par les tests de src/edumatch/config.py.

Un YAML minimal, isolé du vrai configs/ : les tests de chargement et de
validation ne doivent pas dépendre du contenu réel de base.yaml, qui peut
évoluer indépendamment de ce qu'ils vérifient.
"""

from __future__ import annotations

from pathlib import Path

import pytest

BASE_YAML = """
projet:
  nom: test-projet
  version: "0.0.1"

donnees:
  parcoursup:
    millesimes: [2020, 2021, 2022]
    effectif_minimal_cellule: 1
  sirene:
    fichiers: [StockEtablissement]
    filtres:
      etat_administratif: A
      caractere_employeur: true
      diffusible: true

modele:
  type: lightgbm
  objectif: regression_proportion
  ponderation: effectif_cellule
  split:
    entrainement: [2020, 2021]
    validation: [2022]
    test: [2023]
  hyperparametres:
    num_leaves: 31
    max_depth: 8
    learning_rate: 0.05
    min_child_samples: 20
    reg_alpha: 0.1
    reg_lambda: 0.1
    n_estimators: 100
    early_stopping_rounds: 10

evaluation:
  metrique_principale: mae_ponderee
  calibration: true
  courbe_apprentissage: [0.5, 1.0]
  baseline: taux_session_precedente

equite:
  dimensions: [type_bac]
  variables_interdites: [genre]
  substituts_a_tester: []
  seuil_impact_disparate: 0.80

derive:
  reference: distribution_entrainement
  tests: [psi]
  seuil_reentrainement: 0.20

api:
  slo_latence_p95_ms: 300
"""

DEV_YAML = """
herite_de: base.yaml

modele:
  hyperparametres:
    n_estimators: 5

execution:
  moteur_volume: local
  niveau_journal: DEBUG
"""


@pytest.fixture()
def configs_dir_isole(tmp_path: Path) -> Path:
    """Un dossier configs/ jetable, avec base.yaml et dev.yaml minimalistes."""
    dossier = tmp_path / "configs"
    dossier.mkdir()
    (dossier / "base.yaml").write_text(BASE_YAML, encoding="utf-8")
    (dossier / "dev.yaml").write_text(DEV_YAML, encoding="utf-8")
    return dossier
