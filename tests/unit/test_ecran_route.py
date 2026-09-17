"""Test de contrat de l'écran conseiller : `/` sert le document, `/static/*` sert les
assets — sans dépendance lourde (même politique que `/health`, voir `test_api_health.py`)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from edumatch.api.main import create_app


def test_racine_sert_le_document_html() -> None:
    client = TestClient(create_app())

    reponse = client.get("/")

    assert reponse.status_code == 200
    assert "text/html" in reponse.headers["content-type"]
    assert '<html lang="fr">' in reponse.text


def test_assets_statiques_sont_servis_sous_static() -> None:
    client = TestClient(create_app())

    css = client.get("/static/style.css")
    js = client.get("/static/app.js")

    assert css.status_code == 200
    assert "css" in css.headers["content-type"]
    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]


def test_routes_api_restent_prioritaires_sur_le_montage_statique() -> None:
    """`app.mount("/static", ...)` est déclaré en dernier (voir `api/main.py`) : les routes
    métier (`/health`, `/matching`...) ne doivent jamais être capturées par le montage."""
    client = TestClient(create_app())

    reponse = client.get("/health")

    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "ok"
