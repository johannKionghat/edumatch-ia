"""Test du point d'entrée de production du connecteur référentiels : `telecharger_tous`.

`referentiels.telecharger_tous()` est l'équivalent, pour ce connecteur, de
`parcoursup.telecharger_tous()` et `sirene.telecharger_tous()` : c'est la
fonction qu'un DAG appelle réellement en production, pas `telecharger_ideo`
ou les fonctions RNCP prises séparément (déjà couvertes par
`test_ingestion_referentiels.py` et `test_ingestion_referentiels_rncp.py`).
Ce module exerce l'enchaînement des deux volets — IDÉO puis RNCP — dans une
seule session HTTP, avec une session factice qui sait répondre aux deux.

Aucun accès réseau.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Self

import pytest

from edumatch.config import load_settings
from edumatch.ingestion.referentiels import telecharger_tous

URL_IDEO_FORMATIONS = "https://exemple.test/ideo/formations.csv"
URL_CATALOGUE_RNCP = "https://exemple.test/api/1/datasets/repertoire-national-des-certifications-professionnelles-et-repertoire-specifique/"
URL_ZIP_RNCP = "https://exemple.test/export-fiches-csv-2026-08-29.zip"
URL_CATALOGUE_FT = "https://exemple.test/api/1/datasets/58da857388ee384902e505f5/"
URL_XLSX_FT = "https://exemple.test/rome-arborescence-des-secteurs-naf.xlsx"

CONTENU_IDEO_UTF8 = '"code";"libellé"\n"A01";"formation générale"\n'.encode()
NOM_CSV_STANDARD = "export_fiches_CSV_Standard_2026_08_29.csv"
NOM_CSV_ROME = "export_fiches_CSV_Rome_2026_08_29.csv"
CONTENU_RNCP_UTF8 = '"Id_Fiche";"Intitule"\n"RNCP1";"Assistant(e) en comptabilité"\n'.encode()
CONTENU_ROME_UTF8 = b'"Numero_Fiche";"Codes_Rome_Code"\n"RNCP1";"M1607"\n'


def _contenu_xlsx_minimal() -> bytes:
    """Un xlsx n'est qu'un ZIP : suffisant pour passer le contrôle de contrat du connecteur.

    Le résultat est figé une fois pour toutes dans `CONTENU_XLSX_FT` ci-dessous, et
    c'est cette constante — jamais deux appels distincts — qui sert à la fois à
    fabriquer la réponse et à vérifier ce qui a été écrit. `ZipFile.writestr`
    horodate en effet chaque entrée à la seconde courante : deux appels séparés par
    une frontière de seconde produisent des octets différents à contenu identique.
    Comparer deux constructions indépendantes rendait ce test instable, d'autant
    plus souvent que la suite complète était chargée et l'intervalle allongé.
    """
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, mode="w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
    return tampon.getvalue()


CONTENU_XLSX_FT = _contenu_xlsx_minimal()


def _zip_rncp() -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, mode="w") as archive:
        archive.writestr(NOM_CSV_STANDARD, CONTENU_RNCP_UTF8)
        archive.writestr(NOM_CSV_ROME, CONTENU_ROME_UTF8)
    return tampon.getvalue()


CATALOGUE_RNCP = {
    "resources": [
        {
            "title": "export-fiches-csv-2026-08-29.zip",
            "format": "zip",
            "url": URL_ZIP_RNCP,
            "last_modified": "2026-08-29T02:00:12.883000+00:00",
        }
    ]
}

CATALOGUE_FT = {
    "resources": [
        {"title": "Les tables de correspondance ROME / autres référentiels - ROME/NAF", "format": "xlsx", "url": URL_XLSX_FT}
    ]
}


class _ReponseFluxIdeo:
    """Reproduit l'interface utilisée par `telecharger_en_flux` (IDÉO)."""

    def __init__(self, contenu: bytes) -> None:
        self._contenu = contenu

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        yield self._contenu

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


class _ReponseJsonRncp:
    """Reproduit l'interface utilisée pour le catalogue RNCP (`.json()`, pas de flux)."""

    def __init__(self, corps: dict) -> None:
        self._corps = corps

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._corps


class _ReponseZipRncp:
    """Reproduit l'interface utilisée pour l'archive RNCP (`.content`, pas de flux)."""

    def __init__(self, contenu: bytes) -> None:
        self.content = contenu

    def raise_for_status(self) -> None:
        return None


class SessionFacticeCombinee:
    """Une seule session factice, servant à la fois IDÉO et RNCP.

    `telecharger_ideo` appelle `.get(url, stream=True, timeout=...)` et lit la
    réponse en flux (`iter_content`) ; les fonctions RNCP appellent
    `.get(url, timeout=...)` sans `stream` et lisent `.json()` ou `.content`.
    Une session de production doit répondre correctement aux deux, c'est
    exactement ce que `telecharger_tous` exige d'elle en pratique.
    """

    def __init__(self) -> None:
        self.urls_appelees: list[str] = []

    def get(self, url: str, stream: bool = False, timeout: float | None = None):
        self.urls_appelees.append(url)
        if url == URL_IDEO_FORMATIONS:
            return _ReponseFluxIdeo(CONTENU_IDEO_UTF8)
        if url == URL_CATALOGUE_RNCP:
            return _ReponseJsonRncp(CATALOGUE_RNCP)
        if url == URL_ZIP_RNCP:
            return _ReponseZipRncp(_zip_rncp())
        if url == URL_CATALOGUE_FT:
            return _ReponseJsonRncp(CATALOGUE_FT)
        if url == URL_XLSX_FT:
            return _ReponseFluxIdeo(CONTENU_XLSX_FT)
        raise AssertionError(f"URL inattendue appelée par telecharger_tous : {url}")


@pytest.fixture()
def settings_test(configs_dir_isole: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Un seul jeu IDÉO (`formations`) et le jeu RNCP, comme déclaré dans `configs_dir_isole`."""
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(tmp_path / "data"))
    return load_settings("dev", configs_dir=configs_dir_isole)


def test_telecharger_tous_enchaine_ideo_puis_rncp_dans_une_seule_session(settings_test) -> None:
    """Preuve du critère B3.3 : le point d'entrée de production, celui que le DAG appelle,
    exerce réellement l'enchaînement des deux volets, pas seulement chacun séparément.
    """
    session = SessionFacticeCombinee()

    resultats = telecharger_tous(settings=settings_test, session=session)

    assert [r.source for r in resultats] == ["ideo", "rncp", "rncp", "france_travail"], (
        "l'ordre annoncé par le docstring de telecharger_tous est IDÉO, RNCP (standard puis "
        "ROME), puis France Travail"
    )
    assert [r.jeu for r in resultats] == ["formations", "rncp", "rncp_rome", "france_travail_rome_naf"]
    assert resultats[0].chemin.read_bytes() == CONTENU_IDEO_UTF8
    assert resultats[1].chemin.read_bytes() == CONTENU_RNCP_UTF8
    assert resultats[2].chemin.read_bytes() == CONTENU_ROME_UTF8
    assert resultats[3].chemin.read_bytes() == CONTENU_XLSX_FT
    assert session.urls_appelees == [
        URL_IDEO_FORMATIONS,
        URL_CATALOGUE_RNCP,
        URL_ZIP_RNCP,
        URL_ZIP_RNCP,  # deuxième téléchargement de la même archive pour le membre ROME — voir _telecharger_membre
        URL_CATALOGUE_FT,
        URL_XLSX_FT,
    ]
