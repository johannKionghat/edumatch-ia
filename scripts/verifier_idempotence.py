"""Vérification d'idempotence du pipeline (critère 3.6, ADR 0019, section « 3. Idempotence »).

Compare le **contenu** des sorties du pipeline avant et après une exécution
rejouée sans rien changer en amont — jamais leur empreinte binaire. Un fichier
Parquet réécrit par le même code, avec les mêmes données en entrée, n'est pas
garanti identique octet pour octet (métadonnées internes d'écriture,
compression, ordre de certains blocs) : ce n'est pas ce que « idempotent »
signifie ici. Ce qui compte, et ce que `pandas.testing.assert_frame_equal`
vérifie réellement, c'est que les mêmes lignes et les mêmes valeurs
ressortent — la même propriété que
`tests/integration/test_pipeline_enchainement.py::test_enchainement_silver_gold_variables_est_idempotent`
démontre déjà sur des échantillons, appliquée ici aux sorties réelles produites
sur l'instance de production.

Usage :
    PYTHONPATH=src python scripts/verifier_idempotence.py capturer
    # ... rejouer le ou les DAG concernés sans rien changer en amont ...
    PYTHONPATH=src python scripts/verifier_idempotence.py comparer

`capturer` copie l'état courant des quatre sorties suivies dans un répertoire
de référence horodaté, sous `EDUMATCH_DATA_ROOT/.idempotence/`. `comparer`
relit l'état courant, le compare au dernier instantané capturé, et échoue
bruyamment (code de sortie non nul, différences imprimées) au moindre écart —
jamais un succès supposé faute de comparaison.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from edumatch.config import Settings, get_settings  # noqa: E402

NOM_DOSSIER_CAPTURE = ".idempotence"

# Les quatre sorties dont l'ADR 0019 exige la comparaison de contenu : la
# chaîne Parcoursup au complet (silver, le fait, la table de variables) et
# l'agrégat Sirene — quel que soit le moteur (Polars ou Spark) qui l'a produit,
# l'ADR le précise explicitement. Chemins relatifs à `settings.data_root`,
# jamais en dur ailleurs que dans ce tuple : c'est la même convention que
# `edumatch.config.Settings` (raw_dir, interim_dir, processed_dir).
SORTIES_SUIVIES: dict[str, str] = {
    "silver_parcoursup": "interim/parcoursup/silver.parquet",
    "fait_admission": "processed/parcoursup/fait_admission.parquet",
    "variables": "processed/parcoursup/variables.parquet",
    "agregats_sirene": "processed/sirene/agregats_commune_naf.parquet",
}


def _dossier_capture(settings: Settings) -> Path:
    return settings.data_root / NOM_DOSSIER_CAPTURE


def capturer(settings: Settings) -> int:
    """Copie l'état courant de chaque sortie suivie dans le répertoire de référence.

    Une sortie absente (par exemple l'agrégat Sirene si ce DAG n'a pas encore
    tourné) est signalée, pas masquée : la comparaison qui suivra ne pourra
    porter que sur ce qui a été réellement capturé.
    """
    destination = _dossier_capture(settings)
    destination.mkdir(parents=True, exist_ok=True)
    manquantes: list[str] = []
    for nom, chemin_relatif in SORTIES_SUIVIES.items():
        source = settings.data_root / chemin_relatif
        if not source.exists():
            manquantes.append(chemin_relatif)
            continue
        shutil.copy2(source, destination / f"{nom}.parquet")
        print(f"[capture] {chemin_relatif} -> {destination / f'{nom}.parquet'}")

    if manquantes:
        print(
            "AVERTISSEMENT : sorties absentes, non capturées (le DAG correspondant "
            f"n'a peut-être pas encore tourné) : {', '.join(manquantes)}",
            file=sys.stderr,
        )
    if len(manquantes) == len(SORTIES_SUIVIES):
        print("ERREUR : aucune sortie à capturer. Rien n'a tourné ?", file=sys.stderr)
        return 1
    print(f"Capture terminée sous {destination}. Rejouer le pipeline, puis lancer 'comparer'.")
    return 0


def comparer(settings: Settings) -> int:
    """Compare le contenu courant de chaque sortie à sa capture de référence.

    Retourne un code non nul si une sortie diffère, si une capture est
    absente, ou si aucune capture n'a jamais été faite — jamais un succès par
    défaut faute de point de comparaison.
    """
    destination = _dossier_capture(settings)
    if not destination.exists():
        print(
            f"ERREUR : aucune capture sous {destination}. Lancer 'capturer' avant de rejouer le pipeline.",
            file=sys.stderr,
        )
        return 1

    en_echec: list[str] = []
    ignorees: list[str] = []
    for nom, chemin_relatif in SORTIES_SUIVIES.items():
        reference = destination / f"{nom}.parquet"
        actuel = settings.data_root / chemin_relatif
        if not reference.exists():
            ignorees.append(f"{chemin_relatif} (jamais capturé)")
            continue
        if not actuel.exists():
            en_echec.append(f"{chemin_relatif} : absent après la seconde exécution")
            continue
        table_reference = pd.read_parquet(reference)
        table_actuelle = pd.read_parquet(actuel)
        try:
            pd.testing.assert_frame_equal(
                table_reference.reset_index(drop=True),
                table_actuelle.reset_index(drop=True),
            )
        except AssertionError as ecart:
            en_echec.append(f"{chemin_relatif} :\n{ecart}")
        else:
            print(f"[identique] {chemin_relatif} ({len(table_actuelle)} ligne(s))")

    if ignorees:
        print(f"AVERTISSEMENT : non comparées, jamais capturées : {', '.join(ignorees)}", file=sys.stderr)

    if en_echec:
        print("\nIDEMPOTENCE NON VÉRIFIÉE — au moins une sortie diffère :", file=sys.stderr)
        for message in en_echec:
            print(f"  - {message}", file=sys.stderr)
        return 1

    print("\nIdempotence vérifiée par le contenu : les sorties capturées sont identiques.")
    return 0


def main() -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("action", choices=["capturer", "comparer"])
    arguments = analyseur.parse_args()

    settings = get_settings()
    if arguments.action == "capturer":
        return capturer(settings)
    return comparer(settings)


if __name__ == "__main__":
    sys.exit(main())
