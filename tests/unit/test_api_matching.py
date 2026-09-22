"""Test de contrat de `/matching`.

Fixtures reprises de `tests/unit/test_matching_score.py` : un `EtatMatching`
construit à la main plutôt que par `api.state.construire_etat_matching`
(coûteux — entraînement complet et lecture du stock Sirene), pour isoler le
contrat HTTP de la construction de l'état, déjà testée ailleurs.

Depuis la revue de sécurité (motif A), `/matching` exige un compte conseiller nominatif comme
`/feedback` : `IDENTIFIANT_TEST`/`MOT_DE_PASSE_TEST` sont les identifiants de démonstration
injectés par la fixture `_authentification` via `CONSEILLER_COMPTES`.
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
from edumatch.api.deps import get_etat_matching, get_journal_audit, get_limiteur_matching
from edumatch.api.main import create_app
from edumatch.api.rate_limit import LimiteurDebit
from edumatch.api.state import EtatMatching, _artefacts_debouches_indisponibles
from edumatch.config import get_settings
from edumatch.matching.debouches import (
    ArtefactsDebouches,
    RapportCorrespondanceFormation,
    RapportKAnonymat,
)
from edumatch.matching.score import MISE_EN_GARDE_ACCESSIBILITE

IDENTIFIANT_TEST = "conseiller-test"
MOT_DE_PASSE_TEST = "mot-de-passe-test"
IDENTIFIANT_AUTRE_TEST = "autre-conseiller-test"
MOT_DE_PASSE_AUTRE_TEST = "autre-mot-de-passe-test"


def _en_tete_basic(identifiant: str, mot_de_passe: str) -> dict[str, str]:
    jeton = base64.b64encode(f"{identifiant}:{mot_de_passe}".encode()).decode("ascii")
    return {"Authorization": f"Basic {jeton}"}


@pytest.fixture()
def _authentification(monkeypatch: pytest.MonkeyPatch):
    """Deux comptes nominatifs configurés (voir `test_matching_deux_comptes_distincts_sont_acceptes`) :
    même politique de nettoyage du cache que `test_api_feedback.py`."""
    comptes = (
        f"{IDENTIFIANT_TEST}:{calculer_empreinte(MOT_DE_PASSE_TEST)};"
        f"{IDENTIFIANT_AUTRE_TEST}:{calculer_empreinte(MOT_DE_PASSE_AUTRE_TEST)}"
    )
    monkeypatch.setenv("CONSEILLER_COMPTES", comptes)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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
            },
            {
                "cod_aff_form": "F2",
                "fili": "Licence",  # affinité nulle si type_formation="BTS" est demandé
                "fil_lib_voe_acc": "Mathématiques",
                "form_lib_voe_acc": "Licence Mathématiques",
                "dep": "75",
                "type_bac": "bg",
                "boursier": False,
                "taux_predit": 0.95,
            },
            {
                "cod_aff_form": "F3",
                "fili": "BTS",
                "fil_lib_voe_acc": "BTS SIO",
                "form_lib_voe_acc": "BTS Services informatiques aux organisations",
                "dep": "75",
                "type_bac": "bp",  # autre dimension de cellule : jamais mêlée à bg
                "boursier": False,
                "taux_predit": 0.3,
            },
        ]
    )


def _artefacts_debouches() -> ArtefactsDebouches:
    correspondance = pl.DataFrame({"fil_lib_voe_acc": ["BTS SIO"], "code_rncp_ideo": ["RNCP001"]})
    table_naf = pl.DataFrame({"code_rncp_ideo": ["RNCP001"], "naf_division": ["62"]})
    agregat = pl.DataFrame({"departement": ["75"], "naf_division": ["62"], "nb_actifs_employeurs_diffusibles": [25]})
    cellules_non_vides = agregat.select("departement", "naf_division")
    rapport_k = RapportKAnonymat("departement x division_naf", 5, 1, 0, 25, 0)
    rapport_corr = RapportCorrespondanceFormation(1, 1, 1, 1, [("BTS SIO", "RNCP001")])
    return ArtefactsDebouches(
        correspondance_formation=correspondance,
        table_naf_rome_formation=table_naf,
        agregat_conserve=agregat,
        cellules_non_vides=cellules_non_vides,
        rapport_k_anonymat=rapport_k,
        rapport_correspondance=rapport_corr,
    )


def _etat(*, disponible: bool = True) -> EtatMatching:
    artefacts = _artefacts_debouches() if disponible else _artefacts_debouches_indisponibles()
    return EtatMatching(
        settings=None,  # jamais lu par les routes : `get_settings()` y est appelé séparément
        session_courante=2025,
        catalogue=_catalogue(),
        artefacts_debouches=artefacts,
        debouches_disponible=disponible,
        motif_indisponibilite_debouches=None if disponible else "stock Sirene introuvable",
    )


@pytest.fixture()
def client(tmp_path: Path, _authentification: None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_etat_matching] = lambda: _etat()
    journal = JournalAudit(tmp_path / "journal.jsonl")
    app.dependency_overrides[get_journal_audit] = lambda: journal
    client = TestClient(app, headers=_en_tete_basic(IDENTIFIANT_TEST, MOT_DE_PASSE_TEST))
    client.journal_audit = journal  # type: ignore[attr-defined]
    return client


@pytest.fixture()
def client_debouches_indisponibles(tmp_path: Path, _authentification: None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_etat_matching] = lambda: _etat(disponible=False)
    app.dependency_overrides[get_journal_audit] = lambda: JournalAudit(tmp_path / "journal.jsonl")
    return TestClient(app, headers=_en_tete_basic(IDENTIFIANT_TEST, MOT_DE_PASSE_TEST))


# ─── Contrat de base ─────────────────────────────────────────────────────────


def test_matching_ordonne_les_recommandations_par_score_decroissant(client: TestClient) -> None:
    reponse = client.post(
        "/matching",
        json={"type_bac": "bg", "boursier": False, "type_formation": "BTS", "departement": "75", "top_n": 10},
    )
    assert reponse.status_code == 200
    corps = reponse.json()

    identifiants = [r["identifiant_formation"] for r in corps["recommandations"]]
    # F3 est exclue : elle relève de la dimension (bp) hors du profil déclaré (bg).
    assert identifiants == ["F1", "F2"]
    scores = {r["identifiant_formation"]: r["score"] for r in corps["recommandations"]}
    assert scores["F2"] == 0.0  # filtre dur du type de formation
    assert scores["F1"] > 0.0


def test_matching_porte_la_mise_en_garde_accessibilite(client: TestClient) -> None:
    reponse = client.post("/matching", json={"type_bac": "bg", "boursier": False, "departement": "75"})
    corps = reponse.json()
    assert corps["avertissement_accessibilite"] == MISE_EN_GARDE_ACCESSIBILITE
    assert "0,0758" in corps["avertissement_accessibilite"]


def test_matching_porte_lavis_dassistance_article_22(client: TestClient) -> None:
    reponse = client.post("/matching", json={"type_bac": "bg", "boursier": False})
    corps = reponse.json()
    assert "assiste un conseiller" in corps["avis_assistance"]
    assert "décision automatisée" in corps["avis_assistance"]


def test_matching_declare_le_terme_debouches_disponible_avec_son_motif(client: TestClient) -> None:
    reponse = client.post("/matching", json={"type_bac": "bg", "boursier": False, "departement": "75"})
    corps = reponse.json()
    debouches_f1 = next(r["debouches"] for r in corps["recommandations"] if r["identifiant_formation"] == "F1")
    assert debouches_f1["statut"] == "mesure"
    assert debouches_f1["disponible"] is True
    assert "Sirene" in debouches_f1["motif"]
    assert corps["debouches_disponible"] is True


def test_matching_sans_departement_rend_le_terme_debouches_neutre_et_motive(client: TestClient) -> None:
    reponse = client.post("/matching", json={"type_bac": "bg", "boursier": False})
    corps = reponse.json()
    debouches_f1 = next(r["debouches"] for r in corps["recommandations"] if r["identifiant_formation"] == "F1")
    assert debouches_f1["valeur"] == 1.0
    assert debouches_f1["disponible"] is False
    assert "Aucun département" in debouches_f1["motif"]


# ─── Dégradation du terme de débouchés (infrastructure indisponible) ────────


def test_matching_service_debouches_indisponible_ne_masque_rien(
    client_debouches_indisponibles: TestClient,
) -> None:
    reponse = client_debouches_indisponibles.post(
        "/matching", json={"type_bac": "bg", "boursier": False, "departement": "75"}
    )
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["debouches_disponible"] is False
    assert corps["motif_indisponibilite_debouches"] == "stock Sirene introuvable"
    debouches_f1 = next(r["debouches"] for r in corps["recommandations"] if r["identifiant_formation"] == "F1")
    assert debouches_f1["disponible"] is False
    assert debouches_f1["valeur"] == 1.0  # neutre, jamais un zéro qui supprimerait la recommandation


# ─── Validation stricte du contrat d'entrée ──────────────────────────────────


def test_matching_refuse_un_champ_genre(client: TestClient) -> None:
    """Contrat de non-régression de l'ADR 0011 : le genre n'a sa place dans aucun schéma
    d'entrée, y compris s'il est fourni par un client mal intentionné ou distrait."""
    reponse = client.post("/matching", json={"type_bac": "bg", "boursier": False, "genre": "F"})
    assert reponse.status_code == 422


def test_matching_refuse_labsence_de_type_bac(client: TestClient) -> None:
    reponse = client.post("/matching", json={"boursier": False})
    assert reponse.status_code == 422


def test_matching_refuse_un_type_bac_hors_domaine(client: TestClient) -> None:
    reponse = client.post("/matching", json={"type_bac": "bg_invalide", "boursier": False})
    assert reponse.status_code == 422


def test_matching_refuse_un_departement_mal_forme(client: TestClient) -> None:
    reponse = client.post("/matching", json={"type_bac": "bg", "boursier": False, "departement": "abc"})
    assert reponse.status_code == 422


def test_matching_catalogue_vide_ne_leve_pas_et_declare_zero_recommandation(client: TestClient) -> None:
    reponse = client.post("/matching", json={"type_bac": "bt", "boursier": True})
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["recommandations"] == []
    assert corps["n_formations_disponibles"] == 0


def test_matching_plafond_de_catalogue_renvoie_422_explicite(_authentification: None) -> None:
    """Le catalogue au-delà du plafond de configuration n'est jamais tronqué en silence :
    l'API refuse et explique comment réduire le périmètre (voir `configs/base.yaml`,
    `api.max_formations_evaluees`)."""
    catalogue_large = pd.DataFrame(
        [
            {
                "cod_aff_form": f"F{i}",
                "fili": "BTS",
                "fil_lib_voe_acc": "BTS SIO",
                "form_lib_voe_acc": "BTS Services informatiques aux organisations",
                "dep": "75",
                "type_bac": "bg",
                "boursier": False,
                "taux_predit": 0.5,
            }
            for i in range(get_settings().api.max_formations_evaluees + 1)
        ]
    )
    etat = EtatMatching(
        settings=None,
        session_courante=2025,
        catalogue=catalogue_large,
        artefacts_debouches=_artefacts_debouches_indisponibles(),
        debouches_disponible=False,
        motif_indisponibilite_debouches="indisponible pour ce test",
    )
    app = create_app()
    app.dependency_overrides[get_etat_matching] = lambda: etat
    client = TestClient(app, headers=_en_tete_basic(IDENTIFIANT_TEST, MOT_DE_PASSE_TEST))

    reponse = client.post("/matching", json={"type_bac": "bg", "boursier": False})
    assert reponse.status_code == 422
    detail = reponse.json()["detail"]
    assert "plafond" in detail
    # Seul le département réduit le périmètre du plafond : le domaine et le type de formation
    # s'appliquent après, dans l'affinité : les suggérer induirait le conseiller en erreur.
    assert "département" in detail
    assert "domaine" not in detail
    assert "type de formation" not in detail


def test_matching_service_non_initialise_repond_503(_authentification: None) -> None:
    """Sans état chargé (cycle de vie non exécuté, voir `TestClient` sans bloc `with`), la
    route répond 503 plutôt que de planter — voir `api/deps.get_etat_matching`."""
    client = TestClient(create_app(), headers=_en_tete_basic(IDENTIFIANT_TEST, MOT_DE_PASSE_TEST))
    reponse = client.post("/matching", json={"type_bac": "bg", "boursier": False})
    assert reponse.status_code == 503


# ─── Limitation de débit (revue de sécurité) ─────────────────────────────────


def test_matching_au_dela_de_la_limite_repond_429(tmp_path: Path, _authentification: None) -> None:
    """Le plafond de débit (revue de sécurité) reste appliqué par adresse IP — voir
    `api/rate_limit.py`. `TestClient` porte toujours la même adresse simulée (`testclient`),
    donc les deux appels partagent la même identité."""
    etat = _etat()
    limiteur = LimiteurDebit(limite=1, fenetre_secondes=60.0)  # une seule instance, partagée entre les appels
    app = create_app()
    app.dependency_overrides[get_etat_matching] = lambda: etat
    app.dependency_overrides[get_journal_audit] = lambda: JournalAudit(tmp_path / "journal.jsonl")
    app.dependency_overrides[get_limiteur_matching] = lambda: limiteur
    client = TestClient(app, headers=_en_tete_basic(IDENTIFIANT_TEST, MOT_DE_PASSE_TEST))

    premiere = client.post("/matching", json={"type_bac": "bg", "boursier": False})
    assert premiere.status_code == 200

    seconde = client.post("/matching", json={"type_bac": "bg", "boursier": False})
    assert seconde.status_code == 429


# ─── Authentification nominative (revue de sécurité, motif A) ───────────────


def test_matching_sans_en_tete_dauthentification_est_refuse(tmp_path: Path, _authentification: None) -> None:
    app = create_app()
    app.dependency_overrides[get_etat_matching] = lambda: _etat()
    app.dependency_overrides[get_journal_audit] = lambda: JournalAudit(tmp_path / "journal.jsonl")
    client_sans_auth = TestClient(app)

    reponse = client_sans_auth.post("/matching", json={"type_bac": "bg", "boursier": False})

    assert reponse.status_code == 401
    assert reponse.headers["www-authenticate"] == "Basic"


def test_matching_deux_comptes_distincts_sont_acceptes(tmp_path: Path, _authentification: None) -> None:
    """Deux conseillers différents, chacun avec son propre mot de passe, peuvent tous les deux
    utiliser le service — non-régression du compte partagé unique remplacé (motif A)."""
    app = create_app()
    app.dependency_overrides[get_etat_matching] = lambda: _etat()
    app.dependency_overrides[get_journal_audit] = lambda: JournalAudit(tmp_path / "journal.jsonl")

    client_alice = TestClient(app, headers=_en_tete_basic(IDENTIFIANT_TEST, MOT_DE_PASSE_TEST))
    client_bruno = TestClient(app, headers=_en_tete_basic(IDENTIFIANT_AUTRE_TEST, MOT_DE_PASSE_AUTRE_TEST))

    assert client_alice.post("/matching", json={"type_bac": "bg", "boursier": False}).status_code == 200
    assert client_bruno.post("/matching", json={"type_bac": "bg", "boursier": False}).status_code == 200


def test_matching_journalise_lidentifiant_du_conseiller_authentifie(tmp_path: Path, _authentification: None) -> None:
    """L'identité authentifiée est journalisée à chaque inférence (T5, motif A) : sans elle, une
    inférence contestée ne remonterait à aucune personne identifiée."""
    app = create_app()
    app.dependency_overrides[get_etat_matching] = lambda: _etat()
    chemin_journal = tmp_path / "journal.jsonl"
    app.dependency_overrides[get_journal_audit] = lambda: JournalAudit(chemin_journal)
    client_bruno = TestClient(app, headers=_en_tete_basic(IDENTIFIANT_AUTRE_TEST, MOT_DE_PASSE_AUTRE_TEST))

    reponse = client_bruno.post("/matching", json={"type_bac": "bg", "boursier": False})
    assert reponse.status_code == 200

    ligne = json.loads(chemin_journal.read_text(encoding="utf-8").strip().splitlines()[0])
    assert ligne["entrees"]["identifiant_conseiller"] == IDENTIFIANT_AUTRE_TEST


def test_matching_authentification_non_configuree_repond_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONSEILLER_COMPTES", raising=False)
    get_settings.cache_clear()
    try:
        app = create_app()
        app.dependency_overrides[get_etat_matching] = lambda: _etat()
        app.dependency_overrides[get_journal_audit] = lambda: JournalAudit(tmp_path / "journal.jsonl")
        client_sans_config = TestClient(app, headers=_en_tete_basic("peu-importe", "peu-importe"))
        reponse = client_sans_config.post("/matching", json={"type_bac": "bg", "boursier": False})
        assert reponse.status_code == 503
    finally:
        get_settings.cache_clear()


def test_health_reste_ouvert_sans_authentification() -> None:
    """Non-régression : étendre l'authentification à l'écran et à `/matching` ne doit jamais
    gagner `/health`, utilisé par les sondes d'orchestration."""
    client = TestClient(create_app())
    reponse = client.get("/health")
    assert reponse.status_code == 200
