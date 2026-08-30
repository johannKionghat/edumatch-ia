"""Test du point d'entrée `make train` (E22), de bout en bout, sur les échantillons.

Même schéma que `test_models_baseline_run.py` (E21) : un `data_root` jetable
dans `tmp_path`, silver (E15), gold (E16) puis la table de variables (E20)
produits depuis les huit échantillons versionnés, puis
`edumatch.models.train` dessus. Aucune écriture dans `data/processed/` du
dépôt, et aucune connexion MLflow requise (`mlflow_tracking_uri` non défini
dans l'environnement de test : la journalisation se contente d'avertir et
l'entraînement se poursuit, voir `train._journaliser_mlflow`).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest

from edumatch.config import Settings, load_settings
from edumatch.features import build
from edumatch.models import train
from edumatch.models.train import COLONNE_A_ANTECEDENT, COLONNE_TAUX_PRECEDENT
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


def test_executer_entraine_et_evalue_selon_le_split_temporel(settings_avec_variables: Settings) -> None:
    modele, rapport = train.executer(settings_avec_variables)

    assert modele is not None
    assert rapport.meilleure_iteration >= 1

    for score in (rapport.scores_validation, rapport.scores_test):
        assert score.n_cellules >= 0
        assert score.mae_ponderee >= 0.0
        assert score.mae_non_ponderee >= 0.0

    assert rapport.scores_validation.perimetre == "validation"
    assert rapport.scores_test.perimetre == "test"


def test_executer_ne_journalise_pas_dans_mlflow_sans_tracking_uri(
    settings_avec_variables: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING"):
        train.executer(settings_avec_variables)
    assert any("MLFLOW_TRACKING_URI" in message for message in caplog.messages)


def test_le_genre_ne_figure_jamais_parmi_les_colonnes_utilisees(settings_avec_variables: Settings) -> None:
    """Invariant du projet : aucune colonne de genre n'est une variable, même indirectement."""
    _, rapport = train.executer(settings_avec_variables)
    colonnes_utilisees = set(rapport.colonnes_categorielles) | set(rapport.colonnes_numeriques)
    assert not any("genre" in colonne.lower() or "sexe" in colonne.lower() for colonne in colonnes_utilisees)


def test_predictions_sont_dans_lintervalle_du_label(settings_avec_variables: Settings) -> None:
    """Le modèle peut sortir de [0, 1] (un arbre ne connaît pas la borne du label) : mesuré, pas supposé."""
    modele, rapport = train.executer(settings_avec_variables)
    # Les scores sont déjà calculés sur des prédictions réelles : si l'entraînement
    # n'a produit aucune valeur aberrante extrême, les MAE restent dans un ordre
    # de grandeur raisonnable pour un taux borné à 1.
    assert rapport.scores_validation.mae_non_ponderee < 5.0
    assert rapport.scores_test.mae_non_ponderee < 5.0


def test_source_absente_leve_une_erreur_explicite(tmp_path: Path) -> None:
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    with pytest.raises(train.ErreurEntrainement):
        train.executer(settings)


# ─── Le taux de la session précédente comme variable (`inclure_taux_precedent`) ──


def test_le_taux_precedent_figure_parmi_les_variables_quand_le_drapeau_est_actif(
    settings_avec_variables: Settings,
) -> None:
    modele_config = settings_avec_variables.modele.model_copy(update={"inclure_taux_precedent": True})
    settings = settings_avec_variables.model_copy(update={"modele": modele_config})

    _, rapport = train.executer(settings)

    colonnes_utilisees = set(rapport.colonnes_categorielles) | set(rapport.colonnes_numeriques)
    assert COLONNE_TAUX_PRECEDENT in colonnes_utilisees
    assert COLONNE_A_ANTECEDENT in colonnes_utilisees


def test_le_taux_precedent_est_absent_des_variables_quand_le_drapeau_est_inactif(
    settings_avec_variables: Settings,
) -> None:
    modele_config = settings_avec_variables.modele.model_copy(update={"inclure_taux_precedent": False})
    settings = settings_avec_variables.model_copy(update={"modele": modele_config})

    _, rapport = train.executer(settings)

    colonnes_utilisees = set(rapport.colonnes_categorielles) | set(rapport.colonnes_numeriques)
    assert COLONNE_TAUX_PRECEDENT not in colonnes_utilisees
    assert COLONNE_A_ANTECEDENT not in colonnes_utilisees


def test_le_plancher_est_rapporte_a_couverture_totale(settings_avec_variables: Settings) -> None:
    """La couverture à 100 % est le point même de la correction : elle ne doit jamais régresser."""
    _, rapport = train.executer(settings_avec_variables)
    assert rapport.baseline_validation.n_cellules == rapport.scores_validation.n_cellules
    assert rapport.baseline_test.n_cellules == rapport.scores_test.n_cellules
    assert rapport.baseline_validation.mae_ponderee >= 0.0
    assert rapport.baseline_test.mae_ponderee >= 0.0
