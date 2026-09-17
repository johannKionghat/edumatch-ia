"""Test de contrat de `/feedback` : l'écartement doit être motivé, horodaté, journalisé
(R6, `docs/sous-docs-projets/05-gouvernance/risques.md`).

Depuis la revue de sécurité, `/feedback` exige une authentification HTTP Basic
(`api/auth.py`) : `identifiant_conseiller` n'est plus un champ du corps de la requête,
il est dérivé du principal authentifié. `IDENTIFIANT_TEST`/`MOT_DE_PASSE_TEST` sont les
identifiants de démonstration injectés par la fixture `client` via des variables
d'environnement — jamais en dur ailleurs que dans ce module de test.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from edumatch.api.deps import get_journal_feedback
from edumatch.api.feedback_store import JournalFeedback
from edumatch.api.main import create_app
from edumatch.config import get_settings

IDENTIFIANT_TEST = "conseiller-test"
MOT_DE_PASSE_TEST = "mot-de-passe-test"


def _en_tete_basic(identifiant: str, mot_de_passe: str) -> dict[str, str]:
    """Construit l'en-tête `Authorization: Basic ...` à la main plutôt que de dépendre du
    paramètre `auth=` du client de test : les versions de `TestClient` diffèrent sur ce point
    selon la version de starlette installée, l'en-tête HTTP lui-même est stable partout."""
    jeton = base64.b64encode(f"{identifiant}:{mot_de_passe}".encode()).decode("ascii")
    return {"Authorization": f"Basic {jeton}"}


@pytest.fixture()
def _authentification(monkeypatch: pytest.MonkeyPatch):
    """Configure les identifiants HTTP Basic pour la durée du test, puis vide le cache de
    `get_settings()` (partagé pour tout le processus, voir son docstring) avant et après :
    sans ce nettoyage, un test qui s'exécuterait plus tôt sans ces variables d'environnement
    figerait dans le cache un `Settings` sans identifiants conseiller, et un test qui
    s'exécuterait après celui-ci hériterait au contraire des identifiants de test."""
    monkeypatch.setenv("CONSEILLER_IDENTIFIANT", IDENTIFIANT_TEST)
    monkeypatch.setenv("CONSEILLER_MOT_DE_PASSE", MOT_DE_PASSE_TEST)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client(tmp_path: Path, _authentification: None) -> TestClient:
    app = create_app()
    journal = JournalFeedback(tmp_path / "feedback.jsonl")
    app.dependency_overrides[get_journal_feedback] = lambda: journal
    client = TestClient(app, headers=_en_tete_basic(IDENTIFIANT_TEST, MOT_DE_PASSE_TEST))
    client.journal = journal  # type: ignore[attr-defined]
    return client


REQUETE_DE_BASE = {
    "session": 2025,
    "identifiant_formation": "F1",
    "type_bac": "bg",
    "boursier": False,
}


def test_feedback_retenue_ne_requiert_aucun_motif(client: TestClient) -> None:
    reponse = client.post("/feedback", json={**REQUETE_DE_BASE, "decision": "retenue"})
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["enregistre"] is True
    assert corps["identifiant_feedback"]
    assert corps["horodatage"]


def test_feedback_ecartee_sans_motif_est_refusee(client: TestClient) -> None:
    reponse = client.post("/feedback", json={**REQUETE_DE_BASE, "decision": "ecartee"})
    assert reponse.status_code == 422
    assert "motif' est obligatoire" in json.dumps(reponse.json())


def test_feedback_ecartee_avec_motif_est_enregistree_et_journalisee(client: TestClient) -> None:
    reponse = client.post(
        "/feedback", json={**REQUETE_DE_BASE, "decision": "ecartee", "motif": "Établissement fermé depuis 2024."}
    )
    assert reponse.status_code == 201

    enregistrements = client.journal.lire_tout()  # type: ignore[attr-defined]
    assert len(enregistrements) == 1
    assert enregistrements[0].decision == "ecartee"
    assert enregistrements[0].motif == "Établissement fermé depuis 2024."
    assert enregistrements[0].identifiant_formation == "F1"


def test_feedback_ne_journalise_aucune_donnee_de_candidat(client: TestClient) -> None:
    """Cohérent avec l'AIPD (§2.3) : ni profil, ni saisie du candidat, uniquement la cellule et
    la décision du conseiller."""
    reponse = client.post("/feedback", json={**REQUETE_DE_BASE, "decision": "retenue"})
    assert reponse.status_code == 201

    contenu = client.journal.chemin.read_text(encoding="utf-8")  # type: ignore[attr-defined]
    champs_attendus = {
        "identifiant_feedback",
        "horodatage",
        "session",
        "identifiant_formation",
        "type_bac",
        "boursier",
        "decision",
        "motif",
        "identifiant_conseiller",
    }
    ligne = json.loads(contenu.strip().splitlines()[0])
    assert set(ligne.keys()) == champs_attendus


def test_feedback_refuse_un_champ_genre(client: TestClient) -> None:
    reponse = client.post("/feedback", json={**REQUETE_DE_BASE, "decision": "retenue", "genre": "F"})
    assert reponse.status_code == 422


def test_feedback_decision_hors_domaine_est_refusee(client: TestClient) -> None:
    reponse = client.post("/feedback", json={**REQUETE_DE_BASE, "decision": "approuvee"})
    assert reponse.status_code == 422


def test_feedback_refuse_un_champ_identifiant_conseiller_declaratif(client: TestClient) -> None:
    """Non-régression du motif corrigé par la revue de sécurité : un appelant ne peut plus
    déclarer lui-même l'identifiant du conseiller dans le corps de la requête, même s'il est
    par ailleurs authentifié — voir `schemas.RequeteFeedback`."""
    reponse = client.post(
        "/feedback", json={**REQUETE_DE_BASE, "decision": "retenue", "identifiant_conseiller": "usurpe"}
    )
    assert reponse.status_code == 422


# ─── Authentification (revue de sécurité) ────────────────────────────────────


def test_feedback_sans_en_tete_dauthentification_est_refuse(tmp_path: Path, _authentification: None) -> None:
    app = create_app()
    app.dependency_overrides[get_journal_feedback] = lambda: JournalFeedback(tmp_path / "feedback.jsonl")
    client_sans_auth = TestClient(app)  # aucun `auth=` : pas d'en-tête Authorization
    reponse = client_sans_auth.post("/feedback", json={**REQUETE_DE_BASE, "decision": "retenue"})
    assert reponse.status_code == 401
    assert reponse.headers["www-authenticate"] == "Basic"


def test_feedback_avec_mauvais_mot_de_passe_est_refuse(tmp_path: Path, _authentification: None) -> None:
    app = create_app()
    app.dependency_overrides[get_journal_feedback] = lambda: JournalFeedback(tmp_path / "feedback.jsonl")
    client_mauvais_mdp = TestClient(app, headers=_en_tete_basic(IDENTIFIANT_TEST, "mauvais-mot-de-passe"))
    reponse = client_mauvais_mdp.post("/feedback", json={**REQUETE_DE_BASE, "decision": "retenue"})
    assert reponse.status_code == 401


def test_feedback_avec_authentification_valide_derive_lidentifiant_du_conseiller(client: TestClient) -> None:
    """Le 200 (ici 201, création) attendu avec un en-tête valide — et surtout, l'identifiant
    journalisé est celui du principal authentifié, jamais une valeur du corps de la requête
    (que le schéma ne porte d'ailleurs plus)."""
    reponse = client.post("/feedback", json={**REQUETE_DE_BASE, "decision": "retenue"})
    assert reponse.status_code == 201

    enregistrements = client.journal.lire_tout()  # type: ignore[attr-defined]
    assert enregistrements[0].identifiant_conseiller == IDENTIFIANT_TEST


def test_feedback_authentification_non_configuree_repond_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sans `CONSEILLER_IDENTIFIANT`/`CONSEILLER_MOT_DE_PASSE` dans l'environnement, la route
    refuse explicitement plutôt que d'accepter n'importe quel appelant (voir `api/auth.py`)."""
    monkeypatch.delenv("CONSEILLER_IDENTIFIANT", raising=False)
    monkeypatch.delenv("CONSEILLER_MOT_DE_PASSE", raising=False)
    get_settings.cache_clear()
    try:
        app = create_app()
        app.dependency_overrides[get_journal_feedback] = lambda: JournalFeedback(tmp_path / "feedback.jsonl")
        client_sans_config = TestClient(app, headers=_en_tete_basic("peu-importe", "peu-importe"))
        reponse = client_sans_config.post("/feedback", json={**REQUETE_DE_BASE, "decision": "retenue"})
        assert reponse.status_code == 503
    finally:
        get_settings.cache_clear()


# ─── Limitation de débit (revue de sécurité) ─────────────────────────────────


def test_feedback_au_dela_de_la_limite_repond_429(tmp_path: Path, _authentification: None) -> None:
    from edumatch.api.deps import get_limiteur_feedback
    from edumatch.api.rate_limit import LimiteurDebit

    limiteur = LimiteurDebit(limite=1, fenetre_secondes=60.0)  # une seule instance, partagée entre les appels
    app = create_app()
    app.dependency_overrides[get_journal_feedback] = lambda: JournalFeedback(tmp_path / "feedback.jsonl")
    app.dependency_overrides[get_limiteur_feedback] = lambda: limiteur
    client_limite = TestClient(app, headers=_en_tete_basic(IDENTIFIANT_TEST, MOT_DE_PASSE_TEST))

    premiere = client_limite.post("/feedback", json={**REQUETE_DE_BASE, "decision": "retenue"})
    assert premiere.status_code == 201

    seconde = client_limite.post("/feedback", json={**REQUETE_DE_BASE, "decision": "retenue"})
    assert seconde.status_code == 429
