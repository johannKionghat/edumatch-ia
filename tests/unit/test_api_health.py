"""Test de contrat de `/health` : sonde de vivacité, sans dépendance lourde."""

from __future__ import annotations

from fastapi.testclient import TestClient

from edumatch.api.main import create_app
from edumatch.config import get_settings


def test_health_repond_200_sans_etat_charge() -> None:
    """`/health` ne doit dépendre d'aucun état lourd (`etat_matching`, `etat_explicabilite`) :
    ce test instancie l'application sans faire tourner le cycle de vie (`TestClient` sans bloc
    `with`, voir `api/main.py`) — la sonde doit répondre quand même."""
    client = TestClient(create_app())

    reponse = client.get("/health")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] == "ok"
    assert corps["version"] == get_settings().projet.version
