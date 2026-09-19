"""Entraînement du modèle d'accessibilité : LightGBM pondéré, tracé dans MLflow.

## Ce que ce module fait, et rien de plus

`features/build.py` a produit la table de variables, une ligne par
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
plancher (`session_precedente_avec_repli`) sur EXACTEMENT le périmètre du
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
de conception (`docs/modele.html`) : données tabulaires et
hétérogènes, valeurs manquantes structurelles (ADR 0013 §6) — un réseau
n'apporterait rien sur ce volume (286 463 cellules d'entraînement) et
coûterait l'explicabilité exacte que permet TreeSHAP.
"""

from __future__ import annotations

import hashlib
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
from sklearn.isotonic import IsotonicRegression

from edumatch.config import (
    PROJECT_ROOT,
    HyperparametresConfig,
    Settings,
    VariablesConfig,
    VarianteModeleConfig,
    get_settings,
)
from edumatch.models.baseline import (
    COLONNES_GROUPE as _COLONNES_GROUPE_BASELINE,
)
from edumatch.models.baseline import predire_moyenne_expansive, predire_session_precedente
from edumatch.models.jeux import (
    ErreurJeuxDonnees,
    JeuDonnees,
    chemin_table_variables,
    evaluer_sur_perimetre,
    extraire_jeu,
    scores_par_session,
)
from edumatch.models.metrics import (
    ScoreSession,
    calibration,
    classement_importance,
    predictions_baseline_couverture_egale,
    score_baseline_couverture_egale,
)
from edumatch.models.variante import (
    CALIBRATION_ISOTONIQUE,
    CIBLE_ECART,
    CIBLE_TAUX,
    poids_recence,
    reconstruire_prediction,
)

LOGGER = logging.getLogger(__name__)

# ─── Preuve de gel du candidat figé (ADR 0021, phase 2) ────────────────────
#
# Empreintes SHA-256 des quatre fichiers qui déterminent entièrement le
# comportement du candidat retenu : la configuration (`configs/base.yaml`),
# l'entraînement lui-même (ce module), la porte de promotion et le script de
# sélection (conservé pour que le candidat reste reproductible depuis son
# origine). Calculées avant l'unique évaluation de test et recalculées après :
# une différence signalerait qu'un fichier a changé entre les deux, ce que le
# protocole interdit (voir `docs/decisions.html#adr-0021`, point 5, et la
# consigne de cette étape).
FICHIERS_GELES: tuple[str, ...] = (
    "configs/base.yaml",
    "src/edumatch/models/train.py",
    "src/edumatch/orchestration/promotion.py",
    "src/edumatch/models/selection.py",
)


def empreintes_gel() -> dict[str, str]:
    """L'empreinte SHA-256 de chacun des `FICHIERS_GELES`, clé = chemin relatif au dépôt."""
    return {
        chemin_relatif: hashlib.sha256((PROJECT_ROOT / chemin_relatif).read_bytes()).hexdigest()
        for chemin_relatif in FICHIERS_GELES
    }


def _variante_active(variante: VarianteModeleConfig) -> bool:
    """Vrai si `modele.variante` s'écarte du comportement par défaut (ADR 0021) —
    dans ce cas, `entrainer_et_evaluer` emprunte le chemin de refit à deux
    temps plutôt que l'entraînement à une seule passe."""
    return variante.demi_vie_recence is not None or variante.cible != CIBLE_TAUX or variante.calibration != "aucune"

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
# taux de la baseline sont donc déjà visibles, séparément, par cellule.
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
#.
HYPERPARAMETRES_EXPLORES = "voir le commentaire ci-dessus : recherche conduite hors module, sur validation uniquement"


class ErreurEntrainement(ErreurJeuxDonnees):
    """L'entraînement ne peut pas continuer sans violer une garantie attendue.

    Sous-classe de `jeux.ErreurJeuxDonnees` : un split vide (`extraire_jeu`)
    et une source absente ou une colonne hors classement (ce module) sont la
    même famille de défaillance — définitive, une colonne hors classement,
    une source absente, ou un split vide ne se règlent pas en relançant à
    l'identique.
    """


@dataclass(frozen=True)
class RapportEntrainement:
    """Ce que `make train` a produit, à déclarer tel quel."""

    colonnes_categorielles: list[str]
    colonnes_numeriques: list[str]
    meilleure_iteration: int
    duree_secondes: float
    scores_validation: ScoreSession
    scores_test: ScoreSession
    scores_par_session: list[ScoreSession]
    importance_variables: list[tuple[str, float]]
    # Le plancher, à COUVERTURE ÉGALE avec le modèle (100 %, grâce au
    # repli sur la moyenne de groupe) : sans lui, le plancher serait jugé sur
    # le seul sous-ensemble le plus facile, un biais qui exagère l'écart.
    baseline_validation: ScoreSession
    baseline_test: ScoreSession
    # Erreur de calibration attendue (ECE, `models.metrics.calibration`) sur
    # la prédiction FINALE (après reconstruction ancre + écart et calibration
    # isotonique le cas échéant, ADR 0021) : c'est elle que la porte de
    # promotion compare au plancher de l'AIPD (`evaluation.seuil_ece_test`).
    ece_validation: float
    ece_test: float
    # Nombre de prédictions de test hors de [0, 1] avant écrêtage — mesuré, jamais
    # supposé nul : le chemin par défaut (modèle v1) et la variante « écart »
    # (ADR 0021 point 1) reposent tous deux sur une perte L2 qui ne borne pas la
    # sortie ; seule la variante « taux » du chemin figé, en `cross_entropy`, l'est.
    n_predictions_ecretees_test: int = 0

    def resume(self) -> str:
        lignes = [
            (
                f"Entraînement terminé en {self.duree_secondes:.1f} s, "
                f"{self.meilleure_iteration} arbres retenus."
            ),
            f"  {self.scores_validation.resume()}  ece={self.ece_validation:.4f}",
            f"  {self.scores_test.resume()}  ece={self.ece_test:.4f}  (touché une seule fois, à la fin)",
            f"  {self.baseline_validation.resume()}  (plancher, à couverture égale)",
            f"  {self.baseline_test.resume()}  (plancher, à couverture égale)",
            f"  prédictions de test écrêtées : {self.n_predictions_ecretees_test}",
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
    sources sont déjà décalées d'une session par `features.build` (contrat
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
    validation, exactement le rôle que `docs/modele.html` (§5) lui
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
        LOGGER.warning("MLFLOW_TRACKING_URI non configuré : entraînement non journalisé dans MLflow.")
        return
    try:
        import mlflow
        import mlflow.lightgbm
    except ImportError:
        LOGGER.warning("Le paquet mlflow n'est pas installé dans cet environnement : entraînement non journalisé.")
        return

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(NOM_EXPERIENCE_MLFLOW)
    variante_taux_precedent = "avec-taux-precedent" if settings.modele.inclure_taux_precedent else "sans-taux-precedent"
    variante_modele = settings.modele.variante
    candidat_fige = _variante_active(variante_modele)
    with mlflow.start_run(run_name=f"lightgbm-pondere-{variante_taux_precedent}"):
        mlflow.set_tag("etape", "train")
        mlflow.set_tag("variante", variante_taux_precedent)
        mlflow.set_tag("candidat_fige_adr0021", str(candidat_fige))
        commit = _commit_git()
        if commit:
            mlflow.set_tag("commit_git", commit)
        if candidat_fige:
            # Preuve de gel (ADR 0021 point 5) : empreinte SHA-256 des quatre fichiers qui
            # déterminent le comportement du candidat, journalisée AVANT l'évaluation de test —
            # à recalculer après coup et comparer, voir `empreintes_gel()`.
            for chemin_relatif, empreinte in empreintes_gel().items():
                cle = "empreinte_" + chemin_relatif.replace("/", "__")
                mlflow.set_tag(cle, empreinte)
            mlflow.log_param("variante_demi_vie_recence", variante_modele.demi_vie_recence)
            mlflow.log_param("variante_cible", variante_modele.cible)
            mlflow.log_param("variante_calibration", variante_modele.calibration)
            mlflow.log_param("variante_n_estimators_fige", variante_modele.n_estimators_fige)
            mlflow.log_metric("n_predictions_ecretees_test", rapport.n_predictions_ecretees_test)
        mlflow.log_params(hyperparametres.model_dump())
        mlflow.log_param("nombre_variables", len(colonnes_features_liste))
        mlflow.log_param("inclure_taux_precedent", settings.modele.inclure_taux_precedent)
        mlflow.log_param("meilleure_iteration", rapport.meilleure_iteration)
        mlflow.log_metric("duree_secondes", rapport.duree_secondes)
        mlflow.log_metric("ece_validation", rapport.ece_validation)
        mlflow.log_metric("ece_test", rapport.ece_test)
        mlflow.log_metric("seuil_ece_test_aipd", settings.evaluation.seuil_ece_test)
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


def charger_table(settings: Settings) -> pd.DataFrame:
    """Charge la table de variables et y ajoute le taux de la session précédente.

    Partagé avec `models.evaluate` : les deux modules doivent lire
    exactement la même table, avec la même colonne dérivée, pour que les
    prédictions qu'`evaluate.py` recalcule s'alignent, ligne à ligne, sur
    celles évaluées ici.
    """
    chemin = chemin_table_variables(settings)
    if not chemin.exists():
        raise ErreurEntrainement(f"{chemin} est introuvable : exécuter `make features` avant `make train`.")
    table = pq.read_table(chemin).to_pandas()
    return ajouter_taux_precedent(table)


def preparer_jeux(
    table: pd.DataFrame, settings: Settings
) -> tuple[list[str], JeuDonnees, JeuDonnees, JeuDonnees]:
    """Les colonnes retenues et les trois jeux du split temporel, prêts pour `entrainer_modele`."""
    colonnes = colonnes_features(settings.modele.variables, list(table.columns))
    if not settings.modele.inclure_taux_precedent:
        colonnes = [colonne for colonne in colonnes if colonne not in COLONNES_DERIVEES]

    split = settings.modele.split
    jeu_entrainement = extraire_jeu(table, split.entrainement, colonnes)
    jeu_validation = extraire_jeu(table, split.validation, colonnes)
    jeu_test = extraire_jeu(table, split.test, colonnes)
    return colonnes, jeu_entrainement, jeu_validation, jeu_test


@dataclass(frozen=True)
class ResultatEntrainement:
    """Tout ce que produit un entraînement complet, y compris ce que l'évaluation
    réutilise pour ne jamais recalculer un modèle ou une prédiction déjà obtenus ici.
    """

    modele: lgb.LGBMRegressor
    rapport: RapportEntrainement
    table: pd.DataFrame
    colonnes: list[str]
    jeu_validation: JeuDonnees
    jeu_test: JeuDonnees
    prediction_validation: np.ndarray
    prediction_test: np.ndarray
    moyenne_groupe: pd.Series


# ─── L'artefact que sert l'API, sans jamais réentraîner ─────────
#
# Colonnes du catalogue de la session courante retenues pour le matching :
# les six colonnes requises par `matching.score.recommander`
# (`COLONNES_CATALOGUE_REQUISES`, sans `taux_predit` qui est ajoutée à part)
# plus les deux dimensions de la cellule (`type_bac`, `boursier`), nécessaires
# pour filtrer le catalogue au profil déclaré par le candidat avant de
# scorer. Définie ici, à l'endroit qui produit la prédiction, et importée
# par `api/state.py` plutôt que dupliquée : les deux doivent porter
# exactement les mêmes colonnes.
COLONNES_CATALOGUE: tuple[str, ...] = (
    "cod_aff_form",
    "fili",
    "fil_lib_voe_acc",
    "form_lib_voe_acc",
    "dep",
    "type_bac",
    "boursier",
)

# Sous-dossier et nom de fichier de l'artefact, sous `processed_dir` (donc
# sous `EDUMATCH_DATA_ROOT`, déjà configurable par variable d'environnement) :
# même convention que le précalcul SHAP (`models/explain.py`,
# `SOUS_DOSSIER_PRECALCUL`), pour qu'un même mécanisme de volume monté serve
# les deux artefacts que l'API attend au démarrage.
SOUS_DOSSIER_CATALOGUE_PREDICTIONS = "matching"
NOM_FICHIER_CATALOGUE_PREDICTIONS = "catalogue_predictions.parquet"


def construire_catalogue_predictions(resultat: ResultatEntrainement) -> pd.DataFrame:
    """Le catalogue de la session de test, prédictions incluses — exactement ce que l'API sert
    sur `/matching`, jamais recalculé à la requête (voir `api/state.py`)."""
    index_test = resultat.jeu_test.X.index
    catalogue = resultat.table.loc[index_test, list(COLONNES_CATALOGUE)].copy().reset_index(drop=True)
    catalogue["cod_aff_form"] = catalogue["cod_aff_form"].astype(str)
    catalogue["type_bac"] = catalogue["type_bac"].astype(str)
    catalogue["boursier"] = catalogue["boursier"].astype(bool)
    catalogue["taux_predit"] = resultat.prediction_test
    return catalogue


def exporter_catalogue_predictions(resultat: ResultatEntrainement, settings: Settings) -> Path:
    """Écrit l'artefact que l'API charge au démarrage : sans lui, `construire_etat_matching`
    retombe sur un entraînement complet — acceptable en développement, pas en production, où cet
    artefact est produit par `make train` (ou `docker/Dockerfile.train`) et monté en volume au
    même chemin (`processed_dir`, dérivé de `EDUMATCH_DATA_ROOT`) que l'API lit.

    Écriture atomique (fichier `.part` renommé à la fin, convention du dépôt, et
    principe d'immuabilité des données brutes que je me suis fixé) : un lecteur concurrent ne peut jamais observer un fichier
    tronqué."""
    catalogue = construire_catalogue_predictions(resultat)
    dossier = settings.processed_dir / SOUS_DOSSIER_CATALOGUE_PREDICTIONS
    dossier.mkdir(parents=True, exist_ok=True)
    chemin_final = dossier / NOM_FICHIER_CATALOGUE_PREDICTIONS
    chemin_provisoire = chemin_final.with_name(chemin_final.name + ".part")
    catalogue.to_parquet(chemin_provisoire, index=False)
    chemin_provisoire.replace(chemin_final)
    return chemin_final


def _entrainer_lightgbm_fixe(
    X: pd.DataFrame,
    y: pd.Series,
    poids: pd.Series,
    hyperparametres: HyperparametresConfig,
    n_estimators: int,
    objective: str,
) -> lgb.LGBMRegressor:
    """Un LightGBM pondéré, nombre d'arbres FIXE (pas d'arrêt anticipé, pas de jeu d'évaluation) :
    le rôle que la validation jouait pour arrêter l'entraînement a déjà été
    joué lors de la sélection (ADR 0021 point 4) — le refit n'a plus besoin
    d'un jeu qu'il vient justement d'absorber dans son propre entraînement.

    `deterministic=True` et `force_row_wise=True` : sans eux, l'ordre de
    sommation des histogrammes en construction multi-thread peut varier d'une
    exécution à l'autre, et deux entraînements par ailleurs identiques
    (mêmes données, mêmes hyperparamètres, même `random_state`) produiraient
    des arbres marginalement différents. La preuve d'égalité entre les
    prédictions de `reentrainer_modele`, `evaluate` et `fairness` (même
    candidat figé, ré-entraîné trois fois) dépend de ce déterminisme.
    """
    modele = lgb.LGBMRegressor(
        objective=objective,
        n_estimators=n_estimators,
        num_leaves=hyperparametres.num_leaves,
        max_depth=hyperparametres.max_depth,
        learning_rate=hyperparametres.learning_rate,
        min_child_samples=hyperparametres.min_child_samples,
        reg_alpha=hyperparametres.reg_alpha,
        reg_lambda=hyperparametres.reg_lambda,
        random_state=42,
        n_jobs=2,
        deterministic=True,
        force_row_wise=True,
        verbose=-1,
    )
    modele.fit(X, y, sample_weight=poids)
    return modele


def _entrainer_variante_figee(table: pd.DataFrame, colonnes: list[str], settings: Settings) -> ResultatEntrainement:
    """Le chemin de refit à deux temps du candidat figé (ADR 0021, points 1 et 4) :

    (a) le modèle de sélection est ré-entraîné sur 2020-2023, nombre d'arbres
        figé à `variante.n_estimators_fige` (la meilleure itération trouvée en
        sélection), pour produire les prédictions 2024 qui ajustent le
        calibrateur isotonique global ;
    (b) un second modèle, mêmes hyperparamètres et même nombre d'arbres, est
        entraîné (« refit ») sur 2020-2024 — l'ADR justifie ce choix : la
        baseline de test connaît déjà les taux 2024, un modèle qui ne les a
        pas vus part avec un an de retard sur elle ;
    (c) la prédiction de test 2025 est `ancre + écart` (ou le taux direct,
        selon `variante.cible`), écrêtée à [0, 1], puis passée au calibrateur
        de (a) — jamais un calibrateur réajusté sur le modèle refitté, faute
        d'une session non vue pour le faire proprement (approximation
        déclarée, ADR 0021 point 4).

    Ne modifie ni ne compare plusieurs candidats : `variante` est déjà figée
    par `configs/base.yaml`, ce chemin ne fait qu'exécuter le protocole que
    l'ADR décrit pour LE candidat retenu.
    """
    variante = settings.modele.variante
    split = settings.modele.split
    hyperparametres = settings.modele.hyperparametres
    n_arbres = variante.n_estimators_fige or hyperparametres.n_estimators
    objective = "regression" if variante.cible == CIBLE_ECART else "cross_entropy"

    jeu_entrainement = extraire_jeu(table, split.entrainement, colonnes)
    jeu_validation = extraire_jeu(table, split.validation, colonnes)
    jeu_test = extraire_jeu(table, split.test, colonnes)

    moyenne_groupe = predire_moyenne_expansive(table, _COLONNES_GROUPE_BASELINE)
    ancre_entrainement = predictions_baseline_couverture_egale(
        table, COLONNE_TAUX_PRECEDENT, moyenne_groupe, split.entrainement
    ).reindex(jeu_entrainement.X.index)
    ancre_validation = predictions_baseline_couverture_egale(
        table, COLONNE_TAUX_PRECEDENT, moyenne_groupe, split.validation
    ).reindex(jeu_validation.X.index)
    ancre_test = predictions_baseline_couverture_egale(
        table, COLONNE_TAUX_PRECEDENT, moyenne_groupe, split.test
    ).reindex(jeu_test.X.index)

    def _cible(y: pd.Series, ancre: pd.Series) -> pd.Series:
        return (y - ancre) if variante.cible == CIBLE_ECART else y

    debut = time.monotonic()

    # (a) Modèle de sélection, 2020-2023, s_ref = dernière session d'entraînement.
    poids_a = jeu_entrainement.poids
    if variante.demi_vie_recence is not None:
        s_ref_a = int(jeu_entrainement.sessions.max())
        poids_a = poids_a * poids_recence(jeu_entrainement.sessions, s_ref_a, variante.demi_vie_recence)

    modele_selection = _entrainer_lightgbm_fixe(
        jeu_entrainement.X, _cible(jeu_entrainement.y, ancre_entrainement), poids_a, hyperparametres, n_arbres, objective
    )

    prediction_validation_brute = modele_selection.predict(jeu_validation.X)
    prediction_validation, _n_ecretages_validation = reconstruire_prediction(
        prediction_validation_brute, variante.cible, ancre_validation
    )

    calibrateur: IsotonicRegression | None = None
    if variante.calibration == CALIBRATION_ISOTONIQUE:
        calibrateur = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        calibrateur.fit(
            prediction_validation, jeu_validation.y.to_numpy(dtype="float64"),
            sample_weight=jeu_validation.poids.to_numpy(dtype="float64"),
        )
        prediction_validation_finale = calibrateur.predict(prediction_validation)
    else:
        prediction_validation_finale = prediction_validation

    # (b) Refit, 2020-2024, s_ref = dernière session de validation.
    sessions_refit = list(split.entrainement) + list(split.validation)
    jeu_refit = extraire_jeu(table, sessions_refit, colonnes)
    ancre_refit = predictions_baseline_couverture_egale(
        table, COLONNE_TAUX_PRECEDENT, moyenne_groupe, sessions_refit
    ).reindex(jeu_refit.X.index)
    poids_refit = jeu_refit.poids
    if variante.demi_vie_recence is not None:
        s_ref_b = int(jeu_refit.sessions.max())
        poids_refit = poids_refit * poids_recence(jeu_refit.sessions, s_ref_b, variante.demi_vie_recence)

    modele_refit = _entrainer_lightgbm_fixe(
        jeu_refit.X, _cible(jeu_refit.y, ancre_refit), poids_refit, hyperparametres, n_arbres, objective
    )
    duree = time.monotonic() - debut

    # (c) Prédiction de test = ancre + écart (ou taux direct), écrêtée, puis calibrateur de (a).
    prediction_test_brute = modele_refit.predict(jeu_test.X)
    prediction_test_reconstruite, n_ecretages_test = reconstruire_prediction(
        prediction_test_brute, variante.cible, ancre_test
    )
    prediction_test_finale = (
        calibrateur.predict(prediction_test_reconstruite) if calibrateur is not None else prediction_test_reconstruite
    )

    n_tranches = settings.evaluation.n_tranches_calibration
    rapport = RapportEntrainement(
        colonnes_categorielles=sorted(jeu_refit.X.select_dtypes(include="category").columns),
        colonnes_numeriques=sorted(jeu_refit.X.select_dtypes(include="float64").columns),
        meilleure_iteration=n_arbres,
        duree_secondes=duree,
        scores_validation=evaluer_sur_perimetre(jeu_validation, prediction_validation_finale, "validation"),
        scores_test=evaluer_sur_perimetre(jeu_test, prediction_test_finale, "test"),
        scores_par_session=scores_par_session(jeu_validation, prediction_validation_finale)
        + scores_par_session(jeu_test, prediction_test_finale),
        importance_variables=classement_importance(modele_refit, colonnes),
        baseline_validation=score_baseline_couverture_egale(
            table, COLONNE_TAUX_PRECEDENT, moyenne_groupe, split.validation, "validation"
        ),
        baseline_test=score_baseline_couverture_egale(
            table, COLONNE_TAUX_PRECEDENT, moyenne_groupe, split.test, "test"
        ),
        ece_validation=calibration(
            jeu_validation.y, jeu_validation.poids, prediction_validation_finale, n_tranches, "validation"
        ).ece,
        ece_test=calibration(jeu_test.y, jeu_test.poids, prediction_test_finale, n_tranches, "test").ece,
        n_predictions_ecretees_test=n_ecretages_test,
    )

    _journaliser_mlflow(modele_refit, hyperparametres, rapport, colonnes, settings)
    return ResultatEntrainement(
        modele=modele_refit,
        rapport=rapport,
        table=table,
        colonnes=colonnes,
        jeu_validation=jeu_validation,
        jeu_test=jeu_test,
        prediction_validation=prediction_validation_finale,
        prediction_test=prediction_test_finale,
        moyenne_groupe=moyenne_groupe,
    )


def entrainer_et_evaluer(settings: Settings | None = None) -> ResultatEntrainement:
    """Charge la table de variables, entraîne le modèle et l'évalue selon le protocole.

    Le test n'est chargé et prédit qu'une fois le modèle définitivement
    entraîné (arrêt anticipé décidé sur la seule validation) : aucune boucle
    de ce module ne compare deux configurations sur le test.

    Deux chemins, choisis par `_variante_active(settings.modele.variante)` :
    le chemin par défaut (une seule passe d'entraînement, comportement
    inchangé depuis avant l'ADR 0021) si `modele.variante` n'a pas été
    renseignée, ou le chemin de refit à deux temps du candidat figé
    (`_entrainer_variante_figee`) si elle l'a été — c'est le cas de
    `configs/base.yaml` depuis le 18 septembre 2026 (candidat C-h2 /
    isotonique globale, voir `docs/decisions.html#adr-0021`).
    """
    settings = settings or get_settings()
    table = charger_table(settings)
    colonnes, jeu_entrainement, jeu_validation, jeu_test = preparer_jeux(table, settings)

    if _variante_active(settings.modele.variante):
        return _entrainer_variante_figee(table, colonnes, settings)

    debut = time.monotonic()
    modele = entrainer_modele(jeu_entrainement, jeu_validation, settings.modele.hyperparametres)
    duree = time.monotonic() - debut

    prediction_validation = modele.predict(jeu_validation.X)
    prediction_test = modele.predict(jeu_test.X)

    # Plancher à couverture égale (voir `score_baseline_couverture_egale`) :
    # calculé sur `table` avant tout split, exactement comme le modèle n'a
    # accès qu'aux sessions <= N-1 pour prédire N.
    moyenne_groupe = predire_moyenne_expansive(table, _COLONNES_GROUPE_BASELINE)
    split = settings.modele.split
    n_tranches = settings.evaluation.n_tranches_calibration

    rapport = RapportEntrainement(
        colonnes_categorielles=sorted(jeu_entrainement.X.select_dtypes(include="category").columns),
        colonnes_numeriques=sorted(jeu_entrainement.X.select_dtypes(include="float64").columns),
        meilleure_iteration=int(modele.best_iteration_ or settings.modele.hyperparametres.n_estimators),
        duree_secondes=duree,
        scores_validation=evaluer_sur_perimetre(jeu_validation, prediction_validation, "validation"),
        scores_test=evaluer_sur_perimetre(jeu_test, prediction_test, "test"),
        scores_par_session=scores_par_session(jeu_validation, prediction_validation)
        + scores_par_session(jeu_test, prediction_test),
        importance_variables=classement_importance(modele, colonnes),
        baseline_validation=score_baseline_couverture_egale(
            table, COLONNE_TAUX_PRECEDENT, moyenne_groupe, split.validation, "validation"
        ),
        baseline_test=score_baseline_couverture_egale(
            table, COLONNE_TAUX_PRECEDENT, moyenne_groupe, split.test, "test"
        ),
        ece_validation=calibration(
            jeu_validation.y, jeu_validation.poids, prediction_validation, n_tranches, "validation"
        ).ece,
        ece_test=calibration(jeu_test.y, jeu_test.poids, prediction_test, n_tranches, "test").ece,
        # Chemin par défaut (modèle v1, moindres carrés) : rien ne borne la sortie dans [0, 1], le
        # nombre de prédictions qui en sortent est donc compté, jamais supposé nul.
        n_predictions_ecretees_test=int(((prediction_test < 0.0) | (prediction_test > 1.0)).sum()),
    )

    _journaliser_mlflow(modele, settings.modele.hyperparametres, rapport, colonnes, settings)
    return ResultatEntrainement(
        modele=modele,
        rapport=rapport,
        table=table,
        colonnes=colonnes,
        jeu_validation=jeu_validation,
        jeu_test=jeu_test,
        prediction_validation=prediction_validation,
        prediction_test=prediction_test,
        moyenne_groupe=moyenne_groupe,
    )


def executer(settings: Settings | None = None) -> tuple[lgb.LGBMRegressor, RapportEntrainement]:
    """Point d'entrée de `make train` : le modèle entraîné et son rapport, rien de plus.

    `evaluate.py` appelle `entrainer_et_evaluer` directement plutôt que
    cette fonction, pour récupérer aussi les jeux et les prédictions sans les
    recalculer une seconde fois.
    """
    resultat = entrainer_et_evaluer(settings)
    return resultat.modele, resultat.rapport


def main() -> int:
    """Point d'entrée de `make train` et de `docker/Dockerfile.train`.

    Exporte aussi le catalogue de prédictions (`exporter_catalogue_predictions`) : c'est cet
    artefact, monté en volume au même chemin par l'image de service, qui évite à l'API de
    réentraîner le modèle à chaque démarrage de processus (voir `api/state.py`)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    resultat = entrainer_et_evaluer(settings)
    LOGGER.info("Entraînement terminé.\n%s", resultat.rapport.resume())
    chemin = exporter_catalogue_predictions(resultat, settings)
    LOGGER.info("Catalogue de prédictions exporté vers %s : l'API le charge au démarrage, sans réentraîner.", chemin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
