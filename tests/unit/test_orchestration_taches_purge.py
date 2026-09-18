"""Tests unitaires des tâches de purge (`orchestration.taches`) : chacune doit appeler la
purge réelle (`simulation=False`) du bon module d'`audit_purge`, sans dépendre d'Airflow.

L'enchaînement dans le graphe (deux tâches distinctes du DAG `edumatch_audit_purge`) est
couvert par `tests/unit/test_pipeline_dag_airflow.py` ; le comportement des trois paliers
eux-mêmes, par `tests/unit/test_audit_purge.py`.
"""

from __future__ import annotations

import pytest

from edumatch.config import Settings
from edumatch.orchestration import taches
from tests.unit.test_ingestion_sirene import settings_test  # réexportée comme fixture

__all__ = ["settings_test"]


def test_purger_audit_appelle_la_purge_reelle_du_journal_d_inference(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings
) -> None:
    appels: list[tuple[Settings, bool]] = []
    monkeypatch.setattr(
        taches.audit_purge,
        "purger",
        lambda settings, *, simulation: appels.append((settings, simulation)) or "rapport-inference",
    )

    resultat = taches.purger_audit(settings_test)

    assert resultat == "rapport-inference"
    assert appels == [(settings_test, False)]


def test_purger_supervision_appelle_la_purge_reelle_du_journal_de_supervision(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings
) -> None:
    """Motif de blocage B : la tâche doit exister et appeler `audit_purge.purger_feedback`
    en mode réel — une durée de conservation documentée mais jamais appliquée n'en est pas
    une (voir `docs/registres.html#t6`)."""
    appels: list[tuple[Settings, bool]] = []
    monkeypatch.setattr(
        taches.audit_purge,
        "purger_feedback",
        lambda settings, *, simulation: appels.append((settings, simulation)) or "rapport-supervision",
    )

    resultat = taches.purger_supervision(settings_test)

    assert resultat == "rapport-supervision"
    assert appels == [(settings_test, False)]
