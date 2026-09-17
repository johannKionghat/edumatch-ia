"""Dépendances FastAPI : accès à l'état chargé au démarrage, jamais reconstruit par requête.

Chaque fonction lit `request.app.state`, peuplé par le cycle de vie de
l'application (`api.main._cycle_de_vie`) ou, dans les tests, directement par
le test lui-même (voir `tests/unit/test_api_matching.py`) — aucune de ces deux
voies ne passe par ce module, ce qui le laisse simple : lire l'état, ou
répondre 503 s'il n'existe pas plutôt que de lever une exception non gérée.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from edumatch.api.audit import NOM_FICHIER_JOURNAL as NOM_FICHIER_JOURNAL_AUDIT
from edumatch.api.audit import SOUS_DOSSIER_AUDIT, JournalAudit
from edumatch.api.feedback_store import NOM_FICHIER_JOURNAL, SOUS_DOSSIER_JOURNAL, JournalFeedback
from edumatch.api.rate_limit import LimiteurDebit
from edumatch.api.state import EtatExplicabilite, EtatMatching
from edumatch.config import get_settings
from edumatch.rag.assistant import AssistantRAG, construire_assistant
from edumatch.rag.corpus import ErreurCorpusRag
from edumatch.rag.index import ErreurIndexRag


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
            detail="Précalcul d'explicabilité non chargé : exécuter `make explain` puis redémarrer l'API.",
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


def get_journal_audit(request: Request) -> JournalAudit:
    """Même politique de construction paresseuse que `get_journal_feedback` : le journal
    d'inférence (T5, article 12) n'est pas une dépendance dont l'absence doit empêcher l'API de
    démarrer — voir `audit.py`."""
    journal = getattr(request.app.state, "journal_audit", None)
    if journal is not None:
        return journal
    settings = get_settings()
    journal = JournalAudit(settings.processed_dir / SOUS_DOSSIER_AUDIT / NOM_FICHIER_JOURNAL_AUDIT)
    request.app.state.journal_audit = journal
    return journal


def get_limiteur_matching(request: Request) -> LimiteurDebit:
    """Limiteur de débit de `/matching` (revue de sécurité), construit au premier appel
    comme `get_journal_feedback` : un plafond de configuration n'a rien de coûteux à
    charger au démarrage. Une instance par processus applicatif — voir les limites
    assumées dans `rate_limit.py`."""
    limiteur = getattr(request.app.state, "limiteur_matching", None)
    if limiteur is not None:
        return limiteur
    settings = get_settings()
    limiteur = LimiteurDebit(limite=settings.api.limite_requetes_par_minute, fenetre_secondes=60.0)
    request.app.state.limiteur_matching = limiteur
    return limiteur


def get_limiteur_feedback(request: Request) -> LimiteurDebit:
    """Même politique que `get_limiteur_matching`, instance distincte : `/feedback` compte
    par identifiant de conseiller authentifié, `/matching` par adresse IP — mélanger les
    deux compteurs ferait consommer le même quota à deux usages différents."""
    limiteur = getattr(request.app.state, "limiteur_feedback", None)
    if limiteur is not None:
        return limiteur
    settings = get_settings()
    limiteur = LimiteurDebit(limite=settings.api.limite_requetes_par_minute, fenetre_secondes=60.0)
    request.app.state.limiteur_feedback = limiteur
    return limiteur


def get_assistant_rag(request: Request) -> AssistantRAG:
    """Construit l'assistant documentaire au premier appel, comme `get_journal_feedback` :
    un référentiel IDÉO absent (poste sans `data/external/referentiels/`) n'est pas une raison
    d'empêcher tout le service de démarrer, seule cette route répond 503."""
    assistant = getattr(request.app.state, "assistant_rag", None)
    if assistant is not None:
        return assistant
    settings = get_settings()
    try:
        assistant = construire_assistant(settings)
    except (ErreurCorpusRag, ErreurIndexRag) as erreur:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Assistant documentaire non disponible : {erreur} Voir "
                "`python -m edumatch.ingestion.referentiels` pour peupler data/external/referentiels/."
            ),
        ) from erreur
    request.app.state.assistant_rag = assistant
    return assistant
