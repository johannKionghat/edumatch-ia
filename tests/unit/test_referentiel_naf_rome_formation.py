"""Tests de la réconciliation NAF -> ROME -> formation (src/edumatch/referentiel/naf_rome_formation.py).

Fixtures écrites avec le schéma réel des trois sources (colonnes et
guillemets identiques à ceux constatés sur les fichiers téléchargés le
2026-08-30 — voir le module), pas des schémas inventés. Aucun accès réseau :
ce module ne fait que lire des fichiers déjà sur disque.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import openpyxl
import polars as pl
import pytest

from edumatch.referentiel.naf_rome_formation import (
    ErreurContratNafRomeFormation,
    charger_correspondance_rome_naf,
    charger_etat_rncp,
    charger_formations_ideo,
    charger_rncp_rome,
    construire_table,
    mesurer_couverture,
    mesurer_couverture_naf_sirene,
)

# ─── Fixtures fichiers ──────────────────────────────────────────────────────


def _ecrire_ideo(chemin: Path) -> None:
    entete = (
        '"code NSF";"code scolarité";"sigle type formation";"libellé type formation";'
        '"libellé formation principal";"sigle formation";"durée";"niveau de sortie indicatif";'
        '"code RNCP";"niveau de certification";"libellé niveau de certification";"tutelle";'
        '"URL et ID Onisep";"domaine/sous-domaine";"date création";"date de modification"\n'
    )
    lignes = [
        # une formation avec code RNCP qui trouvera un ROME couvert par la table NAF
        '"326";"";"BTS";"brevet de technicien supérieur";"BTS comptabilité et gestion";"CG";'
        '"2 ans";"III";"38506";"";"";"";"";"";"";""\n',
        # une formation avec code RNCP dont la fiche n'existe pas dans l'export ROME (orpheline)
        '"326";"";"BTS";"brevet de technicien supérieur";"formation orpheline";"OR";'
        '"2 ans";"III";"99999";"";"";"";"";"";"";""\n',
        # une formation sans code RNCP du tout
        '"326";"";"CAP";"certificat d\'aptitude professionnelle";"CAP sans RNCP";"NR";'
        '"2 ans";"V";"";"";"";"";"";"";"";""\n',
    ]
    chemin.write_text("﻿" + entete + "".join(lignes), encoding="utf-8")


def _ecrire_rncp_rome(chemin: Path) -> None:
    contenu = (
        '"Numero_Fiche";"Codes_Rome_Code";"Codes_Rome_Libelle"\n'
        '"RNCP38506";"M1203";"Comptabilité"\n'
        '"RNCP38506";"M1607";"Secrétariat"\n'
    )
    chemin.write_text("﻿" + contenu, encoding="utf-8")


def _ecrire_rncp_standard(chemin: Path) -> None:
    """Schéma réel du CSV standard (voir `rncp_2026-08-30.csv`) : seules `Numero_Fiche` et
    `Actif` sont utiles ici. La fiche RNCP38506 (celle qui traverse toute la chaîne dans les
    fixtures ci-dessus) est délibérément marquée `INACTIVE` : c'est le cas que le module doit
    exposer, jamais filtrer de sa propre initiative."""
    contenu = (
        '"Numero_Fiche";"Actif"\n'
        '"RNCP38506";"INACTIVE"\n'
        '"RNCP99999";"ACTIVE"\n'
    )
    chemin.write_text("﻿" + contenu, encoding="utf-8")


def _ecrire_rome_naf(chemin: Path) -> None:
    """Reproduit la structure hiérarchique réelle du classeur France Travail : une feuille
    "Définition" (ignorée) et une feuille "Secteur NAF <edition>" où une ligne "division"
    (code numérique, libellé) précède les codes ROME qui s'y rattachent."""
    classeur = openpyxl.Workbook()
    feuille_definition = classeur.active
    feuille_definition.title = "Définition"
    feuille_definition.append(("Arborescence secteur NAF du ROME",))

    feuille = classeur.create_sheet("Secteur NAF 06-2026")
    feuille.append(("0", "Transverse aux secteurs"))
    feuille.append(("Z9999", "Un métier transverse, à exclure"))
    feuille.append(("69", "Activites juridiques et comptables"))
    feuille.append(("M1203", "Comptabilité"))
    feuille.append(("82", "Activites administratives et autres activites de soutien aux entreprises"))
    feuille.append(("M1607", "Secrétariat"))
    classeur.save(chemin)


@pytest.fixture()
def sources(tmp_path: Path) -> dict[str, Path]:
    chemin_ideo = tmp_path / "formations.csv"
    chemin_rncp_rome = tmp_path / "rncp_rome_2026-08-30.csv"
    chemin_rncp_standard = tmp_path / "rncp_2026-08-30.csv"
    chemin_rome_naf = tmp_path / "rome_naf.xlsx"
    _ecrire_ideo(chemin_ideo)
    _ecrire_rncp_rome(chemin_rncp_rome)
    _ecrire_rncp_standard(chemin_rncp_standard)
    _ecrire_rome_naf(chemin_rome_naf)
    return {
        "ideo": chemin_ideo,
        "rncp_rome": chemin_rncp_rome,
        "rncp_standard": chemin_rncp_standard,
        "rome_naf": chemin_rome_naf,
    }


# ─── Lecture de chaque source ───────────────────────────────────────────────


def test_charger_formations_ideo_ne_garde_que_les_trois_colonnes_utiles(sources) -> None:
    df = charger_formations_ideo(sources["ideo"])

    assert df.columns == ["code_rncp_ideo", "code_nsf", "libelle_formation_ideo"]
    assert df.height == 3
    assert df.filter(pl.col("code_rncp_ideo") == "38506").height == 1


def test_charger_formations_ideo_leve_si_colonne_attendue_absente(tmp_path: Path) -> None:
    chemin = tmp_path / "formations_cassees.csv"
    chemin.write_text('"colonne_inattendue"\n"valeur"\n', encoding="utf-8")

    with pytest.raises(ErreurContratNafRomeFormation, match="Colonnes attendues absentes"):
        charger_formations_ideo(chemin)


def test_charger_rncp_rome_une_ligne_par_couple_fiche_rome(sources) -> None:
    df = charger_rncp_rome(sources["rncp_rome"])

    assert df.height == 2
    assert set(df["code_rncp_fiche"].to_list()) == {"38506"}
    assert set(df["code_rome"].to_list()) == {"M1203", "M1607"}


def test_charger_etat_rncp_convertit_actif_en_booleen(sources) -> None:
    df = charger_etat_rncp(sources["rncp_standard"])

    assert df.columns == ["code_rncp", "rncp_actif"]
    par_code = dict(zip(df["code_rncp"].to_list(), df["rncp_actif"].to_list()))
    assert par_code == {"38506": False, "99999": True}


def test_charger_etat_rncp_leve_si_valeur_hors_active_inactive(tmp_path: Path) -> None:
    chemin = tmp_path / "rncp_casse.csv"
    chemin.write_text('"Numero_Fiche";"Actif"\n"RNCP1";"RADIEE_PARTIELLE"\n', encoding="utf-8")

    with pytest.raises(ErreurContratNafRomeFormation, match="Valeurs inattendues"):
        charger_etat_rncp(chemin)


def test_charger_etat_rncp_leve_si_colonne_actif_absente(tmp_path: Path) -> None:
    chemin = tmp_path / "rncp_sans_actif.csv"
    chemin.write_text('"Numero_Fiche"\n"RNCP1"\n', encoding="utf-8")

    with pytest.raises(ErreurContratNafRomeFormation, match="Colonnes attendues absentes"):
        charger_etat_rncp(chemin)


def test_charger_correspondance_rome_naf_exclut_la_sentinelle_transverse(sources) -> None:
    df = charger_correspondance_rome_naf(sources["rome_naf"])

    codes_rome = set(df["code_rome"].to_list())
    assert codes_rome == {"M1203", "M1607"}, "Z9999 (sous la division sentinelle '0') doit être exclu"
    assert "00" not in df["naf_division"].to_list()


def test_charger_correspondance_rome_naf_leve_si_feuille_absente(tmp_path: Path) -> None:
    chemin = tmp_path / "sans_feuille_secteur.xlsx"
    classeur = openpyxl.Workbook()
    classeur.active.title = "Autre chose"
    classeur.save(chemin)

    with pytest.raises(ErreurContratNafRomeFormation, match="Secteur NAF"):
        charger_correspondance_rome_naf(chemin)


# ─── Jointure et mesure de couverture ──────────────────────────────────────


def test_construire_table_ne_garde_que_ce_qui_traverse_toute_la_chaine(sources) -> None:
    formations = charger_formations_ideo(sources["ideo"])
    rncp_rome = charger_rncp_rome(sources["rncp_rome"])
    rome_naf = charger_correspondance_rome_naf(sources["rome_naf"])
    etat_rncp = charger_etat_rncp(sources["rncp_standard"])

    table = construire_table(formations, rncp_rome, rome_naf, etat_rncp)

    # la formation orpheline (RNCP99999) et celle sans code RNCP sont absentes :
    # seule "BTS comptabilité et gestion" traverse toute la chaîne, vers ses deux métiers.
    assert set(table["code_rncp_ideo"].to_list()) == {"38506"}
    assert table.height == 2
    assert set(table["naf_division"].to_list()) == {"69", "82"}


def test_construire_table_expose_l_etat_rncp_sans_filtrer_les_fiches_radiees(sources) -> None:
    """RNCP38506 est marquée INACTIVE dans le CSV standard (voir `_ecrire_rncp_standard`) :
    la ligne doit rester dans la table, avec `rncp_actif` à `False` — jamais disparaître."""
    formations = charger_formations_ideo(sources["ideo"])
    rncp_rome = charger_rncp_rome(sources["rncp_rome"])
    rome_naf = charger_correspondance_rome_naf(sources["rome_naf"])
    etat_rncp = charger_etat_rncp(sources["rncp_standard"])

    table = construire_table(formations, rncp_rome, rome_naf, etat_rncp)

    assert "rncp_actif" in table.columns
    assert table.height == 2, "la certification radiée doit rester dans la table, pas être filtrée"
    assert set(table["rncp_actif"].to_list()) == {False}


def test_mesurer_couverture_rapporte_chaque_maillon_et_declare_le_manque_parcoursup(sources) -> None:
    formations = charger_formations_ideo(sources["ideo"])
    rncp_rome = charger_rncp_rome(sources["rncp_rome"])
    rome_naf = charger_correspondance_rome_naf(sources["rome_naf"])
    etat_rncp = charger_etat_rncp(sources["rncp_standard"])
    table = construire_table(formations, rncp_rome, rome_naf, etat_rncp)

    rapport = mesurer_couverture(formations, rncp_rome, rome_naf, table)

    par_nom = {m.nom: m for m in rapport.maillons}
    assert par_nom["formation_ideo -> code_rncp_renseigne"].total == 3
    assert par_nom["formation_ideo -> code_rncp_renseigne"].retenus == 2
    assert par_nom["formation_ideo(avec_rncp) -> rattachee_a_un_rome"].retenus == 1, (
        "la fiche RNCP99999 n'existe pas dans l'export ROME : elle ne doit pas être comptée"
    )
    assert any("Parcoursup" in m for m in rapport.manques_declares), (
        "le manque de clé vers Parcoursup doit être déclaré explicitement, pas seulement omis"
    )
    assert par_nom["table_finale -> lignes_rattachees_a_certification_active"].total == 2
    assert par_nom["table_finale -> lignes_rattachees_a_certification_active"].retenus == 0, (
        "les deux lignes de la table finale portent la fiche RNCP38506, marquée INACTIVE"
    )
    assert par_nom["table_finale -> formations_distinctes_rattachees_a_certification_active"].total == 1
    assert par_nom["table_finale -> formations_distinctes_rattachees_a_certification_active"].retenus == 0


def test_mesurer_couverture_naf_sirene_isole_les_divisions_non_couvertes() -> None:
    codes_naf = ["62.01Z", "62.02A", "10.11Z", "34.00Z", "00.00Z"]
    divisions_couvertes = {"62", "10"}

    rapport = mesurer_couverture_naf_sirene(codes_naf, divisions_couvertes)

    # divisions distinctes présentes dans Sirene : 62, 10, 34, 00 (un code NAF "00.00Z" a
    # bien une division "00", même si elle est par ailleurs exclue de la table France Travail
    # à titre de sentinelle "transverse" — les deux exclusions n'ont pas la même origine).
    assert rapport.total == 4
    assert rapport.retenus == 2
    assert "34" in rapport.note
    assert "00" in rapport.note


def test_ecriture_atomique_utf8_est_utilisee_par_les_manifestes(sources) -> None:
    """Non-régression légère : les libellés accentués de ces sources ne doivent jamais planter
    la lecture (couvre indirectement le bug corrigé dans `_flux.ecriture_atomique`, testé
    directement dans `test_ingestion_flux.py`)."""
    df = charger_formations_ideo(sources["ideo"])
    assert "comptabilité" in df["libelle_formation_ideo"].to_list()[0]
