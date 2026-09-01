"""Contrat entre l'écran conseiller (`api/static/app.js`, E31) et les réponses réelles de l'API.

`app.js` ne peut pas être testé par `pytest` (ce n'est pas du Python) : ce test vérifie, côté
serveur, que chaque champ que `app.js` lit dans les réponses de `/matching` et `/explain`, et
chaque champ qu'il envoie à `/feedback`, existe bien dans le contrat réel — pour qu'une
évolution de `api/schemas.py` qui renommerait un champ casse ce test plutôt que l'écran, en
silence, uniquement constatable au clic dans un navigateur.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl
import pytest
from fastapi.testclient import TestClient

from edumatch.api.deps import get_etat_explicabilite, get_etat_matching, get_journal_audit, get_journal_feedback
from edumatch.api.feedback_store import JournalFeedback
from edumatch.api.main import create_app
from edumatch.api.audit import JournalAudit
from edumatch.api.state import EtatExplicabilite, EtatMatching
from edumatch.matching.debouches import ArtefactsDebouches, RapportCorrespondanceFormation, RapportKAnonymat

DOSSIER_STATIQUE = Path(__file__).resolve().parents[2] / "src" / "edumatch" / "api" / "static"
JS = (DOSSIER_STATIQUE / "app.js").read_text(encoding="utf-8")

# Chaque chemin que `app.js` déréférence sur la réponse de `/matching` (voir
# `construireDetailScore`, `afficherResultats`, `construireActions`).
CHAMPS_MATCHING_RECOMMANDATION = (
    "identifiant_formation",
    "libelle_formation",
    "score",
    "affinite.filtre_type_formation_respecte",
    "affinite.filtre_domaine_respecte",
    "affinite.valeur",
    "accessibilite.valeur",
    "accessibilite.valeur_brute",
    "debouches.disponible",
    "debouches.motif",
)
CHAMPS_MATCHING_RACINE = (
    "session",
    "recommandations",
    "avertissement_accessibilite",
    "avertissement_debouches",
    "debouches_disponible",
    "motif_indisponibilite_debouches",
)
CHAMPS_EXPLAIN = ("prediction", "valeur_base", "avertissement_accessibilite", "contributions")
CHAMPS_CONTRIBUTION = ("variable", "contribution")
CHAMPS_ENVOYES_A_FEEDBACK = (
    "session",
    "identifiant_formation",
    "type_bac",
    "boursier",
    "decision",
    "motif",
    "identifiant_conseiller",
)


def _lire_chemin(objet: dict, chemin: str) -> None:
    valeur = objet
    for segment in chemin.split("."):
        assert segment in valeur, f"champ '{chemin}' absent de la réponse : manque '{segment}'"
        valeur = valeur[segment]


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


def _etat_matching() -> EtatMatching:
    return EtatMatching(
        settings=None,
        session_courante=2025,
        catalogue=_catalogue(),
        artefacts_debouches=_artefacts_debouches(),
        debouches_disponible=True,
        motif_indisponibilite_debouches=None,
    )


def _etat_explicabilite() -> EtatExplicabilite:
    precalcul = pd.DataFrame(
        [
            {
                "session": 2025,
                "cod_aff_form": "F1",
                "type_bac": "bg",
                "boursier": False,
                "prediction": 0.62,
                "valeur_base": 0.50,
                "shap__fili": 0.05,
            }
        ]
    )
    colonnes_shap = tuple(c for c in precalcul.columns if c.startswith("shap__"))
    return EtatExplicabilite(precalcul=precalcul, colonnes_shap=colonnes_shap, chemin=None)


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_etat_matching] = lambda: _etat_matching()
    app.dependency_overrides[get_etat_explicabilite] = lambda: _etat_explicabilite()
    app.dependency_overrides[get_journal_audit] = lambda: JournalAudit(tmp_path / "audit.jsonl")
    app.dependency_overrides[get_journal_feedback] = lambda: JournalFeedback(tmp_path / "feedback.jsonl")
    return TestClient(app)


def test_reponse_matching_porte_tous_les_champs_lus_par_app_js(client: TestClient) -> None:
    reponse = client.post("/matching", json={"type_bac": "bg", "boursier": False, "departement": "75"})
    assert reponse.status_code == 200
    corps = reponse.json()

    for champ in CHAMPS_MATCHING_RACINE:
        assert champ in corps, f"champ racine '{champ}' absent de /matching"
    assert corps["recommandations"], "au moins une recommandation attendue pour ce test de contrat"
    for champ in CHAMPS_MATCHING_RECOMMANDATION:
        _lire_chemin(corps["recommandations"][0], champ)


def test_reponse_explain_porte_tous_les_champs_lus_par_app_js(client: TestClient) -> None:
    reponse = client.get(
        "/explain", params={"session": 2025, "cod_aff_form": "F1", "type_bac": "bg", "boursier": False}
    )
    assert reponse.status_code == 200
    corps = reponse.json()

    for champ in CHAMPS_EXPLAIN:
        assert champ in corps, f"champ '{champ}' absent de /explain"
    assert corps["contributions"], "au moins une contribution attendue pour ce test de contrat"
    for champ in CHAMPS_CONTRIBUTION:
        assert champ in corps["contributions"][0]


def test_requete_feedback_envoyee_par_app_js_est_acceptee(client: TestClient) -> None:
    """Vérifie que le corps que `enregistrerDecision` construit (voir `app.js`) est bien celui
    qu'accepte `RequeteFeedback` — les mêmes noms de champs, dans les deux sens."""
    corps = {
        "session": 2025,
        "identifiant_formation": "F1",
        "type_bac": "bg",
        "boursier": False,
        "decision": "ecartee",
        "motif": "Établissement fermé.",
        "identifiant_conseiller": "conseiller-test",
    }
    assert set(corps) == set(CHAMPS_ENVOYES_A_FEEDBACK)

    reponse = client.post("/feedback", json=corps)
    assert reponse.status_code == 201


def test_app_js_reference_bien_les_noms_de_champs_du_contrat() -> None:
    """Défense en profondeur : si un des noms de champs listés ci-dessus disparaissait du
    fichier `app.js` (faute de frappe lors d'une future modification), ce test le signale
    séparément des tests de contrat serveur ci-dessus."""
    for champ in (*CHAMPS_MATCHING_RACINE, *CHAMPS_MATCHING_RECOMMANDATION, *CHAMPS_EXPLAIN, *CHAMPS_CONTRIBUTION):
        nom_final = champ.split(".")[-1]
        assert nom_final in JS, f"'{nom_final}' n'apparaît pas dans app.js"
