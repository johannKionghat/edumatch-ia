"""Test du point d'entrée `make ablation` (E27), de bout en bout, sur les échantillons.

Même schéma que `test_models_fairness_run.py` (E26) : un `data_root` jetable,
silver (E15), gold (E16) et la table de variables (E20) produits depuis les
huit échantillons versionnés, puis `edumatch.models.ablation` dessus.

`ablation.executer` entraîne sept LightGBM (une par variante) et reconstruit
deux fois la table de variables (mentions, `cod_uai`) : coûteux à répéter,
donc calculé **une seule fois par module** (`scope="module"`) et partagé par
toutes les assertions, plutôt qu'une fixture par fonction de test.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from edumatch.config import Settings, load_settings
from edumatch.features import build
from edumatch.models import ablation, fairness
from edumatch.models.train import ErreurEntrainement
from edumatch.transform import run, run_etoile

NOMS_VARIANTES_ATTENDUS = (
    "modele_complet",
    "sans_decalees",
    "sans_taux_precedent",
    "taux_precedent_seul",
    "mentions_incluses",
    "cod_uai_reintroduit",
    "sans_substituts_genre",
)


@pytest.fixture(scope="module")
def settings_avec_variables(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    tmp_path = tmp_path_factory.mktemp("ablation-e27")
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path, "mlflow_tracking_uri": None})
    dossier_raw = settings.raw_dir / "parcoursup"
    dossier_raw.mkdir(parents=True)
    for millesime in settings.donnees.parcoursup.millesimes:
        source = base.samples_dir / "parcoursup" / f"parcoursup_{millesime}.csv"
        shutil.copy(source, dossier_raw / f"parcoursup_{millesime}.csv")
    run.executer(settings)
    run_etoile.executer(settings)
    build.executer(settings)
    return settings


@pytest.fixture(scope="module", autouse=True)
def seuil_fiabilite_abaisse() -> None:
    """Sur l'échantillon, aucun groupe n'atteint 30 cellules (voir test_models_fairness_run.py) :
    sans cet abaissement, `ratio_impact_disparate_dimension` lèverait faute de groupe fiable.
    """
    valeur_defaut = fairness.N_CELLULES_MIN_FIABLE
    fairness.N_CELLULES_MIN_FIABLE = 1
    yield
    fairness.N_CELLULES_MIN_FIABLE = valeur_defaut


@pytest.fixture(scope="module")
def rapport(settings_avec_variables: Settings) -> ablation.RapportAblation:
    return ablation.executer(settings_avec_variables)


def test_executer_produit_les_sept_variantes_dans_l_ordre(rapport: ablation.RapportAblation) -> None:
    assert tuple(variante.nom for variante in rapport.variantes) == NOMS_VARIANTES_ATTENDUS


def test_le_modele_complet_est_l_ancrage_a_ecart_nul(rapport: ablation.RapportAblation) -> None:
    reference = rapport.variantes[0]
    assert reference.nom == "modele_complet"
    assert reference.ecart_mae_vs_complet == 0.0
    assert reference.mae_validation >= 0.0


def test_chaque_variante_rapporte_un_score_positif(rapport: ablation.RapportAblation) -> None:
    for variante in rapport.variantes:
        assert variante.mae_validation >= 0.0
        assert variante.ece_validation >= 0.0
        assert variante.n_variables > 0
        assert variante.commentaire  # jamais un écart tu, même nul


def test_sans_decalees_retire_bien_les_decalees_et_le_taux_precedent(
    rapport: ablation.RapportAblation, settings_avec_variables: Settings
) -> None:
    reference = next(v for v in rapport.variantes if v.nom == "modele_complet")
    variante = next(v for v in rapport.variantes if v.nom == "sans_decalees")
    variables = settings_avec_variables.modele.variables
    # taux_session_precedente + a_antecedent en plus des 35 décalées : 37 colonnes de moins.
    assert variante.n_variables == reference.n_variables - len(variables.decalees) - 2


def test_taux_precedent_seul_ne_garde_que_les_dimensions_et_le_taux(
    rapport: ablation.RapportAblation, settings_avec_variables: Settings
) -> None:
    variante = next(v for v in rapport.variantes if v.nom == "taux_precedent_seul")
    variables = settings_avec_variables.modele.variables
    assert variante.n_variables == len(variables.dimensions_cellule) + 1


def test_mentions_incluses_ajoute_les_huit_colonnes_de_mention(
    rapport: ablation.RapportAblation, settings_avec_variables: Settings
) -> None:
    reference = next(v for v in rapport.variantes if v.nom == "modele_complet")
    variante = next(v for v in rapport.variantes if v.nom == "mentions_incluses")
    variables = settings_avec_variables.modele.variables
    assert variante.n_variables == reference.n_variables + len(variables.decalees_sous_reserve)


def test_cod_uai_reintroduit_ajoute_une_seule_colonne(rapport: ablation.RapportAblation) -> None:
    reference = next(v for v in rapport.variantes if v.nom == "modele_complet")
    variante = next(v for v in rapport.variantes if v.nom == "cod_uai_reintroduit")
    assert variante.n_variables == reference.n_variables + 1


def test_sans_substituts_genre_retire_les_quatre_substituts(rapport: ablation.RapportAblation) -> None:
    reference = next(v for v in rapport.variantes if v.nom == "modele_complet")
    variante = next(v for v in rapport.variantes if v.nom == "sans_substituts_genre")
    assert variante.n_variables == reference.n_variables - 4


def test_le_genre_n_entre_dans_aucune_variante(rapport: ablation.RapportAblation) -> None:
    """Invariant du projet, vérifié même en ablation : aucune variante ne peut nommer le genre."""
    for variante in rapport.variantes:
        assert "genre" not in variante.description.lower() or "substitut" in variante.description.lower()


def test_l_equite_genre_est_mesuree_avec_et_sans_substituts(rapport: ablation.RapportAblation) -> None:
    equite = rapport.equite_genre
    assert equite.ratio_avec_substituts.dimension == "genre"
    assert equite.ratio_sans_substituts.dimension == "genre"
    assert equite.ventilation_avec_substituts
    assert equite.ventilation_sans_substituts


def test_le_score_de_test_de_la_configuration_retenue_est_celui_deja_journalise_par_e22(
    rapport: ablation.RapportAblation, settings_avec_variables: Settings
) -> None:
    """`ablation.executer` ne doit jamais recalculer le test séparément : même modèle, même score."""
    from edumatch.models import train

    _, rapport_train = train.executer(settings_avec_variables)
    assert rapport.scores_test_configuration_retenue.mae_ponderee == pytest.approx(
        rapport_train.scores_test.mae_ponderee
    )


def test_sirene_est_declaree_impossible_a_mesurer_pas_simulee(rapport: ablation.RapportAblation) -> None:
    assert "impossible" in rapport.declaration_sirene.lower()
    assert "NAF" in rapport.declaration_sirene


def test_resume_ne_leve_pas_et_cite_les_sept_variantes(rapport: ablation.RapportAblation) -> None:
    texte = rapport.resume()
    for nom in NOMS_VARIANTES_ATTENDUS:
        assert nom in texte


def test_executer_ne_journalise_pas_dans_mlflow_sans_tracking_uri(
    settings_avec_variables: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING"):
        ablation.executer(settings_avec_variables)
    assert any("MLFLOW_TRACKING_URI" in message for message in caplog.messages)


def test_source_gold_absente_leve_une_erreur_explicite(tmp_path: Path) -> None:
    base = load_settings("prod")
    settings = base.model_copy(update={"data_root": tmp_path})
    with pytest.raises(ErreurEntrainement):  # table de variables (E20) absente
        ablation.executer(settings)
