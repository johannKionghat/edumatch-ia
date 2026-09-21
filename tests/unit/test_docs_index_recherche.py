"""L'index de recherche de la documentation suit les pages, et ses ancres suivent site.js."""

from __future__ import annotations

import importlib.util
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "generer_index_recherche", RACINE / "scripts" / "generer_index_recherche.py"
)
generateur = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generateur)


def test_index_versionne_a_jour() -> None:
    """Une page modifiée sans `make docs-index` laisserait la recherche pointer vers l'ancien texte."""
    attendu = generateur.rendre(generateur.construire_index())
    assert generateur.DESTINATION.read_text(encoding="utf-8") == attendu, (
        "relancer `make docs-index`"
    )


def test_slug_identique_a_site_js() -> None:
    assert generateur.slug("Dérive : limite à 0,20 (PSI)") == "derive-limite-a-0-20-psi"
    assert generateur.slug("  Ça, c'est l'été  ") == "ca-c-est-l-ete"


def test_h3_prefixe_par_son_h2_et_collision_numerotee() -> None:
    sections = [
        {"niveau": "h2", "id": "adr-0001", "titre": "ADR 0001"},
        {"niveau": "h3", "id": None, "titre": "Contexte"},
        {"niveau": "h2", "id": "adr-0002", "titre": "ADR 0002"},
        {"niveau": "h3", "id": None, "titre": "Contexte"},
        {"niveau": "h2", "id": None, "titre": "Résumé"},
        {"niveau": "h2", "id": None, "titre": "Résumé"},
    ]
    generateur.attribuer_ancres(sections, {"adr-0001", "adr-0002"})
    assert [s["id"] for s in sections] == [
        "adr-0001",
        "adr-0001-contexte",
        "adr-0002",
        "adr-0002-contexte",
        "resume",
        "resume-2",
    ]


def test_ancres_uniques_par_page() -> None:
    index = generateur.construire_index()
    cles = [(e["page"], e["ancre"]) for e in index]
    assert len(cles) == len(set(cles))


def test_nom_de_page_lu_dans_la_navigation() -> None:
    assert generateur.NOMS_DE_PAGE["modele.html"] == "Modèle"
    assert len(generateur.NOMS_DE_PAGE) == len(list(generateur.DOSSIER_DOCS.glob("*.html")))
