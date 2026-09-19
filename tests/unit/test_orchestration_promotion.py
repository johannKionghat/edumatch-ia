"""Tests unitaires de `orchestration.promotion` (critères 3.3 et 4.12) : la porte de
promotion refuse de publier un modèle qui ne satisfait pas la CONJONCTION du plancher de
l'AIPD (MAE pondérée de test sous le plancher ET ECE de test sous le seuil, ADR 0021),
sans jamais réentraîner.

Le `ResultatEntrainement` réel (`models.train`) porte un modèle LightGBM, des DataFrames de
jeux de test/validation et une table complète : reconstruire tout cela ici coûterait un
entraînement, exactement ce que ce module ne fait pas. `decider_promotion` et
`promouvoir_si_meilleur` ne lisent que `resultat.rapport.scores_test.mae_ponderee`,
`resultat.rapport.baseline_test.mae_ponderee`, `resultat.rapport.ece_test` et
`settings.evaluation.seuil_ece_test` (typage structurel, pas `isinstance`) : un double
factice minimal suffit à couvrir la décision sans instancier `ResultatEntrainement`.
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
    ece_test: float


@dataclass(frozen=True)
class _ResultatFactice:
    rapport: _RapportFactice


def _resultat(mae_modele: float, mae_baseline: float, ece_modele: float = 0.01) -> _ResultatFactice:
    return _ResultatFactice(
        rapport=_RapportFactice(
            scores_test=_ScoreFactice(mae_ponderee=mae_modele),
            baseline_test=_ScoreFactice(mae_ponderee=mae_baseline),
            ece_test=ece_modele,
        )
    )


# `settings_test` (fixture) charge `configs/base.yaml` réel via `_config_fixtures.py`,
# où `evaluation.seuil_ece_test` vaut 0,0322 (même valeur que le dépôt) : les tests de ce
# module l'utilisent directement plutôt que d'inventer un second seuil.


def test_decider_promotion_vrai_si_les_deux_conditions_sont_satisfaites(settings_test: Settings) -> None:
    resultat = _resultat(mae_modele=0.06, mae_baseline=0.07, ece_modele=0.01)
    assert promotion.decider_promotion(resultat, settings_test) is True  # type: ignore[arg-type]


def test_decider_promotion_faux_si_la_mae_perd(settings_test: Settings) -> None:
    # Le cas historique mesuré sur ce dépôt avant l'ADR 0021 : 0,0758 contre 0,0701.
    resultat = _resultat(mae_modele=0.0758, mae_baseline=0.0701, ece_modele=0.01)
    assert promotion.decider_promotion(resultat, settings_test) is False  # type: ignore[arg-type]


def test_decider_promotion_faux_a_egalite_stricte_de_mae(settings_test: Settings) -> None:
    """Une égalité n'est pas un progrès : elle ne justifie pas de remplacer l'artefact publié."""
    resultat = _resultat(mae_modele=0.07, mae_baseline=0.07, ece_modele=0.01)
    assert promotion.decider_promotion(resultat, settings_test) is False  # type: ignore[arg-type]


def test_decider_promotion_faux_si_seule_lece_echoue(settings_test: Settings) -> None:
    """La MAE bat le plancher, mais l'ECE dépasse le seuil de l'AIPD (0,0322) : la
    conjonction doit refuser — un modèle rapide mais mal calibré n'est pas promouvable."""
    resultat = _resultat(mae_modele=0.06, mae_baseline=0.07, ece_modele=0.05)
    assert promotion.decider_promotion(resultat, settings_test) is False  # type: ignore[arg-type]


def test_promouvoir_publie_le_catalogue_si_les_deux_conditions_sont_satisfaites(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings
) -> None:
    chemin_attendu = Path("catalogue_predictions.parquet")
    appels: list[tuple[object, Settings]] = []

    def _export_factice(resultat: object, settings: Settings) -> Path:
        appels.append((resultat, settings))
        return chemin_attendu

    monkeypatch.setattr(promotion, "exporter_catalogue_predictions", _export_factice)

    resultat = _resultat(mae_modele=0.06, mae_baseline=0.07, ece_modele=0.01)
    rapport = promotion.promouvoir_si_meilleur(resultat, settings_test)  # type: ignore[arg-type]

    assert rapport.promu is True
    assert rapport.mae_ok is True
    assert rapport.ece_ok is True
    assert rapport.chemin_catalogue == chemin_attendu
    assert len(appels) == 1


def test_promouvoir_refuse_et_n_exporte_rien_si_la_mae_perd(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    appels: list[object] = []
    monkeypatch.setattr(
        promotion, "exporter_catalogue_predictions", lambda resultat, settings: appels.append(resultat)
    )

    resultat = _resultat(mae_modele=0.0758, mae_baseline=0.0701, ece_modele=0.01)
    with caplog.at_level("ERROR"):
        rapport = promotion.promouvoir_si_meilleur(resultat, settings_test)  # type: ignore[arg-type]

    assert rapport.promu is False
    assert rapport.mae_ok is False
    assert rapport.ece_ok is True
    assert rapport.chemin_catalogue is None
    assert appels == []  # l'artefact déjà servi n'est jamais touché
    assert any("refus" in message.lower() for message in caplog.messages)


def test_promouvoir_refuse_et_indique_lechec_de_lece_quand_seule_elle_echoue(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings
) -> None:
    monkeypatch.setattr(promotion, "exporter_catalogue_predictions", lambda resultat, settings: Path("x"))

    resultat = _resultat(mae_modele=0.06, mae_baseline=0.07, ece_modele=0.05)
    rapport = promotion.promouvoir_si_meilleur(resultat, settings_test)  # type: ignore[arg-type]

    assert rapport.promu is False
    assert rapport.mae_ok is True
    assert rapport.ece_ok is False
    assert "ÉCHEC" in rapport.resume()


def test_promouvoir_est_idempotent_rejouer_sur_le_meme_resultat_donne_la_meme_decision(
    monkeypatch: pytest.MonkeyPatch, settings_test: Settings
) -> None:
    """Rejouer la tâche (reprise sur erreur, critère 3.4) doit reproduire exactement
    le même verdict — jamais un doublon, jamais une décision différente au hasard."""
    compteur = {"appels": 0}

    def _export_factice(resultat: object, settings: Settings) -> Path:
        compteur["appels"] += 1
        return Path("catalogue_predictions.parquet")

    monkeypatch.setattr(promotion, "exporter_catalogue_predictions", _export_factice)

    resultat = _resultat(mae_modele=0.06, mae_baseline=0.07, ece_modele=0.01)
    premier = promotion.promouvoir_si_meilleur(resultat, settings_test)  # type: ignore[arg-type]
    second = promotion.promouvoir_si_meilleur(resultat, settings_test)  # type: ignore[arg-type]

    assert premier == second
    assert compteur["appels"] == 2  # rejouée deux fois, publiée deux fois, jamais divergente
