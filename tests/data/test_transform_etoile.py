"""Tests du modèle en étoile gold (E16), sur des millésimes fabriqués.

Isolé de la réconciliation (E15, déjà testée par
`test_transform_reconciliation.py`) : les fixtures construisent directement
une table au format silver — typée, un `DataFrame` par cas — pour ne
vérifier qu'une chose à la fois : le dépliage en cellules, le grain de
`fait_admission`, la SCD 2 de `dim_formation`, l'intégrité référentielle.
"""

from __future__ import annotations

import copy

import pandas as pd
import pytest

from edumatch.transform.etoile import (
    CATEGORIES,
    ErreurEtoile,
    base_exploitable,
    construire_dim_formation,
    construire_dim_profil_candidat,
    construire_dim_session,
    construire_dim_territoire,
    construire_etoile,
    construire_fait_admission,
)

# Une ligne silver minimale, valeurs par défaut. `bg` est exploitable
# (dénominateur renseigné et non nul, numérateur renseigné) ; les cinq
# autres catégories sont délibérément vides, pour que chaque test choisisse
# ce qu'il rend exploitable sans porter les cinq autres à chaque fois.
_LIGNE_DEFAUT: dict = {
    "session": 2025,
    "cod_aff_form": "1000",
    "dep": "75",
    "ville_etab": "Paris",
    "dep_lib": "Paris",
    "acad_mies": "Paris",
    "region_etab_aff": "Ile-de-France",
    "fili": "BTS",
    "form_lib_voe_acc": "BTS Exemple",
    "fil_lib_voe_acc": "BTS Exemple",
    "select_form": "oui",
    "contrat_etab": "Public",
    "tri": "Lycée",
    "capa_fin": 30,
    "cod_uai": "0750001A",
}
for _categorie in CATEGORIES:
    _LIGNE_DEFAUT[f"nb_voe_pp_{_categorie}"] = pd.NA
    _LIGNE_DEFAUT[f"prop_tot_{_categorie}"] = pd.NA
_LIGNE_DEFAUT["nb_voe_pp_bg"] = 10
_LIGNE_DEFAUT["prop_tot_bg"] = 6


def _silver(lignes: list[dict]) -> pd.DataFrame:
    """Fabrique une table silver à partir de fusions de `_LIGNE_DEFAUT`."""
    fusionnees = []
    for ligne in lignes:
        fusion = copy.deepcopy(_LIGNE_DEFAUT)
        fusion.update(ligne)
        fusionnees.append(fusion)
    table = pd.DataFrame(fusionnees)
    table["capa_fin"] = table["capa_fin"].astype("Int64")
    for categorie in CATEGORIES:
        table[f"nb_voe_pp_{categorie}"] = table[f"nb_voe_pp_{categorie}"].astype("Int64")
        table[f"prop_tot_{categorie}"] = table[f"prop_tot_{categorie}"].astype("Int64")
    return table


# ─── Le filtre d'exploitabilité de la cellule ─────────────────────────────


def test_denominateur_nul_exclut_la_cellule() -> None:
    """`nb_voe_pp_bg = 0` : le dénominateur existe mais ne peut rien diviser."""
    silver = _silver([{"cod_aff_form": "1", "nb_voe_pp_bg": 0, "prop_tot_bg": 0}])
    base = base_exploitable(silver)
    assert len(base) == 0


def test_denominateur_manquant_exclut_la_cellule() -> None:
    """Le cas réel de 2018-2019 (ADR 0012) : `prop_tot_*` n'existe pas encore."""
    silver = _silver([{"cod_aff_form": "1", "nb_voe_pp_bg": pd.NA, "prop_tot_bg": pd.NA}])
    base = base_exploitable(silver)
    assert len(base) == 0


def test_numerateur_manquant_exclut_la_cellule_meme_avec_denominateur_positif() -> None:
    silver = _silver([{"cod_aff_form": "1", "nb_voe_pp_bg": 10, "prop_tot_bg": pd.NA}])
    base = base_exploitable(silver)
    assert len(base) == 0


def test_cle_manquante_exclut_la_ligne() -> None:
    silver = _silver([{"cod_aff_form": pd.NA}])
    base = base_exploitable(silver)
    assert len(base) == 0


# ─── Le dépliage et le grain de fait_admission ────────────────────────────


def test_une_ligne_avec_deux_categories_exploitables_produit_deux_cellules() -> None:
    silver = _silver([{"cod_aff_form": "1", "nb_voe_pp_bt": 5, "prop_tot_bt": 4}])
    etoile = construire_etoile(silver)
    assert len(etoile.fait_admission) == 2
    assert set(etoile.rapport.lignes_fait_par_session[2025] for _ in [0]) == {2}


def test_grain_fait_admission_est_session_formation_profil() -> None:
    silver = _silver(
        [
            {"cod_aff_form": "1", "nb_voe_pp_bp": 3, "prop_tot_bp": 1},
            {"cod_aff_form": "2", "nb_voe_pp_bp": 3, "prop_tot_bp": 1},
        ]
    )
    etoile = construire_etoile(silver)
    fait = etoile.fait_admission
    assert not fait.duplicated(subset=["session", "sk_formation", "sk_profil"]).any()
    assert len(fait) == 4  # bg + bp, pour deux formations


def test_construire_fait_admission_leve_sur_dimensions_dupliquees_fabriquees() -> None:
    """Vérifie le garde-fou interne : une dimension formation mal construite doit être détectée.

    Deux versions SCD 2 qui se recouvrent sur la même session, pour la même
    formation, produiraient deux résolutions de `sk_formation` pour une
    seule cellule — exactement la violation de grain que
    `construire_fait_admission` doit lever, indépendamment de la façon dont
    `dim_formation` a été construite.
    """
    silver = _silver([{"cod_aff_form": "1"}])
    base = base_exploitable(silver)
    dim_formation_corrompue = pd.DataFrame(
        [
            {
                "sk_formation": 1,
                "cod_aff_form": "1",
                "session_debut": 2025,
                "session_fin": 2025,
                "fili": "BTS",
            },
            {
                "sk_formation": 2,
                "cod_aff_form": "1",
                "session_debut": 2025,
                "session_fin": 2025,
                "fili": "BTS",
            },
        ]
    )
    dim_territoire = construire_dim_territoire(base)
    dim_profil = construire_dim_profil_candidat()
    with pytest.raises(ErreurEtoile):
        construire_fait_admission(base, dim_formation_corrompue, dim_territoire, dim_profil)


def test_construire_fait_admission_leve_sur_profil_duplique_fabrique() -> None:
    """Même garde-fou, sur `dim_profil_candidat` : une clé (type_bac, boursier) dupliquée doit être détectée."""
    silver = _silver([{"cod_aff_form": "1"}])
    base = base_exploitable(silver)
    dim_formation = construire_dim_formation(base)
    dim_territoire = construire_dim_territoire(base)
    dim_profil_corrompu = pd.DataFrame(
        [
            {"sk_profil": 1, "type_bac": "bg", "boursier": False},
            {"sk_profil": 2, "type_bac": "bg", "boursier": False},  # même clé naturelle
        ]
    )
    with pytest.raises(ErreurEtoile):
        construire_fait_admission(base, dim_formation, dim_territoire, dim_profil_corrompu)


# ─── Le label : bornage et dépassement (ADR 0009) ─────────────────────────


def test_taux_est_borne_a_un_et_le_depassement_est_signale() -> None:
    silver = _silver([{"cod_aff_form": "1", "nb_voe_pp_bg": 10, "prop_tot_bg": 26}])
    etoile = construire_etoile(silver)
    ligne = etoile.fait_admission.iloc[0]
    assert ligne["taux"] == 1.0
    assert bool(ligne["taux_depasse_1"]) is True


def test_taux_normal_n_est_pas_signale_comme_depassement() -> None:
    etoile = construire_etoile(_silver([{"cod_aff_form": "1"}]))  # 6/10, défaut
    ligne = etoile.fait_admission.iloc[0]
    assert ligne["taux"] == pytest.approx(0.6)
    assert bool(ligne["taux_depasse_1"]) is False


# ─── dim_session ───────────────────────────────────────────────────────────


def test_session_sans_cellule_exploitable_est_marquee_indisponible() -> None:
    silver = _silver(
        [
            {"session": 2019, "cod_aff_form": "1", "nb_voe_pp_bg": pd.NA, "prop_tot_bg": pd.NA},
            {"session": 2025, "cod_aff_form": "2"},
        ]
    )
    base = base_exploitable(silver)
    dim_session = construire_dim_session(silver, base)
    disponibilite = dict(zip(dim_session["session"], dim_session["label_disponible"]))
    assert disponibilite == {2019: False, 2025: True}


# ─── dim_formation : SCD 2 ─────────────────────────────────────────────────


def test_deux_sessions_identiques_sont_regroupees_dans_une_seule_version() -> None:
    silver = _silver([{"session": 2024, "cod_aff_form": "1"}, {"session": 2025, "cod_aff_form": "1"}])
    base = base_exploitable(silver)
    dim_formation = construire_dim_formation(base)
    assert len(dim_formation) == 1
    version = dim_formation.iloc[0]
    assert version["session_debut"] == 2024
    assert version["session_fin"] == 2025


def test_changement_de_capacite_cree_une_nouvelle_version_scd2() -> None:
    """Le cas énoncé par l'étape : une formation dont la capacité change relève du SCD 2."""
    silver = _silver(
        [
            {"session": 2024, "cod_aff_form": "1", "capa_fin": 30},
            {"session": 2025, "cod_aff_form": "1", "capa_fin": 35},
        ]
    )
    base = base_exploitable(silver)
    dim_formation = construire_dim_formation(base)
    assert len(dim_formation) == 2
    dim_formation = dim_formation.sort_values("session_debut")
    assert dim_formation.iloc[0][["session_debut", "session_fin", "capa_fin"]].tolist() == [2024, 2024, 30]
    assert dim_formation.iloc[1][["session_debut", "session_fin", "capa_fin"]].tolist() == [2025, 2025, 35]


def test_deux_formations_distinctes_ont_des_cles_de_substitution_distinctes() -> None:
    silver = _silver([{"cod_aff_form": "1"}, {"cod_aff_form": "2"}])
    dim_formation = construire_dim_formation(base_exploitable(silver))
    assert dim_formation["sk_formation"].nunique() == len(dim_formation) == 2


# ─── dim_territoire ─────────────────────────────────────────────────────────


def test_deux_formations_du_meme_territoire_partagent_la_dimension() -> None:
    silver = _silver(
        [
            {"cod_aff_form": "1", "dep": "75", "ville_etab": "Paris"},
            {"cod_aff_form": "2", "dep": "75", "ville_etab": "Paris"},
        ]
    )
    base = base_exploitable(silver)
    dim_territoire = construire_dim_territoire(base)
    assert len(dim_territoire) == 1


def test_ville_manquante_reste_un_territoire_distinct_par_departement() -> None:
    """`ville_etab` n'existe pas dans le fichier 2020 : ne doit pas faire échouer la dimension."""
    silver = _silver([{"cod_aff_form": "1", "dep": "75", "ville_etab": pd.NA}])
    base = base_exploitable(silver)
    dim_territoire = construire_dim_territoire(base)
    assert len(dim_territoire) == 1
    assert pd.isna(dim_territoire.iloc[0]["ville_etab"])


# ─── dim_profil_candidat ───────────────────────────────────────────────────


def test_dim_profil_candidat_a_six_lignes_fixes() -> None:
    dim = construire_dim_profil_candidat()
    assert len(dim) == 6
    assert set(zip(dim["type_bac"], dim["boursier"])) == {
        ("bg", False),
        ("bg", True),
        ("bt", False),
        ("bt", True),
        ("bp", False),
        ("bp", True),
    }


# ─── Intégrité référentielle et idempotence de l'ensemble ─────────────────


def test_aucune_reference_orpheline_entre_fait_et_dimensions() -> None:
    silver = _silver(
        [
            {"session": 2024, "cod_aff_form": "1", "dep": "75", "ville_etab": "Paris", "nb_voe_pp_bt": 4, "prop_tot_bt": 1},
            {"session": 2025, "cod_aff_form": "1", "dep": "75", "ville_etab": "Paris"},
            {"session": 2025, "cod_aff_form": "2", "dep": "13", "ville_etab": "Marseille", "capa_fin": 12},
        ]
    )
    etoile = construire_etoile(silver)
    fait = etoile.fait_admission
    assert set(fait["sk_formation"]) <= set(etoile.dim_formation["sk_formation"])
    assert set(fait["sk_territoire"]) <= set(etoile.dim_territoire["sk_territoire"])
    assert set(fait["sk_profil"]) <= set(etoile.dim_profil_candidat["sk_profil"])
    assert set(fait["session"]) <= set(etoile.dim_session["session"])


def test_construire_etoile_est_idempotent() -> None:
    silver = _silver(
        [
            {"session": 2024, "cod_aff_form": "1", "capa_fin": 30},
            {"session": 2025, "cod_aff_form": "1", "capa_fin": 35, "nb_voe_pp_bp": 2, "prop_tot_bp": 1},
            {"session": 2025, "cod_aff_form": "2", "dep": "13", "ville_etab": "Marseille"},
        ]
    )
    premiere = construire_etoile(silver)
    seconde = construire_etoile(silver)
    pd.testing.assert_frame_equal(premiere.fait_admission, seconde.fait_admission)
    pd.testing.assert_frame_equal(premiere.dim_formation, seconde.dim_formation)
    pd.testing.assert_frame_equal(premiere.dim_territoire, seconde.dim_territoire)
    assert premiere.rapport == seconde.rapport
