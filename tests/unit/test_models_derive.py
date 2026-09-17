"""Tests unitaires de la détection de dérive : `mesurer_variable`, l'agrégation en
médiane et le déclenchement du réentraînement — fonctions pures ou quasi, sur des séries et
des rapports fabriqués. Le contrat de bout en bout (`make derive` sur les échantillons)
est dans `tests/data/test_models_derive_run.py`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from edumatch.config import DeriveConfig
from edumatch.models.derive import (
    RapportDerive,
    ScoreDerive,
    _tracer_figure_trajectoire,
    _tracer_figure_variables,
    mesurer_variable,
)


def _config(seuil: float = 0.20) -> DeriveConfig:
    return DeriveConfig(
        reference="distribution_entrainement", tests=["psi", "kolmogorov_smirnov"],
        seuil_reentrainement=seuil, n_tranches_psi=10, top_k_categories_psi=30,
    )


def _score(comparaison: str, psi: float, seuil: float = 0.20) -> ScoreDerive:
    return ScoreDerive(
        variable="x", type_variable="numerique", comparaison=comparaison,
        n_reference=10, n_comparaison=10, psi=psi, ks=0.1, au_dela_du_seuil=psi >= seuil,
    )


# ─── mesurer_variable ────────────────────────────────────────────────────────


def test_mesurer_variable_numerique_calcule_le_ks() -> None:
    reference = pd.Series(np.linspace(0.0, 1.0, 100))
    comparaison = pd.Series(np.linspace(0.0, 1.0, 100))

    score = mesurer_variable("x", reference, comparaison, "entrainement -> test", _config())

    assert score.type_variable == "numerique"
    assert score.ks is not None
    assert score.au_dela_du_seuil is False


def test_mesurer_variable_categorielle_ne_calcule_pas_le_ks() -> None:
    reference = pd.Series(["a", "b"] * 10, dtype="string")
    comparaison = pd.Series(["a", "b"] * 10, dtype="string")

    score = mesurer_variable("x", reference, comparaison, "entrainement -> test", _config())

    assert score.type_variable == "categorielle"
    assert score.ks is None


def test_mesurer_variable_detecte_le_depassement_du_seuil() -> None:
    reference = pd.Series(np.linspace(0.0, 1.0, 200))
    comparaison = pd.Series(np.linspace(3.0, 4.0, 200))  # translation totale, hors référence

    score = mesurer_variable("x", reference, comparaison, "entrainement -> test", _config(seuil=0.20))

    assert score.psi >= 0.20
    assert score.au_dela_du_seuil is True


# ─── RapportDerive.mediane_variables_par_comparaison / reentrainement_recommande ────────────


def _rapport(
    variables: list[ScoreDerive], cible: list[ScoreDerive], predictions: list[ScoreDerive], seuil: float = 0.20
) -> RapportDerive:
    return RapportDerive(
        seuil_reentrainement=seuil,
        derive_variables_production=variables,
        derive_variables_consecutive=[],
        derive_cible_production=cible,
        derive_cible_consecutive=[],
        derive_predictions_production=predictions,
        derive_predictions_consecutive=[],
        chemin_figure_variables=Path("x.png"),
        chemin_figure_trajectoire=Path("y.png"),
    )


def test_mediane_variables_ignore_un_seul_outlier() -> None:
    """Une seule variable très dérivée (nomenclature instable, cf. région) ne doit pas faire
    basculer la médiane des 46 — voir la docstring de `models/derive.py`."""
    variables = [_score("entrainement -> test", psi) for psi in [0.01, 0.01, 0.02, 0.01, 4.99]]

    rapport = _rapport(variables, cible=[], predictions=[])

    assert rapport.mediane_variables_par_comparaison["entrainement -> test"] < 0.20
    assert rapport.reentrainement_recommande is False


def test_reentrainement_recommande_si_la_mediane_des_variables_depasse_le_seuil() -> None:
    variables = [_score("entrainement -> test", psi) for psi in [0.25, 0.30, 0.22]]

    rapport = _rapport(variables, cible=[], predictions=[])

    assert rapport.reentrainement_recommande is True


def test_reentrainement_recommande_si_la_cible_derive() -> None:
    cible = [_score("entrainement -> test", 0.30)]

    rapport = _rapport(variables=[_score("entrainement -> test", 0.01)], cible=cible, predictions=[])

    assert rapport.reentrainement_recommande is True


def test_reentrainement_recommande_si_les_predictions_derivent() -> None:
    predictions = [_score("entrainement -> test", 0.30)]

    rapport = _rapport(variables=[_score("entrainement -> test", 0.01)], cible=[], predictions=predictions)

    assert rapport.reentrainement_recommande is True


def test_reentrainement_non_recommande_sous_le_seuil_partout() -> None:
    variables = [_score("entrainement -> test", psi) for psi in [0.01, 0.02, 0.015]]
    cible = [_score("entrainement -> test", 0.01)]
    predictions = [_score("entrainement -> test", 0.02)]

    rapport = _rapport(variables, cible, predictions)

    assert rapport.reentrainement_recommande is False


def test_resume_liste_les_variables_individuellement_au_dela_du_seuil() -> None:
    variables = [
        ScoreDerive("region_etab_aff", "categorielle", "entrainement -> test", 100, 100, 0.75, None, True),
        ScoreDerive("fili", "categorielle", "entrainement -> test", 100, 100, 0.02, None, False),
    ]
    rapport = _rapport(variables, cible=[], predictions=[])

    texte = rapport.resume()

    assert "region_etab_aff" in texte
    assert "fili" not in texte  # sous le seuil : jamais listée individuellement


# ─── Figures ──────────────────────────────────────────────────────────────────


def test_tracer_figure_variables_ecrit_un_fichier(tmp_path: Path) -> None:
    scores = [_score("entrainement -> test", psi) for psi in [0.01, 0.30, 0.15]]

    chemin = _tracer_figure_variables(scores, seuil=0.20, destination=tmp_path / "figures" / "variables.png")

    assert chemin.exists()
    assert chemin.stat().st_size > 0


def test_tracer_figure_trajectoire_ecrit_un_fichier(tmp_path: Path) -> None:
    variables = [_score("2020 -> 2021", 0.01), _score("2021 -> 2022", 0.02)]
    cible = [_score("2020 -> 2021", 0.01), _score("2021 -> 2022", 0.02)]
    predictions = [_score("2020 -> 2021", 0.01), _score("2021 -> 2022", 0.02)]

    chemin = _tracer_figure_trajectoire(
        variables, cible, predictions, seuil=0.20, destination=tmp_path / "figures" / "trajectoire.png"
    )

    assert chemin.exists()
    assert chemin.stat().st_size > 0
