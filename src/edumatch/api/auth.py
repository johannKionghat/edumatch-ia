"""Authentification HTTP Basic nominative de l'écran conseiller (revue de sécurité, motif A).

## Le motif corrigé — imputabilité individuelle, pas un compte partagé

`POST /feedback` exigeait déjà une authentification HTTP Basic, mais sur un seul couple
identifiant/mot de passe partagé par tous les conseillers : la trace d'un écartement était
imputable à « le conseiller » en général, jamais à une personne précise, ce qui ruine
l'imputabilité individuelle attendue du contrôle humain (article 14 du règlement sur l'IA — voir
`docs/registres.html`, T6, motif A). Cette version porte plusieurs comptes nominatifs
(`config.Settings.comptes_conseiller`, parsé depuis `CONSEILLER_COMPTES`) et étend
l'authentification à l'écran (`GET /`) et à `POST /matching`, jusqu'ici ouverts à quiconque.

## Pourquoi HTTP Basic plutôt qu'OAuth2/OIDC

Un seul rôle (« conseiller »), trois points d'accès protégés (`GET /`, `POST /matching`,
`POST /feedback`), aucune fédération d'identité avec un système tiers, aucune session longue à
révoquer indépendamment du mot de passe lui-même. OAuth2/OIDC ajouterait un fournisseur
d'identité, un flux d'échange de jeton et sa bibliothèque, pour un bénéfice qui ne se
matérialise qu'à partir d'une fédération avec l'annuaire d'un établissement scolaire — hors de
ce projet de démonstration. **Le seuil qui ferait basculer vers OAuth2/OIDC** : une intégration
avec un tel annuaire, ou un nombre de comptes qui rende la rotation manuelle des mots de passe
(par variable d'environnement, sans redéploiement du code) intenable.

## `hashlib.scrypt` plutôt qu'un mot de passe en clair, ou `bcrypt`

Un mot de passe en clair dans l'environnement serait lisible par quiconque a accès au
processus (`ps`, un tableau de bord d'orchestrateur) ; le stocker en clair dans `CONSEILLER_COMPTES`
en ferait un secret aussi fragile que le code lui-même. `hashlib.scrypt` est dans la
bibliothèque standard de Python (aucune dépendance à ajouter, contrairement à `bcrypt`, absent
du projet) et applique une fonction de dérivation de clé coûteuse en mémoire, qui ralentit
délibérément une attaque par force brute hors ligne si `CONSEILLER_COMPTES` fuitait. **Le seuil qui
ferait basculer vers `bcrypt`/`argon2`** : `bcrypt` déjà présent comme dépendance transitive
d'un autre paquet du projet, ce qui rendrait son usage direct gratuit plutôt qu'un ajout.

## `secrets.compare_digest`, jamais `==`

Une comparaison de chaînes Python ordinaire (`==`) s'arrête à la première différence : le temps
de réponse varie donc avec le nombre d'octets déjà devinés correctement, une fuite d'information
exploitable par une attaque temporelle. `secrets.compare_digest` compare en temps constant,
appliqué à l'identifiant comme au hachage du mot de passe. Quand aucun identifiant ne
correspond, une empreinte factice est tout de même vérifiée (`_EMPREINTE_FACTICE`) : sans ce
calcul de remplissage, répondre plus vite pour un identifiant inconnu que pour un mot de passe
faux sur un identifiant connu revèlerait, par le temps de réponse, quels identifiants existent.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import sys

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from edumatch.config import CompteConseiller, Settings, get_settings

LOGGER = logging.getLogger(__name__)

_SCHEME_BASIC = HTTPBasic()

_EN_TETE_NON_AUTHENTIFIE = {"WWW-Authenticate": "Basic"}

# Paramètres scrypt : coût mémoire (n), coût de parallélisation (r, p), taille de la clé dérivée
# (dklen). Valeurs de démonstration usuelles pour scrypt appliqué à un mot de passe (RFC 7914) —
# à revoir seulement si un audit mesure un temps de vérification incompatible avec le débit
# attendu de l'écran conseiller, ce qui n'est pas le cas ici (quelques authentifications par
# heure, pas par seconde).
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_PREFIXE_EMPREINTE = "scrypt"

# Empreinte d'un mot de passe qui n'est le mot de passe d'aucun compte réel : sert uniquement à
# consommer le même temps de calcul qu'une vérification réelle quand l'identifiant fourni ne
# correspond à aucun compte configuré, pour ne pas laisser le temps de réponse distinguer « ce
# compte n'existe pas » de « ce mot de passe est faux ».
_EMPREINTE_FACTICE = (
    "scrypt$00000000000000000000000000000000$"
    "0000000000000000000000000000000000000000000000000000000000000000"
)


def calculer_empreinte(mot_de_passe: str, sel: bytes | None = None) -> str:
    """Calcule l'empreinte scrypt d'un mot de passe, au format `scrypt$<sel>$<hachage>` (hexadécimal).

    C'est la fonction à utiliser hors ligne pour préparer `CONSEILLER_COMPTES` : jamais un mot de
    passe en clair dans la configuration, seulement le résultat de cet appel. `sel` n'est
    paramétrable que pour les tests (reproductibilité) ; en usage réel, il est toujours tiré
    aléatoirement (`secrets.token_bytes`).
    """
    sel_effectif = sel if sel is not None else secrets.token_bytes(16)
    hachage = hashlib.scrypt(
        mot_de_passe.encode("utf-8"), salt=sel_effectif, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN
    )
    return f"{_PREFIXE_EMPREINTE}${sel_effectif.hex()}${hachage.hex()}"


def _verifier_mot_de_passe(mot_de_passe: str, empreinte: str) -> bool:
    """Vérifie un mot de passe contre une empreinte au format `calculer_empreinte`.

    Renvoie `False` sur toute empreinte malformée plutôt que de lever une exception : une entrée
    de `CONSEILLER_COMPTES` mal recopiée ne doit jamais se traduire par une erreur 500 exploitable,
    seulement par un refus d'authentification.
    """
    segments = empreinte.split("$")
    if len(segments) != 3 or segments[0] != _PREFIXE_EMPREINTE:
        return False
    try:
        sel = bytes.fromhex(segments[1])
        hachage_attendu = bytes.fromhex(segments[2])
    except ValueError:
        return False
    hachage_calcule = hashlib.scrypt(
        mot_de_passe.encode("utf-8"), salt=sel, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN
    )
    return secrets.compare_digest(hachage_calcule, hachage_attendu)


def _trouver_compte(identifiant: str, comptes: tuple[CompteConseiller, ...]) -> CompteConseiller | None:
    """Cherche le compte dont l'identifiant correspond, en temps constant par comparaison.

    Parcourt systématiquement tous les comptes (pas de sortie anticipée sur la première
    correspondance) : le nombre de comptes configurés est petit (quelques conseillers), le coût
    de parcourir la liste en entier est négligeable devant le bénéfice de ne pas faire varier le
    temps de réponse selon la position du compte trouvé dans la liste.
    """
    trouve: CompteConseiller | None = None
    for compte in comptes:
        if secrets.compare_digest(identifiant.encode("utf-8"), compte.identifiant.encode("utf-8")):
            trouve = compte
    return trouve


def get_conseiller_courant(
    identifiants: HTTPBasicCredentials = Depends(_SCHEME_BASIC),
    settings: Settings = Depends(get_settings),
) -> str:
    """Vérifie l'identifiant et le mot de passe HTTP Basic contre les comptes nominatifs
    configurés, renvoie l'identifiant du conseiller authentifié.

    Ne journalise jamais le mot de passe ni l'empreinte fournis, seulement l'identifiant tenté en
    cas d'échec — l'identifiant renvoyé ici est ensuite journalisé par les routes appelantes
    (`routes/matching.py`, `routes/feedback.py`) à chaque inférence et à chaque écartement, pour
    que la trace de contrôle humain soit imputable à une personne (motif A).
    """
    comptes = settings.comptes_conseiller
    if not comptes:
        LOGGER.error(
            "Authentification conseiller non configurée : CONSEILLER_COMPTES absente ou vide "
            "dans l'environnement."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentification non configurée côté serveur : voir CONSEILLER_COMPTES dans .env.example.",
        )

    compte = _trouver_compte(identifiants.username, comptes)
    if compte is None:
        # Calcul factice : même coût qu'une vérification réelle, pour qu'un identifiant inconnu
        # ne réponde pas plus vite qu'un mot de passe faux sur un identifiant existant.
        _verifier_mot_de_passe(identifiants.password, _EMPREINTE_FACTICE)
        LOGGER.warning("Authentification refusée pour l'identifiant '%s'.", identifiants.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides.",
            headers=_EN_TETE_NON_AUTHENTIFIE,
        )

    if not _verifier_mot_de_passe(identifiants.password, compte.empreinte_mot_de_passe):
        LOGGER.warning("Authentification refusée pour l'identifiant '%s'.", identifiants.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides.",
            headers=_EN_TETE_NON_AUTHENTIFIE,
        )
    return compte.identifiant


if __name__ == "__main__":  # pragma: no cover — utilitaire d'exploitation, pas de code testé ici
    if len(sys.argv) != 2:
        print("Usage : python -m edumatch.api.auth <mot-de-passe-en-clair>", file=sys.stderr)
        raise SystemExit(1)
    print(calculer_empreinte(sys.argv[1]))
