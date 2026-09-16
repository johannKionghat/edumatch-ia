"""Tests des contrôles qualité Parcoursup (E14).

Deux catégories : sur les échantillons versionnés (`data/samples/`), qui
doivent tous passer sans anomalie bloquante ; sur des fichiers fabriqués
dans `tmp_path`, volontairement invalides, un par famille de contrôle.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from conftest import LIGNE_VALIDE, _ecrire_csv

from edumatch.config import Settings, load_settings
from edumatch.quality import parcoursup as qp
from edumatch.quality._diagnostic import Gravite


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings("prod")


@pytest.mark.parametrize("millesime", range(2018, 2026))
def test_echantillons_reels_ne_produisent_aucune_anomalie_bloquante(
    settings: Settings, millesime: int
) -> None:
    chemin = settings.samples_dir / "parcoursup" / f"parcoursup_{millesime}.csv"
    rapport = qp.controler_millesime(chemin, millesime, settings)
    assert not rapport.est_bloquant, [a.formatee() for a in rapport.bloquantes]


def test_ligne_valide_ne_produit_aucune_anomalie(
    settings: Settings, fichier_parcoursup_valide
) -> None:
    chemin = fichier_parcoursup_valide()
    rapport = qp.controler_millesime(chemin, 2025, settings)
    assert rapport.anomalies == ()


def test_colonne_de_la_liste_blanche_absente_bloque(
    settings: Settings, tmp_path: Path
) -> None:
    """Schéma : `fili` manquante doit bloquer, pas seulement avertir."""
    ligne = copy.deepcopy(LIGNE_VALIDE)
    del ligne["fili"]
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, [ligne])
    rapport = qp.controler_millesime(chemin, 2025, settings)
    assert rapport.est_bloquant
    assert any(a.famille == "schema" for a in rapport.bloquantes)


def test_departement_hors_domaine_bloque(settings: Settings, tmp_path: Path) -> None:
    """`dep` doit accepter 2A/2B mais rejeter une valeur hors du motif départemental."""
    ligne = copy.deepcopy(LIGNE_VALIDE)
    ligne["dep"] = "PAS-UN-DEPARTEMENT"
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, [ligne])
    rapport = qp.controler_millesime(chemin, 2025, settings)
    assert rapport.est_bloquant


@pytest.mark.parametrize("code_corse", ["2A", "2B"])
def test_departement_corse_ne_bloque_pas(
    settings: Settings, tmp_path: Path, code_corse: str
) -> None:
    """Le piège explicitement visé par l'étape : 2A/2B ne sont pas des entiers."""
    ligne = copy.deepcopy(LIGNE_VALIDE)
    ligne["dep"] = code_corse
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, [ligne])
    rapport = qp.controler_millesime(chemin, 2025, settings)
    assert not rapport.est_bloquant


def test_completude_sous_le_seuil_bloque(settings: Settings, tmp_path: Path) -> None:
    """98 lignes complètes, 2 où `region_etab_aff` manque : 98 % < seuil de 99 %."""
    lignes = []
    for i in range(98):
        ligne = copy.deepcopy(LIGNE_VALIDE)
        ligne["cod_aff_form"] = str(1000 + i)
        lignes.append(ligne)
    for i in range(2):
        ligne_incomplete = copy.deepcopy(LIGNE_VALIDE)
        ligne_incomplete["cod_aff_form"] = str(9000 + i)
        ligne_incomplete["region_etab_aff"] = ""
        lignes.append(ligne_incomplete)
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, lignes)
    rapport = qp.controler_millesime(chemin, 2025, settings)
    assert rapport.est_bloquant
    assert any(a.famille == "completude" for a in rapport.bloquantes)


def test_acc_term_bimodale_ne_declenche_aucun_avertissement(
    settings: Settings, tmp_path: Path
) -> None:
    """Le piège `acc_term` : vide pour toutes les lignes d'une filière, ce n'est pas une anomalie."""
    lignes = [copy.deepcopy(LIGNE_VALIDE) for _ in range(3)]
    for i, ligne in enumerate(lignes):
        ligne["cod_aff_form"] = str(2000 + i)
        ligne["fili"] = "Licence"
        ligne["acc_term"] = ""  # non applicable pour toutes les lignes de cette filière
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, lignes)
    rapport = qp.controler_non_applicable_acc_term(chemin)
    assert rapport.anomalies == ()


def test_acc_term_partiellement_remplie_dans_une_filiere_avertit(
    settings: Settings, tmp_path: Path
) -> None:
    """Le contrôle inverse du précédent : une filière ni 0 % ni 100 % doit avertir."""
    lignes = []
    for i, valeur in enumerate(["", "3", ""]):
        ligne = copy.deepcopy(LIGNE_VALIDE)
        ligne["cod_aff_form"] = str(3000 + i)
        ligne["fili"] = "Licence"
        ligne["acc_term"] = valeur
        lignes.append(ligne)
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, lignes)
    rapport = qp.controler_non_applicable_acc_term(chemin)
    assert rapport.anomalies != ()
    assert all(a.gravite is Gravite.AVERTISSEMENT for a in rapport.anomalies)


def test_ratio_admission_negatif_bloque(settings: Settings, tmp_path: Path) -> None:
    ligne = copy.deepcopy(LIGNE_VALIDE)
    ligne["nb_voe_pp_bg"] = "-1"
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, [ligne])
    rapport = qp.controler_coherence(chemin, 0.5)
    assert rapport.est_bloquant


def test_ratio_admission_superieur_a_un_ne_bloque_pas(
    settings: Settings, tmp_path: Path
) -> None:
    """Structurel (ADR 0009) : ne jamais interdire un dépassement de 1."""
    ligne = copy.deepcopy(LIGNE_VALIDE)
    ligne["prop_tot_bg"] = "50"
    ligne["nb_voe_pp_bg"] = "2"  # ratio de 25, comparable au maximum réel observé (26)
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, [ligne])
    rapport = qp.controler_coherence(chemin, 0.5)
    assert not rapport.est_bloquant


def test_admis_positif_a_denominateur_nul_ne_bloque_pas(
    settings: Settings, tmp_path: Path
) -> None:
    """Falsifié sur données réelles (482 cellules en 2025) : ne doit pas bloquer."""
    ligne = copy.deepcopy(LIGNE_VALIDE)
    ligne["prop_tot_bg"] = "3"
    ligne["nb_voe_pp_bg"] = "0"
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, [ligne])
    rapport = qp.controler_coherence(chemin, 0.5)
    assert not rapport.est_bloquant


def test_pourcentage_incoherent_avec_sa_reconstruction_bloque(
    settings: Settings, tmp_path: Path
) -> None:
    ligne = copy.deepcopy(LIGNE_VALIDE)
    ligne["pct_bg"] = "10"  # devrait valoir 60 (6/10*100)
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, [ligne])
    rapport = qp.controler_coherence(chemin, 0.5)
    assert rapport.est_bloquant


def test_epsilon_flottant_de_la_reconstruction_ne_bloque_pas(
    settings: Settings, tmp_path: Path
) -> None:
    """Reproduit l'écart mesuré sur la session 2025 réelle (23/40×100 = 57,49999999999999)."""
    ligne = copy.deepcopy(LIGNE_VALIDE)
    ligne["acc_bg"] = "23"
    ligne["acc_neobac"] = "40"
    ligne["pct_bg"] = "58"
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, [ligne])
    rapport = qp.controler_coherence(chemin, 0.5)
    assert not rapport.est_bloquant


def test_somme_admis_incoherente_avertit_sans_bloquer(
    settings: Settings, tmp_path: Path
) -> None:
    """Falsifié sur cinq des huit sessions réelles : avertissement, jamais blocage."""
    ligne = copy.deepcopy(LIGNE_VALIDE)
    ligne["acc_tot"] = "11"  # somme réelle des quatre bacs vaut 10
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, [ligne])
    rapport = qp.controler_coherence(chemin, 0.5)
    assert not rapport.est_bloquant
    assert any(a.gravite is Gravite.AVERTISSEMENT for a in rapport.anomalies)


def test_colonne_absente_avant_sa_premiere_apparition_ne_bloque_pas(
    settings: Settings, tmp_path: Path
) -> None:
    """`select_form` n'existe pas avant 2020 : l'absence sur 2019 n'est pas une anomalie."""
    ligne = copy.deepcopy(LIGNE_VALIDE)
    del ligne["select_form"]
    del ligne["cod_aff_form"]  # absente elle aussi avant 2020
    ligne["session"] = "2019"
    chemin = tmp_path / "parcoursup_2019.csv"
    _ecrire_csv(chemin, [ligne])
    rapport = qp.controler_schema_et_completude(
        chemin, 2019, settings.modele.variables, settings.qualite.parcoursup.seuil_completude
    )
    assert not rapport.est_bloquant


def test_colonne_absente_apres_sa_premiere_apparition_bloque(
    settings: Settings, tmp_path: Path
) -> None:
    """La même absence, mais sur 2025 : `select_form` doit exister depuis 2020."""
    ligne = copy.deepcopy(LIGNE_VALIDE)
    del ligne["select_form"]
    chemin = tmp_path / "parcoursup_2025.csv"
    _ecrire_csv(chemin, [ligne])
    rapport = qp.controler_schema_et_completude(
        chemin, 2025, settings.modele.variables, settings.qualite.parcoursup.seuil_completude
    )
    assert rapport.est_bloquant
