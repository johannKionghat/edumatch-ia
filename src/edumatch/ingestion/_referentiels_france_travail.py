"""France Travail — table de correspondance ROME / NAF (E18).

Recherche menée en E18 : NAF (Sirene) décrit une activité d'établissement,
ROME (France Travail) décrit un métier. Aucune table officielle ne les relie
directement à l'échelle demandée ; la seule trouvée qui relie réellement les
deux univers est celle-ci, publiée par France Travail au sein du jeu de
données ROME sur data.gouv (identifiant déclaré en configuration, voir
`donnees.referentiels.france_travail.jeu_de_donnees`), ressource « Les
tables de correspondance ROME / autres référentiels - ROME/NAF ».

Deux limites, vérifiées et à assumer, pas à masquer :

- La correspondance est au niveau **division NAF** (2 chiffres, ex. « 62 » —
  Programmation, conseil et autres activités informatiques), pas à la
  sous-classe complète (5 caractères, ex. « 62.01Z ») que porte
  `activitePrincipaleEtablissement` dans l'agrégat Sirene (E17). Le
  rattachement exige donc de tronquer le code Sirene à ses deux premiers
  caractères — une perte de granularité déclarée, pas une invention : la
  division est par construction le préfixe de toute sous-classe NAF.
- Le nom du fichier change à chaque révision du ROME (ex. suffixe
  « juin-2026 » constaté le 2026-08-30) : aucune URL de fichier n'est codée
  en dur, la ressource est résolue par sous-chaîne de titre dans le
  catalogue, comme Sirene et RNCP résolvent la leur par identifiant de jeu de
  données.

Contrairement à Sirene (republié chaque mois) et RNCP (chaque jour), cette
ressource n'a pas de cadence de republication connue : l'idempotence se fait
donc par empreinte SHA-256 sur un nom de fichier fixe, comme pour IDÉO, pas
par date de publication.

Le fichier est un classeur Excel (xlsx), seul format publié pour cette table
— pas de CSV alternatif au catalogue. Le contrat vérifié après téléchargement
n'est donc pas un encodage de texte (comme pour IDÉO et RNCP) mais la
validité du conteneur ZIP sous-jacent : un xlsx est un ZIP contenant au
minimum `[Content_Types].xml`.
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from edumatch.config import Settings
from edumatch.ingestion._flux import (
    DELAI_ATTENTE_SECONDES_DEFAUT,
    ecrire_manifeste,
    empreinte_sha256,
    fichier_intact,
    lire_manifeste,
    session_http,
    telecharger_en_flux,
)
from edumatch.ingestion._referentiels_communs import (
    ErreurCatalogueReferentiels,
    ErreurContratReferentiels,
    ErreurReseauReferentiels,
    ResultatTelechargementReferentiel,
    chemin_manifeste,
    dossier_referentiels,
    valider_forme_catalogue,
)

LOGGER = logging.getLogger(__name__)

NOM_JEU = "france_travail_rome_naf"


@dataclass(frozen=True)
class RessourceFranceTravail:
    """Une ressource France Travail résolue depuis le catalogue data.gouv."""

    url: str
    titre: str


def _url_catalogue(settings: Settings) -> str:
    config = settings.donnees.referentiels.france_travail
    return config.url_catalogue_gabarit.format(jeu_de_donnees=config.jeu_de_donnees)


def resoudre_ressource(settings: Settings, session: requests.Session | None = None) -> RessourceFranceTravail:
    """Interroge le catalogue data.gouv et résout la ressource ROME/NAF par sous-chaîne de titre.

    Raises:
        ErreurReseauReferentiels: catalogue injoignable — transitoire.
        ErreurCatalogueReferentiels: catalogue mal formé, aucune ressource ou
            plusieurs ressources correspondent à la sous-chaîne configurée.
    """
    config = settings.donnees.referentiels.france_travail
    url_catalogue = _url_catalogue(settings)

    with session_http(session) as session_active:
        try:
            reponse = session_active.get(url_catalogue, timeout=DELAI_ATTENTE_SECONDES_DEFAUT)
            reponse.raise_for_status()
        except requests.RequestException as erreur:
            raise ErreurReseauReferentiels(
                f"Catalogue France Travail injoignable ({url_catalogue}) : {erreur}."
            ) from erreur
        catalogue = reponse.json()

    ressources = valider_forme_catalogue(catalogue, url_catalogue, "France Travail")
    candidates = [
        r
        for r in ressources
        if config.sous_chaine_titre_ressource in (r.get("title") or "") and r.get("format") == config.format_ressource
    ]
    if not candidates:
        raise ErreurCatalogueReferentiels(
            f"Aucune ressource dont le titre contient {config.sous_chaine_titre_ressource!r} "
            f"(format {config.format_ressource!r}) trouvée dans le catalogue ({url_catalogue}) : "
            "le jeu de données a peut-être changé de convention de titrage."
        )
    if len(candidates) > 1:
        titres = [c.get("title") for c in candidates]
        raise ErreurCatalogueReferentiels(
            f"{len(candidates)} ressources correspondent à {config.sous_chaine_titre_ressource!r} "
            f"dans le catalogue France Travail ({url_catalogue}) : résolution ambiguë ({titres})."
        )
    ressource = candidates[0]
    url = ressource.get("url")
    if not url:
        raise ErreurCatalogueReferentiels(
            f"Ressource France Travail résolue dans le catalogue ({url_catalogue}) mal formée : "
            f"champ 'url' absent ou vide (reçu {url!r})."
        )
    return RessourceFranceTravail(url=url, titre=str(ressource.get("title")))


def chemin_destination(settings: Settings) -> Path:
    return dossier_referentiels(settings) / "france_travail" / "rome_naf.xlsx"


def _verifier_conteneur_zip(chemin: Path, contexte: str) -> None:
    """Vérifie que le fichier téléchargé est un conteneur ZIP valide — le contrat d'un xlsx.

    Équivalent, pour un format binaire, de `verifier_encodage` pour un CSV
    texte : un contrat de données se vérifie après écriture, il ne se
    suppose pas. Un xlsx est un ZIP ; un fichier qui ne s'ouvre pas comme tel
    signale que la source a changé de format (page d'erreur HTML servie avec
    un statut 200, par exemple), pas un incident réseau — voir la même
    distinction, plus détaillée, dans `_referentiels_rncp._extraire_csv_standard`.
    """
    try:
        with zipfile.ZipFile(chemin):
            pass
    except zipfile.BadZipFile as erreur:
        raise ErreurContratReferentiels(
            f"{contexte} : le fichier téléchargé ({chemin}) n'est pas un conteneur ZIP "
            f"valide ({erreur}), alors qu'un xlsx en est un par construction. La source a "
            "changé de format : mettre à jour la configuration avant de retélécharger."
        ) from erreur


def telecharger(
    ressource: RessourceFranceTravail,
    settings: Settings,
    session: requests.Session | None = None,
    forcer: bool = False,
) -> ResultatTelechargementReferentiel:
    """Télécharge la table ROME/NAF résolue, ou constate qu'elle est déjà présente et intacte.

    Raises:
        ErreurReseauReferentiels: échec réseau ou HTTP — transitoire.
        ErreurContratReferentiels: le fichier téléchargé n'est pas un xlsx
            valide — définitif.
    """
    config = settings.donnees.referentiels.france_travail
    chemin_final = chemin_destination(settings)
    chemin_manif = chemin_manifeste(settings)

    manifeste = lire_manifeste(chemin_manif)
    cle = f"{NOM_JEU}:rome_naf"
    entree_existante = manifeste.get(cle)

    if not forcer and fichier_intact(chemin_final, entree_existante):
        LOGGER.info("France Travail ROME/NAF déjà présent et intact (%s) : téléchargement évité.", chemin_final)
        return _resultat_depuis_manifeste(chemin_final, entree_existante, telecharge=False)

    LOGGER.info("Téléchargement de la table France Travail ROME/NAF depuis %s", ressource.url)
    with session_http(session) as session_active:
        try:
            telecharger_en_flux(session_active, ressource.url, chemin_final)
        except requests.RequestException as erreur:
            raise ErreurReseauReferentiels(
                f"Échec du téléchargement de la table France Travail ROME/NAF depuis {ressource.url} : {erreur}"
            ) from erreur

    _verifier_conteneur_zip(chemin_final, "France Travail ROME/NAF")

    taille_octets = chemin_final.stat().st_size
    empreinte = empreinte_sha256(chemin_final)
    manifeste[cle] = {
        "source": "france_travail",
        "url": ressource.url,
        "titre_ressource": ressource.titre,
        "date_telechargement": datetime.now(UTC).isoformat(),
        "licence": config.licence,
        "taille_octets": taille_octets,
        "empreinte_sha256": empreinte,
    }
    ecrire_manifeste(chemin_manif, manifeste)

    return _resultat_depuis_manifeste(chemin_final, manifeste[cle], telecharge=True)


def _resultat_depuis_manifeste(
    chemin: Path, entree: dict[str, object], telecharge: bool
) -> ResultatTelechargementReferentiel:
    return ResultatTelechargementReferentiel(
        source="france_travail",
        jeu=NOM_JEU,
        url=str(entree["url"]),
        chemin=chemin,
        telecharge=telecharge,
        taille_octets=int(entree["taille_octets"]),
        empreinte_sha256=str(entree["empreinte_sha256"]),
        encodage="binaire",  # xlsx : pas d'encodage de texte, voir _verifier_conteneur_zip
        delimiteur="",
        licence=str(entree["licence"]),
        date_publication=None,
    )
