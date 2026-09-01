"""Tests de l'index de similarité lexicale (src/edumatch/rag/index.py).

Documents construits à la main, sans passer par `corpus.py` : ce module ne
teste que la mécanique de recherche (score, tri, seuil implicite de score
nul), pas la lecture des CSV IDÉO.
"""

from __future__ import annotations

import pytest

from edumatch.rag.corpus import Document
from edumatch.rag.index import ErreurIndexRag, construire_index, rechercher

DOCUMENT_COMPTABILITE = Document(
    identifiant="ideo:formations:0",
    jeu="formations",
    texte="BTS comptabilité et gestion — gestion des entreprises, comptabilité",
    url="https://exemple.test/1",
    licence="ODbL (odc-odbl)",
    date_collecte=None,
)
DOCUMENT_INFORMATIQUE = Document(
    identifiant="ideo:formations:1",
    jeu="formations",
    texte="BTS services informatiques aux organisations — informatique, réseaux",
    url="https://exemple.test/2",
    licence="ODbL (odc-odbl)",
    date_collecte=None,
)
DOCUMENT_CUISINE = Document(
    identifiant="ideo:formations:2",
    jeu="formations",
    texte="CAP cuisine — hôtellerie restauration",
    url="https://exemple.test/3",
    licence="ODbL (odc-odbl)",
    date_collecte=None,
)


def test_construire_index_leve_erreur_sur_corpus_vide() -> None:
    with pytest.raises(ErreurIndexRag, match="vide"):
        construire_index([])


def test_rechercher_retourne_le_document_le_plus_proche_en_tete() -> None:
    index = construire_index([DOCUMENT_COMPTABILITE, DOCUMENT_INFORMATIQUE, DOCUMENT_CUISINE])
    resultats = rechercher(index, "formation en comptabilité", top_k=3)
    assert resultats[0].document.identifiant == DOCUMENT_COMPTABILITE.identifiant


def test_rechercher_respecte_top_k() -> None:
    index = construire_index([DOCUMENT_COMPTABILITE, DOCUMENT_INFORMATIQUE, DOCUMENT_CUISINE])
    resultats = rechercher(index, "formation", top_k=1)
    assert len(resultats) <= 1


def test_rechercher_ignore_les_accents_dans_la_question() -> None:
    """`strip_accents="unicode"` : "comptabilite" sans accent doit retrouver le passage accentué."""
    index = construire_index([DOCUMENT_COMPTABILITE, DOCUMENT_INFORMATIQUE, DOCUMENT_CUISINE])
    resultats = rechercher(index, "comptabilite", top_k=3)
    assert resultats
    assert resultats[0].document.identifiant == DOCUMENT_COMPTABILITE.identifiant


def test_rechercher_sans_recouvrement_lexical_ne_retourne_rien() -> None:
    """Un score nul (aucun terme en commun) n'est jamais un résultat — voir le docstring."""
    index = construire_index([DOCUMENT_COMPTABILITE, DOCUMENT_INFORMATIQUE])
    resultats = rechercher(index, "xyzabc123 inconnu du corpus", top_k=3)
    assert resultats == []


def test_rechercher_question_vide_ne_retourne_rien() -> None:
    index = construire_index([DOCUMENT_COMPTABILITE])
    assert rechercher(index, "", top_k=3) == []
    assert rechercher(index, "   ", top_k=3) == []


def test_scores_tries_par_ordre_decroissant() -> None:
    index = construire_index([DOCUMENT_COMPTABILITE, DOCUMENT_INFORMATIQUE, DOCUMENT_CUISINE])
    resultats = rechercher(index, "comptabilité gestion entreprise", top_k=3)
    scores = [resultat.score for resultat in resultats]
    assert scores == sorted(scores, reverse=True)
