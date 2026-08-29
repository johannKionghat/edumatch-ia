"""Point d'entrée de la réconciliation Parcoursup (E15) : `make transform`.

Résout les chemins des millésimes réellement présents sur disque depuis la
configuration (`donnees.parcoursup.millesimes`, `Settings.raw_dir`), délègue
la réconciliation à `reconciliation.py`, écrit le résultat dans
`data/interim/parcoursup/silver.parquet` et journalise la couverture
mesurée. Ne bloque jamais silencieusement : une erreur de réconciliation
(`ErreurReconciliationParcoursup`) traverse ce module sans être avalée.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from edumatch.config import Settings, get_settings
from edumatch.transform.reconciliation import RapportReconciliation, ecrire_silver, reconcilier

LOGGER = logging.getLogger(__name__)

NOM_FICHIER_SILVER = "silver.parquet"


def _chemins_disponibles(settings: Settings) -> dict[int, Path]:
    """Les millésimes configurés dont le fichier bronze existe réellement sur disque.

    Un millésime configuré mais pas encore téléchargé n'est pas une erreur de
    ce module : l'ingestion (E05) est responsable de la présence des
    fichiers, pas la transformation. Silver reflète ce qui est disponible.
    """
    dossier = settings.raw_dir / "parcoursup"
    chemins = {
        millesime: dossier / f"parcoursup_{millesime}.csv"
        for millesime in settings.donnees.parcoursup.millesimes
    }
    return {millesime: chemin for millesime, chemin in chemins.items() if chemin.exists()}


def executer(settings: Settings | None = None) -> RapportReconciliation:
    """Réconcilie les millésimes disponibles et écrit la table silver. Retourne le rapport."""
    settings = settings or get_settings()
    chemins = _chemins_disponibles(settings)
    table, rapport = reconcilier(chemins, settings.modele.variables)
    destination = settings.interim_dir / "parcoursup" / NOM_FICHIER_SILVER
    ecrire_silver(table, destination)
    return rapport


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rapport = executer()
    LOGGER.info("Réconciliation Parcoursup (bronze -> silver) terminée.\n%s", rapport.resume())
    return 0


if __name__ == "__main__":
    sys.exit(main())
