"""RNCP/RS — résolution de l'export quotidien et téléchargement de l'archive.

Sirene republie un stock complet chaque mois ; son connecteur écrase alors le
même nom de fichier, la date de publication n'étant conservée que dans le
manifeste. Appliquer telle quelle cette mécanique à un export qui change
chaque **jour** poserait un problème différent : une table construite en
aval à partir d'un export RNCP donné doit rester rejouable sans reprocher la
source — c'est la raison d'être de la couche bronze (immuabilité, rejeu sans
retéléchargement). Si le fichier RNCP est écrasé à chaque nouvelle
publication, l'export qui a servi à une exécution passée n'existe plus le
lendemain.

Ce module conserve donc un fichier par date de publication
(`rncp_AAAA-MM-JJ.csv`), avec une entrée de manifeste par date. Le contrôle
d'idempotence porte alors sur le grain réel de republication de la source :
une réexécution le même jour ne retélécharge rien (la ressource résolue
porte la même date), une réexécution un autre jour crée un nouveau fichier
sans toucher aux précédents — même logique que Sirene (dater le stock plutôt
que se fier au seul contenu), appliquée à une cadence quotidienne plutôt que
mensuelle.

Assumé et non couvert ici : l'accumulation dans le temps (~9 Mo par jour)
suppose une purge ou un archivage périodique si cette tâche est un jour
programmée à cadence quotidienne dans un DAG, sur une longue durée — hors du
périmètre de cette étape, qui porte l'ingestion, pas la rétention.
"""

from __future__ import annotations

import fnmatch
import io
import logging
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from edumatch.config import Settings
from edumatch.ingestion._flux import (
    DELAI_ATTENTE_SECONDES_DEFAUT,
    ecrire_manifeste,
    ecriture_atomique,
    empreinte_sha256,
    fichier_intact,
    lire_manifeste,
    session_http,
)
from edumatch.ingestion._referentiels_communs import (
    ErreurCatalogueReferentiels,
    ErreurReseauReferentiels,
    ResultatTelechargementReferentiel,
    chemin_manifeste,
    dossier_referentiels,
    valider_forme_catalogue,
    verifier_encodage,
)

LOGGER = logging.getLogger(__name__)

# AAAA-MM-JJ (ISO 8601) : format renvoyé par 'last_modified' de l'API
# data.gouv. On n'accepte que ce préfixe, jamais une chaîne arbitraire,
# puisqu'il finit dans un nom de fichier sur disque.
MOTIF_DATE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class RessourceRncp:
    """Une ressource RNCP résolue depuis le catalogue data.gouv."""

    url: str
    date_publication: str  # ISO 8601 complet, tel que rendu par le catalogue
    date_publication_jour: str  # AAAA-MM-JJ, dérivée de date_publication


def _url_catalogue(settings: Settings) -> str:
    config = settings.donnees.referentiels.rncp
    return config.url_catalogue_gabarit.format(jeu_de_donnees=config.jeu_de_donnees)


def _ressources_du_catalogue(catalogue: object, url_catalogue: str) -> list[dict]:
    """Valide la forme de la réponse du catalogue — voir `valider_forme_catalogue`, partagée avec France Travail."""
    return valider_forme_catalogue(catalogue, url_catalogue, "RNCP")


def resoudre_ressource(settings: Settings, session: requests.Session | None = None) -> RessourceRncp:
    """Interroge le catalogue data.gouv et résout l'archive de l'export RNCP le plus récent.

    Sélectionne, parmi les ressources dont le titre commence par
    `prefixe_ressource` et dont le format est `format_ressource`, celle dont
    `last_modified` est le plus récent — la même logique que
    `scripts/verifier_sources.sh` pour cette source, ici rendue testable.

    Raises:
        ErreurReseauReferentiels: catalogue injoignable — transitoire.
        ErreurCatalogueReferentiels: catalogue mal formé, aucune ressource
            d'export trouvée, ou date de publication non exploitable.
    """
    config = settings.donnees.referentiels.rncp
    url_catalogue = _url_catalogue(settings)

    with session_http(session) as session_active:
        try:
            reponse = session_active.get(url_catalogue, timeout=DELAI_ATTENTE_SECONDES_DEFAUT)
            reponse.raise_for_status()
        except requests.RequestException as erreur:
            raise ErreurReseauReferentiels(f"Catalogue RNCP injoignable ({url_catalogue}) : {erreur}.") from erreur
        catalogue = reponse.json()

    ressources = _ressources_du_catalogue(catalogue, url_catalogue)
    candidates = [
        r
        for r in ressources
        if (r.get("title") or "").startswith(config.prefixe_ressource) and r.get("format") == config.format_ressource
    ]
    if not candidates:
        raise ErreurCatalogueReferentiels(
            f"Aucune ressource dont le titre commence par {config.prefixe_ressource!r} "
            f"(format {config.format_ressource!r}) trouvée dans le catalogue ({url_catalogue}) : "
            "l'export du jour n'est peut-être pas encore publié, ou le catalogue a changé de convention."
        )
    candidates.sort(key=lambda r: r.get("last_modified") or "", reverse=True)
    plus_recente = candidates[0]

    url = plus_recente.get("url")
    if not url:
        raise ErreurCatalogueReferentiels(
            f"Ressource RNCP la plus récente du catalogue ({url_catalogue}) mal formée : "
            f"champ 'url' absent ou vide (reçu {url!r})."
        )
    date_publication = plus_recente.get("last_modified")
    if not date_publication or not isinstance(date_publication, str) or not MOTIF_DATE_ISO.match(date_publication):
        raise ErreurCatalogueReferentiels(
            f"Ressource RNCP la plus récente du catalogue ({url_catalogue}) mal formée : "
            f"champ 'last_modified' absent ou non exploitable (reçu {date_publication!r}). Sans "
            "lui, l'export ne peut pas être daté, donc pas conservé comme un instantané distinct."
        )
    return RessourceRncp(url=url, date_publication=date_publication, date_publication_jour=date_publication[:10])


def chemin_destination(settings: Settings, date_publication_jour: str) -> Path:
    return dossier_referentiels(settings) / "rncp" / f"rncp_{date_publication_jour}.csv"


def chemin_destination_rome(settings: Settings, date_publication_jour: str) -> Path:
    """Fichier de correspondance fiche RNCP -> codes ROME, membre distinct de la même archive.

    Utilisé par la réconciliation NAF/ROME pour relier une certification (code RNCP) à un ou
    plusieurs métiers ROME. Une ligne par couple (fiche, code ROME) : une
    fiche RNCP peut couvrir plusieurs métiers.
    """
    return dossier_referentiels(settings) / "rncp" / f"rncp_rome_{date_publication_jour}.csv"


def _extraire_csv_standard(contenu_zip: bytes, motif_nom: str, url: str) -> bytes:
    """Extrait, depuis l'archive téléchargée en mémoire, le CSV nommé selon `motif_nom` (glob).

    L'archive pèse environ 9 Mo : la garder en mémoire pour l'extraction est
    raisonnable, bien en-deçà des volumes qui justifieraient un flux (voir le
    seuil documenté pour Sirene). Un membre absent ou ambigu est un
    changement de contrat de la source, pas une exception générique.

    Raises:
        ErreurCatalogueReferentiels: archive illisible (`zipfile.BadZipFile`,
            y compris un CRC de membre invalide constaté à la lecture), ou
            membre CSV absent ou ambigu — définitif, voir la justification
            ci-dessous.

    Pourquoi définitif et pas transitoire (là où une erreur réseau l'est) :
    au moment où cette fonction s'exécute, le corps de la réponse HTTP a déjà
    été reçu intégralement — `telecharger` a appelé `raise_for_status()` puis
    lu `reponse.content` sans qu'aucune `requests.RequestException` ne soit
    levée. Une troncature en transit (coupure réseau, proxy qui coupe le
    flux) est précisément ce que ce chemin détecte déjà, en amont, comme
    erreur réseau transitoire : `ChunkedEncodingError` et consorts sont des
    sous-classes de `requests.RequestException`. Ce qui arrive jusqu'ici est
    donc, par construction, exactement l'ensemble d'octets renvoyé par le
    serveur, complet de bout en bout — un problème de contenu, pas de
    transport. Une archive qui ne s'ouvre pas ou dont un membre a un CRC
    invalide dans ces conditions signale que le serveur a répondu un contenu
    qui n'est plus un ZIP valide (page d'erreur HTML servie avec un statut
    200, changement de format d'export...), pas un incident passager :
    retenter la même requête reproduirait le même résultat. Un téléchargement
    réellement abîmé en transit resterait de toute façon rattrapable au
    passage suivant par le contrôle d'empreinte (`fichier_intact`), puisque
    cette fonction échoue avant tout appel à `ecriture_atomique` : aucun
    fichier partiel ou corrompu n'est jamais écrit sur le disque ici.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(contenu_zip)) as archive:
            candidats = [nom for nom in archive.namelist() if fnmatch.fnmatch(nom, motif_nom)]
            if not candidats:
                raise ErreurCatalogueReferentiels(
                    f"Aucun fichier correspondant à {motif_nom!r} dans l'archive RNCP téléchargée "
                    f"depuis {url} : contenu = {archive.namelist()}."
                )
            if len(candidats) > 1:
                raise ErreurCatalogueReferentiels(
                    f"{len(candidats)} fichiers correspondent à {motif_nom!r} dans l'archive RNCP "
                    f"téléchargée depuis {url} : résolution ambiguë ({candidats})."
                )
            return archive.read(candidats[0])
    except zipfile.BadZipFile as erreur:
        raise ErreurCatalogueReferentiels(
            f"Archive RNCP illisible, téléchargée depuis {url} : ce n'est pas un fichier "
            f"ZIP valide, ou l'un de ses membres est corrompu ({erreur}). Le corps de la "
            "réponse a pourtant été reçu intégralement (aucune erreur réseau) : la source "
            "a changé de contrat, retélécharger à l'identique ne le résoudra pas."
        ) from erreur


def _resultat_depuis_manifeste(
    jeu: str, chemin: Path, entree: dict[str, object], telecharge: bool
) -> ResultatTelechargementReferentiel:
    return ResultatTelechargementReferentiel(
        source="rncp",
        jeu=jeu,
        url=str(entree["url"]),
        chemin=chemin,
        telecharge=telecharge,
        taille_octets=int(entree["taille_octets"]),
        empreinte_sha256=str(entree["empreinte_sha256"]),
        encodage=str(entree["encodage"]),
        delimiteur=str(entree["delimiteur"]),
        licence=str(entree["licence"]),
        date_publication=str(entree["date_publication"]),
    )


def _telecharger_membre(
    ressource: RessourceRncp,
    settings: Settings,
    *,
    jeu: str,
    motif_nom: str,
    chemin_final: Path,
    session: requests.Session | None,
    forcer: bool,
) -> ResultatTelechargementReferentiel:
    """Télécharge l'archive RNCP résolue et en extrait le membre `motif_nom`, ou constate qu'il est déjà présent.

    Factorise ce que le CSV standard (`telecharger`) et le fichier de codes
    ROME par fiche (`telecharger_rome`) partagent : les deux sont des membres
    de la même archive quotidienne, avec la même mécanique d'idempotence par
    date de publication. Seuls le motif du membre recherché, le chemin de
    destination et le préfixe de la clé de manifeste diffèrent d'un appelant
    à l'autre — factoriser évite que le contrat d'idempotence (déjà testé
    pour le CSV standard) diverge silencieusement entre les deux membres.

    Compromis assumé : chaque membre déclenche son propre téléchargement de
    l'archive complète (~9,6 Mo au 30/08/2026) plutôt qu'un seul
    téléchargement partagé entre les deux extractions. L'export n'est
    consommé qu'une fois par jour ; doubler ce volume ne pèse pas assez pour
    justifier de complexifier l'appelant (`referentiels.telecharger_tous`)
    avec un cache d'octets en mémoire entre deux appels indépendants. Le
    seuil qui ferait reconsidérer ce choix : une archive dont la taille
    imposerait un flux plutôt qu'un chargement en mémoire (voir la limite
    documentée dans `_extraire_csv_standard`), ou une fréquence de collecte
    plus élevée qu'une fois par jour.

    Raises:
        ErreurReseauReferentiels: échec réseau ou HTTP — transitoire.
        ErreurCatalogueReferentiels: archive mal formée, membre absent ou
            ambigu — définitif.
        ErreurContratReferentiels: le fichier extrait ne décode pas selon
            l'encodage déclaré — définitif.
    """
    config = settings.donnees.referentiels.rncp
    chemin_manif = chemin_manifeste(settings)

    manifeste = lire_manifeste(chemin_manif)
    cle = f"{jeu}:{ressource.date_publication_jour}"
    entree_existante = manifeste.get(cle)

    if not forcer and fichier_intact(chemin_final, entree_existante):
        LOGGER.info(
            "%s du %s déjà présent et intact (%s) : téléchargement évité.",
            jeu,
            ressource.date_publication_jour,
            chemin_final,
        )
        return _resultat_depuis_manifeste(jeu, chemin_final, entree_existante, telecharge=False)

    LOGGER.info(
        "Téléchargement de l'archive RNCP (%s) du %s depuis %s", jeu, ressource.date_publication_jour, ressource.url
    )
    with session_http(session) as session_active:
        try:
            reponse = session_active.get(ressource.url, timeout=DELAI_ATTENTE_SECONDES_DEFAUT)
            reponse.raise_for_status()
        except requests.RequestException as erreur:
            raise ErreurReseauReferentiels(
                f"Échec du téléchargement de l'archive RNCP depuis {ressource.url} : {erreur}"
            ) from erreur
        contenu_zip = reponse.content

    contenu_csv = _extraire_csv_standard(contenu_zip, motif_nom, ressource.url)
    with ecriture_atomique(chemin_final, mode="wb") as flux:
        flux.write(contenu_csv)

    verifier_encodage(chemin_final, config.encodage, f"RNCP ({jeu}) du {ressource.date_publication_jour}")

    taille_octets = chemin_final.stat().st_size
    empreinte = empreinte_sha256(chemin_final)
    manifeste[cle] = {
        "source": "rncp",
        "url": ressource.url,
        "date_publication": ressource.date_publication,
        "date_publication_jour": ressource.date_publication_jour,
        "date_telechargement": datetime.now(UTC).isoformat(),
        "encodage": config.encodage,
        "delimiteur": config.delimiteur,
        "licence": config.licence,
        "taille_octets": taille_octets,
        "empreinte_sha256": empreinte,
    }
    ecrire_manifeste(chemin_manif, manifeste)

    return _resultat_depuis_manifeste(jeu, chemin_final, manifeste[cle], telecharge=True)


def telecharger(
    ressource: RessourceRncp,
    settings: Settings,
    session: requests.Session | None = None,
    forcer: bool = False,
) -> ResultatTelechargementReferentiel:
    """Télécharge l'archive RNCP résolue, extrait le CSV standard, ou constate qu'il est déjà présent.

    Raises: voir `_telecharger_membre`.
    """
    config = settings.donnees.referentiels.rncp
    return _telecharger_membre(
        ressource,
        settings,
        jeu="rncp",
        motif_nom=config.nom_fichier_gabarit,
        chemin_final=chemin_destination(settings, ressource.date_publication_jour),
        session=session,
        forcer=forcer,
    )


def telecharger_rome(
    ressource: RessourceRncp,
    settings: Settings,
    session: requests.Session | None = None,
    forcer: bool = False,
) -> ResultatTelechargementReferentiel:
    """Télécharge le fichier de correspondance fiche RNCP -> codes ROME, membre de la même archive.

    Maillon central de la réconciliation NAF/ROME : chaque ligne associe un `Numero_Fiche` RNCP à un
    `Codes_Rome_Code` (une fiche peut apparaître sur plusieurs lignes, un
    code ROME par ligne). Sans ce fichier, aucune fiche RNCP ne peut être
    reliée à un métier ROME — le CSV standard n'en porte aucune trace.

    Raises: voir `_telecharger_membre`.
    """
    config = settings.donnees.referentiels.rncp
    return _telecharger_membre(
        ressource,
        settings,
        jeu="rncp_rome",
        motif_nom=config.nom_fichier_rome_gabarit,
        chemin_final=chemin_destination_rome(settings, ressource.date_publication_jour),
        session=session,
        forcer=forcer,
    )
