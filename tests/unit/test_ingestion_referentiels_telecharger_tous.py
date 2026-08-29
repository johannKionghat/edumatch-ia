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

import pytest

from edumatch.config import load_settings
from edumatch.ingestion.referentiels import telecharger_tous

URL_IDEO_FORMATIONS = "https://exemple.test/ideo/formations.csv"
URL_CATALOGUE_RNCP = "https://exemple.test/api/1/datasets/repertoire-national-des-certifications-professionnelles-et-repertoire-specifique/"
URL_ZIP_RNCP = "https://exemple.test/export-fiches-csv-2026-08-29.zip"

CONTENU_IDEO_UTF8 = '"code";"libellé"\n"A01";"formation générale"\n'.encode("utf-8")
NOM_CSV_STANDARD = "export_fiches_CSV_Standard_2026_08_29.csv"
CONTENU_RNCP_UTF8 = '"Id_Fiche";"Intitule"\n"RNCP1";"Assistant(e) en comptabilité"\n'.encode("utf-8")


def _zip_rncp() -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, mode="w") as archive:
        archive.writestr(NOM_CSV_STANDARD, CONTENU_RNCP_UTF8)
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


class _ReponseFluxIdeo:
    """Reproduit l'interface utilisée par `telecharger_en_flux` (IDÉO)."""

    def __init__(self, contenu: bytes) -> None:
        self._contenu = contenu

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):  # noqa: ARG002 - signature imposée par requests
        yield self._contenu

    def __enter__(self) -> "_ReponseFluxIdeo":
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

    def get(self, url: str, stream: bool = False, timeout: float | None = None):  # noqa: ARG002
        self.urls_appelees.append(url)
        if url == URL_IDEO_FORMATIONS:
            return _ReponseFluxIdeo(CONTENU_IDEO_UTF8)
        if url == URL_CATALOGUE_RNCP:
            return _ReponseJsonRncp(CATALOGUE_RNCP)
        if url == URL_ZIP_RNCP:
            return _ReponseZipRncp(_zip_rncp())
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

    assert [r.source for r in resultats] == ["ideo", "rncp"], (
        "l'ordre annoncé par le docstring de telecharger_tous est IDÉO puis RNCP"
    )
    assert [r.jeu for r in resultats] == ["formations", "rncp"]
    assert resultats[0].chemin.read_bytes() == CONTENU_IDEO_UTF8
    assert resultats[1].chemin.read_bytes() == CONTENU_RNCP_UTF8
    assert session.urls_appelees == [URL_IDEO_FORMATIONS, URL_CATALOGUE_RNCP, URL_ZIP_RNCP]
