"""Tests unitaires des statistiques de dérive (E34) : PSI, KS, canonisation — fonctions pures,
sur des séries fabriquées, sans dépendre de `data/samples/`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edumatch.models.derive_stats import (
    canoniser_categorie,
    est_categorielle,
    ks_numerique,
    psi_categorielle,
    psi_numerique,
)

# ─── est_categorielle ────────────────────────────────────────────────────────


def test_est_categorielle_vrai_pour_une_colonne_texte() -> None:
    assert est_categorielle(pd.Series(["a", "b"], dtype="string")) is True


def test_est_categorielle_faux_pour_une_colonne_numerique() -> None:
    assert est_categorielle(pd.Series([1.0, 2.0], dtype="Float64").astype("float64")) is False


# ─── canoniser_categorie ─────────────────────────────────────────────────────


def test_canoniser_categorie_neutralise_accent_casse_et_tiret() -> None:
    assert canoniser_categorie("Grand-Est") == canoniser_categorie("grand est")
    assert canoniser_categorie("formation sélective") == canoniser_categorie("Formation Selective")


def test_canoniser_categorie_traite_labsence_comme_une_modalite() -> None:
    assert canoniser_categorie(None) == canoniser_categorie(pd.NA)


# ─── psi_numerique ────────────────────────────────────────────────────────────


def test_psi_numerique_nul_quand_les_deux_distributions_sont_identiques() -> None:
    reference = pd.Series(np.linspace(0.0, 1.0, 200))
    assert psi_numerique(reference, reference, n_tranches=10) == pytest.approx(0.0, abs=1e-9)


def test_psi_numerique_positif_quand_la_distribution_se_deplace() -> None:
    reference = pd.Series(np.linspace(0.0, 1.0, 200))
    comparaison = pd.Series(np.linspace(0.5, 1.5, 200))  # translation complète hors de la référence

    psi = psi_numerique(reference, comparaison, n_tranches=10)

    assert psi > 0.5  # translation totale : dérive forte, pas un frémissement


def test_psi_numerique_nul_si_la_reference_est_constante() -> None:
    """Aucune tranche à comparer : `0.0` plutôt qu'une division par zéro."""
    reference = pd.Series([0.5] * 50)
    comparaison = pd.Series(np.linspace(0.0, 1.0, 50))
    assert psi_numerique(reference, comparaison, n_tranches=10) == 0.0


def test_psi_numerique_nul_si_une_serie_est_entierement_manquante() -> None:
    reference = pd.Series([np.nan] * 10)
    comparaison = pd.Series(np.linspace(0.0, 1.0, 10))
    assert psi_numerique(reference, comparaison, n_tranches=10) == 0.0


# ─── psi_categorielle ─────────────────────────────────────────────────────────


def test_psi_categorielle_nul_quand_les_proportions_sont_identiques() -> None:
    reference = pd.Series(["a"] * 50 + ["b"] * 50)
    assert psi_categorielle(reference, reference, top_k=10) == pytest.approx(0.0, abs=1e-9)


def test_psi_categorielle_neutralise_une_variation_de_forme() -> None:
    """« Grand Est » et « Grand-Est » ne doivent pas compter comme deux catégories distinctes
    (voir `models/derive.py`, mesure sur `region_etab_aff`)."""
    reference = pd.Series(["Grand Est"] * 50 + ["Ile de France"] * 50)
    comparaison = pd.Series(["Grand-Est"] * 50 + ["Ile-de-France"] * 50)

    assert psi_categorielle(reference, comparaison, top_k=10) == pytest.approx(0.0, abs=1e-9)


def test_psi_categorielle_positif_quand_une_categorie_apparait() -> None:
    reference = pd.Series(["a"] * 100)
    comparaison = pd.Series(["a"] * 50 + ["b"] * 50)

    assert psi_categorielle(reference, comparaison, top_k=10) > 0.1


def test_psi_categorielle_regroupe_les_categories_rares_sous_autre() -> None:
    """Au-delà de `top_k`, les modalités les moins fréquentes de la référence ne doivent
    pas, seules, dominer le PSI (voir `fil_lib_voe_acc`, 712 modalités réelles)."""
    rares_reference = [f"rare-{i}" for i in range(20)]
    reference = pd.Series(["frequente"] * 80 + rares_reference)
    rares_comparaison = [f"rare-{i}" for i in range(20, 40)]  # entièrement différentes, mais toutes rares
    comparaison = pd.Series(["frequente"] * 80 + rares_comparaison)

    psi = psi_categorielle(reference, comparaison, top_k=1)

    assert psi < 0.5  # le renouvellement des modalités rares ne fait pas exploser le PSI


# ─── ks_numerique ─────────────────────────────────────────────────────────────


def test_ks_numerique_nul_pour_deux_distributions_identiques() -> None:
    reference = pd.Series(np.linspace(0.0, 1.0, 100))
    assert ks_numerique(reference, reference) == pytest.approx(0.0)


def test_ks_numerique_vaut_un_pour_deux_supports_disjoints() -> None:
    reference = pd.Series(np.linspace(0.0, 1.0, 50))
    comparaison = pd.Series(np.linspace(2.0, 3.0, 50))
    assert ks_numerique(reference, comparaison) == pytest.approx(1.0)


def test_ks_numerique_none_si_une_serie_est_vide() -> None:
    assert ks_numerique(pd.Series([], dtype="float64"), pd.Series([1.0])) is None
