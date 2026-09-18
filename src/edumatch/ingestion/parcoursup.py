"""Connecteur d'ingestion Parcoursup — huit millésimes, un fichier CSV chacun.

Télécharge, pour chaque millésime déclaré dans la configuration, l'export CSV
publié par le MESR sur son portail public, et l'écrit dans la zone brute
(`raw_dir/parcoursup/`), immuable une fois posée. L'hôte exact et
l'identifiant de chaque millésime viennent de `configs/base.yaml`, pas de ce
module.

Deux garanties structurent ce module, exigées pour toute tâche d'un pipeline
de données :

- **Idempotence** : rejouer le téléchargement d'un millésime déjà présent et
  intact ne retélécharge rien. C'est ce qui permet de relancer la chaîne
  après un incident sans dupliquer ni retélécharger inutilement les 82 Mo
  des huit millésimes.
- **Écriture atomique** : chaque fichier est écrit sous un nom temporaire
  (`.part`) puis renommé vers son nom définitif seulement une fois le
  téléchargement terminé avec succès. Une interruption au milieu du transfert
  ne laisse donc jamais de fichier tronqué à l'emplacement que le reste du
  pipeline croirait complet.

Ce module ne porte que ce qui est propre à Parcoursup : la résolution de
l'URL à partir d'un identifiant de millésime, et l'orchestration du
téléchargement d'un ou plusieurs millésimes. Le reste — flux HTTP, empreinte,
écriture atomique, manifeste — est mutualisé dans `_flux.py`, commun à tout
connecteur d'ingestion du projet.

Aucun identifiant de jeu de données, aucune URL, aucun chemin n'est écrit en
dur ici : tout vient de `Settings` (`configs/*.yaml`), conformément à la
configuration centralisée du projet.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from edumatch.config import Settings, get_settings
from edumatch.ingestion._flux import (
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


class ErreurTelechargementParcoursup(RuntimeError):
    """Le téléchargement d'un millésime a échoué.

    Levée plutôt que masquée : un appelant (tâche d'orchestration, script) ne
    doit jamais recevoir un fichier partiel sans le savoir.

    Base commune, conservée pour que `pytest.raises(ErreurTelechargementParcoursup)`
    et tout appelant qui ne distingue pas encore les deux natures d'échec
    continuent de fonctionner sans changement. Un appelant qui doit décider
    entre retenter et alerter capture plutôt l'une des deux sous-classes
    ci-dessous — ou le vocabulaire commun `ErreurTransitoire` /
    `ErreurDefinitive` de `_flux.py`, partagé avec Sirene.
    """


class ErreurReseauParcoursup(ErreurTelechargementParcoursup, ErreurTransitoire):
    """Le fichier d'un millésime était injoignable : échec transitoire, à retenter.

    Levée sur `requests.RequestException` — coupure réseau, délai dépassé,
    5xx. Le gabarit d'URL et la configuration du millésime ne sont pas en
    cause, seul l'accès à cet instant a échoué.
    """


class ErreurConfigurationParcoursup(ErreurTelechargementParcoursup, ErreurDefinitive):
    """Le millésime demandé n'est pas configuré : échec définitif, à ne pas retenter.

    Retenter ne fera pas apparaître un identifiant qui n'existe pas dans
    `donnees.parcoursup.millesimes` : seule une mise à jour de la
    configuration (ou une correction de l'appelant) peut le résoudre.
    """


@dataclass(frozen=True)
class ResultatTelechargement:
    """Trace d'un téléchargement, qu'il ait eu lieu ou ait été évité.

    `telecharge` distingue les deux cas pour que l'appelant (et les tests)
    puissent vérifier l'idempotence sans inspecter le système de fichiers.
    """

    millesime: int
    identifiant: str
    chemin: Path
    telecharge: bool
    taille_octets: int
    empreinte_sha256: str


def _url_export(identifiant: str, gabarit: str) -> str:
    """Construit l'URL d'export CSV d'un millésime à partir du gabarit configuré.

    Spécifique à Parcoursup : le gabarit est fixe, seul l'identifiant varie.
    Ce n'est pas mutualisable avec Sirene, dont l'URL vient d'une recherche
    dans le catalogue data.gouv et change chaque mois.
    """
    return gabarit.format(identifiant=identifiant)


def _dossier_parcoursup(settings: Settings) -> Path:
    return settings.raw_dir / "parcoursup"


def _chemin_destination(settings: Settings, millesime: int) -> Path:
    return _dossier_parcoursup(settings) / f"parcoursup_{millesime}.csv"


def _chemin_manifeste(settings: Settings) -> Path:
    return _dossier_parcoursup(settings) / NOM_FICHIER_MANIFESTE


def _identifiant_valide(millesime: int, settings: Settings) -> str:
    """Vérifie que le millésime est configuré et renvoie son identifiant de jeu de données."""
    parcoursup_config = settings.donnees.parcoursup
    if millesime not in parcoursup_config.millesimes:
        raise ErreurConfigurationParcoursup(
            f"Millésime {millesime} absent de donnees.parcoursup.millesimes "
            f"({parcoursup_config.millesimes}) : rien à télécharger."
        )
    return parcoursup_config.identifiants[millesime]


def _resultat_depuis_manifeste(
    millesime: int, identifiant: str, chemin: Path, entree: dict[str, object]
) -> ResultatTelechargement:
    return ResultatTelechargement(
        millesime=millesime,
        identifiant=identifiant,
        chemin=chemin,
        telecharge=False,
        taille_octets=int(entree["taille_octets"]),
        empreinte_sha256=str(entree["empreinte_sha256"]),
    )


def telecharger_millesime(
    millesime: int,
    settings: Settings | None = None,
    session: requests.Session | None = None,
    forcer: bool = False,
) -> ResultatTelechargement:
    """Télécharge l'export CSV d'un millésime, ou constate qu'il est déjà présent et intact.

    Args:
        millesime: année Parcoursup à télécharger. Doit figurer dans
            `settings.donnees.parcoursup.millesimes` et avoir un identifiant
            dans `settings.donnees.parcoursup.identifiants`.
        settings: configuration résolue. À défaut, `get_settings()`.
        session: session HTTP réutilisable (tests, appels groupés). À défaut,
            une session `requests` neuve.
        forcer: ignore le contrôle d'idempotence et retélécharge.

    Raises:
        ErreurConfigurationParcoursup: le millésime n'est pas déclaré dans
            la configuration — définitif, retenter ne suffit pas.
        ErreurReseauParcoursup: échec réseau ou HTTP lors du téléchargement —
            transitoire, une nouvelle tentative après temporisation peut
            suffire.
        ErreurFluxVide: réponse HTTP réussie mais au corps vide (0 octet) —
            levée telle quelle par `_flux.telecharger_en_flux`, pas traduite
            dans le vocabulaire de ce connecteur : ce n'est pas un incident
            réseau, donc pas `ErreurReseauParcoursup`.
    """
    settings = settings or get_settings()
    identifiant = _identifiant_valide(millesime, settings)
    url = _url_export(identifiant, settings.donnees.parcoursup.url_export_gabarit)
    chemin_final = _chemin_destination(settings, millesime)
    chemin_manifeste = _chemin_manifeste(settings)

    manifeste = lire_manifeste(chemin_manifeste)
    entree_existante = manifeste.get(str(millesime))

    if not forcer and fichier_intact(chemin_final, entree_existante):
        LOGGER.info(
            "Millésime %s déjà présent et intact (%s) : téléchargement évité.",
            millesime,
            chemin_final,
        )
        return _resultat_depuis_manifeste(millesime, identifiant, chemin_final, entree_existante)

    LOGGER.info("Téléchargement du millésime %s depuis %s", millesime, url)
    with session_http(session) as session_active:
        try:
            telecharger_en_flux(session_active, url, chemin_final)
        except requests.RequestException as erreur:
            # On ne masque pas la cause : l'écriture atomique a déjà nettoyé
            # tout fichier `.part` résiduel, on ne fait que traduire
            # l'exception dans le vocabulaire de ce connecteur.
            raise ErreurReseauParcoursup(
                f"Échec du téléchargement du millésime {millesime} depuis {url} : {erreur}"
            ) from erreur

    taille_octets = chemin_final.stat().st_size
    empreinte = empreinte_sha256(chemin_final)
    manifeste[str(millesime)] = {
        "millesime": millesime,
        "identifiant": identifiant,
        "url": url,
        "date_telechargement": datetime.now(UTC).isoformat(),
        "taille_octets": taille_octets,
        "empreinte_sha256": empreinte,
    }
    ecrire_manifeste(chemin_manifeste, manifeste)

    return ResultatTelechargement(
        millesime=millesime,
        identifiant=identifiant,
        chemin=chemin_final,
        telecharge=True,
        taille_octets=taille_octets,
        empreinte_sha256=empreinte,
    )


def telecharger_tous(
    settings: Settings | None = None,
    session: requests.Session | None = None,
    forcer: bool = False,
) -> list[ResultatTelechargement]:
    """Télécharge tous les millésimes déclarés dans la configuration, dans l'ordre croissant.

    Une session HTTP unique est réutilisée pour les huit appels : elle
    maintient la connexion TCP ouverte au lieu d'en renégocier une par
    millésime.
    """
    settings = settings or get_settings()
    with session_http(session) as session_active:
        return [
            telecharger_millesime(millesime, settings=settings, session=session_active, forcer=forcer)
            for millesime in sorted(settings.donnees.parcoursup.millesimes)
        ]


def resultat_en_dict(resultat: ResultatTelechargement) -> dict[str, object]:
    """Représentation sérialisable d'un résultat, pour la journalisation ou un DAG."""
    donnees = asdict(resultat)
    donnees["chemin"] = str(donnees["chemin"])
    return donnees


def main() -> int:
    """Point d'entrée : télécharge les millésimes Parcoursup configurés, puis résume ce qui a été fait.

    `--forcer` retélécharge même si le manifeste annonce le fichier déjà pris.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    forcer = "--forcer" in sys.argv[1:]
    resultats = telecharger_tous(forcer=forcer)
    telecharges = sum(1 for resultat in resultats if resultat.telecharge)
    LOGGER.info(
        "les millésimes Parcoursup configurés : %d ressource(s) traitée(s), %d téléchargée(s), %d déjà à jour.",
        len(resultats),
        telecharges,
        len(resultats) - telecharges,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
