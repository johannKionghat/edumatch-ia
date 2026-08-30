"""Test du point d'entrée `make fairness` (E26), de bout en bout, sur les échantillons.

Même schéma que `test_models_evaluate_run.py` (E23) : un `data_root` jetable
dans `tmp_path`, silver (E15), gold (E16) puis la table de variables (E20)
produits depuis les huit échantillons versionnés, puis
`edumatch.models.fairness` dessus — qui entraîne à son tour (E22) avant
d'auditer. Les échantillons versionnés (quelques dizaines de lignes par
millésime) ne comptent jamais 30 cellules dans le moindre groupe : le seuil
de fiabilité de production (`N_CELLULES_MIN_FIABLE`) est donc abaissé à 1
pour ce test, uniquement pour que le calcul du ratio d'impact disparate ait
un groupe sur lequel s'exécuter — la valeur de production n'est jamais
modifiée par ce test, seule cette exécution jetable l'ignore.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from edumatch.config import Settings, load_settings
from edumatch.features import build
from edumatch.models import fairness
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


@pytest.fixture()
def seuil_fiabilite_abaisse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sur l'échantillon, aucun groupe n'atteint 30 cellules : voir le docstring du module."""
    monkeypatch.setattr(fairness, "N_CELLULES_MIN_FIABLE", 1)


def test_executer_produit_un_rapport_complet(
    settings_avec_variables: Settings, seuil_fiabilite_abaisse: None, tmp_path: Path
) -> None:
    dossier_figures = tmp_path / "figures"
    rapport = fairness.executer(settings_avec_variables, dossier_figures=dossier_figures)

    assert set(rapport.ventilations) == {"type_bac", "boursier", "territoire", "genre"}
    for groupes in rapport.ventilations.values():
        assert groupes  # au moins un groupe dans l'échantillon
        for groupe in groupes:
            assert groupe.n_cellules > 0
            assert groupe.mae_ponderee_modele >= 0.0

    assert set(rapport.ratios) == {"type_bac", "boursier", "territoire", "genre"}
    for ratio in rapport.ratios.values():
        assert ratio.ratios_modele  # au moins un groupe fiable, seuil abaissé


def test_executer_ne_range_jamais_une_formation_sans_denominateur_en_minoritaire(
    settings_avec_variables: Settings, seuil_fiabilite_abaisse: None, tmp_path: Path
) -> None:
    """Non-régression du piège déjà rencontré : contrôlé ici sur des données réelles, pas seulement fabriquées."""
    table_audit, _ = fairness.assembler_table_audit(settings_avec_variables)
    formations = table_audit.drop_duplicates("cod_aff_form")
    indeterminees = formations.loc[formations["composition_candidate"].isna()]
    assert (indeterminees["bucket_genre"] == fairness.CATEGORIE_GENRE_INDETERMINEE).all()


def test_executer_calcule_un_ecart_d_admission_genre_borne(
    settings_avec_variables: Settings, seuil_fiabilite_abaisse: None, tmp_path: Path
) -> None:
    rapport = fairness.executer(settings_avec_variables, dossier_figures=tmp_path / "figures")
    assert -1.0 <= rapport.ecart_admission_genre_median <= 1.0
    assert 0.0 <= rapport.part_formations_ecart_genre_sous_5_points <= 1.0


def test_executer_teste_les_substituts_du_genre(
    settings_avec_variables: Settings, seuil_fiabilite_abaisse: None, tmp_path: Path
) -> None:
    rapport = fairness.executer(settings_avec_variables, dossier_figures=tmp_path / "figures")
    assert set(rapport.correlations_substituts) == set(fairness.COLONNES_SUBSTITUTS_TESTEES)
    for valeur in rapport.correlations_substituts.values():
        assert 0.0 <= valeur <= 1.0 or valeur != valeur  # `eta_carre` peut renvoyer NaN si un substitut est constant


def test_executer_ecrit_les_figures_hors_du_depot(
    settings_avec_variables: Settings, seuil_fiabilite_abaisse: None, tmp_path: Path
) -> None:
    dossier_figures = tmp_path / "figures"
    rapport = fairness.executer(settings_avec_variables, dossier_figures=dossier_figures)

    for chemin in (
        rapport.chemin_figure_impact_disparate,
        rapport.chemin_figure_calibration_genre,
        rapport.chemin_figure_substituts,
    ):
        assert chemin.exists()
        assert chemin.parent == dossier_figures


def test_executer_ne_journalise_pas_dans_mlflow_sans_tracking_uri(
    settings_avec_variables: Settings, seuil_fiabilite_abaisse: None, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING"):
        fairness.executer(settings_avec_variables, dossier_figures=tmp_path / "figures")
    assert any("MLFLOW_TRACKING_URI" in message for message in caplog.messages)


def test_source_silver_absente_leve_une_erreur_explicite(tmp_path: Path) -> None:
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    with pytest.raises(Exception):  # ErreurEntrainement (table de variables absente), levée avant même la silver
        fairness.executer(settings, dossier_figures=tmp_path / "figures")
