"""Tests des contrôles qualité Sirene (E14), sur `data/samples/` et sur des fichiers fabriqués."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from edumatch.quality import sirene as qsirene
from edumatch.quality._diagnostic import Gravite

COLONNES = list(qsirene.COLONNES_UTILES)


def _ligne_valide() -> dict[str, object]:
    return {
        "siret": "12345678901234",
        "activitePrincipaleEtablissement": "68.20B",
        "nomenclatureActivitePrincipaleEtablissement": "NAFRev2",
        "activitePrincipaleNAF25Etablissement": None,
        "codeCommuneEtablissement": "75115",
        "trancheEffectifsEtablissement": "NN",
        "etatAdministratifEtablissement": "A",
        "caractereEmployeurEtablissement": "N",
        "dateCreationEtablissement": date(2020, 1, 1),
    }


def _ecrire_parquet(chemin: Path, lignes: list[dict[str, object]]) -> None:
    colonnes = {nom: [ligne[nom] for ligne in lignes] for nom in COLONNES}
    table = pa.table(colonnes)
    pq.write_table(table, chemin)


def test_echantillon_reel_ne_produit_aucune_anomalie() -> None:
    chemin = Path("data/samples/sirene/StockEtablissement.parquet")
    rapport = qsirene.controler_fichier(chemin, 0.99)
    assert rapport.anomalies == ()


def test_ligne_valide_ne_produit_aucune_anomalie(tmp_path: Path) -> None:
    chemin = tmp_path / "StockEtablissement.parquet"
    _ecrire_parquet(chemin, [_ligne_valide()] * 10)
    rapport = qsirene.controler_fichier(chemin, 0.99)
    assert rapport.anomalies == ()


def test_colonne_absente_bloque(tmp_path: Path) -> None:
    colonnes = {nom: ["x"] for nom in COLONNES if nom != "siret"}
    table = pa.table(colonnes)
    chemin = tmp_path / "StockEtablissement.parquet"
    pq.write_table(table, chemin)
    rapport = qsirene.controler_fichier(chemin, 0.99)
    assert rapport.est_bloquant
    assert any(a.famille == "schema" for a in rapport.bloquantes)


def test_siret_manquant_sous_le_seuil_bloque(tmp_path: Path) -> None:
    lignes = [_ligne_valide() for _ in range(100)]
    for ligne in lignes[:5]:
        ligne["siret"] = None
    chemin = tmp_path / "StockEtablissement.parquet"
    _ecrire_parquet(chemin, lignes)
    rapport = qsirene.controler_fichier(chemin, 0.99)
    assert rapport.est_bloquant
    assert any(a.famille == "completude" for a in rapport.bloquantes)


def test_tranche_effectifs_nn_ne_declenche_aucune_anomalie(tmp_path: Path) -> None:
    """Le piège documenté : `NN` est une valeur, pas une absence."""
    lignes = [_ligne_valide() for _ in range(50)]
    chemin = tmp_path / "StockEtablissement.parquet"
    _ecrire_parquet(chemin, lignes)
    rapport = qsirene.controler_fichier(chemin, 0.99)
    assert rapport.anomalies == ()


def test_siret_non_conforme_bloque(tmp_path: Path) -> None:
    ligne = _ligne_valide()
    ligne["siret"] = "abc"
    chemin = tmp_path / "StockEtablissement.parquet"
    _ecrire_parquet(chemin, [ligne])
    rapport = qsirene.controler_fichier(chemin, 0.99)
    assert rapport.est_bloquant


def test_etat_administratif_hors_domaine_bloque(tmp_path: Path) -> None:
    ligne = _ligne_valide()
    ligne["etatAdministratifEtablissement"] = "X"
    chemin = tmp_path / "StockEtablissement.parquet"
    _ecrire_parquet(chemin, [ligne])
    rapport = qsirene.controler_fichier(chemin, 0.99)
    assert rapport.est_bloquant


@pytest.mark.parametrize(
    "nomenclature,code,attendu_bloquant",
    [
        ("NAFRev2", "68.20B", False),
        ("NAFRev2", "70.3C", True),  # format d'une autre nomenclature, refusé sous NAFRev2
        ("NAF1993", "70.3C", False),  # format historique, toléré car nomenclature différente
    ],
)
def test_format_naf_depend_de_la_nomenclature(
    tmp_path: Path, nomenclature: str, code: str, attendu_bloquant: bool
) -> None:
    ligne = _ligne_valide()
    ligne["nomenclatureActivitePrincipaleEtablissement"] = nomenclature
    ligne["activitePrincipaleEtablissement"] = code
    chemin = tmp_path / "StockEtablissement.parquet"
    _ecrire_parquet(chemin, [ligne])
    rapport = qsirene.controler_fichier(chemin, 0.99)
    assert rapport.est_bloquant is attendu_bloquant


def test_date_creation_proche_du_futur_avertit_sans_bloquer(tmp_path: Path) -> None:
    ligne = _ligne_valide()
    ligne["dateCreationEtablissement"] = date.today() + timedelta(days=90)
    chemin = tmp_path / "StockEtablissement.parquet"
    _ecrire_parquet(chemin, [ligne])
    rapport = qsirene.controler_fichier(chemin, 0.99)
    assert not rapport.est_bloquant
    assert any(a.gravite is Gravite.AVERTISSEMENT for a in rapport.anomalies)


def test_date_creation_tres_lointaine_bloque(tmp_path: Path) -> None:
    ligne = _ligne_valide()
    ligne["dateCreationEtablissement"] = date(3000, 1, 1)
    chemin = tmp_path / "StockEtablissement.parquet"
    _ecrire_parquet(chemin, [ligne])
    rapport = qsirene.controler_fichier(chemin, 0.99)
    assert rapport.est_bloquant
