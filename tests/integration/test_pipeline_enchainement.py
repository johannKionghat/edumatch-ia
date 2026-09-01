"""Tests d'intégration du pipeline (E33) : idempotence de l'enchaînement et blocage qualité.

Ces tests appellent les fonctions de `edumatch.orchestration.taches` — celles
que `pipelines/edumatch_pipeline.py` assemble en graphe Airflow — directement,
sans Airflow. C'est la logique métier de la chaîne qui est vérifiée ici ;
la structure du graphe lui-même (dépendances entre tâches) est vérifiée à
part dans `tests/unit/test_pipeline_dag_airflow.py`, conditionnée à la
présence d'Airflow.

Deux propriétés démontrées, pas seulement affirmées :

1. Rejouer l'enchaînement silver -> gold -> variables produit un état
   strictement identique (idempotence, critère 3.6).
2. Un contrôle qualité bloquant interrompt la chaîne avant la transformation :
   `silver.parquet` n'est jamais écrit (blocage qualité, critère 3.5).
"""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from edumatch.config import Settings, get_settings, load_settings
from edumatch.orchestration import taches
from edumatch.quality._diagnostic import ErreurQualiteBloquante


def _horodatage() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Idempotence de l'enchaînement silver -> gold -> variables ─────────────


@pytest.fixture()
def settings_jetables(tmp_path: Path) -> Settings:
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    dossier_raw = settings.raw_dir / "parcoursup"
    dossier_raw.mkdir(parents=True)
    for millesime in settings.donnees.parcoursup.millesimes:
        source = base.samples_dir / "parcoursup" / f"parcoursup_{millesime}.csv"
        shutil.copy(source, dossier_raw / f"parcoursup_{millesime}.csv")
    return settings


def test_enchainement_silver_gold_variables_est_idempotent(settings_jetables: Settings) -> None:
    """Rejoue la chaîne complète deux fois : le second passage doit produire un état identique.

    C'est l'enchaînement orchestré (les fonctions de `taches.py`, dans
    l'ordre où le DAG les appelle) qui est testé ici — l'idempotence de
    chaque étape prise séparément est déjà démontrée par
    `tests/data/test_transform_run.py`, `test_transform_run_etoile.py` et
    `test_features_build_run.py` (E15, E16, E20).
    """
    taches.transformer_silver(settings_jetables)
    taches.construire_gold(settings_jetables)
    taches.construire_variables(settings_jetables)

    chemin_silver = settings_jetables.interim_dir / "parcoursup" / "silver.parquet"
    chemin_fait = settings_jetables.processed_dir / "parcoursup" / "fait_admission.parquet"
    chemin_variables = settings_jetables.processed_dir / "parcoursup" / "variables.parquet"

    premier_silver = pq.read_table(chemin_silver).to_pandas()
    premier_fait = pq.read_table(chemin_fait).to_pandas()
    premieres_variables = pq.read_table(chemin_variables).to_pandas()

    # Second passage, exactement la même séquence de tâches.
    taches.transformer_silver(settings_jetables)
    taches.construire_gold(settings_jetables)
    taches.construire_variables(settings_jetables)

    second_silver = pq.read_table(chemin_silver).to_pandas()
    second_fait = pq.read_table(chemin_fait).to_pandas()
    secondes_variables = pq.read_table(chemin_variables).to_pandas()

    pd.testing.assert_frame_equal(premier_silver, second_silver)
    pd.testing.assert_frame_equal(premier_fait, second_fait)
    pd.testing.assert_frame_equal(premieres_variables, secondes_variables)


# ─── Blocage qualité : la chaîne s'arrête avant toute transformation ────────

FICHIERS_SIRENE = (
    "StockEtablissement",
    "StockEtablissementHistorique",
    "StockUniteLegale",
    "StockUniteLegaleHistorique",
)


def _installer_sirene_valide(racine: Path) -> None:
    destination = racine / "raw" / "sirene"
    destination.mkdir(parents=True, exist_ok=True)
    manifeste = {}
    for fichier in FICHIERS_SIRENE:
        source = Path(f"data/samples/sirene/{fichier}.parquet")
        shutil.copy(source, destination / f"{fichier}.parquet")
        manifeste[fichier] = {
            "url": "https://exemple.test/stock",
            "date_publication_stock": _horodatage(),
            "date_telechargement": _horodatage(),
            "empreinte_sha256": "0" * 64,
        }
    (destination / "manifeste.json").write_text(json.dumps(manifeste), encoding="utf-8")


def _installer_referentiels_valides(racine: Path) -> None:
    destination = racine / "external" / "referentiels"
    (destination / "ideo").mkdir(parents=True, exist_ok=True)
    (destination / "rncp").mkdir(parents=True, exist_ok=True)
    manifeste: dict[str, dict[str, object]] = {}
    for jeu in ("formations", "metiers", "structures_secondaire", "structures_superieur"):
        source = Path(f"data/samples/referentiels/ideo/{jeu}.csv")
        shutil.copy(source, destination / "ideo" / f"{jeu}.csv")
        manifeste[f"ideo:{jeu}"] = {
            "url": "https://exemple.test",
            "date_telechargement": _horodatage(),
        }
    jour = datetime.now(timezone.utc).date().isoformat()
    shutil.copy(
        Path("data/samples/referentiels/rncp/rncp_echantillon.csv"),
        destination / "rncp" / f"rncp_{jour}.csv",
    )
    manifeste[f"rncp:{jour}"] = {"url": "https://exemple.test", "date_publication": _horodatage()}
    (destination / "manifeste.json").write_text(json.dumps(manifeste), encoding="utf-8")


def _installer_parcoursup_valide(racine: Path, millesimes: list[int]) -> None:
    destination = racine / "raw" / "parcoursup"
    destination.mkdir(parents=True, exist_ok=True)
    manifeste: dict[str, dict[str, object]] = {}
    for millesime in millesimes:
        source = Path(f"data/samples/parcoursup/parcoursup_{millesime}.csv")
        shutil.copy(source, destination / f"parcoursup_{millesime}.csv")
        manifeste[str(millesime)] = {
            "millesime": millesime,
            "identifiant": f"fr-esr-parcoursup-{millesime}",
            "url": "https://exemple.test",
            "date_telechargement": _horodatage(),
            "taille_octets": (destination / f"parcoursup_{millesime}.csv").stat().st_size,
            "empreinte_sha256": "0" * 64,
        }
    (destination / "manifeste.json").write_text(json.dumps(manifeste), encoding="utf-8")


def _corrompre_millesime_le_plus_recent(racine: Path, millesime: int) -> None:
    """Retire la colonne `fili` (liste blanche `session_courante`) du millésime le plus récent —
    même panne que `tests/data/test_quality_run_blocage.py` : une colonne de la liste blanche
    disparaît, sans laquelle la construction des variables lirait une colonne absente."""
    chemin = racine / "raw" / "parcoursup" / f"parcoursup_{millesime}.csv"
    with chemin.open("r", encoding="utf-8-sig", newline="") as flux:
        lignes = list(csv.DictReader(flux, delimiter=";"))
    colonnes = [c for c in lignes[0].keys() if c != "fili"] if lignes else []
    with chemin.open("w", encoding="utf-8-sig", newline="") as flux:
        ecrivain = csv.DictWriter(flux, fieldnames=colonnes, delimiter=";", extrasaction="ignore")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)


@pytest.fixture()
def environnement_complet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    racine = tmp_path / "data"
    _installer_sirene_valide(racine)
    _installer_referentiels_valides(racine)
    _installer_parcoursup_valide(racine, load_settings("prod").donnees.parcoursup.millesimes)
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(racine))
    monkeypatch.setenv("EDUMATCH_ENV", "prod")
    get_settings.cache_clear()
    yield racine
    get_settings.cache_clear()


def test_environnement_complet_ne_bloque_pas(environnement_complet: Path) -> None:
    """Préalable : sans cette vérification, un blocage provoqué plus loin ne prouverait rien."""
    settings = load_settings("prod")
    taches.controler_qualite(settings)  # ne lève pas


def test_panne_qualite_arrete_la_chaine_avant_la_transformation(
    environnement_complet: Path,
) -> None:
    """Panne provoquée : une colonne de la liste blanche disparaît du millésime le plus récent.

    Reproduit ici l'ordre exact que `pipelines/edumatch_pipeline.py` impose
    au DAG `edumatch_parcoursup` (ingestion >> qualité >> silver >> gold >>
    variables) : chaque étape n'est appelée que si la précédente n'a pas
    levé — exactement le comportement `trigger_rule="all_success"` par
    défaut d'un opérateur Airflow. `transformer_silver` ne doit jamais être
    invoquée, et ne doit donc laisser aucune trace sur disque.
    """
    settings = load_settings("prod")
    dernier_millesime = max(settings.donnees.parcoursup.millesimes)
    _corrompre_millesime_le_plus_recent(environnement_complet, dernier_millesime)

    ordre_execute: list[str] = []
    chaine = [
        ("qualite", taches.controler_qualite),
        ("silver", taches.transformer_silver),
        ("gold", taches.construire_gold),
        ("variables", taches.construire_variables),
    ]

    with pytest.raises(ErreurQualiteBloquante, match="fili"):
        for nom, fonction in chaine:
            ordre_execute.append(nom)
            fonction(settings)

    assert ordre_execute == ["qualite"]  # jamais silver, gold ni variables
    chemin_silver = settings.interim_dir / "parcoursup" / "silver.parquet"
    assert not chemin_silver.exists()


def test_restauration_leve_le_blocage_et_la_chaine_reprend(environnement_complet: Path) -> None:
    """Reprise : le fichier corrompu est restauré, la chaîne va alors jusqu'au bout."""
    settings = load_settings("prod")
    dernier_millesime = max(settings.donnees.parcoursup.millesimes)
    _corrompre_millesime_le_plus_recent(environnement_complet, dernier_millesime)
    with pytest.raises(ErreurQualiteBloquante):
        taches.controler_qualite(settings)

    _installer_parcoursup_valide(environnement_complet, [dernier_millesime])

    taches.controler_qualite(settings)  # ne lève plus
    taches.transformer_silver(settings)
    taches.construire_gold(settings)
    taches.construire_variables(settings)

    chemin_variables = settings.processed_dir / "parcoursup" / "variables.parquet"
    assert chemin_variables.exists()
