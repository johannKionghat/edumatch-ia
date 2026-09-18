"""Test de contrat de l'écran conseiller : `/` sert le document, `/static/*` sert les
assets — sans dépendance lourde (même politique que `/health`, voir `test_api_health.py`).

Depuis la revue de sécurité (motif A), `GET /` exige un compte conseiller nominatif comme
`/matching` et `/feedback` : `IDENTIFIANT_TEST`/`MOT_DE_PASSE_TEST` sont les identifiants de
démonstration injectés par la fixture `client` via `CONSEILLER_COMPTES`.
"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from edumatch.api.auth import calculer_empreinte
from edumatch.api.main import create_app
from edumatch.config import get_settings

IDENTIFIANT_TEST = "conseiller-test"
MOT_DE_PASSE_TEST = "mot-de-passe-test"


def _en_tete_basic(identifiant: str, mot_de_passe: str) -> dict[str, str]:
    jeton = base64.b64encode(f"{identifiant}:{mot_de_passe}".encode()).decode("ascii")
    return {"Authorization": f"Basic {jeton}"}


@pytest.fixture()
def _authentification(monkeypatch: pytest.MonkeyPatch):
    empreinte = calculer_empreinte(MOT_DE_PASSE_TEST)
    monkeypatch.setenv("CONSEILLER_COMPTES", f"{IDENTIFIANT_TEST}:{empreinte}")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client(_authentification: None) -> TestClient:
    return TestClient(create_app(), headers=_en_tete_basic(IDENTIFIANT_TEST, MOT_DE_PASSE_TEST))


def test_racine_sert_le_document_html(client: TestClient) -> None:
    reponse = client.get("/")

    assert reponse.status_code == 200
    assert "text/html" in reponse.headers["content-type"]
    assert '<html lang="fr">' in reponse.text


def test_racine_accepte_deux_comptes_distincts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deux conseillers différents, chacun avec son propre mot de passe, accèdent tous les deux
    à l'écran — non-régression du compte partagé unique remplacé (motif A)."""
    identifiant_autre, mot_de_passe_autre = "autre-conseiller-test", "autre-mot-de-passe-test"
    comptes = (
        f"{IDENTIFIANT_TEST}:{calculer_empreinte(MOT_DE_PASSE_TEST)};"
        f"{identifiant_autre}:{calculer_empreinte(mot_de_passe_autre)}"
    )
    monkeypatch.setenv("CONSEILLER_COMPTES", comptes)
    get_settings.cache_clear()
    try:
        app = create_app()
        client_alice = TestClient(app, headers=_en_tete_basic(IDENTIFIANT_TEST, MOT_DE_PASSE_TEST))
        client_bruno = TestClient(app, headers=_en_tete_basic(identifiant_autre, mot_de_passe_autre))
        assert client_alice.get("/").status_code == 200
        assert client_bruno.get("/").status_code == 200
    finally:
        get_settings.cache_clear()


def test_racine_sans_authentification_est_refusee(_authentification: None) -> None:
    client_sans_auth = TestClient(create_app())

    reponse = client_sans_auth.get("/")

    assert reponse.status_code == 401
    assert reponse.headers["www-authenticate"] == "Basic"


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


# ─── Rubrique « Sources et licences » (motif E) ──────────────────────────────


def test_sources_et_licences_est_servie_sans_authentification() -> None:
    """Page d'attribution, ouverte : voir le docstring de `routes/ecran.py`."""
    client = TestClient(create_app())

    reponse = client.get("/sources-et-licences")

    assert reponse.status_code == 200
    assert "text/html" in reponse.headers["content-type"]


def test_sources_et_licences_cite_les_cinq_producteurs_et_les_deux_licences() -> None:
    client = TestClient(create_app())
    texte = client.get("/sources-et-licences").text

    for producteur in ("MESR", "INSEE", "ONISEP", "France Compétences", "France Travail"):
        assert producteur in texte, f"producteur {producteur!r} absent de la rubrique sources et licences"
    assert "Licence Ouverte" in texte
    assert "ODbL" in texte


# ─── Notice d'information du candidat (motif C) ──────────────────────────────


def test_notice_information_est_servie_sans_authentification() -> None:
    client = TestClient(create_app())

    reponse = client.get("/notice-information")

    assert reponse.status_code == 200
    assert "text/html" in reponse.headers["content-type"]


def test_notice_information_porte_les_rubriques_obligatoires() -> None:
    client = TestClient(create_app())
    texte = " ".join(client.get("/notice-information").text.lower().split())

    # Responsable, finalité, base légale.
    assert "responsable de ce traitement" in texte
    assert "consentement" in texte.lower()
    assert "mission d'intérêt public" in texte.lower() or "mission d’intérêt public" in texte.lower()
    # Données traitées, durées.
    assert "type de baccalauréat" in texte.lower()
    assert "12 mois" in texte
    # Décision non entièrement automatisée.
    assert "ne décide jamais" in texte.lower() or "ne décide jamais à votre place" in texte.lower()
    # Droits et contact.
    assert "vos droits" in texte.lower()
    assert "cnil" in texte.lower()


def test_ecran_conseiller_renvoie_vers_les_deux_pages(client: TestClient) -> None:
    """L'écran authentifié doit permettre d'atteindre les deux pages ouvertes."""
    texte = client.get("/").text
    assert '/sources-et-licences"' in texte
    assert '/notice-information"' in texte
