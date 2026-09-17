"""Corpus documentaire de l'assistant sur les échantillons réels de `data/samples/`.

Comme `tests/data/test_matching_debouches_run.py` : extraits réels,
aucun téléchargement, aucun appel réseau — seulement que la lecture des CSV
IDÉO échantillonnés produit des documents bien formés et cités.
"""

from __future__ import annotations

from pathlib import Path

from edumatch.config import get_settings
from edumatch.rag.corpus import charger_corpus

DOSSIER_IDEO_ECHANTILLON = Path("data/samples/referentiels/ideo")
MANIFESTE_ECHANTILLON = Path("data/samples/manifeste.json")


def test_le_corpus_se_construit_sur_les_echantillons_reels_sans_erreur() -> None:
    settings = get_settings()
    documents = charger_corpus(
        DOSSIER_IDEO_ECHANTILLON,
        settings.donnees.referentiels.ideo.jeux,
        tuple(settings.rag.jeux_indexes),
        MANIFESTE_ECHANTILLON,
    )
    assert documents
    assert {document.jeu for document in documents} <= {"formations", "metiers"}


def test_chaque_document_reel_porte_une_citation_complete() -> None:
    settings = get_settings()
    documents = charger_corpus(
        DOSSIER_IDEO_ECHANTILLON,
        settings.donnees.referentiels.ideo.jeux,
        tuple(settings.rag.jeux_indexes),
        MANIFESTE_ECHANTILLON,
    )
    for document in documents:
        assert document.texte.strip()
        assert document.url.startswith("https://")
        assert document.licence == "ODbL (odc-odbl)"
        # L'échantillon (data/samples/manifeste.json) porte bien une date de collecte pour
        # chaque jeu IDÉO retenu (voir data/samples/manifeste.json, entrées "ideo_*").
        assert document.date_collecte is not None
