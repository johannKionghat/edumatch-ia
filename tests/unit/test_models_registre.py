"""Enregistrement au registre de modèles (critère 4.10, seconde moitié) : `models/registre.py`.

Le suivi d'expériences (paramètres, métriques, artefact) est déjà couvert par
`test_mlflow_disponible.py` et par les tests de contrat de `models/train.py`.
Ce fichier couvre ce que ces derniers ne couvrent pas : le passage d'une
exécution journalisée à une *version nommée* du registre, avec son statut
honnête (jamais promue) et sa description chiffrée.

Magasin SQLite jetable dans `tmp_path`, comme `test_mlflow_disponible.py` :
jamais `mlflow.db` ni `mlruns/` du dépôt.
"""

from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pytest

from edumatch.config import get_settings
from edumatch.models.registre import (
    ETIQUETTE_STATUT,
    NOM_MODELE_REGISTRE,
    ErreurRegistreModele,
    enregistrer_version_modele,
)
from edumatch.models.train import NOM_EXPERIENCE_MLFLOW


def _uri_magasin(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'mlflow_registre_test.db').as_posix()}"


def _journaliser_run_entrainement_factice(uri_magasin: str, *, commit: str = "abc1234") -> str:
    """Reproduit la forme minimale d'une exécution `models.train` : mêmes tags,
    mêmes métriques utiles, un vrai modèle LightGBM en artefact `modele` — sans
    passer par la table de variables réelle, hors de propos ici."""
    import mlflow
    import mlflow.lightgbm

    mlflow.set_tracking_uri(uri_magasin)
    mlflow.set_experiment(NOM_EXPERIENCE_MLFLOW)

    modele = lgb.LGBMRegressor(n_estimators=5, num_leaves=3, min_child_samples=1, verbose=-1)
    x = np.array([[0.0], [1.0], [2.0], [3.0]])
    y = np.array([0.1, 0.2, 0.3, 0.4])
    modele.fit(x, y)

    with mlflow.start_run(run_name="lightgbm-pondere-avec-taux-precedent") as run:
        mlflow.set_tag("etape", "train")
        mlflow.set_tag("variante", "avec-taux-precedent")
        mlflow.set_tag("commit_git", commit)
        mlflow.log_metric("test_mae_ponderee", 0.0758)
        mlflow.log_metric("baseline_test_mae_ponderee", 0.0701)
        mlflow.lightgbm.log_model(modele, name="modele")
        return run.info.run_id


@pytest.fixture
def _settings_registre(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    uri_magasin = _uri_magasin(tmp_path)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri_magasin)
    get_settings.cache_clear()
    try:
        yield uri_magasin, get_settings()
    finally:
        get_settings.cache_clear()


def test_enregistrer_version_modele_trouve_la_derniere_execution_entrainement(_settings_registre) -> None:
    """Sans `run_id`, la fonction retrouve la dernière exécution `train` de la variante active."""
    uri_magasin, settings = _settings_registre
    run_id = _journaliser_run_entrainement_factice(uri_magasin)

    rapport = enregistrer_version_modele(settings=settings)

    assert rapport.nom_modele == NOM_MODELE_REGISTRE
    assert str(rapport.version) == "1"
    assert rapport.run_id == run_id
    assert rapport.commit_git == "abc1234"
    assert rapport.test_mae_ponderee == pytest.approx(0.0758)
    assert rapport.baseline_test_mae_ponderee == pytest.approx(0.0701)


def test_enregistrer_version_modele_declare_le_statut_non_retenu(_settings_registre) -> None:
    """La version enregistrée porte l'étiquette et la description honnêtes : ce modèle perd
    contre le plancher et n'est promu à aucun alias."""
    import mlflow
    from mlflow.tracking import MlflowClient

    uri_magasin, settings = _settings_registre
    _journaliser_run_entrainement_factice(uri_magasin)

    enregistrer_version_modele(settings=settings)

    mlflow.set_tracking_uri(uri_magasin)
    client = MlflowClient(tracking_uri=uri_magasin)
    version = client.get_model_version(NOM_MODELE_REGISTRE, "1")

    assert version.tags[ETIQUETTE_STATUT] == (
        "ne bat pas le plancher (session precedente a couverture egale) sur le test 2025 : "
        "non retenu pour un usage reel, enregistre pour la tracabilite du registre (critere 4.10)"
    )
    assert "0.0758" in version.description
    assert "0.0701" in version.description
    assert "ne bat pas le plancher" in version.description

    modele_enregistre = client.get_registered_model(NOM_MODELE_REGISTRE)
    assert modele_enregistre.aliases == {}, "aucun alias (donc aucune promotion) ne doit être posé automatiquement"


def test_enregistrer_version_modele_leve_sans_execution(_settings_registre) -> None:
    """Aucune exécution `train` journalisée : erreur explicite, jamais un registre créé à vide."""
    _, settings = _settings_registre

    with pytest.raises(ErreurRegistreModele, match="Aucune expérience"):
        enregistrer_version_modele(settings=settings)


def test_enregistrer_version_modele_leve_sans_tracking_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    """MLFLOW_TRACKING_URI absent : erreur explicite, pas un enregistrement muet."""
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.mlflow_tracking_uri is None

        with pytest.raises(ErreurRegistreModele, match="MLFLOW_TRACKING_URI"):
            enregistrer_version_modele(settings=settings)
    finally:
        get_settings.cache_clear()
