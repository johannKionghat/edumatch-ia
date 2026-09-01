"""Point d'entrée de l'API (E29) : `/health`, `/matching`, `/explain`, `/feedback`.

## Ce que cette API fait, et ce qu'elle ne fait jamais

Elle assiste un conseiller dans l'estimation des chances d'admission et
l'explication d'une recommandation. Elle **ne décide jamais** à la place d'un
établissement ni d'un candidat (article 22 du RGPD) — voir `avis_assistance`
sur chaque réponse qui porte une recommandation ou une explication, et
`POST /feedback`, le point d'entrée par lequel un conseiller écarte, avec
motif, ce que le système propose.

## Le cycle de vie : un état lourd construit une fois, jamais par requête

`_cycle_de_vie` construit, au démarrage du processus, l'état de matching
(entraînement du modèle, artefacts de débouchés — coûteux, voir
`api/state.py`) et le précalcul d'explicabilité (lecture d'un fichier
Parquet). Un échec de l'une ou l'autre construction ne fait pas échouer le
démarrage de l'API : il est journalisé, et la route concernée répond 503
plutôt que de laisser tout le processus indisponible pour une seule
dépendance en panne — cohérent avec la distinction `liveness` / `readiness`
que `routes.health` documente.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from edumatch.api.errors import enregistrer_gestionnaires_erreurs
from edumatch.api.routes import assistant, ecran, explain, feedback, health, matching
from edumatch.api.state import construire_etat_explicabilite, construire_etat_matching
from edumatch.config import get_settings

DOSSIER_STATIQUE = Path(__file__).resolve().parent / "static"

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def _cycle_de_vie(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    try:
        app.state.etat_matching = construire_etat_matching(settings)
    except Exception:  # un état indisponible ne doit jamais empêcher le démarrage du processus
        LOGGER.exception("État de matching non initialisé au démarrage : /matching répondra 503.")
        app.state.etat_matching = None

    try:
        app.state.etat_explicabilite = construire_etat_explicabilite(settings)
    except Exception:  # même politique que ci-dessus
        LOGGER.exception("Précalcul d'explicabilité non chargé au démarrage : /explain répondra 503.")
        app.state.etat_explicabilite = None

    app.state.journal_feedback = None  # construit paresseusement au premier POST /feedback
    app.state.journal_audit = None  # construit paresseusement à la première inférence /matching
    app.state.assistant_rag = None  # construit paresseusement au premier POST /assistant (E32)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="EduMatch-IA — API de matching",
        version=settings.projet.version,
        description=(
            "Assiste un conseiller dans l'estimation des chances d'admission et l'explication "
            "d'une recommandation. Ne constitue jamais une décision automatisée (article 22 du "
            "RGPD) : voir `avis_assistance` sur chaque réponse, et `POST /feedback` pour "
            "l'écartement motivé."
        ),
        lifespan=_cycle_de_vie,
    )
    enregistrer_gestionnaires_erreurs(app)
    app.include_router(health.router)
    app.include_router(matching.router)
    app.include_router(explain.router)
    app.include_router(feedback.router)
    app.include_router(assistant.router)
    app.include_router(ecran.router)
    # Assets de l'écran conseiller (E31) : `style.css` et `app.js`, servis sous `/static/...`.
    # `routes.ecran` reste seule responsable de ce qui répond sur `/` — monté en dernier, ce
    # mount ne peut donc jamais capturer les routes déclarées ci-dessus (`/health`, `/matching`...).
    app.mount("/static", StaticFiles(directory=DOSSIER_STATIQUE), name="static")
    return app


app = create_app()
