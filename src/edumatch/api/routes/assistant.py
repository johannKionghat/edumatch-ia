"""Route `/assistant` : assistant documentaire qui répond à une question en citant ses
sources.

Brique secondaire : contrairement à `/matching` et `/explain`, cette route ne
sert aucune prédiction du modèle appris. Elle n'entre dans le périmètre ni de
l'audit d'équité, ni de la détection de dérive — voir le
docstring de `edumatch.rag`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from edumatch.api.deps import get_assistant_rag
from edumatch.api.schemas import CitationAssistantReponse, ReponseAssistant, RequeteAssistant
from edumatch.rag.assistant import AssistantRAG

router = APIRouter(tags=["assistant"])


@router.post(
    "/assistant",
    response_model=ReponseAssistant,
    summary="Répond à une question sur les formations, en citant ses sources",
)
def assistant(requete: RequeteAssistant, service: AssistantRAG = Depends(get_assistant_rag)) -> ReponseAssistant:
    reponse = service.repondre(requete.question)
    return ReponseAssistant(
        reponse=reponse.reponse,
        mode=reponse.mode,
        citations=[
            CitationAssistantReponse(
                identifiant=citation.identifiant,
                source=citation.source,
                licence=citation.licence,
                url=citation.url,
                date_collecte=citation.date_collecte,
                extrait=citation.extrait,
            )
            for citation in reponse.citations
        ],
        avertissement=reponse.avertissement,
    )
