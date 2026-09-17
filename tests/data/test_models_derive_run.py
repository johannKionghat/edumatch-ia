"""Test du point d'entrée `make derive`, de bout en bout, sur les échantillons.

Même schéma que `test_models_evaluate_run.py` : un `data_root` jetable dans
`tmp_path`, silver, gold puis la table de variables produits depuis les
huit échantillons versionnés, puis `edumatch.models.derive` dessus — qui entraîne le
modèle avant de mesurer la dérive. Les figures sont écrites dans `tmp_path`, jamais
dans `reports/figures/` du dépôt (module partagé par tous les tests de ce fichier :
`scope="module"`, coûteux à répéter — un seul entraînement pour toutes les assertions).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from edumatch.config import Settings, load_settings
from edumatch.features import build
from edumatch.models import derive
from edumatch.transform import run, run_etoile

COMPARAISONS_PRODUCTION_ATTENDUES = {"entrainement -> validation-2024", "entrainement -> test-2025"}


@pytest.fixture(scope="module")
def settings_avec_variables(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    tmp_path = tmp_path_factory.mktemp("derive-e34")
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path, "mlflow_tracking_uri": None})
    dossier_raw = settings.raw_dir / "parcoursup"
    dossier_raw.mkdir(parents=True)
    for millesime in settings.donnees.parcoursup.millesimes:
        source = base.samples_dir / "parcoursup" / f"parcoursup_{millesime}.csv"
        shutil.copy(source, dossier_raw / f"parcoursup_{millesime}.csv")
    run.executer(settings)
    run_etoile.executer(settings)
    build.executer(settings)
    return settings


@pytest.fixture(scope="module")
def rapport(settings_avec_variables: Settings, tmp_path_factory: pytest.TempPathFactory) -> derive.RapportDerive:
    dossier_figures = tmp_path_factory.mktemp("derive-figures")
    return derive.executer(settings_avec_variables, dossier_figures=dossier_figures)


def test_executer_couvre_les_deux_comparaisons_de_production(rapport: derive.RapportDerive) -> None:
    comparaisons = {score.comparaison for score in rapport.derive_variables_production}
    assert comparaisons == COMPARAISONS_PRODUCTION_ATTENDUES


def test_executer_mesure_les_46_variables_licites(
    rapport: derive.RapportDerive, settings_avec_variables: Settings
) -> None:
    variables = settings_avec_variables.modele.variables
    attendu = len(variables.dimensions_cellule) + len(variables.session_courante) + len(variables.decalees)
    assert attendu == 46

    variables_mesurees = {
        score.variable for score in rapport.derive_variables_production if score.comparaison == "entrainement -> test-2025"
    }
    assert len(variables_mesurees) == 46


def test_executer_mesure_la_derive_de_la_cible_et_des_predictions(rapport: derive.RapportDerive) -> None:
    assert {score.comparaison for score in rapport.derive_cible_production} == COMPARAISONS_PRODUCTION_ATTENDUES
    assert {score.comparaison for score in rapport.derive_predictions_production} == COMPARAISONS_PRODUCTION_ATTENDUES
    for score in rapport.derive_cible_production + rapport.derive_predictions_production:
        assert score.type_variable == "numerique"
        assert score.psi >= 0.0


def test_executer_produit_des_comparaisons_consecutives(rapport: derive.RapportDerive) -> None:
    """Les échantillons couvrent huit millésimes bruts (2018-2025) ; la table de variables
    n'en retient que six (2020-2025, label ADR 0012) : cinq paires consécutives."""
    comparaisons = {score.comparaison for score in rapport.derive_variables_consecutive}
    assert len(comparaisons) == 5


def test_executer_ecrit_les_deux_figures_hors_du_depot(rapport: derive.RapportDerive) -> None:
    assert rapport.chemin_figure_variables.exists()
    assert rapport.chemin_figure_trajectoire.exists()
    assert rapport.chemin_figure_variables.stat().st_size > 0
    assert rapport.chemin_figure_trajectoire.stat().st_size > 0


def test_executer_ne_journalise_pas_dans_mlflow_sans_tracking_uri(
    settings_avec_variables: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING"):
        derive.executer(settings_avec_variables, dossier_figures=tmp_path / "figures")
    assert any("MLFLOW_TRACKING_URI" in message for message in caplog.messages)


def test_source_absente_leve_une_erreur_explicite(tmp_path: Path) -> None:
    from edumatch.models.train import ErreurEntrainement

    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    with pytest.raises(ErreurEntrainement):
        derive.executer(settings, dossier_figures=tmp_path / "figures")
