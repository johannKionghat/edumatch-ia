"""Porte de promotion du modèle réentraîné (critères 3.3 et 4.12).

## Le problème que ce module referme

`models.train.entrainer_et_evaluer` mesure déjà, à couverture égale, l'écart entre
le modèle et le plancher (`session_precedente_avec_repli`) sur la session de test —
`rapport.scores_test` (le modèle) contre `rapport.baseline_test` (la règle triviale). Ce
que l'entraînement ne fait pas, c'est en tirer une décision de publication : `models.train.main()`
exporte le catalogue de prédictions (`exporter_catalogue_predictions`) quel que soit le
résultat de cette comparaison, ce qui est le comportement voulu pour une exécution manuelle
d'inspection, mais qui serait dangereux automatisé dans un DAG.

Mesuré sur ce dépôt, avec la configuration retenue (`taux_session_precedente` inclus comme
variable) : le modèle vaut 0,0758 de MAE pondérée en test contre 0,0701 pour le plancher —
le modèle **perd** contre la règle triviale d'une génération à l'autre (défaut de
généralisation temporelle documenté dans `models/train.py`, section « SANS/AVEC
`taux_session_precedente` »). Publier aveuglément ce qui sort d'un réentraînement
remplacerait donc, à chaque exécution planifiée, un plancher qui fonctionne par un modèle
qui fait strictement pire, pour la seule raison qu'un DAG l'a produit ce jour-là.

## La règle, et pourquoi elle est stricte

`decider_promotion` exige une MAE pondérée de test **strictement inférieure** à celle du
plancher, sur EXACTEMENT le même périmètre (couverture égale à 100 %, déjà garantie par
`RapportEntrainement.baseline_test` — voir son docstring : le plancher est jugé avec repli
sur la moyenne de groupe, jamais sur le seul sous-ensemble le plus facile). Une égalité
n'est pas un progrès : elle ne justifie pas de remplacer un artefact déjà servi par un
nouveau, aussi coûteux à produire (temps de calcul, trace MLflow, risque de régression
silencieuse ailleurs) pour un gain nul.

Aucune marge de tolérance n'est ajoutée (pas de `mae_modele < mae_baseline * 1.02` par
exemple) : au moment d'écrire ce module, l'écart mesuré va dans le mauvais sens (+0,0057),
donc toute tolérance ne ferait qu'autoriser une dégradation supplémentaire avant de la
détecter. Le seuil qui ferait reconsidérer cette règle : si un futur réentraînement bat le
plancher de très peu (par exemple 0,0699 contre 0,0701) et que ce gain s'avère instable
d'une exécution à l'autre (bruit d'échantillonnage plutôt que progrès réel) — c'est alors
une marge de tolérance, documentée et mesurée, qui se justifierait, pas avant.

## Ce que ce module ne fait pas

Il ne réentraîne rien : il reçoit un `ResultatEntrainement` déjà produit par
`models.train.entrainer_et_evaluer` et se contente de décider s'il doit être publié. Un
refus de promotion n'est pas une panne du pipeline — il est journalisé au niveau ERREUR
pour rester visible en supervision (critère 3.7), mais la tâche qui appelle ce module
(`orchestration.taches.reentrainer_modele`) ne lève pas : c'est un résultat légitime et
attendu tant que le modèle ne généralise pas mieux que la baseline, pas un état à masquer
ni à faire échouer artificiellement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from edumatch.config import Settings
from edumatch.models.train import ResultatEntrainement, exporter_catalogue_predictions

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RapportPromotion:
    """La décision de publication du réentraînement, à déclarer telle quelle."""

    promu: bool
    mae_modele: float
    mae_baseline: float
    chemin_catalogue: Path | None

    def resume(self) -> str:
        verdict = "PROMU" if self.promu else "REFUSÉ"
        return (
            f"Promotion : {verdict} — modèle MAE pondérée test={self.mae_modele:.4f} "
            f"contre plancher (couverture égale)={self.mae_baseline:.4f}."
        )


def decider_promotion(resultat: ResultatEntrainement) -> bool:
    """Vrai seulement si le modèle bat STRICTEMENT le plancher, en MAE pondérée de test.

    Comparaison sur `evaluation.metrique_principale` (`configs/base.yaml`), au même
    périmètre que le modèle (`baseline_test`, à couverture égale, voir le docstring du
    module) : comparer à une baseline jugée sur un sous-ensemble différent exagérerait ou
    minorerait l'écart selon le sens du biais de couverture.
    """
    mae_modele = resultat.rapport.scores_test.mae_ponderee
    mae_baseline = resultat.rapport.baseline_test.mae_ponderee
    return mae_modele < mae_baseline


def promouvoir_si_meilleur(resultat: ResultatEntrainement, settings: Settings) -> RapportPromotion:
    """Publie le catalogue de prédictions seulement si `decider_promotion` l'autorise.

    Idempotente : `decider_promotion` ne dépend que de métriques déjà calculées de façon
    déterministe par `entrainer_et_evaluer` (`random_state` fixé) à partir des mêmes
    données, et `exporter_catalogue_predictions` écrit par remplacement atomique
    (fichier `.part` renommé à la fin) — rejouer cette fonction sur le même
    `ResultatEntrainement` produit exactement la même décision et, si elle est promue, un
    fichier de sortie identique, jamais un doublon ni un fichier partiel.
    """
    mae_modele = resultat.rapport.scores_test.mae_ponderee
    mae_baseline = resultat.rapport.baseline_test.mae_ponderee

    if not decider_promotion(resultat):
        LOGGER.error(
            "Promotion refusée : MAE pondérée de test du modèle réentraîné (%.4f) "
            "non inférieure au plancher à couverture égale (%.4f). L'artefact déjà "
            "servi par l'API (%s) n'est pas remplacé.",
            mae_modele,
            mae_baseline,
            exporter_catalogue_predictions.__module__,
        )
        return RapportPromotion(
            promu=False, mae_modele=mae_modele, mae_baseline=mae_baseline, chemin_catalogue=None
        )

    chemin = exporter_catalogue_predictions(resultat, settings)
    LOGGER.info(
        "Promotion acceptée : MAE pondérée de test %.4f < plancher %.4f. "
        "Catalogue de prédictions publié vers %s.",
        mae_modele,
        mae_baseline,
        chemin,
    )
    return RapportPromotion(
        promu=True, mae_modele=mae_modele, mae_baseline=mae_baseline, chemin_catalogue=chemin
    )
