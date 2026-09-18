"""Test de contrat du journal d'audit : `/matching` doit journaliser chaque inférence
(horodatage, exécution, version du modèle, entrées, sortie — article 12), sans jamais écrire
cette trace via `logging` (voir le docstring de `api/audit.py` et `api/errors.py`).

Depuis la revue de sécurité (motif A), `/matching` exige un compte conseiller nominatif comme
`/feedback` : `IDENTIFIANT_TEST`/`MOT_DE_PASSE_TEST` sont les identifiants de démonstration
injectés par la fixture `client` via `CONSEILLER_COMPTES`.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pandas as pd
import polars as pl
import pytest
from fastapi.testclient import TestClient

from edumatch.api.audit import JournalAudit
from edumatch.api.auth import calculer_empreinte
from edumatch.api.deps import get_etat_matching, get_journal_audit
from edumatch.api.main import create_app
from edumatch.api.state import EtatMatching
from edumatch.config import get_settings
from edumatch.matching.debouches import (
    ArtefactsDebouches,
    RapportCorrespondanceFormation,
    RapportKAnonymat,
)

IDENTIFIANT_TEST = "conseiller-test"
MOT_DE_PASSE_TEST = "mot-de-passe-test"


def _en_tete_basic(identifiant: str, mot_de_passe: str) -> dict[str, str]:
    jeton = base64.b64encode(f"{identifiant}:{mot_de_passe}".encode()).decode("ascii")
    return {"Authorization": f"Basic {jeton}"}


def _catalogue() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cod_aff_form": "F1",
                "fili": "BTS",
                "fil_lib_voe_acc": "BTS SIO",
                "form_lib_voe_acc": "BTS Services informatiques aux organisations",
                "dep": "75",
                "type_bac": "bg",
                "boursier": False,
                "taux_predit": 0.6,
            }
        ]
    )


def _artefacts_debouches() -> ArtefactsDebouches:
    correspondance = pl.DataFrame({"fil_lib_voe_acc": ["BTS SIO"], "code_rncp_ideo": ["RNCP001"]})
    table_naf = pl.DataFrame({"code_rncp_ideo": ["RNCP001"], "naf_division": ["62"]})
    agregat = pl.DataFrame({"departement": ["75"], "naf_division": ["62"], "nb_actifs_employeurs_diffusibles": [25]})
    cellules_non_vides = agregat.select("departement", "naf_division")
    return ArtefactsDebouches(
        correspondance_formation=correspondance,
        table_naf_rome_formation=table_naf,
        agregat_conserve=agregat,
        cellules_non_vides=cellules_non_vides,
        rapport_k_anonymat=RapportKAnonymat("departement x division_naf", 5, 1, 0, 25, 0),
        rapport_correspondance=RapportCorrespondanceFormation(1, 1, 1, 1, [("BTS SIO", "RNCP001")]),
    )


def _etat() -> EtatMatching:
    return EtatMatching(
        settings=None,  # type: ignore[arg-type]
        session_courante=2025,
        catalogue=_catalogue(),
        artefacts_debouches=_artefacts_debouches(),
        debouches_disponible=True,
        motif_indisponibilite_debouches=None,
    )


@pytest.fixture()
def _authentification(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CONSEILLER_COMPTES", f"{IDENTIFIANT_TEST}:{calculer_empreinte(MOT_DE_PASSE_TEST)}")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client(tmp_path: Path, _authentification: None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_etat_matching] = lambda: _etat()
    journal = JournalAudit(tmp_path / "journal.jsonl")
    app.dependency_overrides[get_journal_audit] = lambda: journal
    client = TestClient(app, headers=_en_tete_basic(IDENTIFIANT_TEST, MOT_DE_PASSE_TEST))
    client.journal_audit = journal  # type: ignore[attr-defined]
    return client


def test_matching_journalise_une_inference_avec_entrees_et_sortie(client: TestClient) -> None:
    reponse = client.post(
        "/matching", json={"type_bac": "bg", "boursier": False, "departement": "75", "top_n": 5}
    )
    assert reponse.status_code == 200

    enregistrements = client.journal_audit.lire_tout()  # type: ignore[attr-defined]
    assert len(enregistrements) == 1
    ligne = enregistrements[0]
    assert ligne.identifiant_audit
    assert ligne.horodatage
    assert ligne.identifiant_execution
    assert ligne.version_modele
    assert ligne.entrees == {
        "session": 2025,
        "type_bac": "bg",
        "boursier": False,
        "type_formation": None,
        "domaine": None,
        "departement": "75",
        "identifiant_conseiller": IDENTIFIANT_TEST,
    }
    assert ligne.sortie["n_formations_disponibles"] == 1
    assert ligne.sortie["recommandations"][0]["identifiant_formation"] == "F1"
    assert ligne.decision_conseiller is None
    assert ligne.pseudonymise is False


def test_matching_journalise_meme_une_reponse_vide(client: TestClient) -> None:
    """Aucune formation ne correspond au profil (autre type de bac) : c'est un événement du
    système au même titre, pas une exception qui dispenserait de la trace."""
    reponse = client.post("/matching", json={"type_bac": "bp", "boursier": False})
    assert reponse.status_code == 200
    assert reponse.json()["n_formations_disponibles"] == 0

    enregistrements = client.journal_audit.lire_tout()  # type: ignore[attr-defined]
    assert len(enregistrements) == 1
    assert enregistrements[0].sortie["n_formations_disponibles"] == 0
    assert enregistrements[0].sortie["recommandations"] == []


def test_matching_journalise_un_appel_par_requete(client: TestClient) -> None:
    client.post("/matching", json={"type_bac": "bg", "boursier": False})
    client.post("/matching", json={"type_bac": "bg", "boursier": False})
    enregistrements = client.journal_audit.lire_tout()  # type: ignore[attr-defined]
    assert len(enregistrements) == 2
    assert enregistrements[0].identifiant_execution != enregistrements[1].identifiant_execution


def test_journal_audit_ecrit_uniquement_dans_son_fichier_dedie(client: TestClient) -> None:
    """Cohérent avec `api/errors.py` : le journal d'audit est un fichier protégé, distinct des
    journaux applicatifs — la ligne écrite porte les variables d'entrée en clair, ce que
    `logging` ne doit jamais faire ailleurs dans l'API."""
    client.post("/matching", json={"type_bac": "bg", "boursier": False, "departement": "75"})
    contenu = client.journal_audit.chemin.read_text(encoding="utf-8")  # type: ignore[attr-defined]
    ligne = json.loads(contenu.strip().splitlines()[0])
    champs_attendus = {
        "identifiant_audit",
        "horodatage",
        "identifiant_execution",
        "version_modele",
        "empreinte_commit",
        "entrees",
        "sortie",
        "decision_conseiller",
        "pseudonymise",
    }
    assert set(ligne.keys()) == champs_attendus
