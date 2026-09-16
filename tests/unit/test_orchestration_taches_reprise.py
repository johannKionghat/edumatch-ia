"""Reprise sur erreur, de bout en bout avec un vrai connecteur (E33, critère 3.4).

`test_orchestration_reprise.py` prouve la mécanique de `executer_avec_reprise`
avec des erreurs factices. Ce test-ci referme la boucle avec le code réel
qu'un DAG appellerait vraiment : `edumatch.ingestion.sirene.telecharger_tous`,
dont `resoudre_ressources` lève `ErreurReseauSirene` — une `ErreurTransitoire`
réelle, pas une classe fabriquée pour l'occasion — quand le catalogue data.gouv
répond en erreur. Aucun accès réseau : la session HTTP reste remplacée par
`SessionFactice`, comme dans le reste des tests d'ingestion Sirene.
"""

from __future__ import annotations

import pytest

from edumatch.ingestion import sirene
from edumatch.orchestration.reprise import PolitiqueReprise, executer_avec_reprise
from tests.unit.test_ingestion_sirene import (
    CATALOGUE_NOMINAL,
    SessionFactice,
    _ReponseJson,
    settings_test,
)

__all__ = ["settings_test"]  # réexportée comme fixture


class _SessionInstable(SessionFactice):
    """Comme `SessionFactice`, mais le catalogue échoue les `echecs_avant_succes` premiers appels.

    Simule une coupure réseau qui se résorbe d'elle-même après quelques
    tentatives — le cas exact que `orchestration.reprise` doit absorber sans
    intervention humaine.
    """

    def __init__(self, echecs_avant_succes: int, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._echecs_restants = echecs_avant_succes

    def get(self, url: str, stream: bool = False, timeout: float | None = None):
        if not stream and self._echecs_restants > 0:
            self._echecs_restants -= 1
            self.appels_catalogue += 1
            return _ReponseJson(self.catalogue, statut_en_erreur=True)
        return super().get(url, stream=stream, timeout=timeout)


def test_ingestion_sirene_reussit_apres_deux_pannes_reseau_transitoires(settings_test) -> None:
    session = _SessionInstable(echecs_avant_succes=2, catalogue=CATALOGUE_NOMINAL)
    delais_observes: list[float] = []
    politique = PolitiqueReprise(tentatives_max=3, delai_secondes=1.0, facteur_backoff=2.0)

    resultats = executer_avec_reprise(
        lambda: sirene.telecharger_tous(settings=settings_test, session=session),
        politique=politique,
        nom_tache="ingerer_sirene_test",
        dormir=delais_observes.append,
    )

    assert len(resultats) == 1  # le fichier configuré (StockEtablissement) est bien téléchargé
    assert session.appels_catalogue == 3  # deux échecs, puis la tentative qui réussit
    assert delais_observes == [1.0, 2.0]  # temporisation croissante entre chaque reprise


def test_ingestion_sirene_persiste_en_panne_epuise_les_tentatives(settings_test) -> None:
    """Une panne réseau qui ne se résorbe jamais finit par alerter, pas par boucler indéfiniment."""
    from edumatch.orchestration.reprise import ErreurRepriseEpuisee

    session = _SessionInstable(echecs_avant_succes=10, catalogue=CATALOGUE_NOMINAL)
    politique = PolitiqueReprise(tentatives_max=3, delai_secondes=1.0, facteur_backoff=2.0)

    with pytest.raises(ErreurRepriseEpuisee):
        executer_avec_reprise(
            lambda: sirene.telecharger_tous(settings=settings_test, session=session),
            politique=politique,
            nom_tache="ingerer_sirene_test",
            dormir=lambda _: None,
        )

    assert session.appels_catalogue == 3  # jamais plus que tentatives_max
