"""Métriques d'évaluation partagées entre la baseline (E21), l'entraînement (E22) et
l'évaluation (E23).

## Pourquoi un module séparé

`models/baseline.py` calcule déjà une MAE pondérée et non pondérée, mais en
ligne, mêlée à la logique propre aux variantes de baseline
(`_score_sur_sous_ensemble`). Ce module en extrait la seule partie
générique — le calcul d'un écart absolu moyen, pondéré ou non, sur des
`pandas.Series` alignées par index — pour que `train.py` (E22) ne la
réécrive pas et que `evaluate.py` (E23) l'utilise à l'identique. Le calcul de
la baseline lui-même n'est pas modifié : la fonction publique de
`baseline.py` (`_score_sur_sous_ensemble`) continue d'exister telle quelle,
seule la formule qu'elle partage avec l'entraînement est désormais unique.

La métrique retenue — l'erreur absolue moyenne pondérée par l'effectif de
la cellule (`modele.ponderation`, `configs/base.yaml`) — est celle que
l'ADR 0009 et `configs/base.yaml` (`evaluation.metrique_principale`)
arrêtent comme métrique principale : une cellule à 3 vœux ne doit pas peser
autant qu'une cellule à 500 dans le score final, exactement comme elle ne
pèse pas autant dans l'entraînement (poids d'effectif, ADR 0009).

`ScoreSession` et `score_baseline_couverture_egale` vivent ici pour la même
raison : `models.train` (le modèle) et le plancher qu'il faut lui comparer
(E21) doivent produire le même type de score, sur le même périmètre, avec la
même formule — sinon la comparaison mélange des mesures qui ne se
répondent pas (voir le compte rendu de l'étape E22, correction de la
comparaison à couverture égale).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def mae_ponderee(observe: pd.Series, predit: pd.Series | np.ndarray, poids: pd.Series) -> float:
    """Erreur absolue moyenne pondérée par `poids` : `sum(|y - ŷ| * w) / sum(w)`.

    Métrique principale du projet (`evaluation.metrique_principale`,
    `configs/base.yaml`) : elle donne à une cellule de 500 vœux cinq cents
    fois le poids d'une cellule à 1 vœu dans le score, cohérent avec la
    pondération appliquée à l'entraînement (`features.label.poids_effectif`).
    """
    ecarts = observe.to_numpy(dtype="float64") - np.asarray(predit, dtype="float64")
    poids_array = poids.to_numpy(dtype="float64")
    return float((np.abs(ecarts) * poids_array).sum() / poids_array.sum())


def mae_non_ponderee(observe: pd.Series, predit: pd.Series | np.ndarray) -> float:
    """Erreur absolue moyenne simple, sans pondération : chaque cellule compte pour une unité.

    Donnée en complément de `mae_ponderee`, jamais à sa place : elle répond à
    la question « quelle est l'erreur typique sur une formation prise au
    hasard », alors que la métrique pondérée répond à « quelle est l'erreur
    typique pour un vœu pris au hasard ». Les deux lectures sont utiles et
    ne se substituent pas l'une à l'autre.
    """
    ecarts = observe.to_numpy(dtype="float64") - np.asarray(predit, dtype="float64")
    return float(np.abs(ecarts).mean())


@dataclass(frozen=True)
class ScoreSession:
    """Le score, pondéré et non pondéré, sur une session ou un périmètre de sessions donné.

    Partagé entre `models.train` (le modèle) et `score_baseline_couverture_egale`
    (le plancher, calculé sur le même périmètre) : les deux doivent pouvoir se
    lire côte à côte sans conversion, exactement comme leurs MAE viennent de
    la même formule (`mae_ponderee` / `mae_non_ponderee` ci-dessus).
    """

    perimetre: str
    n_cellules: int
    mae_ponderee: float
    mae_non_ponderee: float

    def resume(self) -> str:
        return (
            f"{self.perimetre:16s} n={self.n_cellules:6d}  "
            f"mae_ponderee={self.mae_ponderee:.4f}  mae_non_ponderee={self.mae_non_ponderee:.4f}"
        )


def score_baseline_couverture_egale(
    table: pd.DataFrame,
    colonne_prediction: str,
    moyenne_groupe: pd.Series,
    sessions: list[int],
    perimetre: str,
) -> ScoreSession:
    """Le plancher (E21) sur `sessions`, avec repli, jugé sur EXACTEMENT le même périmètre qu'un modèle.

    `table[colonne_prediction]` porte la prédiction `session_precedente`
    (sans repli, `models.baseline.predire_session_precedente`) ; cette
    fonction la complète ici par `moyenne_groupe`
    (`models.baseline.predire_moyenne_expansive`, calculée une fois sur la
    table entière avant tout split) pour atteindre 100 % de couverture —
    c'est la variante `session_precedente_avec_repli` de `models/baseline.py`,
    à laquelle un modèle qui prédit toujours une valeur doit être comparé,
    jamais à la variante sans repli qui ne se prononce que sur les cellules
    qui ont un antécédent. Comparer un modèle à couverture totale à une
    baseline jugée sur le seul sous-ensemble qui a un antécédent (92,9 % des
    cellules 2025) exagérerait l'écart : c'est cette erreur que cette
    fonction évite.
    """
    masque = table["session"].isin(sessions)
    sous_table = table.loc[masque]
    prediction = sous_table[colonne_prediction].fillna(moyenne_groupe.loc[masque])
    poids = sous_table["effectif"].astype("float64")
    return ScoreSession(
        perimetre=perimetre,
        n_cellules=len(sous_table),
        mae_ponderee=mae_ponderee(sous_table["taux"], prediction, poids),
        mae_non_ponderee=mae_non_ponderee(sous_table["taux"], prediction),
    )


def score(y: pd.Series, poids: pd.Series, prediction: np.ndarray, perimetre: str) -> ScoreSession:
    """MAE pondérée et non pondérée d'une prédiction déjà calculée sur un jeu donné.

    Générique sur `y` / `poids` plutôt que sur `models.train.JeuDonnees`, pour
    que ce module reste indépendant de LightGBM et de la structure interne de
    l'entraînement — seul un vecteur observé, un vecteur de poids et une
    prédiction sont nécessaires pour produire un score comparable à celui de
    `score_baseline_couverture_egale`.
    """
    return ScoreSession(
        perimetre=perimetre,
        n_cellules=len(y),
        mae_ponderee=mae_ponderee(y, prediction, poids),
        mae_non_ponderee=mae_non_ponderee(y, prediction),
    )


def classement_importance(modele: object, colonnes: list[str]) -> list[tuple[str, float]]:
    """Le classement des variables par importance de gain, décroissant.

    L'importance de gain (`importance_type="gain"`, celle que LightGBM
    calcule à partir de la réduction de perte à chaque coupure) répond à
    « combien cette variable a-t-elle réduit l'erreur, en moyenne sur toutes
    ses coupures » — plus directement lisible ici que le compte de coupures
    (`importance_type="split"`), qui pénaliserait une variable dominante
    utilisée peu de fois mais avec un fort effet à chaque fois. `modele` est
    typé `object` plutôt que `lgb.LGBMRegressor` pour ne pas faire de ce
    module purement numérique une dépendance de LightGBM : seul
    `modele.booster_.feature_importance` est requis. Ce n'est **pas** une
    valeur de Shapley (E25) : c'est une vue globale, pas une décomposition
    additive d'une prédiction individuelle, et elle ne dit rien sur la
    direction de l'effet ni sur les interactions entre variables.
    """
    importances = modele.booster_.feature_importance(importance_type="gain")
    paires = list(zip(colonnes, (float(v) for v in importances)))
    return sorted(paires, key=lambda paire: paire[1], reverse=True)
