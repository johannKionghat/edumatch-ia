"""Tests unitaires des métriques partagées : `models/metrics.py`."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edumatch.models.metrics import (
    calibration,
    mae_non_ponderee,
    mae_ponderee,
    predictions_baseline_couverture_egale,
)


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


# ─── predictions_baseline_couverture_egale ──────────────────────────────────


def test_predictions_baseline_couverture_egale_comble_par_la_moyenne_de_groupe() -> None:
    table = pd.DataFrame(
        {
            "session": [2024, 2024],
            "effectif": [10, 20],
            "taux": [0.5, 0.2],
            "taux_session_precedente": [0.4, np.nan],
        }
    )
    moyenne_groupe = pd.Series([0.0, 0.3], index=table.index)

    prediction = predictions_baseline_couverture_egale(
        table, "taux_session_precedente", moyenne_groupe, [2024]
    )

    assert prediction.tolist() == pytest.approx([0.4, 0.3])


def test_predictions_baseline_couverture_egale_filtre_par_session() -> None:
    table = pd.DataFrame(
        {
            "session": [2024, 2025],
            "effectif": [10, 10],
            "taux": [0.5, 999.0],
            "taux_session_precedente": [0.5, 0.0],
        }
    )
    moyenne_groupe = pd.Series([0.0, 0.0], index=table.index)

    prediction = predictions_baseline_couverture_egale(
        table, "taux_session_precedente", moyenne_groupe, [2024]
    )

    assert len(prediction) == 1
    assert prediction.iloc[0] == pytest.approx(0.5)


# ─── calibration : diagramme de fiabilité sur cible continue, et ECE ────────


def test_calibration_parfaite_donne_une_ece_nulle() -> None:
    observe = pd.Series([0.05, 0.35, 0.65, 0.95])
    poids = pd.Series([1.0, 1.0, 1.0, 1.0])
    prediction = observe.to_numpy()

    rapport = calibration(observe, poids, prediction, n_tranches=10, perimetre="test")

    assert rapport.ece == pytest.approx(0.0, abs=1e-9)
    assert len(rapport.points) == 4  # une cellule par tranche de 0,1 occupée


def test_calibration_detecte_la_sur_confiance() -> None:
    """Le modèle annonce systématiquement plus haut que ce qui se réalise : écart positif, ECE > 0."""
    observe = pd.Series([0.40, 0.40])
    poids = pd.Series([1.0, 1.0])
    prediction = np.array([0.70, 0.70])

    rapport = calibration(observe, poids, prediction, n_tranches=10, perimetre="test")

    assert rapport.ece == pytest.approx(0.30, abs=1e-9)
    assert rapport.points[0].ecart == pytest.approx(0.30, abs=1e-9)


def test_calibration_pondere_par_leffectif() -> None:
    """Une tranche à fort effectif doit peser plus que sa voisine à faible effectif dans l'ECE."""
    observe = pd.Series([0.0, 0.0])
    poids_grosse_en_tete = pd.Series([100.0, 1.0])
    poids_petite_en_tete = pd.Series([1.0, 100.0])
    prediction = np.array([0.9, 0.1])  # deux tranches distinctes (0,9 et 0,1)

    rapport_grosse = calibration(observe, poids_grosse_en_tete, prediction, n_tranches=10, perimetre="test")
    rapport_petite = calibration(observe, poids_petite_en_tete, prediction, n_tranches=10, perimetre="test")

    assert rapport_grosse.ece > rapport_petite.ece


def test_calibration_ecrete_les_predictions_hors_intervalle() -> None:
    """Un arbre peut sortir de [0, 1] (ADR 0009) : la tranche reste bornée, jamais hors diagramme."""
    observe = pd.Series([1.0])
    poids = pd.Series([1.0])
    prediction = np.array([1.4])  # au-delà de la borne du label

    rapport = calibration(observe, poids, prediction, n_tranches=10, perimetre="test")

    assert len(rapport.points) == 1
    assert rapport.points[0].prediction_moyenne == pytest.approx(1.0)
    assert rapport.points[0].tranche == 9  # dernière tranche, [0.9, 1.0]


def test_calibration_ignore_les_tranches_vides() -> None:
    observe = pd.Series([0.05, 0.95])
    poids = pd.Series([1.0, 1.0])
    prediction = np.array([0.05, 0.95])

    rapport = calibration(observe, poids, prediction, n_tranches=10, perimetre="test")

    assert len(rapport.points) == 2
    assert {point.tranche for point in rapport.points} == {0, 9}
