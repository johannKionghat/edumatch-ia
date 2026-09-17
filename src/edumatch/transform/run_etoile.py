"""Point d'entrée du modèle en étoile gold : `make gold`.

Lit `data/interim/parcoursup/silver.parquet`, délègue la construction
à `etoile.py`, écrit les cinq tables dans `data/processed/parcoursup/` et
journalise les volumétries mesurées, à confronter aux chiffres déjà connus
(440 030 cellules exploitables sur 2020-2025). N'avale jamais une erreur : un
échec de `edumatch.transform.etoile` (grain violé, dimension orpheline)
traverse ce module sans être masqué.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from edumatch.config import Settings, get_settings
from edumatch.transform.etoile import Etoile, RapportEtoile, construire_etoile, ecrire_etoile

LOGGER = logging.getLogger(__name__)

NOM_FICHIER_SILVER = "silver.parquet"
SOUS_DOSSIER = "parcoursup"


class ErreurEtoileSourceAbsente(RuntimeError):
    """Silver n'est pas encore disponible : la réconciliation doit tourner d'abord.

    Définitive au sens de `edumatch.ingestion._flux.ErreurDefinitive` : relancer
    ce module à l'identique ne fait pas apparaître le fichier manquant.
    """


def _chemin_silver(settings: Settings) -> Path:
    return settings.interim_dir / SOUS_DOSSIER / NOM_FICHIER_SILVER


def executer(settings: Settings | None = None) -> RapportEtoile:
    """Construit et écrit le modèle en étoile gold. Retourne le rapport de volumétrie."""
    settings = settings or get_settings()
    chemin = _chemin_silver(settings)
    if not chemin.exists():
        raise ErreurEtoileSourceAbsente(
            f"{chemin} introuvable : exécuter `make transform` avant `make gold`."
        )
    silver: pd.DataFrame = pq.read_table(chemin).to_pandas()
    etoile: Etoile = construire_etoile(silver)
    destination = settings.processed_dir / SOUS_DOSSIER
    ecrire_etoile(etoile, destination)
    return etoile.rapport


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rapport = executer()
    LOGGER.info("Modèle en étoile gold (silver -> gold) terminé.\n%s", rapport.resume())
    return 0


if __name__ == "__main__":
    sys.exit(main())
