"""Tests unitaires de `api/state.py` : la dégradation du terme de débouchés (jamais un zéro
silencieux) et l'absence explicite du précalcul d'explicabilité."""

from __future__ import annotations

from pathlib import Path

import pytest

from edumatch.api.state import ErreurEtatAPI, _artefacts_debouches_indisponibles, construire_etat_explicabilite
from edumatch.config import Settings, get_settings
from edumatch.matching.debouches import STATUT_INDISPONIBLE_CHAINE_ROMPUE, VALEUR_NEUTRE, calculer_terme_debouches


def test_artefacts_debouches_indisponibles_donne_un_statut_explicite_pas_un_zero() -> None:
    """Une formation scorée avec des artefacts dégradés reçoit le même statut qu'un libellé non
    apparié (`STATUT_INDISPONIBLE_CHAINE_ROMPUE`) — une valeur neutre, jamais un zéro qui
    supprimerait la recommandation par erreur (voir `matching/score.py`, le caractère
    multiplicatif du score)."""
    artefacts = _artefacts_debouches_indisponibles()

    terme = calculer_terme_debouches(
        fil_lib_voe_acc="BTS SIO",
        departement_candidat="75",
        correspondance_formation=artefacts.correspondance_formation,
        table_naf_rome_formation=artefacts.table_naf_rome_formation,
        agregat_conserve=artefacts.agregat_conserve,
        cellules_non_vides=artefacts.cellules_non_vides,
        seuil_saturation=100,
    )

    assert terme.statut == STATUT_INDISPONIBLE_CHAINE_ROMPUE
    assert terme.disponible is False
    assert terme.valeur == VALEUR_NEUTRE


def test_construire_etat_explicabilite_leve_une_erreur_explicite_si_precalcul_absent(tmp_path: Path) -> None:
    settings: Settings = get_settings().model_copy(update={"data_root": tmp_path})
    with pytest.raises(ErreurEtatAPI, match="make explain"):
        construire_etat_explicabilite(settings)
