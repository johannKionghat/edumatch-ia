"""Exemple de bout en bout du score à trois termes (E28), sur données réelles.

`make matching-exemple` : entraîne le modèle d'accessibilité (E22, ~20 s sur
ce poste, voir `models/train.py`), construit l'agrégat Sirene département x
NAF k-anonymisé et la correspondance formation -> IDÉO (E28, ~20 s), puis
score et affiche les formations recommandées à un profil de candidat donné,
avec le détail des trois termes.

Ce module n'est pas testé par la suite rapide (`make test`) : il retraîne le
modèle et relit `data/raw/sirene/StockEtablissement.parquet` (4,4 Go, non
versionné) — un coût d'environ une minute, incompatible avec la suite de
tests qui doit tourner sans télécharger 4,6 Go (voir `data/samples/README.md`).
Les fonctions qu'il assemble sont, elles, testées séparément et rapidement
(`tests/unit/test_matching_*.py`).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import polars as pl

from edumatch.config import get_settings
from edumatch.matching.affinite import ProfilCandidat
from edumatch.matching.debouches import construire_artefacts
from edumatch.matching.score import ScoreFormation
from edumatch.matching.score import recommander as recommander_formations
from edumatch.models import train

LOGGER = logging.getLogger(__name__)

# Département d'exemple, choisi pour sa taille de catalogue raisonnable : voir
# le docstring de `matching.score.recommander`, l'assemblage n'est pas
# vectorisé et reste pensé pour un catalogue de la taille d'une recherche
# candidate (quelques centaines de lignes), pas les 92 000 cellules du test
# 2025 entier — un travail de vectorisation pour l'API (E29), hors périmètre
# ici.
DEPARTEMENT_EXEMPLE = "75"

PROFIL_EXEMPLE = ProfilCandidat(type_formation="BTS", domaine="informatique", departement=DEPARTEMENT_EXEMPLE)


def _construire_catalogue(table: pd.DataFrame, index_test: pd.Index, prediction_test: np.ndarray) -> pd.DataFrame:
    """Assemble le catalogue attendu par `recommander` : les colonnes de la table de variables
    (E20) déjà alignées sur l'index du jeu de test, plus la prédiction du modèle (E22)."""
    catalogue = table.loc[index_test, ["cod_aff_form", "fili", "fil_lib_voe_acc", "form_lib_voe_acc", "dep"]].copy()
    catalogue["taux_predit"] = prediction_test
    return catalogue[catalogue["dep"] == DEPARTEMENT_EXEMPLE].reset_index(drop=True)


def _afficher(resultats: list[ScoreFormation]) -> None:
    for rang, resultat in enumerate(resultats, start=1):
        LOGGER.info(
            "#%2d  score=%.3f  (affinite=%.2f x accessibilite=%.2f x debouches=%.2f [%s])  cellule=%s",
            rang,
            resultat.score,
            resultat.affinite.valeur,
            resultat.accessibilite,
            resultat.debouches.valeur,
            resultat.debouches.statut,
            resultat.identifiant_cellule,
        )


def executer() -> list[ScoreFormation]:
    settings = get_settings()

    LOGGER.info("Entraînement du modèle d'accessibilité (E22)...")
    resultat_entrainement = train.entrainer_et_evaluer(settings)

    catalogue = _construire_catalogue(
        resultat_entrainement.table,
        resultat_entrainement.jeu_test.X.index,
        resultat_entrainement.prediction_test,
    )
    LOGGER.info("Catalogue restreint au département %s : %d cellules.", DEPARTEMENT_EXEMPLE, len(catalogue))

    LOGGER.info("Construction des artefacts de débouchés (E28)...")
    artefacts = construire_artefacts(
        catalogue_parcoursup=pl.from_pandas(catalogue[["fil_lib_voe_acc"]]),
        settings=settings,
    )

    LOGGER.info("Profil d'exemple : %s", PROFIL_EXEMPLE)
    resultats = recommander_formations(catalogue, PROFIL_EXEMPLE, artefacts, settings, top_n=10)
    _afficher(resultats)
    return resultats


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    executer()


if __name__ == "__main__":
    main()
