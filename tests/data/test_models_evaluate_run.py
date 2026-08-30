"""Test du point d'entrée `make evaluate` (E23), de bout en bout, sur les échantillons.

Même schéma que `test_models_train_run.py` (E22) : un `data_root` jetable
dans `tmp_path`, silver (E15), gold (E16) puis la table de variables (E20)
produits depuis les huit échantillons versionnés, puis
`edumatch.models.evaluate` dessus — qui entraîne à son tour (E22) avant
d'évaluer. La figure de calibration est écrite dans `tmp_path`, jamais dans
`reports/figures/` du dépôt.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from edumatch.config import Settings, load_settings
from edumatch.features import build
from edumatch.models import evaluate
from edumatch.transform import run, run_etoile


@pytest.fixture()
def settings_avec_variables(tmp_path: Path) -> Settings:
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


def test_executer_produit_un_rapport_complet(settings_avec_variables: Settings, tmp_path: Path) -> None:
    dossier_figures = tmp_path / "figures"
    rapport = evaluate.executer(settings_avec_variables, dossier_figures=dossier_figures)

    for score in (
        rapport.scores_validation,
        rapport.scores_test,
        rapport.baseline_validation,
        rapport.baseline_test,
    ):
        assert score.n_cellules >= 0
        assert score.mae_ponderee >= 0.0

    assert rapport.scores_validation.perimetre == "validation"
    assert rapport.scores_test.perimetre == "test"


def test_executer_calcule_une_ece_positive_pour_le_modele_et_la_baseline(
    settings_avec_variables: Settings, tmp_path: Path
) -> None:
    rapport = evaluate.executer(settings_avec_variables, dossier_figures=tmp_path / "figures")

    for calib in (
        rapport.calibration_modele_validation,
        rapport.calibration_modele_test,
        rapport.calibration_baseline_validation,
        rapport.calibration_baseline_test,
    ):
        assert calib.ece >= 0.0


def test_executer_ventile_par_type_de_baccalaureat(settings_avec_variables: Settings, tmp_path: Path) -> None:
    rapport = evaluate.executer(settings_avec_variables, dossier_figures=tmp_path / "figures")

    codes_test = {ventile.type_bac for ventile in rapport.ventilation_test}
    assert codes_test  # au moins un profil présent dans l'échantillon
    assert codes_test <= {"bg", "bt", "bp"}
    for ventile in rapport.ventilation_test:
        assert ventile.modele.n_cellules > 0
        assert ventile.baseline.n_cellules == ventile.modele.n_cellules


def test_executer_ecrit_la_figure_de_calibration_hors_du_depot(
    settings_avec_variables: Settings, tmp_path: Path
) -> None:
    dossier_figures = tmp_path / "figures"
    rapport = evaluate.executer(settings_avec_variables, dossier_figures=dossier_figures)

    assert rapport.chemin_figure.exists()
    assert rapport.chemin_figure.parent == dossier_figures


def test_executer_ne_journalise_pas_dans_mlflow_sans_tracking_uri(
    settings_avec_variables: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING"):
        evaluate.executer(settings_avec_variables, dossier_figures=tmp_path / "figures")
    assert any("MLFLOW_TRACKING_URI" in message for message in caplog.messages)


def test_source_absente_leve_une_erreur_explicite(tmp_path: Path) -> None:
    from edumatch.models.train import ErreurEntrainement

    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    with pytest.raises(ErreurEntrainement):
        evaluate.executer(settings, dossier_figures=tmp_path / "figures")
