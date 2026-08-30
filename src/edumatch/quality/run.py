"""Point d'entrée des contrôles qualité (E14) : `make quality` ou `python -m edumatch.quality.run`.

Contrôle les trois sources — Parcoursup, Sirene, référentiels — sur les
fichiers réellement présents dans `data/raw/` et `data/external/`, agrège
les anomalies, journalise les avertissements et **bloque** au premier
ensemble d'anomalies bloquantes rencontré : une chaîne qui journalise sans
jamais interrompre laisserait une donnée corrompue atteindre `dbt` (E15) et,
de là, le modèle : les données se valident comme du code.

`ErreurQualiteBloquante` (voir `_diagnostic.py`) est volontairement rangée
du côté définitif du vocabulaire commun d'erreurs (`ingestion._flux`) : un
futur DAG Airflow (E33) qui capte `ErreurDefinitive` sur cette tâche sait
qu'il doit alerter un humain, pas retenter — retenter ne change rien tant
que la donnée ou le contrôle n'ont pas été corrigés.
"""

from __future__ import annotations

import logging
import sys

from edumatch.config import Settings, get_settings
from edumatch.quality import parcoursup, referentiels, sirene
from edumatch.quality._diagnostic import ErreurQualiteBloquante, RapportControle, fusionner

LOGGER = logging.getLogger(__name__)


def executer(settings: Settings | None = None) -> RapportControle:
    """Exécute les trois contrôles de source et retourne le rapport agrégé, sans lever.

    Séparée de `main()` pour que l'orchestration future (E33) puisse
    inspecter le rapport avant de décider quoi faire de chaque anomalie, sans
    dépendre du comportement `sys.exit` de ce module.
    """
    settings = settings or get_settings()
    rapport = fusionner(
        "pipeline",
        parcoursup.controler_tous(settings),
        sirene.controler_tous(settings),
        referentiels.controler_tous(settings),
    )
    for anomalie in rapport.avertissements:
        LOGGER.warning(anomalie.formatee())
    return rapport


def main() -> int:
    """Exécute les contrôles et bloque le processus appelant en cas d'anomalie bloquante.

    Code de sortie non nul sur blocage : c'est ce qu'un orchestrateur (make,
    Airflow, CI) sait déjà interpréter comme un échec de tâche, sans avoir à
    connaître le vocabulaire d'erreur interne de ce module.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rapport = executer()
    try:
        rapport.lever_si_bloquant()
    except ErreurQualiteBloquante as erreur:
        LOGGER.error(str(erreur))
        return 1
    LOGGER.info(
        "Contrôles qualité passés : %d avertissement(s), aucune anomalie bloquante.",
        len(rapport.avertissements),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
