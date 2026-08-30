"""Non-régression du label (E19) : la formule ne doit jamais dériver silencieusement.

Deux niveaux, complémentaires :

1. Un vecteur figé, directement sur `edumatch.features.label` : si la
   formule change (borne, définition, forme du poids), ces valeurs codées en
   dur cessent de correspondre et le test échoue — c'est le filet explicite
   demandé par `tests/data` (contrats de données).
2. Le pipeline complet sur `data/samples/parcoursup/` (les huit millésimes
   échantillonnés, E08) : silver (E15) puis gold (E16), qui appelle
   désormais `edumatch.features.label.calculer_taux`. Vérifie que
   l'extraction n'a rien changé au résultat de bout en bout, pas seulement à
   la fonction isolée.

Les volumétries au 2. ont été mesurées une fois sur les échantillons
versionnés du dépôt (reproductibles par quiconque relance ce test), pas
inventées.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from edumatch.config import Settings, load_settings
from edumatch.features.label import BORNE_SUPERIEURE_TAUX, calculer_taux, poids_effectif
from edumatch.transform import run, run_etoile

# ─── 1. Vecteur figé, formule isolée ────────────────────────────────────────


def test_vecteur_fige_calculer_taux() -> None:
    """Cinq cellules choisies pour couvrir la formule et son bornage, valeurs attendues figées."""
    numerateur = pd.Series([6, 12, 0, 5, pd.NA], dtype="Int64")
    denominateur = pd.Series([10, 10, 10, 0, 10], dtype="Int64")

    taux, depasse = calculer_taux(numerateur, denominateur)

    attendu_taux = [0.6, 1.0, 0.0, 1.0, pd.NA]
    attendu_depasse = [False, True, False, True, pd.NA]
    for obtenu, attendu in zip(taux.tolist(), attendu_taux, strict=True):
        if pd.isna(attendu):
            assert pd.isna(obtenu)
        else:
            assert obtenu == pytest.approx(attendu)
    for obtenu, attendu in zip(depasse.tolist(), attendu_depasse, strict=True):
        if pd.isna(attendu):
            assert pd.isna(obtenu)
        else:
            assert bool(obtenu) is attendu
    assert BORNE_SUPERIEURE_TAUX == 1.0  # la borne elle-même fait partie du contrat


def test_vecteur_fige_poids_effectif() -> None:
    """Le poids est l'effectif brut : toute forme (racine, log, plafond) romprait ce vecteur."""
    poids = poids_effectif(pd.Series([1, 9, 30, 287, 16483], dtype="Int64"))
    assert poids.tolist() == [1.0, 9.0, 30.0, 287.0, 16483.0]


# ─── 2. Pipeline complet sur les échantillons versionnés ───────────────────


@pytest.fixture()
def settings_avec_gold(tmp_path: Path) -> Settings:
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    dossier_raw = settings.raw_dir / "parcoursup"
    dossier_raw.mkdir(parents=True)
    for millesime in settings.donnees.parcoursup.millesimes:
        source = base.samples_dir / "parcoursup" / f"parcoursup_{millesime}.csv"
        shutil.copy(source, dossier_raw / f"parcoursup_{millesime}.csv")
    run.executer(settings)
    run_etoile.executer(settings)
    return settings


def test_non_regression_label_sur_les_echantillons(settings_avec_gold: Settings) -> None:
    """Mesuré une fois sur `data/samples/parcoursup/` (2018-2025) : 1 280 cellules exploitables."""
    fait = pq.read_table(
        settings_avec_gold.processed_dir / "parcoursup" / "fait_admission.parquet"
    ).to_pandas()

    assert len(fait) == 1280
    assert fait["taux"].sum() == pytest.approx(558.7422527761335)
    assert int(fait["taux_depasse_1"].sum()) == 85
    assert int(fait["effectif"].sum()) == 180192
