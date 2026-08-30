"""Test de contrat de l'explicabilité (E25), de bout en bout, sur les échantillons.

Même schéma que `test_models_evaluate_run.py` (E23) : un `data_root` jetable
dans `tmp_path`, silver (E15), gold (E16) puis la table de variables (E20)
produits depuis les huit échantillons versionnés, puis
`edumatch.models.explain` dessus — qui entraîne à son tour (E22) avant
d'expliquer. Figure et précalcul sont écrits dans `tmp_path`, jamais dans le
dépôt.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from edumatch.config import Settings, load_settings
from edumatch.features import build
from edumatch.models import explain
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


def _executer(settings: Settings, tmp_path: Path) -> explain.RapportExplicabilite:
    return explain.executer(
        settings,
        dossier_figures=tmp_path / "figures",
        dossier_precalcul=tmp_path / "precalcul",
    )


def test_executer_produit_une_importance_globale_complete(
    settings_avec_variables: Settings, tmp_path: Path
) -> None:
    rapport = _executer(settings_avec_variables, tmp_path)

    resultat_entrainement = explain.train.entrainer_et_evaluer(settings_avec_variables)
    assert len(rapport.importance_globale) == len(resultat_entrainement.colonnes)
    valeurs = [c.importance for c in rapport.importance_globale]
    assert valeurs == sorted(valeurs, reverse=True)
    assert sum(c.part for c in rapport.importance_globale) == pytest.approx(1.0, abs=1e-6)


def test_executer_ecrit_la_figure_hors_du_depot(
    settings_avec_variables: Settings, tmp_path: Path
) -> None:
    rapport = _executer(settings_avec_variables, tmp_path)

    assert rapport.chemin_figure.exists()
    assert rapport.chemin_figure.parent == tmp_path / "figures"


def test_executer_precalcule_une_ligne_par_cellule(
    settings_avec_variables: Settings, tmp_path: Path
) -> None:
    rapport = _executer(settings_avec_variables, tmp_path)

    table_variables = pd.read_parquet(
        settings_avec_variables.processed_dir / "parcoursup" / "variables.parquet"
    )
    assert rapport.n_cellules_precalculees == len(table_variables)
    assert rapport.chemin_precalcul.exists()

    precalcul = pd.read_parquet(rapport.chemin_precalcul)
    assert len(precalcul) == len(table_variables)
    colonnes_shap = [c for c in precalcul.columns if c.startswith("shap__")]
    assert len(colonnes_shap) == len(rapport.importance_globale)
    assert {"session", "cod_aff_form", "type_bac", "boursier", "prediction", "valeur_base"} <= set(
        precalcul.columns
    )


def test_executer_mesure_une_duree_et_une_taille_positives(
    settings_avec_variables: Settings, tmp_path: Path
) -> None:
    rapport = _executer(settings_avec_variables, tmp_path)

    assert rapport.duree_precalcul_secondes >= 0.0
    assert rapport.taille_octets_precalcul > 0
    assert rapport.n_cellules_precalculees > 0
    # Ne doit pas lever, et doit citer le nombre de cellules dans son verdict.
    assert str(rapport.n_cellules_precalculees) in rapport.recommandation_precalcul()


def test_executer_produit_deux_exemples_locaux_distincts(
    settings_avec_variables: Settings, tmp_path: Path
) -> None:
    rapport = _executer(settings_avec_variables, tmp_path)

    assert rapport.exemple_haut.prediction >= rapport.exemple_bas.prediction
    assert len(rapport.exemple_haut.contributions) > 0
    assert len(rapport.exemple_bas.contributions) > 0


def test_executer_mesure_la_part_des_quatre_substituts_du_genre(
    settings_avec_variables: Settings, tmp_path: Path
) -> None:
    rapport = _executer(settings_avec_variables, tmp_path)

    assert set(rapport.part_substituts_genre) == {"fili", "select_form", "dep", "acad_mies"}
    for part in rapport.part_substituts_genre.values():
        assert 0.0 <= part <= 1.0


def test_executer_ne_journalise_pas_dans_mlflow_sans_tracking_uri(
    settings_avec_variables: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING"):
        _executer(settings_avec_variables, tmp_path)
    assert any("MLFLOW_TRACKING_URI" in message for message in caplog.messages)


def test_source_absente_leve_une_erreur_explicite(tmp_path: Path) -> None:
    from edumatch.models.train import ErreurEntrainement

    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    with pytest.raises(ErreurEntrainement):
        explain.executer(
            settings, dossier_figures=tmp_path / "figures", dossier_precalcul=tmp_path / "precalcul"
        )
