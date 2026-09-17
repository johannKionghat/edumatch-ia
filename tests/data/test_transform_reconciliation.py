"""Tests de la réconciliation bronze -> silver Parcoursup.

Deux catégories, sur le modèle des tests qualité : les huit
échantillons versionnés (`data/samples/parcoursup/`), qui doivent tous se
réconcilier en un seul bloc sans erreur ; des millésimes fabriqués dans
`tmp_path`, un par piège déjà documenté.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd
import pytest
from conftest import LIGNE_VALIDE, _ecrire_csv

from edumatch.config import Settings, load_settings
from edumatch.transform.reconciliation import (
    COLONNE_CLE,
    COLONNE_SESSION,
    ErreurReconciliationParcoursup,
    reconcilier,
)


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings("prod")


@pytest.fixture()
def chemins_echantillons(settings: Settings) -> dict[int, Path]:
    dossier = settings.samples_dir / "parcoursup"
    return {
        millesime: dossier / f"parcoursup_{millesime}.csv"
        for millesime in settings.donnees.parcoursup.millesimes
    }


# ─── Sur les huit échantillons réels ──────────────────────────────────────


def test_toutes_les_colonnes_classees_sont_dans_le_resultat(
    settings: Settings, chemins_echantillons: dict[int, Path]
) -> None:
    table, _ = reconcilier(chemins_echantillons, settings.modele.variables)
    attendues = settings.modele.variables.colonnes_sources - {COLONNE_SESSION}
    assert set(table.columns) - {COLONNE_SESSION} == attendues


def test_grain_unique_sur_les_echantillons_reels(
    settings: Settings, chemins_echantillons: dict[int, Path]
) -> None:
    """`reconcilier` lèverait sur un doublon : ne pas lever ici prouve déjà l'unicité."""
    table, _ = reconcilier(chemins_echantillons, settings.modele.variables)
    avec_cle = table[table[COLONNE_CLE].notna()]
    assert not avec_cle.duplicated(subset=[COLONNE_SESSION, COLONNE_CLE]).any()


def test_lignes_sans_label_disponible_couvre_2018_et_2019(
    settings: Settings, chemins_echantillons: dict[int, Path]
) -> None:
    """Le numérateur du label n'existe qu'à partir de 2020 (ADR 0012) : 2018 et 2019 n'ont pas de label."""
    table, rapport = reconcilier(chemins_echantillons, settings.modele.variables)
    attendu = int((table[COLONNE_SESSION] < 2020).sum())
    assert rapport.lignes_sans_label_disponible == attendu
    assert attendu > 0  # les échantillons couvrent bien 2018 et 2019


def test_idempotence_sur_les_echantillons_reels(
    settings: Settings, chemins_echantillons: dict[int, Path]
) -> None:
    table_1, rapport_1 = reconcilier(chemins_echantillons, settings.modele.variables)
    table_2, rapport_2 = reconcilier(chemins_echantillons, settings.modele.variables)
    pd.testing.assert_frame_equal(table_1, table_2)
    assert rapport_1 == rapport_2


def test_departement_corse_reste_texte_sur_les_echantillons_reels(
    settings: Settings, chemins_echantillons: dict[int, Path]
) -> None:
    table, _ = reconcilier(chemins_echantillons, settings.modele.variables)
    assert table["dep"].dtype == "string"


# ─── Sur des millésimes fabriqués, un piège à la fois ─────────────────────


def test_reconstruction_cod_aff_form_depuis_g_ta_cod(
    settings: Settings, tmp_path: Path
) -> None:
    """Le piège central de 2018/2019 : `cod_aff_form` absente, reconstruite depuis l'URL."""
    ligne = copy.deepcopy(LIGNE_VALIDE)
    del ligne["cod_aff_form"]
    ligne["session"] = "2018"
    ligne["lien_form_psup"] = "https://dossier.parcoursup.fr/candidature?g_ta_cod=42017"
    chemin = tmp_path / "parcoursup_2018.csv"
    _ecrire_csv(chemin, [ligne])

    table, rapport = reconcilier({2018: chemin}, settings.modele.variables)

    assert table.loc[0, COLONNE_CLE] == "42017"
    assert rapport.taux_cle_reconstruite_par_session[2018] == 1.0


def test_couverture_de_reconstruction_partielle_est_mesuree(
    settings: Settings, tmp_path: Path
) -> None:
    """Une ligne sur deux sans `g_ta_cod` extractible : la couverture doit le refléter, pas le masquer."""
    complete = copy.deepcopy(LIGNE_VALIDE)
    del complete["cod_aff_form"]
    complete["session"] = "2019"
    complete["lien_form_psup"] = "https://dossier.parcoursup.fr/candidature?g_ta_cod=7"

    incomplete = copy.deepcopy(LIGNE_VALIDE)
    del incomplete["cod_aff_form"]
    incomplete["session"] = "2019"
    incomplete["lien_form_psup"] = "https://dossier.parcoursup.fr/lien-sans-parametre"

    chemin = tmp_path / "parcoursup_2019.csv"
    _ecrire_csv(chemin, [complete, incomplete])

    _, rapport = reconcilier({2019: chemin}, settings.modele.variables)

    assert rapport.taux_cle_reconstruite_par_session[2019] == pytest.approx(0.5)


def test_colonne_non_encore_publiee_est_remplie_de_valeurs_manquantes(
    settings: Settings, tmp_path: Path
) -> None:
    """`select_form` n'existe pas en 2019 : elle doit exister dans le résultat, entièrement vide."""
    ligne = copy.deepcopy(LIGNE_VALIDE)
    del ligne["select_form"]
    del ligne["cod_aff_form"]
    ligne["session"] = "2019"
    chemin = tmp_path / "parcoursup_2019.csv"
    _ecrire_csv(chemin, [ligne])

    table, rapport = reconcilier({2019: chemin}, settings.modele.variables)

    assert "select_form" in table.columns
    assert table["select_form"].isna().all()
    assert "select_form" in rapport.colonnes_manquantes_par_session[2019]


def test_grain_duplique_leve_une_erreur_explicite(settings: Settings, tmp_path: Path) -> None:
    """Deux lignes de la même session portant la même clé violent le grain (session, cod_aff_form)."""
    ligne_a = copy.deepcopy(LIGNE_VALIDE)
    ligne_b = copy.deepcopy(LIGNE_VALIDE)  # même session, même cod_aff_form
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, [ligne_a, ligne_b])

    with pytest.raises(ErreurReconciliationParcoursup):
        reconcilier({2025: chemin}, settings.modele.variables)


def test_meme_cle_sur_deux_sessions_differentes_ne_leve_pas(
    settings: Settings, tmp_path: Path
) -> None:
    """Le grain est (session, cod_aff_form) : la même formation d'une année sur l'autre n'est pas un doublon."""
    ligne = copy.deepcopy(LIGNE_VALIDE)
    chemin_2024 = tmp_path / "parcoursup_2024.csv"
    chemin_2025 = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin_2024, [copy.deepcopy(ligne)])
    _ecrire_csv(chemin_2025, [copy.deepcopy(ligne)])

    table, _ = reconcilier({2024: chemin_2024, 2025: chemin_2025}, settings.modele.variables)
    assert len(table) == 2


def test_typage_entier_pour_un_compteur_sans_decimale(settings: Settings, tmp_path: Path) -> None:
    lignes = [copy.deepcopy(LIGNE_VALIDE), copy.deepcopy(LIGNE_VALIDE)]
    lignes[0]["cod_aff_form"], lignes[0]["acc_tot"] = "1", "10"
    lignes[1]["cod_aff_form"], lignes[1]["acc_tot"] = "2", "434"
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, lignes)

    table, _ = reconcilier({2025: chemin}, settings.modele.variables)

    assert table["acc_tot"].dtype == "Int64"
    assert table["acc_tot"].tolist() == [10, 434]


def test_typage_decimal_pour_un_pourcentage(settings: Settings, tmp_path: Path) -> None:
    lignes = [copy.deepcopy(LIGNE_VALIDE), copy.deepcopy(LIGNE_VALIDE)]
    lignes[0]["cod_aff_form"], lignes[0]["pct_bg"] = "1", "60.0"
    lignes[1]["cod_aff_form"], lignes[1]["pct_bg"] = "2", "33.3"
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, lignes)

    table, _ = reconcilier({2025: chemin}, settings.modele.variables)

    assert table["pct_bg"].dtype == "Float64"


def test_departement_corse_force_le_type_texte_meme_sans_autre_valeur_manquante(
    settings: Settings, tmp_path: Path
) -> None:
    """Le piège explicite de l'étape : `2A`/`2B` ne doivent jamais devenir une conversion ratée masquée."""
    lignes = [copy.deepcopy(LIGNE_VALIDE), copy.deepcopy(LIGNE_VALIDE)]
    lignes[0]["cod_aff_form"], lignes[0]["dep"] = "1", "2A"
    lignes[1]["cod_aff_form"], lignes[1]["dep"] = "2", "2B"
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, lignes)

    table, _ = reconcilier({2025: chemin}, settings.modele.variables)

    assert table["dep"].dtype == "string"
    assert set(table["dep"]) == {"2A", "2B"}


def test_aucun_fichier_leve_une_erreur_explicite(settings: Settings) -> None:
    with pytest.raises(ErreurReconciliationParcoursup):
        reconcilier({}, settings.modele.variables)
