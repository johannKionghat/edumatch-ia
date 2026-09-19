"""Porte de promotion du modèle réentraîné (critères 3.3 et 4.12).

## Le problème que ce module referme

`models.train.entrainer_et_evaluer` mesure déjà, à couverture égale, l'écart entre
le modèle et le plancher (`session_precedente_avec_repli`) sur la session de test —
`rapport.scores_test` (le modèle) contre `rapport.baseline_test` (la règle triviale). Ce
que l'entraînement ne fait pas, c'est en tirer une décision de publication : `models.train.main()`
exporte le catalogue de prédictions (`exporter_catalogue_predictions`) quel que soit le
résultat de cette comparaison, ce qui est le comportement voulu pour une exécution manuelle
d'inspection, mais qui serait dangereux automatisé dans un DAG.

Historique mesuré sur ce dépôt, avant le candidat figé de l'ADR 0021 (`taux_session_precedente`
inclus comme variable, sans décroissance de récence ni calibration) : le modèle valait 0,0758 de
MAE pondérée en test contre 0,0701 pour le plancher — il **perdait** contre la règle triviale
d'une génération à l'autre (défaut de généralisation temporelle documenté dans `models/train.py`).
Publier aveuglément ce qui sort d'un réentraînement remplacerait donc, à chaque exécution
planifiée, un plancher qui fonctionne par un modèle qui fait strictement pire, pour la seule
raison qu'un DAG l'a produit ce jour-là.

## La règle, et pourquoi elle est double depuis l'ADR 0021

Le plancher pré-enregistré de l'AIPD est une **conjonction**, pas une seule condition : MAE
pondérée de test sous le plancher **et** erreur de calibration attendue (ECE) de test sous
0,0322 (`evaluation.seuil_ece_test`). `decider_promotion` teste désormais les deux, sur
EXACTEMENT le même périmètre que le modèle pour la MAE (couverture égale à 100 %, déjà garantie
par `RapportEntrainement.baseline_test`). Une porte qui n'aurait testé que la MAE aurait laissé
passer un modèle rapide mais mal calibré — annoncer une probabilité fausse est nuisible même
avec un bon classement (voir `docs/decisions.html#adr-0021`, point 5).

Aucune marge de tolérance n'est ajoutée sur la MAE (pas de `mae_modele < mae_baseline * 1.02`
par exemple) : une égalité n'est pas un progrès, elle ne justifie pas de remplacer un artefact
déjà servi par un nouveau, aussi coûteux à produire (temps de calcul, trace MLflow, risque de
régression silencieuse ailleurs) pour un gain nul. Le seuil qui ferait reconsidérer cette
règle : si un futur réentraînement bat le plancher de très peu et que ce gain s'avère instable
d'une exécution à l'autre (bruit d'échantillonnage plutôt que progrès réel) — c'est alors une
marge de tolérance, documentée et mesurée, qui se justifierait, pas avant.

## Ce que ce module ne fait pas

Il ne réentraîne rien : il reçoit un `ResultatEntrainement` déjà produit par
`models.train.entrainer_et_evaluer` et se contente de décider s'il doit être publié. Un
refus de promotion n'est pas une panne du pipeline — il est journalisé au niveau ERREUR
pour rester visible en supervision (critère 3.7), mais la tâche qui appelle ce module
(`orchestration.taches.reentrainer_modele`) ne lève pas : c'est un résultat légitime et
attendu tant que le modèle ne satisfait pas la conjonction MAE/ECE, pas un état à masquer
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
    """La décision de publication du réentraînement, à déclarer telle quelle.

    `mae_ok` et `ece_ok` sont conservés séparément (et pas seulement combinés
    dans `promu`) pour que le rapport puisse dire LAQUELLE des deux
    conditions de la conjonction a échoué, sans obliger le lecteur à
    recomparer les chiffres lui-même.
    """

    promu: bool
    mae_modele: float
    mae_baseline: float
    ece_modele: float
    seuil_ece: float
    mae_ok: bool
    ece_ok: bool
    chemin_catalogue: Path | None

    def resume(self) -> str:
        verdict = "PROMU" if self.promu else "REFUSÉ"
        mae_statut = "OK" if self.mae_ok else "ÉCHEC"
        ece_statut = "OK" if self.ece_ok else "ÉCHEC"
        return (
            f"Promotion : {verdict} — "
            f"MAE pondérée test={self.mae_modele:.4f} contre plancher={self.mae_baseline:.4f} [{mae_statut}] ; "
            f"ECE test={self.ece_modele:.4f} contre seuil AIPD={self.seuil_ece:.4f} [{ece_statut}]."
        )


def decider_promotion(resultat: ResultatEntrainement, settings: Settings) -> bool:
    """Vrai seulement si le modèle satisfait la CONJONCTION du plancher de l'AIPD (ADR 0021,
    point 5) : MAE pondérée de test strictement sous le plancher (`evaluation.metrique_principale`,
    au même périmètre que le modèle — voir le docstring du module) ET erreur de calibration
    attendue de test strictement sous `evaluation.seuil_ece_test`.
    """
    mae_ok = resultat.rapport.scores_test.mae_ponderee < resultat.rapport.baseline_test.mae_ponderee
    ece_ok = resultat.rapport.ece_test < settings.evaluation.seuil_ece_test
    return mae_ok and ece_ok


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
    ece_modele = resultat.rapport.ece_test
    seuil_ece = settings.evaluation.seuil_ece_test
    mae_ok = mae_modele < mae_baseline
    ece_ok = ece_modele < seuil_ece
    promu = mae_ok and ece_ok

    rapport = RapportPromotion(
        promu=promu,
        mae_modele=mae_modele,
        mae_baseline=mae_baseline,
        ece_modele=ece_modele,
        seuil_ece=seuil_ece,
        mae_ok=mae_ok,
        ece_ok=ece_ok,
        chemin_catalogue=None,
    )

    if not promu:
        LOGGER.error(
            "Promotion refusée : %s L'artefact déjà servi par l'API (%s) n'est pas remplacé.",
            rapport.resume(),
            exporter_catalogue_predictions.__module__,
        )
        return rapport

    chemin = exporter_catalogue_predictions(resultat, settings)
    LOGGER.info("Promotion acceptée : %s Catalogue de prédictions publié vers %s.", rapport.resume(), chemin)
    return RapportPromotion(
        promu=True,
        mae_modele=mae_modele,
        mae_baseline=mae_baseline,
        ece_modele=ece_modele,
        seuil_ece=seuil_ece,
        mae_ok=mae_ok,
        ece_ok=ece_ok,
        chemin_catalogue=chemin,
    )
