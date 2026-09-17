"""Corpus documentaire de l'assistant : les formations et métiers IDÉO, chacun
associé à sa citation vérifiable — jeu, licence, URL, date de collecte.

Deux jeux IDÉO sont indexables aujourd'hui (`COLONNES_TEXTE`) : `formations`
et `metiers`. Un jeu absent de ce dictionnaire n'est pas indexable par ce
module, même s'il est présent dans `donnees.referentiels.ideo.jeux` —
`structures_secondaire` et `structures_superieur` (adresses d'établissements)
ne répondent à aucune question documentaire sur les formations, ils sont
donc délibérément exclus.

## Pourquoi une citation par ligne, pas un fichier

IDÉO est sous licence ODbL, qui impose une attribution portant le
producteur *et* la date de la donnée réutilisée (voir
`docs/sous-docs-projets/05-gouvernance/registre-sources.md`). Un document de
ce corpus est donc une ligne du CSV source, jamais un extrait de plusieurs
lignes fusionnées : la citation reste alignée avec l'URL Onisep qui identifie
cette formation ou ce métier précis, pas avec le fichier entier.
"""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from edumatch.config import IdeoJeuConfig, Settings, get_settings
from edumatch.ingestion._referentiels_communs import dossier_referentiels

LOGGER = logging.getLogger(__name__)

# Colonnes retenues par jeu IDÉO pour construire le texte indexé, dans l'ordre
# où elles apparaissent dans le passage restitué à l'utilisateur.
COLONNES_TEXTE: dict[str, tuple[str, ...]] = {
    "formations": (
        "libellé formation principal",
        "libellé type formation",
        "durée",
        "niveau de sortie indicatif",
        "libellé niveau de certification",
        "domaine/sous-domaine",
        "tutelle",
    ),
    "metiers": (
        "libellé métier",
        "GFE",
        "libellé ROME",
        "domaine/sous-domaine",
    ),
}

# Colonne portant l'URL Onisep propre à chaque ligne, quand elle existe : plus précise que
# l'URL de téléchargement du jeu entier (`IdeoJeuConfig.url`), qui sert de repli.
COLONNE_URL_LIGNE: dict[str, str] = {
    "formations": "URL et ID Onisep",
    "metiers": "lien site onisep.fr",
}

JEUX_INDEXABLES: tuple[str, ...] = tuple(COLONNES_TEXTE)


class ErreurCorpusRag(RuntimeError):
    """Le corpus documentaire ne peut pas être construit : jeu inconnu, colonne absente,
    fichier introuvable."""


@dataclass(frozen=True)
class Document:
    """Une ligne indexable du corpus, avec tout ce qu'il faut pour citer sa provenance."""

    identifiant: str
    jeu: str
    texte: str
    url: str
    licence: str
    date_collecte: str | None


def _lire_csv_ideo(chemin: Path, delimiteur: str) -> pl.DataFrame:
    """Lit un CSV IDÉO avec BOM UTF-8, non typé (`infer_schema_length=0`).

    Même contrat que `referentiel.naf_rome_formation._lire_csv_utf8_sig`,
    dupliqué ici à dessein : les deux modules servent des besoins distincts
    (réconciliation NAF/ROME contre corpus documentaire) et n'ont pas de
    raison de dépendre l'un de l'autre pour cinq lignes de lecture de
    fichier.
    """
    if not chemin.exists():
        raise ErreurCorpusRag(
            f"Fichier IDÉO introuvable : {chemin}. Lancer "
            "`python -m edumatch.ingestion.referentiels` (ou `make samples` en développement) "
            "avant de construire le corpus de l'assistant."
        )
    texte = chemin.read_text(encoding="utf-8-sig")
    return pl.read_csv(io.StringIO(texte), separator=delimiteur, infer_schema_length=0)


def _date_collecte_depuis_manifeste(chemin_manifeste: Path, jeu: str) -> str | None:
    """Cherche la date de collecte du jeu IDÉO donné dans l'un des deux formats de manifeste
    du dépôt.

    - `data/external/referentiels/manifeste.json` : dictionnaire, clé
      ``ideo:{jeu}``, champ ``date_telechargement``.
    - `data/samples/manifeste.json` : liste ``echantillons``, entrée dont le
      champ ``source`` vaut ``ideo_{jeu}``, champ ``date_source``.

    Retourne `None` si le manifeste est absent ou ne porte pas ce jeu :
    l'absence est déclarée sur `Document.date_collecte`, jamais masquée par
    une date inventée.
    """
    if not chemin_manifeste.exists():
        return None
    contenu = json.loads(chemin_manifeste.read_text(encoding="utf-8"))
    if isinstance(contenu, dict) and isinstance(contenu.get("echantillons"), list):
        for entree in contenu["echantillons"]:
            if entree.get("source") == f"ideo_{jeu}":
                return entree.get("date_source")
        return None
    if isinstance(contenu, dict):
        entree = contenu.get(f"ideo:{jeu}")
        if isinstance(entree, dict):
            return entree.get("date_telechargement")
    return None


def _construire_documents(
    brut: pl.DataFrame, jeu: str, url_defaut: str, licence: str, date_collecte: str | None
) -> list[Document]:
    colonnes = COLONNES_TEXTE.get(jeu)
    if colonnes is None:
        raise ErreurCorpusRag(
            f"Jeu IDÉO {jeu!r} non indexable par l'assistant : aucune colonne de texte déclarée "
            f"dans corpus.COLONNES_TEXTE (jeux indexables : {JEUX_INDEXABLES})."
        )
    manquantes = set(colonnes) - set(brut.columns)
    if manquantes:
        raise ErreurCorpusRag(
            f"Colonnes attendues absentes du jeu IDÉO {jeu!r} : {sorted(manquantes)}. "
            f"Colonnes présentes : {brut.columns}. Le référentiel a changé de contrat."
        )
    colonne_url = COLONNE_URL_LIGNE.get(jeu)

    documents: list[Document] = []
    for indice, ligne in enumerate(brut.iter_rows(named=True)):
        fragments = [str(ligne[colonne]).strip() for colonne in colonnes if ligne.get(colonne) not in (None, "")]
        if not fragments:
            continue  # ligne sans aucun champ textuel exploitable : rien à indexer ni à citer
        url_ligne = ligne.get(colonne_url) if colonne_url else None
        documents.append(
            Document(
                identifiant=f"ideo:{jeu}:{indice}",
                jeu=jeu,
                texte=" — ".join(fragments),
                url=(url_ligne or url_defaut),
                licence=licence,
                date_collecte=date_collecte,
            )
        )
    return documents


def charger_corpus(
    dossier_ideo: Path,
    jeux: dict[str, IdeoJeuConfig],
    jeux_indexes: tuple[str, ...],
    chemin_manifeste: Path | None = None,
) -> list[Document]:
    """Construit le corpus à partir d'un dossier IDÉO donné — réel (`data/external/...`) ou
    échantillon (`data/samples/...`), le contrat de colonnes est identique dans les deux cas."""
    documents: list[Document] = []
    for jeu in jeux_indexes:
        config_jeu = jeux.get(jeu)
        if config_jeu is None:
            raise ErreurCorpusRag(
                f"Jeu IDÉO {jeu!r} demandé dans rag.jeux_indexes mais absent de "
                "donnees.referentiels.ideo.jeux : configuration incohérente."
            )
        brut = _lire_csv_ideo(dossier_ideo / f"{jeu}.csv", config_jeu.delimiteur)
        date_collecte = _date_collecte_depuis_manifeste(chemin_manifeste, jeu) if chemin_manifeste else None
        documents.extend(_construire_documents(brut, jeu, config_jeu.url, config_jeu.licence, date_collecte))

    LOGGER.info("Corpus RAG construit : %d document(s) sur %d jeu(x) IDÉO (%s).", len(documents), len(jeux_indexes), jeux_indexes)
    return documents


def charger_corpus_depuis_settings(settings: Settings | None = None) -> list[Document]:
    """Point d'entrée réel : lit les référentiels IDÉO déjà téléchargés sous `external_dir`."""
    settings = settings or get_settings()
    dossier = dossier_referentiels(settings) / "ideo"
    chemin_manifeste = dossier_referentiels(settings) / "manifeste.json"
    return charger_corpus(
        dossier,
        settings.donnees.referentiels.ideo.jeux,
        tuple(settings.rag.jeux_indexes),
        chemin_manifeste,
    )
