"""Point d'entrée de l'agrégat Sirene commune x NAF (E17) : `make sirene-agregats`.

Résout la source (`data/raw/sirene/StockEtablissement.parquet`), la date de
référence de l'ancienneté (`date_publication_stock` du manifeste — jamais la
date du jour, pour que deux exécutions sur le même stock produisent le même
résultat) et le moteur de calcul, puis délègue à l'un des deux modules
d'agrégation :

- `execution.moteur_volume: local` (dev, staging) -> `sirene_agregats_polars`,
  le chemin réellement le plus rapide sur le volume actuel (mesuré :
  18,2 s contre 87,0 s pour Spark, voir le docstring de ce module) ;
- `execution.moteur_volume: cluster` (prod) -> `sirene_agregats` (PySpark),
  le chemin exigé par le critère « structures adaptées au volume » et la
  trajectoire de croissance du stock Sirene.

Ce choix n'est pas laissé à l'appelant : il suit exactement la même variable
de configuration que le reste du projet (`configs/dev.yaml`,
`configs/staging.yaml`, `configs/prod.yaml`), déjà utilisée nulle part
ailleurs à ce jour — c'est ce module qui la consomme pour la première fois.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from edumatch.config import Settings, get_settings
from edumatch.spark.definitions import FiltresSirene, resoudre_filtres
from edumatch.spark.sirene_agregats_polars import (
    NOM_FICHIER_SORTIE,
    RapportAgregation,
    agreger_polars,
    ecrire_agregats,
    rapport_depuis_agregat,
)

LOGGER = logging.getLogger(__name__)

NOM_FICHIER_SOURCE = "StockEtablissement.parquet"
SOUS_DOSSIER = "sirene"
NOM_FICHIER_MANIFESTE = "manifeste.json"


class ErreurSireneAgregatsSourceAbsente(RuntimeError):
    """`StockEtablissement.parquet` n'est pas encore téléchargé : l'étape E06 doit tourner d'abord.

    Définitive au sens de `edumatch.ingestion._flux.ErreurDefinitive` :
    relancer ce module à l'identique ne fait pas apparaître le fichier.
    """


class ErreurSireneAgregatsManifesteInvalide(RuntimeError):
    """Le manifeste Sirene n'a pas de `date_publication_stock` exploitable pour `StockEtablissement`.

    Définitive : sans cette date, l'ancienneté calculée ne serait pas
    reproductible d'une exécution à l'autre (voir le docstring de
    `agreger_polars`) — se rabattre sur `date.today()` masquerait le
    problème plutôt que de le signaler, ce que ce module refuse de faire.
    """


def _chemin_source(settings: Settings) -> Path:
    return settings.raw_dir / SOUS_DOSSIER / NOM_FICHIER_SOURCE


def _chemin_manifeste(settings: Settings) -> Path:
    return settings.raw_dir / SOUS_DOSSIER / NOM_FICHIER_MANIFESTE


def resoudre_date_reference(settings: Settings) -> date:
    """Lit `date_publication_stock` du manifeste Sirene pour `StockEtablissement` — jamais `date.today()`."""
    chemin = _chemin_manifeste(settings)
    if not chemin.exists():
        raise ErreurSireneAgregatsManifesteInvalide(
            f"{chemin} introuvable : exécuter `python -m edumatch.ingestion.sirene` (E06) avant "
            "cet agrégat, il écrit ce manifeste."
        )
    manifeste = json.loads(chemin.read_text(encoding="utf-8"))
    entree = manifeste.get("StockEtablissement")
    date_publication = entree.get("date_publication_stock") if entree else None
    if not date_publication:
        raise ErreurSireneAgregatsManifesteInvalide(
            f"{chemin} : aucune 'date_publication_stock' pour 'StockEtablissement'. Sans elle, "
            "l'ancienneté calculée par cet agrégat ne serait pas reproductible d'une exécution "
            "à l'autre sur le même stock."
        )
    return datetime.fromisoformat(date_publication).date()


def executer(settings: Settings | None = None) -> RapportAgregation:
    """Construit l'agrégat commune x NAF avec le moteur configuré, l'écrit, retourne le rapport."""
    settings = settings or get_settings()
    chemin_source = _chemin_source(settings)
    if not chemin_source.exists():
        raise ErreurSireneAgregatsSourceAbsente(
            f"{chemin_source} introuvable : exécuter `python -m edumatch.ingestion.sirene` "
            "(E06) avant `make sirene-agregats`."
        )

    date_reference = resoudre_date_reference(settings)
    filtres: FiltresSirene = resoudre_filtres(settings)
    destination = settings.processed_dir / SOUS_DOSSIER

    moteur = settings.execution.moteur_volume
    if moteur == "local":
        agregat = agreger_polars(chemin_source, date_reference, filtres)
        ecrire_agregats(agregat, destination)
        rapport = rapport_depuis_agregat(agregat, date_reference)
    elif moteur == "cluster":
        # Import différé : PySpark n'est nécessaire qu'à ce chemin, et
        # amorcer une JVM (voir le docstring de `sirene_agregats.py`, ~18 s
        # de démarrage mesurés) serait un coût inutile chaque fois que ce
        # module est importé en mode `local`, y compris par les tests.
        from edumatch.spark.sirene_agregats import (
            agreger,
            construire_session,
            ecrire_agregats_spark,
            lire_projection,
        )
        from edumatch.spark.sirene_agregats import rapport_depuis_agregat as rapport_spark

        spark = construire_session()
        try:
            df = lire_projection(spark, chemin_source)
            agregat_spark = agreger(df, date_reference, filtres)
            trame = ecrire_agregats_spark(agregat_spark, destination)
        finally:
            spark.stop()
        rapport = rapport_spark(trame, date_reference)
    else:
        raise ValueError(f"execution.moteur_volume={moteur!r} inattendu : 'local' ou 'cluster' seulement.")

    LOGGER.info("Agrégat écrit : %s", destination / NOM_FICHIER_SORTIE)
    return rapport


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rapport = executer()
    LOGGER.info("Agrégat Sirene commune x NAF (E17) terminé.\n%s", rapport.resume())
    return 0


if __name__ == "__main__":
    sys.exit(main())
