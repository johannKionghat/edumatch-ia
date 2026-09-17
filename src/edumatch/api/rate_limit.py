"""Limitation de débit (revue de sécurité) : `deps.get_limiteur_matching` en
consomme une instance sur `/matching`, `deps.get_limiteur_feedback` sur `/feedback`.

## Le motif corrigé

`api.max_formations_evaluees` borne le coût d'une **seule** requête `/matching` (le
nombre de lignes du catalogue scorées) : il ne borne en rien leur **fréquence**. Rien
n'empêchait, avant cette étape, des milliers d'appels consécutifs d'un même client.

## Le choix — fenêtre glissante en mémoire de processus

Une file d'horodatages par identité (adresse IP sur `/matching`, où personne n'est
authentifié ; identifiant de conseiller authentifié sur `/feedback`, une identité plus
fiable qu'une adresse IP partagée) : on purge les horodatages plus vieux que la fenêtre,
puis on compte ce qui reste.

**Alternative écartée : `slowapi` / un magasin partagé (Redis).** Round-trip réseau et
composant supplémentaire à exploiter, pour un service de démonstration à un seul réplica
(`api.replicas` vaut 1 en dev/staging, voir `configs/*.yaml`) où un compteur en mémoire de
processus suffit déjà à démontrer la protection. **Limite assumée** : plusieurs réplicas
ou plusieurs workers ne partagent pas ce compteur, chacun compte pour son propre compte —
la limite réelle appliquée serait alors `limite × nombre de réplicas`, pas la valeur
configurée. **Le seuil qui ferait basculer vers un magasin partagé** : `api.replicas` ou
le plafond du HPA (`api.autoscaling.max`) passant durablement au-delà de 1, ce qui est
déjà le cas en production (jusqu'à 6, voir `edumatch-cicd/k8s/base/hpa.yaml`) — à corriger
avant un déploiement multi-réplicas réel, pas pour cette démonstration.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class LimiteurDebit:
    """Au plus `limite` requêtes par identité, sur une fenêtre glissante de
    `fenetre_secondes`. Protégé par un verrou pour les appels concurrents d'un même
    worker — la même réserve que `feedback_store.JournalFeedback` sur le multi-processus."""

    def __init__(self, limite: int, fenetre_secondes: float) -> None:
        self._limite = limite
        self._fenetre_secondes = fenetre_secondes
        self._verrou = threading.Lock()
        self._horodatages_par_identite: dict[str, deque[float]] = {}

    def autoriser(self, identite: str) -> bool:
        """Enregistre une tentative pour `identite` et renvoie si elle est autorisée."""
        maintenant = time.monotonic()
        with self._verrou:
            horodatages = self._horodatages_par_identite.setdefault(identite, deque())
            while horodatages and maintenant - horodatages[0] > self._fenetre_secondes:
                horodatages.popleft()
            if len(horodatages) >= self._limite:
                return False
            horodatages.append(maintenant)
            return True
