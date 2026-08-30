"""Tests unitaires de l'explicabilité (E25) : fonctions pures, sur des données fabriquées.

Le test de contrat (`tests/data/test_models_explain_run.py`) rejoue le
pipeline complet et entraîne réellement un LightGBM sur `data/samples/` ;
ici, seuls le calcul de l'importance globale, la sélection des exemples
locaux, l'écriture du précalcul et l'axiome d'efficacité de SHAP (sur un
modèle jouet, entraîné dans ce fichier) sont vérifiés.
"""

from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from edumatch.models.explain import (
    ContributionVariable,
    ErreurExplicabilite,
    calculer_valeurs_shap,
    choisir_exemples,
    construire_explainer,
    construire_table_precalcul,
    ecrire_precalcul,
    importance_globale,
    part_substituts_genre,
    tracer_importance_globale,
)

# ─── importance_globale ─────────────────────────────────────────────────────


def test_importance_globale_pondere_par_effectif() -> None:
    """Une cellule à effectif 10 doit peser dix fois plus qu'une cellule à effectif 1."""
    valeurs_shap = np.array([[1.0, 0.0], [0.0, 1.0]])
    poids = pd.Series([10.0, 1.0])

    importance = importance_globale(valeurs_shap, poids, ["a", "b"])

    par_nom = {contribution.nom: contribution.importance for contribution in importance}
    assert par_nom["a"] == pytest.approx(10.0 / 11.0)
    assert par_nom["b"] == pytest.approx(1.0 / 11.0)


def test_importance_globale_est_triee_decroissante() -> None:
    valeurs_shap = np.array([[0.1, 0.9], [0.2, 0.8]])
    poids = pd.Series([1.0, 1.0])

    importance = importance_globale(valeurs_shap, poids, ["faible", "forte"])

    assert [c.nom for c in importance] == ["forte", "faible"]


def test_importance_globale_les_parts_somment_a_un() -> None:
    valeurs_shap = np.array([[0.3, 0.5, 0.2], [0.1, 0.1, 0.1]])
    poids = pd.Series([2.0, 3.0])

    importance = importance_globale(valeurs_shap, poids, ["x", "y", "z"])

    assert sum(c.part for c in importance) == pytest.approx(1.0)


def test_importance_globale_leve_si_colonnes_incoherentes() -> None:
    valeurs_shap = np.array([[0.1, 0.2]])
    poids = pd.Series([1.0])
    with pytest.raises(ErreurExplicabilite):
        importance_globale(valeurs_shap, poids, ["une_seule_colonne"])


def test_importance_globale_leve_si_poids_total_nul() -> None:
    valeurs_shap = np.array([[0.1, 0.2]])
    poids = pd.Series([0.0])
    with pytest.raises(ErreurExplicabilite):
        importance_globale(valeurs_shap, poids, ["a", "b"])


# ─── part_substituts_genre ───────────────────────────────────────────────────


def test_part_substituts_genre_retourne_la_part_mesuree() -> None:
    importance = [
        ContributionVariable(nom="fili", importance=0.5, part=0.4),
        ContributionVariable(nom="dep", importance=0.2, part=0.16),
        ContributionVariable(nom="autre_variable", importance=0.6, part=0.44),
    ]
    resultat = part_substituts_genre(importance)
    assert resultat["fili"] == pytest.approx(0.4)
    assert resultat["dep"] == pytest.approx(0.16)


def test_part_substituts_genre_vaut_zero_si_absent_de_limportance() -> None:
    seule_variable = ContributionVariable(nom="autre_variable", importance=1.0, part=1.0)
    resultat = part_substituts_genre([seule_variable])
    assert resultat["fili"] == 0.0
    assert resultat["select_form"] == 0.0
    assert resultat["dep"] == 0.0
    assert resultat["acad_mies"] == 0.0


# ─── tracer_importance_globale ───────────────────────────────────────────────


def test_tracer_importance_globale_ecrit_un_fichier_png(tmp_path: Path) -> None:
    importance = [
        ContributionVariable(nom=f"var_{i}", importance=1.0 / (i + 1), part=0.1) for i in range(5)
    ]
    destination = tmp_path / "figures" / "importance.png"

    chemin = tracer_importance_globale(importance, destination, top_n=3)

    assert chemin == destination
    assert destination.exists()
    assert destination.stat().st_size > 0


# ─── construire_table_precalcul / ecrire_precalcul ──────────────────────────


def _table_deux_cellules() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "session": [2024, 2025],
            "cod_aff_form": ["A1", "A2"],
            "type_bac": ["bg", "bp"],
            "boursier": [False, True],
            "taux": [0.5, 0.2],
            "effectif": [10.0, 20.0],
        }
    )


def test_construire_table_precalcul_produit_une_colonne_shap_par_variable() -> None:
    table = _table_deux_cellules()
    colonnes = ["fili", "dep"]
    valeurs_shap = np.array([[0.1, -0.05], [0.2, 0.03]])
    base = np.array([0.4, 0.4])
    prediction = base + valeurs_shap.sum(axis=1)

    precalcul = construire_table_precalcul(table, colonnes, valeurs_shap, base, prediction)

    assert {"shap__fili", "shap__dep", "prediction", "valeur_base"} <= set(precalcul.columns)
    assert len(precalcul) == 2
    np.testing.assert_allclose(precalcul["shap__fili"].to_numpy(), valeurs_shap[:, 0], rtol=1e-6)


def test_ecrire_precalcul_cree_le_dossier_parent_et_le_fichier(tmp_path: Path) -> None:
    table = _table_deux_cellules()
    valeurs_shap = np.zeros((2, 1))
    base = np.array([0.4, 0.4])
    precalcul = construire_table_precalcul(table, ["fili"], valeurs_shap, base, base)
    destination = tmp_path / "un_dossier_absent" / "explications.parquet"

    chemin = ecrire_precalcul(precalcul, destination)

    assert chemin.exists()
    relu = pd.read_parquet(chemin)
    assert len(relu) == 2


# ─── choisir_exemples ────────────────────────────────────────────────────────


def test_choisir_exemples_respecte_effectif_minimal() -> None:
    """La cellule à effectif 2 a la meilleure prédiction, mais est sous le plancher : ignorée."""
    table = pd.DataFrame(
        {
            "session": [2025, 2025, 2025],
            "cod_aff_form": ["A", "B", "C"],
            "type_bac": ["bg", "bg", "bp"],
            "boursier": [False, False, True],
            "taux": [0.9, 0.5, 0.1],
            "effectif": [2.0, 50.0, 40.0],
            "fili": ["Licence", "BTS", "CPGE"],
        }
    )
    colonnes = ["fili"]
    valeurs_shap = np.array([[0.4], [0.1], [-0.2]])
    base = np.array([0.4, 0.4, 0.4])
    prediction = np.array([0.99, 0.5, 0.1])

    haut, bas = choisir_exemples(
        table, colonnes, valeurs_shap, base, prediction, effectif_minimal=30
    )

    assert haut.cod_aff_form == "B"  # la meilleure prédiction parmi les cellules éligibles
    assert bas.cod_aff_form == "C"


def test_choisir_exemples_leve_si_aucune_cellule_eligible() -> None:
    table = pd.DataFrame(
        {
            "session": [2025],
            "cod_aff_form": ["A"],
            "type_bac": ["bg"],
            "boursier": [False],
            "taux": [0.5],
            "effectif": [5.0],
        }
    )
    valeurs_shap = np.array([[0.1]])
    base = np.array([0.4])
    prediction = np.array([0.5])

    with pytest.raises(ErreurExplicabilite):
        choisir_exemples(table, ["fili"], valeurs_shap, base, prediction, effectif_minimal=30)


def test_exemple_local_resume_est_lisible() -> None:
    table = pd.DataFrame(
        {
            "session": [2025, 2025],
            "cod_aff_form": ["A", "B"],
            "type_bac": ["bg", "bp"],
            "boursier": [False, True],
            "taux": [0.9, 0.1],
            "effectif": [50.0, 40.0],
            "fili": ["Licence", "BTS"],
        }
    )
    colonnes = ["fili"]
    valeurs_shap = np.array([[0.4], [-0.2]])
    base = np.array([0.4, 0.4])
    prediction = np.array([0.8, 0.2])

    haut, _ = choisir_exemples(table, colonnes, valeurs_shap, base, prediction, effectif_minimal=1)
    texte = haut.resume()

    assert "A" in texte
    assert "fili" in texte
    assert "0.800" in texte  # la prédiction


# ─── calculer_valeurs_shap : l'axiome d'efficacité de Shapley ───────────────


def test_shap_verifie_laxiome_defficacite() -> None:
    """prédiction == valeur de base + somme des contributions, sur un LightGBM réel entraîné ici.

    C'est l'axiome d'efficacité des valeurs de Shapley : la somme des
    contributions doit exactement combler l'écart entre la prédiction et la
    valeur de base. TreeSHAP le garantit exactement (contrairement à une
    approximation comme KernelSHAP) — ce test le vérifie à la précision
    flottante près, sur un modèle jouet plutôt que le modèle réel (E22),
    pour rester rapide et indépendant de `data/samples/`.
    """
    rng = np.random.default_rng(42)
    n = 200
    X = pd.DataFrame(
        {
            "x1": rng.uniform(0, 1, n),
            "x2": rng.uniform(0, 1, n),
            "x3": rng.integers(0, 5, n),
        }
    )
    y = 0.6 * X["x1"] - 0.3 * X["x2"] + 0.02 * X["x3"] + rng.normal(0, 0.01, n)
    modele = lgb.LGBMRegressor(
        n_estimators=30, num_leaves=7, min_child_samples=5, verbose=-1, random_state=42
    )
    modele.fit(X, y)

    explainer = construire_explainer(modele)
    valeurs_shap, base = calculer_valeurs_shap(explainer, X)
    prediction_attendue = modele.predict(X)

    reconstruite = base + valeurs_shap.sum(axis=1)
    np.testing.assert_allclose(reconstruite, prediction_attendue, atol=1e-6)


def test_calculer_valeurs_shap_a_la_bonne_forme() -> None:
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"a": rng.uniform(size=50), "b": rng.uniform(size=50)})
    y = X["a"] + rng.normal(0, 0.01, 50)
    modele = lgb.LGBMRegressor(n_estimators=10, num_leaves=3, min_child_samples=5, verbose=-1)
    modele.fit(X, y)

    explainer = construire_explainer(modele)
    valeurs_shap, base = calculer_valeurs_shap(explainer, X)

    assert valeurs_shap.shape == (50, 2)
    assert base.shape == (50,)
