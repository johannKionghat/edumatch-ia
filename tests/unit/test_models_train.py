"""Tests unitaires de l'entraînement (E22) : fonctions pures, sur des tables fabriquées.

Pas besoin de `data/samples/` ici — contrairement au test de contrat
(`tests/data/test_models_train_run.py`) qui rejoue le pipeline complet et
entraîne réellement un LightGBM. `numpy`/`pandas` seuls suffisent à vérifier
la préparation des données et la défense anti-fuite ; l'entraînement
lui-même appartient au test de contrat.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edumatch.config import VariablesConfig
from edumatch.models import train as train_module
from edumatch.models.jeux import preparer_matrice
from edumatch.models.train import (
    COLONNE_A_ANTECEDENT,
    COLONNE_TAUX_PRECEDENT,
    COLONNES_DERIVEES,
    COLONNES_NON_FEATURES,
    ErreurEntrainement,
    JeuDonnees,
    ajouter_taux_precedent,
    classement_importance,
    colonnes_features,
    evaluer_sur_perimetre,
    score_baseline_couverture_egale,
)

# ─── colonnes_features : la défense anti-fuite de ce module ────────────────


def _variables_minimales() -> VariablesConfig:
    return VariablesConfig(
        cles=["session", "cod_aff_form"],
        dimensions_cellule=["type_bac", "boursier"],
        session_courante=["fili", "dep"],
        decalees=["voe_tot", "prop_tot_bg"],
        decalees_sous_reserve=["acc_tb"],
        exclues={"cod_uai": "substitut"},
    )


def test_colonnes_features_retient_la_liste_blanche() -> None:
    variables = _variables_minimales()
    colonnes_table = [*COLONNES_NON_FEATURES, "type_bac", "boursier", "fili", "dep", "voe_tot", "prop_tot_bg"]
    features = colonnes_features(variables, colonnes_table)
    assert set(features) == {"type_bac", "boursier", "fili", "dep", "voe_tot", "prop_tot_bg"}


def test_colonnes_features_exclut_les_colonnes_non_features_connues() -> None:
    variables = _variables_minimales()
    colonnes_table = [*COLONNES_NON_FEATURES, "type_bac"]
    features = colonnes_features(variables, colonnes_table)
    assert set(COLONNES_NON_FEATURES).isdisjoint(features)


def test_colonnes_features_leve_sur_une_colonne_inconnue() -> None:
    """Une colonne « genre » qui se glisserait dans la table doit bloquer l'entraînement, pas passer inaperçue."""
    variables = _variables_minimales()
    colonnes_table = [*COLONNES_NON_FEATURES, "type_bac", "genre"]
    with pytest.raises(ErreurEntrainement, match="genre"):
        colonnes_features(variables, colonnes_table)


def test_colonnes_features_admet_les_variables_de_mention_sous_reserve() -> None:
    variables = _variables_minimales()
    colonnes_table = [*COLONNES_NON_FEATURES, "type_bac", "boursier", "acc_tb"]
    features = colonnes_features(variables, colonnes_table)
    assert "acc_tb" in features


# ─── preparer_matrice : conversion des types nullables Pandas ──────────────


def test_preparer_matrice_convertit_int64_nullable_en_float64_avec_na() -> None:
    table = pd.DataFrame({"voe_tot": pd.array([10, None, 30], dtype="Int64")})
    matrice = preparer_matrice(table, ["voe_tot"])
    assert matrice["voe_tot"].dtype == np.dtype("float64")
    assert np.isnan(matrice["voe_tot"].iloc[1])


def test_preparer_matrice_convertit_les_chaines_en_categorie() -> None:
    table = pd.DataFrame({"fili": pd.array(["LICENCE", "BTS"], dtype="string")})
    matrice = preparer_matrice(table, ["fili"])
    assert str(matrice["fili"].dtype) == "category"


def test_preparer_matrice_convertit_les_booleens_en_categorie() -> None:
    table = pd.DataFrame({"boursier": pd.array([True, False], dtype="boolean")})
    matrice = preparer_matrice(table, ["boursier"])
    assert str(matrice["boursier"].dtype) == "category"


def test_preparer_matrice_ne_touche_pas_aux_colonnes_hors_liste() -> None:
    table = pd.DataFrame({"voe_tot": pd.array([10], dtype="Int64"), "taux": [0.5]})
    matrice = preparer_matrice(table, ["voe_tot"])
    assert list(matrice.columns) == ["voe_tot"]


# ─── evaluer_sur_perimetre ──────────────────────────────────────────────────


def test_evaluer_sur_perimetre_calcule_les_deux_mae() -> None:
    jeu = JeuDonnees(
        X=pd.DataFrame({"a": [1, 2]}),
        y=pd.Series([0.2, 0.8]),
        poids=pd.Series([1.0, 9.0]),
        sessions=pd.Series([2024, 2024]),
    )
    score = evaluer_sur_perimetre(jeu, np.array([0.2, 0.6]), "2024")
    assert score.n_cellules == 2
    assert score.mae_non_ponderee == pytest.approx((0.0 + 0.2) / 2)
    assert score.mae_ponderee == pytest.approx((0.0 * 1.0 + 0.2 * 9.0) / 10.0)


# ─── ajouter_taux_precedent : le taux précédent comme variable, sans fuite ──
#
# Le test le plus important n'est pas celui qui vérifie la valeur dans le cas
# normal — c'est `test_ajouter_taux_precedent_recalcule_le_quotient_jamais_ne_lit_le_label`,
# qui construit délibérément un `taux` (le label de la session N) très
# différent du quotient attendu : si le code lisait ce label au lieu de
# recalculer depuis les colonnes décalées `prop_tot_bg` / `nb_voe_pp_bg`, ce
# test échouerait, et lui seul — la fuite serait par ailleurs invisible sur
# une table où les deux valeurs coïncideraient par hasard. Vérifié par
# mutation : remplacer le corps de `ajouter_taux_precedent` par
# `table[COLONNE_TAUX_PRECEDENT] = table["taux"]` fait échouer ce test, et
# aucun autre.


def _table_pour_taux_precedent(**colonnes: object) -> pd.DataFrame:
    """Une ligne minimale portant toutes les colonnes que `predire_session_precedente` lit."""
    n = len(next(iter(colonnes.values())))
    base: dict[str, list] = {}
    for cat in ("bg", "bg_brs", "bt", "bt_brs", "bp", "bp_brs"):
        base[f"prop_tot_{cat}"] = [np.nan] * n
        base[f"nb_voe_pp_{cat}"] = [np.nan] * n
    base.update(colonnes)
    return pd.DataFrame(base)


def test_ajouter_taux_precedent_recalcule_le_quotient_jamais_ne_lit_le_label() -> None:
    table = _table_pour_taux_precedent(
        type_bac=["bg"],
        boursier=[False],
        prop_tot_bg=[30],
        nb_voe_pp_bg=[100],
        taux=[0.999],  # le label de la session N : ne doit jamais être lu ici
    )
    resultat = ajouter_taux_precedent(table)
    assert resultat[COLONNE_TAUX_PRECEDENT].iloc[0] == pytest.approx(0.3)
    assert bool(resultat[COLONNE_A_ANTECEDENT].iloc[0]) is True


def test_ajouter_taux_precedent_reutilise_la_fonction_de_la_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Une seule formule pour la baseline (E21) et la variable (E22), jamais deux implémentations."""
    appels: list[pd.DataFrame] = []

    def _espion(table: pd.DataFrame) -> pd.Series:
        appels.append(table)
        return pd.Series([0.42], index=table.index)

    monkeypatch.setattr(train_module, "predire_session_precedente", _espion)
    table = _table_pour_taux_precedent(type_bac=["bg"], boursier=[False])

    resultat = train_module.ajouter_taux_precedent(table)

    assert len(appels) == 1
    assert resultat[COLONNE_TAUX_PRECEDENT].iloc[0] == pytest.approx(0.42)


def test_absence_d_antecedent_ne_comble_rien() -> None:
    """Une formation sans antécédent reste sans prédiction : jamais une valeur inventée."""
    table = _table_pour_taux_precedent(type_bac=["bp"], boursier=[True])
    resultat = ajouter_taux_precedent(table)
    assert pd.isna(resultat[COLONNE_TAUX_PRECEDENT].iloc[0])
    assert bool(resultat[COLONNE_A_ANTECEDENT].iloc[0]) is False


def test_colonnes_features_admet_les_variables_derivees_du_taux_precedent() -> None:
    variables = _variables_minimales()
    colonnes_table = [*COLONNES_NON_FEATURES, "type_bac", "boursier", *COLONNES_DERIVEES]
    features = colonnes_features(variables, colonnes_table)
    assert set(COLONNES_DERIVEES) <= set(features)


# ─── score_baseline_couverture_egale ────────────────────────────────────────


def test_score_baseline_couverture_egale_comble_par_la_moyenne_de_groupe() -> None:
    """100 % de couverture : la cellule sans antécédent est comblée par le repli, pas ignorée."""
    table = pd.DataFrame(
        {
            "session": [2024, 2024],
            "effectif": [10, 20],
            "taux": [0.5, 0.2],
            COLONNE_TAUX_PRECEDENT: [0.4, np.nan],
        }
    )
    moyenne_groupe = pd.Series([0.0, 0.3], index=table.index)

    score = score_baseline_couverture_egale(table, COLONNE_TAUX_PRECEDENT, moyenne_groupe, [2024], "validation")

    assert score.n_cellules == 2
    assert score.mae_ponderee == pytest.approx((0.1 * 10 + 0.1 * 20) / 30)
    assert score.mae_non_ponderee == pytest.approx(0.1)


def test_score_baseline_couverture_egale_filtre_par_session() -> None:
    table = pd.DataFrame(
        {
            "session": [2024, 2025],
            "effectif": [10, 10],
            "taux": [0.5, 999.0],  # 2025 ne doit jamais entrer dans le score de 2024
            COLONNE_TAUX_PRECEDENT: [0.5, 0.0],
        }
    )
    moyenne_groupe = pd.Series([0.0, 0.0], index=table.index)

    score = score_baseline_couverture_egale(table, COLONNE_TAUX_PRECEDENT, moyenne_groupe, [2024], "validation")

    assert score.n_cellules == 1
    assert score.mae_ponderee == pytest.approx(0.0)


# ─── classement_importance ───────────────────────────────────────────────────


class _BoosterFactice:
    def feature_importance(self, importance_type: str) -> np.ndarray:
        assert importance_type == "gain"
        return np.array([5.0, 20.0, 1.0])


class _ModeleFactice:
    def __init__(self) -> None:
        self.booster_ = _BoosterFactice()


def test_classement_importance_trie_par_gain_decroissant() -> None:
    classement = classement_importance(_ModeleFactice(), ["a", "b", "c"])
    assert classement == [("b", 20.0), ("a", 5.0), ("c", 1.0)]
