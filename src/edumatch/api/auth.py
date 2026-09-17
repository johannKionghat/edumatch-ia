"""Authentification HTTP Basic de l'écran conseiller (revue de sécurité).

## Le motif corrigé

`POST /feedback` acceptait jusqu'ici un `identifiant_conseiller` déclaré
librement par l'appelant dans le corps de la requête : n'importe qui pouvait
imputer un écartement à un conseiller qui ne l'a jamais décidé, ce qui ruine
la trace de contrôle humain exigée par l'article 14 du règlement sur l'IA
(voir `docs/risques-aipd.html`, R6). La correction
retire ce champ du contrat d'entrée (`schemas.RequeteFeedback` ne le porte
plus) : c'est cette fonction qui construit le principal authentifié dont
`routes/feedback.py` dérive l'identifiant, jamais une valeur saisie par
l'appelant.

## Pourquoi HTTP Basic plutôt qu'OAuth2/OIDC

Un seul rôle (« conseiller »), un seul point d'accès protégé (`POST
/feedback`, consommé par l'écran de supervision), aucune fédération
d'identité avec un système tiers, aucune session longue à révoquer
indépendamment du mot de passe lui-même. OAuth2/OIDC ajouterait un
fournisseur d'identité, un flux d'échange de jeton et sa bibliothèque, pour
un bénéfice qui ne se matérialise qu'à partir de plusieurs rôles distincts
ou d'une fédération avec l'annuaire d'un établissement — aucun des deux
n'existe dans ce projet de démonstration. Le compromis assumé : un seul
couple identifiant/mot de passe partagé circule sur chaque requête protégée,
et `identifiant_conseiller` vaut alors le nom d'utilisateur HTTP Basic, pas
un identifiant individuel distinct par personne.

**Le seuil qui ferait basculer vers OAuth2/OIDC** : plusieurs conseillers
distincts nécessitant une traçabilité individuelle (pas un compte partagé),
ou une intégration avec l'annuaire d'un établissement scolaire existant.

## `secrets.compare_digest`, jamais `==`

Une comparaison de chaînes Python ordinaire (`==`) s'arrête à la première
différence : le temps de réponse varie donc avec le nombre de caractères
déjà devinés correctement, une fuite d'information exploitable par une
attaque temporelle. `secrets.compare_digest` compare en temps constant.
Les deux comparaisons (identifiant et mot de passe) sont toujours effectuées
l'une et l'autre, jamais court-circuitées : un `and` paresseux sur le
résultat, calculé après coup, ne réintroduit pas la fuite qu'une évaluation
paresseuse des appels eux-mêmes aurait produite.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from edumatch.config import Settings, get_settings

LOGGER = logging.getLogger(__name__)

_SCHEME_BASIC = HTTPBasic()

_EN_TETE_NON_AUTHENTIFIE = {"WWW-Authenticate": "Basic"}


def get_conseiller_courant(
    identifiants: HTTPBasicCredentials = Depends(_SCHEME_BASIC),
    settings: Settings = Depends(get_settings),
) -> str:
    """Vérifie l'identifiant et le mot de passe HTTP Basic, renvoie l'identifiant du
    conseiller authentifié.

    Ne journalise jamais le mot de passe fourni, seulement l'identifiant tenté en cas
    d'échec — cohérent avec `identifiant_conseiller` : « pseudonyme, jamais un nom »
    (voir `schemas.RequeteFeedback`).
    """
    identifiant_attendu = settings.conseiller_identifiant
    mot_de_passe_attendu = settings.conseiller_mot_de_passe
    if identifiant_attendu is None or mot_de_passe_attendu is None:
        LOGGER.error(
            "Authentification conseiller non configurée : CONSEILLER_IDENTIFIANT et/ou "
            "CONSEILLER_MOT_DE_PASSE absents de l'environnement."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authentification non configurée côté serveur : voir CONSEILLER_IDENTIFIANT et "
                "CONSEILLER_MOT_DE_PASSE dans .env.example."
            ),
        )

    identifiant_correct = secrets.compare_digest(
        identifiants.username.encode("utf-8"), identifiant_attendu.encode("utf-8")
    )
    mot_de_passe_correct = secrets.compare_digest(
        identifiants.password.encode("utf-8"), mot_de_passe_attendu.get_secret_value().encode("utf-8")
    )
    if not (identifiant_correct and mot_de_passe_correct):
        LOGGER.warning("Authentification refusée pour l'identifiant '%s'.", identifiants.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides.",
            headers=_EN_TETE_NON_AUTHENTIFIE,
        )
    return identifiants.username
