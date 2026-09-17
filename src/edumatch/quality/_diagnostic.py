"""Vocabulaire commun des contrôles qualité : anomalie, gravité, rapport.

Ce module ne connaît aucune source précise (ni Parcoursup, ni Sirene, ni
référentiels) : il porte uniquement la mécanique répétée par tout contrôle,
sur le modèle de `edumatch.ingestion._flux`, qui joue le même rôle pour les
connecteurs.

Deux gravités, et deux seulement :

- **BLOQUANT** — la donnée ne doit pas atteindre la couche suivante en
  l'état : un schéma rompu, une valeur impossible, une complétude qui
  s'effondre sans explication. Lever `ErreurQualiteBloquante` interrompt la
  chaîne.
- **AVERTISSEMENT** — la donnée reste exploitable, mais un humain devrait le
  savoir : une source qui vieillit, une réserve déjà documentée par ailleurs
  (ADR 0013) que le contrôle ne fait que constater à nouveau. Un
  avertissement est journalisé, jamais silencieux, mais ne bloque rien.

Un contrôle qui journalise sans jamais bloquer laisse une donnée corrompue
atteindre le modèle — les données se valident comme du code : c'est pourquoi
`RapportControle.lever_si_bloquant` est la sortie normale de tout contrôle
appelé depuis `edumatch.quality.run`, jamais un simple retour de valeur que
l'appelant pourrait ignorer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from edumatch.ingestion._flux import ErreurDefinitive


class Gravite(str, Enum):
    """Deux niveaux seulement : le tiers est le début d'une échelle qu'on ne veut pas."""

    BLOQUANT = "bloquant"
    AVERTISSEMENT = "avertissement"


@dataclass(frozen=True)
class Anomalie:
    """Une violation constatée par un contrôle, sur une source et une famille données.

    `famille` vaut l'une de « schema », « completude », « coherence » ou
    « fraicheur » (les quatre familles retenues pour les contrôles qualité) : elle sert à
    regrouper le rapport à l'affichage, pas à la logique de blocage, qui ne
    dépend que de `gravite`.
    """

    source: str
    famille: str
    gravite: Gravite
    message: str

    def formatee(self) -> str:
        """Une ligne lisible dans un journal ou une sortie de terminal."""
        return f"[{self.gravite.value}] {self.source}/{self.famille} — {self.message}"


class ErreurControleQualite(RuntimeError):
    """Base commune aux échecs des contrôles qualité, quelle que soit la source.

    Conservée pour qu'un appelant qui ne distingue pas encore les gravités
    puisse écrire `except ErreurControleQualite`, sur le même principe que
    `ErreurTelechargementParcoursup` et les autres bases de connecteur.
    """


class ErreurQualiteBloquante(ErreurControleQualite, ErreurDefinitive):
    """Au moins une anomalie bloquante a été détectée : la chaîne s'arrête.

    Rangée du côté définitif du vocabulaire commun (`_flux.ErreurDefinitive`),
    pas transitoire : retenter le même contrôle sur les mêmes données produit
    la même anomalie. Ce n'est pas un incident réseau ni une indisponibilité
    passagère — c'est la donnée elle-même qui viole son contrat. Seule une
    nouvelle collecte, ou une correction du contrôle s'il s'avère trop
    strict, peut changer l'issue. Un futur DAG peut donc traiter tout
    échec de ce module comme il traite un échec de connecteur : alerter un
    humain, ne jamais retenter en boucle.
    """


@dataclass(frozen=True)
class RapportControle:
    """Le résultat complet d'un contrôle sur une source : toutes les anomalies constatées."""

    source: str
    anomalies: tuple[Anomalie, ...]

    @property
    def bloquantes(self) -> tuple[Anomalie, ...]:
        return tuple(a for a in self.anomalies if a.gravite is Gravite.BLOQUANT)

    @property
    def avertissements(self) -> tuple[Anomalie, ...]:
        return tuple(a for a in self.anomalies if a.gravite is Gravite.AVERTISSEMENT)

    @property
    def est_bloquant(self) -> bool:
        return bool(self.bloquantes)

    def lever_si_bloquant(self) -> None:
        """Interrompt la chaîne si une anomalie bloquante a été détectée.

        C'est la seule façon dont ce module doit être appelé en production
        (`edumatch.quality.run`) : un appelant qui se contenterait
        d'inspecter `est_bloquant` sans appeler cette méthode pourrait, par
        oubli, laisser passer une donnée corrompue — exactement le défaut
        qu'un contrôle qui journalise sans bloquer introduit ailleurs.
        """
        if not self.bloquantes:
            return
        detail = "\n".join(a.formatee() for a in self.bloquantes)
        raise ErreurQualiteBloquante(
            f"{len(self.bloquantes)} anomalie(s) bloquante(s) sur {self.source} :\n{detail}"
        )


def fusionner(source: str, *rapports: RapportControle) -> RapportControle:
    """Combine plusieurs rapports partiels (un par famille de contrôle) en un seul.

    Chaque fonction de contrôle (`controler_schema`, `controler_completude`...)
    produit son propre `RapportControle` restreint à sa famille ; cette
    fonction les recompose en un rapport unique par source, celui que
    `edumatch.quality.run` agrège à son tour sur l'ensemble du pipeline.
    """
    toutes = tuple(a for r in rapports for a in r.anomalies)
    return RapportControle(source=source, anomalies=toutes)
