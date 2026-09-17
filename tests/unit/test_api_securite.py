"""Tests de la revue de sécurité qui ne relèvent d'aucune route existante en
particulier : en-têtes de sécurité HTTP sur toute réponse, et disponibilité de `/metrics`
sans authentification.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from edumatch.api.main import create_app
from edumatch.api.security_headers import EN_TETES_SECURITE


def test_toute_reponse_porte_les_en_tetes_de_securite() -> None:
    """`/health` ne dépend d'aucun état lourd (voir `test_api_health.py`) : une route simple
    suffit à vérifier que le middleware s'applique à toute réponse."""
    client = TestClient(create_app())
    reponse = client.get("/health")
    assert reponse.status_code == 200
    for nom, valeur in EN_TETES_SECURITE.items():
        assert reponse.headers[nom] == valeur


def test_aucun_en_tete_strict_transport_security() -> None:
    """Revue de sécurité : mentir sur une protection TLS qui n'existe pas serait pire que de ne
    rien déclarer — voir le docstring de `security_headers.py`."""
    client = TestClient(create_app())
    reponse = client.get("/health")
    assert "strict-transport-security" not in {cle.lower() for cle in reponse.headers}


def test_en_tetes_de_securite_presents_meme_sur_une_erreur() -> None:
    """Un middleware ASGI s'applique à toute la chaîne, y compris aux réponses produites par les
    gestionnaires d'erreur (`errors.py`) — vérifié sur un 404 franc."""
    client = TestClient(create_app())
    reponse = client.get("/route-inexistante")
    assert reponse.status_code == 404
    for nom, valeur in EN_TETES_SECURITE.items():
        assert reponse.headers[nom] == valeur


def test_metrics_repond_sans_authentification() -> None:
    """Le collecteur Prometheus ne porte aucune authentification (voir
    `edumatch-cicd/monitoring/README.md`) : cette route doit rester ouverte."""
    client = TestClient(create_app())
    reponse = client.get("/metrics")
    assert reponse.status_code == 200
    assert "text/plain" in reponse.headers["content-type"]


def test_metrics_nexpose_aucune_route_dans_son_propre_schema_openapi() -> None:
    """`/metrics` n'est pas une route fonctionnelle pour un conseiller (voir `main.py`) : elle
    n'apparaît pas dans le contrat public de l'API."""
    client = TestClient(create_app())
    schema = client.get("/openapi.json").json()
    assert "/metrics" not in schema["paths"]
