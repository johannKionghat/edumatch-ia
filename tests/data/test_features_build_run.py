"""Test du point d'entrée `make features` (E20), de bout en bout, sur les échantillons.

Même schéma que `test_transform_run_etoile.py` (E16) : un `data_root` jetable
dans `tmp_path`, silver (E15) puis gold (E16) produits depuis les huit
échantillons versionnés, puis `edumatch.features.build` dessus. Aucune
écriture dans `data/processed/` du dépôt.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from edumatch.config import Settings, load_settings
from edumatch.features import build
from edumatch.transform import run, run_etoile


@pytest.fixture()
def settings_avec_gold(tmp_path: Path) -> Settings:
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    dossier_raw = settings.raw_dir / "parcoursup"
    dossier_raw.mkdir(parents=True)
    for millesime in settings.donnees.parcoursup.millesimes:
        source = base.samples_dir / "parcoursup" / f"parcoursup_{millesime}.csv"
        shutil.copy(source, dossier_raw / f"parcoursup_{millesime}.csv")
    run.executer(settings)
    run_etoile.executer(settings)
    return settings


def test_executer_ecrit_la_table_de_variables(settings_avec_gold: Settings) -> None:
    rapport = build.executer(settings_avec_gold)

    destination = settings_avec_gold.processed_dir / "parcoursup" / build.NOM_FICHIER_VARIABLES
    assert destination.exists()

    table = pq.read_table(destination).to_pandas()
    assert len(table) == rapport.lignes

    fait = pq.read_table(
        settings_avec_gold.processed_dir / "parcoursup" / "fait_admission.parquet"
    ).to_pandas()
    assert len(table) == len(fait)  # une ligne de variables par cellule, jamais plus ni moins


def test_les_46_variables_de_reference_sont_toutes_presentes(settings_avec_gold: Settings) -> None:
    """9 (session_courante) + 35 (décalées) + 2 (dimensions de cellule) = 46, ADR 0013."""
    build.executer(settings_avec_gold)
    variables = settings_avec_gold.modele.variables
    table = pq.read_table(
        settings_avec_gold.processed_dir / "parcoursup" / build.NOM_FICHIER_VARIABLES
    ).to_pandas()

    attendues = set(variables.dimensions_cellule) | set(variables.session_courante) | set(variables.decalees)
    assert attendues <= set(table.columns)
    assert len(attendues) == 46


def test_executer_est_idempotent(settings_avec_gold: Settings) -> None:
    build.executer(settings_avec_gold)
    destination = settings_avec_gold.processed_dir / "parcoursup" / build.NOM_FICHIER_VARIABLES
    premiere = pq.read_table(destination).to_pandas()

    build.executer(settings_avec_gold)
    seconde = pq.read_table(destination).to_pandas()

    pd.testing.assert_frame_equal(premiere, seconde)


def test_source_absente_leve_une_erreur_explicite(tmp_path: Path) -> None:
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    with pytest.raises(build.ErreurVariablesSourceAbsente):
        build.executer(settings)
