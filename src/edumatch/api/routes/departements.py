"""Route `/departements` : la liste qui alimente le menu déroulant de l'écran conseiller.

Les codes viennent du catalogue de la session courante, déjà en mémoire (`api.state`) : la liste
ne propose que des départements où au moins une formation existe, et elle suit le catalogue sans
liste codée en dur. Les libellés viennent de `matching/departements.py` ; faute d'artefact, la
réponse le dit (`libelles_disponibles: false`) et l'écran affiche les codes seuls.

Authentifiée comme l'écran qui la consomme (motif A) : rien de personnel dans la réponse, mais
aucune raison d'exposer une route de l'écran à qui ne peut pas ouvrir l'écran.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from edumatch.api.auth import get_conseiller_courant
from edumatch.api.deps import get_etat_matching
from edumatch.api.schemas import Departement, ReponseDepartements
from edumatch.api.state import EtatMatching
from edumatch.matching.departements import trier_codes

router = APIRouter(tags=["matching"])


@router.get(
    "/departements", response_model=ReponseDepartements, summary="Départements du catalogue courant"
)
def departements(
    etat: EtatMatching = Depends(get_etat_matching),
    conseiller: str = Depends(get_conseiller_courant),
) -> ReponseDepartements:
    libelles = etat.libelles_departements
    codes = trier_codes(etat.catalogue["dep"].astype(str))
    return ReponseDepartements(
        session=etat.session_courante,
        libelles_disponibles=bool(libelles),
        departements=[Departement(code=code, libelle=libelles.get(code)) for code in codes],
    )
