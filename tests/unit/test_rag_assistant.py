"""Tests de l'orchestration de l'assistant (src/edumatch/rag/assistant.py).

Aucun appel réseau : le mode génératif est exercé avec un faux client qui
implémente le protocole `ClientGeneration`, jamais `mistralai` ni le réseau
réel — voir `test_rag_generation.py` pour les tests du client Mistral
lui-même.
"""

from __future__ import annotations

from edumatch.rag.assistant import MESSAGE_AUCUNE_SOURCE, AssistantRAG
from edumatch.rag.corpus import Document
from edumatch.rag.generation import ErreurGeneration
from edumatch.rag.index import construire_index

DOCUMENT_COMPTABILITE = Document(
    identifiant="ideo:formations:0",
    jeu="formations",
    texte="BTS comptabilité et gestion — gestion des entreprises, comptabilité",
    url="https://exemple.test/1",
    licence="ODbL (odc-odbl)",
    date_collecte="2026-08-29T04:10:05+00:00",
)
DOCUMENT_INFORMATIQUE = Document(
    identifiant="ideo:formations:1",
    jeu="metiers",
    texte="développeur informatique — programmation, réseaux",
    url="https://exemple.test/2",
    licence="ODbL (odc-odbl)",
    date_collecte=None,
)


def _assistant(client_generation=None, seuil: float = 0.05, top_k: int = 4) -> AssistantRAG:
    index = construire_index([DOCUMENT_COMPTABILITE, DOCUMENT_INFORMATIQUE])
    return AssistantRAG(index=index, top_k=top_k, seuil_similarite_minimale=seuil, client_generation=client_generation)


# ─── Mode extractif (par défaut, sans secret) ────────────────────────────────


def test_mode_extractif_par_defaut_sans_client_generation() -> None:
    assistant = _assistant(client_generation=None)
    reponse = assistant.repondre("Quelle formation prépare à la comptabilité ?")
    assert reponse.mode == "extractif"
    assert reponse.citations
    assert reponse.avertissement is None


def test_les_citations_portent_toutes_les_informations_de_provenance() -> None:
    assistant = _assistant(client_generation=None)
    reponse = assistant.repondre("Quelle formation prépare à la comptabilité ?")
    citation = reponse.citations[0]
    assert citation.identifiant == DOCUMENT_COMPTABILITE.identifiant
    assert citation.licence == "ODbL (odc-odbl)"
    assert citation.url == DOCUMENT_COMPTABILITE.url
    assert citation.date_collecte == DOCUMENT_COMPTABILITE.date_collecte
    assert citation.extrait == DOCUMENT_COMPTABILITE.texte
    assert "ONISEP" in citation.source


def test_la_reponse_extractive_cite_le_texte_reel_du_document() -> None:
    assistant = _assistant(client_generation=None)
    reponse = assistant.repondre("Quelle formation prépare à la comptabilité ?")
    assert DOCUMENT_COMPTABILITE.texte in reponse.reponse


def test_aucune_source_au_dessus_du_seuil_dit_ne_pas_savoir() -> None:
    """Le verrou anti-invention : une question sans recouvrement lexical avec le corpus ne doit
    jamais produire une réponse inventée."""
    assistant = _assistant(client_generation=None)
    reponse = assistant.repondre("xyzabc123 question totalement hors du corpus indexé")
    assert reponse.mode == "extractif"
    assert reponse.citations == ()
    assert reponse.reponse == MESSAGE_AUCUNE_SOURCE
    assert reponse.avertissement == MESSAGE_AUCUNE_SOURCE


def test_seuil_de_similarite_filtre_les_passages_trop_eloignes() -> None:
    """Un seuil très élevé écarte un passage qui aurait été retenu avec le seuil par défaut."""
    assistant = _assistant(client_generation=None, seuil=0.99)
    reponse = assistant.repondre("Quelle formation prépare à la comptabilité ?")
    assert reponse.citations == ()


# ─── Mode génératif (faux client, aucun réseau) ──────────────────────────────


class _FauxClientGeneration:
    def __init__(self, texte: str | None = None, erreur: Exception | None = None) -> None:
        self._texte = texte
        self._erreur = erreur
        self.appels: list[tuple[str, list[str]]] = []

    def generer(self, question: str, passages: list[str]) -> str:
        self.appels.append((question, passages))
        if self._erreur is not None:
            raise self._erreur
        return self._texte or ""


def test_mode_generatif_utilise_le_client_et_conserve_les_citations_de_la_recherche() -> None:
    faux_client = _FauxClientGeneration(texte="Réponse reformulée à partir des extraits.")
    assistant = _assistant(client_generation=faux_client)
    reponse = assistant.repondre("Quelle formation prépare à la comptabilité ?")
    assert reponse.mode == "generatif"
    assert reponse.reponse == "Réponse reformulée à partir des extraits."
    # Les citations viennent de la recherche, pas du texte généré : le faux client ne les
    # mentionne même pas dans sa réponse, elles sont pourtant bien présentes.
    assert reponse.citations
    assert reponse.citations[0].identifiant == DOCUMENT_COMPTABILITE.identifiant


def test_le_client_recoit_bien_les_passages_retrouves() -> None:
    faux_client = _FauxClientGeneration(texte="peu importe")
    assistant = _assistant(client_generation=faux_client)
    assistant.repondre("Quelle formation prépare à la comptabilité ?")
    (question, passages) = faux_client.appels[0]
    assert question == "Quelle formation prépare à la comptabilité ?"
    assert DOCUMENT_COMPTABILITE.texte in passages


def test_generation_indisponible_replie_sur_le_mode_extractif_sans_plantage() -> None:
    faux_client = _FauxClientGeneration(erreur=ErreurGeneration("panne simulée du modèle"))
    assistant = _assistant(client_generation=faux_client)
    reponse = assistant.repondre("Quelle formation prépare à la comptabilité ?")
    assert reponse.mode == "extractif"
    assert reponse.citations  # les sources restent disponibles même en repli
    assert reponse.avertissement is not None
    assert "panne simulée du modèle" in reponse.avertissement


def test_generation_jamais_appelee_si_aucune_source_ne_depasse_le_seuil() -> None:
    """Ne pas appeler un modèle de langage sur une question sans aucun passage pertinent évite
    de lui laisser la moindre chance d'inventer une réponse hors sources."""
    faux_client = _FauxClientGeneration(texte="ne devrait jamais être retourné")
    assistant = _assistant(client_generation=faux_client)
    reponse = assistant.repondre("xyzabc123 question totalement hors du corpus indexé")
    assert reponse.reponse == MESSAGE_AUCUNE_SOURCE
    assert faux_client.appels == []
