"""Tests unitaires des métriques partagées (E22/E23) : `models/metrics.py`."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edumatch.models.metrics import mae_non_ponderee, mae_ponderee


def test_mae_ponderee_vaut_zero_si_prediction_parfaite() -> None:
    observe = pd.Series([0.1, 0.5, 0.9])
    poids = pd.Series([10.0, 1.0, 100.0])
    assert mae_ponderee(observe, observe.to_numpy(), poids) == pytest.approx(0.0)


def test_mae_ponderee_donne_plus_de_poids_a_la_grosse_cellule() -> None:
    """Une cellule à poids 100 doit dominer une cellule à poids 1 dans le score."""
    observe = pd.Series([0.0, 0.0])
    prediction = np.array([1.0, 0.0])  # la première cellule (grosse) est totalement fausse
    poids_grosse_en_tete = pd.Series([100.0, 1.0])
    poids_petite_en_tete = pd.Series([1.0, 100.0])

    score_grosse_fausse = mae_ponderee(observe, prediction, poids_grosse_en_tete)
    score_petite_fausse = mae_ponderee(observe, prediction, poids_petite_en_tete)

    assert score_grosse_fausse > score_petite_fausse


def test_mae_non_ponderee_traite_chaque_cellule_a_egalite() -> None:
    observe = pd.Series([0.0, 0.0])
    prediction = np.array([1.0, 0.0])
    # peu importe le poids que porterait chacune : mae_non_ponderee l'ignore
    assert mae_non_ponderee(observe, prediction) == pytest.approx(0.5)


def test_mae_ponderee_et_non_ponderee_coincident_a_poids_egaux() -> None:
    observe = pd.Series([0.2, 0.6, 1.0])
    prediction = np.array([0.3, 0.5, 0.8])
    poids = pd.Series([5.0, 5.0, 5.0])
    assert mae_ponderee(observe, prediction, poids) == pytest.approx(mae_non_ponderee(observe, prediction))
