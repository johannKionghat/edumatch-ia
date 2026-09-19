"""Primitives partagées des variantes de candidat (ADR 0021) : décroissance de récence,
reconstruction ancre + écart. Module séparé de `models/selection.py` et de `models/train.py`
pour que les deux puissent l'importer sans dépendance circulaire — `selection.py` importe déjà
`models.train` (pour `ajouter_taux_precedent`, `colonnes_features`...), donc `train.py` ne peut
pas importer `selection.py` en retour.

Ces fonctions sont pures, sans lecture de fichier ni appel MLflow : c'est ce qui permet à
`models/selection.py` (recherche du candidat, sur la seule validation) et à `models/train.py`
(entraînement du candidat figé, refit puis test) de les appliquer à l'identique, sans jamais
dupliquer la formule.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

CIBLE_TAUX = "taux"
CIBLE_ECART = "ecart"
CALIBRATION_AUCUNE = "aucune"
CALIBRATION_ISOTONIQUE = "isotonique_globale"


class ErreurVariante(RuntimeError):
    """Un paramètre de variante ne respecte pas une garantie attendue (ex. demi-vie non positive)."""


def poids_recence(sessions: pd.Series, s_ref: int, demi_vie: int) -> pd.Series:
    """`0,5 ** ((s_ref - session) / demi_vie)` : une cellule de la session `s_ref` pèse plein,
    une cellule à `demi_vie` sessions de distance pèse moitié moins (ADR 0021, variantes A/C)."""
    if demi_vie < 1:
        raise ErreurVariante(f"demi_vie doit être >= 1, obtenu {demi_vie}.")
    ecart_sessions = (s_ref - sessions.astype("int64")).astype("float64")
    return 0.5 ** (ecart_sessions / float(demi_vie))


def reconstruire_prediction(
    prediction_brute: np.ndarray, cible: str, ancre: pd.Series
) -> tuple[np.ndarray, int]:
    """Reconstruit la prédiction en espace taux, écrête à [0, 1], et compte les écrêtages.

    `cible == "taux"` : la prédiction est déjà en espace taux (objectif
    `cross_entropy`, déjà bornée par construction) — aucun écrêtage n'est
    normalement nécessaire, mais le compte est mesuré, jamais supposé nul.

    `cible == "ecart"` : la prédiction est `ancre + écart`, un `LGBMRegressor`
    en perte L2 n'étant contraint par aucune borne (ADR 0021, variante B).
    """
    if cible == CIBLE_TAUX:
        brute = np.asarray(prediction_brute, dtype="float64")
    else:
        brute = ancre.to_numpy(dtype="float64") + np.asarray(prediction_brute, dtype="float64")
    ecretee = np.clip(brute, 0.0, 1.0)
    n_ecretages = int(np.sum((brute < 0.0) | (brute > 1.0)))
    return ecretee, n_ecretages
