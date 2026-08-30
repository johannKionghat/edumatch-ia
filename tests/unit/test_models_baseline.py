"""Tests unitaires de la baseline (E21) : fonctions pures, sur des tables fabriquées.

Pas besoin de `data/samples/` ici — contrairement au test de contrat
(`tests/data/test_models_baseline_run.py`) qui rejoue le pipeline complet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edumatch.models.baseline import (
    ErreurBaseline,
    _score_sur_sous_ensemble,
    predire_moyenne_expansive,
    predire_session_precedente,
)

# ─── predire_session_precedente ─────────────────────────────────────────────


def _table_minimale(**colonnes: list) -> pd.DataFrame:
    base = {
        "prop_tot_bg": [np.nan] * len(next(iter(colonnes.values()))),
        "nb_voe_pp_bg": [np.nan] * len(next(iter(colonnes.values()))),
        "prop_tot_bg_brs": [np.nan] * len(next(iter(colonnes.values()))),
        "nb_voe_pp_bg_brs": [np.nan] * len(next(iter(colonnes.values()))),
        "prop_tot_bt": [np.nan] * len(next(iter(colonnes.values()))),
        "nb_voe_pp_bt": [np.nan] * len(next(iter(colonnes.values()))),
        "prop_tot_bt_brs": [np.nan] * len(next(iter(colonnes.values()))),
        "nb_voe_pp_bt_brs": [np.nan] * len(next(iter(colonnes.values()))),
        "prop_tot_bp": [np.nan] * len(next(iter(colonnes.values()))),
        "nb_voe_pp_bp": [np.nan] * len(next(iter(colonnes.values()))),
        "prop_tot_bp_brs": [np.nan] * len(next(iter(colonnes.values()))),
        "nb_voe_pp_bp_brs": [np.nan] * len(next(iter(colonnes.values()))),
    }
    base.update(colonnes)
    return pd.DataFrame(base)


def test_predit_le_taux_de_la_categorie_bg_non_boursier() -> None:
    table = _table_minimale(
        type_bac=["bg"], boursier=[False], prop_tot_bg=[30], nb_voe_pp_bg=[100]
    )
    prediction = predire_session_precedente(table)
    assert prediction.iloc[0] == pytest.approx(0.3)


def test_predit_le_taux_de_la_categorie_bt_boursier() -> None:
    table = _table_minimale(
        type_bac=["bt"], boursier=[True], prop_tot_bt_brs=[40], nb_voe_pp_bt_brs=[80]
    )
    prediction = predire_session_precedente(table)
    assert prediction.iloc[0] == pytest.approx(0.5)


def test_categorie_bg_non_boursier_ne_lit_jamais_la_colonne_boursiere() -> None:
    """Un candidat non boursier ne doit jamais recevoir le taux de la cellule boursière."""
    table = _table_minimale(
        type_bac=["bg"], boursier=[False], prop_tot_bg=[10], nb_voe_pp_bg=[100],
        prop_tot_bg_brs=[99], nb_voe_pp_bg_brs=[100],
    )
    prediction = predire_session_precedente(table)
    assert prediction.iloc[0] == pytest.approx(0.1)


def test_absence_d_antecedent_produit_une_prediction_manquante() -> None:
    table = _table_minimale(type_bac=["bp"], boursier=[True])
    prediction = predire_session_precedente(table)
    assert pd.isna(prediction.iloc[0])


def test_denominateur_nul_est_borne_a_un_comme_le_label() -> None:
    """Cohérence avec `features.label.calculer_taux` : n/0 est borné, pas une erreur."""
    table = _table_minimale(type_bac=["bg"], boursier=[False], prop_tot_bg=[5], nb_voe_pp_bg=[0])
    prediction = predire_session_precedente(table)
    assert prediction.iloc[0] == 1.0


def test_colonne_decalee_manquante_leve_une_erreur_explicite() -> None:
    table = pd.DataFrame({"type_bac": ["bg"], "boursier": [False]})
    with pytest.raises(ErreurBaseline, match="prop_tot_bg"):
        predire_session_precedente(table)


# ─── predire_moyenne_expansive ──────────────────────────────────────────────


def test_moyenne_expansive_ignore_la_session_cible_et_le_futur() -> None:
    """La moyenne de la session 2022 ne doit dépendre que de 2020 et 2021, jamais de 2022."""
    table = pd.DataFrame(
        {
            "session": [2020, 2021, 2022],
            "type_bac": ["bg", "bg", "bg"],
            "boursier": [False, False, False],
            "taux": [0.2, 0.4, 999.0],  # une valeur aberrante en 2022 ne doit rien changer
            "effectif": [10, 10, 10],
        }
    )
    prediction = predire_moyenne_expansive(table, ("type_bac", "boursier"))
    assert prediction.iloc[2] == pytest.approx(0.3)  # moyenne pondérée de 0.2 et 0.4


def test_premiere_session_de_la_table_n_a_aucune_prediction() -> None:
    """Aucune session antérieure : aucune moyenne calculable, quelle que soit la fenêtre."""
    table = pd.DataFrame(
        {
            "session": [2020, 2020],
            "type_bac": ["bg", "bt"],
            "boursier": [False, False],
            "taux": [0.5, 0.3],
            "effectif": [10, 20],
        }
    )
    prediction = predire_moyenne_expansive(table, ("type_bac", "boursier"))
    assert prediction.isna().all()


def test_moyenne_globale_expansive_ignore_le_groupe() -> None:
    table = pd.DataFrame(
        {
            "session": [2020, 2020, 2021],
            "type_bac": ["bg", "bt", "bp"],
            "boursier": [False, False, False],
            "taux": [0.2, 0.6, 0.0],
            "effectif": [10, 10, 5],
        }
    )
    prediction = predire_moyenne_expansive(table, ())
    assert prediction.iloc[2] == pytest.approx(0.4)  # moyenne pondérée de 0.2 et 0.6, poids égaux


def test_groupe_absent_du_passe_reste_sans_prediction() -> None:
    """Un groupe (bac professionnel) jamais vu avant la cible n'a pas de moyenne à lui appliquer."""
    table = pd.DataFrame(
        {
            "session": [2020, 2021],
            "type_bac": ["bg", "bp"],
            "boursier": [False, False],
            "taux": [0.5, 0.1],
            "effectif": [10, 10],
        }
    )
    prediction = predire_moyenne_expansive(table, ("type_bac", "boursier"))
    assert pd.isna(prediction.iloc[1])  # bp/False jamais observé en 2020, la seule session passée


# ─── _score_sur_sous_ensemble ───────────────────────────────────────────────


def test_score_pondere_correctement_par_effectif() -> None:
    table = pd.DataFrame({"taux": [0.0, 1.0], "effectif": [1, 99]})
    prediction = pd.Series([0.5, 0.5], index=table.index)
    score = _score_sur_sous_ensemble(table, prediction, "variante_test", "perimetre_test")
    # écart de 0.5 partout, mais le poids ne change rien à un écart constant
    assert score.mae_ponderee == pytest.approx(0.5)
    assert score.mae_non_ponderee == pytest.approx(0.5)
    assert score.couverture == 1.0
    assert score.n_cellules == 2


def test_score_sans_aucune_prediction_disponible() -> None:
    table = pd.DataFrame({"taux": [0.3], "effectif": [10]})
    prediction = pd.Series([np.nan], index=table.index)
    score = _score_sur_sous_ensemble(table, prediction, "variante_test", "perimetre_test")
    assert score.mae_ponderee is None
    assert score.mae_non_ponderee is None
    assert score.couverture == 0.0


def test_score_exclut_les_cellules_sans_prediction_du_calcul() -> None:
    table = pd.DataFrame({"taux": [0.2, 0.8], "effectif": [10, 10]})
    prediction = pd.Series([0.2, np.nan], index=table.index)
    score = _score_sur_sous_ensemble(table, prediction, "variante_test", "perimetre_test")
    assert score.mae_ponderee == pytest.approx(0.0)
    assert score.couverture == pytest.approx(0.5)
