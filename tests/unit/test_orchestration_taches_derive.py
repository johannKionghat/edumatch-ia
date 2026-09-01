"""Tests unitaires de `orchestration.taches.detecter_derive` (E34) : le contrat de la
tâche (jamais bloquante, journalise sur dérive) — sans entraîner un vrai modèle,
`edumatch.models.derive.executer` est remplacé par un rapport fabriqué.

Le contrat de bout en bout (mesure réelle sur les échantillons) est couvert par
`tests/data/test_models_derive_run.py` ; l'enchaînement réel dans le graphe Airflow, par
`tests/unit/test_pipeline_dag_airflow.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edumatch.config import Settings
from edumatch.models.derive import RapportDerive, ScoreDerive
from edumatch.orchestration import taches
from tests.unit.test_ingestion_sirene import settings_test  # réexportée comme fixture

__all__ = ["settings_test"]


def _rapport(reentrainement_recommande: bool) -> RapportDerive:
    predictions = []
    if reentrainement_recommande:
        predictions = [ScoreDerive("taux prédit", "numerique", "entrainement -> test-2025", 10, 10, 0.30, None, True)]
    return RapportDerive(
        seuil_reentrainement=0.20,
        derive_variables_production=[],
        derive_variables_consecutive=[],
        derive_cible_production=[],
        derive_cible_consecutive=[],
        derive_predictions_production=predictions,
        derive_predictions_consecutive=[],
        chemin_figure_variables=Path("variables.png"),
        chemin_figure_trajectoire=Path("trajectoire.png"),
    )


def test_detecter_derive_retourne_le_rapport_sans_lever(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings
) -> None:
    rapport_attendu = _rapport(reentrainement_recommande=False)
    monkeypatch.setattr(taches.models_derive, "executer", lambda settings: rapport_attendu)

    rapport = taches.detecter_derive(settings_test)

    assert rapport is rapport_attendu


def test_detecter_derive_journalise_un_avertissement_si_reentrainement_recommande(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    rapport_attendu = _rapport(reentrainement_recommande=True)
    monkeypatch.setattr(taches.models_derive, "executer", lambda settings: rapport_attendu)

    with caplog.at_level("WARNING"):
        taches.detecter_derive(settings_test)

    assert any("réentraînement" in message for message in caplog.messages)


def test_detecter_derive_ne_journalise_rien_si_sous_le_seuil(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    rapport_attendu = _rapport(reentrainement_recommande=False)
    monkeypatch.setattr(taches.models_derive, "executer", lambda settings: rapport_attendu)

    with caplog.at_level("WARNING"):
        taches.detecter_derive(settings_test)

    assert not any("réentraînement" in message for message in caplog.messages)
