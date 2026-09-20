"""La page d'attribution versionnée doit correspondre aux manifestes d'ingestion.

C'est le test qui ferme le motif de blocage E : sans lui, un retéléchargement des sources
laisserait la page servie par l'API annoncer une date de collecte fausse, et personne ne
le verrait. Ici, la divergence casse la chaîne.

Le test lit les manifestes réels de `data/`. Ils ne sont pas versionnés : quand ils sont
absents — sur la forge, par exemple — il n'y a rien à comparer et le test est ignoré, avec
son motif. Il protège donc le poste de développement et le pipeline, là où les
retéléchargements ont lieu.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edumatch.api import sources_licences
from edumatch.config import load_settings

SETTINGS = load_settings("prod")
MANIFESTES = (
    SETTINGS.raw_dir / "parcoursup" / "manifeste.json",
    SETTINGS.raw_dir / "sirene" / "manifeste.json",
    SETTINGS.external_dir / "referentiels" / "manifeste.json",
)

besoin_de_manifestes = pytest.mark.skipif(
    not all(chemin.exists() for chemin in MANIFESTES),
    reason="manifestes d'ingestion absents : rien à comparer (data/ n'est pas versionné)",
)


@besoin_de_manifestes
def test_la_page_versionnee_correspond_aux_manifestes() -> None:
    """Si ce test échoue, régénérer la page : `make sources-licences`."""
    page = Path(sources_licences.DOSSIER_STATIQUE / sources_licences.NOM_PAGE)
    attendue = sources_licences.rendre(sources_licences.collecter(SETTINGS))

    reelle = page.read_text(encoding="utf-8")

    assert reelle == attendue, (
        "La page d'attribution diverge des manifestes d'ingestion : une source a été "
        "retéléchargée sans régénérer la page. Lancer `make sources-licences`."
    )


@besoin_de_manifestes
def test_chaque_source_declare_une_date_de_collecte() -> None:
    """Une ligne sans date n'attribue rien : la Licence Ouverte exige la date (art. 2)."""
    sources = sources_licences.collecter(SETTINGS)

    assert sources, "aucune source collectée alors que les manifestes existent"
    for source in sources:
        assert source.date[:4].isdigit(), f"{source.jeu} : date de collecte absente"
        assert source.producteur and source.licence, f"{source.jeu} : producteur ou licence absent"
