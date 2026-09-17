"""Terme de débouchés sur les échantillons réels de `data/samples/`.

Comme `tests/data/test_referentiel_naf_rome_formation_reel.py` dont ce
module réutilise la chaîne : extraits réels, aucun téléchargement, aucune
garantie de taux d'appariement précis (l'échantillonnage indépendant des
sources réduit mécaniquement les correspondances trouvées) — seulement que
la chaîne s'exécute sur des données réelles sans erreur et que la structure
du résultat est celle attendue.

L'agrégat Sirene département x NAF (`construire_agregat_departement_naf`)
n'est volontairement pas exercé ici : `data/samples/sirene/StockEtablissement.parquet`
ne porte pas `statutDiffusionEtablissement` (l'échantillon versionné retient les 9
colonnes utiles à l'agrégat Sirene, qui n'inclut pas le filtre diffusible — voir le
docstring de `matching/debouches.py`). Cette fonction est testée sur une
fixture construite à la main dans `tests/unit/test_matching_debouches.py`,
avec les 5 colonnes réellement nécessaires ; l'étendre à
`data/samples/sirene/` est un gap déclaré, pas masqué, à traiter par une
régénération de l'échantillon si ce terme doit un jour être démontré
de bout en bout sur des échantillons versionnés plutôt que sur le fichier
Sirene complet (`data/raw/sirene/`, non versionné, ~4,4 Go).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from edumatch.matching.debouches import (
    construire_correspondance_formation_ideo,
    normaliser_libelle,
)
from edumatch.referentiel.naf_rome_formation import charger_formations_ideo

CHEMIN_IDEO = Path("data/samples/referentiels/ideo/formations.csv")
CHEMIN_PARCOURSUP_2025 = Path("data/samples/parcoursup/parcoursup_2025.csv")


def _catalogue_parcoursup_echantillon() -> pl.DataFrame:
    brut = pl.read_csv(CHEMIN_PARCOURSUP_2025, separator=";", infer_schema_length=0, encoding="utf8-lossy")
    return brut.select("fil_lib_voe_acc")


def test_la_correspondance_sexecute_sur_les_echantillons_reels_sans_erreur() -> None:
    formations_ideo = charger_formations_ideo(CHEMIN_IDEO)
    catalogue = _catalogue_parcoursup_echantillon()

    correspondance, rapport = construire_correspondance_formation_ideo(catalogue, formations_ideo)

    assert correspondance.columns == ["fil_lib_voe_acc", "code_rncp_ideo"]
    assert rapport.n_libelles_parcoursup_distincts > 0
    assert 0.0 <= rapport.taux_appariement_libelles <= 1.0
    assert 0.0 <= rapport.taux_appariement_lignes <= 1.0
    # Zéro correspondance est un résultat valide sur des échantillons indépendants
    # (voir le docstring) : ce test ne l'exige pas positif, seulement cohérent.
    assert rapport.n_libelles_apparies <= rapport.n_libelles_parcoursup_distincts
    assert rapport.n_lignes_appariees <= rapport.n_lignes_parcoursup


def test_normaliser_libelle_sur_des_libelles_ideo_reels_ne_leve_jamais() -> None:
    formations_ideo = charger_formations_ideo(CHEMIN_IDEO)
    for libelle in formations_ideo["libelle_formation_ideo"].to_list():
        resultat = normaliser_libelle(libelle)
        assert isinstance(resultat, str)
        assert resultat == resultat.lower()
