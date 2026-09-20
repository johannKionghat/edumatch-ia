"""Routes de l'écran de supervision du conseiller : documents HTML statiques.

## Le cadre retenu — HTML servi par FastAPI, pas de framework front

Décision d'architecture arrêtée dès la conception de l'API : le contrôle du RGAA (référentiel
d'accessibilité, qui s'appuie sur WCAG 2.1 niveau AA) prime sur le confort de
développement qu'apporterait React ou un autre framework. `ecran_conseiller` ne fait que
renvoyer `index.html` ; toute la logique (voir une recommandation, la comprendre, l'écarter avec
motif) tourne côté client en JavaScript vanilla, contre les API déjà existantes (`/matching`,
`/explain`, `/feedback`) — aucune duplication de logique métier ici, cette route ne calcule rien.

`include_in_schema=False` : ce n'est pas un point d'entrée de l'API décrite par OpenAPI, c'est
l'écran qui la consomme.

## Authentification (revue de sécurité, motif A)

`GET /` exige désormais un compte conseiller nominatif (`api/auth.get_conseiller_courant`) : cet
écran expose les caractéristiques déclarées d'un candidat, potentiellement mineur, il ne peut
plus rester ouvert à quiconque connaît l'URL du service.

`GET /sources-et-licences` et `GET /notice-information` restent volontairement ouvertes, sans
authentification :

- la première est une page d'attribution (producteur, licence, date de collecte de chaque
  source) exigée par l'ODbL (IDÉO) et par la Licence Ouverte — aucune donnée personnelle, aucune
  raison de la réserver au conseiller ;
- la seconde est la notice d'information du candidat (article 12 à 14 du RGPD, motif C) : elle
  s'adresse à la personne dont les données sont traitées, qui ne détient par construction aucun
  compte conseiller. La gater derrière l'authentification conseiller la rendrait invisible à son
  seul destinataire légitime.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from edumatch.api.auth import get_conseiller_courant

router = APIRouter(tags=["écran conseiller"], include_in_schema=False)

DOSSIER_STATIQUE = Path(__file__).resolve().parent.parent / "static"


@router.get("/")
def ecran_conseiller(conseiller: str = Depends(get_conseiller_courant)) -> FileResponse:
    """L'écran de supervision : voir les recommandations, comprendre une explication
    SHAP, écarter avec motif — voir `api/static/app.js` pour le détail des trois fonctions.

    Authentifiée depuis la revue de sécurité (motif A) : sans compte conseiller nominatif valide,
    le navigateur reçoit une invite HTTP Basic plutôt que le document."""
    return FileResponse(DOSSIER_STATIQUE / "index.html", media_type="text/html")


@router.get("/sources-et-licences")
def sources_et_licences() -> FileResponse:
    """Rubrique « Sources et licences » : producteur, jeu, licence et date de collecte de chaque
    source du projet.

    La page est un fichier statique, servi tel quel — le contenu des manifestes ne change qu'au
    prochain téléchargement, jamais à la requête. Mais elle n'est plus saisie à la main : elle est
    **générée** depuis les manifestes d'ingestion par `api/sources_licences.py` (`make
    sources-licences`), et `tests/data/test_sources_licences_a_jour.py` échoue si elle en diverge.
    Alimentée à la main, elle annonçait une collecte du 28 août alors que les fichiers dataient du
    17 septembre : une attribution fausse au regard de l'article 2 de la Licence Ouverte.

    Voir le docstring du module pour pourquoi elle reste ouverte, sans authentification."""
    return FileResponse(DOSSIER_STATIQUE / "sources-et-licences.html", media_type="text/html")


@router.get("/notice-information")
def notice_information() -> FileResponse:
    """Notice d'information du candidat (motif C, article 12 à 14 du RGPD) : qui traite ses
    données, pourquoi, combien de temps, quels droits — rédigée dans un langage lisible par un
    lycéen de 17 ans. Voir le docstring du module pour pourquoi elle reste ouverte, sans
    authentification conseiller."""
    return FileResponse(DOSSIER_STATIQUE / "notice-information.html", media_type="text/html")
