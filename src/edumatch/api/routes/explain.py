"""Route `/explain` : l'explication SHAP **précalculée** d'une cellule.

Jamais un recalcul TreeSHAP à la demande — le précalcul complet (99,8 Mo,
440 030 cellules, ~8,3 minutes) rend le calcul à la demande déraisonnable
pour une latence d'API (voir le docstring de `models/explain.py` et de
`api/state.py`).
"""

from __future__ import annotations

from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status

from edumatch.api.deps import get_etat_explicabilite
from edumatch.api.schemas import ContributionReponse, ReponseExplication, TypeBac
from edumatch.api.state import EtatExplicabilite
from edumatch.matching.score import MISE_EN_GARDE_ACCESSIBILITE

router = APIRouter(tags=["explicabilité"])

N_CONTRIBUTIONS_DEFAUT = 8


def _selectionner_cellule(
    precalcul: pd.DataFrame, session: int, cod_aff_form: str, type_bac: str, boursier: bool
) -> pd.Series | None:
    masque = (
        (precalcul["session"] == session)
        & (precalcul["cod_aff_form"] == cod_aff_form)
        & (precalcul["type_bac"] == type_bac)
        & (precalcul["boursier"] == boursier)
    )
    ligne = precalcul.loc[masque]
    return ligne.iloc[0] if not ligne.empty else None


def _contributions_triees(ligne: pd.Series, colonnes_shap: tuple[str, ...]) -> list[ContributionReponse]:
    paires = [(nom[len("shap__") :], float(ligne[nom])) for nom in colonnes_shap]
    paires.sort(key=lambda paire: abs(paire[1]), reverse=True)
    return [ContributionReponse(variable=nom, contribution=valeur) for nom, valeur in paires[:N_CONTRIBUTIONS_DEFAUT]]


@router.get("/explain", response_model=ReponseExplication, summary="Explique la prédiction d'une cellule")
def explain(
    session: Annotated[int, Query(ge=2018, description="Millésime de la cellule.")],
    cod_aff_form: Annotated[str, Query(min_length=1, description="Identifiant de la formation Parcoursup.")],
    type_bac: Annotated[TypeBac, Query()],
    boursier: Annotated[bool, Query()],
    etat: EtatExplicabilite = Depends(get_etat_explicabilite),
) -> ReponseExplication:
    ligne = _selectionner_cellule(etat.precalcul, session, cod_aff_form, type_bac, boursier)
    if ligne is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Aucune explication précalculée pour cette cellule (session, formation, type de "
                "baccalauréat, boursier) — voir 'session' et 'cod_aff_form' dans la réponse de /matching."
            ),
        )

    return ReponseExplication(
        session=session,
        identifiant_formation=cod_aff_form,
        type_bac=type_bac,
        boursier=boursier,
        prediction=float(ligne["prediction"]),
        valeur_base=float(ligne["valeur_base"]),
        contributions=_contributions_triees(ligne, etat.colonnes_shap),
        avertissement_accessibilite=MISE_EN_GARDE_ACCESSIBILITE,
    )
