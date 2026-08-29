"""Tests du contrôle générique de fraîcheur (`_fraicheur.py`)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from edumatch.quality._diagnostic import Gravite
from edumatch.quality._fraicheur import controler_fraicheur

MAINTENANT = datetime(2026, 8, 29, tzinfo=timezone.utc)


def test_entree_absente_bloque() -> None:
    anomalies = controler_fraicheur("src", {"x": None}, 30, maintenant=MAINTENANT)
    assert len(anomalies) == 1
    assert anomalies[0].gravite is Gravite.BLOQUANT


def test_date_illisible_bloque() -> None:
    anomalies = controler_fraicheur("src", {"x": "pas-une-date"}, 30, maintenant=MAINTENANT)
    assert len(anomalies) == 1
    assert anomalies[0].gravite is Gravite.BLOQUANT


def test_date_dans_le_futur_bloque() -> None:
    demain = (MAINTENANT + timedelta(days=1)).isoformat()
    anomalies = controler_fraicheur("src", {"x": demain}, 30, maintenant=MAINTENANT)
    assert len(anomalies) == 1
    assert anomalies[0].gravite is Gravite.BLOQUANT


def test_date_fraiche_ne_produit_aucune_anomalie() -> None:
    hier = (MAINTENANT - timedelta(days=1)).isoformat()
    anomalies = controler_fraicheur("src", {"x": hier}, 30, maintenant=MAINTENANT)
    assert anomalies == []


def test_date_perimee_avertit_sans_bloquer() -> None:
    il_y_a_60_jours = (MAINTENANT - timedelta(days=60)).isoformat()
    anomalies = controler_fraicheur("src", {"x": il_y_a_60_jours}, 30, maintenant=MAINTENANT)
    assert len(anomalies) == 1
    assert anomalies[0].gravite is Gravite.AVERTISSEMENT


def test_plusieurs_entrees_sont_toutes_controlees() -> None:
    hier = (MAINTENANT - timedelta(days=1)).isoformat()
    anomalies = controler_fraicheur("src", {"a": hier, "b": None}, 30, maintenant=MAINTENANT)
    assert len(anomalies) == 1
    assert "b" in anomalies[0].message
