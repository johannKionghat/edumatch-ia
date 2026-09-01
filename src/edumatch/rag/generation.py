"""Génération optionnelle par un modèle de langage externe (E32).

Le mode extractif (`assistant._reponse_extractive`) ne dépend d'aucun secret
et fonctionne toujours. Ce module ajoute, seulement si `MISTRAL_API_KEY` est
renseignée, une reformulation suivie des mêmes passages — jamais une source
d'information supplémentaire : l'instruction système interdit explicitement
au modèle d'ajouter quoi que ce soit qui ne figure pas dans les extraits
fournis, et les citations retournées à l'appelant proviennent toujours de la
recherche (`index.rechercher`), jamais de ce que le modèle affirme avoir dit.

Sans la clé, `client_generation_depuis_settings` retourne `None` : c'est la
dégradation explicite attendue, pas un plantage au démarrage du service ni un
silence qui ferait croire à une génération qui n'a pas eu lieu.
"""

from __future__ import annotations

import logging
from typing import Protocol

from edumatch.config import Settings

LOGGER = logging.getLogger(__name__)

INSTRUCTION_SYSTEME = (
    "Tu es l'assistant documentaire d'EduMatch-IA. Réponds UNIQUEMENT à partir des extraits "
    "numérotés ci-dessous, tous issus du référentiel ONISEP (IDÉO). N'invente aucune formation, "
    "aucun métier, aucun chiffre, aucune URL, aucun débouché qui n'y figure pas explicitement. "
    "Si les extraits ne permettent pas de répondre à la question, dis-le clairement plutôt que "
    "de compléter par une connaissance générale."
)


class ErreurGeneration(RuntimeError):
    """Le service de génération ne peut pas répondre.

    Ne masque jamais l'échec par une réponse inventée : l'appelant
    (`assistant.AssistantRAG.repondre`) capture cette exception pour replier
    explicitement sur le mode extractif, avec le motif de la panne porté par
    la réponse.
    """


class ClientGeneration(Protocol):
    """Ce que l'assistant attend d'un générateur de texte, quel qu'il soit — permet de tester
    `assistant.py` sans dépendre de `mistralai` ni du réseau."""

    def generer(self, question: str, passages: list[str]) -> str: ...


class ClientGenerationMistral:
    """Appelle l'API Mistral. Construit uniquement quand une clé est présente
    (voir `client_generation_depuis_settings`)."""

    def __init__(self, cle_api: str, modele: str) -> None:
        self._cle_api = cle_api
        self._modele = modele

    def generer(self, question: str, passages: list[str]) -> str:
        # Importé ici, pas en tête de module : `mistralai` n'appartient qu'à l'extra optionnel
        # `pip install -e ".[rag]"`. Un déploiement qui ne configure jamais MISTRAL_API_KEY
        # (et reste donc toujours en mode extractif) ne doit pas avoir besoin de ce paquet.
        try:
            from mistralai import Mistral
        except ImportError as erreur:
            raise ErreurGeneration(
                "MISTRAL_API_KEY est renseignée mais le paquet 'mistralai' n'est pas installé : "
                'lancer `pip install -e ".[rag]"`, ou retirer la clé pour rester en mode extractif.'
            ) from erreur

        contexte = "\n\n".join(f"Extrait {indice + 1} : {passage}" for indice, passage in enumerate(passages))
        message = f"{INSTRUCTION_SYSTEME}\n\n{contexte}\n\nQuestion : {question}"
        try:
            client = Mistral(api_key=self._cle_api)
            reponse = client.chat.complete(
                model=self._modele,
                messages=[{"role": "user", "content": message}],
                temperature=0.0,
                max_tokens=600,
            )
        except Exception as erreur:  # l'appel réseau peut échouer de multiples façons (SDK tiers,
            # sans hiérarchie d'exceptions stable) : toutes sont ici une génération indisponible,
            # jamais une raison de renvoyer une réponse inventée.
            raise ErreurGeneration(f"Appel au modèle de génération {self._modele!r} échoué : {erreur}") from erreur
        return reponse.choices[0].message.content


def client_generation_depuis_settings(settings: Settings) -> ClientGeneration | None:
    """`None` si aucune clé n'est configurée : voir le docstring du module pour ce que
    l'absence de clé signifie pour l'appelant."""
    if settings.mistral_api_key is None:
        return None
    return ClientGenerationMistral(settings.mistral_api_key.get_secret_value(), settings.rag.modele_generation)
