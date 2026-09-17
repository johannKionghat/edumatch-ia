"""Assistant documentaire : orchestre recherche et génération, jamais l'inverse.

Voir le docstring de `edumatch.rag` pour la portée de cette brique et ce
qu'elle ne fait jamais.

## La garantie que ce module tient

Une réponse ne cite jamais que des documents réellement retrouvés par
`index.rechercher`, au-dessus du seuil configuré
(`rag.seuil_similarite_minimale`). Que le mode soit extractif ou génératif,
la liste de citations retournée à l'appelant vient de la recherche, jamais
d'une affirmation du modèle de langage sur ce qu'il aurait consulté — un
mode génératif ne peut donc pas fabriquer ses propres sources.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from edumatch.config import Settings, get_settings
from edumatch.rag.corpus import Document, charger_corpus_depuis_settings
from edumatch.rag.generation import (
    ClientGeneration,
    ErreurGeneration,
    client_generation_depuis_settings,
)
from edumatch.rag.index import IndexDocumentaire, construire_index, rechercher

LOGGER = logging.getLogger(__name__)

MESSAGE_AUCUNE_SOURCE = (
    "Je n'ai trouvé, dans le référentiel ONISEP indexé, aucun passage suffisamment proche de "
    "cette question pour y répondre sans risquer d'inventer. Reformulez, ou précisez le nom "
    "d'une formation ou d'un métier."
)

_LIBELLES_SOURCE: dict[str, str] = {
    "formations": "ONISEP — IDÉO — référentiel des formations",
    "metiers": "ONISEP — IDÉO — référentiel des métiers",
}


@dataclass(frozen=True)
class Citation:
    """Une source vérifiable : de quel jeu elle vient, sous quelle licence, à quelle URL, et
    depuis quand elle a été collectée — le minimum qu'exige l'attribution Licence Ouverte / ODbL
    (voir `docs/registres.html#sources`)."""

    identifiant: str
    source: str
    licence: str
    url: str
    date_collecte: str | None
    extrait: str


@dataclass(frozen=True)
class ReponseAssistant:
    reponse: str
    mode: str  # "extractif" ou "generatif"
    citations: tuple[Citation, ...]
    avertissement: str | None


def _citation_depuis_document(document: Document) -> Citation:
    return Citation(
        identifiant=document.identifiant,
        source=_LIBELLES_SOURCE.get(document.jeu, f"ONISEP — IDÉO — {document.jeu}"),
        licence=document.licence,
        url=document.url,
        date_collecte=document.date_collecte,
        extrait=document.texte,
    )


def _reponse_extractive(citations: list[Citation]) -> str:
    lignes = [f"[{indice + 1}] {citation.extrait}" for indice, citation in enumerate(citations)]
    return "Voici ce que le référentiel ONISEP (IDÉO) indique :\n\n" + "\n\n".join(lignes)


@dataclass(frozen=True)
class AssistantRAG:
    """État construit une fois (index TF-IDF ajusté sur le corpus), interrogé à chaque question
    par `repondre` — voir `construire_assistant` pour la construction réelle."""

    index: IndexDocumentaire
    top_k: int
    seuil_similarite_minimale: float
    client_generation: ClientGeneration | None

    def repondre(self, question: str) -> ReponseAssistant:
        # Jamais la question elle-même dans le journal : voir le docstring de edumatch.rag sur
        # l'absence de donnée personnelle dans les journaux de cette brique.
        LOGGER.info(
            "Question reçue (%d caractère(s)) : recherche de %d passage(s) au plus.",
            len(question or ""),
            self.top_k,
        )
        resultats = rechercher(self.index, question, self.top_k)
        retenus = [resultat for resultat in resultats if resultat.score >= self.seuil_similarite_minimale]
        if not retenus:
            LOGGER.info(
                "Aucun passage au-dessus du seuil de similarité %.2f (%d résultat(s) brut(s)).",
                self.seuil_similarite_minimale,
                len(resultats),
            )
            return ReponseAssistant(
                reponse=MESSAGE_AUCUNE_SOURCE, mode="extractif", citations=(), avertissement=MESSAGE_AUCUNE_SOURCE
            )

        citations = [_citation_depuis_document(resultat.document) for resultat in retenus]

        if self.client_generation is not None:
            try:
                texte = self.client_generation.generer(question, [citation.extrait for citation in citations])
            except ErreurGeneration as erreur:
                LOGGER.warning("Génération indisponible, repli en mode extractif : %s", erreur)
                return ReponseAssistant(
                    reponse=_reponse_extractive(citations),
                    mode="extractif",
                    citations=tuple(citations),
                    avertissement=f"Génération indisponible ({erreur}) : réponse extractive de repli.",
                )
            return ReponseAssistant(reponse=texte, mode="generatif", citations=tuple(citations), avertissement=None)

        return ReponseAssistant(
            reponse=_reponse_extractive(citations), mode="extractif", citations=tuple(citations), avertissement=None
        )


def construire_assistant(settings: Settings | None = None) -> AssistantRAG:
    """Point d'entrée réel : charge le corpus IDÉO, ajuste l'index, prépare la génération
    optionnelle. Coûteux (lecture de deux CSV, ajustement TF-IDF) mais rapide sur ce volume —
    voir le docstring de `index.py` pour l'ordre de grandeur — appelé une fois par processus,
    comme `api.state.construire_etat_matching`."""
    settings = settings or get_settings()
    documents = charger_corpus_depuis_settings(settings)
    index = construire_index(documents)
    client = client_generation_depuis_settings(settings)
    return AssistantRAG(
        index=index,
        top_k=settings.rag.top_k,
        seuil_similarite_minimale=settings.rag.seuil_similarite_minimale,
        client_generation=client,
    )
