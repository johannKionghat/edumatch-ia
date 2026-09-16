"""Test de contrat de `/explain` (E29) de bout en bout, sur les échantillons réels.

Même schéma que `tests/data/test_models_explain_run.py` (E25) : un `data_root` jetable
construit depuis les huit échantillons versionnés, jusqu'au précalcul SHAP complet, puis
`api.state.construire_etat_explicabilite` le charge tel quel — jamais recalculé par l'API.
"""

from __future__ import annotations

import shutil

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from edumatch.api.deps import get_etat_explicabilite
from edumatch.api.main import create_app
from edumatch.api.state import construire_etat_explicabilite
from edumatch.config import Settings, load_settings
from edumatch.features import build
from edumatch.models import explain
from edumatch.transform import run, run_etoile


@pytest.fixture(scope="module")
def settings_avec_precalcul(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    tmp_path = tmp_path_factory.mktemp("api-explain")
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path, "mlflow_tracking_uri": None})
    dossier_raw = settings.raw_dir / "parcoursup"
    dossier_raw.mkdir(parents=True)
    for millesime in settings.donnees.parcoursup.millesimes:
        source = base.samples_dir / "parcoursup" / f"parcoursup_{millesime}.csv"
        shutil.copy(source, dossier_raw / f"parcoursup_{millesime}.csv")
    run.executer(settings)
    run_etoile.executer(settings)
    build.executer(settings)
    explain.executer(settings, dossier_figures=tmp_path / "figures")  # écrit dans processed_dir/explicabilite/
    return settings


@pytest.fixture(scope="module")
def cellule_reelle(settings_avec_precalcul: Settings) -> pd.Series:
    """Une cellule réellement précalculée, prise telle quelle plutôt qu'inventée."""
    chemin = settings_avec_precalcul.processed_dir / "explicabilite" / "explications_locales.parquet"
    precalcul = pd.read_parquet(chemin)
    return precalcul.iloc[0]


@pytest.fixture()
def client(settings_avec_precalcul: Settings) -> TestClient:
    etat = construire_etat_explicabilite(settings_avec_precalcul)
    app = create_app()
    app.dependency_overrides[get_etat_explicabilite] = lambda: etat
    return TestClient(app)


def test_explain_sert_une_cellule_reellement_precalculee(client: TestClient, cellule_reelle: pd.Series) -> None:
    reponse = client.get(
        "/explain",
        params={
            "session": int(cellule_reelle["session"]),
            "cod_aff_form": str(cellule_reelle["cod_aff_form"]),
            "type_bac": str(cellule_reelle["type_bac"]),
            "boursier": bool(cellule_reelle["boursier"]),
        },
    )
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["prediction"] == pytest.approx(float(cellule_reelle["prediction"]), abs=1e-4)
    assert len(corps["contributions"]) > 0


def test_explain_cellule_inexistante_repond_404(client: TestClient) -> None:
    reponse = client.get(
        "/explain",
        params={"session": 2025, "cod_aff_form": "INCONNUE", "type_bac": "bg", "boursier": False},
    )
    assert reponse.status_code == 404
