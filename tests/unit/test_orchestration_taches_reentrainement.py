"""Tests unitaires de `orchestration.taches.reentrainer_modele` et `.evaluer_modele`
(E22, E23, E33) : le contrat des deux tâches — l'une décide de la publication, l'autre ne
bloque jamais — sans entraîner un vrai modèle. `edumatch.models.train.entrainer_et_evaluer`,
`edumatch.orchestration.promotion.promouvoir_si_meilleur` et `edumatch.models.evaluate.executer`
sont remplacés par des doubles factices.

Le contrat de bout en bout (entraînement réel sur les échantillons) est couvert par
`tests/data/`, si présent, et par la démonstration de production (E39) ; l'enchaînement
réel dans le graphe Airflow, par `tests/unit/test_pipeline_dag_airflow.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edumatch.config import Settings
from edumatch.orchestration import taches
from edumatch.orchestration.promotion import RapportPromotion
from tests.unit.test_ingestion_sirene import settings_test  # réexportée comme fixture

__all__ = ["settings_test"]


def test_reentrainer_modele_retourne_le_rapport_de_promotion(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings
) -> None:
    resultat_factice = object()
    rapport_attendu = RapportPromotion(
        promu=True, mae_modele=0.06, mae_baseline=0.07, chemin_catalogue=Path("catalogue.parquet")
    )

    monkeypatch.setattr(taches.models_train, "entrainer_et_evaluer", lambda settings: resultat_factice)
    appels: list[tuple[object, Settings]] = []

    def _promouvoir_factice(resultat: object, settings: Settings) -> RapportPromotion:
        appels.append((resultat, settings))
        return rapport_attendu

    monkeypatch.setattr(taches.models_promotion, "promouvoir_si_meilleur", _promouvoir_factice)

    rapport = taches.reentrainer_modele(settings_test)

    assert rapport is rapport_attendu
    assert appels == [(resultat_factice, settings_test)]


def test_reentrainer_modele_ne_leve_pas_quand_la_promotion_est_refusee(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings
) -> None:
    """Un modèle qui perd contre le plancher (E21) est un résultat attendu, pas une panne
    du graphe : la tâche doit se terminer normalement, la reprise (E33) ne doit jamais
    rejouer une comparaison déjà tranchée."""
    rapport_refuse = RapportPromotion(promu=False, mae_modele=0.0758, mae_baseline=0.0701, chemin_catalogue=None)
    monkeypatch.setattr(taches.models_train, "entrainer_et_evaluer", lambda settings: object())
    monkeypatch.setattr(taches.models_promotion, "promouvoir_si_meilleur", lambda resultat, settings: rapport_refuse)

    rapport = taches.reentrainer_modele(settings_test)

    assert rapport.promu is False


def test_evaluer_modele_delegue_a_models_evaluate_sans_rien_publier(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings
) -> None:
    rapport_attendu = object()
    appels: list[Settings] = []

    def _executer_factice(settings: Settings) -> object:
        appels.append(settings)
        return rapport_attendu

    monkeypatch.setattr(taches.models_evaluate, "executer", _executer_factice)

    rapport = taches.evaluer_modele(settings_test)

    assert rapport is rapport_attendu
    assert appels == [settings_test]
