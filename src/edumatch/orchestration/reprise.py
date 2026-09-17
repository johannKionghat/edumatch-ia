"""Reprise sur erreur pour l'orchestrateur (critère 3.4).

Rejoue une tâche entière avec temporisation croissante quand elle échoue
d'une manière transitoire, et abandonne immédiatement — sans nouvelle
tentative — quand elle échoue d'une manière définitive. La distinction
repose sur le vocabulaire commun déjà posé pour les connecteurs
d'ingestion (`edumatch.ingestion._flux.ErreurTransitoire` /
`ErreurDefinitive`) : ce module ne le redéfinit pas, il le consomme pour
piloter une tâche entière plutôt qu'un seul appel HTTP.

Ce que ce module ne fait pas : il ne connaît aucune tâche précise
(Parcoursup, Sirene, qualité...). Il reçoit une fonction sans argument et la
rejoue TELLE QUELLE en cas d'erreur transitoire — jamais une portion d'elle
— ce qui suppose que la fonction est elle-même idempotente. C'est le cas de
toutes les fonctions de `taches.py` : écriture atomique ou fichier ignoré
si déjà intact côté ingestion, écrasement déterministe du fichier de sortie
côté transformation.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from edumatch.config import Settings
from edumatch.ingestion._flux import ErreurTransitoire

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class ErreurRepriseEpuisee(RuntimeError):
    """Toutes les tentatives autorisées ont été consommées sans succès.

    Le dernier échec, bien que transitoire à chaque tentative individuelle,
    n'est plus rejoué : au-delà de `tentatives_max`, il est traité comme une
    panne à faire remonter (journal au niveau ERREUR, tâche Airflow en
    échec) plutôt que retenté indéfiniment.
    """


@dataclass(frozen=True)
class PolitiqueReprise:
    """Les trois paramètres de reprise, lus depuis `configs/*.yaml`
    (`orchestration.*`) — jamais une valeur en dur dans ce module :
    voir `politique_depuis_settings`."""

    tentatives_max: int
    delai_secondes: float
    facteur_backoff: float


def politique_depuis_settings(settings: Settings) -> PolitiqueReprise:
    """Construit la politique de reprise depuis la configuration résolue."""
    cfg = settings.orchestration
    return PolitiqueReprise(
        tentatives_max=cfg.tentatives_max,
        delai_secondes=cfg.delai_reprise_secondes,
        facteur_backoff=cfg.facteur_backoff,
    )


def executer_avec_reprise(
    tache: Callable[[], T],
    *,
    politique: PolitiqueReprise,
    nom_tache: str,
    dormir: Callable[[float], None] = time.sleep,
) -> T:
    """Exécute `tache()`, la retente selon `politique` si elle lève `ErreurTransitoire`.

    Toute autre exception — `ErreurDefinitive`, `ErreurQualiteBloquante`
    (rangée du côté définitif, voir `quality/_diagnostic.py`), ou n'importe
    quelle exception qui n'hérite pas explicitement d'`ErreurTransitoire` —
    traverse immédiatement, sans nouvelle tentative : le contrat de la
    source ou de la donnée a changé, retenter reproduirait exactement le
    même échec. C'est ce qui distingue cette fonction d'un simple compteur
    de tentatives : elle sait quand s'arrêter d'elle-même.

    `dormir`, injectable, permet aux tests de vérifier la séquence de délais
    (temporisation croissante) sans attendre réellement.

    Raises:
        ErreurRepriseEpuisee: `tentatives_max` échecs transitoires
            consécutifs, aucun n'ayant réussi.
    """
    delai = politique.delai_secondes
    derniere_erreur: ErreurTransitoire | None = None
    for tentative in range(1, politique.tentatives_max + 1):
        try:
            return tache()
        except ErreurTransitoire as erreur:
            derniere_erreur = erreur
            if tentative == politique.tentatives_max:
                break
            LOGGER.warning(
                "%s : échec transitoire (tentative %d/%d) — %s. Nouvelle tentative dans %.0f s.",
                nom_tache,
                tentative,
                politique.tentatives_max,
                erreur,
                delai,
            )
            dormir(delai)
            delai *= politique.facteur_backoff

    raise ErreurRepriseEpuisee(
        f"{nom_tache} : {politique.tentatives_max} tentative(s) épuisée(s), "
        f"dernière erreur transitoire : {derniere_erreur}"
    ) from derniere_erreur
