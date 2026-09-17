"""Exemple de bout en bout de l'assistant documentaire, sur données réelles.

`make assistant-exemple` : construit l'assistant depuis
`data/external/referentiels/ideo/` (corpus complet), pose une question
d'exemple, et affiche la réponse ainsi que chacune de ses citations —
demonstration que le critère de validation (« cite ses sources ») se vérifie
en pratique, pas seulement dans le code.

Non couvert par la suite rapide (`make test`) : ce module lit le référentiel
IDÉO complet sous `data/external/`, absent d'un poste qui n'a pas exécuté
`python -m edumatch.ingestion.referentiels`. Les fonctions qu'il assemble
sont, elles, testées séparément et rapidement sur `data/samples/`
(`tests/unit/test_rag_*.py`).
"""

from __future__ import annotations

import logging

from edumatch.config import get_settings
from edumatch.rag.assistant import ReponseAssistant, construire_assistant

LOGGER = logging.getLogger(__name__)

QUESTION_EXEMPLE = "Quelle formation prépare aux métiers de la comptabilité ?"


def _afficher(reponse: ReponseAssistant) -> None:
    LOGGER.info("Mode : %s", reponse.mode)
    LOGGER.info("Réponse : %s", reponse.reponse)
    if reponse.avertissement:
        LOGGER.info("Avertissement : %s", reponse.avertissement)
    for rang, citation in enumerate(reponse.citations, start=1):
        LOGGER.info(
            "  Source #%d : %s — %s — collecté le %s — %s",
            rang,
            citation.source,
            citation.licence,
            citation.date_collecte or "date inconnue",
            citation.url,
        )


def executer(question: str = QUESTION_EXEMPLE) -> ReponseAssistant:
    settings = get_settings()
    LOGGER.info("Construction de l'assistant (corpus IDÉO, index TF-IDF)...")
    assistant = construire_assistant(settings)
    LOGGER.info("Question d'exemple : %s", question)
    reponse = assistant.repondre(question)
    _afficher(reponse)
    return reponse


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    executer()


if __name__ == "__main__":
    main()
