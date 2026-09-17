"""Tests unitaires de la construction des variables, sur des tables fabriquées.

Isolé des vraies données Parcoursup : chaque test construit directement les
quatre entrées de `construire_table_apprentissage` (fait, dim_formation,
dim_profil, silver) et une `VariablesConfig` minimale, pour ne vérifier que la
mécanique des jointures — le décalage temporel, l'absence d'antécédent, les
garde-fous de fan-out. La conformité à l'ADR 0013 (les 128 colonnes réelles)
est couverte séparément par `tests/data/test_variables_reference.py` et par
`tests/data/test_features_build_antifuite.py`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from edumatch.config import VariablesConfig
from edumatch.features.build import (
    ErreurConstructionVariables,
    construire_table_apprentissage,
)


def _variables(**surcharges: object) -> VariablesConfig:
    """Une `VariablesConfig` minimale et cohérente, pour les tests de ce module."""
    base = {
        "cles": ["session", "cod_aff_form"],
        "dimensions_cellule": ["type_bac", "boursier"],
        "session_courante": ["fili"],
        "decalees": ["capa_fin"],
        "decalees_sous_reserve": ["acc_tb"],
        "exclues": {"pct_f": "interdite"},
    }
    base.update(surcharges)
    return VariablesConfig(**base)


def _fait(lignes: list[dict]) -> pd.DataFrame:
    defaut = {"session": 2025, "sk_formation": 1, "sk_profil": 1, "effectif": 10, "taux": 0.5, "taux_depasse_1": False}
    return pd.DataFrame([{**defaut, **ligne} for ligne in lignes])


def _dim_formation(lignes: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(lignes)


def _dim_profil(lignes: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(lignes)


def _silver(lignes: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(lignes)


# ─── Dimensions de la cellule et liste blanche (sans décalage) ────────────


def test_dimensions_de_cellule_resolues_depuis_dim_profil() -> None:
    fait = _fait([{"sk_formation": 1, "sk_profil": 2}])
    dim_formation = _dim_formation([{"sk_formation": 1, "cod_aff_form": "1"}])
    dim_profil = _dim_profil(
        [
            {"sk_profil": 1, "type_bac": "bg", "boursier": False},
            {"sk_profil": 2, "type_bac": "bt", "boursier": True},
        ]
    )
    silver = _silver([{"session": 2025, "cod_aff_form": "1", "fili": "BTS", "capa_fin": 30}])

    table, _ = construire_table_apprentissage(fait, dim_formation, dim_profil, silver, _variables())

    assert table.iloc[0]["type_bac"] == "bt"
    assert bool(table.iloc[0]["boursier"]) is True


def test_session_courante_est_lue_sans_decalage() -> None:
    """`fili` doit provenir de la ligne silver de la MÊME session, pas de N-1."""
    fait = _fait([{"session": 2025}])
    dim_formation = _dim_formation([{"sk_formation": 1, "cod_aff_form": "1"}])
    dim_profil = _dim_profil([{"sk_profil": 1, "type_bac": "bg", "boursier": False}])
    silver = _silver(
        [
            {"session": 2024, "cod_aff_form": "1", "fili": "ANCIEN_LIBELLE", "capa_fin": 20},
            {"session": 2025, "cod_aff_form": "1", "fili": "NOUVEAU_LIBELLE", "capa_fin": 25},
        ]
    )

    table, _ = construire_table_apprentissage(fait, dim_formation, dim_profil, silver, _variables())

    assert table.iloc[0]["fili"] == "NOUVEAU_LIBELLE"


# ─── Le décalage temporel ───────────────────────────────────────────────


def test_variable_decalee_provient_de_la_session_n_moins_1() -> None:
    fait = _fait([{"session": 2025}])
    dim_formation = _dim_formation([{"sk_formation": 1, "cod_aff_form": "1"}])
    dim_profil = _dim_profil([{"sk_profil": 1, "type_bac": "bg", "boursier": False}])
    silver = _silver(
        [
            {"session": 2024, "cod_aff_form": "1", "fili": "X", "capa_fin": 20},
            {"session": 2025, "cod_aff_form": "1", "fili": "X", "capa_fin": 999},
        ]
    )

    table, _ = construire_table_apprentissage(fait, dim_formation, dim_profil, silver, _variables())

    assert table.iloc[0]["capa_fin"] == 20


def test_cellule_sans_antecedent_recoit_une_valeur_manquante_pas_imputee() -> None:
    """Cas réel de la session cible 2020 (ADR 0013 §6) : aucune ligne silver en N-1."""
    fait = _fait([{"session": 2025}])
    dim_formation = _dim_formation([{"sk_formation": 1, "cod_aff_form": "1"}])
    dim_profil = _dim_profil([{"sk_profil": 1, "type_bac": "bg", "boursier": False}])
    silver = _silver([{"session": 2025, "cod_aff_form": "1", "fili": "X", "capa_fin": 30}])  # pas de 2024

    table, rapport = construire_table_apprentissage(fait, dim_formation, dim_profil, silver, _variables())

    assert pd.isna(table.iloc[0]["capa_fin"])
    assert rapport.cellules_sans_antecedent == 1
    assert rapport.taux_manquant_par_variable["capa_fin"] == pytest.approx(1.0)


def test_nouvelle_formation_sans_antecedent_est_comptee() -> None:
    fait = _fait(
        [
            {"session": 2025, "sk_formation": 1},
            {"session": 2025, "sk_formation": 2},
        ]
    )
    dim_formation = _dim_formation(
        [{"sk_formation": 1, "cod_aff_form": "1"}, {"sk_formation": 2, "cod_aff_form": "2"}]
    )
    dim_profil = _dim_profil([{"sk_profil": 1, "type_bac": "bg", "boursier": False}])
    silver = _silver(
        [
            {"session": 2024, "cod_aff_form": "1", "fili": "X", "capa_fin": 10},
            {"session": 2025, "fili": "X", "capa_fin": 12},
            {"session": 2025, "cod_aff_form": "2", "fili": "Y", "capa_fin": 40},  # formation nouvelle en 2025
        ]
    )

    _, rapport = construire_table_apprentissage(fait, dim_formation, dim_profil, silver, _variables())

    assert rapport.cellules_sans_antecedent == 1


# ─── Réserve (mentions) : exclue par défaut, activable explicitement ──────


def test_decalees_sous_reserve_absentes_par_defaut() -> None:
    fait = _fait([{"session": 2025}])
    dim_formation = _dim_formation([{"sk_formation": 1, "cod_aff_form": "1"}])
    dim_profil = _dim_profil([{"sk_profil": 1, "type_bac": "bg", "boursier": False}])
    silver = _silver([{"session": 2024, "cod_aff_form": "1", "fili": "X", "capa_fin": 10, "acc_tb": 3}])

    table, _ = construire_table_apprentissage(fait, dim_formation, dim_profil, silver, _variables())

    assert "acc_tb" not in table.columns


def test_decalees_sous_reserve_incluses_sur_demande_explicite() -> None:
    fait = _fait([{"session": 2025}])
    dim_formation = _dim_formation([{"sk_formation": 1, "cod_aff_form": "1"}])
    dim_profil = _dim_profil([{"sk_profil": 1, "type_bac": "bg", "boursier": False}])
    silver = _silver([{"session": 2024, "cod_aff_form": "1", "fili": "X", "capa_fin": 10, "acc_tb": 3}])

    table, _ = construire_table_apprentissage(
        fait, dim_formation, dim_profil, silver, _variables(), inclure_sous_reserve=True
    )

    assert table.iloc[0]["acc_tb"] == 3


# ─── Garde-fous de jointure ────────────────────────────────────────────


def test_sk_formation_duplique_dans_dim_formation_leve() -> None:
    fait = _fait([{"session": 2025}])
    dim_formation = _dim_formation(
        [{"sk_formation": 1, "cod_aff_form": "1"}, {"sk_formation": 1, "cod_aff_form": "2"}]
    )
    dim_profil = _dim_profil([{"sk_profil": 1, "type_bac": "bg", "boursier": False}])
    silver = _silver([{"session": 2025, "cod_aff_form": "1", "fili": "X", "capa_fin": 10}])

    with pytest.raises(ErreurConstructionVariables):
        construire_table_apprentissage(fait, dim_formation, dim_profil, silver, _variables())


def test_sk_formation_orphelin_leve() -> None:
    fait = _fait([{"session": 2025, "sk_formation": 99}])
    dim_formation = _dim_formation([{"sk_formation": 1, "cod_aff_form": "1"}])
    dim_profil = _dim_profil([{"sk_profil": 1, "type_bac": "bg", "boursier": False}])
    silver = _silver([{"session": 2025, "cod_aff_form": "1", "fili": "X", "capa_fin": 10}])

    with pytest.raises(ErreurConstructionVariables):
        construire_table_apprentissage(fait, dim_formation, dim_profil, silver, _variables())


def test_le_label_et_les_cles_de_substitution_sont_conserves() -> None:
    fait = _fait([{"session": 2025, "taux": 0.42, "effectif": 17}])
    dim_formation = _dim_formation([{"sk_formation": 1, "cod_aff_form": "1"}])
    dim_profil = _dim_profil([{"sk_profil": 1, "type_bac": "bg", "boursier": False}])
    silver = _silver([{"session": 2025, "cod_aff_form": "1", "fili": "X", "capa_fin": 10}])

    table, _ = construire_table_apprentissage(fait, dim_formation, dim_profil, silver, _variables())

    assert table.iloc[0]["taux"] == pytest.approx(0.42)
    assert table.iloc[0]["effectif"] == 17
