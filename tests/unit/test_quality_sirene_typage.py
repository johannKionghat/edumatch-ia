"""Deux régressions vues à la première exécution du pipeline en production, le 26 septembre 2026.

1. **Le typage des booléens.** `Series.str.fullmatch` renvoie des booléens dont le type dépend de
   la conversion Arrow vers pandas : `bool` quand les chaînes sont adossées à Arrow, `object`
   sinon. Sur une série `object`, `~` inverse chaque booléen **arithmétiquement** (`~True` vaut
   -2, qui est vrai) au lieu de le nier : toutes les lignes deviennent fautives. Sur l'instance de
   production, 7 411 217 codes NAF parfaitement valides (`32.12Z`, `47.89Z`) ont ainsi été
   déclarés non conformes, alors que le même code sur le même fichier n'en comptait aucun sur le
   poste de développement. Ces tests forcent le type `object`, celui qui échouait.

2. **Les dates de création implausibles.** Cinq lignes sur 43 896 818 bloquaient toute la chaîne.
   Elles sont désormais déclarées en avertissement, et ne redeviennent bloquantes qu'au-dessus
   d'une proportion écrite dans le module.
"""

from __future__ import annotations

import pandas as pd
import pytest

from edumatch.quality._diagnostic import Gravite
from edumatch.quality.sirene import (
    PROPORTION_MAX_DATES_IMPLAUSIBLES,
    _anomalies_domaine,
    _booleen,
    _Compteur,
)

# ─── Le typage des booléens ──────────────────────────────────────────────────


def test_booleen_neutralise_le_type_object() -> None:
    """Le cas qui échouait : une série `object` de booléens Python."""
    serie = pd.Series([True, False, None], dtype="object")
    converti = _booleen(serie)
    assert converti.dtype == bool
    assert list(converti) == [True, False, False]
    assert list(~converti) == [False, True, True]  # négation logique, pas arithmétique


def test_negation_arithmetique_reproduite_sans_la_conversion() -> None:
    """Preuve du défaut : sans conversion, `~` sur une série `object` ne nie pas, il calcule."""
    brut = pd.Series([True, False], dtype="object")
    assert list(~brut) == [
        -2,
        -1,
    ]  # les deux valeurs sont vraies, d'où le comptage de toutes les lignes


def _lot_object(codes: list[str], nomenclatures: list[str]) -> pd.DataFrame:
    """Un lot minimal, colonnes de chaînes forcées en `object` comme dans l'image de production."""
    n = len(codes)
    return pd.DataFrame(
        {
            "siret": pd.Series(["12345678901234"] * n, dtype="object"),
            "activitePrincipaleEtablissement": pd.Series(codes, dtype="object"),
            "nomenclatureActivitePrincipaleEtablissement": pd.Series(nomenclatures, dtype="object"),
            "activitePrincipaleNAF25Etablissement": pd.Series([None] * n, dtype="object"),
            "codeCommuneEtablissement": pd.Series(["75056"] * n, dtype="object"),
            "trancheEffectifsEtablissement": pd.Series(["NN"] * n, dtype="object"),
            "etatAdministratifEtablissement": pd.Series(["A"] * n, dtype="object"),
            "caractereEmployeurEtablissement": pd.Series(["O"] * n, dtype="object"),
            "dateCreationEtablissement": pd.Series(["2010-01-01"] * n, dtype="object"),
        }
    )


def _observer(trame: pd.DataFrame) -> _Compteur:
    compteur = _Compteur()
    compteur.total += len(trame)
    for nom in compteur.non_vides:
        compteur.non_vides[nom] += int(trame[nom].notna().sum())
    compteur._observer_domaines(trame)
    return compteur


def test_codes_rev2_valides_ne_sont_pas_comptes_fautifs() -> None:
    """Le comptage qui valait 104 705 sur 104 705 lignes valides doit valoir zéro."""
    compteur = _observer(_lot_object(["32.12Z", "47.89Z", "68.20B"], ["NAFRev2"] * 3))
    assert compteur.naf_rev2_non_conformes == 0
    assert compteur.siret_non_conformes == 0


def test_code_rev2_reellement_mal_forme_est_compte() -> None:
    compteur = _observer(_lot_object(["3212Z", "32.12Z"], ["NAFRev2"] * 2))
    assert compteur.naf_rev2_non_conformes == 1


def test_les_autres_nomenclatures_ne_sont_jamais_jugees_sur_le_format_rev2() -> None:
    """Un code NAF 1993 déclaré NAF1993 est conforme : c'est la nomenclature de la ligne qui décide."""
    compteur = _observer(_lot_object(["74.1J", "70.2C", "67.01"], ["NAF1993", "NAFRev1", "NAP"]))
    assert compteur.naf_rev2_non_conformes == 0


def test_siret_mal_forme_reste_detecte() -> None:
    trame = _lot_object(["32.12Z", "32.12Z"], ["NAFRev2"] * 2)
    trame["siret"] = pd.Series(["12345678901234", "1234"], dtype="object")
    assert _observer(trame).siret_non_conformes == 1


# ─── Les dates de création implausibles ──────────────────────────────────────


def _compteur_dates(implausibles: int, total: int) -> _Compteur:
    compteur = _Compteur()
    compteur.total = total
    compteur.dates_futures_implausibles = implausibles
    return compteur


def test_cinq_dates_implausibles_sur_44_millions_avertissent_sans_bloquer() -> None:
    """Le cas réel du répertoire national : 5 lignes sur 43 896 818."""
    anomalies = _anomalies_domaine("StockEtablissement.parquet", _compteur_dates(5, 43_896_818))
    dates = [a for a in anomalies if "dans le futur" in a.message]
    assert len(dates) == 1
    assert dates[0].gravite is Gravite.AVERTISSEMENT
    assert "seuil bloquant" in dates[0].message


def test_au_dela_du_seuil_de_proportion_l_anomalie_redevient_bloquante() -> None:
    total = 1_000_000
    au_dessus = int(total * PROPORTION_MAX_DATES_IMPLAUSIBLES) + 1
    anomalies = _anomalies_domaine("StockEtablissement.parquet", _compteur_dates(au_dessus, total))
    dates = [a for a in anomalies if "dans le futur" in a.message]
    assert dates and dates[0].gravite is Gravite.BLOQUANT


@pytest.mark.parametrize("implausibles", [0])
def test_aucune_date_implausible_aucune_anomalie(implausibles: int) -> None:
    anomalies = _anomalies_domaine(
        "StockEtablissement.parquet", _compteur_dates(implausibles, 1000)
    )
    assert not [a for a in anomalies if "dans le futur" in a.message]


def test_le_seuil_reste_deux_ordres_de_grandeur_au_dessus_du_mesure() -> None:
    """Le seuil doit rester lâche devant les 0,000011 % mesurés, et strict devant un défaut de source."""
    mesure = 5 / 43_896_818
    assert mesure < PROPORTION_MAX_DATES_IMPLAUSIBLES < 0.01
