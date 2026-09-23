"""Le contrôle qui refuse de démarrer la pile de production avec des valeurs de gabarit."""

from __future__ import annotations

import base64
import importlib.util
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "verifier_env_prod", RACINE / "scripts" / "verifier_env_prod.py"
)
controle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(controle)

FERNET_VALIDE = base64.urlsafe_b64encode(b"\x11" * 32).decode()


def _env_conforme() -> dict[str, str]:
    return {
        "AIRFLOW__CORE__FERNET_KEY": FERNET_VALIDE,
        "AIRFLOW__WEBSERVER__SECRET_KEY": "cle-de-session-de-test-non-secrete",
        "POSTGRES_ADMIN_PASSWORD": "mot-de-passe-choisi-1",
        "AIRFLOW_DB_PASSWORD": "mot-de-passe-choisi-2",
        "AIRFLOW_ADMIN_PASSWORD": "mot-de-passe-choisi-3",
    }


def test_environnement_conforme_ne_remonte_aucune_anomalie() -> None:
    assert controle.verifier(_env_conforme(), {}) == []


@pytest.mark.parametrize("nom", controle.VARIABLES_REQUISES)
def test_variable_absente_est_refusee(nom: str) -> None:
    valeurs = _env_conforme()
    del valeurs[nom]
    anomalies = controle.verifier(valeurs, {})
    assert any(nom in a and "absente" in a for a in anomalies)


@pytest.mark.parametrize("nom", controle.VARIABLES_REQUISES)
def test_valeur_de_gabarit_est_refusee(nom: str) -> None:
    valeurs = _env_conforme() | {nom: "changez_moi_cle_fernet_a_generer"}
    assert any(nom in a and "gabarit" in a for a in controle.verifier(valeurs, {}))


def test_valeur_recopiee_du_gabarit_est_refusee() -> None:
    """Le cas réel : un `.env` copié depuis `.env.example` sans rien remplacer."""
    gabarit = {"AIRFLOW_ADMIN_PASSWORD": "un-mot-de-passe-d-exemple"}
    valeurs = _env_conforme() | gabarit
    assert any(
        "AIRFLOW_ADMIN_PASSWORD" in a and "exemple" in a
        for a in controle.verifier(valeurs, gabarit)
    )


@pytest.mark.parametrize("valeur", ["pas-une-cle", base64.urlsafe_b64encode(b"court").decode(), ""])
def test_cle_fernet_invalide_est_refusee(valeur: str) -> None:
    valeurs = _env_conforme() | {"AIRFLOW__CORE__FERNET_KEY": valeur}
    assert any("AIRFLOW__CORE__FERNET_KEY" in a for a in controle.verifier(valeurs, {}))


def test_cle_fernet_valide_est_acceptee() -> None:
    assert controle.cle_fernet_valide(FERNET_VALIDE)


def test_le_gabarit_du_depot_serait_refuse_tel_quel() -> None:
    """Non-régression : `.env.example` ne doit jamais pouvoir servir de `.env` de production."""
    gabarit = controle.lire_env(RACINE / ".env.example")
    anomalies = controle.verifier(gabarit, gabarit)
    assert len(anomalies) == len(controle.VARIABLES_REQUISES)


def test_aucune_valeur_dans_les_messages() -> None:
    """Un message d'erreur ne cite jamais la valeur fautive."""
    secret = "valeur-secrete-a-ne-pas-afficher"
    valeurs = _env_conforme() | {"AIRFLOW__CORE__FERNET_KEY": secret}
    assert all(secret not in a for a in controle.verifier(valeurs, {}))
