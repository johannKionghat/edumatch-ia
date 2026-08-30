"""Test du point d'entrée `make baseline` (E21), de bout en bout, sur les échantillons.

Même schéma que `test_features_build_run.py` (E20) : un `data_root` jetable
dans `tmp_path`, silver (E15), gold (E16) puis la table de variables (E20)
produits depuis les huit échantillons versionnés, puis `edumatch.models.baseline`
dessus. Aucune écriture dans `data/processed/` du dépôt.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from edumatch.config import Settings, load_settings
from edumatch.features import build
from edumatch.models import baseline
from edumatch.transform import run, run_etoile


@pytest.fixture()
def settings_avec_variables(tmp_path: Path) -> Settings:
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    dossier_raw = settings.raw_dir / "parcoursup"
    dossier_raw.mkdir(parents=True)
    for millesime in settings.donnees.parcoursup.millesimes:
        source = base.samples_dir / "parcoursup" / f"parcoursup_{millesime}.csv"
        shutil.copy(source, dossier_raw / f"parcoursup_{millesime}.csv")
    run.executer(settings)
    run_etoile.executer(settings)
    build.executer(settings)
    return settings


def test_executer_mesure_les_quatre_variantes_sur_chaque_session(
    settings_avec_variables: Settings,
) -> None:
    rapport = baseline.executer(settings_avec_variables)

    variantes = {score.variante for score in rapport.scores}
    assert variantes == {
        baseline.VARIANTE_PRECEDENTE,
        baseline.VARIANTE_PRECEDENTE_AVEC_REPLI,
        baseline.VARIANTE_MOYENNE_GROUPE,
        baseline.VARIANTE_MOYENNE_GLOBALE,
    }

    perimetres = {score.perimetre for score in rapport.scores}
    assert "validation+test" in perimetres
    for session in (2020, 2021, 2022, 2023, 2024, 2025):
        assert str(session) in perimetres


def test_baseline_avec_repli_couvre_toujours_au_moins_autant_que_sans_repli(
    settings_avec_variables: Settings,
) -> None:
    rapport = baseline.executer(settings_avec_variables)
    for perimetre in ("2024", "2025", "validation+test"):
        sans_repli = rapport.score(baseline.VARIANTE_PRECEDENTE, perimetre)
        avec_repli = rapport.score(baseline.VARIANTE_PRECEDENTE_AVEC_REPLI, perimetre)
        assert avec_repli.couverture >= sans_repli.couverture


def test_premiere_session_de_la_fenetre_labellisee_n_a_aucun_score(
    settings_avec_variables: Settings,
) -> None:
    """Session 2020 : aucune session antérieure n'a de label, aucune variante n'y prédit rien.

    Voir ADR 0012 : le numérateur ventilé par type de baccalauréat n'existe
    qu'à partir de la première session de la fenêtre labellisée.
    """
    rapport = baseline.executer(settings_avec_variables)
    for variante in (
        baseline.VARIANTE_PRECEDENTE,
        baseline.VARIANTE_PRECEDENTE_AVEC_REPLI,
        baseline.VARIANTE_MOYENNE_GROUPE,
        baseline.VARIANTE_MOYENNE_GLOBALE,
    ):
        score = rapport.score(variante, "2020")
        assert score.couverture == 0.0
        assert score.mae_ponderee is None


def test_source_absente_leve_une_erreur_explicite(tmp_path: Path) -> None:
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    with pytest.raises(baseline.ErreurBaseline):
        baseline.executer(settings)
