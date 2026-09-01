"""Test de contrat de `/explain` (E29) : sert le précalcul SHAP (E25), jamais un recalcul.

Le précalcul est construit à la main plutôt que via `models.explain.executer` (coûteux —
entraînement complet) : `tests/data/test_api_explain_run.py` couvre le chemin de bout en bout
sur les échantillons réels.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from edumatch.api.deps import get_etat_explicabilite
from edumatch.api.main import create_app
from edumatch.api.state import EtatExplicabilite
from edumatch.matching.score import MISE_EN_GARDE_ACCESSIBILITE


def _precalcul() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "session": 2025,
                "cod_aff_form": "F1",
                "type_bac": "bg",
                "boursier": False,
                "prediction": 0.62,
                "valeur_base": 0.50,
                "shap__fili": 0.05,
                "shap__dep": -0.02,
                "shap__taux_session_precedente": 0.09,
            }
        ]
    )


def _etat() -> EtatExplicabilite:
    precalcul = _precalcul()
    colonnes_shap = tuple(c for c in precalcul.columns if c.startswith("shap__"))
    return EtatExplicabilite(precalcul=precalcul, colonnes_shap=colonnes_shap, chemin=None)


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_etat_explicabilite] = lambda: _etat()
    return TestClient(app)


def test_explain_retourne_les_contributions_triees_par_ordre_decroissant(client: TestClient) -> None:
    reponse = client.get(
        "/explain", params={"session": 2025, "cod_aff_form": "F1", "type_bac": "bg", "boursier": False}
    )
    assert reponse.status_code == 200
    corps = reponse.json()

    assert corps["prediction"] == pytest.approx(0.62)
    assert corps["valeur_base"] == pytest.approx(0.50)
    contributions = corps["contributions"]
    valeurs_absolues = [abs(c["contribution"]) for c in contributions]
    assert valeurs_absolues == sorted(valeurs_absolues, reverse=True)
    assert contributions[0]["variable"] == "taux_session_precedente"


def test_explain_porte_la_mise_en_garde_accessibilite(client: TestClient) -> None:
    reponse = client.get(
        "/explain", params={"session": 2025, "cod_aff_form": "F1", "type_bac": "bg", "boursier": False}
    )
    assert reponse.json()["avertissement_accessibilite"] == MISE_EN_GARDE_ACCESSIBILITE


def test_explain_cellule_absente_repond_404_sans_exposer_de_chemin(client: TestClient) -> None:
    reponse = client.get(
        "/explain", params={"session": 2025, "cod_aff_form": "INCONNUE", "type_bac": "bg", "boursier": False}
    )
    assert reponse.status_code == 404
    assert "data" not in reponse.json()["detail"].lower()


def test_explain_type_bac_invalide_est_rejete(client: TestClient) -> None:
    reponse = client.get(
        "/explain", params={"session": 2025, "cod_aff_form": "F1", "type_bac": "invalide", "boursier": False}
    )
    assert reponse.status_code == 422


def test_explain_service_non_initialise_repond_503() -> None:
    client = TestClient(create_app())
    reponse = client.get(
        "/explain", params={"session": 2025, "cod_aff_form": "F1", "type_bac": "bg", "boursier": False}
    )
    assert reponse.status_code == 503
