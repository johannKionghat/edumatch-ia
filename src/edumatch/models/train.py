"""Entraînement du modèle d'accessibilité (E22) : LightGBM pondéré, tracé dans MLflow.

## Ce que ce module fait, et rien de plus

`features/build.py` (E20) a produit la table de variables, une ligne par
cellule `(session, formation, type de baccalauréat, boursier)`, avec son
label (`taux`) et son effectif (`effectif`). Ce module :

1. sépare cette table selon le split **strictement temporel** arrêté par
   l'ADR 0012 (`modele.split`) — entraînement 2020-2023, validation 2024,
   test 2025 ;
2. entraîne un LightGBM pondéré par l'effectif de la cellule
   (`features.label.poids_effectif`, ADR 0009), arrêté sur la MAE pondérée
   de validation — jamais sur le test ;
3. journalise l'exécution dans MLflow : hyperparamètres, métriques, commit
   Git, modèle en artefact.

Le test 2025 n'est touché qu'une fois, à la fin, avec les hyperparamètres déjà
arrêtés par `configs/base.yaml` — jamais pour choisir entre configurations
(recherche conduite exclusivement sur la validation 2024, voir
`HYPERPARAMETRES_EXPLORES` plus bas).

## Le plancher, comparé à couverture égale, et le taux précédent comme variable

`RapportEntrainement.baseline_validation` / `.baseline_test` mesurent le
plancher E21 (`session_precedente_avec_repli`) sur EXACTEMENT le périmètre du
modèle (100 % des cellules) : le juger à couverture partielle exagérerait
l'écart, voir `HYPERPARAMETRES_EXPLORES` pour les chiffres. `ajouter_taux_precedent`
calcule ce même plancher (sans repli, `a_antecedent` signale l'absence) et le
donne en plus au modèle comme variable, plutôt que comme seul concurrent
(`modele.inclure_taux_precedent`) : un ensemble d'arbres n'apprend pas
nativement une division, il doit l'approximer par des coupures successives
sur le numérateur et le dénominateur, déjà présents séparément.

## Le choix des variables : liste blanche, pas de fuite

Les colonnes passées au modèle sont exactement celles que `modele.variables`
(ADR 0013) classe comme licites — les deux dimensions de la cellule, les
neuf colonnes de catalogue de la session prédite, et les colonnes décalées
d'une session. Clés, cible et poids sont exclus explicitement
(`COLONNES_NON_FEATURES`) ; le genre n'apparaît dans aucune catégorie licite
(ADR 0011) : il n'a donc jamais l'occasion d'entrer ici. `colonnes_features`
refuse de continuer si la table porte une colonne non classée nulle part —
même défense en profondeur que `features.build._verifier_colonnes_licites`,
appliquée ici à la frontière suivante de la chaîne.

## Le type des variables, et pourquoi LightGBM plutôt qu'un réseau

`preparer_matrice` convertit les types nullables Pandas issus de Parquet
(`Int64`, `Float64`, `string`, `boolean`) en `float64` (absence -> `NaN`) ou
en `category` (LightGBM les traite nativement, sans encodage one-hot qui
ferait exploser la dimension pour une colonne à forte cardinalité).
LightGBM plutôt qu'un réseau de neurones, pour la même raison qu'à l'étape
de conception (`04-modele/specification.md`) : données tabulaires et
hétérogènes, valeurs manquantes structurelles (ADR 0013 §6) — un réseau
n'apporterait rien sur ce volume (286 463 cellules d'entraînement) et
coûterait l'explicabilité exacte que permet TreeSHAP (E25).
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from edumatch.config import HyperparametresConfig, Settings, VariablesConfig, get_settings
from edumatch.features.build import NOM_FICHIER_VARIABLES, SOUS_DOSSIER
from edumatch.features.label import poids_effectif
from edumatch.models.baseline import (
    COLONNES_GROUPE as _COLONNES_GROUPE_BASELINE,
)
from edumatch.models.baseline import predire_moyenne_expansive, predire_session_precedente
from edumatch.models.metrics import ScoreSession, classement_importance, score, score_baseline_couverture_egale

LOGGER = logging.getLogger(__name__)

NOM_EXPERIENCE_MLFLOW = "edumatch-accessibilite"

# Clés, cible et poids : jamais des variables explicatives (voir docstring du module).
COLONNES_NON_FEATURES: tuple[str, ...] = (
    "session",
    "cod_aff_form",
    "sk_formation",
    "sk_profil",
    "effectif",
    "taux",
    "taux_depasse_1",
)

# ─── Le taux de la session précédente comme variable explicite ─────────────
#
# `prop_tot_{cat}` et `nb_voe_pp_{cat}` (colonnes décalées, ADR 0013 §2) sont
# déjà des variables licites du modèle : le numérateur et le dénominateur du
# taux de la baseline (E21) sont donc déjà visibles, séparément, par cellule.
# Un ensemble d'arbres n'apprend pas nativement une division ; il l'approxime
# par des coupures successives, ce qui coûte de la précision sur la relation
# la plus forte du problème. `ajouter_taux_precedent` calcule le quotient une
# fois pour toutes et le donne comme variable à part entière — la baseline
# devient une entrée du modèle plutôt qu'un concurrent séparé.
COLONNE_TAUX_PRECEDENT = "taux_session_precedente"
COLONNE_A_ANTECEDENT = "a_antecedent"
COLONNES_DERIVEES: tuple[str, ...] = (COLONNE_TAUX_PRECEDENT, COLONNE_A_ANTECEDENT)

# ─── La recherche d'hyperparamètres qui a arrêté configs/base.yaml ──────────
#
# Conduite une seule fois, en dehors de ce module (script d'exploration non
# versionné), sur la table de variables réelle (`data/processed/`), en
# respectant le protocole : chaque candidat entraîné sur 2020-2023, jugé sur
# la MAE de la seule validation 2024, le test 2025 jamais consulté pendant
# la comparaison. Pour aller vite pendant la recherche, ces quatre essais
# utilisent la perte L2 et une MAE de validation **non pondérée** comme
# critère d'arrêt anticipé (comparaison relative entre candidats, donc
# insensible à ce choix) ; l'exécution retenue plus bas, elle, s'arrête sur
# la MAE **pondérée**, celle que retient `evaluation.metrique_principale`
# (`configs/base.yaml`) — d'où un léger écart entre les deux séries de
# chiffres.
#
# Quatre candidats, capacité poussée jusqu'à ce que le meilleur essai cesse de
# toucher la borne de `n_estimators` (signe qu'il ne s'améliorait plus) :
#   1. num_leaves=31 max_depth=8  lr=0.05 min_child=20  (retenu) : 3000 arbres -> 0,0728
#   2. num_leaves=15 max_depth=6  lr=0.05 min_child=30  :           800 arbres -> 0,0769
#   3. num_leaves=31 max_depth=8  lr=0.15 min_child=50, reg=0.2  : 1500 arbres -> 0,0740
#   4. num_leaves=15 max_depth=5  lr=0.15 min_child=100, reg=0.5 : 1500 arbres -> 0,0747
#
# Le premier candidat (déjà commis dans `configs/base.yaml`) est le meilleur
# des quatre, utilisé sans rouvrir la recherche à chaque exécution.
#
# SANS `taux_session_precedente` : 0,0731 validation, 0,0820 test. ATTENTION
# à la couverture avant de comparer à la baseline : jugée à 100 % (comme le
# modèle, `session_precedente_avec_repli`, jamais la variante sans repli qui
# ne se prononce que sur les 92,9 % de cellules 2025 qui ont un antécédent),
# elle vaut 0,0727 validation / 0,0701 test — le modèle fait jeu égal en
# validation (+0,0004) et décroche en test (+0,0119) : un défaut de
# généralisation temporelle, la baseline encaissant mieux la dérive
# 2024 -> 2025 que le modèle.
#
# AVEC `taux_session_precedente` (`inclure_taux_precedent`, activé par
# défaut, décidé sur la seule validation) : 0,0690 validation (sous le
# plancher) et 0,0758 test (encore au-dessus, mais l'écart passe de 0,0119 à
# 0,0057). Elle domine `classement_importance` d'un ordre de grandeur —
# lecture développée dans le compte rendu de l'étape, utile à l'ablation
# (E27).
HYPERPARAMETRES_EXPLORES = "voir le commentaire ci-dessus : recherche conduite hors module, sur validation uniquement"


class ErreurEntrainement(RuntimeError):
    """L'entraînement ne peut pas continuer sans violer une garantie attendue.

    Définitive : une colonne hors classement, une source absente, ou un split
    vide ne se règlent pas en relançant à l'identique.
    """


@dataclass(frozen=True)
class JeuDonnees:
    """Les trois pièces alignées par index dont un entraînement ou une évaluation ont besoin."""

    X: pd.DataFrame
    y: pd.Series
    poids: pd.Series
    sessions: pd.Series


@dataclass(frozen=True)
class RapportEntrainement:
    """Ce que `make train` (E22) a produit, à déclarer tel quel."""

    colonnes_categorielles: list[str]
    colonnes_numeriques: list[str]
    meilleure_iteration: int
    duree_secondes: float
    scores_validation: ScoreSession
    scores_test: ScoreSession
    scores_par_session: list[ScoreSession]
    importance_variables: list[tuple[str, float]]
    # Le plancher (E21), à COUVERTURE ÉGALE avec le modèle (100 %, grâce au
    # repli sur la moyenne de groupe) : sans lui, le plancher serait jugé sur
    # le seul sous-ensemble le plus facile, un biais qui exagère l'écart.
    baseline_validation: ScoreSession
    baseline_test: ScoreSession

    def resume(self) -> str:
        lignes = [
            f"Entraînement terminé en {self.duree_secondes:.1f} s, "
            f"{self.meilleure_iteration} arbres retenus (arrêt anticipé sur la validation).",
            f"  {self.scores_validation.resume()}  (choix des hyperparamètres et du nombre d'arbres)",
            f"  {self.scores_test.resume()}  (touché une seule fois, à la fin)",
            f"  {self.baseline_validation.resume()}  (plancher E21, à couverture égale)",
            f"  {self.baseline_test.resume()}  (plancher E21, à couverture égale)",
        ]
        for score in self.scores_par_session:
            lignes.append(f"    {score.resume()}")
        for rang, (nom, importance) in enumerate(self.importance_variables[:10], start=1):
            lignes.append(f"    #{rang:2d} {nom:32s} gain={importance:.1f}")
        return "\n".join(lignes)


def colonnes_features(variables: VariablesConfig, colonnes_table: list[str]) -> list[str]:
    """Les colonnes de `colonnes_table` licites comme variable, dans l'ordre où `variables` les classe.

    Lève si une colonne de `colonnes_table` ne relève ni de la liste blanche
    de `modele.variables` (ADR 0013), ni des colonnes non-features connues
    (`COLONNES_NON_FEATURES`), ni des deux variables dérivées de ce module
    (`COLONNES_DERIVEES`) : défense en profondeur, symétrique de
    `features.build._verifier_colonnes_licites`, contre une colonne ajoutée à
    la table de variables sans avoir été classée nulle part.
    """
    licites = (
        set(variables.dimensions_cellule)
        | set(variables.session_courante)
        | set(variables.decalees)
        | set(variables.decalees_sous_reserve)
        | set(COLONNES_DERIVEES)
    )
    inattendues = set(colonnes_table) - licites - set(COLONNES_NON_FEATURES)
    if inattendues:
        raise ErreurEntrainement(
            f"Colonne(s) {sorted(inattendues)} de la table de variables ne relève(nt) ni de la "
            "liste blanche de modele.variables (ADR 0013), ni des colonnes non-features connues : "
            "entraînement refusé."
        )
    return [colonne for colonne in colonnes_table if colonne in licites]


def ajouter_taux_precedent(table: pd.DataFrame) -> pd.DataFrame:
    """Ajoute le taux de la session précédente comme variable explicite (voir §« Le taux… » ci-dessus).

    Réutilise `models.baseline.predire_session_precedente` à l'identique —
    même formule, mêmes colonnes décalées `prop_tot_{cat}` / `nb_voe_pp_{cat}`
    (ADR 0013 §2), jamais recalculée séparément — pour que la variable donnée
    au modèle soit *exactement* le plancher qu'elle est censée l'aider à
    dépasser, pas une resucée qui pourrait diverger de lui. Ces deux colonnes
    sources sont déjà décalées d'une session par `features.build` (E20, contrat
    anti-fuite vérifié par mutation) : ajouter ce dérivé ici ne lit donc rien
    de plus tôt que ce que ce contrat autorise déjà.

    `a_antecedent` distingue une absence d'antécédent — formation nouvelle,
    ou dont le code a changé, ou première session de la fenêtre labellisée —
    d'un simple `NaN` que LightGBM traiterait sans lui donner de sens propre :
    l'absence est une information, pas seulement un trou (voir la consigne de
    cette étape).
    """
    table = table.copy()
    table[COLONNE_TAUX_PRECEDENT] = predire_session_precedente(table)
    table[COLONNE_A_ANTECEDENT] = table[COLONNE_TAUX_PRECEDENT].notna()
    return table


def preparer_matrice(table: pd.DataFrame, colonnes: list[str]) -> pd.DataFrame:
    """Convertit les types nullables Pandas issus de Parquet vers ce que LightGBM attend.

    `Int64` / `Float64` (entiers et flottants nullables) -> `float64`, `NaN`
    remplaçant `pandas.NA` ; LightGBM traite nativement l'absence, aucune
    imputation n'a lieu ici. `string` / `object` / `boolean` -> `category` :
    LightGBM détecte automatiquement les colonnes de ce type et les traite
    par regroupement de modalités, sans encodage one-hot préalable qui
    ferait exploser la dimension pour `fil_lib_voe_acc` (712 modalités).
    """
    matrice = table[colonnes].copy()
    for colonne in matrice.columns:
        dtype = str(matrice[colonne].dtype)
        if dtype in ("Int64", "Float64"):
            matrice[colonne] = matrice[colonne].astype("float64")
        elif dtype in ("string", "str", "object", "bool", "boolean"):
            matrice[colonne] = matrice[colonne].astype("category")
    return matrice


def _extraire_jeu(table: pd.DataFrame, sessions: list[int], colonnes: list[str]) -> JeuDonnees:
    sous_table = table[table["session"].isin(sessions)]
    if sous_table.empty:
        raise ErreurEntrainement(f"Aucune cellule pour les sessions {sessions} dans la table de variables.")
    return JeuDonnees(
        X=preparer_matrice(sous_table, colonnes),
        y=sous_table["taux"].astype("float64"),
        poids=poids_effectif(sous_table["effectif"]).astype("float64"),
        sessions=sous_table["session"],
    )


def entrainer_modele(
    entrainement: JeuDonnees, validation: JeuDonnees, hyperparametres: HyperparametresConfig
) -> lgb.LGBMRegressor:
    """Entraîne un LightGBM pondéré, arrêté sur la MAE pondérée de validation.

    Objectif `regression` (perte quadratique) plutôt que `regression_l1`
    (MAE) : mesuré sur cette table, la perte L1 est un ordre de grandeur plus
    lente à ajuster par nœud (recherche de médiane contre calcul de moyenne),
    sans gain observé sur la métrique de validation qui compte réellement —
    la MAE pondérée, choisie ici comme `eval_metric`, pas comme fonction de
    perte optimisée. C'est elle, et seulement elle, qui gouverne l'arrêt
    anticipé (`early_stopping_rounds`, `configs/base.yaml`) : le nombre
    d'arbres n'est donc jamais fixé a priori, il est tranché par la
    validation, exactement le rôle que `04-modele/specification.md` (§5) lui
    assigne dans le compromis biais-variance.
    """
    modele = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=hyperparametres.n_estimators,
        num_leaves=hyperparametres.num_leaves,
        max_depth=hyperparametres.max_depth,
        learning_rate=hyperparametres.learning_rate,
        min_child_samples=hyperparametres.min_child_samples,
        reg_alpha=hyperparametres.reg_alpha,
        reg_lambda=hyperparametres.reg_lambda,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    modele.fit(
        entrainement.X,
        entrainement.y,
        sample_weight=entrainement.poids,
        eval_X=validation.X,
        eval_y=validation.y,
        eval_sample_weight=[validation.poids],
        eval_metric="mae",
        callbacks=[lgb.early_stopping(hyperparametres.early_stopping_rounds, verbose=False)],
    )
    return modele


def evaluer_sur_perimetre(jeu: JeuDonnees, prediction: np.ndarray, perimetre: str) -> ScoreSession:
    """MAE pondérée et non pondérée d'une prédiction déjà calculée sur un jeu donné.

    Fine couche sur `metrics.score` : `JeuDonnees` est propre à ce module,
    la formule qu'elle sert à évaluer ne l'est pas (voir `metrics.py`).
    """
    return score(jeu.y, jeu.poids, prediction, perimetre)


def _scores_par_session(jeu: JeuDonnees, prediction: np.ndarray) -> list[ScoreSession]:
    scores = []
    for session in sorted(jeu.sessions.unique()):
        masque = (jeu.sessions == session).to_numpy()
        sous_jeu = JeuDonnees(
            X=jeu.X.loc[masque] if hasattr(jeu.X, "loc") else jeu.X[masque],
            y=jeu.y[masque],
            poids=jeu.poids[masque],
            sessions=jeu.sessions[masque],
        )
        scores.append(evaluer_sur_perimetre(sous_jeu, prediction[masque], str(session)))
    return scores


def _commit_git() -> str | None:
    """Le hachage court du commit courant, pour relier une exécution MLflow à un état du dépôt.

    Best-effort : ni un dépôt Git absent, ni `git` non installé ne doivent
    interrompre l'entraînement — seule la traçabilité en pâtit, journalisée
    comme telle plutôt que masquée.
    """
    try:
        resultat = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as erreur:
        LOGGER.warning("Commit Git non résolu, traçabilité MLflow incomplète : %s", erreur)
        return None
    return resultat.stdout.strip() or None


def _journaliser_mlflow(
    modele: lgb.LGBMRegressor,
    hyperparametres: HyperparametresConfig,
    rapport: RapportEntrainement,
    colonnes_features_liste: list[str],
    settings: Settings,
) -> None:
    """Enregistre l'exécution dans MLflow : hyperparamètres, métriques, commit, artefact modèle.

    Absence de `mlflow_tracking_uri` ou du paquet lui-même : journalisée, pas
    masquée (même politique que `models.baseline._journaliser_mlflow`) — le
    modèle est déjà entraîné et évalué avant cet appel, son résultat ne
    dépend jamais de MLflow.
    """
    if not settings.mlflow_tracking_uri:
        LOGGER.warning("MLFLOW_TRACKING_URI non configuré : entraînement non journalisé dans MLflow (E22).")
        return
    try:
        import mlflow
        import mlflow.lightgbm
    except ImportError:
        LOGGER.warning("Le paquet mlflow n'est pas installé dans cet environnement : entraînement non journalisé.")
        return

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(NOM_EXPERIENCE_MLFLOW)
    variante = "avec-taux-precedent" if settings.modele.inclure_taux_precedent else "sans-taux-precedent"
    with mlflow.start_run(run_name=f"lightgbm-pondere-{variante}"):
        mlflow.set_tag("etape", "E22")
        mlflow.set_tag("variante", variante)
        commit = _commit_git()
        if commit:
            mlflow.set_tag("commit_git", commit)
        mlflow.log_params(hyperparametres.model_dump())
        mlflow.log_param("nombre_variables", len(colonnes_features_liste))
        mlflow.log_param("inclure_taux_precedent", settings.modele.inclure_taux_precedent)
        mlflow.log_param("meilleure_iteration", rapport.meilleure_iteration)
        mlflow.log_metric("duree_secondes", rapport.duree_secondes)
        for score, prefixe in (
            (rapport.scores_validation, "validation"),
            (rapport.scores_test, "test"),
            (rapport.baseline_validation, "baseline_validation"),
            (rapport.baseline_test, "baseline_test"),
        ):
            mlflow.log_metric(f"{prefixe}_mae_ponderee", score.mae_ponderee)
            mlflow.log_metric(f"{prefixe}_mae_non_ponderee", score.mae_non_ponderee)
            mlflow.log_metric(f"{prefixe}_n_cellules", score.n_cellules)
        for score in rapport.scores_par_session:
            mlflow.log_metric(f"session_{score.perimetre}_mae_ponderee", score.mae_ponderee)
        noms_importance = [nom for nom, _ in rapport.importance_variables]
        if COLONNE_TAUX_PRECEDENT in noms_importance:
            mlflow.log_metric("rang_taux_precedent", noms_importance.index(COLONNE_TAUX_PRECEDENT) + 1)
        mlflow.lightgbm.log_model(modele, name="modele")


def _chemin_variables(settings: Settings) -> Path:
    return settings.processed_dir / SOUS_DOSSIER / NOM_FICHIER_VARIABLES


def executer(settings: Settings | None = None) -> tuple[lgb.LGBMRegressor, RapportEntrainement]:
    """Charge la table de variables, entraîne le modèle et l'évalue selon le protocole (E22).

    Le test n'est chargé et prédit qu'une fois le modèle définitivement
    entraîné (arrêt anticipé décidé sur la seule validation) : aucune boucle
    de ce module ne compare deux configurations sur le test.
    """
    settings = settings or get_settings()
    chemin = _chemin_variables(settings)
    if not chemin.exists():
        raise ErreurEntrainement(f"{chemin} est introuvable : exécuter `make features` (E20) avant `make train`.")

    table = pq.read_table(chemin).to_pandas()
    table = ajouter_taux_precedent(table)
    colonnes = colonnes_features(settings.modele.variables, list(table.columns))
    if not settings.modele.inclure_taux_precedent:
        colonnes = [colonne for colonne in colonnes if colonne not in COLONNES_DERIVEES]

    split = settings.modele.split
    jeu_entrainement = _extraire_jeu(table, split.entrainement, colonnes)
    jeu_validation = _extraire_jeu(table, split.validation, colonnes)
    jeu_test = _extraire_jeu(table, split.test, colonnes)

    debut = time.monotonic()
    modele = entrainer_modele(jeu_entrainement, jeu_validation, settings.modele.hyperparametres)
    duree = time.monotonic() - debut

    prediction_validation = modele.predict(jeu_validation.X)
    prediction_test = modele.predict(jeu_test.X)

    # Plancher à couverture égale (voir `score_baseline_couverture_egale`) :
    # calculé sur `table` avant tout split, exactement comme le modèle n'a
    # accès qu'aux sessions <= N-1 pour prédire N.
    moyenne_groupe = predire_moyenne_expansive(table, _COLONNES_GROUPE_BASELINE)

    rapport = RapportEntrainement(
        colonnes_categorielles=sorted(jeu_entrainement.X.select_dtypes(include="category").columns),
        colonnes_numeriques=sorted(jeu_entrainement.X.select_dtypes(include="float64").columns),
        meilleure_iteration=int(modele.best_iteration_ or settings.modele.hyperparametres.n_estimators),
        duree_secondes=duree,
        scores_validation=evaluer_sur_perimetre(jeu_validation, prediction_validation, "validation"),
        scores_test=evaluer_sur_perimetre(jeu_test, prediction_test, "test"),
        scores_par_session=_scores_par_session(jeu_validation, prediction_validation)
        + _scores_par_session(jeu_test, prediction_test),
        importance_variables=classement_importance(modele, colonnes),
        baseline_validation=score_baseline_couverture_egale(
            table, COLONNE_TAUX_PRECEDENT, moyenne_groupe, split.validation, "validation"
        ),
        baseline_test=score_baseline_couverture_egale(
            table, COLONNE_TAUX_PRECEDENT, moyenne_groupe, split.test, "test"
        ),
    )

    _journaliser_mlflow(modele, settings.modele.hyperparametres, rapport, colonnes, settings)
    return modele, rapport


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    _, rapport = executer()
    LOGGER.info("Entraînement (E22) terminé.\n%s", rapport.resume())
    return 0


if __name__ == "__main__":
    sys.exit(main())
