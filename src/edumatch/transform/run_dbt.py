"""Invocation du projet dbt de la couche silver Parcoursup (E15) : le lignage.

Point d'entrée distinct de `make transform` (`run.py`) : celui-ci est le
chemin de production, sans dépendance à dbt, un DataFrame pandas d'un bout à
l'autre. Celui-ci ne sert qu'à produire, une fois la réconciliation validée,
le graphe de dépendances que `dbt docs generate` construit automatiquement à
partir des sources et modèles déclarés (`dbt/models/`) — le lignage gratuit
du critère 3.8, sans mention manuelle à tenir à jour.

N'invente aucune commande : `subprocess` appelle `python -m dbt.cli.main`, le
point d'entrée documenté de dbt-core pour être invocable sans dépendre du
script `dbt.exe`, dont l'emplacement varie selon que l'installation est
globale ou `--user` (le cas rencontré sur le poste où cette étape a été
écrite : l'installation globale a échoué sur un droit refusé, `--user` a
réussi, et n'ajoute pas `dbt.exe` au `PATH` par défaut).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from edumatch.config import PROJECT_ROOT, Settings, get_settings

LOGGER = logging.getLogger(__name__)

DOSSIER_DBT = Path(__file__).resolve().parent / "dbt"


class ErreurDbt(RuntimeError):
    """Une commande dbt a échoué : le code de sortie du sous-processus est non nul.

    Définitive au sens de `edumatch.ingestion._flux.ErreurDefinitive` — un
    échec dbt (schéma de source introuvable, test rouge, erreur du modèle
    Python) ne se résout jamais en relançant la même commande à l'identique.
    """


def _environnement(settings: Settings) -> dict[str, str]:
    """Les seules variables que le projet dbt lit (`profiles.yml`, `_sources.yml`).

    `PYTHONPATH` est complété plutôt que remplacé : `import edumatch...` doit
    fonctionner à l'intérieur du modèle Python (`stg_parcoursup.py`), qui
    s'exécute dans le même interpréteur que ce sous-processus, pas dans celui
    qui a lancé ce module.
    """
    env = dict(os.environ)
    env["EDUMATCH_ENV"] = settings.env
    env["EDUMATCH_RAW_PARCOURSUP_DIR"] = str(settings.raw_dir / "parcoursup")
    env["EDUMATCH_DBT_DUCKDB_PATH"] = str(settings.interim_dir / "parcoursup" / "silver.duckdb")
    chemin_src = str(PROJECT_ROOT / "src")
    existant = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(p for p in (chemin_src, existant) if p)
    return env


def _executer_dbt(*commande: str, settings: Settings) -> None:
    arguments = [
        sys.executable,
        "-m",
        "dbt.cli.main",
        *commande,
        "--project-dir",
        str(DOSSIER_DBT),
        "--profiles-dir",
        str(DOSSIER_DBT),
    ]
    resultat = subprocess.run(arguments, env=_environnement(settings), cwd=DOSSIER_DBT)
    if resultat.returncode != 0:
        raise ErreurDbt(f"dbt {' '.join(commande)} a échoué (code {resultat.returncode}).")


def executer(settings: Settings | None = None) -> None:
    """Construit le modèle silver via dbt, le teste, puis génère la documentation (lignage)."""
    settings = settings or get_settings()
    (settings.interim_dir / "parcoursup").mkdir(parents=True, exist_ok=True)
    _executer_dbt("run", settings=settings)
    _executer_dbt("test", settings=settings)
    _executer_dbt("docs", "generate", settings=settings)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    executer()
    LOGGER.info("dbt run / test / docs generate terminés : voir %s", DOSSIER_DBT / "target")
    return 0


if __name__ == "__main__":
    sys.exit(main())
