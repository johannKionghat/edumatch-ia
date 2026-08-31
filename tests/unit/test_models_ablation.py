"""Tests unitaires de `models.ablation` (E27) : logique pure, sans entraînement ni disque.

Complète `tests/data/test_models_ablation_run.py`, qui couvre le protocole de
bout en bout sur les échantillons — coûteux à répéter, donc réservé aux
garanties qui exigent réellement un entraînement.
"""

from __future__ import annotations

import numpy as np
import pytest

from edumatch.config import VariablesConfig
from edumatch.models import ablation
from edumatch.models.metrics import ScoreSession


def _variables(**overrides: object) -> VariablesConfig:
    base = {
        "cles": ["session", "cod_aff_form"],
        "dimensions_cellule": ["type_bac", "boursier"],
        "session_courante": ["fili", "dep"],
        "decalees": ["voe_tot", "capa_fin"],
        "decalees_sous_reserve": ["acc_tb"],
        "exclues": {"pct_f": "interdite", "cod_uai": "substitut"},
    }
    base.update(overrides)
    return VariablesConfig(**base)


# ─── _variables_avec_cod_uai ─────────────────────────────────────────────────


def test_variables_avec_cod_uai_deplace_cod_uai_vers_decalees() -> None:
    variables = _variables()
    variante = ablation._variables_avec_cod_uai(variables)

    assert "cod_uai" in variante.decalees
    assert "cod_uai" not in variante.exclues
    assert "cod_uai" not in variables.decalees  # l'original n'est jamais modifié (frozen)


def test_variables_avec_cod_uai_preserve_les_autres_exclusions() -> None:
    variables = _variables()
    variante = ablation._variables_avec_cod_uai(variables)

    assert variante.exclues == {"pct_f": "interdite"}
    assert variante.decalees == ["voe_tot", "capa_fin", "cod_uai"]
    assert variante.session_courante == variables.session_courante
    assert variante.dimensions_cellule == variables.dimensions_cellule


def test_variables_avec_cod_uai_leve_si_deja_reclasse() -> None:
    variables = _variables(exclues={"pct_f": "interdite"})  # cod_uai déjà absent des exclues
    with pytest.raises(ablation.ErreurAblation, match="cod_uai"):
        ablation._variables_avec_cod_uai(variables)


# ─── _resultat_variante ──────────────────────────────────────────────────────


def _entrainement(mae: float, ece: float) -> ablation._EntrainementVariante:
    score = ScoreSession(perimetre="validation", n_cellules=100, mae_ponderee=mae, mae_non_ponderee=mae)
    return ablation._EntrainementVariante(
        modele=None, jeu_validation=None, prediction_validation=np.array([]), score_validation=score, ece_validation=ece
    )


def test_resultat_variante_calcule_l_ecart_signe() -> None:
    resultat = ablation._resultat_variante(
        "ma_variante", "description", ["a", "b", "c"], _entrainement(mae=0.08, ece=0.02), mae_reference=0.075,
        commentaire="commentaire",
    )
    assert resultat.n_variables == 3
    assert resultat.mae_validation == pytest.approx(0.08)
    assert resultat.ecart_mae_vs_complet == pytest.approx(0.005)
    assert resultat.ece_validation == pytest.approx(0.02)


def test_resultat_variante_ecart_nul_est_rapporte_tel_quel() -> None:
    """Un écart nul n'est ni masqué ni arrondi à un signe arbitraire : il vaut exactement 0."""
    resultat = ablation._resultat_variante(
        "identique", "description", ["a"], _entrainement(mae=0.075, ece=0.01), mae_reference=0.075,
        commentaire="aucun écart mesuré",
    )
    assert resultat.ecart_mae_vs_complet == 0.0


def test_resume_variante_cite_le_nom_et_le_commentaire() -> None:
    resultat = ablation._resultat_variante(
        "ma_variante", "une description", ["a", "b"], _entrainement(mae=0.08, ece=0.02), mae_reference=0.08,
        commentaire="un commentaire précis",
    )
    texte = resultat.resume()
    assert "ma_variante" in texte
    assert "une description" in texte
    assert "un commentaire précis" in texte


# ─── Déclaration Sirene ──────────────────────────────────────────────────────


def test_declaration_sirene_ne_pretend_pas_a_un_ecart_nul() -> None:
    """Contrainte du projet : Sirene n'est pas mesurée à zéro, elle est déclarée hors de portée."""
    assert "impossible" in ablation.DECLARATION_SIRENE.lower()
    assert "pas nulle" in ablation.DECLARATION_SIRENE.lower()
