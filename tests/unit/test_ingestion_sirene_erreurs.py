"""Tests du vocabulaire d'erreurs du connecteur Sirene — transitoire contre définitif.

Séparé de `test_ingestion_sirene.py` (déjà volumineux) pour isoler le sujet de
cette revue : la distinction entre un échec qu'un orchestrateur doit retenter
et un échec qu'il doit remonter à un humain, ainsi que la vérification de la
taille annoncée par le catalogue face à la taille réellement écrite. Réutilise
les factices et la fixture `settings_test` déjà définies pour le connecteur.

Aucun accès réseau : la couche HTTP reste remplacée par `SessionFactice`.
"""

from __future__ import annotations

import logging

import pytest
import requests

from edumatch.ingestion._flux import ErreurDefinitive, ErreurTransitoire
from edumatch.ingestion.sirene import (
    ErreurCatalogueSirene,
    ErreurReseauSirene,
    ErreurTelechargementSirene,
    resoudre_ressources,
    telecharger_fichier,
)
from tests.unit.test_ingestion_sirene import (
    CONTENU_PARQUET,
    URL_STOCK_ETABLISSEMENT,
    SessionFactice,
    _catalogue,
    _ressource,
    settings_test,
)

__all__ = ["settings_test"]  # réexportée comme fixture, pas un import inutilisé


# ─── Transitoire contre définitif — ce que retentera ou non un orchestrateur ─
#
# `ErreurTelechargementSirene` reste la base commune ; ces tests prouvent
# que chaque nature d'échec lève bien la sous-classe qui lui correspond, pas
# seulement la base — c'est ce que le DAG Airflow doit pouvoir distinguer
# sans inspecter le texte du message.


def test_catalogue_injoignable_leve_lerreur_reseau_transitoire(settings_test) -> None:
    session = SessionFactice(catalogue_en_erreur=True)

    with pytest.raises(ErreurReseauSirene) as excinfo:
        resoudre_ressources(settings=settings_test, session=session)

    assert isinstance(excinfo.value, ErreurTelechargementSirene)
    assert isinstance(excinfo.value, ErreurTransitoire)
    assert not isinstance(excinfo.value, ErreurDefinitive)


def test_catalogue_mal_forme_leve_lerreur_catalogue_definitive(settings_test) -> None:
    session = SessionFactice(catalogue=[])  # racine non-objet : contrat rompu

    with pytest.raises(ErreurCatalogueSirene) as excinfo:
        resoudre_ressources(settings=settings_test, session=session)

    assert isinstance(excinfo.value, ErreurTelechargementSirene)
    assert isinstance(excinfo.value, ErreurDefinitive)
    assert not isinstance(excinfo.value, ErreurTransitoire)


def test_fichier_absent_du_catalogue_leve_lerreur_catalogue_definitive(settings_test) -> None:
    catalogue_sans_le_fichier = _catalogue(
        [_ressource("Sirene : Fichier AutreFichier - 01 août 2026 (format parquet)", "parquet", "https://exemple.test/autre")]
    )
    session = SessionFactice(catalogue=catalogue_sans_le_fichier)

    with pytest.raises(ErreurCatalogueSirene):
        resoudre_ressources(settings=settings_test, session=session)


def test_coupure_reseau_pendant_le_telechargement_leve_lerreur_reseau_transitoire(settings_test) -> None:
    session = SessionFactice(erreur_en_cours_de_flux=requests.exceptions.ConnectionError("coupure"))
    ressources = resoudre_ressources(settings=settings_test, session=session)

    with pytest.raises(ErreurReseauSirene) as excinfo:
        telecharger_fichier(ressources[0], settings=settings_test, session=session)

    assert isinstance(excinfo.value, ErreurTransitoire)
    assert not isinstance(excinfo.value, ErreurDefinitive)


# ─── Correctif 2 : taille annoncée contre taille réellement écrite ──────────
#
# `taille_octets_annoncee` (issu de `filesize` au catalogue) est maintenant
# comparé à la taille réellement écrite après téléchargement. Un écart est
# journalisé en avertissement — jamais levé, le catalogue n'apportant aucune
# garantie contractuelle sur cette valeur.


def test_ecart_de_taille_est_journalise_en_avertissement(settings_test, caplog: pytest.LogCaptureFixture) -> None:
    """Le catalogue annonce 30 octets, le contenu réellement servi n'en fait que 5 : écart flagrant."""
    catalogue_taille_annoncee = _catalogue(
        [
            _ressource(
                "Sirene : Fichier StockEtablissement - 01 août 2026 (format parquet)",
                "parquet",
                URL_STOCK_ETABLISSEMENT,
                filesize=30,
            )
        ]
    )
    session = SessionFactice(catalogue=catalogue_taille_annoncee, contenu_fichier=b"x" * 5)
    ressources = resoudre_ressources(settings=settings_test, session=session)

    with caplog.at_level(logging.WARNING, logger="edumatch.ingestion.sirene"):
        telecharger_fichier(ressources[0], settings=settings_test, session=session)

    messages = [enregistrement.message for enregistrement in caplog.records]
    assert any("ECART_TAILLE_SIRENE" in message and "StockEtablissement" in message for message in messages), messages


def test_taille_conforme_ne_journalise_aucun_avertissement(settings_test, caplog: pytest.LogCaptureFixture) -> None:
    catalogue_taille_annoncee = _catalogue(
        [
            _ressource(
                "Sirene : Fichier StockEtablissement - 01 août 2026 (format parquet)",
                "parquet",
                URL_STOCK_ETABLISSEMENT,
                filesize=len(CONTENU_PARQUET),
            )
        ]
    )
    session = SessionFactice(catalogue=catalogue_taille_annoncee)
    ressources = resoudre_ressources(settings=settings_test, session=session)

    with caplog.at_level(logging.WARNING, logger="edumatch.ingestion.sirene"):
        telecharger_fichier(ressources[0], settings=settings_test, session=session)

    assert not any("ECART_TAILLE_SIRENE" in enregistrement.message for enregistrement in caplog.records)


def test_taille_annoncee_nulle_ne_journalise_aucun_avertissement(settings_test, caplog: pytest.LogCaptureFixture) -> None:
    """`filesize` à 0 (ou absent) : rien à comparer, ce n'est pas une anomalie en soi."""
    catalogue_sans_taille = _catalogue(
        [
            _ressource(
                "Sirene : Fichier StockEtablissement - 01 août 2026 (format parquet)",
                "parquet",
                URL_STOCK_ETABLISSEMENT,
                filesize=0,
            )
        ]
    )
    session = SessionFactice(catalogue=catalogue_sans_taille)
    ressources = resoudre_ressources(settings=settings_test, session=session)
    assert ressources[0].taille_octets_annoncee == 0

    with caplog.at_level(logging.WARNING, logger="edumatch.ingestion.sirene"):
        telecharger_fichier(ressources[0], settings=settings_test, session=session)

    assert not any("ECART_TAILLE_SIRENE" in enregistrement.message for enregistrement in caplog.records)
