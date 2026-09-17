"""Tests unitaires de l'évaluation : fonctions pures, sur des tables fabriquées.

Le test de contrat (`tests/data/test_models_evaluate_run.py`) rejoue le
pipeline complet et entraîne réellement un LightGBM ; ici, seules la
ventilation par type de baccalauréat et la production de la figure de
calibration sont vérifiées, sans dépendre de `data/samples/`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from edumatch.models.evaluate import _tracer_calibration, ventiler_par_type_bac
from edumatch.models.metrics import calibration
from edumatch.models.train import JeuDonnees


def _jeu_deux_profils() -> JeuDonnees:
    """Deux cellules bac général, deux bac professionnel — assez pour ventiler."""
    return JeuDonnees(
        X=pd.DataFrame({"type_bac": ["bg", "bg", "bp", "bp"]}),
        y=pd.Series([0.5, 0.7, 0.1, 0.3]),
        poids=pd.Series([10.0, 10.0, 5.0, 5.0]),
        sessions=pd.Series([2025, 2025, 2025, 2025]),
    )


# ─── ventiler_par_type_bac ──────────────────────────────────────────────────


def test_ventiler_par_type_bac_produit_une_entree_par_profil() -> None:
    jeu = _jeu_deux_profils()
    prediction_modele = np.array([0.5, 0.7, 0.1, 0.3])  # prédiction parfaite
    prediction_baseline = pd.Series([0.0, 0.0, 0.0, 0.0])

    ventilation = ventiler_par_type_bac(jeu, prediction_modele, prediction_baseline, "test")

    codes = {ventile.type_bac for ventile in ventilation}
    assert codes == {"bg", "bp"}


def test_ventiler_par_type_bac_isole_bien_les_sous_ensembles() -> None:
    """Le score `bg` ne doit voir aucune cellule `bp`, et réciproquement."""
    jeu = _jeu_deux_profils()
    prediction_modele = np.array([0.5, 0.7, 0.1, 0.3])
    prediction_baseline = pd.Series([0.5, 0.7, 0.1, 0.3])  # baseline parfaite aussi : MAE nulle partout

    ventilation = ventiler_par_type_bac(jeu, prediction_modele, prediction_baseline, "test")

    for ventile in ventilation:
        assert ventile.modele.n_cellules == 2
        assert ventile.baseline.n_cellules == 2
        assert ventile.modele.mae_ponderee == pytest.approx(0.0)
        assert ventile.baseline.mae_ponderee == pytest.approx(0.0)


def test_ventiler_par_type_bac_associe_le_bon_libelle() -> None:
    jeu = _jeu_deux_profils()
    prediction_modele = np.array([0.5, 0.7, 0.1, 0.3])
    prediction_baseline = pd.Series([0.0, 0.0, 0.0, 0.0])

    ventilation = ventiler_par_type_bac(jeu, prediction_modele, prediction_baseline, "test")

    libelles = {ventile.type_bac: ventile.libelle for ventile in ventilation}
    assert libelles == {"bg": "Général", "bp": "Professionnel"}


# ─── _tracer_calibration ─────────────────────────────────────────────────────


def test_tracer_calibration_ecrit_un_fichier_png(tmp_path: Path) -> None:
    observe = pd.Series([0.1, 0.5, 0.9])
    poids = pd.Series([1.0, 1.0, 1.0])
    calibration_modele = calibration(observe, poids, observe.to_numpy(), n_tranches=10, perimetre="test")
    calibration_baseline = calibration(observe, poids, np.array([0.0, 0.0, 0.0]), n_tranches=10, perimetre="test")
    destination = tmp_path / "figures" / "calibration.png"

    chemin = _tracer_calibration(calibration_modele, calibration_baseline, destination)

    assert chemin == destination
    assert destination.exists()
    assert destination.stat().st_size > 0


def test_tracer_calibration_cree_le_dossier_parent(tmp_path: Path) -> None:
    """`reports/figures/` peut ne pas exister encore : la figure ne doit pas échouer pour ça."""
    observe = pd.Series([0.2])
    poids = pd.Series([1.0])
    rapport = calibration(observe, poids, observe.to_numpy(), n_tranches=10, perimetre="test")
    destination = tmp_path / "un_dossier_absent" / "encore_un_autre" / "figure.png"

    _tracer_calibration(rapport, rapport, destination)

    assert destination.exists()
