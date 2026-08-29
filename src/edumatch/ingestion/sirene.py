"""Connecteur d'ingestion Sirene — quatre fichiers stock, résolus depuis le catalogue.

Contrairement à Parcoursup, Sirene n'a **pas de gabarit d'URL fixe** : l'INSEE
republie un stock complet chaque mois, sous un lien qui change à chaque
publication. Ce module interroge donc l'API du catalogue data.gouv
(`donnees.sirene.url_catalogue_gabarit`) pour résoudre, au moment de
l'exécution, l'URL Parquet de chacun des quatre fichiers retenus
(`donnees.sirene.fichiers`) — jamais une URL de fichier codée en dur. Cette
résolution est propre à Sirene ; elle ne migre pas vers `_flux.py`, qui ne
porte que les mécaniques indépendantes de la source.

Le manifeste enregistre, pour chaque fichier, la date de publication de la
ressource telle que rendue par le catalogue en plus de l'URL et de
l'empreinte : un stock Sirene grossit chaque mois, un volume sans sa date de
stock n'est pas reproductible.

Les fichiers retenus pèsent chacun plusieurs centaines de Mo, jusqu'à plus de
2 Go pour le plus volumineux en Parquet : le délai d'attente réseau par
défaut de `_flux.py` (120 s) est insuffisant pour un tel volume, et ce module
retient un délai plus long, propre au poids réel de ces fichiers.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import requests

from edumatch.config import Settings, get_settings
from edumatch.ingestion._flux import (
    DELAI_ATTENTE_SECONDES_DEFAUT,
    ErreurDefinitive,
    ErreurTransitoire,
    ecrire_manifeste,
    empreinte_sha256,
    fichier_intact,
    lire_manifeste,
    session_http,
    telecharger_en_flux,
)

LOGGER = logging.getLogger(__name__)

NOM_FICHIER_MANIFESTE = "manifeste.json"

# Format attendu du fichier téléchargé : Parquet uniquement (colonnaire, cf.
# le choix documenté pour l'analytique sur 36 M de lignes). Le ZIP existe
# aussi au catalogue mais n'est jamais retenu.
FORMAT_RESSOURCE_RETENU = "parquet"

# Le plus gros fichier configuré dépasse 2 Go en Parquet : un délai de 120 s
# (défaut de _flux.py, taillé pour des CSV de quelques dizaines de Mo) serait
# atteint bien avant la fin d'un transfert normal. 20 minutes tolèrent une
# connexion lente sans masquer une vraie panne réseau.
DELAI_ATTENTE_SECONDES_SIRENE = 20 * 60

# Fréquence de journalisation de la progression pendant un téléchargement
# volumineux : sans elle, plusieurs minutes s'écoulent sans aucun signe de vie
# dans les journaux, ce qu'un opérateur ne peut pas distinguer d'un blocage.
# Le rythme est réglé ici ; c'est `_flux.telecharger_en_flux` qui l'applique.
INTERVALLE_JOURNAL_PROGRESSION_SECONDES = 10

# Écart relatif, entre la taille annoncée par le catalogue et la taille
# réellement écrite, au-delà duquel un avertissement est journalisé. Un
# statut HTTP 200 ne garantit pas un flux complet ; `filesize` est la seule
# autre source pour détecter une troncature silencieuse. 5 % tolère les
# écarts d'arrondi et de métadonnées observés en pratique sans masquer une
# troncature réelle, qui se chiffre en dizaines de pourcents sur des fichiers
# de plusieurs centaines de Mo à plus de 2 Go.
SEUIL_ECART_TAILLE_RELATIF = 0.05


class ErreurTelechargementSirene(RuntimeError):
    """Le téléchargement ou la résolution d'un fichier Sirene a échoué.

    Base commune, conservée pour que `pytest.raises(ErreurTelechargementSirene)`
    et tout appelant qui ne distingue pas encore les deux natures d'échec
    continuent de fonctionner sans changement. Un appelant qui doit décider
    entre retenter et alerter capture plutôt l'une des deux sous-classes
    ci-dessous — ou le vocabulaire commun `ErreurTransitoire` /
    `ErreurDefinitive` de `_flux.py`, partagé avec Parcoursup.
    """


class ErreurReseauSirene(ErreurTelechargementSirene, ErreurTransitoire):
    """Le catalogue ou le fichier Sirene était injoignable : échec transitoire, à retenter.

    Levée sur `requests.RequestException` — coupure réseau, délai dépassé,
    5xx. Le contrat du catalogue n'est pas en cause, seul l'accès à cet
    instant a échoué.
    """


class ErreurCatalogueSirene(ErreurTelechargementSirene, ErreurDefinitive):
    """Le catalogue Sirene ne respecte plus le contrat attendu : échec définitif, à ne pas retenter.

    Levée quand la réponse du catalogue est mal formée, quand un fichier
    configuré n'a plus de ressource Parquet correspondante, ou quand la
    résolution est ambiguë. Retenter reproduirait exactement le même échec :
    seule une intervention humaine (mise à jour de la configuration,
    arbitrage sur une ambiguïté) peut le résoudre.
    """


@dataclass(frozen=True)
class RessourceCatalogue:
    """Une ressource résolue depuis le catalogue data.gouv : ce que le module a besoin de savoir d'elle."""

    fichier: str
    url: str
    date_publication: str
    taille_octets_annoncee: int


@dataclass(frozen=True)
class ResultatTelechargementSirene:
    """Trace d'un téléchargement Sirene, qu'il ait eu lieu ou ait été évité."""

    fichier: str
    url: str
    date_publication: str
    chemin: Path
    telecharge: bool
    taille_octets: int
    empreinte_sha256: str


def _dossier_sirene(settings: Settings) -> Path:
    return settings.raw_dir / "sirene"


def _chemin_destination(settings: Settings, fichier: str) -> Path:
    return _dossier_sirene(settings) / f"{fichier}.parquet"


def _chemin_manifeste(settings: Settings) -> Path:
    return _dossier_sirene(settings) / NOM_FICHIER_MANIFESTE


# ─── Résolution du catalogue ────────────────────────────────────────────────


def _url_catalogue(settings: Settings) -> str:
    return settings.donnees.sirene.url_catalogue_gabarit.format(
        jeu_de_donnees=settings.donnees.sirene.jeu_de_donnees
    )


def _correspond_au_fichier(titre_ressource: str, fichier: str) -> bool:
    """Une ressource correspond à `fichier` si son titre porte exactement ce nom, pas un préfixe.

    Les titres INSEE ont la forme « Sirene : Fichier {Nom} - {date} » (avec un
    suffixe « (format parquet) » pour la variante Parquet). Chercher `fichier`
    comme simple sous-chaîne ferait correspondre un nom court au titre d'un
    fichier dont il n'est qu'un préfixe (deux des fichiers configurés sont
    dans ce cas) : on exige donc que le nom soit immédiatement suivi de
    l'espace-tiret qui introduit la date, unique à chaque fichier.
    """
    return f"Fichier {fichier} -" in titre_ressource


def _ressources_du_catalogue(catalogue: object, url_catalogue: str) -> list[dict]:
    """Valide la forme de la réponse JSON du catalogue et en extrait la liste des ressources.

    Une API tierce n'est pas sous notre contrôle : sa réponse est une donnée
    non fiable comme une autre, à valider champ par champ avant usage — pas
    une simple exception à intercepter après coup. Chaque écart au contrat
    attendu (objet JSON à la racine, champ `resources` de type liste, chaque
    ressource elle-même un objet) est nommé explicitement, pour que l'appelant
    (le DAG d'orchestration notamment) sache exactement ce qui a changé côté
    catalogue plutôt que de recevoir une trace Python générique.
    """
    if not isinstance(catalogue, dict):
        raise ErreurCatalogueSirene(
            f"Réponse du catalogue Sirene ({url_catalogue}) mal formée : un objet JSON "
            f"était attendu à la racine, reçu {type(catalogue).__name__}."
        )
    ressources = catalogue.get("resources")
    if ressources is None:
        ressources = []
    if not isinstance(ressources, list):
        raise ErreurCatalogueSirene(
            f"Réponse du catalogue Sirene ({url_catalogue}) mal formée : le champ "
            f"'resources' doit être une liste, reçu {type(ressources).__name__}."
        )
    for index, ressource in enumerate(ressources):
        if not isinstance(ressource, dict):
            raise ErreurCatalogueSirene(
                f"Réponse du catalogue Sirene ({url_catalogue}) mal formée : la ressource "
                f"à l'index {index} doit être un objet JSON, reçu {type(ressource).__name__}."
            )
    return ressources


def _ressource_catalogue_valide(ressource: dict, fichier: str, url_catalogue: str) -> RessourceCatalogue:
    """Construit une `RessourceCatalogue` à partir d'une ressource déjà sélectionnée, en validant `url` et `last_modified`.

    Deux champs sont vérifiés explicitement plutôt que de laisser une
    `KeyError` remonter, sans jamais deviner de valeur par défaut à leur
    place : `url`, sans quoi rien n'est téléchargeable, et `last_modified`,
    la date de publication du stock INSEE (enregistrée au manifeste sous
    `date_publication_stock`) — un stock Sirene grossit chaque mois, un
    volume sans la date à laquelle il se rapporte n'est pas reproductible.
    On ne se rabat ni sur une chaîne vide ni sur la date du jour.

    `filesize` n'est pas soumis à la même exigence : une taille *annoncée*
    par le catalogue, à titre informatif désormais (voir
    `_avertir_si_ecart_de_taille`), jamais une garantie de traçabilité — son
    absence ne bloque donc pas la résolution.
    """
    url = ressource.get("url")
    if not url:
        raise ErreurCatalogueSirene(
            f"Ressource Parquet retenue pour {fichier!r} dans le catalogue ({url_catalogue}) "
            f"est mal formée : champ 'url' absent ou vide (reçu {url!r})."
        )
    date_publication = ressource.get("last_modified")
    if not date_publication or not isinstance(date_publication, str):
        raise ErreurCatalogueSirene(
            f"Ressource Parquet retenue pour {fichier!r} dans le catalogue ({url_catalogue}) "
            f"est mal formée : champ 'last_modified' absent, vide ou non exploitable "
            f"(reçu {date_publication!r}). C'est la date de publication du stock Sirene "
            "(enregistrée au manifeste sous 'date_publication_stock') : sans elle, la "
            "volumétrie téléchargée n'est pas datée et n'est donc pas reproductible."
        )
    return RessourceCatalogue(
        fichier=fichier,
        url=url,
        date_publication=date_publication,
        taille_octets_annoncee=int(ressource.get("filesize") or 0),
    )


def resoudre_ressources(
    settings: Settings | None = None,
    session: requests.Session | None = None,
) -> list[RessourceCatalogue]:
    """Interroge le catalogue data.gouv et résout l'URL Parquet actuelle des fichiers configurés.

    Ne télécharge aucun fichier de données : un seul appel, léger (le
    descriptif JSON du jeu de données), suffit à obtenir les URL courantes.

    Raises:
        ErreurReseauSirene: le catalogue est injoignable (réseau, délai
            dépassé, HTTP 5xx) — transitoire, une nouvelle tentative après
            temporisation peut suffire.
        ErreurCatalogueSirene: le catalogue répond mais ne respecte plus le
            contrat attendu (racine non-objet, `resources` absent/nul/non-liste,
            ressource non-objet ou sans URL exploitable), ou un fichier
            configuré (`donnees.sirene.fichiers`) n'a pas de ressource Parquet
            correspondante ce mois-ci — le catalogue peut avoir renommé ou
            retiré un fichier. Définitif : retenter ne change rien, une
            intervention humaine est nécessaire.
    """
    settings = settings or get_settings()
    url_catalogue = _url_catalogue(settings)

    with session_http(session) as session_active:
        try:
            reponse = session_active.get(url_catalogue, timeout=DELAI_ATTENTE_SECONDES_DEFAUT)
            reponse.raise_for_status()
        except requests.RequestException as erreur:
            raise ErreurReseauSirene(
                f"Catalogue Sirene injoignable ({url_catalogue}) : {erreur}. "
                "Aucune URL ne peut être résolue sans lui — Sirene n'a pas de "
                "gabarit d'URL fixe, contrairement à Parcoursup."
            ) from erreur
        catalogue = reponse.json()

    ressources = _ressources_du_catalogue(catalogue, url_catalogue)
    resultats: list[RessourceCatalogue] = []
    for fichier in settings.donnees.sirene.fichiers:
        candidates = [
            ressource
            for ressource in ressources
            if ressource.get("format") == FORMAT_RESSOURCE_RETENU
            and _correspond_au_fichier(ressource.get("title") or "", fichier)
        ]
        if not candidates:
            raise ErreurCatalogueSirene(
                f"Aucune ressource Parquet nommée « Fichier {fichier} - ... » "
                f"trouvée dans le catalogue ({url_catalogue}) : le fichier a pu "
                "être renommé ou retiré. Rien n'est téléchargé pour lui."
            )
        if len(candidates) > 1:
            raise ErreurCatalogueSirene(
                f"{len(candidates)} ressources Parquet correspondent à {fichier!r} "
                f"dans le catalogue ({url_catalogue}) : résolution ambiguë, "
                "aucune ne peut être choisie sans arbitrage explicite."
            )
        resultats.append(_ressource_catalogue_valide(candidates[0], fichier, url_catalogue))
    return resultats


# ─── Journalisation de la progression ───────────────────────────────────────


def _journaliser_progression(fichier: str) -> Callable[[int], None]:
    """Construit la fonction de rappel journalisant l'avancement d'un fichier nommé.

    `_flux.telecharger_en_flux` porte le rythme de rappel (au plus une fois
    par `INTERVALLE_JOURNAL_PROGRESSION_SECONDES`) et le décompte des octets ;
    cette fonction ne décide que du message, propre à Sirene puisqu'il nomme
    le fichier en cours parmi les quatre téléchargés.
    """

    def _rappel(octets_recus: int) -> None:
        LOGGER.info("Téléchargement %s en cours : %.0f Mo reçus", fichier, octets_recus / 1_000_000)

    return _rappel


# ─── Orchestration ───────────────────────────────────────────────────────────


def _resultat_depuis_manifeste(
    ressource: RessourceCatalogue, chemin: Path, entree: dict[str, object]
) -> ResultatTelechargementSirene:
    return ResultatTelechargementSirene(
        fichier=ressource.fichier,
        url=ressource.url,
        date_publication=ressource.date_publication,
        chemin=chemin,
        telecharge=False,
        taille_octets=int(entree["taille_octets"]),
        empreinte_sha256=str(entree["empreinte_sha256"]),
    )


def _entree_manifeste(ressource: RessourceCatalogue, taille_octets: int, empreinte: str) -> dict[str, object]:
    """Construit l'entrée de manifeste d'un fichier tout juste téléchargé, avec sa date de stock.

    Symétrique de `_resultat_depuis_manifeste` : celle-ci relit une entrée
    existante, celle-ci en écrit une nouvelle. Séparer la construction de ce
    dictionnaire de l'orchestration du téléchargement garde `telecharger_fichier`
    lisible d'un seul tenant.
    """
    return {
        "fichier": ressource.fichier,
        "url": ressource.url,
        "date_publication_stock": ressource.date_publication,
        "date_telechargement": datetime.now(timezone.utc).isoformat(),
        "taille_octets": taille_octets,
        "empreinte_sha256": empreinte,
    }


def _avertir_si_ecart_de_taille(ressource: RessourceCatalogue, taille_octets: int) -> None:
    """Journalise un avertissement si la taille écrite diverge de celle annoncée par le catalogue.

    Sans effet si le catalogue n'annonçait aucune taille exploitable (`0` ou
    négative — fichier tout juste publié, ou `filesize` absent) : rien à
    comparer, ce n'est pas une anomalie en soi. Un dépassement du seuil est
    **journalisé, jamais levé** : contrairement à `url` ou `last_modified`,
    `filesize` n'est pas garanti par contrat — en faire une condition
    bloquante romprait la chaîne pour une cause qui n'est pas nécessairement
    la nôtre. L'écart doit rester visible, pas fatal.
    """
    annoncee = ressource.taille_octets_annoncee
    if annoncee <= 0:
        return
    ecart_relatif = abs(taille_octets - annoncee) / annoncee
    if ecart_relatif <= SEUIL_ECART_TAILLE_RELATIF:
        return
    LOGGER.warning(
        "ECART_TAILLE_SIRENE %s : %.0f Mo annoncés par le catalogue, %.0f Mo réellement "
        "écrits (écart de %.1f%%) — possible troncature silencieuse, à vérifier avant usage.",
        ressource.fichier,
        annoncee / 1_000_000,
        taille_octets / 1_000_000,
        ecart_relatif * 100,
    )


def _telecharger_et_verifier_taille(
    ressource: RessourceCatalogue, chemin_final: Path, session_active: requests.Session
) -> tuple[int, str]:
    """Télécharge le fichier, traduit un échec réseau, puis confronte la taille écrite à celle annoncée.

    Isole la notion propre à ce correctif — un statut HTTP 200 ne garantit
    pas un flux complet — du reste de l'orchestration de `telecharger_fichier`,
    qui n'a pas à connaître le détail de cette vérification.
    """
    try:
        telecharger_en_flux(
            session_active,
            ressource.url,
            chemin_final,
            timeout=DELAI_ATTENTE_SECONDES_SIRENE,
            sur_progression=_journaliser_progression(ressource.fichier),
            intervalle_progression_secondes=INTERVALLE_JOURNAL_PROGRESSION_SECONDES,
        )
    except requests.RequestException as erreur:
        raise ErreurReseauSirene(
            f"Échec du téléchargement de {ressource.fichier} depuis {ressource.url} : {erreur}"
        ) from erreur

    taille_octets = chemin_final.stat().st_size
    _avertir_si_ecart_de_taille(ressource, taille_octets)
    return taille_octets, empreinte_sha256(chemin_final)


def telecharger_fichier(
    ressource: RessourceCatalogue,
    settings: Settings | None = None,
    session: requests.Session | None = None,
    forcer: bool = False,
) -> ResultatTelechargementSirene:
    """Télécharge un fichier Sirene déjà résolu, ou constate qu'il est présent et intact.

    Args:
        ressource: URL et métadonnées déjà résolues par `resoudre_ressources`.
            Séparer résolution et téléchargement permet de prouver la
            résolution (tests, vérification manuelle) sans déclencher un
            transfert de plusieurs centaines de Mo.
        settings: configuration résolue. À défaut, `get_settings()`.
        session: session HTTP réutilisable. À défaut, une session neuve.
        forcer: ignore le contrôle d'idempotence et retélécharge.

    Raises:
        ErreurReseauSirene: échec réseau ou HTTP lors du téléchargement —
            transitoire, à retenter.
        ErreurFluxVide: réponse HTTP réussie mais au corps vide (0 octet) —
            levée telle quelle par `_flux.telecharger_en_flux`, pas traduite
            en `ErreurReseauSirene` : ce n'est pas un incident réseau.
    """
    settings = settings or get_settings()
    chemin_final = _chemin_destination(settings, ressource.fichier)
    chemin_manifeste = _chemin_manifeste(settings)

    manifeste = lire_manifeste(chemin_manifeste)
    entree_existante = manifeste.get(ressource.fichier)

    if not forcer and fichier_intact(chemin_final, entree_existante):
        LOGGER.info(
            "%s déjà présent et intact (%s) : téléchargement évité.",
            ressource.fichier,
            chemin_final,
        )
        return _resultat_depuis_manifeste(ressource, chemin_final, entree_existante)

    LOGGER.info(
        "Téléchargement de %s (stock du %s) depuis %s",
        ressource.fichier,
        ressource.date_publication,
        ressource.url,
    )
    with session_http(session) as session_active:
        taille_octets, empreinte = _telecharger_et_verifier_taille(ressource, chemin_final, session_active)

    LOGGER.info("Téléchargement %s terminé : %.0f Mo reçus au total", ressource.fichier, taille_octets / 1_000_000)
    manifeste[ressource.fichier] = _entree_manifeste(ressource, taille_octets, empreinte)
    ecrire_manifeste(chemin_manifeste, manifeste)

    return ResultatTelechargementSirene(
        fichier=ressource.fichier,
        url=ressource.url,
        date_publication=ressource.date_publication,
        chemin=chemin_final,
        telecharge=True,
        taille_octets=taille_octets,
        empreinte_sha256=empreinte,
    )


def telecharger_tous(
    settings: Settings | None = None,
    session: requests.Session | None = None,
    forcer: bool = False,
) -> list[ResultatTelechargementSirene]:
    """Résout le catalogue une fois, puis télécharge chaque fichier configuré.

    Une session HTTP unique est réutilisée pour l'appel au catalogue et les
    téléchargements, comme pour Parcoursup.
    """
    settings = settings or get_settings()
    with session_http(session) as session_active:
        ressources = resoudre_ressources(settings=settings, session=session_active)
        return [
            telecharger_fichier(ressource, settings=settings, session=session_active, forcer=forcer)
            for ressource in ressources
        ]


def resultat_en_dict(resultat: ResultatTelechargementSirene) -> dict[str, object]:
    """Représentation sérialisable d'un résultat, pour la journalisation ou un DAG."""
    donnees = asdict(resultat)
    donnees["chemin"] = str(donnees["chemin"])
    return donnees
