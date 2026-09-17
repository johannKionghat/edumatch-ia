"""Test du point d'entrée `make gold`, de bout en bout, sur les échantillons.

Même schéma que `test_transform_run.py` : un `data_root` jetable dans
`tmp_path`, silver produit par `edumatch.transform.run` depuis les huit
échantillons versionnés, puis `edumatch.transform.run_etoile` dessus.
Aucune écriture dans `data/interim/` ni `data/processed/` du dépôt.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from edumatch.config import Settings, load_settings
from edumatch.transform import run, run_etoile
from edumatch.transform.etoile import CATEGORIES, NOMS_TABLES


@pytest.fixture()
def settings_avec_silver(tmp_path: Path) -> Settings:
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    dossier_raw = settings.raw_dir / "parcoursup"
    dossier_raw.mkdir(parents=True)
    for millesime in settings.donnees.parcoursup.millesimes:
        source = base.samples_dir / "parcoursup" / f"parcoursup_{millesime}.csv"
        shutil.copy(source, dossier_raw / f"parcoursup_{millesime}.csv")
    run.executer(settings)
    return settings


def _volumetrie_attendue(settings: Settings) -> int:
    """Recalcule, indépendamment du module testé, le nombre de cellules exploitables."""
    silver = pq.read_table(
        settings.interim_dir / "parcoursup" / run.NOM_FICHIER_SILVER
    ).to_pandas()
    avec_cle = silver[silver["cod_aff_form"].notna()]
    total = 0
    for categorie in CATEGORIES:
        denom = avec_cle[f"nb_voe_pp_{categorie}"]
        num = avec_cle[f"prop_tot_{categorie}"]
        total += int((denom.notna() & (denom > 0) & num.notna()).sum())
    return total


def test_executer_ecrit_les_cinq_tables(settings_avec_silver: Settings) -> None:
    rapport = run_etoile.executer(settings_avec_silver)

    dossier = settings_avec_silver.processed_dir / "parcoursup"
    for nom in NOMS_TABLES:
        assert (dossier / f"{nom}.parquet").exists()

    fait = pq.read_table(dossier / "fait_admission.parquet").to_pandas()
    assert len(fait) == rapport.lignes_fait_totales
    assert rapport.lignes_fait_totales == _volumetrie_attendue(settings_avec_silver)


def test_integrite_referentielle_entre_fait_et_dimensions(settings_avec_silver: Settings) -> None:
    run_etoile.executer(settings_avec_silver)
    dossier = settings_avec_silver.processed_dir / "parcoursup"
    fait = pq.read_table(dossier / "fait_admission.parquet").to_pandas()
    dim_formation = pq.read_table(dossier / "dim_formation.parquet").to_pandas()
    dim_territoire = pq.read_table(dossier / "dim_territoire.parquet").to_pandas()
    dim_profil = pq.read_table(dossier / "dim_profil_candidat.parquet").to_pandas()
    dim_session = pq.read_table(dossier / "dim_session.parquet").to_pandas()

    assert set(fait["sk_formation"]) <= set(dim_formation["sk_formation"])
    assert set(fait["sk_territoire"]) <= set(dim_territoire["sk_territoire"])
    assert set(fait["sk_profil"]) <= set(dim_profil["sk_profil"])
    assert set(fait["session"]) <= set(dim_session["session"])
    # 2018 et 2019 sont bien dans dim_session, jamais dans fait_admission (ADR 0012).
    assert {2018, 2019} <= set(dim_session["session"])
    assert not ({2018, 2019} & set(fait["session"]))


def test_grain_fait_admission_est_unique(settings_avec_silver: Settings) -> None:
    run_etoile.executer(settings_avec_silver)
    dossier = settings_avec_silver.processed_dir / "parcoursup"
    fait = pq.read_table(dossier / "fait_admission.parquet").to_pandas()
    assert not fait.duplicated(subset=["session", "sk_formation", "sk_profil"]).any()


def test_executer_est_idempotent(settings_avec_silver: Settings) -> None:
    run_etoile.executer(settings_avec_silver)
    dossier = settings_avec_silver.processed_dir / "parcoursup"
    premieres = {nom: pq.read_table(dossier / f"{nom}.parquet").to_pandas() for nom in NOMS_TABLES}

    run_etoile.executer(settings_avec_silver)
    secondes = {nom: pq.read_table(dossier / f"{nom}.parquet").to_pandas() for nom in NOMS_TABLES}

    for nom in NOMS_TABLES:
        pd.testing.assert_frame_equal(premieres[nom], secondes[nom])


def test_silver_absente_leve_une_erreur_explicite(tmp_path: Path) -> None:
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    with pytest.raises(run_etoile.ErreurEtoileSourceAbsente):
        run_etoile.executer(settings)
