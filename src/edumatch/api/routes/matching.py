"""Route `/matching` : le score à trois termes pour un profil, réutilisant
`matching/score.recommander` — cette route ne recalcule rien, elle filtre le catalogue déjà
en mémoire (`api.state.EtatMatching`) puis délègue le scoring.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, status
from prometheus_client import Counter

from edumatch.api.audit import JournalAudit
from edumatch.api.auth import get_conseiller_courant
from edumatch.api.deps import get_etat_matching, get_journal_audit, get_limiteur_matching
from edumatch.api.rate_limit import LimiteurDebit
from edumatch.api.schemas import (
    ProfilRequete,
    RecommandationFormation,
    ReponseMatching,
    TermeAccessibiliteReponse,
    TermeAffiniteReponse,
    TermeDebouchesReponse,
)
from edumatch.api.state import EtatMatching
from edumatch.config import get_settings
from edumatch.matching.affinite import ProfilCandidat
from edumatch.matching.debouches import (
    STATUT_INDISPONIBLE_CERTIFICATION_RADIEE,
    STATUT_INDISPONIBLE_CHAINE_ROMPUE,
    STATUT_INDISPONIBLE_K_ANONYMAT,
    STATUT_INDISPONIBLE_TERRITOIRE_NON_RENSEIGNE,
    STATUT_MESURE,
)
from edumatch.matching.score import MISE_EN_GARDE_ACCESSIBILITE, recommander

LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["matching"])

AVERTISSEMENT_DEBOUCHES = (
    "Le terme de débouchés n'est mesuré que pour 1,4 % des lignes du catalogue (appariement "
    "textuel entre les libellés Parcoursup et le répertoire RNCP, fiable pour des intitulés de "
    "diplômes d'État très normés seulement — voir 'motif' sur chaque formation ci-dessous)."
)

# Motif lisible de chaque statut de `matching/debouches.py` : ce module de code porte des
# constantes techniques, jamais un texte à montrer à un conseiller — la traduction est ici,
# pas là-bas, pour ne pas mêler logique de calcul et présentation.
MOTIFS_DEBOUCHES: dict[str, str] = {
    STATUT_MESURE: "Mesuré sur l'agrégat Sirene département x division NAF, k-anonymisé (k=5).",
    STATUT_INDISPONIBLE_TERRITOIRE_NON_RENSEIGNE: (
        "Aucun département renseigné par le candidat : le terme est neutre (1,0)."
    ),
    STATUT_INDISPONIBLE_CHAINE_ROMPUE: (
        "Le libellé de cette formation n'est rattaché à aucun diplôme RNCP identifié par "
        "appariement textuel (couverture mesurée : 1,4 % des lignes du catalogue)."
    ),
    STATUT_INDISPONIBLE_CERTIFICATION_RADIEE: (
        "Le diplôme rattaché à cette formation est radié du RNCP : aucun débouché actif (valeur nulle, réelle)."
    ),
    STATUT_INDISPONIBLE_K_ANONYMAT: (
        "Au moins un établissement existe dans ce secteur et ce département, mais sous le seuil "
        "de confidentialité (k=5) : non exposé, terme neutre (1,0)."
    ),
}
MOTIF_PAR_DEFAUT = "Motif non documenté pour ce statut."

# Signal métier (non couvert par l'instrumentation HTTP générique) : combinaisons trop
# restrictives, pas une panne d'infrastructure — voir monitoring/README.md côté edumatch-cicd.
_MATCHING_SANS_RESULTAT = Counter(
    "edumatch_matching_sans_resultat_total",
    "Requêtes /matching pour lesquelles aucune formation ne correspond au profil.",
)


def _sous_catalogue(etat: EtatMatching, profil: ProfilRequete) -> pd.DataFrame:
    """Le catalogue de la session courante restreint aux deux dimensions de la cellule déclarées
    par le candidat, et au département s'il en exprime un — `recommander` ne filtre jamais sur
    ces colonnes lui-même (voir `matching/score.py`)."""
    catalogue = etat.catalogue
    masque = (catalogue["type_bac"] == profil.type_bac) & (catalogue["boursier"] == profil.boursier)
    if profil.departement is not None:
        masque &= catalogue["dep"] == profil.departement
    return catalogue.loc[masque]


def _libelle_formation(catalogue: pd.DataFrame, identifiant_cellule: str) -> str:
    lignes = catalogue.loc[catalogue["cod_aff_form"] == identifiant_cellule, "form_lib_voe_acc"]
    return str(lignes.iloc[0]) if not lignes.empty else identifiant_cellule


def _entrees_journal(profil: ProfilRequete, session: int, conseiller: str) -> dict[str, Any]:
    """Les variables d'entrée de l'inférence, au sens de T5 (`docs/registres.html`) : la
    session courante, déterminée côté serveur, le profil déclaré par le candidat — jamais son
    genre, qui n'existe même pas dans `ProfilRequete` (voir le docstring du module) — et
    l'identifiant du conseiller authentifié qui a déclenché la requête (revue de sécurité, motif
    A) : sans lui, une inférence contestée ne remonterait à aucune personne identifiée."""
    return {
        "session": session,
        "type_bac": profil.type_bac,
        "boursier": profil.boursier,
        "type_formation": profil.type_formation,
        "domaine": profil.domaine,
        "departement": profil.departement,
        "identifiant_conseiller": conseiller,
    }


def _sortie_journal(reponse: ReponseMatching) -> dict[str, Any]:
    """Le score produit, au sens de T5 : exactement ce que la réponse HTTP restitue, jamais
    davantage (minimisation, art. 5.1.c) — aucun champ recalculé pour le seul journal."""
    return {
        "n_formations_disponibles": reponse.n_formations_disponibles,
        "recommandations": [
            {"identifiant_formation": r.identifiant_formation, "score": r.score} for r in reponse.recommandations
        ],
    }


def _reponse_vide(etat: EtatMatching) -> ReponseMatching:
    return ReponseMatching(
        session=etat.session_courante,
        recommandations=[],
        n_formations_disponibles=0,
        n_formations_evaluees=0,
        avertissement_accessibilite=MISE_EN_GARDE_ACCESSIBILITE,
        debouches_disponible=etat.debouches_disponible,
        motif_indisponibilite_debouches=etat.motif_indisponibilite_debouches,
        avertissement_debouches=AVERTISSEMENT_DEBOUCHES,
    )


@router.post("/matching", response_model=ReponseMatching, summary="Recommande des formations pour un profil")
def matching(
    requete_http: Request,
    profil: ProfilRequete,
    etat: EtatMatching = Depends(get_etat_matching),
    journal: JournalAudit = Depends(get_journal_audit),
    limiteur: LimiteurDebit = Depends(get_limiteur_matching),
    conseiller: str = Depends(get_conseiller_courant),
) -> ReponseMatching:
    """Score le catalogue de la session courante pour le profil déclaré et retourne les
    meilleures formations, chaque terme du score restant visible séparément — jamais un score
    seul (voir `matching/score.py`, l'effet du produit de trois termes).

    Chaque appel journalise l'inférence (T5, article 12) avant de répondre, avec l'identifiant du
    conseiller authentifié qui l'a déclenchée — voir `api/audit.py` et
    `_entrees_journal`/`_sortie_journal` ci-dessus pour ce qui est écrit.

    Authentifiée depuis la revue de sécurité (motif A), comme `/feedback` (`api/auth.py`) : le
    plafond de débit (revue de sécurité) reste appliqué par adresse IP plutôt que par identité —
    voir `rate_limit.py` — car c'est la ressource de calcul du service, partagée par tous les
    conseillers d'un même poste, que ce plafond protège, pas l'imputabilité d'une décision."""
    identite = requete_http.client.host if requete_http.client is not None else "inconnue"
    if not limiteur.autoriser(identite):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de requêtes /matching pour cette adresse : réessayer plus tard.",
        )
    settings = get_settings()
    sous_catalogue = _sous_catalogue(etat, profil)
    n_disponibles = len(sous_catalogue)
    if n_disponibles == 0:
        _MATCHING_SANS_RESULTAT.inc()
        reponse = _reponse_vide(etat)
        journal.enregistrer(
            version_modele=settings.projet.version,
            entrees=_entrees_journal(profil, etat.session_courante, conseiller),
            sortie=_sortie_journal(reponse),
        )
        return reponse
    if n_disponibles > settings.api.max_formations_evaluees:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{n_disponibles} formations correspondent à ce profil, au-delà du plafond "
                f"({settings.api.max_formations_evaluees}) fixé pour tenir le SLO de latence "
                f"p95 ({settings.api.slo_latence_p95_ms} ms) : préciser un département ou un domaine "
                "pour réduire le périmètre plutôt que de tronquer le catalogue en silence."
            ),
        )
    top_n = min(profil.top_n, settings.api.top_n_max)

    profil_candidat = ProfilCandidat(
        type_formation=profil.type_formation, domaine=profil.domaine, departement=profil.departement
    )
    resultats = recommander(sous_catalogue, profil_candidat, etat.artefacts_debouches, settings, top_n=top_n)

    recommandations = [
        RecommandationFormation(
            identifiant_formation=resultat.identifiant_cellule,
            libelle_formation=_libelle_formation(sous_catalogue, resultat.identifiant_cellule),
            score=resultat.score,
            affinite=TermeAffiniteReponse(
                valeur=resultat.affinite.valeur,
                filtre_type_formation_respecte=resultat.affinite.filtre_type_formation_respecte,
                filtre_domaine_respecte=resultat.affinite.filtre_domaine_respecte,
                territoire_correspond=resultat.affinite.territoire_correspond,
            ),
            accessibilite=TermeAccessibiliteReponse(
                valeur=resultat.accessibilite, valeur_brute=resultat.accessibilite_brute
            ),
            debouches=TermeDebouchesReponse(
                valeur=resultat.debouches.valeur,
                disponible=resultat.debouches.disponible,
                statut=resultat.debouches.statut,
                motif=MOTIFS_DEBOUCHES.get(resultat.debouches.statut, MOTIF_PAR_DEFAUT),
                naf_divisions=resultat.debouches.naf_divisions,
                n_etablissements=resultat.debouches.n_etablissements,
            ),
        )
        for resultat in resultats
    ]
    reponse = ReponseMatching(
        session=etat.session_courante,
        recommandations=recommandations,
        n_formations_disponibles=n_disponibles,
        n_formations_evaluees=n_disponibles,
        avertissement_accessibilite=MISE_EN_GARDE_ACCESSIBILITE,
        debouches_disponible=etat.debouches_disponible,
        motif_indisponibilite_debouches=etat.motif_indisponibilite_debouches,
        avertissement_debouches=AVERTISSEMENT_DEBOUCHES,
    )
    journal.enregistrer(
        version_modele=settings.projet.version,
        entrees=_entrees_journal(profil, etat.session_courante, conseiller),
        sortie=_sortie_journal(reponse),
    )
    return reponse
