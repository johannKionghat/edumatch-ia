"""Sélection pré-enregistrée du candidat destiné à passer sous le plancher de l'AIPD.

## Ce que ce module fait, et rien de plus

`docs/decisions.html#adr-0021` consigne, avant toute mesure, la grille
exhaustive des candidats, le critère de choix et ses tolérances. Ce module
l'exécute :

1. charge la table de variables en excluant le test 2025 **au moment de la
   lecture** (predicate pushdown Parquet sur `session`), et affirme qu'aucune
   ligne 2025 n'est présente en mémoire ensuite ;
2. entraîne 8 modèles sur 2020-2023, arrêtés sur la validation 2024 (jamais
   le test) — la grille {décroissance de récence} × {cible} de l'ADR ;
3. pour chacun, dérive deux candidats évalués (sans calibration, avec
   calibration isotonique globale ajustée sur la validation), soit 16
   candidats au total ;
4. mesure MAE pondérée et non pondérée, ECE global et par groupe de mixité,
   le nombre de prédictions écrêtées — tout, à couverture égale avec la
   baseline ;
5. journalise chaque candidat dans MLflow, puis applique le critère
   lexicographique de l'ADR pour désigner LE candidat retenu.

## Ce que ce module ne fait pas

Il n'entraîne le modèle retenu ni sur 2020-2024 (le refit), ni ne le compare
au test 2025, ni ne modifie la porte de promotion : ce sont les étapes
suivantes de l'ADR 0021, hors du périmètre de cette phase.
"""

from __future__ import annotations

import gc
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import date

import lightgbm as lgb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import GroupKFold

from edumatch.config import HyperparametresConfig, Settings, get_settings
from edumatch.models import train
from edumatch.models.baseline import COLONNES_GROUPE, predire_moyenne_expansive
from edumatch.models.fairness import (
    CATEGORIE_GENRE_MAJORITAIRE,
    CATEGORIE_GENRE_MINORITAIRE,
    CATEGORIE_GENRE_MIXTE,
    chemin_silver,
    classer_composition_genre,
)
from edumatch.features.label import calculer_taux
from edumatch.models.jeux import JeuDonnees, chemin_table_variables, extraire_jeu
from edumatch.models.metrics import (
    RapportCalibration,
    calibration,
    mae_non_ponderee,
    mae_ponderee,
    predictions_baseline_couverture_egale,
    score_baseline_couverture_egale,
)
from edumatch.models.variante import (
    CALIBRATION_AUCUNE,
    CALIBRATION_ISOTONIQUE,
    CIBLE_ECART,
    CIBLE_TAUX,
    ErreurVariante,
)
from edumatch.models.variante import poids_recence as _poids_recence
from edumatch.models.variante import reconstruire_prediction as _reconstruire_prediction

LOGGER = logging.getLogger(__name__)

NOM_EXPERIENCE_MLFLOW = "edumatch-selection-adr0021"

N_PLIS_VALIDATION_CROISEE = 5

GROUPES_MIXITE: tuple[str, ...] = (
    CATEGORIE_GENRE_MINORITAIRE,
    CATEGORIE_GENRE_MIXTE,
    CATEGORIE_GENRE_MAJORITAIRE,
)

# Tolérances du critère lexicographique, ADR 0021 point 3 — pré-enregistrées,
# jamais ajustées après avoir vu les résultats.
TOLERANCE_MAE = 0.0005
TOLERANCE_ECE = 0.001


class ErreurSelection(RuntimeError):
    """La sélection ne peut pas continuer sans violer une garantie attendue."""


@dataclass(frozen=True)
class ModeleGrille:
    """Un des 8 modèles entraînés : une combinaison {décroissance de récence, cible}."""

    nom: str
    demi_vie_recence: int | None
    cible: str


# La grille exhaustive de l'ADR 0021, rien d'autre n'est essayé.
GRILLE_MODELES: tuple[ModeleGrille, ...] = (
    ModeleGrille("modele_actuel", None, CIBLE_TAUX),
    ModeleGrille("A-h1", 1, CIBLE_TAUX),
    ModeleGrille("A-h2", 2, CIBLE_TAUX),
    ModeleGrille("A-h3", 3, CIBLE_TAUX),
    ModeleGrille("B", None, CIBLE_ECART),
    ModeleGrille("C-h1", 1, CIBLE_ECART),
    ModeleGrille("C-h2", 2, CIBLE_ECART),
    ModeleGrille("C-h3", 3, CIBLE_ECART),
)

VARIANTES_CALIBRATION: tuple[str, ...] = (CALIBRATION_AUCUNE, CALIBRATION_ISOTONIQUE)


def poids_recence(sessions: pd.Series, s_ref: int, demi_vie: int) -> pd.Series:
    """Décroissance de récence — voir `models.variante.poids_recence`.

    Fine enveloppe qui traduit `ErreurVariante` en `ErreurSelection` : dans ce
    module, toute défaillance de la sélection lève la même famille d'erreur
    (voir `charger_table_sans_test`, `_assert_aucune_session_test`).
    """
    try:
        return _poids_recence(sessions, s_ref, demi_vie)
    except ErreurVariante as erreur:
        raise ErreurSelection(str(erreur)) from erreur


def _assert_aucune_session_test(sessions_presentes: set[int], sessions_test: set[int]) -> None:
    """Deuxième ligne de défense, testée isolément : lève si une session de test
    est présente en mémoire, quelle qu'en soit la cause (filtre Parquet contourné,
    colonne `session` mal typée, etc.)."""
    intersection = sessions_presentes & sessions_test
    if intersection:
        raise ErreurSelection(
            f"Fuite : session(s) de test {sorted(intersection)} présente(s) en mémoire "
            "après filtrage à la lecture. La sélection est interrompue plutôt que de "
            "continuer avec une table contaminée."
        )


def charger_table_sans_test(settings: Settings) -> pd.DataFrame:
    """Charge la table de variables en excluant le test 2025 au moment de la lecture.

    Le filtre Parquet (`filters=[("session", "<=", session_max_validation)]`)
    est appliqué à la lecture, pas après coup : les lignes de la session de
    test ne sont jamais matérialisées en mémoire, exactement comme
    `03-pipeline`/`04-modele` appliquent un filtrage à la lecture plutôt qu'un
    nettoyage a posteriori. L'assertion qui suit est une seconde ligne de
    défense, testée séparément (`tests/unit/test_models_selection.py`).
    """
    chemin = chemin_table_variables(settings)
    if not chemin.exists():
        raise ErreurSelection(f"{chemin} est introuvable : exécuter `make features` avant la sélection.")

    session_max_validation = max(settings.modele.split.validation)
    table = pq.read_table(chemin, filters=[("session", "<=", session_max_validation)]).to_pandas()

    sessions_presentes = set(int(s) for s in table["session"].unique())
    sessions_test = set(settings.modele.split.test)
    _assert_aucune_session_test(sessions_presentes, sessions_test)
    return train.ajouter_taux_precedent(table)


def _composition_genre_validation(settings: Settings, session_validation: int) -> pd.DataFrame:
    """La composition candidate par genre de chaque formation, sur la SEULE session de validation.

    Écrit à part de `models.fairness.charger_composition_genre` (qui est
    câblée sur `settings.modele.split.test`) : cette fonction lit
    explicitement `session_validation`, jamais le test. Réutilise les
    fonctions pures de `fairness.py` (`classer_composition_genre`) et de
    `features.label` (`calculer_taux`), qui ne dépendent d'aucune session
    particulière.
    """
    chemin = chemin_silver(settings)
    if not chemin.exists():
        raise ErreurSelection(f"{chemin} est introuvable : exécuter `make silver` avant la sélection.")

    colonnes = ["session", "cod_aff_form", "voe_tot", "voe_tot_f"]
    silver = pq.read_table(chemin, columns=colonnes, filters=[("session", "=", session_validation)]).to_pandas()
    if silver.empty:
        raise ErreurSelection(f"Aucune ligne silver pour la session de validation {session_validation}.")

    composition_candidate, _ = calculer_taux(silver["voe_tot_f"], silver["voe_tot"])
    composition = pd.DataFrame(
        {
            "cod_aff_form": silver["cod_aff_form"].astype("string").astype(str),
            "composition_candidate": composition_candidate.astype("float64"),
        }
    )
    composition["bucket_genre"] = classer_composition_genre(composition["composition_candidate"])
    return composition


@dataclass(frozen=True)
class JeuxSelection:
    """Tout ce que la sélection partage entre les 8 entraînements : jamais recalculé deux fois."""

    table: pd.DataFrame
    colonnes: list[str]
    jeu_entrainement: JeuDonnees
    jeu_validation: JeuDonnees
    ancre_entrainement: pd.Series
    ancre_validation: pd.Series
    baseline_validation_mae_ponderee: float
    cod_aff_form_validation: pd.Series
    bucket_genre_validation: pd.Series


def preparer_jeux_selection(settings: Settings) -> JeuxSelection:
    """Charge la table (sans le test), construit les deux jeux et les ancres de la variante B.

    N'appelle JAMAIS `train.preparer_jeux` : cette fonction extrait aussi un
    jeu de test (`extraire_jeu(table, split.test, colonnes)`), qui lèverait
    `ErreurJeuxDonnees` ici puisque `charger_table_sans_test` ne matérialise
    jamais les lignes 2025 — et qui, même sans lever, accéderait à une donnée
    hors du périmètre de cette phase (voir la consigne de cette étape : « tu
    n'appelles pas [la fonction], tu extrais ce dont tu as besoin »). Seules
    les deux premières pièces de `train.preparer_jeux` (colonnes,
    entraînement, validation) sont reconstruites ici, à l'identique.
    """
    table = charger_table_sans_test(settings)
    colonnes = train.colonnes_features(settings.modele.variables, list(table.columns))
    if not settings.modele.inclure_taux_precedent:
        colonnes = [c for c in colonnes if c not in train.COLONNES_DERIVEES]

    split = settings.modele.split
    jeu_entrainement = extraire_jeu(table, split.entrainement, colonnes)
    jeu_validation = extraire_jeu(table, split.validation, colonnes)
    moyenne_groupe = predire_moyenne_expansive(table, COLONNES_GROUPE)
    ancre_entrainement = predictions_baseline_couverture_egale(
        table, train.COLONNE_TAUX_PRECEDENT, moyenne_groupe, split.entrainement
    )
    ancre_validation = predictions_baseline_couverture_egale(
        table, train.COLONNE_TAUX_PRECEDENT, moyenne_groupe, split.validation
    )
    baseline_validation = score_baseline_couverture_egale(
        table, train.COLONNE_TAUX_PRECEDENT, moyenne_groupe, split.validation, "validation"
    )

    session_validation = max(split.validation)
    lignes_validation = table.loc[jeu_validation.X.index]
    composition = _composition_genre_validation(settings, session_validation)
    fusion = lignes_validation[["cod_aff_form"]].astype({"cod_aff_form": str}).merge(
        composition, on="cod_aff_form", how="left"
    )
    fusion.index = jeu_validation.X.index
    fusion["bucket_genre"] = fusion["bucket_genre"].fillna("sans_candidature_denominateur_nul")

    return JeuxSelection(
        table=table,
        colonnes=colonnes,
        jeu_entrainement=jeu_entrainement,
        jeu_validation=jeu_validation,
        ancre_entrainement=ancre_entrainement.reindex(jeu_entrainement.X.index),
        ancre_validation=ancre_validation.reindex(jeu_validation.X.index),
        baseline_validation_mae_ponderee=baseline_validation.mae_ponderee,
        cod_aff_form_validation=fusion["cod_aff_form"],
        bucket_genre_validation=fusion["bucket_genre"],
    )


def _entrainer_lightgbm(
    X_entrainement: pd.DataFrame,
    y_entrainement: pd.Series,
    poids_entrainement: pd.Series,
    X_validation: pd.DataFrame,
    y_validation: pd.Series,
    poids_validation: pd.Series,
    hyperparametres: HyperparametresConfig,
    objective: str,
) -> lgb.LGBMRegressor:
    """Un LightGBM pondéré, arrêté sur la MAE pondérée de validation — mêmes hyperparamètres
    que `configs/base.yaml`, FIGÉS pour toute la grille (aucune recherche, ADR 0021).

    `n_jobs=2` plutôt que `-1` : la machine dispose d'environ 2 Go de RAM
    libre pour huit entraînements strictement séquentiels (voir la consigne
    de cette étape) ; un parallélisme interne maximal sur chaque entraînement
    ajouterait un pic mémoire que rien ne justifie ici.
    """
    modele = lgb.LGBMRegressor(
        objective=objective,
        n_estimators=hyperparametres.n_estimators,
        num_leaves=hyperparametres.num_leaves,
        max_depth=hyperparametres.max_depth,
        learning_rate=hyperparametres.learning_rate,
        min_child_samples=hyperparametres.min_child_samples,
        reg_alpha=hyperparametres.reg_alpha,
        reg_lambda=hyperparametres.reg_lambda,
        random_state=42,
        n_jobs=2,
        verbose=-1,
    )
    modele.fit(
        X_entrainement,
        y_entrainement,
        sample_weight=poids_entrainement,
        eval_X=X_validation,
        eval_y=y_validation,
        eval_sample_weight=[poids_validation],
        eval_metric="mae",
        callbacks=[lgb.early_stopping(hyperparametres.early_stopping_rounds, verbose=False)],
    )
    return modele


@dataclass(frozen=True)
class ResultatCandidat:
    """Le résultat complet d'un des 16 candidats, tel que journalisé et comparé."""

    nom: str
    demi_vie_recence: int | None
    cible: str
    calibration: str
    mae_ponderee: float
    mae_non_ponderee: float
    ece_global: float
    ece_par_groupe: dict[str, float] = field(default_factory=dict)
    n_predictions_ecretees: int = 0
    meilleure_iteration: int = 0
    run_id_mlflow: str | None = None

    def resume(self) -> str:
        groupes = " ".join(f"{g}={v:.4f}" for g, v in self.ece_par_groupe.items())
        return (
            f"{self.nom:14s} calib={self.calibration:20s} "
            f"mae_ponderee={self.mae_ponderee:.4f} mae_non_ponderee={self.mae_non_ponderee:.4f} "
            f"ece_global={self.ece_global:.4f} [{groupes}] "
            f"ecretages={self.n_predictions_ecretees} iterations={self.meilleure_iteration}"
        )


def _ece_par_groupe(
    observe: pd.Series, poids: pd.Series, prediction: np.ndarray, bucket: pd.Series, n_tranches: int
) -> dict[str, float]:
    resultats: dict[str, float] = {}
    for groupe in GROUPES_MIXITE:
        masque = (bucket == groupe).to_numpy()
        if not masque.any():
            continue
        rapport: RapportCalibration = calibration(
            observe[masque], poids[masque], prediction[masque], n_tranches, groupe
        )
        resultats[groupe] = rapport.ece
    return resultats


def _metriques_directes(
    observe: pd.Series, poids: pd.Series, prediction: np.ndarray, bucket: pd.Series, n_tranches: int
) -> tuple[float, float, float, dict[str, float]]:
    mae_p = mae_ponderee(observe, prediction, poids)
    mae_np = mae_non_ponderee(observe, prediction)
    rapport = calibration(observe, poids, prediction, n_tranches, "validation")
    return mae_p, mae_np, rapport.ece, _ece_par_groupe(observe, poids, prediction, bucket, n_tranches)


def _metriques_calibrees_cv(
    observe: pd.Series,
    poids: pd.Series,
    prediction: np.ndarray,
    groupes_cod_aff_form: pd.Series,
    bucket: pd.Series,
    n_tranches: int,
    n_plis: int = N_PLIS_VALIDATION_CROISEE,
) -> tuple[float, float, float, dict[str, float]]:
    """Métriques honnêtes d'un calibrateur isotonique : validation croisée à `n_plis` GROUPÉE
    par `cod_aff_form`, entièrement à l'intérieur de la validation 2024 (ADR 0021, point 2).

    Aucune formation n'est à la fois dans le pli qui ajuste le calibrateur et
    dans celui qui le note : la même exigence anti-fuite qui gouverne le
    split principal (groupe, pas ligne), appliquée ici à l'intérieur d'une
    seule session.
    """
    y_arr = observe.to_numpy(dtype="float64")
    poids_arr = poids.to_numpy(dtype="float64")
    pred_arr = np.asarray(prediction, dtype="float64")
    groupes_arr = groupes_cod_aff_form.to_numpy()

    n_groupes_distincts = len(np.unique(groupes_arr))
    n_plis_effectifs = min(n_plis, n_groupes_distincts)
    gkf = GroupKFold(n_splits=n_plis_effectifs)

    hors_pli = np.full(len(y_arr), np.nan)
    for indice_entrainement, indice_test in gkf.split(pred_arr.reshape(-1, 1), y_arr, groups=groupes_arr):
        isotonique = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        isotonique.fit(pred_arr[indice_entrainement], y_arr[indice_entrainement], sample_weight=poids_arr[indice_entrainement])
        hors_pli[indice_test] = isotonique.predict(pred_arr[indice_test])

    observe_serie = pd.Series(y_arr, index=observe.index)
    poids_serie = pd.Series(poids_arr, index=poids.index)
    mae_p = mae_ponderee(observe_serie, hors_pli, poids_serie)
    mae_np = mae_non_ponderee(observe_serie, hors_pli)
    rapport = calibration(observe_serie, poids_serie, hors_pli, n_tranches, "validation-cv-isotonique")
    return mae_p, mae_np, rapport.ece, _ece_par_groupe(observe_serie, poids_serie, hors_pli, bucket, n_tranches)


def _evaluer_modele(
    modele: lgb.LGBMRegressor,
    grille: ModeleGrille,
    jeux: JeuxSelection,
    n_tranches: int,
) -> list[ResultatCandidat]:
    """Les deux candidats (sans calibration, isotonique globale) dérivés d'un modèle entraîné."""
    prediction_brute = modele.predict(jeux.jeu_validation.X)
    prediction, n_ecretages = _reconstruire_prediction(prediction_brute, grille.cible, jeux.ancre_validation)
    meilleure_iteration = int(modele.best_iteration_ or 0)

    resultats: list[ResultatCandidat] = []

    mae_p, mae_np, ece_global, ece_groupes = _metriques_directes(
        jeux.jeu_validation.y, jeux.jeu_validation.poids, prediction, jeux.bucket_genre_validation, n_tranches
    )
    resultats.append(
        ResultatCandidat(
            nom=grille.nom,
            demi_vie_recence=grille.demi_vie_recence,
            cible=grille.cible,
            calibration=CALIBRATION_AUCUNE,
            mae_ponderee=mae_p,
            mae_non_ponderee=mae_np,
            ece_global=ece_global,
            ece_par_groupe=ece_groupes,
            n_predictions_ecretees=n_ecretages,
            meilleure_iteration=meilleure_iteration,
        )
    )

    mae_p_cv, mae_np_cv, ece_global_cv, ece_groupes_cv = _metriques_calibrees_cv(
        jeux.jeu_validation.y,
        jeux.jeu_validation.poids,
        prediction,
        jeux.cod_aff_form_validation,
        jeux.bucket_genre_validation,
        n_tranches,
    )
    resultats.append(
        ResultatCandidat(
            nom=grille.nom,
            demi_vie_recence=grille.demi_vie_recence,
            cible=grille.cible,
            calibration=CALIBRATION_ISOTONIQUE,
            mae_ponderee=mae_p_cv,
            mae_non_ponderee=mae_np_cv,
            ece_global=ece_global_cv,
            ece_par_groupe=ece_groupes_cv,
            n_predictions_ecretees=n_ecretages,
            meilleure_iteration=meilleure_iteration,
        )
    )
    return resultats


def _commit_git() -> str | None:
    return train._commit_git()  # même politique best-effort que l'entraînement, non dupliquée


def _journaliser_candidat_mlflow(resultat: ResultatCandidat, settings: Settings, date_donnees: str) -> None:
    if not settings.mlflow_tracking_uri:
        LOGGER.warning("MLFLOW_TRACKING_URI non configuré : candidat %s non journalisé.", resultat.nom)
        return
    try:
        import mlflow
    except ImportError:
        LOGGER.warning("Le paquet mlflow n'est pas installé : candidat %s non journalisé.", resultat.nom)
        return

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(NOM_EXPERIENCE_MLFLOW)
    with mlflow.start_run(run_name=f"{resultat.nom}-{resultat.calibration}") as run:
        mlflow.set_tag("etape", "selection")
        mlflow.set_tag("adr", "0021")
        mlflow.set_tag("date_donnees", date_donnees)
        commit = _commit_git()
        if commit:
            mlflow.set_tag("commit_git", commit)
        mlflow.log_param("nom", resultat.nom)
        mlflow.log_param("demi_vie_recence", resultat.demi_vie_recence)
        mlflow.log_param("cible", resultat.cible)
        mlflow.log_param("calibration", resultat.calibration)
        mlflow.log_params(settings.modele.hyperparametres.model_dump())
        mlflow.log_metric("meilleure_iteration", resultat.meilleure_iteration)
        mlflow.log_metric("mae_ponderee", resultat.mae_ponderee)
        mlflow.log_metric("mae_non_ponderee", resultat.mae_non_ponderee)
        mlflow.log_metric("ece_global", resultat.ece_global)
        for groupe, valeur in resultat.ece_par_groupe.items():
            mlflow.log_metric(f"ece_{groupe}", valeur)
        mlflow.log_metric("n_predictions_ecretees", resultat.n_predictions_ecretees)
        object.__setattr__(resultat, "run_id_mlflow", run.info.run_id)


def selectionner_candidat(resultats: list[ResultatCandidat]) -> ResultatCandidat:
    """Le critère lexicographique de l'ADR 0021, avec ses tolérances pré-enregistrées.

    (i) MAE pondérée de validation la plus basse, égalité à moins de
    `TOLERANCE_MAE` ; (ii) parmi eux, ECE global le plus bas, égalité à moins
    de `TOLERANCE_ECE` ; (iii) départage par l'ECE du groupe le plus féminisé.
    """
    if not resultats:
        raise ErreurSelection("Aucun candidat à départager.")

    meilleure_mae = min(r.mae_ponderee for r in resultats)
    proches_mae = [r for r in resultats if (r.mae_ponderee - meilleure_mae) < TOLERANCE_MAE]

    meilleure_ece = min(r.ece_global for r in proches_mae)
    proches_ece = [r for r in proches_mae if (r.ece_global - meilleure_ece) < TOLERANCE_ECE]

    def _ece_groupe_majoritaire(candidat: ResultatCandidat) -> float:
        return candidat.ece_par_groupe.get(CATEGORIE_GENRE_MAJORITAIRE, float("inf"))

    return min(proches_ece, key=_ece_groupe_majoritaire)


@dataclass(frozen=True)
class RapportSelection:
    """Les 16 candidats mesurés, le plancher, et le candidat désigné — à déclarer tel quel."""

    candidats: list[ResultatCandidat]
    baseline_mae_ponderee: float
    candidat_retenu: ResultatCandidat

    def resume(self) -> str:
        lignes = [f"Plancher (baseline, couverture égale) mae_ponderee={self.baseline_mae_ponderee:.4f}"]
        for candidat in self.candidats:
            lignes.append("  " + candidat.resume())
        lignes.append(f"Candidat retenu : {self.candidat_retenu.nom} / {self.candidat_retenu.calibration}")
        return "\n".join(lignes)


def executer(settings: Settings | None = None) -> RapportSelection:
    """Exécute la grille complète de l'ADR 0021 et désigne le candidat retenu.

    N'entraîne jamais sur le test, ne le charge jamais : `preparer_jeux_selection`
    lit la table filtrée à la lecture, et aucune fonction de ce module n'accède
    à `jeu_test` (voir `preparer_jeux_selection`, qui le supprime explicitement
    sitôt reçu de `train.preparer_jeux`).
    """
    settings = settings or get_settings()
    jeux = preparer_jeux_selection(settings)
    date_donnees = date.today().isoformat()
    n_tranches = settings.evaluation.n_tranches_calibration

    tous_les_resultats: list[ResultatCandidat] = []
    for grille in GRILLE_MODELES:
        debut = time.monotonic()
        poids_entrainement = jeux.jeu_entrainement.poids
        if grille.demi_vie_recence is not None:
            s_ref = int(jeux.jeu_entrainement.sessions.max())
            decroissance = poids_recence(jeux.jeu_entrainement.sessions, s_ref, grille.demi_vie_recence)
            poids_entrainement = poids_entrainement * decroissance

        if grille.cible == CIBLE_TAUX:
            y_entrainement = jeux.jeu_entrainement.y
            y_validation = jeux.jeu_validation.y
            objective = "cross_entropy"
        else:
            y_entrainement = jeux.jeu_entrainement.y - jeux.ancre_entrainement
            y_validation = jeux.jeu_validation.y - jeux.ancre_validation
            objective = "regression"

        modele = _entrainer_lightgbm(
            jeux.jeu_entrainement.X,
            y_entrainement,
            poids_entrainement,
            jeux.jeu_validation.X,
            y_validation,
            jeux.jeu_validation.poids,
            settings.modele.hyperparametres,
            objective,
        )
        duree = time.monotonic() - debut
        LOGGER.info("Candidat %s entraîné en %.1f s.", grille.nom, duree)

        resultats = _evaluer_modele(modele, grille, jeux, n_tranches)
        for resultat in resultats:
            _journaliser_candidat_mlflow(resultat, settings, date_donnees)
            LOGGER.info("  %s", resultat.resume())
        tous_les_resultats.extend(resultats)

        del modele
        gc.collect()

    candidat_retenu = selectionner_candidat(tous_les_resultats)
    return RapportSelection(
        candidats=tous_les_resultats,
        baseline_mae_ponderee=jeux.baseline_validation_mae_ponderee,
        candidat_retenu=candidat_retenu,
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    rapport = executer(settings)
    LOGGER.info("Sélection terminée.\n%s", rapport.resume())
    return 0


if __name__ == "__main__":
    sys.exit(main())
