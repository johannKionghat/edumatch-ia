"""Outillage de l'exercice des droits des personnes (T8) — articles 12 à 22 du RGPD.

`docs/registres.html#t8` déclare ce traitement « à construire » : une procédure de
réception des demandes existe dans le principe, mais aucun outil ne permettait jusqu'ici
de retrouver, exporter ou effacer réellement une trace. Ce module ferme cet écart pour les
deux journaux du dépôt qui portent une donnée personnelle — le journal d'inférence (T5,
`api/audit.py`) et le journal des décisions du conseiller (T6, `api/feedback_store.py`).

## Trois opérations, sur un identifiant

Une personne qui exerce un droit ne connaît jamais le contenu interne d'un journal ; elle
fournit un identifiant de requête (`identifiant_audit`, `identifiant_execution` ou
`identifiant_feedback`, selon ce qui lui a été communiqué) ou, si la ligne a déjà été
purgée, le jeton pseudonymisé qui l'a remplacé (`audit_purge.py`). `CHAMPS_IDENTIFIANTS`
énumère, pour chaque journal, les champs contre lesquels une correspondance est
recherchée — aucune autre heuristique de recherche n'est tentée : un identifiant
approximatif ne doit jamais renvoyer une trace qui n'est pas la bonne.

- **retrouver** : liste les lignes correspondantes, sans rien modifier.
- **exporter** : produit un texte JSON ou CSV des lignes correspondantes, sans rien
  modifier — le format de portabilité que l'article 20 du RGPD exige.
- **effacer** : retire les lignes correspondantes du journal. `simulation=True` par
  défaut, comme `audit_purge.purger` : un effacement est une opération irréversible, elle
  ne doit jamais s'exécuter à l'insu de qui l'invoque.

## Délai de réponse

Le RGPD impose une réponse dans un délai d'un mois à compter de la réception de la
demande, prorogeable de deux mois pour une demande complexe (article 12.3). Ce module ne
planifie ni ne chronomètre rien : il rend chaque opération exécutable en une commande,
pour que ce délai d'un mois reste consommé par la qualification humaine de la demande
(vérifier l'identité du demandeur, décider de la portée) et non par l'absence d'outil.

## La trace d'exécution ne contient jamais de donnée personnelle

Chaque appel — quelle que soit l'opération, simulée ou réelle — ajoute une ligne à
`processed/audit/droits.jsonl` : horodatage, opération, journal concerné, nombre de
lignes concernées. Jamais l'identifiant recherché, jamais le contenu d'une ligne : cette
trace prouve qu'une demande a été traitée, elle ne permet pas de reconstituer ce qu'elle
contenait. C'est la même discipline que `audit_purge.py` applique à `purges.jsonl`.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from edumatch.api.audit_purge import chemins_audit, chemins_supervision
from edumatch.config import Settings, get_settings

LOGGER = logging.getLogger(__name__)

NOM_FICHIER_TRACE = "droits.jsonl"
SOUS_DOSSIER_TRACE = "audit"

MODE_SIMULATION = "simulation"
MODE_REEL = "reel"

DELAI_REPONSE_JOURS = 30
"""Délai maximal de réponse à une demande d'exercice des droits (article 12.3 du RGPD),
prorogeable de deux mois pour une demande complexe. Valeur documentaire : ce module ne
la fait pas respecter automatiquement, voir le docstring du module."""

JournalCible = Literal["inference", "supervision"]

CHAMPS_IDENTIFIANTS: dict[JournalCible, tuple[str, ...]] = {
    "inference": ("identifiant_audit", "identifiant_execution"),
    "supervision": ("identifiant_feedback", "identifiant_conseiller"),
}


@dataclass(frozen=True)
class TraceExecution:
    """Une ligne de `droits.jsonl` — jamais de donnée personnelle, voir le docstring du
    module."""

    horodatage: str
    operation: str
    journal: str
    lignes_concernees: int


def _chemin_journal(settings: Settings, journal: JournalCible) -> Path:
    if journal == "inference":
        return chemins_audit(settings).journal
    return chemins_supervision(settings).journal


def _chemin_trace(settings: Settings) -> Path:
    return settings.processed_dir / SOUS_DOSSIER_TRACE / NOM_FICHIER_TRACE


def _ecrire_texte_atomique(chemin: Path, contenu: str) -> None:
    """Même principe qu'`audit_purge._ecrire_texte_atomique` : un fichier `.part` renommé
    une fois complet, jamais de fichier tronqué visible sous son nom définitif."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".part")
    temporaire.write_text(contenu, encoding="utf-8")
    os.replace(temporaire, chemin)


def _lire_lignes(chemin: Path) -> list[dict[str, Any]]:
    if not chemin.exists():
        return []
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    return [json.loads(ligne) for ligne in lignes if ligne.strip()]


def _correspond(enregistrement: dict[str, Any], journal: JournalCible, identifiant: str) -> bool:
    return any(enregistrement.get(champ) == identifiant for champ in CHAMPS_IDENTIFIANTS[journal])


def _journaliser_trace(settings: Settings, *, operation: str, journal: JournalCible, lignes_concernees: int) -> None:
    trace = TraceExecution(
        horodatage=datetime.now(UTC).isoformat(),
        operation=operation,
        journal=journal,
        lignes_concernees=lignes_concernees,
    )
    chemin = _chemin_trace(settings)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8") as flux:
        flux.write(json.dumps(asdict(trace), ensure_ascii=False) + "\n")
    LOGGER.info(
        "Exercice des droits : %s sur le journal %s, %s ligne(s) concernée(s).",
        operation,
        journal,
        lignes_concernees,
    )


def retrouver(settings: Settings, *, journal: JournalCible, identifiant: str) -> list[dict[str, Any]]:
    """Retrouve les lignes du journal désigné dont un champ identifiant correspond à
    `identifiant`. Ne modifie jamais rien."""
    lignes = [
        ligne
        for ligne in _lire_lignes(_chemin_journal(settings, journal))
        if _correspond(ligne, journal, identifiant)
    ]
    _journaliser_trace(settings, operation="retrouver", journal=journal, lignes_concernees=len(lignes))
    return lignes


def exporter(settings: Settings, *, journal: JournalCible, identifiant: str, format: str = "json") -> str:
    """Exporte, sous forme de texte, les lignes correspondant à `identifiant`.

    `format='json'` (par défaut) ou `'csv'`. Ne modifie jamais rien. Lève `ValueError` sur
    tout autre format — une erreur définitive plutôt qu'un export silencieusement vide,
    conforme au vocabulaire d'erreur du dépôt (`edumatch.ingestion._flux`).
    """
    if format not in ("json", "csv"):
        raise ValueError(f"Format d'export non supporté : {format!r} (attendu : 'json' ou 'csv').")

    lignes = [
        ligne
        for ligne in _lire_lignes(_chemin_journal(settings, journal))
        if _correspond(ligne, journal, identifiant)
    ]

    if format == "json":
        contenu = json.dumps(lignes, indent=2, ensure_ascii=False)
    else:
        if not lignes:
            contenu = ""
        else:
            colonnes = sorted({cle for ligne in lignes for cle in ligne})
            tampon = io.StringIO()
            ecrivain = csv.DictWriter(tampon, fieldnames=colonnes)
            ecrivain.writeheader()
            for ligne in lignes:
                ecrivain.writerow(
                    {
                        cle: json.dumps(valeur, ensure_ascii=False) if isinstance(valeur, (dict, list)) else valeur
                        for cle, valeur in ligne.items()
                    }
                )
            contenu = tampon.getvalue()

    _journaliser_trace(settings, operation="exporter", journal=journal, lignes_concernees=len(lignes))
    return contenu


def effacer(settings: Settings, *, journal: JournalCible, identifiant: str, simulation: bool = True) -> int:
    """Efface du journal désigné les lignes correspondant à `identifiant`.

    `simulation=True` par défaut : rapporte ce qui serait effacé sans rien modifier ;
    l'effacement réel est un choix explicite de l'appelant (même prudence que
    `audit_purge.purger`). Idempotente : une seconde exécution ne trouve plus rien à
    effacer et rapporte zéro ligne concernée.
    """
    chemin = _chemin_journal(settings, journal)
    lignes = _lire_lignes(chemin)
    a_conserver = [ligne for ligne in lignes if not _correspond(ligne, journal, identifiant)]
    nb_effacees = len(lignes) - len(a_conserver)

    if not simulation:
        _ecrire_texte_atomique(
            chemin, "".join(json.dumps(ligne, ensure_ascii=False) + "\n" for ligne in a_conserver)
        )

    operation = "effacer" if not simulation else "effacer_simulation"
    _journaliser_trace(settings, operation=operation, journal=journal, lignes_concernees=nb_effacees)
    return nb_effacees


def _analyser_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    analyseur = argparse.ArgumentParser(
        description="Exercice des droits des personnes (T8) : retrouver, exporter ou effacer les traces "
        "liées à un identifiant, dans le journal d'inférence ou de supervision."
    )
    sous_analyseurs = analyseur.add_subparsers(dest="operation", required=True)

    commun = argparse.ArgumentParser(add_help=False)
    commun.add_argument("--journal", choices=["inference", "supervision"], required=True)
    commun.add_argument("--identifiant", required=True, help="Identifiant de requête ou jeton pseudonymisé.")

    sous_analyseurs.add_parser("retrouver", parents=[commun])

    analyseur_exporter = sous_analyseurs.add_parser("exporter", parents=[commun])
    analyseur_exporter.add_argument("--format", choices=["json", "csv"], default="json")

    analyseur_effacer = sous_analyseurs.add_parser("effacer", parents=[commun])
    analyseur_effacer.add_argument(
        "--appliquer",
        action="store_true",
        help="Efface réellement les lignes. Sans cette option, simulation seule : rien n'est modifié sur disque.",
    )

    return analyseur.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    arguments = _analyser_arguments(argv)
    settings = get_settings()

    if arguments.operation == "retrouver":
        resultat = retrouver(settings, journal=arguments.journal, identifiant=arguments.identifiant)
        print(json.dumps(resultat, indent=2, ensure_ascii=False))
    elif arguments.operation == "exporter":
        print(
            exporter(
                settings, journal=arguments.journal, identifiant=arguments.identifiant, format=arguments.format
            )
        )
    elif arguments.operation == "effacer":
        nb_effacees = effacer(
            settings, journal=arguments.journal, identifiant=arguments.identifiant, simulation=not arguments.appliquer
        )
        sortie = {
            "mode": MODE_REEL if arguments.appliquer else MODE_SIMULATION,
            "journal": arguments.journal,
            "lignes_effacees": nb_effacees,
        }
        print(json.dumps(sortie, ensure_ascii=False))


if __name__ == "__main__":
    main()
