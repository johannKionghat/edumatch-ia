"""Métriques d'évaluation partagées entre la baseline, l'entraînement et
l'évaluation.

## Pourquoi un module séparé

`models/baseline.py` calcule déjà une MAE pondérée et non pondérée, mais en
ligne, mêlée à la logique propre aux variantes de baseline
(`_score_sur_sous_ensemble`). Ce module en extrait la seule partie
générique — le calcul d'un écart absolu moyen, pondéré ou non, sur des
`pandas.Series` alignées par index — pour que `train.py` ne la
réécrive pas et que `evaluate.py` l'utilise à l'identique. Le calcul de
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
 doivent produire le même type de score, sur le même périmètre, avec la
même formule — sinon la comparaison mélange des mesures qui ne se
répondent pas (correction de la comparaison à couverture égale, voir
l'entraînement).
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


def predictions_baseline_couverture_egale(
    table: pd.DataFrame,
    colonne_prediction: str,
    moyenne_groupe: pd.Series,
    sessions: list[int],
) -> pd.Series:
    """La prédiction du plancher, avec repli, sur `sessions` — sans la noter.

    Extrait de `score_baseline_couverture_egale` pour qu'`models.evaluate`
    puisse comparer cette même prédiction, cellule par cellule, à la
    cible observée dans le diagramme de calibration et la ventilation par
    type de baccalauréat, pas seulement en tirer une MAE agrégée. Voir cette
    fonction pour la raison du repli par la moyenne de groupe.
    """
    masque = table["session"].isin(sessions)
    sous_table = table.loc[masque]
    return sous_table[colonne_prediction].fillna(moyenne_groupe.loc[masque])


def score_baseline_couverture_egale(
    table: pd.DataFrame,
    colonne_prediction: str,
    moyenne_groupe: pd.Series,
    sessions: list[int],
    perimetre: str,
) -> ScoreSession:
    """Le plancher sur `sessions`, avec repli, jugé sur EXACTEMENT le même périmètre qu'un modèle.

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
    prediction = predictions_baseline_couverture_egale(table, colonne_prediction, moyenne_groupe, sessions)
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


@dataclass(frozen=True)
class PointCalibration:
    """Un point du diagramme de fiabilité : une tranche de valeur prédite, sa moyenne
    prédite et sa moyenne observée, toutes deux pondérées par l'effectif.
    """

    tranche: int
    borne_basse: float
    borne_haute: float
    n_cellules: int
    poids: float
    prediction_moyenne: float
    observe_moyen: float

    @property
    def ecart(self) -> float:
        """Positif : le modèle sur-annonce dans cette tranche. Négatif : il sous-annonce."""
        return self.prediction_moyenne - self.observe_moyen


@dataclass(frozen=True)
class RapportCalibration:
    """Le diagramme de fiabilité complet et l'erreur de calibration attendue (ECE), pondérée."""

    perimetre: str
    points: list[PointCalibration]
    ece: float

    def resume(self) -> str:
        lignes = [f"calibration {self.perimetre:16s} ece_ponderee={self.ece:.4f}"]
        for point in self.points:
            lignes.append(
                f"    [{point.borne_basse:.1f}, {point.borne_haute:.1f}[ n={point.n_cellules:6d}  "
                f"prédit={point.prediction_moyenne:.3f}  observé={point.observe_moyen:.3f}  "
                f"écart={point.ecart:+.3f}"
            )
        return "\n".join(lignes)


def calibration(
    observe: pd.Series,
    poids: pd.Series,
    prediction: pd.Series | np.ndarray,
    n_tranches: int,
    perimetre: str,
) -> RapportCalibration:
    """Diagramme de fiabilité sur une cible continue bornée, et son erreur de calibration attendue.

    La cible est un taux dans [0, 1] (ADR 0009), pas une classe : la
    calibration usuelle d'un classifieur (probabilité prédite contre
    fréquence observée dans des tranches de probabilité) se transpose ici en
    découpant `n_tranches` intervalles également espacés sur [0, 1] et en
    comparant, dans chacun, la moyenne prédite à la moyenne observée — les
    deux pondérées par l'effectif de la cellule, cohérent avec la MAE
    pondérée qui gouverne le reste de l'évaluation.

    `prediction` est **écrêtée à [0, 1]** avant le découpage en tranches et
    le calcul des moyennes affichées : un arbre ne connaît pas la borne du
    label (voir `train.py`, test `test_predictions_sont_dans_lintervalle_du_label`),
    et un excès au-delà de 1 n'a pas de sens à représenter comme une
    probabilité annoncée sur un diagramme de fiabilité. L'écrêtage ne change
    rien à la MAE rapportée ailleurs, qui reste calculée sur la valeur brute.

    L'ECE retournée est la moyenne des écarts absolus par tranche, pondérée
    par le poids total de chaque tranche rapporté au poids total du
    périmètre — une tranche vide (aucune cellule dont la prédiction y tombe)
    est simplement absente du rapport, jamais comblée par une valeur
    inventée.
    """
    predit = np.clip(np.asarray(prediction, dtype="float64"), 0.0, 1.0)
    observe_arr = observe.to_numpy(dtype="float64")
    poids_arr = poids.to_numpy(dtype="float64")
    poids_total = float(poids_arr.sum())

    bornes = np.linspace(0.0, 1.0, n_tranches + 1)
    points: list[PointCalibration] = []
    ece = 0.0
    for indice in range(n_tranches):
        basse, haute = bornes[indice], bornes[indice + 1]
        derniere_tranche = indice == n_tranches - 1
        if derniere_tranche:
            masque = (predit >= basse) & (predit <= haute)
        else:
            masque = (predit >= basse) & (predit < haute)
        n_cellules = int(masque.sum())
        if n_cellules == 0:
            continue
        poids_tranche = poids_arr[masque]
        poids_tranche_total = float(poids_tranche.sum())
        prediction_moyenne = float((predit[masque] * poids_tranche).sum() / poids_tranche_total)
        observe_moyen = float((observe_arr[masque] * poids_tranche).sum() / poids_tranche_total)
        points.append(
            PointCalibration(
                tranche=indice,
                borne_basse=float(basse),
                borne_haute=float(haute),
                n_cellules=n_cellules,
                poids=poids_tranche_total,
                prediction_moyenne=prediction_moyenne,
                observe_moyen=observe_moyen,
            )
        )
        if poids_total > 0:
            ece += (poids_tranche_total / poids_total) * abs(prediction_moyenne - observe_moyen)

    return RapportCalibration(perimetre=perimetre, points=points, ece=float(ece))


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
    valeur de Shapley : c'est une vue globale, pas une décomposition
    additive d'une prédiction individuelle, et elle ne dit rien sur la
    direction de l'effet ni sur les interactions entre variables.
    """
    importances = modele.booster_.feature_importance(importance_type="gain")
    paires = list(zip(colonnes, (float(v) for v in importances), strict=False))
    return sorted(paires, key=lambda paire: paire[1], reverse=True)
