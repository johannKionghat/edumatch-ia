"""Les jeux du split temporel : préparation partagée par l'entraînement et l'évaluation.

## Pourquoi un module séparé

`JeuDonnees` et sa construction — conversion des types Parquet vers ce que
LightGBM attend, découpage de la table de variables par session — ne sont
spécifiques ni à l'entraînement ni à l'évaluation : les deux étapes doivent
construire *exactement* le même jeu de validation et le même jeu de test à
partir de la même table, avec la même conversion de types. Les regrouper ici
plutôt que les dupliquer, ou les laisser dans `train.py` au prix d'une
dépendance d'`evaluate.py` vers `train.py` pour des raisons de pure
organisation du code, rend visible que c'est un socle commun aux deux étapes.

`models/train.py` réexporte ces noms (`from edumatch.models.jeux import ...`)
pour que le code et les tests existants, écrits avant cette extraction,
continuent de les trouver sous `edumatch.models.train` sans modification.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from edumatch.config import Settings
from edumatch.features.build import NOM_FICHIER_VARIABLES, SOUS_DOSSIER
from edumatch.features.label import poids_effectif
from edumatch.models.metrics import ScoreSession, score


class ErreurJeuxDonnees(RuntimeError):
    """Aucune cellule pour les sessions demandées : le split ne peut pas être construit."""


@dataclass(frozen=True)
class JeuDonnees:
    """Les trois pièces alignées par index dont un entraînement ou une évaluation ont besoin."""

    X: pd.DataFrame
    y: pd.Series
    poids: pd.Series
    sessions: pd.Series


def chemin_table_variables(settings: Settings) -> Path:
    """Emplacement de la table de variables que l'entraînement et l'évaluation partagent."""
    return settings.processed_dir / SOUS_DOSSIER / NOM_FICHIER_VARIABLES


def preparer_matrice(table: pd.DataFrame, colonnes: list[str]) -> pd.DataFrame:
    """Convertit les types nullables Pandas issus de Parquet vers ce que LightGBM attend.

    `Int64` / `Float64` (entiers et flottants nullables) -> `float64`, `NaN`
    remplaçant `pandas.NA` ; LightGBM traite nativement l'absence, aucune
    imputation n'a lieu ici. `string` / `object` / `boolean` -> `category` :
    LightGBM détecte automatiquement les colonnes de ce type et les traite
    par regroupement de modalités, sans encodage one-hot préalable qui
    ferait exploser la dimension pour `fil_lib_voe_acc` (712 modalités).
    """
    matrice = table[colonnes].copy()
    for colonne in matrice.columns:
        dtype = str(matrice[colonne].dtype)
        if dtype in ("Int64", "Float64"):
            matrice[colonne] = matrice[colonne].astype("float64")
        elif dtype in ("string", "str", "object", "bool", "boolean"):
            matrice[colonne] = matrice[colonne].astype("category")
    return matrice


def extraire_jeu(table: pd.DataFrame, sessions: list[int], colonnes: list[str]) -> JeuDonnees:
    """Le sous-ensemble de `table` restreint à `sessions`, prêt pour l'entraînement ou la prédiction."""
    sous_table = table[table["session"].isin(sessions)]
    if sous_table.empty:
        raise ErreurJeuxDonnees(f"Aucune cellule pour les sessions {sessions} dans la table de variables.")
    return JeuDonnees(
        X=preparer_matrice(sous_table, colonnes),
        y=sous_table["taux"].astype("float64"),
        poids=poids_effectif(sous_table["effectif"]).astype("float64"),
        sessions=sous_table["session"],
    )


def evaluer_sur_perimetre(jeu: JeuDonnees, prediction: np.ndarray, perimetre: str) -> ScoreSession:
    """MAE pondérée et non pondérée d'une prédiction déjà calculée sur un jeu donné.

    Fine couche sur `metrics.score` : `JeuDonnees` est propre à ce module,
    la formule qu'elle sert à évaluer ne l'est pas (voir `metrics.py`).
    """
    return score(jeu.y, jeu.poids, prediction, perimetre)


def scores_par_session(jeu: JeuDonnees, prediction: np.ndarray) -> list[ScoreSession]:
    """Le score de `jeu`, éclaté session par session — utile quand `jeu` couvre plusieurs sessions."""
    scores = []
    for session in sorted(jeu.sessions.unique()):
        masque = (jeu.sessions == session).to_numpy()
        sous_jeu = JeuDonnees(
            X=jeu.X.loc[masque] if hasattr(jeu.X, "loc") else jeu.X[masque],
            y=jeu.y[masque],
            poids=jeu.poids[masque],
            sessions=jeu.sessions[masque],
        )
        scores.append(evaluer_sur_perimetre(sous_jeu, prediction[masque], str(session)))
    return scores
