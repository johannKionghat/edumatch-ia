"""Tests du score à trois termes (src/edumatch/matching/score.py).

`recommander` est testée avec un `ArtefactsDebouches` construit à la main
(mêmes petites tables que `test_matching_debouches.py`), pas les fichiers
réels : c'est le caractère multiplicatif et l'assemblage des trois termes
qui sont vérifiés ici, pas la construction de chacun des termes (déjà
couverte séparément).
"""

from __future__ import annotations

import pandas as pd
import polars as pl
import pytest

from edumatch.config import Settings, get_settings
from edumatch.matching.affinite import ProfilCandidat, TermeAffinite
from edumatch.matching.debouches import (
    STATUT_MESURE,
    ArtefactsDebouches,
    RapportCorrespondanceFormation,
    RapportKAnonymat,
    TermeDebouches,
)
from edumatch.matching.score import (
    MISE_EN_GARDE_ACCESSIBILITE,
    ErreurScore,
    borner_accessibilite,
    calculer_score,
    recommander,
)

# ─── borner_accessibilite ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [(0.5, 0.5), (-0.1, 0.0), (1.3, 1.0), (0.0, 0.0), (1.0, 1.0)],
)
def test_borner_accessibilite(brut: float, attendu: float) -> None:
    assert borner_accessibilite(brut) == pytest.approx(attendu)


# ─── calculer_score : le produit, et le terme nul ──────────────────────────


def _terme_affinite(valeur: float) -> TermeAffinite:
    return TermeAffinite(valeur=valeur, filtre_type_formation_respecte=True, filtre_domaine_respecte=True, territoire_correspond=None)


def _terme_debouches(valeur: float, disponible: bool = True) -> TermeDebouches:
    return TermeDebouches(valeur=valeur, disponible=disponible, statut=STATUT_MESURE)


def test_le_score_est_le_produit_exact_des_trois_termes() -> None:
    resultat = calculer_score(_terme_affinite(0.8), 0.5, _terme_debouches(0.4), "cellule-1")
    assert resultat.score == pytest.approx(0.8 * 0.5 * 0.4)
    assert resultat.accessibilite == pytest.approx(0.5)


@pytest.mark.parametrize(
    "affinite_valeur, accessibilite, debouches_valeur",
    [(0.0, 0.9, 0.9), (0.9, 0.0, 0.9), (0.9, 0.9, 0.0)],
)
def test_un_terme_nul_supprime_le_score(affinite_valeur: float, accessibilite: float, debouches_valeur: float) -> None:
    """Le critère de validation de l'E28 : un terme nul, quel qu'il soit, ramène le score à 0."""
    resultat = calculer_score(
        _terme_affinite(affinite_valeur), accessibilite, _terme_debouches(debouches_valeur), "cellule-1"
    )
    assert resultat.score == 0.0


def test_trois_termes_moyens_donnent_un_score_bien_plus_bas_que_la_moyenne() -> None:
    """Effet de bord assumé du produit : 0,5 x 0,5 x 0,5 = 0,125, pas 0,5 — voir le docstring
    du module pour la façon dont ce terme doit être présenté (les trois termes toujours visibles
    à côté du score, jamais le score seul)."""
    resultat = calculer_score(_terme_affinite(0.5), 0.5, _terme_debouches(0.5), "cellule-1")
    assert resultat.score == pytest.approx(0.125)
    assert resultat.score < 0.5


def test_accessibilite_hors_bornes_est_ecretee_dans_le_score() -> None:
    resultat = calculer_score(_terme_affinite(1.0), 1.4, _terme_debouches(1.0), "cellule-1")
    assert resultat.accessibilite == 1.0
    assert resultat.accessibilite_brute == pytest.approx(1.4)
    assert resultat.score == 1.0


def test_la_mise_en_garde_accessibilite_est_toujours_presente() -> None:
    resultat = calculer_score(_terme_affinite(1.0), 0.5, _terme_debouches(1.0), "cellule-1")
    assert resultat.mise_en_garde_accessibilite == MISE_EN_GARDE_ACCESSIBILITE
    assert "0,0758" in resultat.mise_en_garde_accessibilite
    assert "0,0701" in resultat.mise_en_garde_accessibilite


# ─── recommander : assemblage sur un petit catalogue ───────────────────────


@pytest.fixture()
def settings() -> Settings:
    return get_settings()


@pytest.fixture()
def artefacts_debouches() -> ArtefactsDebouches:
    correspondance = pl.DataFrame({"fil_lib_voe_acc": ["BTS SIO"], "code_rncp_ideo": ["RNCP001"]})
    table_naf = pl.DataFrame({"code_rncp_ideo": ["RNCP001"], "naf_division": ["62"]})
    agregat = pl.DataFrame(
        {"departement": ["75"], "naf_division": ["62"], "nb_actifs_employeurs_diffusibles": [25]}
    )
    cellules_non_vides = agregat.select("departement", "naf_division")
    rapport_k = RapportKAnonymat("departement x division_naf", 5, 1, 0, 25, 0)
    rapport_corr = RapportCorrespondanceFormation(1, 1, 1, 1, [("BTS SIO", "RNCP001")])
    return ArtefactsDebouches(
        correspondance_formation=correspondance,
        table_naf_rome_formation=table_naf,
        agregat_conserve=agregat,
        cellules_non_vides=cellules_non_vides,
        rapport_k_anonymat=rapport_k,
        rapport_correspondance=rapport_corr,
    )


@pytest.fixture()
def catalogue() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cod_aff_form": "F1",
                "fili": "BTS",
                "fil_lib_voe_acc": "BTS SIO",
                "form_lib_voe_acc": "BTS Services informatiques aux organisations",
                "dep": "75",
                "taux_predit": 0.6,
            },
            {
                "cod_aff_form": "F2",
                "fili": "Licence",  # ne correspond pas au type_formation demandé -> affinité nulle
                "fil_lib_voe_acc": "Mathématiques",
                "form_lib_voe_acc": "Licence Mathématiques",
                "dep": "75",
                "taux_predit": 0.95,
            },
            {
                "cod_aff_form": "F3",
                "fili": "BTS",
                "fil_lib_voe_acc": "Libellé jamais apparié",  # chaîne rompue -> débouchés neutre
                "form_lib_voe_acc": "BTS Autre chose",
                "dep": "75",
                "taux_predit": 0.3,
            },
        ]
    )


def test_recommander_ordonne_par_score_decroissant(
    catalogue: pd.DataFrame, artefacts_debouches: ArtefactsDebouches, settings: Settings
) -> None:
    # Le candidat n'exprime pas de préférence territoriale : le terme de débouchés est donc
    # indisponible (neutre, 1,0) pour les trois formations — seuls affinité et accessibilité
    # discriminent ici, le terme de débouchés étant testé isolément dans
    # `test_matching_debouches.py`.
    profil = ProfilCandidat(type_formation="BTS")
    resultats = recommander(catalogue, profil, artefacts_debouches, settings, top_n=10)

    identifiants = [r.identifiant_cellule for r in resultats]
    scores = {r.identifiant_cellule: r.score for r in resultats}
    # F2 (Licence) est exclue par le filtre dur du type de formation : affinité nulle -> score nul.
    assert scores["F2"] == 0.0
    # F1 (accessibilité 0,6) devance F3 (accessibilité 0,3), toutes choses égales par ailleurs.
    assert scores["F1"] == pytest.approx(0.6)
    assert scores["F3"] == pytest.approx(0.3)
    assert identifiants == ["F1", "F3", "F2"]


def test_recommander_respecte_top_n(
    catalogue: pd.DataFrame, artefacts_debouches: ArtefactsDebouches, settings: Settings
) -> None:
    resultats = recommander(catalogue, ProfilCandidat(), artefacts_debouches, settings, top_n=1)
    assert len(resultats) == 1


def test_recommander_leve_une_erreur_si_une_colonne_requise_manque(
    artefacts_debouches: ArtefactsDebouches, settings: Settings
) -> None:
    catalogue_incomplet = pd.DataFrame([{"cod_aff_form": "F1", "fili": "BTS"}])
    with pytest.raises(ErreurScore):
        recommander(catalogue_incomplet, ProfilCandidat(), artefacts_debouches, settings)
