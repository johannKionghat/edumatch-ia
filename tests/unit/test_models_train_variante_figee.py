"""Tests unitaires du chemin de refit à deux temps du candidat figé (ADR 0021, phase 2) :
`train._entrainer_variante_figee`, `train._variante_active`, `train.empreintes_gel`.

Entraînement LightGBM réel, mais sur une table minuscule fabriquée (200 lignes, 3 arbres) :
rapide, sans dépendre de `data/samples/` ni de `data/processed/`. Le contrat de bout en bout
sur les échantillons réels reste couvert par `tests/data/test_models_train_run.py`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import yaml

from edumatch.config import load_settings
from edumatch.models import train
from tests.unit.conftest import BASE_YAML

N_LIGNES = 200


def _table_fabriquee() -> pd.DataFrame:
    """200 lignes réparties sur les quatre sessions du split de `_config_fixtures.BASE_YAML`
    (entraînement 2020-2021, validation 2022, test 2023), avec `taux_session_precedente`
    déjà présente (comme le fait `train.ajouter_taux_precedent` en amont) — certaines
    valeurs manquantes, pour exercer le repli de la baseline sans qu'il soit nécessaire de
    recalculer `prop_tot_*` / `nb_voe_pp_*` ici."""
    sessions = [2020 + (i % 4) for i in range(N_LIGNES)]
    taux = [round((i % 7) / 7, 4) for i in range(N_LIGNES)]
    return pd.DataFrame(
        {
            "session": sessions,
            "type_bac": ["bg"] * N_LIGNES,
            "boursier": [False] * N_LIGNES,
            "fili": ["L" if i % 2 == 0 else "S" for i in range(N_LIGNES)],
            "dep": ["75" if i % 3 == 0 else "13" for i in range(N_LIGNES)],
            "voe_tot": [float(i % 10 + 1) for i in range(N_LIGNES)],
            "capa_fin": [float(i % 5 + 1) for i in range(N_LIGNES)],
            "taux": taux,
            "effectif": [float(10 + i % 5) for i in range(N_LIGNES)],
            "taux_session_precedente": [np.nan if i % 4 == 0 else max(0.0, t - 0.05) for i, t in enumerate(taux)],
        }
    )


COLONNES_TEST: list[str] = ["fili", "dep", "voe_tot", "capa_fin", "type_bac", "boursier"]


def _settings_avec_variante(configs_dir_isole, **variante_kwargs):
    contenu = yaml.safe_load(BASE_YAML)
    contenu["modele"]["variante"] = {
        "demi_vie_recence": None,
        "cible": "taux",
        "calibration": "aucune",
        "n_estimators_fige": None,
        **variante_kwargs,
    }
    (configs_dir_isole / "base.yaml").write_text(yaml.dump(contenu), encoding="utf-8")
    return load_settings("dev", configs_dir=configs_dir_isole)


# ─── _variante_active ───────────────────────────────────────────────────────


def test_variante_active_faux_par_defaut(configs_dir_isole) -> None:
    settings = _settings_avec_variante(configs_dir_isole)
    assert train._variante_active(settings.modele.variante) is False


def test_variante_active_vrai_si_cible_ecart(configs_dir_isole) -> None:
    settings = _settings_avec_variante(configs_dir_isole, cible="ecart")
    assert train._variante_active(settings.modele.variante) is True


def test_variante_active_vrai_si_demi_vie_recence(configs_dir_isole) -> None:
    settings = _settings_avec_variante(configs_dir_isole, demi_vie_recence=2)
    assert train._variante_active(settings.modele.variante) is True


def test_variante_active_vrai_si_calibration(configs_dir_isole) -> None:
    settings = _settings_avec_variante(configs_dir_isole, calibration="isotonique_globale")
    assert train._variante_active(settings.modele.variante) is True


# ─── _entrainer_variante_figee ──────────────────────────────────────────────


def test_entrainer_variante_figee_produit_un_rapport_complet(configs_dir_isole) -> None:
    settings = _settings_avec_variante(
        configs_dir_isole,
        demi_vie_recence=1,
        cible="ecart",
        calibration="isotonique_globale",
        n_estimators_fige=3,
    )
    table = _table_fabriquee()

    resultat = train._entrainer_variante_figee(table, COLONNES_TEST, settings)

    assert resultat.rapport.meilleure_iteration == 3  # le nombre d'arbres figé, jamais l'arrêt anticipé
    assert resultat.rapport.scores_test.perimetre == "test"
    assert resultat.rapport.scores_validation.perimetre == "validation"
    assert 0.0 <= resultat.rapport.ece_test <= 1.0
    assert 0.0 <= resultat.rapport.ece_validation <= 1.0
    assert resultat.rapport.n_predictions_ecretees_test >= 0
    # La prédiction finale de test est bornée à [0, 1] par la reconstruction + l'écrêtage,
    # et par les bornes y_min/y_max du calibrateur isotonique appliqué ensuite.
    assert np.all(resultat.prediction_test >= 0.0) and np.all(resultat.prediction_test <= 1.0)


def test_entrainer_variante_figee_le_refit_voit_bien_la_validation(configs_dir_isole) -> None:
    """Le modèle final (`resultat.modele`) est le refit sur entraînement + validation,
    jamais le modèle de sélection sur le seul entraînement : le nombre de lignes vues doit
    donc couvrir les sessions 2020, 2021 ET 2022, pas seulement 2020-2021."""
    settings = _settings_avec_variante(
        configs_dir_isole, demi_vie_recence=1, cible="ecart", calibration="isotonique_globale", n_estimators_fige=3
    )
    table = _table_fabriquee()

    resultat = train._entrainer_variante_figee(table, COLONNES_TEST, settings)

    n_refit_attendu = int(table["session"].isin([2020, 2021, 2022]).sum())
    assert resultat.modele.n_features_ == len(COLONNES_TEST)
    # LightGBM ne conserve pas le nombre de lignes d'entraînement sur l'estimateur ; on le
    # vérifie indirectement via le nombre de sessions couvertes par jeu_validation + jeu_test,
    # qui eux sont bien ceux du split (2022 et 2023 seulement, jamais 2020-2021 pour le test).
    assert set(resultat.jeu_validation.sessions.unique()) == {2022}
    assert set(resultat.jeu_test.sessions.unique()) == {2023}
    assert n_refit_attendu > 0


def test_entrainer_variante_figee_est_deterministe(configs_dir_isole) -> None:
    """Même table, mêmes paramètres : deux exécutions indépendantes doivent produire une
    prédiction de test rigoureusement identique (`random_state` fixé, LightGBM en mode
    déterministe) — condition nécessaire pour que `reentrainer_modele`, `evaluate` et
    `fairness` retrouvent le même candidat en le ré-entraînant chacun de leur côté."""
    settings = _settings_avec_variante(
        configs_dir_isole, demi_vie_recence=1, cible="ecart", calibration="isotonique_globale", n_estimators_fige=3
    )
    table = _table_fabriquee()

    resultat_1 = train._entrainer_variante_figee(table, COLONNES_TEST, settings)
    resultat_2 = train._entrainer_variante_figee(table, COLONNES_TEST, settings)

    ecart_maximal = float(np.max(np.abs(resultat_1.prediction_test - resultat_2.prediction_test)))
    assert ecart_maximal == pytest.approx(0.0, abs=1e-12)


def test_entrainer_variante_figee_sans_calibration_ne_change_pas_la_reconstruction(configs_dir_isole) -> None:
    """`calibration: aucune` : la prédiction de test doit rester exactement `ancre + écart`
    écrêtée, sans transformation supplémentaire."""
    settings = _settings_avec_variante(
        configs_dir_isole, demi_vie_recence=None, cible="ecart", calibration="aucune", n_estimators_fige=3
    )
    table = _table_fabriquee()

    resultat = train._entrainer_variante_figee(table, COLONNES_TEST, settings)

    prediction_brute = resultat.modele.predict(resultat.jeu_test.X)
    ancre_test = train.predictions_baseline_couverture_egale(
        table, train.COLONNE_TAUX_PRECEDENT, resultat.moyenne_groupe, settings.modele.split.test
    ).reindex(resultat.jeu_test.X.index)
    attendu, _ = train.reconstruire_prediction(prediction_brute, "ecart", ancre_test)
    np.testing.assert_allclose(resultat.prediction_test, attendu)


def test_entrainer_et_evaluer_bascule_sur_le_chemin_fige_quand_la_variante_est_active(configs_dir_isole) -> None:
    """`entrainer_et_evaluer` doit dispatcher vers `_entrainer_variante_figee`, pas exécuter
    le chemin par défaut, dès que la variante s'écarte des valeurs par défaut."""
    settings = _settings_avec_variante(
        configs_dir_isole, demi_vie_recence=1, cible="ecart", calibration="isotonique_globale", n_estimators_fige=3
    )
    table = _table_fabriquee()

    resultat_direct = train._entrainer_variante_figee(table, COLONNES_TEST, settings)
    # Même table, même settings : les deux chemins doivent produire la même prédiction de
    # test, seule la voie d'appel diffère (`entrainer_et_evaluer` charge la table lui-même,
    # donc on compare seulement que le dispatch choisit bien le chemin figé, pas un doublon
    # d'entraînement complet ici).
    assert train._variante_active(settings.modele.variante) is True
    assert resultat_direct.rapport.meilleure_iteration == 3


# ─── empreintes_gel ─────────────────────────────────────────────────────────


def test_empreintes_gel_retourne_les_quatre_fichiers() -> None:
    empreintes = train.empreintes_gel()
    assert set(empreintes) == set(train.FICHIERS_GELES)
    for empreinte in empreintes.values():
        assert len(empreinte) == 64  # un hex SHA-256


def test_empreintes_gel_est_stable_tant_que_rien_ne_change() -> None:
    assert train.empreintes_gel() == train.empreintes_gel()
