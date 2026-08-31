"""Tests du terme d'affinité (src/edumatch/matching/affinite.py)."""

from __future__ import annotations

from dataclasses import fields

import pytest

from edumatch.matching.affinite import (
    CHAMPS_INTERDITS,
    ProfilCandidat,
    calculer_affinite,
    normaliser,
)


def test_aucun_champ_de_genre_dans_le_profil_candidat() -> None:
    """Invariant du projet (ADR 0011) : le genre n'entre jamais dans un composant qui
    influence une recommandation, affinité comprise."""
    noms = {champ.name for champ in fields(ProfilCandidat)}
    assert not (noms & CHAMPS_INTERDITS)


def test_profil_vide_donne_une_affinite_de_un() -> None:
    profil = ProfilCandidat()
    terme = calculer_affinite("BTS", "Comptabilité", "BTS Comptabilité", "75", profil)
    assert terme.valeur == 1.0
    assert terme.filtre_type_formation_respecte is True
    assert terme.filtre_domaine_respecte is True
    assert terme.territoire_correspond is None


def test_type_formation_qui_ne_correspond_pas_annule_laffinite() -> None:
    profil = ProfilCandidat(type_formation="Licence")
    terme = calculer_affinite("BTS", "Comptabilité", "BTS Comptabilité", "75", profil)
    assert terme.valeur == 0.0
    assert terme.filtre_type_formation_respecte is False


def test_type_formation_insensible_a_la_casse_et_aux_accents() -> None:
    profil = ProfilCandidat(type_formation="bts")
    terme = calculer_affinite("BTS", "Comptabilité", "BTS Comptabilité", "75", profil)
    assert terme.filtre_type_formation_respecte is True
    assert terme.valeur == 1.0


def test_domaine_absent_du_libelle_annule_laffinite() -> None:
    profil = ProfilCandidat(domaine="informatique")
    terme = calculer_affinite("BTS", "Comptabilité et gestion", "BTS CG", "75", profil)
    assert terme.valeur == 0.0
    assert terme.filtre_domaine_respecte is False


def test_domaine_present_dans_le_libelle_ne_penalise_pas() -> None:
    profil = ProfilCandidat(domaine="informatique")
    terme = calculer_affinite(
        "BTS", "Services informatiques aux organisations", "BTS SIO", "75", profil
    )
    assert terme.filtre_domaine_respecte is True
    assert terme.valeur == 1.0


def test_territoire_hors_zone_attenue_sans_exclure() -> None:
    profil = ProfilCandidat(departement="69")
    terme = calculer_affinite(
        "BTS", "Comptabilité", "BTS Comptabilité", "75", profil, facteur_territoire_hors_zone=0.6
    )
    assert terme.territoire_correspond is False
    assert terme.valeur == pytest.approx(0.6)
    assert terme.valeur > 0.0  # atténué, pas exclu (voir le docstring du module)


def test_territoire_correspondant_ne_penalise_pas() -> None:
    profil = ProfilCandidat(departement="75")
    terme = calculer_affinite("BTS", "Comptabilité", "BTS Comptabilité", "75", profil)
    assert terme.territoire_correspond is True
    assert terme.valeur == 1.0


def test_deux_filtres_durs_combines_restent_a_zero() -> None:
    """Le caractère multiplicatif s'applique déjà à l'intérieur du terme d'affinité :
    deux raisons de rejet ne s'additionnent pas, le résultat reste 0,0."""
    profil = ProfilCandidat(type_formation="Licence", domaine="informatique")
    terme = calculer_affinite("BTS", "Comptabilité", "BTS Comptabilité", "75", profil)
    assert terme.valeur == 0.0
    assert terme.filtre_type_formation_respecte is False
    assert terme.filtre_domaine_respecte is False


def test_normaliser_retire_accents_ponctuation_et_espaces_superflus() -> None:
    assert normaliser("  Génie Électrique - Option A  ") == "genie electrique option a"
    assert normaliser(None) == ""
    assert normaliser("") == ""
