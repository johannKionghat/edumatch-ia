"""Assistant documentaire (E32) de bout en bout sur les échantillons réels de `data/samples/`.

Construit le vrai index TF-IDF sur le corpus échantillonné et pose une
question réelle : aucun réseau (mode extractif, `client_generation=None`),
aucun mock — seulement que le critère de validation de l'étape (« cite ses
sources ») se vérifie sur des données réelles, pas seulement sur des
fixtures construites à la main (voir `tests/unit/test_rag_assistant.py`).
"""

from __future__ import annotations

from pathlib import Path

from edumatch.config import get_settings
from edumatch.rag.assistant import AssistantRAG
from edumatch.rag.corpus import charger_corpus
from edumatch.rag.index import construire_index

DOSSIER_IDEO_ECHANTILLON = Path("data/samples/referentiels/ideo")
MANIFESTE_ECHANTILLON = Path("data/samples/manifeste.json")


def _assistant_sur_echantillons() -> AssistantRAG:
    settings = get_settings()
    documents = charger_corpus(
        DOSSIER_IDEO_ECHANTILLON,
        settings.donnees.referentiels.ideo.jeux,
        tuple(settings.rag.jeux_indexes),
        MANIFESTE_ECHANTILLON,
    )
    index = construire_index(documents)
    return AssistantRAG(
        index=index,
        top_k=settings.rag.top_k,
        seuil_similarite_minimale=settings.rag.seuil_similarite_minimale,
        client_generation=None,
    )


def test_une_question_documentaire_produit_une_reponse_citee_ou_l_absence_declaree() -> None:
    """Sur un échantillon de 300 lignes par jeu (`data/samples/README.md`), rien ne garantit
    qu'une formation précise y figure : ce test vérifie le contrat (une réponse cite ses
    sources, ou déclare explicitement ne pas en avoir trouvé), pas un résultat métier précis."""
    assistant = _assistant_sur_echantillons()
    reponse = assistant.repondre("formation en gestion et comptabilité")

    assert reponse.mode == "extractif"
    if reponse.citations:
        for citation in reponse.citations:
            assert citation.url.startswith("https://")
            assert citation.extrait in reponse.reponse
    else:
        assert "n'ai trouvé" in reponse.reponse


def test_une_question_sans_aucun_mot_du_corpus_ne_produit_aucune_citation_fabriquee() -> None:
    """Aucun mot réel du français courant ici : "formation" ou "métier" seuls suffiraient à
    recouvrir une partie du corpus (ces mots figurent dans de nombreux libellés IDÉO), ce
    n'est donc pas ce que ce test vérifie — seulement qu'un texte sans aucun recouvrement
    lexical avec le corpus ne fabrique aucune source."""
    assistant = _assistant_sur_echantillons()
    reponse = assistant.repondre("zzzblibliblou9999 xkcdqwerty1234")
    assert reponse.citations == ()
