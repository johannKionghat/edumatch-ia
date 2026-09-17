"""Tests unitaires de la formule du label et de sa pondération.

Fonctions pures, testées sur des `pd.Series` fabriquées : pas besoin de
`data/samples/` ici, contrairement aux tests de contrat qui rejouent le
pipeline (`tests/data/test_features_label.py`).
"""

from __future__ import annotations

import pandas as pd
import pytest

from edumatch.features.label import (
    BORNE_SUPERIEURE_TAUX,
    ErreurLabel,
    calculer_taux,
    poids_effectif,
    verifier_label,
)

# ─── calculer_taux : cas limites obligatoires ──────────────────────────────


def test_cas_normal_numerateur_inferieur_au_denominateur() -> None:
    taux, depasse = calculer_taux(pd.Series([3], dtype="Int64"), pd.Series([5], dtype="Int64"))
    assert taux.iloc[0] == pytest.approx(0.6)
    assert bool(depasse.iloc[0]) is False


def test_numerateur_superieur_au_denominateur_est_borne_et_signale() -> None:
    taux, depasse = calculer_taux(pd.Series([12], dtype="Int64"), pd.Series([10], dtype="Int64"))
    assert taux.iloc[0] == BORNE_SUPERIEURE_TAUX
    assert bool(depasse.iloc[0]) is True


def test_denominateur_nul_numerateur_non_nul_est_borne_et_signale() -> None:
    """`n / 0` est infini ; la formule le borne à 1 comme tout autre dépassement."""
    taux, depasse = calculer_taux(pd.Series([5], dtype="Int64"), pd.Series([0], dtype="Int64"))
    assert taux.iloc[0] == BORNE_SUPERIEURE_TAUX
    assert bool(depasse.iloc[0]) is True


def test_denominateur_nul_et_numerateur_nul_est_indetermine() -> None:
    """`0 / 0` n'a pas de valeur : ni un taux nul, ni un dépassement."""
    taux, depasse = calculer_taux(pd.Series([0], dtype="Int64"), pd.Series([0], dtype="Int64"))
    assert pd.isna(taux.iloc[0])
    assert pd.isna(depasse.iloc[0])


def test_numerateur_manquant_propage_une_valeur_manquante() -> None:
    taux, depasse = calculer_taux(pd.Series([pd.NA], dtype="Int64"), pd.Series([10], dtype="Int64"))
    assert pd.isna(taux.iloc[0])
    assert pd.isna(depasse.iloc[0])


def test_denominateur_manquant_propage_une_valeur_manquante() -> None:
    taux, depasse = calculer_taux(pd.Series([5], dtype="Int64"), pd.Series([pd.NA], dtype="Int64"))
    assert pd.isna(taux.iloc[0])
    assert pd.isna(depasse.iloc[0])


def test_taux_nul_n_est_jamais_signale_comme_depassement() -> None:
    taux, depasse = calculer_taux(pd.Series([0], dtype="Int64"), pd.Series([10], dtype="Int64"))
    assert taux.iloc[0] == 0.0
    assert bool(depasse.iloc[0]) is False


# ─── poids_effectif ─────────────────────────────────────────────────────────


def test_poids_effectif_est_l_effectif_brut() -> None:
    """ADR 0009 : le poids retenu est l'effectif brut, ni racine ni plafond."""
    effectif = pd.Series([1, 30, 16483], dtype="Int64")
    poids = poids_effectif(effectif)
    assert poids.tolist() == [1.0, 30.0, 16483.0]


def test_poids_effectif_conserve_les_valeurs_manquantes() -> None:
    """Propager, pas masquer : c'est `verifier_label` qui décide si c'est bloquant."""
    poids = poids_effectif(pd.Series([10, pd.NA], dtype="Int64"))
    assert poids.iloc[0] == 10.0
    assert pd.isna(poids.iloc[1])


# ─── verifier_label : les garanties attendues du label ────────────────────


def test_verifier_label_accepte_un_label_valide() -> None:
    taux = pd.Series([0.0, 0.6, 1.0], dtype="Float64")
    poids = pd.Series([1.0, 30.0, 500.0], dtype="Float64")
    verifier_label(taux, poids)  # ne lève pas


def test_verifier_label_tolere_un_taux_manquant() -> None:
    """Un taux `<NA>` est filtré en amont par `base_exploitable`, pas une erreur ici."""
    taux = pd.Series([0.6, pd.NA], dtype="Float64")
    poids = pd.Series([10.0, 20.0], dtype="Float64")
    verifier_label(taux, poids)  # ne lève pas


def test_verifier_label_rejette_un_taux_hors_bornes() -> None:
    taux = pd.Series([1.4], dtype="Float64")
    poids = pd.Series([10.0], dtype="Float64")
    with pytest.raises(ErreurLabel, match="hors de"):
        verifier_label(taux, poids)


def test_verifier_label_rejette_un_taux_negatif() -> None:
    taux = pd.Series([-0.1], dtype="Float64")
    poids = pd.Series([10.0], dtype="Float64")
    with pytest.raises(ErreurLabel, match="hors de"):
        verifier_label(taux, poids)


def test_verifier_label_rejette_une_cellule_sans_effectif() -> None:
    taux = pd.Series([0.5], dtype="Float64")
    poids = pd.Series([pd.NA], dtype="Float64")
    with pytest.raises(ErreurLabel, match="sans effectif"):
        verifier_label(taux, poids)


def test_verifier_label_rejette_un_poids_nul_ou_negatif() -> None:
    taux = pd.Series([0.5, 0.2], dtype="Float64")
    poids = pd.Series([10.0, 0.0], dtype="Float64")
    with pytest.raises(ErreurLabel, match="strictement positif"):
        verifier_label(taux, poids)
