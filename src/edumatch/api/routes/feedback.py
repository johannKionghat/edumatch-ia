"""Route `/feedback` : la décision motivée d'un conseiller (article 14, contrôle humain).

Voir `matching/score.py` (§« ce que le système ne fait jamais ») et
`feedback_store.py` : ce n'est pas la recommandation qui décide, c'est le
conseiller — et cette route est la trace de cette décision.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from prometheus_client import Counter

from edumatch.api.auth import get_conseiller_courant
from edumatch.api.deps import get_journal_feedback, get_limiteur_feedback
from edumatch.api.feedback_store import JournalFeedback
from edumatch.api.rate_limit import LimiteurDebit
from edumatch.api.schemas import ReponseFeedback, RequeteFeedback

router = APIRouter(tags=["supervision"])

# Signal métier le plus direct du contrôle humain exigé par l'article 14 de l'AI Act —
# voir monitoring/README.md côté edumatch-cicd.
_FEEDBACK_DECISIONS = Counter(
    "edumatch_feedback_decisions_total",
    "Décisions de conseiller enregistrées via /feedback, par type de décision.",
    ["decision"],
)


@router.post(
    "/feedback",
    response_model=ReponseFeedback,
    status_code=status.HTTP_201_CREATED,
    summary="Enregistre la décision motivée d'un conseiller sur une recommandation",
)
def feedback(
    requete: RequeteFeedback,
    journal: JournalFeedback = Depends(get_journal_feedback),
    conseiller: str = Depends(get_conseiller_courant),
    limiteur: LimiteurDebit = Depends(get_limiteur_feedback),
) -> ReponseFeedback:
    """Un écartement doit être motivé — validé par le schéma (`RequeteFeedback`) avant d'arriver
    ici — et journalisé, horodaté : la mesure exigée par R6 (`risques.md`) contre le contrôle
    humain de façade.

    Authentifiée depuis la revue de sécurité (`api/auth.py`) : `conseiller` est le principal HTTP
    Basic vérifié, jamais une valeur du corps de la requête — voir le docstring de
    `schemas.RequeteFeedback`."""
    if not limiteur.autoriser(conseiller):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de décisions /feedback pour ce conseiller : réessayer plus tard.",
        )
    enregistrement = journal.enregistrer(
        session=requete.session,
        identifiant_formation=requete.identifiant_formation,
        type_bac=requete.type_bac,
        boursier=requete.boursier,
        decision=requete.decision,
        motif=requete.motif,
        identifiant_conseiller=conseiller,
    )
    _FEEDBACK_DECISIONS.labels(decision=requete.decision).inc()
    return ReponseFeedback(
        identifiant_feedback=enregistrement.identifiant_feedback,
        horodatage=enregistrement.horodatage,
    )
