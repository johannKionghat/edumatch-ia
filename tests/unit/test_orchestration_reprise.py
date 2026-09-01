"""Tests de la reprise sur erreur de l'orchestrateur (E33, critère 3.4).

Aucune dépendance à Airflow ici : `executer_avec_reprise` est du Python pur,
c'est précisément ce qui permet de la tester sans installer le paquet. Le
temps d'attente (`dormir`) est injecté, jamais un vrai `time.sleep`, pour que
la suite reste rapide et déterministe.
"""

from __future__ import annotations

import pytest

from edumatch.ingestion._flux import ErreurDefinitive, ErreurTransitoire
from edumatch.orchestration.reprise import (
    ErreurRepriseEpuisee,
    PolitiqueReprise,
    executer_avec_reprise,
)


class _ErreurReseauExemple(ErreurTransitoire):
    """Erreur transitoire de test, sans dépendre d'un connecteur réel."""


class _ErreurSchemaExemple(ErreurDefinitive):
    """Erreur définitive de test, sans dépendre d'un connecteur réel."""


def _politique(
    *, tentatives_max: int = 3, delai_secondes: float = 10.0, facteur_backoff: float = 2.0
) -> PolitiqueReprise:
    return PolitiqueReprise(
        tentatives_max=tentatives_max,
        delai_secondes=delai_secondes,
        facteur_backoff=facteur_backoff,
    )


def test_succes_du_premier_coup_n_attend_jamais() -> None:
    delais_attendus: list[float] = []
    appels = {"n": 0}

    def tache() -> str:
        appels["n"] += 1
        return "ok"

    resultat = executer_avec_reprise(
        tache, politique=_politique(), nom_tache="test", dormir=delais_attendus.append
    )

    assert resultat == "ok"
    assert appels["n"] == 1
    assert delais_attendus == []


def test_erreur_transitoire_est_retentee_avec_backoff_croissant() -> None:
    """Deux échecs transitoires puis un succès : la tâche est rejouée, jamais court-circuitée."""
    delais_observes: list[float] = []
    appels = {"n": 0}

    def tache() -> str:
        appels["n"] += 1
        if appels["n"] <= 2:
            raise _ErreurReseauExemple("panne réseau simulée")
        return "ok"

    resultat = executer_avec_reprise(
        tache,
        politique=_politique(tentatives_max=3, delai_secondes=10.0, facteur_backoff=2.0),
        nom_tache="test",
        dormir=delais_observes.append,
    )

    assert resultat == "ok"
    assert appels["n"] == 3
    # Temporisation croissante : 10 s avant la 2e tentative, 20 s avant la 3e.
    assert delais_observes == [10.0, 20.0]


def test_erreur_transitoire_persistante_epuise_les_tentatives() -> None:
    appels = {"n": 0}

    def tache() -> None:
        appels["n"] += 1
        raise _ErreurReseauExemple(f"panne {appels['n']}")

    with pytest.raises(ErreurRepriseEpuisee, match="3 tentative"):
        executer_avec_reprise(
            tache,
            politique=_politique(tentatives_max=3),
            nom_tache="test_epuise",
            dormir=lambda _: None,
        )

    assert appels["n"] == 3  # jamais une quatrième tentative au-delà du plafond


def test_erreur_definitive_n_est_jamais_retentee() -> None:
    """Une erreur définitive retentée cinq fois serait cinq fois la même panne, pas une reprise."""
    appels = {"n": 0}
    dormi = {"appele": False}

    def tache() -> None:
        appels["n"] += 1
        raise _ErreurSchemaExemple("schéma cassé")

    with pytest.raises(_ErreurSchemaExemple):
        executer_avec_reprise(
            tache,
            politique=_politique(tentatives_max=5),
            nom_tache="test_definitif",
            dormir=lambda _: dormi.__setitem__("appele", True),
        )

    assert appels["n"] == 1  # un seul appel : aucune reprise sur une erreur définitive
    assert dormi["appele"] is False


def test_exception_hors_vocabulaire_n_est_pas_non_plus_retentee() -> None:
    """Une exception qui n'est ni ErreurTransitoire ni ErreurDefinitive (ex. ValueError d'un
    bug de programmation) reste non retentée par défaut : seul le transitoire est un motif
    de reprise, tout le reste alerte immédiatement."""
    appels = {"n": 0}

    def tache() -> None:
        appels["n"] += 1
        raise ValueError("bug de programmation, pas une panne réseau")

    with pytest.raises(ValueError):
        executer_avec_reprise(
            tache,
            politique=_politique(tentatives_max=5),
            nom_tache="test_valueerror",
            dormir=lambda _: None,
        )

    assert appels["n"] == 1


def test_politique_depuis_settings_reflete_la_configuration() -> None:
    from edumatch.config import load_settings
    from edumatch.orchestration.reprise import politique_depuis_settings

    settings = load_settings("prod")
    politique = politique_depuis_settings(settings)

    assert politique.tentatives_max == settings.orchestration.tentatives_max
    assert politique.delai_secondes == settings.orchestration.delai_reprise_secondes
    assert politique.facteur_backoff == settings.orchestration.facteur_backoff
