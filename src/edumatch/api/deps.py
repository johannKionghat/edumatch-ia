"""Dépendances FastAPI (E29) : accès à l'état chargé au démarrage, jamais reconstruit par requête.

Chaque fonction lit `request.app.state`, peuplé par le cycle de vie de
l'application (`api.main._cycle_de_vie`) ou, dans les tests, directement par
le test lui-même (voir `tests/unit/test_api_matching.py`) — aucune de ces deux
voies ne passe par ce module, ce qui le laisse simple : lire l'état, ou
répondre 503 s'il n'existe pas plutôt que de lever une exception non gérée.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from edumatch.api.feedback_store import NOM_FICHIER_JOURNAL, SOUS_DOSSIER_JOURNAL, JournalFeedback
from edumatch.api.state import EtatExplicabilite, EtatMatching
from edumatch.config import get_settings


def get_etat_matching(request: Request) -> EtatMatching:
    etat = getattr(request.app.state, "etat_matching", None)
    if etat is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Service de matching non initialisé : le modèle et le catalogue n'ont pas pu être "
                "chargés au démarrage. Voir les journaux du service pour la cause."
            ),
        )
    return etat


def get_etat_explicabilite(request: Request) -> EtatExplicabilite:
    etat = getattr(request.app.state, "etat_explicabilite", None)
    if etat is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Précalcul d'explicabilité non chargé : exécuter `make explain` (E25) puis redémarrer l'API.",
        )
    return etat


def get_journal_feedback(request: Request) -> JournalFeedback:
    """Construit le journal au premier appel plutôt qu'au démarrage : contrairement à
    `etat_matching` et `etat_explicabilite`, aucune lecture coûteuse n'est nécessaire ici, un
    répertoire manquant n'est pas une raison de refuser de démarrer l'API."""
    journal = getattr(request.app.state, "journal_feedback", None)
    if journal is not None:
        return journal
    settings = get_settings()
    journal = JournalFeedback(settings.processed_dir / SOUS_DOSSIER_JOURNAL / NOM_FICHIER_JOURNAL)
    request.app.state.journal_feedback = journal
    return journal
