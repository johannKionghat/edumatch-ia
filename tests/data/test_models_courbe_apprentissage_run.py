"""Test de contrat de la courbe d'apprentissage (E24), de bout en bout, sur les échantillons.

Même schéma que `test_models_train_run.py` (E22) : un `data_root` jetable
dans `tmp_path`, silver (E15), gold (E16) puis la table de variables (E20)
produits depuis les huit échantillons versionnés, puis
`edumatch.models.courbe_apprentissage` dessus. Aucune écriture dans
`reports/figures/` du dépôt : la figure est écrite dans un dossier jetable.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from edumatch.config import Settings, load_settings
from edumatch.features import build
from edumatch.models import courbe_apprentissage as ca
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


def test_executer_produit_un_point_par_palier_et_une_figure(
    settings_avec_variables: Settings, tmp_path: Path
) -> None:
    dossier_figures = tmp_path / "figures"
    rapport = ca.executer(settings_avec_variables, dossier_figures=dossier_figures)

    assert [point.fraction for point in rapport.points] == list(ca.PALIERS)
    assert rapport.chemin_figure.exists()
    assert rapport.chemin_figure.parent == dossier_figures


def test_le_volume_dentrainement_croit_strictement_avec_le_palier(
    settings_avec_variables: Settings, tmp_path: Path
) -> None:
    """10 % doit contenir strictement moins de cellules que 100 %, sinon l'échantillonnage ne fait rien."""
    rapport = ca.executer(settings_avec_variables, dossier_figures=tmp_path / "figures")
    volumes = [point.n_cellules_entrainement for point in rapport.points]
    assert volumes == sorted(volumes)
    assert volumes[0] < volumes[-1]


def test_le_palier_a_100_pour_cent_reprend_lentrainement_complet(
    settings_avec_variables: Settings, tmp_path: Path
) -> None:
    """Le dernier palier ne doit pas être un tirage aléatoire à 100 %, mais la table complète."""
    table = ca.charger_table(settings_avec_variables)
    table_entrainement = table[table["session"].isin(settings_avec_variables.modele.split.entrainement)]

    rapport = ca.executer(settings_avec_variables, dossier_figures=tmp_path / "figures")
    dernier = rapport.points[-1]

    assert dernier.fraction == 1.0
    assert dernier.n_cellules_entrainement == len(table_entrainement)


def test_mae_ne_sont_jamais_negatives(settings_avec_variables: Settings, tmp_path: Path) -> None:
    rapport = ca.executer(settings_avec_variables, dossier_figures=tmp_path / "figures")
    for point in rapport.points:
        assert point.mae_entrainement >= 0.0
        assert point.mae_validation >= 0.0


def test_ne_journalise_pas_dans_mlflow_sans_tracking_uri(
    settings_avec_variables: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING"):
        ca.executer(settings_avec_variables, dossier_figures=tmp_path / "figures")
    assert any("MLFLOW_TRACKING_URI" in message for message in caplog.messages)


# ─── echantillonner_par_session : le protocole d'échantillonnage lui-même ──


def _table_deux_sessions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "session": [2020] * 100 + [2023] * 20,
            "taux": [0.5] * 120,
            "effectif": [10] * 120,
        }
    )


def test_echantillonner_par_session_respecte_la_proportion_par_session() -> None:
    table = _table_deux_sessions()
    sous_table = ca.echantillonner_par_session(table, fraction=0.5)

    comptes = sous_table["session"].value_counts()
    # 50 % de chaque session prise séparément, pas 50 % du total mélangé.
    assert comptes[2020] == 50
    assert comptes[2023] == 10


def test_echantillonner_par_session_a_100_pour_cent_retourne_la_table_telle_quelle() -> None:
    table = _table_deux_sessions()
    sous_table = ca.echantillonner_par_session(table, fraction=1.0)
    assert sous_table is table


def test_echantillonner_par_session_leve_hors_intervalle() -> None:
    table = _table_deux_sessions()
    with pytest.raises(ca.ErreurCourbeApprentissage):
        ca.echantillonner_par_session(table, fraction=0.0)
    with pytest.raises(ca.ErreurCourbeApprentissage):
        ca.echantillonner_par_session(table, fraction=1.5)


def test_echantillonner_par_session_est_reproductible() -> None:
    """Même graine, même tirage : condition de la comparabilité d'une exécution à l'autre."""
    table = _table_deux_sessions()
    premier = ca.echantillonner_par_session(table, fraction=0.3)
    second = ca.echantillonner_par_session(table, fraction=0.3)
    pd.testing.assert_frame_equal(premier.sort_index(), second.sort_index())
