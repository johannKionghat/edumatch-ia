"""Vocabulaire et primitives communs aux deux volets du connecteur référentiels (IDÉO, RNCP).

Séparé de `referentiels.py`, mais pas pour une question de longueur : les deux
fichiers fusionnés ne totaliseraient que 351 lignes, largement sous la limite
de 500 du projet. La vraie raison est une dépendance circulaire.

`referentiels.py` importe `_referentiels_rncp` (pour orchestrer IDÉO puis RNCP
dans `telecharger_tous`), et cet import est groupé avec les autres en tête de
fichier, comme l'exige la convention du projet (stdlib, tiers, local). Or
`_referentiels_rncp` a lui-même besoin du vocabulaire commun défini ici
(classes d'erreur, `chemin_manifeste`, `verifier_encodage`...). Si ce
vocabulaire vivait dans `referentiels.py`, `_referentiels_rncp` devrait
l'importer depuis `referentiels` — module qui l'importe déjà en tête de
fichier, avant que ce vocabulaire n'y soit défini : au moment où Python exécute
`from edumatch.ingestion import _referentiels_rncp`, le module `referentiels`
n'est encore que partiellement initialisé, et l'import échoue avec
`ImportError: cannot import name ... from partially initialized module`.

Ce module tiers rompt le cycle : IDÉO (`referentiels.py`) et RNCP
(`_referentiels_rncp.py`) l'importent tous deux, mais aucun des deux n'a besoin
d'importer l'autre pour accéder au vocabulaire partagé. Contrairement à
`_flux.py`, ce module connaît le nom du connecteur qui l'utilise : il n'est pas
destiné à être partagé avec Parcoursup ou Sirene, seulement à séparer les deux
volets d'un même connecteur pour casser leur cycle mutuel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from edumatch.config import Settings
from edumatch.ingestion._flux import ErreurDefinitive, ErreurTransitoire


class ErreurTelechargementReferentiels(RuntimeError):
    """Le téléchargement ou la résolution d'un référentiel a échoué.

    Base commune, dans le même esprit que `ErreurTelechargementParcoursup` et
    `ErreurTelechargementSirene` : un appelant qui ne distingue pas encore
    les deux natures d'échec peut capturer cette seule classe. Un appelant
    qui doit décider entre retenter et alerter capture plutôt l'une des sous-
    classes ci-dessous, ou le vocabulaire commun `ErreurTransitoire` /
    `ErreurDefinitive` de `_flux.py`.
    """


class ErreurReseauReferentiels(ErreurTelechargementReferentiels, ErreurTransitoire):
    """Une source ou le catalogue RNCP était injoignable : échec transitoire, à retenter."""


class ErreurCatalogueReferentiels(ErreurTelechargementReferentiels, ErreurDefinitive):
    """Le catalogue RNCP ne respecte plus le contrat attendu, ou aucun export n'a été trouvé.

    Définitif : retenter reproduirait le même échec, seule une intervention
    humaine (configuration, ou constat que la publication du jour n'a pas
    encore eu lieu) peut le résoudre.
    """


class ErreurConfigurationReferentiels(ErreurTelechargementReferentiels, ErreurDefinitive):
    """Le jeu IDÉO demandé n'est pas déclaré dans la configuration : définitif, à ne pas retenter."""


class ErreurContratReferentiels(ErreurTelechargementReferentiels, ErreurDefinitive):
    """Le fichier téléchargé ne respecte pas le contrat déclaré (ici : l'encodage).

    Un fichier qui ne décode pas selon `encodage` n'est pas un incident
    réseau : la source a changé de contrat (voir le cas réel documenté dans
    `verifier_encodage`), et retélécharger ne change rien tant que la
    configuration n'a pas été mise à jour pour refléter le nouveau contrat.
    """


@dataclass(frozen=True)
class ResultatTelechargementReferentiel:
    """Trace d'un téléchargement de référentiel, IDÉO ou RNCP, qu'il ait eu lieu ou ait été évité."""

    source: str  # "ideo" ou "rncp"
    jeu: str  # nom du jeu IDÉO, ou "rncp" pour le seul jeu RNCP
    url: str
    chemin: Path
    telecharge: bool
    taille_octets: int
    empreinte_sha256: str
    encodage: str
    delimiteur: str
    licence: str
    date_publication: str | None  # uniquement renseigné pour RNCP


def dossier_referentiels(settings: Settings) -> Path:
    return settings.external_dir / "referentiels"


def chemin_manifeste(settings: Settings) -> Path:
    return dossier_referentiels(settings) / "manifeste.json"


def valider_forme_catalogue(catalogue: object, url_catalogue: str, nom_source: str) -> list[dict]:
    """Valide la forme d'une réponse de catalogue data.gouv : partagée par RNCP et France Travail.

    Les deux connecteurs interrogent la même API (`/api/1/datasets/<id>/`) et
    attendent la même forme (`{"resources": [...]}`) : factoriser ce contrôle
    évite qu'un champ absent soit toléré différemment selon la source. Rien
    n'est déduit d'un champ manquant ou mal typé, l'appelant reçoit une
    erreur explicite plutôt qu'une liste vide silencieuse.
    """
    if not isinstance(catalogue, dict):
        raise ErreurCatalogueReferentiels(
            f"Réponse du catalogue {nom_source} ({url_catalogue}) mal formée : un objet JSON "
            f"était attendu à la racine, reçu {type(catalogue).__name__}."
        )
    ressources = catalogue.get("resources")
    if ressources is None:
        ressources = []
    if not isinstance(ressources, list):
        raise ErreurCatalogueReferentiels(
            f"Réponse du catalogue {nom_source} ({url_catalogue}) mal formée : le champ "
            f"'resources' doit être une liste, reçu {type(ressources).__name__}."
        )
    for index, ressource in enumerate(ressources):
        if not isinstance(ressource, dict):
            raise ErreurCatalogueReferentiels(
                f"Réponse du catalogue {nom_source} ({url_catalogue}) mal formée : la ressource "
                f"à l'index {index} doit être un objet JSON, reçu {type(ressource).__name__}."
            )
    return ressources


def verifier_encodage(chemin: Path, encodage: str, contexte: str) -> None:
    """Vérifie que le fichier écrit décode intégralement selon l'encodage déclaré.

    Un contrat de données ne se suppose pas, il se vérifie à l'ingestion :
    l'attribution d'un encodage à une source est une affirmation vérifiable,
    pas une convention prise pour acquise. Le cas réel qui justifie ce
    contrôle : le RNCP a la réputation de publier son export en Latin-1 ;
    l'export vérifié pour ce connecteur décode pourtant intégralement en
    UTF-8, sans aucune erreur — la source a pu changer de contrat sans le
    signaler autrement que par son contenu.

    Garantie réelle, asymétrique — à ne pas surestimer :

    - un fichier réellement encodé en Latin-1 mais déclaré ``utf-8`` est
      détecté : UTF-8 rejette certaines suites d'octets, `decode` lève alors
      `UnicodeDecodeError`.
    - un fichier réellement encodé en UTF-8 mais déclaré à tort ``latin-1``
      n'est **pas** détecté : Latin-1 associe un caractère à chacun des 256
      octets possibles, il ne peut par construction jamais faire échouer un
      `decode`. Le fichier est relu tel quel (mojibake, par exemple
      ``comptabilitÃ©`` au lieu de ``comptabilité``) sans qu'aucune erreur ne
      soit levée. Voir `test_verifier_encodage_ne_detecte_pas_un_fichier_utf8_declare_a_tort_en_latin1`,
      qui met cette limite en évidence.

    Autrement dit : ce contrôle protège contre un encodage déclaré trop
    permissif par rapport au contenu réel (UTF-8 déclaré sur du Latin-1), pas
    contre un encodage déclaré trop restrictif par rapport à un contrat
    réellement permissif (Latin-1 déclaré sur de l'UTF-8). Aucune des deux
    sources configurées aujourd'hui ne déclare ``latin-1`` : le risque n'est
    pas actif, mais il existerait dès qu'une configuration le ferait.
    """
    contenu = chemin.read_bytes()
    try:
        contenu.decode(encodage)
    except (UnicodeDecodeError, LookupError) as erreur:
        raise ErreurContratReferentiels(
            f"{contexte} : le fichier téléchargé ({chemin}) ne décode pas selon "
            f"l'encodage déclaré {encodage!r} ({erreur}). La source a changé de "
            "contrat : mettre à jour la configuration avant de retélécharger, "
            "pas retenter tel quel."
        ) from erreur
