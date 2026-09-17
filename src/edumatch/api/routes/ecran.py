"""Route de l'écran de supervision du conseiller : sert le document HTML statique.

## Le cadre retenu — HTML servi par FastAPI, pas de framework front

Décision d'architecture arrêtée dès la conception de l'API : le contrôle du RGAA (référentiel
d'accessibilité, qui s'appuie sur WCAG 2.1 niveau AA) prime sur le confort de
développement qu'apporterait React ou un autre framework. Cette route ne fait
que renvoyer `index.html` ; toute la logique (voir une recommandation, la
comprendre, l'écarter avec motif) tourne côté client en JavaScript vanilla,
contre les API déjà existantes (`/matching`, `/explain`, `/feedback`) —
aucune duplication de logique métier ici, cette route ne calcule rien.

`include_in_schema=False` : ce n'est pas un point d'entrée de l'API décrite
par OpenAPI, c'est l'écran qui la consomme.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["écran conseiller"], include_in_schema=False)

DOSSIER_STATIQUE = Path(__file__).resolve().parent.parent / "static"


@router.get("/")
def ecran_conseiller() -> FileResponse:
    """L'écran de supervision : voir les recommandations, comprendre une explication
    SHAP, écarter avec motif — voir `api/static/app.js` pour le détail des trois fonctions."""
    return FileResponse(DOSSIER_STATIQUE / "index.html", media_type="text/html")
