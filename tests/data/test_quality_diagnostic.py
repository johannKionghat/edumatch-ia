"""Tests du vocabulaire commun des contrôles qualité (`_diagnostic.py`)."""

from __future__ import annotations

import pytest

from edumatch.quality._diagnostic import (
    Anomalie,
    ErreurQualiteBloquante,
    Gravite,
    RapportControle,
    fusionner,
)
from edumatch.ingestion._flux import ErreurDefinitive


def test_rapport_sans_anomalie_n_est_pas_bloquant() -> None:
    rapport = RapportControle(source="test", anomalies=())
    assert not rapport.est_bloquant
    rapport.lever_si_bloquant()  # ne doit rien lever


def test_avertissement_seul_n_est_pas_bloquant() -> None:
    anomalie = Anomalie("test", "completude", Gravite.AVERTISSEMENT, "message")
    rapport = RapportControle(source="test", anomalies=(anomalie,))
    assert not rapport.est_bloquant
    assert rapport.avertissements == (anomalie,)
    rapport.lever_si_bloquant()


def test_anomalie_bloquante_leve_erreur_qualite_bloquante() -> None:
    anomalie = Anomalie("test", "schema", Gravite.BLOQUANT, "colonne absente")
    rapport = RapportControle(source="test", anomalies=(anomalie,))
    assert rapport.est_bloquant
    with pytest.raises(ErreurQualiteBloquante, match="colonne absente"):
        rapport.lever_si_bloquant()


def test_erreur_qualite_bloquante_est_une_erreur_definitive() -> None:
    """Un échec de contrôle qualité ne se résout pas en retentant : c'est le vocabulaire commun du projet."""
    assert issubclass(ErreurQualiteBloquante, ErreurDefinitive)


def test_fusionner_combine_plusieurs_rapports_partiels() -> None:
    a = Anomalie("test", "schema", Gravite.BLOQUANT, "a")
    b = Anomalie("test", "completude", Gravite.AVERTISSEMENT, "b")
    rapport = fusionner(
        "test",
        RapportControle(source="test", anomalies=(a,)),
        RapportControle(source="test", anomalies=(b,)),
    )
    assert rapport.anomalies == (a, b)
    assert rapport.est_bloquant
