"""Démonstration du blocage de bout en bout (E14, critère central de l'étape).

Construit un environnement de données complet et valide dans `tmp_path`
(jamais dans `data/`), à partir des échantillons versionnés, puis y insère un
fichier Parcoursup volontairement corrompu. Vérifie que `edumatch.quality.run`
interrompt la chaîne — pas seulement qu'il le pourrait en théorie — puis que
la restauration d'un fichier valide fait disparaître le blocage : c'est la
paire panne / reprise que l'étape exige de démontrer.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from edumatch.config import get_settings, load_settings
from edumatch.quality import run as quality_run
from edumatch.quality._diagnostic import ErreurQualiteBloquante

LIGNE_PARCOURSUP_VALIDE = {
    "session": "2025",
    "cod_aff_form": "1000",
    "lien_form_psup": "https://exemple.test/1000",
    "fili": "BTS",
    "fil_lib_voe_acc": "BTS Exemple",
    "form_lib_voe_acc": "BTS",
    "select_form": "oui",
    "contrat_etab": "Public",
    "tri": "Lycée",
    "dep": "75",
    "acad_mies": "Paris",
    "region_etab_aff": "Ile-de-France",
}


def _horodatage() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ecrire_parcoursup(chemin: Path, ligne: dict[str, str]) -> None:
    import csv

    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8-sig", newline="") as fichier:
        ecrivain = csv.DictWriter(fichier, fieldnames=list(ligne), delimiter=";")
        ecrivain.writeheader()
        ecrivain.writerow(ligne)


@pytest.fixture()
def environnement_valide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Un `data_root` complet et valide : Parcoursup, Sirene et référentiels, manifestes frais."""
    racine = tmp_path / "data"
    _installer_sirene(racine)
    _installer_referentiels(racine)
    _ecrire_parcoursup(racine / "raw" / "parcoursup" / "parcoursup_2025.csv", LIGNE_PARCOURSUP_VALIDE)
    _ecrire_manifeste_parcoursup(racine)
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(racine))
    monkeypatch.setenv("EDUMATCH_ENV", "prod")
    # `get_settings()` (utilisé par `quality_run.main()` sans argument) met son
    # résultat en cache pour tout le processus : sans le vider ici, un test
    # précédent laisserait un `data_root` périmé actif pour celui-ci.
    get_settings.cache_clear()
    yield racine
    get_settings.cache_clear()


FICHIERS_SIRENE = (
    "StockEtablissement",
    "StockEtablissementHistorique",
    "StockUniteLegale",
    "StockUniteLegaleHistorique",
)


def _installer_sirene(racine: Path) -> None:
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


def _installer_referentiels(racine: Path) -> None:
    destination = racine / "external" / "referentiels"
    (destination / "ideo").mkdir(parents=True, exist_ok=True)
    (destination / "rncp").mkdir(parents=True, exist_ok=True)
    manifeste: dict[str, dict[str, object]] = {}
    for jeu in ("formations", "metiers", "structures_secondaire", "structures_superieur"):
        source = Path(f"data/samples/referentiels/ideo/{jeu}.csv")
        shutil.copy(source, destination / "ideo" / f"{jeu}.csv")
        manifeste[f"ideo:{jeu}"] = {"url": "https://exemple.test", "date_telechargement": _horodatage()}
    jour = datetime.now(timezone.utc).date().isoformat()
    shutil.copy(
        Path("data/samples/referentiels/rncp/rncp_echantillon.csv"),
        destination / "rncp" / f"rncp_{jour}.csv",
    )
    manifeste[f"rncp:{jour}"] = {"url": "https://exemple.test", "date_publication": _horodatage()}
    (destination / "manifeste.json").write_text(json.dumps(manifeste), encoding="utf-8")


def _ecrire_manifeste_parcoursup(racine: Path) -> None:
    manifeste = {
        "2025": {
            "millesime": 2025,
            "identifiant": "fr-esr-parcoursup",
            "url": "https://exemple.test/2025",
            "date_telechargement": _horodatage(),
            "taille_octets": 100,
            "empreinte_sha256": "0" * 64,
        }
    }
    (racine / "raw" / "parcoursup" / "manifeste.json").write_text(json.dumps(manifeste), encoding="utf-8")


def test_environnement_valide_ne_bloque_pas(environnement_valide: Path) -> None:
    """Vérifie d'abord que l'environnement fabriqué est sain : sans ce préalable, un blocage plus loin ne prouverait rien."""
    settings = load_settings("prod")
    rapport = quality_run.executer(settings)
    assert not rapport.est_bloquant, [a.formatee() for a in rapport.bloquantes]


def test_fichier_parcoursup_corrompu_bloque_la_chaine(environnement_valide: Path) -> None:
    """Panne : une colonne de la liste blanche disparaît du fichier Parcoursup."""
    ligne_corrompue = dict(LIGNE_PARCOURSUP_VALIDE)
    del ligne_corrompue["fili"]
    _ecrire_parcoursup(
        environnement_valide / "raw" / "parcoursup" / "parcoursup_2025.csv", ligne_corrompue
    )

    settings = load_settings("prod")
    rapport = quality_run.executer(settings)
    assert rapport.est_bloquant

    with pytest.raises(ErreurQualiteBloquante, match="fili"):
        rapport.lever_si_bloquant()

    code_retour = quality_run.main()
    assert code_retour == 1


def test_restauration_d_un_fichier_valide_leve_le_blocage(environnement_valide: Path) -> None:
    """Reprise : panne provoquée, puis fichier restauré — le blocage disparaît sans autre action."""
    chemin = environnement_valide / "raw" / "parcoursup" / "parcoursup_2025.csv"
    ligne_corrompue = dict(LIGNE_PARCOURSUP_VALIDE)
    del ligne_corrompue["fili"]
    _ecrire_parcoursup(chemin, ligne_corrompue)
    settings = load_settings("prod")
    assert quality_run.executer(settings).est_bloquant

    _ecrire_parcoursup(chemin, LIGNE_PARCOURSUP_VALIDE)
    rapport_apres_reprise = quality_run.executer(settings)
    assert not rapport_apres_reprise.est_bloquant
    assert quality_run.main() == 0
