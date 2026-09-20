"""La page d'attribution est générée depuis les manifestes, jamais saisie à la main.

Non-régression d'un défaut réel : la page annonçait une collecte du 28 au 30 août 2026
alors que les manifestes de Sirene et des référentiels portaient le 17 septembre. Une
attribution fausse ne viole pas seulement une règle interne : la Licence Ouverte v2.0
impose de citer la source **et sa date** (article 2).

Ces tests portent sur des manifestes fabriqués dans un dossier temporaire : ils vérifient
la mécanique. Le fait que la page **versionnée** corresponde aux manifestes réels est
vérifié séparément, par `tests/data/test_sources_licences_a_jour.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edumatch.api import sources_licences
from edumatch.config import Settings, load_settings


def _ecrire(chemin: Path, contenu: dict) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")


@pytest.fixture()
def settings_manifestes(tmp_path: Path) -> Settings:
    """Trois manifestes minimaux, aux dates volontairement différentes."""
    settings = load_settings("prod").model_copy(update={"data_root": tmp_path})
    _ecrire(
        settings.raw_dir / "parcoursup" / "manifeste.json",
        {
            "2018": {"millesime": 2018, "date_telechargement": "2026-08-28T10:00:00+00:00"},
            "2025": {"millesime": 2025, "date_telechargement": "2026-08-28T10:05:00+00:00"},
        },
    )
    _ecrire(
        settings.raw_dir / "sirene" / "manifeste.json",
        {
            "StockEtablissement": {
                "date_telechargement": "2026-09-17T21:00:00+00:00",
                "date_publication_stock": "2026-09-01T09:08:32+00:00",
            }
        },
    )
    _ecrire(
        settings.external_dir / "referentiels" / "manifeste.json",
        {
            "ideo:formations": {
                "source": "ideo",
                "licence": "ODbL (odc-odbl)",
                "date_telechargement": "2026-09-17T21:54:00+00:00",
            },
            "rncp:2026-09-17": {
                "source": "rncp",
                "licence": "Licence Ouverte v2.0",
                "date_telechargement": "2026-09-17T21:54:10+00:00",
            },
        },
    )
    return settings


def test_les_dates_viennent_des_manifestes(settings_manifestes: Settings) -> None:
    """Chaque ligne porte la date du fichier réellement téléchargé."""
    par_jeu = {s.jeu: s for s in sources_licences.collecter(settings_manifestes)}

    parcoursup = next(s for jeu, s in par_jeu.items() if jeu.startswith("Parcoursup"))
    sirene = next(s for jeu, s in par_jeu.items() if jeu.startswith("Base Sirene"))
    assert parcoursup.date == "2026-08-28"
    assert sirene.date == "2026-09-17 (stock publié le 2026-09-01)"


def test_la_licence_odbl_est_reconnue_sur_ideo(settings_manifestes: Settings) -> None:
    """L'ODbL impose le partage à l'identique : la confondre avec la Licence Ouverte serait une faute de licence."""
    sources = {s.producteur: s for s in sources_licences.collecter(settings_manifestes)}

    assert sources["ONISEP"].licence == sources_licences.LICENCE_ODBL
    assert sources["France Compétences"].licence == sources_licences.LICENCE_OUVERTE


def test_une_date_qui_change_change_la_page(settings_manifestes: Settings) -> None:
    """C'est tout l'intérêt : une nouvelle collecte doit se voir sur la page."""
    avant = sources_licences.rendre(sources_licences.collecter(settings_manifestes))

    _ecrire(
        settings_manifestes.raw_dir / "parcoursup" / "manifeste.json",
        {"2018": {"millesime": 2018, "date_telechargement": "2027-01-15T10:00:00+00:00"}},
    )
    apres = sources_licences.rendre(sources_licences.collecter(settings_manifestes))

    assert "2026-08-28" in avant and "2027-01-15" not in avant
    assert "2027-01-15" in apres and "2026-08-28" not in apres


def test_plusieurs_dates_de_collecte_sont_toutes_declarees(settings_manifestes: Settings) -> None:
    """Deux dates distinctes se lisent « X et Y » ; au-delà, un intervalle."""
    _ecrire(
        settings_manifestes.raw_dir / "parcoursup" / "manifeste.json",
        {
            "2018": {"millesime": 2018, "date_telechargement": "2026-08-28T10:00:00+00:00"},
            "2019": {"millesime": 2019, "date_telechargement": "2026-08-30T10:00:00+00:00"},
        },
    )
    deux = next(s for s in sources_licences.collecter(settings_manifestes) if s.jeu.startswith("Parcoursup"))
    assert deux.date == "2026-08-28 et 2026-08-30"

    _ecrire(
        settings_manifestes.raw_dir / "parcoursup" / "manifeste.json",
        {
            str(a): {"millesime": a, "date_telechargement": f"2026-08-{j}T10:00:00+00:00"}
            for a, j in ((2018, 28), (2019, 29), (2020, 30))
        },
    )
    trois = next(s for s in sources_licences.collecter(settings_manifestes) if s.jeu.startswith("Parcoursup"))
    assert trois.date == "du 2026-08-28 au 2026-08-30"


def test_un_manifeste_absent_ne_fabrique_pas_de_ligne(tmp_path: Path) -> None:
    """Mieux vaut une page incomplète qu'une attribution inventée."""
    settings = load_settings("prod").model_copy(update={"data_root": tmp_path})

    assert sources_licences.collecter(settings) == []


def test_un_libelle_de_manifeste_ne_peut_pas_injecter_de_html(settings_manifestes: Settings) -> None:
    """Les libellés viennent d'un fichier : ils sont échappés, jamais interprétés."""
    _ecrire(
        settings_manifestes.external_dir / "referentiels" / "manifeste.json",
        {
            "ideo:formations": {
                "source": "<script>alert(1)</script>",
                "licence": "ODbL (odc-odbl)",
                "date_telechargement": "2026-09-17T21:54:00+00:00",
            }
        },
    )
    page = sources_licences.rendre(sources_licences.collecter(settings_manifestes))

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_la_page_generee_reste_du_html_complet(settings_manifestes: Settings) -> None:
    page = sources_licences.rendre(sources_licences.collecter(settings_manifestes))

    assert page.startswith("<!DOCTYPE html>")
    assert page.rstrip().endswith("</html>")
    assert page.count("<tr>") == page.count("</tr>")


def test_generer_ecrit_la_page_de_facon_atomique(settings_manifestes: Settings, tmp_path: Path) -> None:
    """Écriture par fichier temporaire renommé : jamais de page tronquée servie par l'API."""
    destination = tmp_path / "page.html"

    chemin = sources_licences.generer(settings_manifestes, destination=destination)

    assert chemin == destination
    assert destination.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    assert not list(tmp_path.glob("*.part"))
