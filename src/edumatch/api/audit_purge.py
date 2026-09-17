"""Purge du journal d'inférence : exécute les trois paliers de conservation décidés par
la gouvernance — voir `audit.py` et `docs/sous-docs-projets/05-gouvernance/registre-traitements.md`
(T5), pour la conciliation entre le plancher de l'article 12 du règlement sur l'IA et le
plafond de l'article 5.1.e du RGPD.

## Pourquoi ce module existe

La gouvernance l'écrit noir sur blanc (`registre-traitements.md`, section
« Ce qui rend la durée vérifiable et non déclarative ») : une durée de
conservation qu'aucune tâche planifiée n'applique n'est pas une durée, c'est
une intention. Ce module est cette tâche. Il est idempotent — l'exécuter
deux fois à la même date produit le même état — et **prudent** : le mode par
défaut est une simulation qui rapporte ce qu'il ferait sans rien modifier ;
appliquer réellement la purge est un choix explicite (`--appliquer`).

## Les trois paliers, traduits en opérations sur le fichier

| Âge de la ligne | Opération | Ce qui change |
|---|---|---|
| < délai de pseudonymisation | Aucune | La ligne reste en clair |
| >= pseudonymisation, < agrégation | Pseudonymisation | `identifiant_execution` remplacé par un jeton aléatoire non réversible (aucune clé ne permet de revenir à l'original) ; `entrees` et `sortie` inchangées, `pseudonymise=True` |
| >= délai d'agrégation | Agrégation | La ligne disparaît du journal ; un compteur (session, type de baccalauréat, boursier) est incrémenté dans un fichier d'agrégats séparé |

Une ligne déjà pseudonymisée qui n'a pas encore atteint le délai
d'agrégation n'est pas retouchée : c'est ce qui rend l'opération idempotente
plutôt que de générer un nouveau jeton à chaque exécution, ce qui casserait
toute analyse déjà en cours sur le journal pseudonymisé.

## La purge elle-même est journalisée

Chaque exécution — simulée ou réelle — ajoute une ligne à
`processed/audit/purges.jsonl` : horodatage, mode, et les quatre compteurs.
Aucune donnée personnelle n'y figure, uniquement des décomptes. C'est ce qui
permet de répondre, en audit, à la question « la purge tourne-t-elle
vraiment ? » par un fichier plutôt que par une affirmation.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from edumatch.api.audit import NOM_FICHIER_JOURNAL, SOUS_DOSSIER_AUDIT
from edumatch.config import Settings, get_settings

LOGGER = logging.getLogger(__name__)

NOM_FICHIER_AGREGATS = "agregats.json"
NOM_FICHIER_PURGES = "purges.jsonl"

MODE_SIMULATION = "simulation"
MODE_REEL = "reel"


@dataclass(frozen=True)
class RapportPurge:
    """Le résultat d'une exécution de purge — jamais une ligne d'inférence, uniquement des
    décomptes (voir le docstring du module)."""

    horodatage_execution: str
    mode: str
    lignes_examinees: int
    lignes_conservees_en_clair: int
    lignes_pseudonymisees: int
    lignes_agregees: int
    chemin_journal: str


@dataclass(frozen=True)
class CheminsAudit:
    journal: Path
    agregats: Path
    purges: Path


def chemins_audit(settings: Settings) -> CheminsAudit:
    dossier = settings.processed_dir / SOUS_DOSSIER_AUDIT
    return CheminsAudit(
        journal=dossier / NOM_FICHIER_JOURNAL,
        agregats=dossier / NOM_FICHIER_AGREGATS,
        purges=dossier / NOM_FICHIER_PURGES,
    )


def _ecrire_texte_atomique(chemin: Path, contenu: str) -> None:
    """Un fichier `.part` renommé une fois complet — même principe que l'ingestion :
    jamais de fichier tronqué visible sous son nom définitif si la purge est interrompue."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".part")
    temporaire.write_text(contenu, encoding="utf-8")
    os.replace(temporaire, chemin)


def _lire_lignes_journal(chemin: Path) -> list[dict[str, Any]]:
    if not chemin.exists():
        return []
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    return [json.loads(ligne) for ligne in lignes if ligne.strip()]


def _cle_agregat(enregistrement: dict[str, Any]) -> str:
    entrees = enregistrement.get("entrees", {})
    session = entrees.get("session", "inconnue")
    type_bac = entrees.get("type_bac", "inconnu")
    boursier = entrees.get("boursier", "inconnu")
    return f"{session}|{type_bac}|{boursier}"


def _lire_agregats(chemin: Path) -> dict[str, dict[str, Any]]:
    if not chemin.exists():
        return {}
    return json.loads(chemin.read_text(encoding="utf-8"))


def _fusionner_agregats(existants: dict[str, dict[str, Any]], compteur: Counter) -> dict[str, dict[str, Any]]:
    fusion = {cle: dict(valeur) for cle, valeur in existants.items()}
    for cle, ajout in compteur.items():
        session, type_bac, boursier = cle.split("|")
        defaut = {"session": session, "type_bac": type_bac, "boursier": boursier, "nb_inferences": 0}
        bucket = fusion.setdefault(cle, defaut)
        bucket["nb_inferences"] += ajout
    return fusion


def _classer(
    enregistrement: dict[str, Any], *, age: timedelta, delai_pseudonymisation: timedelta, delai_agregation: timedelta
) -> str:
    """Renvoie le palier applicable à cette ligne : 'agreger', 'pseudonymiser', 'deja_pseudonymise'
    ou 'conserver'. Isolé de `purger` pour rester testable indépendamment de la lecture/écriture
    de fichiers."""
    if age >= delai_agregation:
        return "agreger"
    if age >= delai_pseudonymisation:
        return "deja_pseudonymise" if enregistrement.get("pseudonymise") else "pseudonymiser"
    return "conserver"


def purger(
    settings: Settings,
    *,
    maintenant: datetime | None = None,
    simulation: bool = True,
) -> RapportPurge:
    """Applique (ou simule) les trois paliers sur le journal d'inférence courant.

    `simulation=True` par défaut : une purge est une suppression, elle ne doit jamais s'exécuter
    à l'insu de qui l'invoque (voir le docstring du module). L'exécution réelle est un choix
    explicite de l'appelant, jamais un défaut.
    """
    maintenant = maintenant or datetime.now(UTC)
    delai_pseudonymisation = timedelta(days=settings.api.audit.delai_pseudonymisation_jours)
    delai_agregation = timedelta(days=settings.api.audit.delai_agregation_jours)
    chemins = chemins_audit(settings)

    lignes = _lire_lignes_journal(chemins.journal)
    lignes_conservees: list[dict[str, Any]] = []
    compteur_agregats: Counter = Counter()
    decomptes = Counter()

    for enregistrement in lignes:
        age = maintenant - datetime.fromisoformat(enregistrement["horodatage"])
        palier = _classer(
            enregistrement, age=age, delai_pseudonymisation=delai_pseudonymisation, delai_agregation=delai_agregation
        )
        if palier == "agreger":
            compteur_agregats[_cle_agregat(enregistrement)] += 1
            decomptes["agregees"] += 1
            continue
        if palier == "pseudonymiser":
            enregistrement = {**enregistrement, "identifiant_execution": str(uuid4()), "pseudonymise": True}
            decomptes["pseudonymisees"] += 1
        elif palier == "deja_pseudonymise":
            decomptes["pseudonymisees"] += 1
        else:
            decomptes["conservees_en_clair"] += 1
        lignes_conservees.append(enregistrement)

    rapport = RapportPurge(
        horodatage_execution=maintenant.isoformat(),
        mode=MODE_REEL if not simulation else MODE_SIMULATION,
        lignes_examinees=len(lignes),
        lignes_conservees_en_clair=decomptes["conservees_en_clair"],
        lignes_pseudonymisees=decomptes["pseudonymisees"],
        lignes_agregees=decomptes["agregees"],
        chemin_journal=str(chemins.journal),
    )

    if not simulation:
        _ecrire_texte_atomique(
            chemins.journal, "".join(json.dumps(ligne, ensure_ascii=False) + "\n" for ligne in lignes_conservees)
        )
        if compteur_agregats:
            agregats_fusionnes = _fusionner_agregats(_lire_agregats(chemins.agregats), compteur_agregats)
            _ecrire_texte_atomique(chemins.agregats, json.dumps(agregats_fusionnes, indent=2, ensure_ascii=False))

    chemins.purges.parent.mkdir(parents=True, exist_ok=True)
    with chemins.purges.open("a", encoding="utf-8") as flux:
        flux.write(json.dumps(asdict(rapport), ensure_ascii=False) + "\n")

    LOGGER.info(
        "Purge du journal d'audit (%s) : %s examinées, %s conservées en clair, %s pseudonymisées, %s agrégées.",
        rapport.mode,
        rapport.lignes_examinees,
        rapport.lignes_conservees_en_clair,
        rapport.lignes_pseudonymisees,
        rapport.lignes_agregees,
    )
    return rapport


def _analyser_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    analyseur = argparse.ArgumentParser(
        description="Applique les trois paliers de conservation du journal d'inférence (art. 12 / RGPD 5.1.e)."
    )
    analyseur.add_argument(
        "--appliquer",
        action="store_true",
        help="Écrit réellement la purge (journal réécrit, agrégats mis à jour). Sans cette option, "
        "simulation seule : rien n'est modifié sur disque.",
    )
    return analyseur.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    arguments = _analyser_arguments(argv)
    rapport = purger(get_settings(), simulation=not arguments.appliquer)
    print(json.dumps(asdict(rapport), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
