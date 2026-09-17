"""Sonde de vivacité (`liveness`), critère 4.7.

Volontairement sans dépendance lourde — ni lecture du catalogue, ni modèle,
ni fichier : un orchestrateur (Kubernetes) doit pouvoir distinguer un
processus **démarré** d'un processus **prêt** (`readiness`), et cette
distinction est l'objet même de la sonde `liveness` — les confondre provoque
des redémarrages en boucle au démarrage, le temps que l'état lourd
(`api.state.construire_etat_matching`) se construise.
"""

from __future__ import annotations

from fastapi import APIRouter

from edumatch.api.schemas import ReponseSante
from edumatch.config import get_settings

router = APIRouter(tags=["santé"])


@router.get("/health", response_model=ReponseSante, summary="Sonde de vivacité")
def sante() -> ReponseSante:
    return ReponseSante(version=get_settings().projet.version)
