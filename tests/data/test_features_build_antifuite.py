"""Test anti-fuite de la construction des variables — le critère de non-fuite du projet.

Ce fichier porte le contrat le plus critique de l'étape : **aucune variable ne
contient d'information postérieure à la décision prédite**. Il s'appuie sur le
vrai classement de l'ADR 0013 (`load_settings("prod").modele.variables`), pas
sur une copie allégée, pour que la preuve porte sur la configuration
réellement utilisée en production.

Le test le plus important n'est pas celui qui vérifie l'appartenance des
colonnes à une catégorie — un classement peut être respecté et la jointure
être fausse quand même, tant que la donnée de test ne distingue pas les deux
cas. `test_les_variables_decalees_proviennent_reellement_de_la_session_precedente`
construit délibérément une session N-1 et une session N où la MÊME colonne
décalée porte deux valeurs différentes : si la jointure lisait la session N
au lieu de N-1, ce test — et lui seul — échouerait. Une table où N-1 et N
porteraient la même valeur ne prouverait rien : la fuite serait invisible.

Les trois tests ci-dessous ont été vérifiés par mutation du code de
`edumatch.features.build`, et non par relecture (voir le compte rendu rendu
avec cette étape) :

1. inverser le sens du décalage (lire N au lieu de N-1)
   -> fait échouer `test_les_variables_decalees_proviennent_reellement_de_la_session_precedente`,
      et lui seul ;
2. réintroduire `cod_uai` (colonne exclue, motif « substitut », ADR 0013 §5)
   dans les colonnes récupérées
   -> fait échouer `test_cod_uai_est_absent_du_jeu_construit`, et lui seul ;
3. réintroduire `pct_f` (colonne interdite, ventilation par sexe, ADR 0013 §4)
   -> fait échouer `test_aucune_colonne_de_genre_n_est_presente`, et lui seul.
"""

from __future__ import annotations

import pandas as pd
import pytest

from edumatch.config import VariablesConfig, load_settings
from edumatch.features.build import construire_table_apprentissage

# Les quatre ventilations par sexe, motif "interdite" de l'ADR 0013 §4 —
# invariant du projet : le genre n'entre jamais dans le modèle.
COLONNES_GENRE: tuple[str, ...] = ("pct_f", "voe_tot_f", "acc_tot_f", "acc_term_f")


@pytest.fixture(scope="module")
def variables_reelles() -> VariablesConfig:
    """Le classement réellement utilisé en production (ADR 0013), pas une copie de test."""
    return load_settings("prod").modele.variables


def _ligne_silver(session: int, cod_aff_form: str, variables: VariablesConfig, **valeurs: object) -> dict:
    """Une ligne silver couvrant TOUTES les colonnes classées (liste blanche + décalées).

    Une valeur par défaut distincte par colonne (son propre nom) pour la
    liste blanche, `0` pour les décalées : `valeurs` permet de surcharger
    ponctuellement celles dont un test a besoin de contrôler la valeur.
    """
    ligne: dict[str, object] = {"session": session, "cod_aff_form": cod_aff_form}
    for colonne in variables.session_courante:
        ligne[colonne] = f"valeur_{colonne}"
    for colonne in variables.decalees:
        ligne[colonne] = 0
    ligne.update(valeurs)
    return ligne


def _entrees_minimales(variables: VariablesConfig, sessions_silver: list[dict]) -> tuple:
    """Fabrique fait_admission / dim_formation / dim_profil / silver pour une seule cellule."""
    fait = pd.DataFrame(
        [{"session": 2025, "sk_formation": 1, "sk_profil": 1, "effectif": 10, "taux": 0.5, "taux_depasse_1": False}]
    )
    dim_formation = pd.DataFrame([{"sk_formation": 1, "cod_aff_form": "1"}])
    dim_profil = pd.DataFrame([{"sk_profil": 1, "type_bac": "bg", "boursier": False}])
    silver = pd.DataFrame(sessions_silver)
    return fait, dim_formation, dim_profil, silver


# ─── Le test critique : le sens réel du décalage ──────────────────────────


def test_les_variables_decalees_proviennent_reellement_de_la_session_precedente(
    variables_reelles: VariablesConfig,
) -> None:
    """`capa_fin` et `voe_tot` doivent valoir la session 2024, jamais la session 2025.

    Les deux sessions portent des valeurs délibérément très différentes pour
    que la confusion soit impossible à manquer : si la jointure lisait la
    session prédite au lieu de la précédente, ce test échouerait avec des
    valeurs visiblement issues de 2025 (999999, "fuite_...").
    """
    fait, dim_formation, dim_profil, silver = _entrees_minimales(
        variables_reelles,
        [
            _ligne_silver(2024, "1", variables_reelles, capa_fin=40, voe_tot=500),
            _ligne_silver(2025, "1", variables_reelles, capa_fin=999999, voe_tot=999999),
        ],
    )

    table, _ = construire_table_apprentissage(fait, dim_formation, dim_profil, silver, variables_reelles)

    assert table.iloc[0]["capa_fin"] == 40
    assert table.iloc[0]["voe_tot"] == 500


def test_la_liste_blanche_provient_de_la_session_predite_sans_decalage(
    variables_reelles: VariablesConfig,
) -> None:
    """Symétrique du test précédent : `fili` doit valoir la session 2025, jamais 2024.

    La liste blanche n'est pas décalée (ADR 0013 §1) : ce sont des attributs
    de catalogue déjà publiés au moment où le lycéen formule son vœu.
    """
    fait, dim_formation, dim_profil, silver = _entrees_minimales(
        variables_reelles,
        [
            _ligne_silver(2024, "1", variables_reelles, fili="ANCIENNE_FILIERE"),
            _ligne_silver(2025, "1", variables_reelles, fili="NOUVELLE_FILIERE"),
        ],
    )

    table, _ = construire_table_apprentissage(fait, dim_formation, dim_profil, silver, variables_reelles)

    assert table.iloc[0]["fili"] == "NOUVELLE_FILIERE"


# ─── L'appartenance au classement de l'ADR 0013 ───────────────────────────


def test_toute_colonne_produite_relève_du_classement_licite(variables_reelles: VariablesConfig) -> None:
    """Aucune colonne produite n'échappe à `dimensions_cellule | session_courante | decalees`."""
    fait, dim_formation, dim_profil, silver = _entrees_minimales(
        variables_reelles,
        [
            _ligne_silver(2024, "1", variables_reelles),
            _ligne_silver(2025, "1", variables_reelles),
        ],
    )

    table, _ = construire_table_apprentissage(fait, dim_formation, dim_profil, silver, variables_reelles)

    identifiants_et_label = {
        "session",
        "cod_aff_form",
        "sk_formation",
        "sk_profil",
        "effectif",
        "taux",
        "taux_depasse_1",
    }
    colonnes_variables = set(table.columns) - identifiants_et_label
    licites = (
        set(variables_reelles.dimensions_cellule)
        | set(variables_reelles.session_courante)
        | set(variables_reelles.decalees)
    )
    assert colonnes_variables <= licites


def test_cod_uai_est_absent_du_jeu_construit(variables_reelles: VariablesConfig) -> None:
    """`cod_uai` est exclu (motif « substitut », ADR 0013 §5) : il ne doit jamais figurer en sortie."""
    assert variables_reelles.exclues["cod_uai"] == "substitut"
    fait, dim_formation, dim_profil, silver = _entrees_minimales(
        variables_reelles,
        [
            _ligne_silver(2024, "1", variables_reelles),
            _ligne_silver(2025, "1", variables_reelles),
        ],
    )

    table, _ = construire_table_apprentissage(fait, dim_formation, dim_profil, silver, variables_reelles)

    assert "cod_uai" not in table.columns


def test_aucune_colonne_de_genre_n_est_presente(variables_reelles: VariablesConfig) -> None:
    """Invariant du projet : le genre n'entre jamais dans le modèle (ADR 0011, ADR 0013 §4)."""
    for colonne in COLONNES_GENRE:
        assert variables_reelles.exclues[colonne] == "interdite"

    fait, dim_formation, dim_profil, silver = _entrees_minimales(
        variables_reelles,
        [
            _ligne_silver(2024, "1", variables_reelles),
            _ligne_silver(2025, "1", variables_reelles),
        ],
    )

    table, _ = construire_table_apprentissage(fait, dim_formation, dim_profil, silver, variables_reelles)

    assert not (set(table.columns) & set(COLONNES_GENRE))
