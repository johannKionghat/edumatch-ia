"""Route `/feedback` (E29) : la décision motivée d'un conseiller (article 14, contrôle humain).

Voir `matching/score.py` (§« ce que le système ne fait jamais ») et
`feedback_store.py` : ce n'est pas la recommandation qui décide, c'est le
conseiller — et cette route est la trace de cette décision.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from edumatch.api.deps import get_journal_feedback
from edumatch.api.feedback_store import JournalFeedback
from edumatch.api.schemas import ReponseFeedback, RequeteFeedback

router = APIRouter(tags=["supervision"])


@router.post(
    "/feedback",
    response_model=ReponseFeedback,
    status_code=status.HTTP_201_CREATED,
    summary="Enregistre la décision motivée d'un conseiller sur une recommandation",
)
def feedback(
    requete: RequeteFeedback, journal: JournalFeedback = Depends(get_journal_feedback)
) -> ReponseFeedback:
    """Un écartement doit être motivé — validé par le schéma (`RequeteFeedback`) avant d'arriver
    ici — et journalisé, horodaté : la mesure exigée par R6 (`risques.md`) contre le contrôle
    humain de façade."""
    enregistrement = journal.enregistrer(
        session=requete.session,
        identifiant_formation=requete.identifiant_formation,
        type_bac=requete.type_bac,
        boursier=requete.boursier,
        decision=requete.decision,
        motif=requete.motif,
        identifiant_conseiller=requete.identifiant_conseiller,
    )
    return ReponseFeedback(
        identifiant_feedback=enregistrement.identifiant_feedback,
        horodatage=enregistrement.horodatage,
    )
