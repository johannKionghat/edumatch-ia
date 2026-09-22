"""Libellés des départements de la session courante, pour la liste déroulante de l'écran.

La liste des départements proposés au conseiller vient du catalogue lui-même (`dep`, les codes
réellement présents) : elle ne peut pas proposer un département où aucune formation n'existe.
Ce module ne fournit que le **libellé** à afficher à côté du code, extrait de la couche silver.

## Pourquoi la session courante seule, et pas `dim_territoire`

La dimension territoire de l'entrepôt rassemble toutes les sessions, et le fichier source de la
session 2021 libelle le département 09 « Ardennes » (c'est l'Ariège ; les Ardennes sont le 08) :
six villes de l'Ariège y portent ce libellé fautif. En session 2025, chaque code n'a qu'un
libellé, et c'est le bon. Restreindre à la session du catalogue évite de montrer un libellé qu'une
autre session a corrompu. Si une session future portait deux libellés pour un même code,
`extraire_libelles` s'arrête plutôt que d'en choisir un au hasard.

## L'artefact

`processed/matching/departements_libelles.parquet` (`make departements`), à côté du catalogue de
prédictions : en production, le conteneur d'initialisation synchronise déjà tout `matching/`
depuis le stockage objet, aucun manifeste n'est à modifier. Absent, ou d'une autre session que
le catalogue, l'API sert les codes seuls et le dit (`libelles_disponibles: false`).
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from edumatch.config import Settings, get_settings
from edumatch.features import build

LOGGER = logging.getLogger(__name__)

SOUS_DOSSIER = "matching"
NOM_FICHIER = "departements_libelles.parquet"


class ErreurLibellesDepartements(RuntimeError):
    """Les libellés ne peuvent pas être extraits sans ambiguïté."""


def chemin_libelles(settings: Settings) -> Path:
    return settings.processed_dir / SOUS_DOSSIER / NOM_FICHIER


def extraire_libelles(silver: pd.DataFrame, session: int) -> pd.DataFrame:
    """Une ligne par code de département de `session` : `session`, `dep`, `dep_lib`."""
    lignes = silver.loc[silver["session"] == session, ["dep", "dep_lib"]].dropna().drop_duplicates()
    if lignes.empty:
        raise ErreurLibellesDepartements(
            f"Aucune ligne de la session {session} dans la couche silver."
        )
    ambigus = lignes.groupby("dep")["dep_lib"].nunique()
    ambigus = ambigus[ambigus > 1]
    if not ambigus.empty:
        raise ErreurLibellesDepartements(
            f"Session {session} : plusieurs libellés pour les départements {sorted(ambigus.index)}."
        )
    libelles = lignes.sort_values("dep").reset_index(drop=True)
    libelles.insert(0, "session", session)
    return libelles


def ecrire_libelles(settings: Settings | None = None) -> Path:
    """Écrit l'artefact pour la session de test (celle du catalogue), de façon atomique."""
    settings = settings or get_settings()
    session = settings.modele.split.test[0]
    silver = pd.read_parquet(
        settings.interim_dir / build.SOUS_DOSSIER / build.NOM_FICHIER_SILVER,
        columns=["session", "dep", "dep_lib"],
    )
    libelles = extraire_libelles(silver, session)
    destination = chemin_libelles(settings)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partiel = destination.with_suffix(".parquet.part")
    libelles.to_parquet(partiel, index=False)
    partiel.replace(destination)
    LOGGER.info(
        "%d libellés de départements (session %d) -> %s", len(libelles), session, destination
    )
    return destination


def charger_libelles(settings: Settings, session: int) -> dict[str, str]:
    """Code -> libellé, ou un dictionnaire vide si l'artefact manque ou date d'une autre session."""
    chemin = chemin_libelles(settings)
    if not chemin.exists():
        LOGGER.warning(
            "Libellés de départements absents (%s) : liste servie en codes seuls.", chemin.name
        )
        return {}
    libelles = pd.read_parquet(chemin)
    sessions = set(libelles["session"].unique())
    if sessions != {session}:
        LOGGER.warning(
            "Libellés de départements de la session %s, catalogue de la session %d : codes seuls.",
            sorted(sessions),
            session,
        )
        return {}
    return dict(zip(libelles["dep"].astype(str), libelles["dep_lib"].astype(str), strict=True))


def _cle_tri(code: str) -> tuple[int, float]:
    """Ordre administratif : 01 à 19, 2A, 2B, 21 à 95, puis l'outre-mer (971…) et 99."""
    corse = {"2A": 20.1, "2B": 20.2}
    if code == "99":  # établissements à l'étranger, en dernier
        return (2, 0.0)
    if code in corse:
        return (0, corse[code])
    return (0, float(code)) if re.fullmatch(r"[0-9]+", code) else (1, 0.0)


def trier_codes(codes: Iterable[str]) -> list[str]:
    return sorted(set(codes), key=lambda c: (_cle_tri(c), c))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ecrire_libelles()
    return 0


if __name__ == "__main__":
    sys.exit(main())
