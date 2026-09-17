"""Gestion des erreurs de l'API : codes HTTP justes, messages qui n'exposent ni chemin
interne ni trace : c'est la règle de sécurité que je me suis fixée pour ce
service.

Chaque gestionnaire journalise le type d'erreur et le chemin de la requête —
jamais le corps de la requête, qui peut porter des caractéristiques
personnelles du candidat (type de baccalauréat, département, statut de
boursier) au sens de l'AIPD (§2.4) — et répond un message générique, stable,
qui ne dépend jamais du texte interne de l'exception (qui peut contenir un
chemin de fichier, voir `matching/debouches.ErreurDebouches`).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse

from edumatch.matching.score import ErreurScore
from edumatch.models.explain import ErreurExplicabilite

LOGGER = logging.getLogger(__name__)


def enregistrer_gestionnaires_erreurs(app: FastAPI) -> None:
    """Enregistre les gestionnaires d'exceptions de l'application — appelé une fois par
    `api.main.create_app`."""

    @app.exception_handler(HTTPException)
    async def _erreur_http(request: Request, exc: HTTPException) -> JSONResponse:
        # HTTPException porte déjà un message métier volontairement rédigé (voir les routes) :
        # ce gestionnaire ne fait que journaliser le code et le chemin, jamais le corps de la requête.
        LOGGER.warning("HTTP %s sur %s", exc.status_code, request.url.path)
        return await http_exception_handler(request, exc)

    @app.exception_handler(ErreurScore)
    async def _erreur_score(request: Request, exc: ErreurScore) -> JSONResponse:
        LOGGER.error("Erreur de scoring sur %s (catalogue invalide) : %s", request.url.path, type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"detail": "Le score n'a pas pu être calculé : catalogue de matching invalide."},
        )

    @app.exception_handler(ErreurExplicabilite)
    async def _erreur_explicabilite(request: Request, exc: ErreurExplicabilite) -> JSONResponse:
        LOGGER.error("Erreur d'explicabilité sur %s : %s", request.url.path, type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"detail": "L'explication n'a pas pu être produite."},
        )

    @app.exception_handler(Exception)
    async def _erreur_inattendue(request: Request, exc: Exception) -> JSONResponse:
        LOGGER.exception("Erreur inattendue sur %s (%s)", request.url.path, type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "Une erreur interne est survenue."})
