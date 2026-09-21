"""Tests de l'index de similarité lexicale (src/edumatch/rag/index.py).

Documents construits à la main, sans passer par `corpus.py` : ce module ne
teste que la mécanique de recherche (score, tri, seuil implicite de score
nul), pas la lecture des CSV IDÉO.
"""

from __future__ import annotations

import pytest

from edumatch.rag.corpus import Document
from edumatch.rag.index import MOTS_VIDES, ErreurIndexRag, construire_index, rechercher

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
# Reproduit le document réellement retourné par le corpus IDÉO pour une question absurde :
# c'est le « Est » de « Centre Est », pris pour un terme porteur, qui portait la similarité.
DOCUMENT_MARKETING_CENTRE_EST = Document(
    identifiant="ideo:formations:3",
    jeu="formations",
    texte="diplôme supérieur en marketing, commerce et gestion (EGC Centre Est) — commerce, vente",
    url="https://exemple.test/4",
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


# ─── Mots vides : une phrase hors sujet ne doit pas ressembler au corpus ────


def test_les_mots_vides_ne_portent_aucune_similarite() -> None:
    """Non-régression d'un défaut mesuré sur le corpus réel.

    « Quelle est la recette du gâteau au chocolat ? » obtenait 0,223 — au-dessus d'une
    question légitime mais vague (0,218) — parce que le terme « est » comptait comme un
    terme porteur et correspondait au « Est » de « EGC Centre Est ». Aucun seuil ne
    pouvait séparer les deux. Sans cette garde, le refus documenté par `assistant.py` ne
    se déclenche que sur du charabia, jamais sur une phrase française hors sujet.
    """
    index = construire_index(
        [DOCUMENT_COMPTABILITE, DOCUMENT_INFORMATIQUE, DOCUMENT_CUISINE, DOCUMENT_MARKETING_CENTRE_EST]
    )

    resultats = rechercher(index, "Quelle est la recette du gâteau au chocolat ?", 4)

    assert resultats == [], (
        "une question hors sujet ne doit ressembler à aucun passage : sans retrait des mots "
        "vides, « est » la rapproche de « EGC Centre Est »"
    )


def test_une_question_du_domaine_reste_trouvee_malgre_ses_mots_vides() -> None:
    """Retirer les mots vides ne doit pas dégrader les questions légitimes : sur le corpus
    réel, la question pertinente est passée de 0,323 à 0,360."""
    index = construire_index([DOCUMENT_COMPTABILITE, DOCUMENT_INFORMATIQUE, DOCUMENT_CUISINE])

    resultats = rechercher(index, "Quelle est la formation qui mène à la comptabilité ?", 3)

    assert resultats, "une question du domaine doit trouver un passage"
    assert resultats[0].document is DOCUMENT_COMPTABILITE


def test_aucun_mot_vide_n_entre_dans_le_vocabulaire_indexe() -> None:
    """La garde porte sur l'index lui-même, pas seulement sur une question d'exemple."""
    index = construire_index([DOCUMENT_COMPTABILITE, DOCUMENT_CUISINE])

    vocabulaire = set(index.vectoriseur.get_feature_names_out())

    assert not vocabulaire & set(MOTS_VIDES)
    assert "comptabilite" in vocabulaire, "les termes porteurs restent indexés"
