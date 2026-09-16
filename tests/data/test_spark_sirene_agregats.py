"""Tests de l'agrégat Sirene commune x NAF (E17), moteurs Polars et Spark.

Trois familles de test, toutes sur `data/samples/sirene/StockEtablissement.parquet`
(500 lignes) ou sur des tables fabriquées : jamais sur le fichier complet
(2,2 Go) — voir `data/samples/README.md`.

1. `agreger_polars` seule, sur une table fabriquée : chaque règle métier
   (cessations conservées, paliers d'effectifs, couverture NAF25, ancienneté)
   vérifiée une par une.
2. Bout en bout via `run_sirene_agregats.executer`, sur l'échantillon
   versionné, moteur `local` (Polars) : écriture, idempotence, cohérence des
   totaux avec un recalcul indépendant.
3. Spark : mêmes résultats que Polars sur le même échantillon (preuve que les
   deux moteurs appliquent la même règle), plus la preuve de projection et de
   filtrage à la lecture par `explain()`.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from edumatch.config import Settings, load_settings
from edumatch.spark import run_sirene_agregats
from edumatch.spark.definitions import COLONNES_PROJECTION, FiltresSirene
from edumatch.spark.sirene_agregats_polars import (
    NOM_FICHIER_SORTIE,
    agreger_polars,
    ecrire_agregats,
)

CHEMIN_ECHANTILLON = Path("data/samples/sirene/StockEtablissement.parquet")
FILTRES = FiltresSirene(etat_actif="A", valeur_employeur="O", filtrer_employeur=True)
DATE_REFERENCE = date(2026, 8, 1)


def _table(lignes: list[dict[str, object]]) -> pa.Table:
    colonnes = {nom: [ligne[nom] for ligne in lignes] for nom in COLONNES_PROJECTION}
    return pa.table(colonnes)


def _ligne(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "siret": "12345678901234",
        "activitePrincipaleEtablissement": "68.20B",
        "nomenclatureActivitePrincipaleEtablissement": "NAFRev2",
        "activitePrincipaleNAF25Etablissement": None,
        "codeCommuneEtablissement": "75115",
        "trancheEffectifsEtablissement": "NN",
        "etatAdministratifEtablissement": "A",
        "caractereEmployeurEtablissement": "O",
        "dateCreationEtablissement": date(2020, 1, 1),
    }
    base.update(overrides)
    return base


# ─── Règles métier, table fabriquée ─────────────────────────────────────────


def test_actifs_et_fermes_comptes_separement(tmp_path: Path) -> None:
    """Un actif-employeur et un fermé-employeur du même couple (commune, NAF) : deux compteurs distincts."""
    chemin = tmp_path / "etab.parquet"
    pq.write_table(
        _table(
            [
                _ligne(etatAdministratifEtablissement="A"),
                _ligne(etatAdministratifEtablissement="F"),
            ]
        ),
        chemin,
    )
    agregat = agreger_polars(chemin, DATE_REFERENCE, FILTRES)
    assert agregat.height == 1
    ligne = agregat.row(0, named=True)
    assert ligne["nb_actifs_employeurs"] == 1
    assert ligne["nb_fermes_employeurs"] == 1


def test_non_employeur_exclu(tmp_path: Path) -> None:
    """`caractereEmployeurEtablissement = 'N'` n'entre dans aucun des deux compteurs."""
    chemin = tmp_path / "etab.parquet"
    pq.write_table(_table([_ligne(caractereEmployeurEtablissement="N")]), chemin)
    agregat = agreger_polars(chemin, DATE_REFERENCE, FILTRES)
    assert agregat.height == 0


def test_commune_manquante_exclue(tmp_path: Path) -> None:
    """Une ligne sans commune ne peut pas être placée sur le grain (commune, NAF)."""
    chemin = tmp_path / "etab.parquet"
    pq.write_table(_table([_ligne(codeCommuneEtablissement=None)]), chemin)
    agregat = agreger_polars(chemin, DATE_REFERENCE, FILTRES)
    assert agregat.height == 0


@pytest.mark.parametrize(
    ("code_tranche", "palier_attendu"),
    [
        ("00", "nb_tranche_0"),
        ("03", "nb_tranche_1_9"),
        ("12", "nb_tranche_10_49"),
        ("31", "nb_tranche_50_249"),
        ("53", "nb_tranche_250_plus"),
        ("NN", "nb_tranche_non_renseignee"),
    ],
)
def test_ventilation_par_tranche_effectifs(tmp_path: Path, code_tranche: str, palier_attendu: str) -> None:
    chemin = tmp_path / "etab.parquet"
    pq.write_table(_table([_ligne(trancheEffectifsEtablissement=code_tranche)]), chemin)
    agregat = agreger_polars(chemin, DATE_REFERENCE, FILTRES)
    ligne = agregat.row(0, named=True)
    for colonne in (
        "nb_tranche_0",
        "nb_tranche_1_9",
        "nb_tranche_10_49",
        "nb_tranche_50_249",
        "nb_tranche_250_plus",
        "nb_tranche_non_renseignee",
    ):
        assert ligne[colonne] == (1 if colonne == palier_attendu else 0)


def test_couverture_naf25_mesuree(tmp_path: Path) -> None:
    """`nb_naf25_renseigne` compte les actifs-employeurs dont la NAF25 est renseignée, pas les autres."""
    chemin = tmp_path / "etab.parquet"
    pq.write_table(
        _table(
            [
                _ligne(codeCommuneEtablissement="75001", activitePrincipaleNAF25Etablissement="12.34Z"),
                _ligne(codeCommuneEtablissement="75001", activitePrincipaleNAF25Etablissement=None),
            ]
        ),
        chemin,
    )
    agregat = agreger_polars(chemin, DATE_REFERENCE, FILTRES)
    ligne = agregat.row(0, named=True)
    assert ligne["nb_actifs_employeurs"] == 2
    assert ligne["nb_naf25_renseigne"] == 1


def test_anciennete_calculee_depuis_la_date_de_reference(tmp_path: Path) -> None:
    """L'âge est mesuré par rapport à `date_reference`, jamais `date.today()`."""
    chemin = tmp_path / "etab.parquet"
    pq.write_table(_table([_ligne(dateCreationEtablissement=date(2021, 8, 1))]), chemin)
    agregat = agreger_polars(chemin, date(2026, 8, 1), FILTRES)
    ligne = agregat.row(0, named=True)
    assert ligne["age_moyen_annees"] == pytest.approx(5.0, abs=0.01)
    assert ligne["nb_crees_moins_3ans"] == 0

    chemin_recent = tmp_path / "etab_recent.parquet"
    pq.write_table(_table([_ligne(dateCreationEtablissement=date(2025, 1, 1))]), chemin_recent)
    agregat_recent = agreger_polars(chemin_recent, date(2026, 8, 1), FILTRES)
    assert agregat_recent.row(0, named=True)["nb_crees_moins_3ans"] == 1


def test_ecriture_idempotente(tmp_path: Path) -> None:
    """Écrire deux fois le même agrégat produit le même fichier, sans jamais laisser de `.part`."""
    chemin = tmp_path / "etab.parquet"
    pq.write_table(_table([_ligne()]), chemin)
    agregat = agreger_polars(chemin, DATE_REFERENCE, FILTRES)

    destination = tmp_path / "sortie"
    destination.mkdir()
    ecrire_agregats(agregat, destination)
    premiere = pq.read_table(destination / NOM_FICHIER_SORTIE).to_pandas()
    ecrire_agregats(agregat, destination)
    seconde = pq.read_table(destination / NOM_FICHIER_SORTIE).to_pandas()

    pd.testing.assert_frame_equal(premiere, seconde)
    assert not list(destination.glob("*.part"))


# ─── Bout en bout, moteur local (Polars) ────────────────────────────────────


@pytest.fixture()
def settings_locales(tmp_path: Path) -> Settings:
    base = load_settings("dev")
    settings = base.model_copy(update={"data_root": tmp_path})
    dossier_raw = settings.raw_dir / "sirene"
    dossier_raw.mkdir(parents=True)
    shutil.copy(base.samples_dir / "sirene" / "StockEtablissement.parquet", dossier_raw / "StockEtablissement.parquet")
    manifeste = {"StockEtablissement": {"date_publication_stock": "2026-08-01T07:46:40.670000+00:00"}}
    (dossier_raw / "manifeste.json").write_text(json.dumps(manifeste), encoding="utf-8")
    assert settings.execution.moteur_volume == "local"
    return settings


def _totaux_attendus(chemin: Path) -> tuple[int, int]:
    """Recalcule, indépendamment du module testé, les deux totaux de référence."""
    table = pq.read_table(chemin, columns=list(COLONNES_PROJECTION)).to_pandas()
    avec_commune = table[table["codeCommuneEtablissement"].notna()]
    employeurs = avec_commune[avec_commune["caractereEmployeurEtablissement"] == "O"]
    actifs = int((employeurs["etatAdministratifEtablissement"] == "A").sum())
    fermes = int((employeurs["etatAdministratifEtablissement"] == "F").sum())
    return actifs, fermes


def test_executer_moteur_local_ecrit_un_agregat_coherent(settings_locales: Settings) -> None:
    rapport = run_sirene_agregats.executer(settings_locales)

    destination = settings_locales.processed_dir / "sirene" / NOM_FICHIER_SORTIE
    assert destination.exists()

    actifs_attendus, fermes_attendus = _totaux_attendus(
        settings_locales.raw_dir / "sirene" / "StockEtablissement.parquet"
    )
    assert rapport.nb_actifs_employeurs == actifs_attendus
    assert rapport.nb_fermes_employeurs == fermes_attendus
    assert rapport.date_reference == date(2026, 8, 1)

    table = pq.read_table(destination).to_pandas()
    assert int(table["nb_actifs_employeurs"].sum()) == actifs_attendus
    # Le grain est vérifié : aucune paire (commune, NAF) dupliquée.
    assert not table.duplicated(subset=["codeCommuneEtablissement", "activitePrincipaleEtablissement"]).any()


def test_executer_source_absente_leve(tmp_path: Path) -> None:
    base = load_settings("dev")
    settings = base.model_copy(update={"data_root": tmp_path})
    with pytest.raises(run_sirene_agregats.ErreurSireneAgregatsSourceAbsente):
        run_sirene_agregats.executer(settings)


def test_executer_moteur_cluster_ecrit_le_meme_resultat(tmp_path: Path) -> None:
    """Le moteur `cluster` passe par Spark et produit le même agrégat que Polars.

    Le moteur est forcé explicitement : depuis que la production s'exécute en
    `local` (Polars, ADR 0016 et 0019), s'appuyer sur la configuration `prod`
    ferait tourner Polars deux fois et « prouverait » l'égalité sans jamais
    exécuter Spark.
    """
    pytest.importorskip("pyspark")
    base = load_settings("prod")
    execution = base.execution.model_copy(update={"moteur_volume": "cluster"})
    settings = base.model_copy(update={"data_root": tmp_path, "execution": execution})
    assert settings.execution.moteur_volume == "cluster"
    dossier_raw = settings.raw_dir / "sirene"
    dossier_raw.mkdir(parents=True)
    shutil.copy(
        base.samples_dir / "sirene" / "StockEtablissement.parquet",
        dossier_raw / "StockEtablissement.parquet",
    )
    manifeste = {"StockEtablissement": {"date_publication_stock": "2026-08-01T07:46:40.670000+00:00"}}
    (dossier_raw / "manifeste.json").write_text(json.dumps(manifeste), encoding="utf-8")

    rapport = run_sirene_agregats.executer(settings)

    destination = settings.processed_dir / "sirene" / NOM_FICHIER_SORTIE
    assert destination.exists()
    actifs_attendus, fermes_attendus = _totaux_attendus(dossier_raw / "StockEtablissement.parquet")
    assert rapport.nb_actifs_employeurs == actifs_attendus
    assert rapport.nb_fermes_employeurs == fermes_attendus


def test_executer_manifeste_sans_date_leve(tmp_path: Path) -> None:
    base = load_settings("dev")
    settings = base.model_copy(update={"data_root": tmp_path})
    dossier_raw = settings.raw_dir / "sirene"
    dossier_raw.mkdir(parents=True)
    shutil.copy(
        base.samples_dir / "sirene" / "StockEtablissement.parquet",
        dossier_raw / "StockEtablissement.parquet",
    )
    (dossier_raw / "manifeste.json").write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(run_sirene_agregats.ErreurSireneAgregatsManifesteInvalide):
        run_sirene_agregats.executer(settings)


# ─── Spark : même résultat que Polars, preuve de projection ────────────────


@pytest.fixture(scope="module")
def spark_session():
    pytest.importorskip("pyspark")
    from edumatch.spark.sirene_agregats import construire_session

    session = construire_session("test-sirene-agregats")
    yield session
    session.stop()


def test_spark_reproduit_le_resultat_polars(spark_session) -> None:
    from edumatch.spark.sirene_agregats import agreger, lire_projection

    agregat_polars = agreger_polars(CHEMIN_ECHANTILLON, DATE_REFERENCE, FILTRES).sort(
        ["codeCommuneEtablissement", "activitePrincipaleEtablissement"]
    )
    df_spark = lire_projection(spark_session, CHEMIN_ECHANTILLON)
    agregat_spark = agreger(df_spark, DATE_REFERENCE, FILTRES).toPandas().sort_values(
        ["codeCommuneEtablissement", "activitePrincipaleEtablissement"]
    ).reset_index(drop=True)

    pd.testing.assert_frame_equal(
        agregat_polars.to_pandas().drop(columns=["date_reference"]).reset_index(drop=True),
        agregat_spark.drop(columns=["date_reference"]),
        check_dtype=False,
    )
    # La colonne de référence porte la même date des deux côtés, seul son type
    # diverge (`date` Polars contre `Timestamp` Spark/pandas) : comparée ici
    # séparément plutôt que dans `assert_frame_equal`, qui exigerait un type
    # identique pour une information qui, elle, est identique.
    assert set(pd.to_datetime(agregat_spark["date_reference"]).dt.date.unique()) == {DATE_REFERENCE}


def test_explain_montre_projection_et_pushdown(spark_session, capsys) -> None:
    """Preuve du critère E17 : 9 colonnes lues sur 54, filtrage appliqué à la lecture."""
    from edumatch.spark.sirene_agregats import lire_projection

    df = lire_projection(spark_session, CHEMIN_ECHANTILLON)
    df = df.filter(df["caractereEmployeurEtablissement"] == "O")
    df.explain(True)
    plan = capsys.readouterr().out

    assert "PushedFilters" in plan
    for colonne in COLONNES_PROJECTION:
        assert colonne in plan
    # Aucune des colonnes non retenues n'apparaît dans le schéma de lecture.
    assert "activitePrincipaleNAF25Etablissement" in plan  # colonne retenue, sanity check
    assert "statutDiffusionEtablissement" not in plan
