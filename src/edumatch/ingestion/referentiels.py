"""Connecteur d'ingestion des référentiels — ONISEP (IDÉO) et RNCP/RS.

Point d'entrée public du troisième connecteur du projet, après Parcoursup et
Sirene. Deux familles de sources, deux comportements :

- **IDÉO** (ONISEP), traité ici : quatre jeux à URL fixe (formations,
  métiers, structures secondaire, structures supérieur). Comme Parcoursup,
  l'URL ne change pas d'une exécution à l'autre : l'idempotence se fait par
  empreinte SHA-256 sur un fichier unique par jeu, écrasé seulement si le
  contenu a changé.
- **RNCP/RS** (France Compétences), dans `_referentiels_rncp.py` : un export
  **republié chaque jour**, qui exige un choix d'idempotence différent —
  voir la discussion dans ce module.

Deux garanties, communes à tout connecteur du projet : **idempotence**
(rejouer un téléchargement déjà présent et intact ne retélécharge rien) et
**écriture atomique** (fichier `.part` renommé une fois complet), toutes
deux fournies par `_flux.py`.

Ce module ne décode jamais le contenu des sources : il vérifie seulement,
une fois le fichier écrit, qu'il est décodable selon l'encodage déclaré en
configuration (`donnees.referentiels.*.encodage`) — un contrôle de contrat de
données, pas une transformation. Le décodage réel appartient à la couche
silver.

Les classes d'erreur (`ErreurTelechargementReferentiels` et ses sous-classes)
et le vocabulaire commun `ErreurTransitoire` / `ErreurDefinitive` sont
partagés avec IDÉO et RNCP dans `_referentiels_communs.py`, ré-exportés ici
pour que l'appelant n'ait qu'un seul module à importer.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import requests

from edumatch.config import Settings, get_settings
from edumatch.ingestion import _referentiels_france_travail as france_travail
from edumatch.ingestion import _referentiels_rncp as rncp
from edumatch.ingestion._flux import (
    ecrire_manifeste,
    empreinte_sha256,
    fichier_intact,
    lire_manifeste,
    session_http,
    telecharger_en_flux,
)
from edumatch.ingestion._referentiels_communs import (
    ErreurCatalogueReferentiels,
    ErreurConfigurationReferentiels,
    ErreurContratReferentiels,
    ErreurReseauReferentiels,
    ErreurTelechargementReferentiels,
    ResultatTelechargementReferentiel,
    chemin_manifeste,
    dossier_referentiels,
    verifier_encodage,
)

# Ré-exportées : le vocabulaire commun aux deux volets vit dans
# _referentiels_communs.py, mais l'appelant de ce connecteur n'a besoin que
# de connaître referentiels.py, comme pour Parcoursup et Sirene.
__all__ = [
    "ErreurCatalogueReferentiels",
    "ErreurConfigurationReferentiels",
    "ErreurContratReferentiels",
    "ErreurReseauReferentiels",
    "ErreurTelechargementReferentiels",
    "ResultatTelechargementReferentiel",
    "resultat_en_dict",
    "telecharger_ideo",
    "telecharger_tous",
    "telecharger_tous_ideo",
]

LOGGER = logging.getLogger(__name__)


# ─── IDÉO (ONISEP) — URL fixe, un fichier par jeu ────────────────────────────


def _chemin_destination_ideo(settings: Settings, jeu: str) -> Path:
    return dossier_referentiels(settings) / "ideo" / f"{jeu}.csv"


def _config_jeu_ideo(jeu: str, settings: Settings):
    jeux = settings.donnees.referentiels.ideo.jeux
    if jeu not in jeux:
        raise ErreurConfigurationReferentiels(
            f"Jeu IDÉO {jeu!r} absent de donnees.referentiels.ideo.jeux "
            f"({sorted(jeux)}) : rien à télécharger."
        )
    return jeux[jeu]


def _resultat_ideo_depuis_manifeste(
    jeu: str, chemin: Path, entree: dict[str, object], telecharge: bool
) -> ResultatTelechargementReferentiel:
    return ResultatTelechargementReferentiel(
        source="ideo",
        jeu=jeu,
        url=str(entree["url"]),
        chemin=chemin,
        telecharge=telecharge,
        taille_octets=int(entree["taille_octets"]),
        empreinte_sha256=str(entree["empreinte_sha256"]),
        encodage=str(entree["encodage"]),
        delimiteur=str(entree["delimiteur"]),
        licence=str(entree["licence"]),
        date_publication=None,
    )


def telecharger_ideo(
    jeu: str,
    settings: Settings | None = None,
    session: requests.Session | None = None,
    forcer: bool = False,
) -> ResultatTelechargementReferentiel:
    """Télécharge un jeu IDÉO, ou constate qu'il est déjà présent et intact.

    Args:
        jeu: nom du jeu (`formations`, `metiers`, `structures_secondaire`,
            `structures_superieur`), doit figurer dans
            `settings.donnees.referentiels.ideo.jeux`.
        settings: configuration résolue. À défaut, `get_settings()`.
        session: session HTTP réutilisable. À défaut, une session neuve.
        forcer: ignore le contrôle d'idempotence et retélécharge.

    Raises:
        ErreurConfigurationReferentiels: jeu non déclaré — définitif.
        ErreurReseauReferentiels: échec réseau ou HTTP — transitoire.
        ErreurContratReferentiels: le fichier téléchargé ne décode pas selon
            l'encodage déclaré.
        ErreurFluxVide: réponse HTTP réussie mais au corps vide (0 octet) —
            levée telle quelle par `_flux.telecharger_en_flux`, pas traduite
            en `ErreurReseauReferentiels` : ce n'est pas un incident réseau.
    """
    settings = settings or get_settings()
    config_jeu = _config_jeu_ideo(jeu, settings)
    chemin_final = _chemin_destination_ideo(settings, jeu)
    chemin_manif = chemin_manifeste(settings)

    manifeste = lire_manifeste(chemin_manif)
    cle = f"ideo:{jeu}"
    entree_existante = manifeste.get(cle)

    if not forcer and fichier_intact(chemin_final, entree_existante):
        LOGGER.info("IDÉO %s déjà présent et intact (%s) : téléchargement évité.", jeu, chemin_final)
        return _resultat_ideo_depuis_manifeste(jeu, chemin_final, entree_existante, telecharge=False)

    LOGGER.info("Téléchargement du jeu IDÉO %s depuis %s", jeu, config_jeu.url)
    with session_http(session) as session_active:
        try:
            telecharger_en_flux(session_active, config_jeu.url, chemin_final)
        except requests.RequestException as erreur:
            raise ErreurReseauReferentiels(
                f"Échec du téléchargement du jeu IDÉO {jeu} depuis {config_jeu.url} : {erreur}"
            ) from erreur

    verifier_encodage(chemin_final, config_jeu.encodage, f"IDÉO {jeu}")

    taille_octets = chemin_final.stat().st_size
    empreinte = empreinte_sha256(chemin_final)
    manifeste[cle] = {
        "source": "ideo",
        "jeu": jeu,
        "url": config_jeu.url,
        "encodage": config_jeu.encodage,
        "delimiteur": config_jeu.delimiteur,
        "licence": config_jeu.licence,
        "date_telechargement": datetime.now(UTC).isoformat(),
        "taille_octets": taille_octets,
        "empreinte_sha256": empreinte,
    }
    ecrire_manifeste(chemin_manif, manifeste)

    return _resultat_ideo_depuis_manifeste(jeu, chemin_final, manifeste[cle], telecharge=True)


def telecharger_tous_ideo(
    settings: Settings | None = None,
    session: requests.Session | None = None,
    forcer: bool = False,
) -> list[ResultatTelechargementReferentiel]:
    """Télécharge tous les jeux IDÉO déclarés dans la configuration."""
    settings = settings or get_settings()
    with session_http(session) as session_active:
        return [
            telecharger_ideo(jeu, settings=settings, session=session_active, forcer=forcer)
            for jeu in sorted(settings.donnees.referentiels.ideo.jeux)
        ]


# ─── Orchestration groupée : IDÉO puis RNCP ─────────────────────────────────


def telecharger_tous(
    settings: Settings | None = None,
    session: requests.Session | None = None,
    forcer: bool = False,
) -> list[ResultatTelechargementReferentiel]:
    """Télécharge IDÉO, puis les deux membres RNCP du jour, puis la table France Travail.

    Une session HTTP unique est réutilisée pour l'ensemble des appels, comme
    pour Parcoursup et Sirene. La résolution et le téléchargement de chaque
    source RNCP et France Travail sont délégués à leur module dédié
    (`_referentiels_rncp`, `_referentiels_france_travail`) : la mécanique d'un
    export quotidien archivé en ZIP, ou d'une ressource résolue par titre,
    n'a rien de commun avec le téléchargement direct des jeux IDÉO.
    """
    settings = settings or get_settings()
    with session_http(session) as session_active:
        resultats = telecharger_tous_ideo(settings=settings, session=session_active, forcer=forcer)
        ressource_rncp = rncp.resoudre_ressource(settings=settings, session=session_active)
        resultats.append(rncp.telecharger(ressource_rncp, settings=settings, session=session_active, forcer=forcer))
        resultats.append(
            rncp.telecharger_rome(ressource_rncp, settings=settings, session=session_active, forcer=forcer)
        )
        ressource_ft = france_travail.resoudre_ressource(settings=settings, session=session_active)
        resultats.append(
            france_travail.telecharger(ressource_ft, settings=settings, session=session_active, forcer=forcer)
        )
        return resultats


def resultat_en_dict(resultat: ResultatTelechargementReferentiel) -> dict[str, object]:
    """Représentation sérialisable d'un résultat, pour la journalisation ou un DAG."""
    donnees = asdict(resultat)
    donnees["chemin"] = str(donnees["chemin"])
    return donnees


def main() -> int:
    """Point d'entrée : télécharge les référentiels IDÉO, RNCP et France Travail, puis résume ce qui a été fait.

    `--forcer` retélécharge même si le manifeste annonce le fichier déjà pris.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    forcer = "--forcer" in sys.argv[1:]
    resultats = telecharger_tous(forcer=forcer)
    telecharges = sum(1 for resultat in resultats if resultat.telecharge)
    LOGGER.info(
        "les référentiels IDÉO, RNCP et France Travail : %d ressource(s) traitée(s), %d téléchargée(s), %d déjà à jour.",
        len(resultats),
        telecharges,
        len(resultats) - telecharges,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
