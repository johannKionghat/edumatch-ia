"""Test de contrat de `/matching` (E29) de bout en bout, sur les échantillons réels.

Même schéma que `tests/data/test_models_explain_run.py` (E25) pour la table de variables.
`data/samples/sirene/StockEtablissement.parquet` ne porte pas `statutDiffusionEtablissement`
(voir `tests/data/test_matching_debouches_run.py`) : `construire_etat_matching` doit donc
dégrader le terme de débouchés proprement, jamais planter — c'est cela que ce test vérifie,
en plus du contrat HTTP de bout en bout.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from edumatch.api.deps import get_etat_matching
from edumatch.api.main import create_app
from edumatch.api.state import construire_etat_matching
from edumatch.config import Settings, load_settings
from edumatch.features import build
from edumatch.transform import run, run_etoile


@pytest.fixture(scope="module")
def settings_avec_variables(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    tmp_path = tmp_path_factory.mktemp("api-matching")
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path, "mlflow_tracking_uri": None})
    dossier_raw_parcoursup = settings.raw_dir / "parcoursup"
    dossier_raw_parcoursup.mkdir(parents=True)
    for millesime in settings.donnees.parcoursup.millesimes:
        source = base.samples_dir / "parcoursup" / f"parcoursup_{millesime}.csv"
        shutil.copy(source, dossier_raw_parcoursup / f"parcoursup_{millesime}.csv")
    dossier_raw_sirene = settings.raw_dir / "sirene"
    dossier_raw_sirene.mkdir(parents=True)
    shutil.copy(
        base.samples_dir / "sirene" / "StockEtablissement.parquet",
        dossier_raw_sirene / "StockEtablissement.parquet",
    )
    run.executer(settings)
    run_etoile.executer(settings)
    build.executer(settings)
    return settings


@pytest.fixture(scope="module")
def etat_matching(settings_avec_variables: Settings):
    return construire_etat_matching(settings_avec_variables)


def test_etat_matching_degrade_le_terme_debouches_sans_planter(etat_matching) -> None:
    """L'échantillon Sirene ne porte pas `statutDiffusionEtablissement` (voir le docstring du
    module) : le service démarre quand même, dégradé et documenté — jamais un crash."""
    assert etat_matching.debouches_disponible is False
    assert etat_matching.motif_indisponibilite_debouches is not None


def test_matching_repond_sur_un_catalogue_reel(etat_matching) -> None:
    app = create_app()
    app.dependency_overrides[get_etat_matching] = lambda: etat_matching
    client = TestClient(app)

    # Le premier profil disponible dans le catalogue réel de la session de test.
    ligne = etat_matching.catalogue.iloc[0]

    reponse = client.post(
        "/matching",
        json={"type_bac": str(ligne["type_bac"]), "boursier": bool(ligne["boursier"])},
    )
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["session"] == etat_matching.session_courante
    assert corps["debouches_disponible"] is False
    assert corps["n_formations_disponibles"] >= 1
