"""Primitives partagées par les connecteurs d'ingestion (Parcoursup, Sirene, référentiels).

Ce module ne contient **aucune connaissance d'une source précise** : ni URL, ni
identifiant de jeu de données, ni nom de fichier attendu. Il porte uniquement
les mécaniques répétées à l'identique par tout connecteur qui télécharge un
fichier public et doit garantir l'idempotence et l'écriture atomique :

- ouverture et fermeture d'une session HTTP, fournie ou créée localement
- téléchargement en flux, bloc par bloc, sans jamais charger le fichier
  entier en mémoire, et rejet d'une réponse à corps vide (`ErreurFluxVide`) :
  un statut HTTP 200 ne garantit pas un contenu, seulement une requête reçue
- calcul d'empreinte SHA-256, pour distinguer un fichier intact d'un fichier
  corrompu ou tronqué
- écriture atomique générique (fichier `.part` renommé une fois complet),
  utilisable aussi bien pour un CSV de plusieurs dizaines de Mo que pour le
  petit JSON du manifeste
- lecture et écriture d'un manifeste de traçabilité, avec la règle : un
  manifeste absent ou corrompu ne bloque jamais la chaîne, mais ne doit
  jamais non plus faire disparaître silencieusement la trace d'un incident
- le vocabulaire commun aux erreurs transitoires et définitives, que chaque
  connecteur combine à sa propre classe d'erreur (voir `ErreurTransitoire` et
  `ErreurDefinitive` ci-dessous)

Ce qui n'est délibérément **pas** ici : la résolution d'une URL à partir d'un
identifiant de millésime ou d'une recherche dans un catalogue. C'est une
variation réelle entre sources (gabarit fixe pour Parcoursup, requête à
data.gouv pour Sirene), pas une mécanique à mutualiser.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

import requests

LOGGER = logging.getLogger(__name__)

# Taille de bloc pour la lecture et l'écriture en flux : évite de charger un
# fichier de plusieurs dizaines de Mo entièrement en mémoire.
TAILLE_BLOC_OCTETS_DEFAUT = 1024 * 1024


# ─── Vocabulaire commun d'erreurs ─────────────────────────────────────────────
#
# Chaque connecteur (Parcoursup, Sirene, référentiels) garde sa propre classe
# d'erreur de base — `ErreurTelechargementParcoursup`, `ErreurTelechargementSirene`
# — pour que les tests et les appelants qui ne s'intéressent qu'à « ce
# connecteur a échoué » continuent d'écrire `pytest.raises(ErreurTelechargementX)`
# sans rien changer. Ce qui manquait, et que tout connecteur doit offrir sans
# le redéfinir chacun à sa façon, c'est la distinction qu'un orchestrateur a
# besoin de faire *avant même de savoir quel connecteur a échoué* : faut-il
# retenter, ou faut-il alerter un humain ?
#
# Ces deux classes sont des mixins, posées ici parce qu'elles ne portent
# aucune connaissance d'une source précise — exactement le critère qui
# gouverne le contenu de ce module. Chaque connecteur les combine par héritage
# multiple avec sa propre classe de base :
#
#     class ErreurReseauSirene(ErreurTelechargementSirene, ErreurTransitoire): ...
#
# Un `except ErreurTransitoire` dans le DAG attrape alors l'échec réseau de
# n'importe quel connecteur, sans connaître leurs classes de base respectives
# ni inspecter le texte du message.


class ErreurTransitoire(Exception):
    """Échec dont une nouvelle tentative, après temporisation, a une chance raisonnable de réussir.

    Typiquement une coupure réseau, un délai d'attente dépassé, une erreur
    HTTP 5xx ou de quota : la source elle-même n'a pas changé de contrat, seul
    l'accès à cet instant a échoué.
    """


class ErreurDefinitive(Exception):
    """Échec qu'une nouvelle tentative ne peut pas résoudre : le contrat de la source a changé.

    Typiquement un catalogue mal formé, une ressource introuvable ou
    ambiguë, un champ obligatoire absent : retenter reproduirait exactement
    le même échec. Un humain doit être alerté, pas un compteur de tentatives.
    """


class ErreurFluxVide(ErreurDefinitive):
    """Une réponse HTTP 200 n'a livré aucun octet.

    Posée ici, dans les primitives communes, et non dans une classe propre à
    chaque connecteur : la faute constatée (un fichier de 0 octet accepté
    comme un téléchargement réussi) était identique pour Parcoursup, Sirene
    et IDÉO, les trois appelants de `telecharger_en_flux`. La corriger une
    seule fois ici les corrige tous les trois à la fois.

    Rangée du côté définitif, pas transitoire : un serveur qui répond 200
    avec un corps vide n'a pas subi un incident de réseau — la requête a
    réussi de bout en bout — il a changé de contrat (export non encore
    généré, ressource déplacée sans mise à jour du lien...). Retenter
    immédiatement reproduirait la même réponse ; seul un humain, ou une
    nouvelle tentative très différée dans le temps, peut trancher.
    """

# Délai maximal d'attente réseau, en secondes, avant d'abandonner une requête.
# Une valeur explicite plutôt que le défaut de `requests` (aucun délai, donc
# un blocage indéfini possible si le serveur ne répond jamais).
DELAI_ATTENTE_SECONDES_DEFAUT = 120


# ─── Session HTTP ─────────────────────────────────────────────────────────────


@contextmanager
def session_http(session: requests.Session | None = None) -> Iterator[requests.Session]:
    """Fournit une session HTTP utilisable, sans jamais fermer une session reçue de l'appelant.

    Reçoit une session existante (tests, appels groupés qui veulent réutiliser
    une connexion TCP) : elle n'est pas fermée à la sortie, sa gestion reste à
    qui l'a créée. Aucune session fournie : une nouvelle est créée, puis fermée
    en sortie de bloc, y compris en cas d'exception.
    """
    session_fournie = session is not None
    session_active = session or requests.Session()
    try:
        yield session_active
    finally:
        if not session_fournie:
            session_active.close()


# ─── Écriture atomique générique ──────────────────────────────────────────────


@contextmanager
def ecriture_atomique(chemin: Path, mode: str = "wb") -> Iterator[IO]:
    """Ouvre un fichier temporaire `.part` et le renomme atomiquement à la sortie du bloc.

    Le fichier n'apparaît sous son nom définitif (`chemin`) que complet et
    fermé : c'est ce qui protège l'immuabilité de `data/raw/` face à une
    interruption réseau ou disque au milieu de l'écriture. En cas d'exception
    dans le bloc, le fichier temporaire est supprimé — jamais de fichier
    tronqué visible sous un nom que le reste du pipeline croirait complet.

    Générique par construction : sert aussi bien à écrire un CSV en flux
    (`mode="wb"`, blocs successifs) qu'un manifeste JSON (`mode="w"`, un seul
    `write`).

    En mode texte (tout `mode` sans "b"), l'encodage est explicitement UTF-8.
    Laisser Python choisir celui de la plateforme (`cp1252` par défaut sous
    Windows) ne fait pas échouer l'écriture — cp1252 sait encoder un accent —
    mais produit des octets que la lecture correspondante ne sait pas relire :
    `lire_manifeste` déclare déjà `encoding="utf-8"`. L'écriture et la lecture
    d'un même fichier ne partageaient donc pas le même contrat, et le défaut
    restait silencieux jusqu'à la relecture. Constaté sur un titre de
    ressource France Travail contenant un accent (« référentiels »). Sous une
    plateforme dont l'encodage par défaut ne saurait pas encoder le caractère,
    l'écriture échouerait franchement — le même défaut se manifeste donc
    différemment selon le poste, ce qui est la pire des deux situations.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin_temporaire = chemin.with_suffix(chemin.suffix + ".part")
    flux = chemin_temporaire.open(mode, encoding=None if "b" in mode else "utf-8")
    try:
        yield flux
    except Exception:
        flux.close()
        chemin_temporaire.unlink(missing_ok=True)
        raise
    else:
        flux.close()
        # Atomique sur un même système de fichiers, y compris sous Windows,
        # contrairement à `Path.rename` qui y échoue si la cible existe déjà.
        os.replace(chemin_temporaire, chemin)


# ─── Téléchargement en flux ────────────────────────────────────────────────────


def telecharger_en_flux(
    session: requests.Session,
    url: str,
    destination: Path,
    *,
    timeout: float = DELAI_ATTENTE_SECONDES_DEFAUT,
    taille_bloc: int = TAILLE_BLOC_OCTETS_DEFAUT,
    sur_progression: Callable[[int], None] | None = None,
    intervalle_progression_secondes: float = 10.0,
) -> None:
    """Télécharge `url` en flux vers `destination`, avec écriture atomique.

    Le statut HTTP est vérifié (`raise_for_status`) avant l'ouverture du
    fichier temporaire : une réponse en erreur (404, 500...) ne crée donc
    jamais de fichier `.part`. Toute exception levée pendant l'écriture
    (coupure réseau en cours de flux) traverse `ecriture_atomique`, qui
    supprime le fichier partiel avant de la propager : l'appelant reste seul
    responsable de traduire cette exception en erreur de son domaine.

    `sur_progression`, optionnel, reçoit le nombre total d'octets déjà écrits,
    au rythme maximal `intervalle_progression_secondes` (jamais plus souvent,
    quelle que soit la taille des blocs reçus du réseau). Sans lui — le cas
    par défaut, celui de Parcoursup, quelques dizaines de Mo téléchargés en
    quelques secondes — aucun décompte n'est effectué et le comportement est
    identique à celui d'avant l'ajout de ce paramètre. La primitive ne décide
    ni du format du message ni de sa destination (journal, métrique...),
    seulement de la cadence à laquelle l'appelant est notifié : c'est le seul
    élément réellement répété entre connecteurs, le contenu du message reste
    propre à chacun (le nom du fichier Sirene n'a pas de sens ici).

    Raises:
        ErreurFluxVide: la réponse a un statut de succès mais ne contient
            aucun octet. Aucun fichier n'est laissé sur le disque dans ce
            cas : l'exception est levée à l'intérieur de l'écriture atomique,
            qui supprime le `.part` avant de la propager.
    """
    with session.get(url, stream=True, timeout=timeout) as reponse:
        reponse.raise_for_status()
        octets_recus = 0
        dernier_appel = time.monotonic()
        with ecriture_atomique(destination, mode="wb") as flux_sortie:
            for bloc in reponse.iter_content(chunk_size=taille_bloc):
                if not bloc:
                    continue
                flux_sortie.write(bloc)
                octets_recus += len(bloc)
                if sur_progression is None:
                    continue
                maintenant = time.monotonic()
                if maintenant - dernier_appel >= intervalle_progression_secondes:
                    sur_progression(octets_recus)
                    dernier_appel = maintenant
            if octets_recus == 0:
                raise ErreurFluxVide(
                    f"Réponse vide (0 octet) reçue depuis {url} : le serveur a répondu "
                    "avec succès mais sans contenu."
                )


# ─── Empreinte et contrôle d'intégrité ─────────────────────────────────────────


def empreinte_sha256(chemin: Path, taille_bloc: int = TAILLE_BLOC_OCTETS_DEFAUT) -> str:
    """Empreinte du contenu d'un fichier, calculée par blocs pour rester sobre en mémoire."""
    hachage = hashlib.sha256()
    with chemin.open("rb") as flux:
        for bloc in iter(lambda: flux.read(taille_bloc), b""):
            hachage.update(bloc)
    return hachage.hexdigest()


def fichier_intact(chemin: Path, entree_manifeste: dict[str, object] | None) -> bool:
    """Un fichier est considéré intact s'il existe, n'est pas vide, et correspond au manifeste.

    Sans entrée de manifeste (première introduction du contrôle, ou manifeste
    perdu), la seule présence du fichier ne suffit pas à conclure à son
    intégrité : on retélécharge par prudence plutôt que de faire confiance à
    un fichier dont on ne peut pas prouver la provenance.
    """
    if not chemin.exists() or chemin.stat().st_size == 0:
        return False
    if entree_manifeste is None:
        return False
    return empreinte_sha256(chemin) == entree_manifeste.get("empreinte_sha256")


# ─── Manifeste de traçabilité ───────────────────────────────────────────────────


def lire_manifeste(chemin: Path) -> dict[str, dict[str, object]]:
    """Lit un manifeste JSON. Absent ou corrompu : traité comme vide, jamais une exception.

    Le manifeste est un cache reconstructible — c'est l'empreinte SHA-256 de
    chaque fichier, pas le manifeste lui-même, qui garantit l'intégrité réelle
    des données. Il ne doit donc jamais bloquer la chaîne. Mais une corruption
    qui fait perdre silencieusement la trace des entrées déjà enregistrées est
    un incident, pas un détail : on le rend visible (log au niveau ERREUR) et
    on met le fichier corrompu en quarantaine plutôt que de le laisser en
    place pour qu'une prochaine écriture l'écrase sans que personne ne l'ait
    su.
    """
    if not chemin.exists():
        return {}
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erreur:
        _mettre_en_quarantaine(chemin, erreur)
        return {}


def _mettre_en_quarantaine(chemin: Path, erreur: Exception) -> None:
    """Déplace un manifeste illisible vers un nom horodaté, et journalise la perte.

    Le déplacement (plutôt qu'une copie suivie d'une suppression) libère le
    nom `chemin` pour la prochaine écriture, tout en conservant le contenu
    fautif à un emplacement stable pour analyse a posteriori — un opérateur
    qui consulte les journaux retrouve immédiatement le fichier incriminé.
    """
    horodatage = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    chemin_quarantaine = chemin.with_name(f"{chemin.name}.corrompu-{horodatage}")
    try:
        os.replace(chemin, chemin_quarantaine)
        destination_journal = str(chemin_quarantaine)
    except OSError as erreur_deplacement:
        # Le déplacement lui-même peut échouer (droits, disque plein) : on ne
        # laisse pas cette erreur secondaire masquer l'incident primaire, on
        # la rapporte comme information complémentaire dans le même message.
        destination_journal = f"impossible à mettre en quarantaine ({erreur_deplacement})"
    LOGGER.error(
        "Manifeste %s illisible (%s) : traité comme vide, la traçabilité des "
        "entrées qu'il portait est perdue de l'index actif. Fichier original "
        "conservé sous %s pour analyse.",
        chemin,
        erreur,
        destination_journal,
    )


def ecrire_manifeste(chemin: Path, manifeste: dict[str, dict[str, object]]) -> None:
    """Écrit le manifeste par fichier temporaire puis renommage, comme tout autre contenu.

    Le manifeste porte la preuve de traçabilité (identifiant, URL, date,
    taille, empreinte) : il ne doit pas plus que les données rester à moitié
    écrit.
    """
    with ecriture_atomique(chemin, mode="w") as flux:
        flux.write(json.dumps(manifeste, indent=2, ensure_ascii=False, sort_keys=True))
