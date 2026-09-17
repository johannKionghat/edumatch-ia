"""Tests des contrôles qualité des référentiels ONISEP (IDÉO) et RNCP."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from edumatch.quality import referentiels as qr


def _ecrire_csv(chemin: Path, colonnes: list[str], lignes: list[dict[str, str]], delimiteur: str = ";") -> None:
    with chemin.open("w", encoding="utf-8", newline="") as fichier:
        ecrivain = csv.DictWriter(fichier, fieldnames=colonnes, delimiter=delimiteur)
        ecrivain.writeheader()
        ecrivain.writerows(lignes)


# ─── IDÉO ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "jeu", ["formations", "metiers", "structures_secondaire", "structures_superieur"]
)
def test_echantillon_reel_ideo_ne_produit_aucune_anomalie(jeu: str) -> None:
    chemin = Path(f"data/samples/referentiels/ideo/{jeu}.csv")
    rapport = qr.controler_ideo_jeu(chemin, jeu, 0.99)
    assert rapport.anomalies == ()


def test_bom_utf8_ne_provoque_pas_de_faux_positif_de_schema(tmp_path: Path) -> None:
    """Reproduit le cas réel : les quatre fichiers IDÉO portent un BOM UTF-8 en tête.

    Sans `utf-8-sig`, le BOM se colle au nom de la première colonne
    (`\\ufefflibelle metier`), qui ne correspond alors plus à l'ancre de
    complétude attendue — constaté sur les quatre fichiers réellement
    téléchargés le 2026-08-29 avant d'être corrigé dans `controler_ideo_jeu`.
    """
    colonnes = [f"c{i}" for i in range(13)]
    colonnes[0] = "libelle metier"
    chemin = tmp_path / "metiers.csv"
    contenu = ";".join(colonnes) + "\n" + ";".join("x" for _ in colonnes) + "\n"
    chemin.write_bytes(b"\xef\xbb\xbf" + contenu.encode("utf-8"))
    rapport = qr.controler_ideo_jeu(chemin, "metiers", 0.99)
    assert rapport.anomalies == ()


def test_nombre_de_colonnes_incorrect_bloque(tmp_path: Path) -> None:
    chemin = tmp_path / "formations.csv"
    _ecrire_csv(chemin, ["a", "b"], [{"a": "1", "b": "2"}])
    rapport = qr.controler_ideo_jeu(chemin, "formations", 0.99)
    assert rapport.est_bloquant
    assert any(a.famille == "schema" for a in rapport.bloquantes)


def test_colonne_ancre_incomplete_bloque(tmp_path: Path) -> None:
    colonnes = [f"c{i}" for i in range(16)]
    colonnes[4] = "libelle formation principal"
    lignes = [dict.fromkeys(colonnes, "x") for _ in range(100)]
    for ligne in lignes[:5]:
        ligne["libelle formation principal"] = ""
    chemin = tmp_path / "formations.csv"
    _ecrire_csv(chemin, colonnes, lignes)
    rapport = qr.controler_ideo_jeu(chemin, "formations", 0.99)
    assert rapport.est_bloquant
    assert any(a.famille == "completude" for a in rapport.bloquantes)


# ─── RNCP ───────────────────────────────────────────────────────────────────


def test_echantillon_reel_rncp_ne_produit_aucune_anomalie() -> None:
    chemin = Path("data/samples/referentiels/rncp/rncp_echantillon.csv")
    rapport = qr.controler_rncp(chemin, "utf-8", ";", 0.99)
    assert rapport.anomalies == ()


LIGNE_RNCP_VALIDE = {
    "Id_Fiche": "1",
    "Numero_Fiche": "RNCP1",
    "Intitule": "Exemple",
    "Abrege_Libelle": "",
    "Abrege_Intitule": "",
    "Nomenclature_Europe_Niveau": "",
    "Nomenclature_Europe_Intitule": "",
    "Accessible_Nouvelle_Caledonie": "",
    "Accessible_Polynesie_Francaise": "",
    "Date_dernier_jo": "01/01/2020",
    "Date_Decision": "",
    "Date_Fin_Enregistrement": "",
    "Date_Effet": "",
    "Type_Enregistrement": "",
    "Validation_Partielle": "",
    "Actif": "ACTIVE",
}


def test_ligne_rncp_valide_ne_produit_aucune_anomalie(tmp_path: Path) -> None:
    chemin = tmp_path / "rncp_2026-08-29.csv"
    _ecrire_csv(chemin, list(LIGNE_RNCP_VALIDE), [LIGNE_RNCP_VALIDE])
    rapport = qr.controler_rncp(chemin, "utf-8", ";", 0.99)
    assert rapport.anomalies == ()


def test_actif_hors_domaine_bloque(tmp_path: Path) -> None:
    ligne = dict(LIGNE_RNCP_VALIDE)
    ligne["Actif"] = "PEUT-ETRE"
    chemin = tmp_path / "rncp_2026-08-29.csv"
    _ecrire_csv(chemin, list(ligne), [ligne])
    rapport = qr.controler_rncp(chemin, "utf-8", ";", 0.99)
    assert rapport.est_bloquant


def test_numero_fiche_hors_motif_bloque(tmp_path: Path) -> None:
    ligne = dict(LIGNE_RNCP_VALIDE)
    ligne["Numero_Fiche"] = "ABC123"
    chemin = tmp_path / "rncp_2026-08-29.csv"
    _ecrire_csv(chemin, list(ligne), [ligne])
    rapport = qr.controler_rncp(chemin, "utf-8", ";", 0.99)
    assert rapport.est_bloquant


def test_numero_fiche_rs_est_accepte(tmp_path: Path) -> None:
    """Le Répertoire Spécifique porte le préfixe RS, pas seulement RNCP."""
    ligne = dict(LIGNE_RNCP_VALIDE)
    ligne["Numero_Fiche"] = "RS27"
    chemin = tmp_path / "rncp_2026-08-29.csv"
    _ecrire_csv(chemin, list(ligne), [ligne])
    rapport = qr.controler_rncp(chemin, "utf-8", ";", 0.99)
    assert rapport.anomalies == ()


def test_date_non_conforme_bloque(tmp_path: Path) -> None:
    ligne = dict(LIGNE_RNCP_VALIDE)
    ligne["Date_dernier_jo"] = "2020-01-01"  # ISO, pas JJ/MM/AAAA
    chemin = tmp_path / "rncp_2026-08-29.csv"
    _ecrire_csv(chemin, list(ligne), [ligne])
    rapport = qr.controler_rncp(chemin, "utf-8", ";", 0.99)
    assert rapport.est_bloquant


def test_colonne_obligatoire_absente_bloque(tmp_path: Path) -> None:
    ligne = dict(LIGNE_RNCP_VALIDE)
    del ligne["Actif"]
    chemin = tmp_path / "rncp_2026-08-29.csv"
    _ecrire_csv(chemin, list(ligne), [ligne])
    rapport = qr.controler_rncp(chemin, "utf-8", ";", 0.99)
    assert rapport.est_bloquant
    assert any(a.famille == "schema" for a in rapport.bloquantes)
