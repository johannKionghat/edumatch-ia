"""Refuse de démarrer la pile Airflow de production avec des valeurs de gabarit.

`docker-compose.prod.yml` exige que chaque variable sensible soit définie (`${VAR:?...}`),
mais il ne peut pas juger de sa valeur : un `.env` recopié depuis `.env.example` la satisfait.
La procédure d'installation dit précisément de partir de `.env.example`, donc le risque est
réel, pas théorique. Ce contrôle ferme cet écart, avant que la pile ne démarre.

Il vérifie trois choses :

- chaque variable requise est présente et non vide ;
- aucune ne porte une valeur de gabarit (`changez_moi...`) ni la valeur qu'`.env.example`
  donne pour cette même variable ;
- la clé Fernet est réellement une clé Fernet : 32 octets en base64 urlsafe, ce qu'Airflow
  exige pour déchiffrer les mots de passe de connexions stockés en base.

    python scripts/verifier_env_prod.py [--env .env]

Sortie 0 si tout est conforme, 1 sinon, avec la liste des variables fautives et jamais leur
valeur. Appelé par `make up-prod` avant `docker compose up`.
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
NOM_GABARIT = ".env.example"
PREFIXE_GABARIT = "changez_moi"

# Variables sans lesquelles la pile de production démarre mal ou reste ouverte : clés de
# chiffrement et de session Airflow, mots de passe de la base de métadonnées et du compte
# d'administration. Même liste que la section « production » de `.env.example`.
VARIABLES_REQUISES: tuple[str, ...] = (
    "AIRFLOW__CORE__FERNET_KEY",
    "AIRFLOW__WEBSERVER__SECRET_KEY",
    "POSTGRES_ADMIN_PASSWORD",
    "AIRFLOW_DB_PASSWORD",
    "AIRFLOW_ADMIN_PASSWORD",
)


def lire_env(chemin: Path) -> dict[str, str]:
    """Paires `CLE=VALEUR` d'un fichier d'environnement, commentaires et lignes vides ignorés."""
    valeurs: dict[str, str] = {}
    if not chemin.is_file():
        return valeurs
    for ligne_brute in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne_brute.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        valeurs[cle.strip()] = valeur.strip().strip('"').strip("'")
    return valeurs


def cle_fernet_valide(valeur: str) -> bool:
    """Une clé Fernet est un secret de 32 octets encodé en base64 urlsafe."""
    try:
        return len(base64.urlsafe_b64decode(valeur.encode("ascii"))) == 32
    except (ValueError, UnicodeEncodeError):
        return False


def verifier(valeurs: dict[str, str], gabarit: dict[str, str]) -> list[str]:
    """Les anomalies, une phrase par variable fautive. Aucune valeur n'est citée."""
    anomalies: list[str] = []
    for nom in VARIABLES_REQUISES:
        valeur = valeurs.get(nom, "")
        if not valeur:
            anomalies.append(f"{nom} : absente ou vide.")
            continue
        if valeur.startswith(PREFIXE_GABARIT):
            anomalies.append(f"{nom} : valeur de gabarit non remplacée.")
            continue
        if nom in gabarit and valeur == gabarit[nom]:
            anomalies.append(f"{nom} : identique à la valeur d'exemple de {NOM_GABARIT}.")
            continue
        if nom == "AIRFLOW__CORE__FERNET_KEY" and not cle_fernet_valide(valeur):
            anomalies.append(
                f"{nom} : ce n'est pas une clé Fernet (32 octets en base64 urlsafe). "
                'La générer avec : python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )
    return anomalies


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", default=".env", help="fichier d'environnement à contrôler")
    args = parser.parse_args()

    chemin = Path(args.env)
    if not chemin.is_absolute():
        chemin = RACINE / chemin
    if not chemin.is_file():
        print(
            f"{chemin} introuvable : copier {NOM_GABARIT} puis remplacer chaque valeur "
            "d'exemple par une vraie valeur.",
            file=sys.stderr,
        )
        return 1

    anomalies = verifier(lire_env(chemin), lire_env(RACINE / NOM_GABARIT))
    if anomalies:
        print(
            f"{chemin.name} : {len(anomalies)} variable(s) à corriger avant de démarrer la pile.",
            file=sys.stderr,
        )
        for anomalie in anomalies:
            print(f"  - {anomalie}", file=sys.stderr)
        return 1
    print(
        f"{chemin.name} : les {len(VARIABLES_REQUISES)} variables sensibles sont renseignées et valides."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
