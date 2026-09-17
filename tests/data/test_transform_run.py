"""Test du point d'entrée `make transform`, de bout en bout, sur les échantillons.

Construit un `data_root` jetable dans `tmp_path`, y copie les huit
échantillons versionnés sous le nom que `run.py` attend
(`raw/parcoursup/parcoursup_{millesime}.csv`), et vérifie que `executer()`
écrit bien `interim/parcoursup/silver.parquet`, lisible, complet, et
idempotent. Aucune écriture dans `data/interim/` du dépôt : ce test ne touche
jamais les vrais répertoires de données.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from edumatch.config import Settings, load_settings
from edumatch.transform import run


@pytest.fixture()
def settings_jetables(tmp_path: Path) -> Settings:
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    dossier_raw = settings.raw_dir / "parcoursup"
    dossier_raw.mkdir(parents=True)
    for millesime in settings.donnees.parcoursup.millesimes:
        source = base.samples_dir / "parcoursup" / f"parcoursup_{millesime}.csv"
        shutil.copy(source, dossier_raw / f"parcoursup_{millesime}.csv")
    return settings


def test_executer_ecrit_la_table_silver_lisible(settings_jetables: Settings) -> None:
    rapport = run.executer(settings_jetables)

    destination = settings_jetables.interim_dir / "parcoursup" / run.NOM_FICHIER_SILVER
    assert destination.exists()

    table = pq.read_table(destination).to_pandas()
    assert len(table) == rapport.lignes_totales
    assert rapport.lignes_totales == sum(rapport.lignes_par_session.values())
    assert set(table.columns) - {"session"} == settings_jetables.modele.variables.colonnes_sources - {
        "session"
    }


def test_executer_est_idempotent(settings_jetables: Settings) -> None:
    run.executer(settings_jetables)
    destination = settings_jetables.interim_dir / "parcoursup" / run.NOM_FICHIER_SILVER
    premiere = pq.read_table(destination).to_pandas()

    run.executer(settings_jetables)
    seconde = pq.read_table(destination).to_pandas()

    pd.testing.assert_frame_equal(premiere, seconde)


def test_millesime_configure_mais_absent_du_disque_est_ignore(
    settings_jetables: Settings,
) -> None:
    """`run.py` ne doit jamais échouer parce qu'un millésime n'est pas encore téléchargé."""
    (settings_jetables.raw_dir / "parcoursup" / "parcoursup_2018.csv").unlink()

    rapport = run.executer(settings_jetables)

    assert 2018 not in rapport.lignes_par_session
    assert 2019 in rapport.lignes_par_session
