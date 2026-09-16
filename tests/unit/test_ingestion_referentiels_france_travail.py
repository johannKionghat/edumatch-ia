"""Tests du connecteur France Travail (src/edumatch/ingestion/_referentiels_france_travail.py).

Aucun accès réseau. Couvre la résolution par sous-chaîne de titre (le nom du
fichier change à chaque révision du ROME, contrairement aux jeux IDÉO à URL
fixe), l'idempotence par empreinte sur un nom de fichier stable (contrairement
à RNCP, daté par publication), et le contrôle de contrat (un xlsx est un ZIP
valide).
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Self

import pytest
import requests

from edumatch.config import load_settings
from edumatch.ingestion._flux import ErreurDefinitive, ErreurTransitoire
from edumatch.ingestion._referentiels_communs import (
    ErreurCatalogueReferentiels,
    ErreurContratReferentiels,
    ErreurReseauReferentiels,
)
from edumatch.ingestion._referentiels_france_travail import (
    chemin_destination,
    resoudre_ressource,
    telecharger,
)

URL_CATALOGUE = "https://exemple.test/api/1/datasets/58da857388ee384902e505f5/"
URL_XLSX = "https://exemple.test/rome-arborescence-des-secteurs-naf-juin-2026.xlsx"
TITRE_RESSOURCE = "Les tables de correspondance ROME / autres référentiels - ROME/NAF"


def _contenu_xlsx_minimal() -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, mode="w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
    return tampon.getvalue()


CONTENU_XLSX_NOMINAL = _contenu_xlsx_minimal()


def _ressource(titre: str, format_: str, url: str) -> dict:
    return {"title": titre, "format": format_, "url": url}


def _catalogue(resources: list[dict]) -> dict:
    return {"resources": resources}


CATALOGUE_NOMINAL = _catalogue([_ressource(TITRE_RESSOURCE, "xlsx", URL_XLSX)])


class _ReponseJson:
    def __init__(self, corps: dict, statut_en_erreur: bool = False) -> None:
        self._corps = corps
        self._statut_en_erreur = statut_en_erreur

    def raise_for_status(self) -> None:
        if self._statut_en_erreur:
            raise requests.exceptions.HTTPError("404 Client Error: Not Found")

    def json(self) -> dict:
        return self._corps


class _ReponseFlux:
    """Reproduit l'interface utilisée par `telecharger_en_flux` (comme IDÉO)."""

    def __init__(self, contenu: bytes, statut_en_erreur: bool = False) -> None:
        self._contenu = contenu
        self._statut_en_erreur = statut_en_erreur

    def raise_for_status(self) -> None:
        if self._statut_en_erreur:
            raise requests.exceptions.HTTPError("500 Server Error")

    def iter_content(self, chunk_size: int):
        yield self._contenu

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


class SessionFactice:
    def __init__(
        self,
        catalogue: dict = CATALOGUE_NOMINAL,
        catalogue_en_erreur: bool = False,
        contenu_xlsx: bytes = CONTENU_XLSX_NOMINAL,
        xlsx_en_erreur: bool = False,
    ) -> None:
        self.catalogue = catalogue
        self.catalogue_en_erreur = catalogue_en_erreur
        self.contenu_xlsx = contenu_xlsx
        self.xlsx_en_erreur = xlsx_en_erreur
        self.appels_catalogue = 0
        self.appels_xlsx = 0

    def get(self, url: str, stream: bool = False, timeout: float | None = None):
        if url == URL_CATALOGUE:
            self.appels_catalogue += 1
            return _ReponseJson(self.catalogue, statut_en_erreur=self.catalogue_en_erreur)
        self.appels_xlsx += 1
        return _ReponseFlux(self.contenu_xlsx, statut_en_erreur=self.xlsx_en_erreur)


@pytest.fixture()
def settings_test(configs_dir_isole: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(tmp_path / "data"))
    return load_settings("dev", configs_dir=configs_dir_isole)


# ─── Résolution par sous-chaîne de titre ────────────────────────────────────


def test_resoudre_ressource_trouve_la_ressource_par_sous_chaine_de_titre(settings_test) -> None:
    session = SessionFactice()
    ressource = resoudre_ressource(settings_test, session=session)

    assert ressource.url == URL_XLSX
    assert ressource.titre == TITRE_RESSOURCE
    assert session.appels_catalogue == 1
    assert session.appels_xlsx == 0, "résoudre une ressource ne doit déclencher aucun téléchargement"


def test_resoudre_ressource_ignore_un_format_different(settings_test) -> None:
    catalogue = _catalogue([_ressource(TITRE_RESSOURCE, "csv", "https://exemple.test/pas-la-bonne-ressource.csv")])
    session = SessionFactice(catalogue=catalogue)

    with pytest.raises(ErreurCatalogueReferentiels, match="ROME/NAF"):
        resoudre_ressource(settings_test, session=session)


def test_resoudre_ressource_leve_si_plusieurs_ressources_correspondent(settings_test) -> None:
    catalogue = _catalogue(
        [
            _ressource(TITRE_RESSOURCE, "xlsx", URL_XLSX),
            _ressource(TITRE_RESSOURCE + " (bis)", "xlsx", "https://exemple.test/autre.xlsx"),
        ]
    )
    session = SessionFactice(catalogue=catalogue)

    with pytest.raises(ErreurCatalogueReferentiels, match="ambiguë"):
        resoudre_ressource(settings_test, session=session)


def test_resoudre_ressource_leve_si_le_catalogue_est_injoignable(settings_test) -> None:
    session = SessionFactice(catalogue_en_erreur=True)

    with pytest.raises(ErreurReseauReferentiels):
        resoudre_ressource(settings_test, session=session)


# ─── Téléchargement, contrat de conteneur ZIP, manifeste ───────────────────


def test_telecharger_ecrit_le_fichier_et_le_manifeste(settings_test) -> None:
    session = SessionFactice()
    ressource = resoudre_ressource(settings_test, session=session)
    resultat = telecharger(ressource, settings_test, session=session)

    assert resultat.telecharge is True
    assert resultat.source == "france_travail"
    assert resultat.chemin == chemin_destination(settings_test)
    assert resultat.chemin.read_bytes() == CONTENU_XLSX_NOMINAL
    assert resultat.licence == "Licence Ouverte v2.0"

    manifeste = json.loads((settings_test.external_dir / "referentiels" / "manifeste.json").read_text())
    assert "france_travail_rome_naf:rome_naf" in manifeste


def test_second_appel_ne_retelecharge_pas_si_intact(settings_test) -> None:
    session = SessionFactice()
    ressource = resoudre_ressource(settings_test, session=session)
    telecharger(ressource, settings_test, session=session)
    resultat_second = telecharger(ressource, settings_test, session=session)

    assert session.appels_xlsx == 1
    assert resultat_second.telecharge is False


def test_fichier_qui_nest_pas_un_zip_valide_leve_une_erreur_de_contrat(settings_test) -> None:
    session = SessionFactice(contenu_xlsx=b"ceci n'est pas un fichier xlsx")
    ressource = resoudre_ressource(settings_test, session=session)

    with pytest.raises(ErreurContratReferentiels, match="ZIP"):
        telecharger(ressource, settings_test, session=session)


def test_erreur_http_pendant_le_telechargement_leve_une_erreur_transitoire(settings_test) -> None:
    session = SessionFactice(xlsx_en_erreur=True)
    ressource = resoudre_ressource(settings_test, session=session)

    with pytest.raises(ErreurReseauReferentiels):
        telecharger(ressource, settings_test, session=session)


def test_erreur_catalogue_est_definitive_pas_transitoire(settings_test) -> None:
    with pytest.raises(ErreurCatalogueReferentiels) as excinfo:
        resoudre_ressource(settings_test, session=SessionFactice(catalogue=_catalogue([])))

    assert isinstance(excinfo.value, ErreurDefinitive)
    assert not isinstance(excinfo.value, ErreurTransitoire)


def test_erreur_reseau_est_transitoire_pas_definitive(settings_test) -> None:
    with pytest.raises(ErreurReseauReferentiels) as excinfo:
        resoudre_ressource(settings_test, session=SessionFactice(catalogue_en_erreur=True))

    assert isinstance(excinfo.value, ErreurTransitoire)
    assert not isinstance(excinfo.value, ErreurDefinitive)


# ─── Aucune URL de fichier en dur ───────────────────────────────────────────


def test_aucune_url_france_travail_en_dur() -> None:
    """Le nom du fichier change à chaque révision du ROME : rien ici ne doit en coder une."""
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "edumatch"
        / "ingestion"
        / "_referentiels_france_travail.py"
    ).read_text(encoding="utf-8")

    assert "francetravail.org" not in source
    assert "58da857388ee384902e505f5" not in source
