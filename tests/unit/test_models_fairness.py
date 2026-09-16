"""Tests unitaires de l'audit d'équité (E26) : fonctions pures, sur des tables fabriquées.

Pas besoin de `data/samples/` ici — contrairement au test de contrat
(`tests/data/test_models_fairness_run.py`) qui rejoue le pipeline complet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edumatch.models.fairness import (
    CATEGORIE_GENRE_INDETERMINEE,
    CATEGORIE_GENRE_MAJORITAIRE,
    CATEGORIE_GENRE_MINORITAIRE,
    CATEGORIE_GENRE_MIXTE,
    ErreurAuditEquite,
    VentilationGroupe,
    calculer_correlations_substituts,
    classer_composition_genre,
    eta_carre,
    ratio_impact_disparate_dimension,
    ventiler_dimension,
)

# ─── classer_composition_genre ──────────────────────────────────────────────


def test_classe_moins_de_20_pct_en_minoritaire() -> None:
    resultat = classer_composition_genre(pd.Series([0.05, 0.19]))
    assert (resultat == CATEGORIE_GENRE_MINORITAIRE).all()


def test_classe_bornes_incluses_dans_mixte() -> None:
    resultat = classer_composition_genre(pd.Series([0.20, 0.50, 0.80]))
    assert (resultat == CATEGORIE_GENRE_MIXTE).all()


def test_classe_plus_de_80_pct_en_majoritaire() -> None:
    resultat = classer_composition_genre(pd.Series([0.81, 0.99]))
    assert (resultat == CATEGORIE_GENRE_MAJORITAIRE).all()


def test_denominateur_nul_est_indetermine_jamais_minoritaire() -> None:
    """Le piège déjà rencontré : une formation sans vœu n'est pas « peu féminisée », elle est indéterminée."""
    resultat = classer_composition_genre(pd.Series([np.nan]))
    assert resultat.iloc[0] == CATEGORIE_GENRE_INDETERMINEE
    assert resultat.iloc[0] != CATEGORIE_GENRE_MINORITAIRE


# ─── eta_carre ───────────────────────────────────────────────────────────────


def test_eta_carre_nul_si_le_groupe_n_explique_rien() -> None:
    valeur = pd.Series([0.5, 0.5, 0.5, 0.5])
    groupe = pd.Series(["a", "a", "b", "b"])
    assert eta_carre(valeur, groupe) == pytest.approx(0.0)


def test_eta_carre_maximal_si_le_groupe_determine_totalement_la_valeur() -> None:
    valeur = pd.Series([0.0, 0.0, 1.0, 1.0])
    groupe = pd.Series(["a", "a", "b", "b"])
    assert eta_carre(valeur, groupe) == pytest.approx(1.0)


def test_eta_carre_ignore_les_valeurs_manquantes() -> None:
    valeur = pd.Series([0.0, 0.0, 1.0, 1.0, np.nan])
    groupe = pd.Series(["a", "a", "b", "b", "c"])
    assert eta_carre(valeur, groupe) == pytest.approx(1.0)


def test_calculer_correlations_substituts_retourne_une_valeur_par_colonne() -> None:
    table = pd.DataFrame(
        {
            "cod_aff_form": ["1", "1", "2", "2"],
            "composition_candidate": [0.9, 0.9, 0.1, 0.1],
            "fili": ["lettres", "lettres", "info", "info"],
        }
    )
    resultat = calculer_correlations_substituts(table, colonnes=("fili",))
    assert resultat["fili"] == pytest.approx(1.0)


# ─── ventiler_dimension ──────────────────────────────────────────────────────


def _table_minimale() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "groupe": ["a"] * 5 + ["b"] * 5,
            "effectif": [10.0] * 10,
            "taux_observe": [0.5] * 10,
            "prediction_modele": [0.5] * 5 + [0.9] * 5,
            "prediction_baseline": [0.5] * 10,
        }
    )


def test_ventiler_dimension_calcule_une_mae_nulle_quand_la_prediction_est_exacte() -> None:
    table = _table_minimale()
    resultats = ventiler_dimension(table, "groupe", "test", n_tranches=10)
    groupe_a = next(v for v in resultats if v.groupe == "a")
    assert groupe_a.mae_ponderee_modele == pytest.approx(0.0)


def test_ventiler_dimension_detecte_le_biais_du_groupe_b() -> None:
    table = _table_minimale()
    resultats = ventiler_dimension(table, "groupe", "test", n_tranches=10)
    groupe_b = next(v for v in resultats if v.groupe == "b")
    assert groupe_b.mae_ponderee_modele == pytest.approx(0.4)


def test_ventiler_dimension_marque_non_fiable_sous_le_seuil() -> None:
    table = _table_minimale()
    resultats = ventiler_dimension(table, "groupe", "test", n_tranches=10)
    assert all(not v.fiable for v in resultats)  # 5 cellules < N_CELLULES_MIN_FIABLE (30)


def test_ventiler_dimension_taux_de_selection_pondere_par_effectif() -> None:
    table = pd.DataFrame(
        {
            "groupe": ["a", "a"],
            "effectif": [90.0, 10.0],
            "taux_observe": [0.6, 0.6],
            "prediction_modele": [0.6, 0.1],  # seule la cellule à 10 de poids est sous le seuil de 0,5
            "prediction_baseline": [0.6, 0.6],
        }
    )
    resultats = ventiler_dimension(table, "groupe", "test", n_tranches=10)
    assert resultats[0].taux_selection_modele == pytest.approx(0.9)


# ─── ratio_impact_disparate_dimension ───────────────────────────────────────


def _ventilation(groupe: str, taux_selection: float, n_cellules: int = 100) -> VentilationGroupe:
    return VentilationGroupe(
        dimension="test",
        groupe=groupe,
        n_cellules=n_cellules,
        effectif_total=1000.0,
        fiable=n_cellules >= 30,
        mae_ponderee_modele=0.0,
        mae_non_ponderee_modele=0.0,
        mae_ponderee_baseline=0.0,
        ece_modele=0.0,
        ece_baseline=0.0,
        taux_selection_modele=taux_selection,
        taux_selection_baseline=taux_selection,
    )


def test_ratio_impact_disparate_du_groupe_de_reference_vaut_un() -> None:
    ventilations = [_ventilation("a", 0.50), _ventilation("b", 0.25)]
    ratio = ratio_impact_disparate_dimension(ventilations, "test", seuil=0.80)
    assert ratio.ratios_modele["a"] == pytest.approx(1.0)
    assert ratio.ratios_modele["b"] == pytest.approx(0.5)


def test_ratio_impact_disparate_detecte_le_passage_sous_le_seuil() -> None:
    ventilations = [_ventilation("a", 0.50), _ventilation("b", 0.30)]
    ratio = ratio_impact_disparate_dimension(ventilations, "test", seuil=0.80)
    assert ratio.groupes_sous_le_seuil_modele() == ["b"]


def test_ratio_impact_disparate_exclut_les_groupes_a_effectif_insuffisant() -> None:
    ventilations = [_ventilation("a", 0.50), _ventilation("b", 0.10, n_cellules=5)]
    ratio = ratio_impact_disparate_dimension(ventilations, "test", seuil=0.80)
    assert "b" not in ratio.ratios_modele
    assert ratio.groupes_exclus_effectif_insuffisant == ("b",)


def test_ratio_impact_disparate_leve_si_aucun_groupe_fiable() -> None:
    ventilations = [_ventilation("a", 0.50, n_cellules=5)]
    with pytest.raises(ErreurAuditEquite):
        ratio_impact_disparate_dimension(ventilations, "test", seuil=0.80)
