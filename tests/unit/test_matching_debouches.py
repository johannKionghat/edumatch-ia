"""Tests du terme de débouchés (src/edumatch/matching/debouches.py).

Fixtures construites à la main, jamais les fichiers réels de `data/samples/`
(ceux-ci sont testés par `tests/data/test_matching_debouches_run.py`) : ce
module isole chaque règle — le grain territorial, le filtre diffusible, les
trois issues du k-anonymat, les statuts du terme de débouchés.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from edumatch.matching.agregat_sirene_debouches import (
    appliquer_k_anonymat,
    construire_agregat_departement_naf,
    departement_depuis_commune,
)
from edumatch.matching.debouches import (
    STATUT_INDISPONIBLE_CERTIFICATION_RADIEE,
    STATUT_INDISPONIBLE_CHAINE_ROMPUE,
    STATUT_INDISPONIBLE_K_ANONYMAT,
    STATUT_INDISPONIBLE_TERRITOIRE_NON_RENSEIGNE,
    STATUT_MESURE,
    VALEUR_NEUTRE,
    calculer_terme_debouches,
    construire_correspondance_formation_ideo,
    normaliser_libelle,
)

# ─── Département depuis un code commune ─────────────────────────────────────


@pytest.mark.parametrize(
    ("code_commune", "attendu"),
    [
        ("75056", "75"),  # Paris
        ("13055", "13"),  # Marseille
        ("2A004", "2A"),  # Corse-du-Sud
        ("2B033", "2B"),  # Haute-Corse
        ("97105", "971"),  # Guadeloupe
        ("97411", "974"),  # La Réunion
        ("98818", "988"),  # Nouvelle-Calédonie
        (None, None),
        ("", None),
        ("7", None),
    ],
)
def test_departement_depuis_commune(code_commune: str | None, attendu: str | None) -> None:
    assert departement_depuis_commune(code_commune) == attendu


# ─── Agrégat Sirene département x division NAF ──────────────────────────────


def _ecrire_sirene(chemin: Path, lignes: list[dict[str, str | None]]) -> None:
    pl.DataFrame(lignes).write_parquet(chemin)


def test_agregat_filtre_actif_employeur_diffusible(tmp_path: Path) -> None:
    chemin = tmp_path / "sirene.parquet"
    _ecrire_sirene(
        chemin,
        [
            # retenu : actif, employeur, diffusible
            {
                "codeCommuneEtablissement": "75056",
                "activitePrincipaleEtablissement": "6201Z",
                "etatAdministratifEtablissement": "A",
                "caractereEmployeurEtablissement": "O",
                "nomenclatureActivitePrincipaleEtablissement": "NAFRev2",
                "statutDiffusionEtablissement": "O",
            },
            # exclu : fermé
            {
                "codeCommuneEtablissement": "75056",
                "activitePrincipaleEtablissement": "6201Z",
                "etatAdministratifEtablissement": "F",
                "caractereEmployeurEtablissement": "O",
                "nomenclatureActivitePrincipaleEtablissement": "NAFRev2",
                "statutDiffusionEtablissement": "O",
            },
            # exclu : non employeur
            {
                "codeCommuneEtablissement": "75056",
                "activitePrincipaleEtablissement": "6201Z",
                "etatAdministratifEtablissement": "A",
                "caractereEmployeurEtablissement": "N",
                "nomenclatureActivitePrincipaleEtablissement": "NAFRev2",
                "statutDiffusionEtablissement": "O",
            },
            # exclu : non diffusible (le filtre que l'agrégat Sirene n'applique pas, ce module si)
            {
                "codeCommuneEtablissement": "75056",
                "activitePrincipaleEtablissement": "6201Z",
                "etatAdministratifEtablissement": "A",
                "caractereEmployeurEtablissement": "O",
                "nomenclatureActivitePrincipaleEtablissement": "NAFRev2",
                "statutDiffusionEtablissement": "P",
            },
            # exclu : commune inconnue
            {
                "codeCommuneEtablissement": None,
                "activitePrincipaleEtablissement": "6201Z",
                "etatAdministratifEtablissement": "A",
                "caractereEmployeurEtablissement": "O",
                "nomenclatureActivitePrincipaleEtablissement": "NAFRev2",
                "statutDiffusionEtablissement": "O",
            },
        ],
    )
    agregat = construire_agregat_departement_naf(chemin)
    assert agregat.height == 1
    ligne = agregat.row(0, named=True)
    assert ligne["departement"] == "75"
    assert ligne["naf_division"] == "62"
    assert ligne["nb_actifs_employeurs_diffusibles"] == 1


def test_agregat_ne_retient_que_la_nomenclature_en_vigueur(tmp_path: Path) -> None:
    """Un code d'une nomenclature ancienne donnerait une division qui désigne autre chose en Rev.2.

    « 74.1J » est un code NAF 1993 : ses deux premiers caractères donneraient la division 74, qui
    ne recouvre pas la même activité dans la nomenclature en vigueur. Ces établissements sont
    déjà écartés de fait par les filtres actif, employeur et diffusible (une seule ligne sur
    2 400 061 dans le stock réel), mais l'exclusion doit être explicite : la bascule vers NAF 2025
    la rendrait décisive.
    """
    chemin = tmp_path / "sirene.parquet"
    commun = {
        "codeCommuneEtablissement": "75056",
        "etatAdministratifEtablissement": "A",
        "caractereEmployeurEtablissement": "O",
        "statutDiffusionEtablissement": "O",
    }
    _ecrire_sirene(
        chemin,
        [
            {
                **commun,
                "activitePrincipaleEtablissement": "62.01Z",
                "nomenclatureActivitePrincipaleEtablissement": "NAFRev2",
            },
            {
                **commun,
                "activitePrincipaleEtablissement": "74.1J",
                "nomenclatureActivitePrincipaleEtablissement": "NAF1993",
            },
            {
                **commun,
                "activitePrincipaleEtablissement": "70.2C",
                "nomenclatureActivitePrincipaleEtablissement": "NAFRev1",
            },
            {
                **commun,
                "activitePrincipaleEtablissement": "67.01",
                "nomenclatureActivitePrincipaleEtablissement": "NAP",
            },
        ],
    )
    agregat = construire_agregat_departement_naf(chemin)
    assert agregat.to_dicts() == [
        {"departement": "75", "naf_division": "62", "nb_actifs_employeurs_diffusibles": 1}
    ]


def test_agregat_regroupe_par_division_naf_pas_par_sous_classe(tmp_path: Path) -> None:
    """La chaîne NAF/ROME/formation ne résout jamais plus finement que la division :
    deux sous-classes de la même division se regroupent dans la même cellule de restitution."""
    chemin = tmp_path / "sirene.parquet"
    _ecrire_sirene(
        chemin,
        [
            {
                "codeCommuneEtablissement": "75056",
                "activitePrincipaleEtablissement": "6201Z",
                "etatAdministratifEtablissement": "A",
                "caractereEmployeurEtablissement": "O",
                "nomenclatureActivitePrincipaleEtablissement": "NAFRev2",
                "statutDiffusionEtablissement": "O",
            },
            {
                "codeCommuneEtablissement": "75001",
                "activitePrincipaleEtablissement": "6202A",
                "etatAdministratifEtablissement": "A",
                "caractereEmployeurEtablissement": "O",
                "nomenclatureActivitePrincipaleEtablissement": "NAFRev2",
                "statutDiffusionEtablissement": "O",
            },
        ],
    )
    agregat = construire_agregat_departement_naf(chemin)
    assert agregat.height == 1
    assert agregat.row(0, named=True)["nb_actifs_employeurs_diffusibles"] == 2


# ─── k-anonymat : les trois issues ──────────────────────────────────────────


def test_k_anonymat_distingue_conserve_supprime_et_absent() -> None:
    agregat = pl.DataFrame(
        {
            "departement": ["75", "75", "75"],
            "naf_division": ["62", "85", "47"],
            "nb_actifs_employeurs_diffusibles": [10, 2, 0],
        }
    ).filter(
        pl.col("nb_actifs_employeurs_diffusibles") > 0
    )  # une cellule à 0 n'existe jamais dans un groupby réel
    conserve, cellules_non_vides, rapport = appliquer_k_anonymat(agregat, k=5)

    assert conserve.height == 1
    assert conserve.row(0, named=True)["naf_division"] == "62"
    assert cellules_non_vides.height == 2  # "62" et "85" existent, "47" n'a jamais existé
    assert rapport.k == 5
    assert rapport.cellules_totales == 2
    assert rapport.cellules_supprimees == 1
    assert rapport.etablissements_totaux == 12
    assert rapport.etablissements_perdus == 2
    assert rapport.part_cellules_supprimees == pytest.approx(0.5)


def test_rapport_k_anonymat_sur_agregat_vide_ne_divise_pas_par_zero() -> None:
    agregat = pl.DataFrame(
        {"departement": [], "naf_division": [], "nb_actifs_employeurs_diffusibles": []},
        schema={
            "departement": pl.Utf8,
            "naf_division": pl.Utf8,
            "nb_actifs_employeurs_diffusibles": pl.Int64,
        },
    )
    _, _, rapport = appliquer_k_anonymat(agregat, k=5)
    assert rapport.part_cellules_supprimees == 0.0
    assert rapport.part_etablissements_perdus == 0.0


# ─── Correspondance textuelle Parcoursup <-> IDÉO ───────────────────────────


def test_normaliser_libelle_meme_regle_que_affinite() -> None:
    assert normaliser_libelle("BTS Comptabilité-Gestion") == "bts comptabilite gestion"
    assert normaliser_libelle(None) == ""


def test_correspondance_exacte_apres_normalisation() -> None:
    catalogue = pl.DataFrame(
        {"fil_lib_voe_acc": ["Certificat de capacité d'orthoptiste", "Formation inconnue"]}
    )
    ideo = pl.DataFrame(
        {
            "code_rncp_ideo": ["12345"],
            "libelle_formation_ideo": ["certificat de capacité d'orthoptiste"],
        }
    )
    correspondance, rapport = construire_correspondance_formation_ideo(catalogue, ideo)

    assert correspondance.height == 1
    assert correspondance.row(0, named=True)["code_rncp_ideo"] == "12345"
    assert rapport.n_libelles_parcoursup_distincts == 2
    assert rapport.n_libelles_apparies == 1
    assert rapport.taux_appariement_libelles == pytest.approx(0.5)


def test_libelle_ideo_ambigu_est_exclu() -> None:
    """Un même libellé normalisé rattaché à deux codes RNCP différents ne peut pas être
    résolu par un choix arbitraire : la ligne est exclue de la correspondance."""
    catalogue = pl.DataFrame({"fil_lib_voe_acc": ["communication"]})
    ideo = pl.DataFrame(
        {
            "code_rncp_ideo": ["111", "222"],
            "libelle_formation_ideo": ["communication", "communication"],
        }
    )
    correspondance, rapport = construire_correspondance_formation_ideo(catalogue, ideo)
    assert correspondance.height == 0
    assert rapport.n_libelles_apparies == 0


# ─── Le terme de débouchés : chaque statut ──────────────────────────────────


@pytest.fixture()
def correspondance() -> pl.DataFrame:
    return pl.DataFrame({"fil_lib_voe_acc": ["BTS SIO"], "code_rncp_ideo": ["RNCP001"]})


@pytest.fixture()
def table_naf() -> pl.DataFrame:
    return pl.DataFrame({"code_rncp_ideo": ["RNCP001", "RNCP001"], "naf_division": ["62", "63"]})


def test_territoire_non_renseigne_est_indisponible(
    correspondance: pl.DataFrame, table_naf: pl.DataFrame
) -> None:
    agregat_vide = pl.DataFrame(
        schema={
            "departement": pl.Utf8,
            "naf_division": pl.Utf8,
            "nb_actifs_employeurs_diffusibles": pl.Int64,
        }
    )
    cellules_vides = pl.DataFrame(schema={"departement": pl.Utf8, "naf_division": pl.Utf8})
    terme = calculer_terme_debouches(
        "BTS SIO", None, correspondance, table_naf, agregat_vide, cellules_vides, 20
    )
    assert terme.disponible is False
    assert terme.statut == STATUT_INDISPONIBLE_TERRITOIRE_NON_RENSEIGNE
    assert terme.valeur == VALEUR_NEUTRE


def test_chaine_rompue_pour_un_libelle_sans_correspondance(
    correspondance: pl.DataFrame, table_naf: pl.DataFrame
) -> None:
    agregat_vide = pl.DataFrame(
        schema={
            "departement": pl.Utf8,
            "naf_division": pl.Utf8,
            "nb_actifs_employeurs_diffusibles": pl.Int64,
        }
    )
    cellules_vides = pl.DataFrame(schema={"departement": pl.Utf8, "naf_division": pl.Utf8})
    terme = calculer_terme_debouches(
        "Libellé jamais apparié", "75", correspondance, table_naf, agregat_vide, cellules_vides, 20
    )
    assert terme.disponible is False
    assert terme.statut == STATUT_INDISPONIBLE_CHAINE_ROMPUE
    assert terme.valeur == VALEUR_NEUTRE


def test_certification_radiee_donne_un_zero_reel(correspondance: pl.DataFrame) -> None:
    table_naf_sans_division_active = pl.DataFrame(
        schema={"code_rncp_ideo": pl.Utf8, "naf_division": pl.Utf8}
    )  # aucune ligne : la certification a été filtrée en amont (rncp_actif == False)
    agregat_vide = pl.DataFrame(
        schema={
            "departement": pl.Utf8,
            "naf_division": pl.Utf8,
            "nb_actifs_employeurs_diffusibles": pl.Int64,
        }
    )
    cellules_vides = pl.DataFrame(schema={"departement": pl.Utf8, "naf_division": pl.Utf8})
    terme = calculer_terme_debouches(
        "BTS SIO",
        "75",
        correspondance,
        table_naf_sans_division_active,
        agregat_vide,
        cellules_vides,
        20,
    )
    assert terme.disponible is True
    assert terme.statut == STATUT_INDISPONIBLE_CERTIFICATION_RADIEE
    assert terme.valeur == 0.0  # un terme nul, réel, qui doit supprimer la recommandation


def test_zero_reel_sans_aucun_etablissement(
    correspondance: pl.DataFrame, table_naf: pl.DataFrame
) -> None:
    agregat_vide = pl.DataFrame(
        schema={
            "departement": pl.Utf8,
            "naf_division": pl.Utf8,
            "nb_actifs_employeurs_diffusibles": pl.Int64,
        }
    )
    cellules_vides = pl.DataFrame(schema={"departement": pl.Utf8, "naf_division": pl.Utf8})
    terme = calculer_terme_debouches(
        "BTS SIO", "75", correspondance, table_naf, agregat_vide, cellules_vides, 20
    )
    assert terme.disponible is True
    assert terme.statut == STATUT_MESURE
    assert terme.valeur == 0.0
    assert terme.n_etablissements == 0


def test_suppression_par_k_anonymat_jamais_confondue_avec_un_zero_reel(
    correspondance: pl.DataFrame, table_naf: pl.DataFrame
) -> None:
    agregat_conserve_vide = pl.DataFrame(
        schema={
            "departement": pl.Utf8,
            "naf_division": pl.Utf8,
            "nb_actifs_employeurs_diffusibles": pl.Int64,
        }
    )
    # la cellule existe (au moins un établissement), mais sous le seuil de k-anonymat :
    # elle a donc disparu de `agregat_conserve` sans disparaître de `cellules_non_vides`.
    cellules_non_vides = pl.DataFrame({"departement": ["75"], "naf_division": ["62"]})
    terme = calculer_terme_debouches(
        "BTS SIO", "75", correspondance, table_naf, agregat_conserve_vide, cellules_non_vides, 20
    )
    assert terme.disponible is False
    assert terme.statut == STATUT_INDISPONIBLE_K_ANONYMAT
    assert terme.valeur == VALEUR_NEUTRE
    assert terme.n_etablissements is None  # jamais exposé sous le seuil


def test_valeur_mesuree_sature_a_un(correspondance: pl.DataFrame, table_naf: pl.DataFrame) -> None:
    agregat = pl.DataFrame(
        {
            "departement": ["75", "75"],
            "naf_division": ["62", "63"],
            "nb_actifs_employeurs_diffusibles": [15, 10],
        }
    )
    cellules_non_vides = agregat.select("departement", "naf_division")
    terme = calculer_terme_debouches(
        "BTS SIO", "75", correspondance, table_naf, agregat, cellules_non_vides, seuil_saturation=20
    )
    assert terme.disponible is True
    assert terme.statut == STATUT_MESURE
    assert terme.n_etablissements == 25
    assert terme.valeur == 1.0  # 25 / 20 saturé à 1,0, jamais > 1


def test_valeur_mesuree_proportionnelle_sous_le_seuil(
    correspondance: pl.DataFrame, table_naf: pl.DataFrame
) -> None:
    agregat = pl.DataFrame(
        {"departement": ["75"], "naf_division": ["62"], "nb_actifs_employeurs_diffusibles": [5]}
    )
    cellules_non_vides = agregat.select("departement", "naf_division")
    terme = calculer_terme_debouches(
        "BTS SIO", "75", correspondance, table_naf, agregat, cellules_non_vides, seuil_saturation=20
    )
    assert terme.valeur == pytest.approx(0.25)
