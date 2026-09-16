"""En-têtes de sécurité HTTP (revue de sécurité, post-E35) : ajoutés à chaque réponse.

## Ce qui est ajouté, et pourquoi

- `X-Content-Type-Options: nosniff` — empêche un navigateur de deviner un type de
  contenu différent de celui déclaré (protection contre le détournement de type MIME).
- `X-Frame-Options: DENY` — interdit d'inclure l'écran conseiller (E31) dans une
  `<iframe>` d'un autre site (protection contre le détournement de clic).
- `Content-Security-Policy: default-src 'self'` — l'écran conseiller ne charge que ses
  propres ressources (`/static/style.css`, `/static/app.js`) : aucune source externe
  (police, script, feuille de style tierce) n'est nécessaire, la politique peut donc
  être stricte plutôt que servir de fourre-tout à corriger plus tard.
- `Referrer-Policy: no-referrer` — le corps d'une requête `/matching` peut contenir un
  type de baccalauréat, un statut de boursier, un département : des caractéristiques du
  candidat au sens de l'AIPD. Rien de tel ne doit fuiter dans l'en-tête `Referer` d'une
  requête déclenchée depuis une page de ce service vers un site tiers.

## Ce qui n'est volontairement pas ici : `Strict-Transport-Security`

Cet en-tête indique au navigateur de refuser tout accès en clair (HTTP) pendant sa durée
de vie. L'ajouter alors qu'aucun TLS n'est en place aujourd'hui (démonstration locale via
`docker-compose.yml`, cluster de démonstration sans certificat configuré) mentirait sur
une protection qui n'existe pas : un navigateur qui aurait mémorisé cet en-tête refuserait
tout accès HTTP futur, y compris légitime, tant qu'aucun certificat ne serait en place. À
ajouter le jour où un reverse proxy termine TLS devant ce service — pas avant.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

EN_TETES_SECURITE: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
}


def enregistrer_en_tetes_securite(app: FastAPI) -> None:
    """Enregistre le middleware qui ajoute `EN_TETES_SECURITE` à chaque réponse, y compris
    les réponses d'erreur (`errors.py`) : un middleware ASGI s'applique à toute la
    chaîne, gestionnaires d'exception compris."""

    @app.middleware("http")
    async def _ajouter_en_tetes_securite(
        request: Request, appel_suivant: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        reponse = await appel_suivant(request)
        for nom, valeur in EN_TETES_SECURITE.items():
            reponse.headers.setdefault(nom, valeur)
        return reponse
