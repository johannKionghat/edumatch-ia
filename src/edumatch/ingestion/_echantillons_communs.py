"""Primitives partagées par `echantillons.py` (Parcoursup, Sirene) et `echantillons_referentiels.py`.

Même raison de séparation que `_referentiels_communs.py` côté ingestion, pas
une question de longueur de fichier prise isolément : `echantillons.py` a
besoin d'orchestrer `echantillons_referentiels.py` dans
`generer_tous_les_echantillons`, et ce dernier a besoin des primitives
(`EchantillonResultat`, l'échantillonnage systématique, la lecture et
l'écriture CSV, l'empreinte, la lecture d'un manifeste de collecte) qui
vivaient à l'origine dans `echantillons.py`. Les deux imports croisés
créeraient un cycle si ces primitives restaient définies après le point
d'import dans l'un des deux modules — ce module tiers le rompt.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EchantillonResultat:
    """Trace de la génération d'un échantillon : source, méthode, taille, licence.

    `url`, `date_source` et `empreinte_sha256_source` décrivent le fichier
    d'origine (dans `data/raw/` ou `data/external/`, jamais versionnés) et
    sont recopiés depuis les manifestes de collecte — voir les fonctions
    `_provenance_*` de chaque module appelant. Sans eux, un lecteur du dépôt
    qui n'a que `data/samples/` ne peut pas remonter à la source publique
    exacte.
    """

    source: str
    chemin_source: Path
    chemin_sortie: Path
    lignes_source: int
    lignes_echantillon: int
    colonnes_retenues: list[str]
    colonnes_exclues: list[str]
    licence: str
    url: str
    date_source: str
    empreinte_sha256_source: str
    empreinte_sha256: str = field(repr=False)


def indices_systematiques(total: int, cible: int) -> list[int]:
    """Indices d'un échantillonnage systématique à pas fixe, sans graine.

    `pas = total // cible` : un index retenu tous les `pas`, à partir de 0.
    Toujours le même résultat pour un `total` et un `cible` donnés — c'est ce
    qui rend la génération reproductible sans avoir à fixer une graine
    aléatoire.
    """
    if total <= 0 or cible <= 0:
        return []
    pas = max(total // cible, 1)
    return list(range(0, total, pas))[:cible]


def empreinte(chemin: Path) -> str:
    hachage = sha256()
    with chemin.open("rb") as flux:
        for bloc in iter(lambda: flux.read(1 << 20), b""):
            hachage.update(bloc)
    return hachage.hexdigest()


def manifeste_source(chemin: Path) -> dict:
    """Lit un manifeste de collecte (`data/raw/**/manifeste.json`, `data/external/**/manifeste.json`).

    Ces manifestes ne sont jamais versionnés (voir `.gitignore`) : c'est
    précisément pourquoi leurs champs `url`, `date` et empreinte doivent être
    recopiés dans le manifeste des échantillons, seul document de lignage
    que le dépôt expose réellement à un lecteur.
    """
    if not chemin.exists():
        raise FileNotFoundError(
            f"Manifeste de collecte introuvable : {chemin}. "
            "Régénérer la source avant de produire les échantillons."
        )
    return json.loads(chemin.read_text(encoding="utf-8"))


def lire_csv(chemin: Path, encodage: str, delimiteur: str) -> tuple[list[str], list[list[str]]]:
    """Lit un CSV avec le module `csv` — jamais `wc -l` ni un simple `split("\\n")`.

    Nécessaire pour le RNCP : ses intitulés de certification contiennent des
    retours à la ligne à l'intérieur de champs entre guillemets. Un comptage
    par ligne physique s'y est déjà trompé une fois sur ce projet.
    """
    with chemin.open("r", encoding=encodage, newline="") as flux:
        lecteur = csv.reader(flux, delimiter=delimiteur)
        lignes = list(lecteur)
    if not lignes:
        return [], []
    return lignes[0], lignes[1:]


def ecrire_csv(chemin: Path, entete: list[str], lignes: list[list[str]], delimiteur: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8", newline="") as flux:
        ecrivain = csv.writer(flux, delimiter=delimiteur, quoting=csv.QUOTE_MINIMAL)
        ecrivain.writerow(entete)
        ecrivain.writerows(lignes)
