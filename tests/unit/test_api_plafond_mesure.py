"""Le plafond de `/matching` est adossé à une mesure, pas posé à la main.

`reports/bench-matching.json` est produit par `scripts/bench_matching.py` sur l'état réel du
service (catalogue de la session courante). Ce test ne remesure pas la latence, qui dépend de
la machine : il vérifie que la configuration reste cohérente avec la mesure versionnée.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edumatch.config import get_settings

BANC = Path(__file__).resolve().parents[2] / "reports" / "bench-matching.json"


@pytest.fixture(scope="module")
def banc() -> dict:
    return json.loads(BANC.read_text(encoding="utf-8"))


def test_le_plafond_couvre_le_plus_gros_departement_reel(banc: dict) -> None:
    """Tout département réel doit pouvoir être demandé : aucun 422 sur un cas d'usage réel."""
    assert (
        get_settings().api.max_formations_evaluees
        >= banc["contexte"]["plus_grosse_cellule_departementale"]
    )


def test_la_france_entiere_reste_refusee(banc: dict) -> None:
    """Sans département, le périmètre dépasse le plafond : le refus explicite reste la règle."""
    assert get_settings().api.max_formations_evaluees < banc["contexte"]["cellule_france_entiere"]


def test_le_banc_mesure_le_plus_gros_departement(banc: dict) -> None:
    mesures = {m["departement"]: m for m in banc["departements_reels"]}
    plus_gros = banc["contexte"]["departement_de_la_plus_grosse_cellule"]
    assert plus_gros in mesures
    assert (
        mesures[plus_gros]["n_formations"] == banc["contexte"]["plus_grosse_cellule_departementale"]
    )
    assert mesures[plus_gros]["repetitions"] >= 30


def test_le_banc_couvre_des_tailles_au_dela_du_plafond(banc: dict) -> None:
    tailles = [m["n_formations"] for m in banc["tailles_fixes"]]
    assert max(tailles) > get_settings().api.max_formations_evaluees
