"""Tests unitaires de la sélection pré-enregistrée (ADR 0021) : fonctions pures,
sur des valeurs fabriquées. Pas d'entraînement réel ici — voir `tests/data/`
pour un éventuel test de contrat sur `data/samples/`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edumatch.models.fairness import (
    CATEGORIE_GENRE_MAJORITAIRE,
    CATEGORIE_GENRE_MINORITAIRE,
    CATEGORIE_GENRE_MIXTE,
)
from edumatch.models.selection import (
    CALIBRATION_AUCUNE,
    CALIBRATION_ISOTONIQUE,
    CIBLE_ECART,
    CIBLE_TAUX,
    ErreurSelection,
    ResultatCandidat,
    _assert_aucune_session_test,
    _metriques_calibrees_cv,
    _reconstruire_prediction,
    poids_recence,
    selectionner_candidat,
)

# ─── poids_recence : la décroissance de récence des variantes A/C ──────────


def test_poids_recence_vaut_un_a_la_session_de_reference() -> None:
    sessions = pd.Series([2023])
    poids = poids_recence(sessions, s_ref=2023, demi_vie=2)
    assert poids.iloc[0] == pytest.approx(1.0)


def test_poids_recence_vaut_moitie_a_une_demi_vie_de_distance() -> None:
    sessions = pd.Series([2021])
    poids = poids_recence(sessions, s_ref=2023, demi_vie=2)
    assert poids.iloc[0] == pytest.approx(0.5)


def test_poids_recence_decroit_avec_lanciennete() -> None:
    sessions = pd.Series([2020, 2021, 2022, 2023])
    poids = poids_recence(sessions, s_ref=2023, demi_vie=1)
    assert list(poids) == sorted(poids, reverse=False)  # croissant avec la session, donc décroissant avec l'âge
    assert poids.iloc[-1] > poids.iloc[0]


def test_poids_recence_leve_si_demi_vie_non_positive() -> None:
    with pytest.raises(ErreurSelection):
        poids_recence(pd.Series([2023]), s_ref=2023, demi_vie=0)


# ─── _reconstruire_prediction : ancre + écart, écrêtage compté ─────────────


def test_reconstruire_prediction_cible_taux_ne_change_rien() -> None:
    brute = np.array([0.2, 0.5, 0.9])
    ancre = pd.Series([0.1, 0.1, 0.1])
    prediction, n_ecretages = _reconstruire_prediction(brute, CIBLE_TAUX, ancre)
    np.testing.assert_allclose(prediction, brute)
    assert n_ecretages == 0


def test_reconstruire_prediction_cible_ecart_additionne_lancre() -> None:
    ecarts = np.array([0.1, -0.1, 0.0])
    ancre = pd.Series([0.5, 0.5, 0.5])
    prediction, n_ecretages = _reconstruire_prediction(ecarts, CIBLE_ECART, ancre)
    np.testing.assert_allclose(prediction, [0.6, 0.4, 0.5])
    assert n_ecretages == 0


def test_reconstruire_prediction_ecrete_et_compte_les_depassements() -> None:
    ecarts = np.array([0.6, -0.6])  # 0.9+0.6=1.5 et 0.2-0.6=-0.4 : les deux hors [0,1]
    ancre = pd.Series([0.9, 0.2])
    prediction, n_ecretages = _reconstruire_prediction(ecarts, CIBLE_ECART, ancre)
    np.testing.assert_allclose(prediction, [1.0, 0.0])
    assert n_ecretages == 2


# ─── _assert_aucune_session_test : la garde anti-fuite de la sélection ─────


def test_assert_aucune_session_test_ne_leve_pas_si_absente() -> None:
    _assert_aucune_session_test({2020, 2021, 2022}, {2023})  # ne doit pas lever


def test_assert_aucune_session_test_leve_si_presente() -> None:
    with pytest.raises(ErreurSelection, match="2023"):
        _assert_aucune_session_test({2020, 2021, 2023}, {2023})


# ─── _metriques_calibrees_cv : validation croisée groupée par formation ────


def test_metriques_calibrees_cv_ne_fait_jamais_fuiter_une_formation_entre_plis() -> None:
    """Chaque formation (`cod_aff_form`) n'apparaît que dans un seul pli : en la
    dupliquant dix fois avec un signal parfaitement appris par le pli d'ajustement,
    la métrique hors-pli ne doit pas être artificiellement nulle."""
    n_formations = 10
    lignes_par_formation = 4
    cod_aff_form = np.repeat([f"F{i}" for i in range(n_formations)], lignes_par_formation)
    rng = np.random.default_rng(42)
    prediction = rng.uniform(0.0, 1.0, size=len(cod_aff_form))
    # Cible bruitée, sans relation forte avec la prédiction : un calibrateur
    # qui aurait vu ces lignes en ajustement ferait mieux qu'un calibrateur honnête.
    observe = pd.Series(rng.uniform(0.0, 1.0, size=len(cod_aff_form)))
    poids = pd.Series(np.ones(len(cod_aff_form)))
    bucket = pd.Series([CATEGORIE_GENRE_MIXTE] * len(cod_aff_form))

    mae_p, mae_np, ece_global, ece_groupes = _metriques_calibrees_cv(
        observe, poids, prediction, pd.Series(cod_aff_form), bucket, n_tranches=5, n_plis=5
    )
    # Sur un signal bruité, l'erreur hors-pli reste substantielle : un calibrateur
    # qui aurait mémorisé ses propres données de test tomberait près de zéro.
    assert mae_p > 0.05
    assert ece_global >= 0.0
    assert CATEGORIE_GENRE_MIXTE in ece_groupes


# ─── selectionner_candidat : le critère lexicographique et ses tolérances ──


def _candidat(nom: str, mae: float, ece: float, ece_majoritaire: float) -> ResultatCandidat:
    return ResultatCandidat(
        nom=nom,
        demi_vie_recence=None,
        cible=CIBLE_TAUX,
        calibration=CALIBRATION_AUCUNE,
        mae_ponderee=mae,
        mae_non_ponderee=mae,
        ece_global=ece,
        ece_par_groupe={CATEGORIE_GENRE_MAJORITAIRE: ece_majoritaire},
    )


def test_selectionner_candidat_retient_la_mae_la_plus_basse() -> None:
    candidats = [_candidat("A", 0.070, 0.030, 0.030), _candidat("B", 0.080, 0.020, 0.020)]
    assert selectionner_candidat(candidats).nom == "A"


def test_selectionner_candidat_departage_par_ece_si_mae_a_egalite() -> None:
    """Écart de MAE < TOLERANCE_MAE (0,0005) : les deux candidats sont à égalité,
    le départage se fait sur l'ECE global."""
    candidats = [_candidat("A", 0.0700, 0.030, 0.030), _candidat("B", 0.07003, 0.020, 0.020)]
    assert selectionner_candidat(candidats).nom == "B"


def test_selectionner_candidat_departage_final_par_ece_groupe_majoritaire() -> None:
    """MAE et ECE global tous deux à égalité (moins de leur tolérance respective) :
    le départage final se fait sur l'ECE du groupe le plus féminisé."""
    candidats = [
        _candidat("A", 0.0700, 0.0300, 0.070),
        _candidat("B", 0.07003, 0.03005, 0.032),
    ]
    assert selectionner_candidat(candidats).nom == "B"


def test_selectionner_candidat_leve_sur_liste_vide() -> None:
    with pytest.raises(ErreurSelection):
        selectionner_candidat([])
