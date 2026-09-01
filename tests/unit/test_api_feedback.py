"""Test de contrat de `/feedback` (E29) : l'écartement doit être motivé, horodaté, journalisé
(R6, `docs/sous-docs-projets/05-gouvernance/risques.md`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from edumatch.api.deps import get_journal_feedback
from edumatch.api.feedback_store import JournalFeedback
from edumatch.api.main import create_app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app()
    journal = JournalFeedback(tmp_path / "feedback.jsonl")
    app.dependency_overrides[get_journal_feedback] = lambda: journal
    client = TestClient(app)
    client.journal = journal  # type: ignore[attr-defined]
    return client


REQUETE_DE_BASE = {
    "session": 2025,
    "identifiant_formation": "F1",
    "type_bac": "bg",
    "boursier": False,
    "identifiant_conseiller": "conseiller-042",
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
