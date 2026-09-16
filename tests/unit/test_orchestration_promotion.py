"""Tests unitaires de `orchestration.promotion` (E33, critères 3.3 et 4.12) : la porte de
promotion refuse de publier un modèle qui ne bat pas le plancher, sans jamais réentraîner.

Le `ResultatEntrainement` réel (`models.train`) porte un modèle LightGBM, des DataFrames de
jeux de test/validation et une table complète : reconstruire tout cela ici coûterait un
entraînement, exactement ce que ce module ne fait pas. `decider_promotion` et
`promouvoir_si_meilleur` ne lisent que `resultat.rapport.scores_test.mae_ponderee` et
`resultat.rapport.baseline_test.mae_ponderee` (typage structurel, pas `isinstance`) : un
double factice minimal suffit à couvrir la décision sans instancier `ResultatEntrainement`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from edumatch.config import Settings
from edumatch.orchestration import promotion
from tests.unit.test_ingestion_sirene import settings_test  # réexportée comme fixture

__all__ = ["settings_test"]


@dataclass(frozen=True)
class _ScoreFactice:
    mae_ponderee: float


@dataclass(frozen=True)
class _RapportFactice:
    scores_test: _ScoreFactice
    baseline_test: _ScoreFactice


@dataclass(frozen=True)
class _ResultatFactice:
    rapport: _RapportFactice


def _resultat(mae_modele: float, mae_baseline: float) -> _ResultatFactice:
    return _ResultatFactice(
        rapport=_RapportFactice(
            scores_test=_ScoreFactice(mae_ponderee=mae_modele),
            baseline_test=_ScoreFactice(mae_ponderee=mae_baseline),
        )
    )


def test_decider_promotion_vrai_si_le_modele_bat_strictement_le_plancher() -> None:
    assert promotion.decider_promotion(_resultat(mae_modele=0.06, mae_baseline=0.07)) is True


def test_decider_promotion_faux_si_le_modele_perd() -> None:
    # Le cas mesuré sur ce dépôt (voir le docstring du module) : 0,0758 contre 0,0701.
    assert promotion.decider_promotion(_resultat(mae_modele=0.0758, mae_baseline=0.0701)) is False


def test_decider_promotion_faux_a_egalite_stricte() -> None:
    """Une égalité n'est pas un progrès : elle ne justifie pas de remplacer l'artefact publié."""
    assert promotion.decider_promotion(_resultat(mae_modele=0.07, mae_baseline=0.07)) is False


def test_promouvoir_publie_le_catalogue_si_le_modele_bat_le_plancher(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings
) -> None:
    chemin_attendu = Path("catalogue_predictions.parquet")
    appels: list[tuple[object, Settings]] = []

    def _export_factice(resultat: object, settings: Settings) -> Path:
        appels.append((resultat, settings))
        return chemin_attendu

    monkeypatch.setattr(promotion, "exporter_catalogue_predictions", _export_factice)

    resultat = _resultat(mae_modele=0.06, mae_baseline=0.07)
    rapport = promotion.promouvoir_si_meilleur(resultat, settings_test)  # type: ignore[arg-type]

    assert rapport.promu is True
    assert rapport.chemin_catalogue == chemin_attendu
    assert len(appels) == 1


def test_promouvoir_refuse_et_n_exporte_rien_si_le_modele_perd(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    appels: list[object] = []
    monkeypatch.setattr(
        promotion, "exporter_catalogue_predictions", lambda resultat, settings: appels.append(resultat)
    )

    resultat = _resultat(mae_modele=0.0758, mae_baseline=0.0701)
    with caplog.at_level("ERROR"):
        rapport = promotion.promouvoir_si_meilleur(resultat, settings_test)  # type: ignore[arg-type]

    assert rapport.promu is False
    assert rapport.chemin_catalogue is None
    assert appels == []  # l'artefact déjà servi n'est jamais touché
    assert any("refus" in message.lower() for message in caplog.messages)


def test_promouvoir_est_idempotent_rejouer_sur_le_meme_resultat_donne_la_meme_decision(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings
) -> None:
    """Rejouer la tâche (reprise sur erreur, E33 critère 3.4) doit reproduire exactement
    le même verdict — jamais un doublon, jamais une décision différente au hasard."""
    compteur = {"appels": 0}

    def _export_factice(resultat: object, settings: Settings) -> Path:
        compteur["appels"] += 1
        return Path("catalogue_predictions.parquet")

    monkeypatch.setattr(promotion, "exporter_catalogue_predictions", _export_factice)

    resultat = _resultat(mae_modele=0.06, mae_baseline=0.07)
    premier = promotion.promouvoir_si_meilleur(resultat, settings_test)  # type: ignore[arg-type]
    second = promotion.promouvoir_si_meilleur(resultat, settings_test)  # type: ignore[arg-type]

    assert premier == second
    assert compteur["appels"] == 2  # rejouée deux fois, publiée deux fois, jamais divergente
