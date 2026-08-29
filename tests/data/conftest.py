"""Fixtures communes aux tests des contrôles qualité (E14).

Fabrique des fichiers Parcoursup minimaux et volontairement invalides dans
`tmp_path` : jamais dans `data/`, conformément à la consigne de l'étape.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

# Une ligne Parcoursup 2025 valide au sens des quatre familles de contrôle :
# schéma (les colonnes de la liste blanche et les clés sont présentes),
# complétude (aucune vide), cohérence (acc_tot = somme des quatre bacs,
# pct_bg exactement reconstruit depuis acc_bg/acc_neobac, ratio positif).
LIGNE_VALIDE: dict[str, str] = {
    "session": "2025",
    "cod_aff_form": "1000",
    "lien_form_psup": "https://exemple.test/fiche/1000",
    "fili": "BTS",
    "fil_lib_voe_acc": "BTS Exemple",
    "form_lib_voe_acc": "BTS",
    "select_form": "oui",
    "contrat_etab": "Public",
    "tri": "Lycée",
    "dep": "75",
    "acad_mies": "Paris",
    "region_etab_aff": "Ile-de-France",
    "acc_tot": "10",
    "acc_bg": "6",
    "acc_bt": "2",
    "acc_bp": "2",
    "acc_at": "0",
    "acc_neobac": "10",
    "pct_bg": "60",
    "prop_tot_bg": "8",
    "nb_voe_pp_bg": "8",
}


def _ecrire_csv(chemin: Path, lignes: list[dict[str, str]]) -> None:
    colonnes = sorted({colonne for ligne in lignes for colonne in ligne})
    with chemin.open("w", encoding="utf-8-sig", newline="") as fichier:
        ecrivain = csv.DictWriter(fichier, fieldnames=colonnes, delimiter=";", restval="")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)


@pytest.fixture()
def fichier_parcoursup_valide(tmp_path: Path):
    """Fabrique un millésime 2025 valide, une seule ligne, dans `tmp_path`."""

    def _fabriquer(lignes: list[dict[str, str]] | None = None) -> Path:
        chemin = tmp_path / "parcoursup_2025.csv"
        _ecrire_csv(chemin, lignes or [dict(LIGNE_VALIDE)])
        return chemin

    return _fabriquer
