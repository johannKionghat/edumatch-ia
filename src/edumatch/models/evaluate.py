"""Évaluation et calibration du modèle d'accessibilité (E23) : la comparaison à la baseline,
rapportée telle quelle, et le contrôle de calibration qu'une seule MAE ne peut pas remplacer.

## Ce que ce module fait, et ce qu'il ne refait pas

`models/train.py` (E22) entraîne le modèle, l'arrête sur la validation et
mesure déjà une MAE pondérée modèle contre plancher. Ce module ne relance
aucun entraînement : il appelle `train.entrainer_et_evaluer` — même
protocole, même split temporel, même random_state — pour récupérer le
modèle, les jeux de validation et de test déjà construits, et les
prédictions déjà calculées, puis il y ajoute ce que E22 ne mesure pas :

1. **La calibration** (`models.metrics.calibration`) : la cible est un taux
   dans [0, 1] (ADR 0009), pas une classe — un modèle peut bien ordonner les
   formations entre elles et pourtant annoncer 70 % quand la réalité est de
   40 %. Une MAE moyenne ne révèle pas cette faute ; le diagramme de
   fiabilité et l'erreur de calibration attendue (ECE), oui.
2. **La ventilation par type de baccalauréat** — l'erreur moyenne peut
   cacher une erreur très inégale selon le profil (`04-modele/evaluation.md`,
   réserve sur la progression bac général -> technologique -> professionnel).
   Nécessaire à l'audit d'équité (E26), qui suit.
3. **La même mesure pour la baseline (E21)**, jamais seulement pour le
   modèle : un score isolé ne se juge pas, et un modèle peut être moins
   précis en MAE tout en étant mieux calibré — ce serait alors un argument
   pour le garder malgré une MAE moins bonne, pas un résultat à taire.

Le test 2025 est déjà touché une fois par `train.entrainer_et_evaluer` (E22) ;
ce module ne le regarde pas une seconde fois pour choisir quoi que ce soit,
il ne fait que décrire, sous des angles supplémentaires, la même prédiction
déjà figée.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # aucun serveur d'affichage sur les postes de calcul et en CI
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from edumatch.config import PROJECT_ROOT, Settings, get_settings
from edumatch.models import train
from edumatch.models.metrics import (
    RapportCalibration,
    ScoreSession,
    calibration,
    predictions_baseline_couverture_egale,
    score,
)
from edumatch.models.train import COLONNE_TAUX_PRECEDENT, JeuDonnees

LOGGER = logging.getLogger(__name__)

NOM_EXPERIENCE_MLFLOW = "edumatch-accessibilite"

# Libellés lisibles des codes de `type_bac` (dimension de la cellule, ADR 0009) —
# repris de `transform.etoile.LIBELLES_TYPE_BAC`, redéfinis ici plutôt qu'importés :
# ce module ne doit pas dépendre de la couche de transformation pour un simple
# libellé d'affichage.
LIBELLES_TYPE_BAC: dict[str, str] = {"bg": "Général", "bt": "Technologique", "bp": "Professionnel"}

DOSSIER_FIGURES_DEFAUT = PROJECT_ROOT / "reports" / "figures"
NOM_FIGURE_CALIBRATION = "e23-calibration.png"


@dataclass(frozen=True)
class ScoreVentile:
    """Le score du modèle et celui de la baseline, sur le seul sous-ensemble d'un type de baccalauréat."""

    type_bac: str
    libelle: str
    modele: ScoreSession
    baseline: ScoreSession

    def resume(self) -> str:
        return (
            f"  {self.libelle:16s} modele    {self.modele.resume()}\n"
            f"  {'':16s} baseline  {self.baseline.resume()}"
        )


@dataclass(frozen=True)
class RapportEvaluation:
    """Ce que `make evaluate` (E23) a produit : comparaison, calibration, ventilation — à déclarer telles quelles."""

    scores_validation: ScoreSession
    scores_test: ScoreSession
    baseline_validation: ScoreSession
    baseline_test: ScoreSession
    calibration_modele_validation: RapportCalibration
    calibration_modele_test: RapportCalibration
    calibration_baseline_validation: RapportCalibration
    calibration_baseline_test: RapportCalibration
    ventilation_validation: list[ScoreVentile]
    ventilation_test: list[ScoreVentile]
    chemin_figure: Path

    def resume(self) -> str:
        lignes = [
            "Comparaison au plancher (E21), à couverture égale :",
            f"  modele    {self.scores_validation.resume()}",
            f"  baseline  {self.baseline_validation.resume()}",
            f"  modele    {self.scores_test.resume()}",
            f"  baseline  {self.baseline_test.resume()}",
            "",
            "Calibration (ECE pondérée par l'effectif) :",
            f"  modele    {self.calibration_modele_validation.resume()}",
            f"  baseline  {self.calibration_baseline_validation.resume()}",
            f"  modele    {self.calibration_modele_test.resume()}",
            f"  baseline  {self.calibration_baseline_test.resume()}",
            "",
            "Ventilation par type de baccalauréat (test) :",
        ]
        for ventile in self.ventilation_test:
            lignes.append(ventile.resume())
        lignes.append(f"Figure de calibration : {self.chemin_figure}")
        return "\n".join(lignes)


def _type_bac(jeu: JeuDonnees) -> pd.Series:
    """`type_bac` est une variable licite du modèle (dimension de la cellule, ADR 0009) :
    elle est déjà dans `jeu.X`, jamais rechargée séparément depuis la table source.
    """
    return jeu.X["type_bac"].astype(str)


def ventiler_par_type_bac(
    jeu: JeuDonnees, prediction_modele: np.ndarray, prediction_baseline: pd.Series, perimetre: str
) -> list[ScoreVentile]:
    """Le score du modèle et celui de la baseline, séparément pour chaque type de baccalauréat.

    Une erreur moyenne peut masquer une erreur très inégale selon le profil
    (`04-modele/evaluation.md`) : nécessaire ici avant l'audit d'équité
    (E26), qui s'appuiera sur cette même ventilation.
    """
    type_bac = _type_bac(jeu)
    prediction_baseline_array = prediction_baseline.to_numpy(dtype="float64")
    ventilation = []
    for code in sorted(type_bac.unique()):
        masque = (type_bac == code).to_numpy()
        sous_jeu = JeuDonnees(
            X=jeu.X.loc[masque] if hasattr(jeu.X, "loc") else jeu.X[masque],
            y=jeu.y[masque],
            poids=jeu.poids[masque],
            sessions=jeu.sessions[masque],
        )
        ventilation.append(
            ScoreVentile(
                type_bac=code,
                libelle=LIBELLES_TYPE_BAC.get(code, code),
                modele=score(sous_jeu.y, sous_jeu.poids, prediction_modele[masque], f"{perimetre}-{code}"),
                baseline=score(
                    sous_jeu.y, sous_jeu.poids, prediction_baseline_array[masque], f"{perimetre}-{code}"
                ),
            )
        )
    return ventilation


def _tracer_calibration(
    calibration_modele: RapportCalibration, calibration_baseline: RapportCalibration, destination: Path
) -> Path:
    """Le diagramme de fiabilité du test 2025 : modèle contre baseline contre calibration parfaite.

    Un point sur la diagonale annoncerait exactement ce qui se réalise ; un
    point au-dessus signale une sur-confiance dans cette tranche, un point
    en dessous une sous-confiance — lecture rendue explicite en légende
    plutôt que laissée à l'interprétation du lecteur.
    """
    figure, axe = plt.subplots(figsize=(6, 6))
    axe.plot([0, 1], [0, 1], linestyle="--", color="grey", label="Calibration parfaite")

    for rapport, couleur, marqueur, nom in (
        (calibration_modele, "tab:blue", "o", "LightGBM"),
        (calibration_baseline, "tab:orange", "s", "Baseline (taux N-1)"),
    ):
        if not rapport.points:
            continue
        x = [point.prediction_moyenne for point in rapport.points]
        y = [point.observe_moyen for point in rapport.points]
        poids_max = max(point.poids for point in rapport.points)
        tailles = [max(20.0, point.poids / max(1.0, poids_max) * 400.0) for point in rapport.points]
        etiquette = f"{nom} (ECE={rapport.ece:.4f})"
        axe.scatter(x, y, s=tailles, c=couleur, marker=marqueur, alpha=0.75, label=etiquette)

    axe.set_xlabel("Taux prédit moyen (par tranche, pondéré par l'effectif)")
    axe.set_ylabel("Taux observé moyen (par tranche, pondéré par l'effectif)")
    axe.set_xlim(0.0, 1.0)
    axe.set_ylim(0.0, 1.0)
    axe.set_title("Calibration — test 2025 (E23)")
    axe.legend(loc="upper left")
    figure.tight_layout()

    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=150)
    plt.close(figure)
    return destination


def _journaliser_mlflow(rapport: RapportEvaluation, settings: Settings) -> None:
    """Enregistre l'évaluation dans MLflow : métriques de comparaison, ECE, figure en artefact.

    Même politique que `models.train._journaliser_mlflow` : l'absence de
    `mlflow_tracking_uri` ou du paquet est journalisée, pas masquée, et
    l'évaluation déjà calculée ne dépend jamais de ce suivi pour exister.
    """
    if not settings.mlflow_tracking_uri:
        LOGGER.warning("MLFLOW_TRACKING_URI non configuré : évaluation non journalisée dans MLflow (E23).")
        return
    try:
        import mlflow
    except ImportError:
        LOGGER.warning("Le paquet mlflow n'est pas installé dans cet environnement : évaluation non journalisée.")
        return

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(NOM_EXPERIENCE_MLFLOW)
    with mlflow.start_run(run_name="evaluation-calibration"):
        mlflow.set_tag("etape", "E23")
        for score_session, prefixe in (
            (rapport.scores_validation, "modele_validation"),
            (rapport.scores_test, "modele_test"),
            (rapport.baseline_validation, "baseline_validation"),
            (rapport.baseline_test, "baseline_test"),
        ):
            mlflow.log_metric(f"{prefixe}_mae_ponderee", score_session.mae_ponderee)
            mlflow.log_metric(f"{prefixe}_mae_non_ponderee", score_session.mae_non_ponderee)
        for calib, prefixe in (
            (rapport.calibration_modele_validation, "modele_validation"),
            (rapport.calibration_modele_test, "modele_test"),
            (rapport.calibration_baseline_validation, "baseline_validation"),
            (rapport.calibration_baseline_test, "baseline_test"),
        ):
            mlflow.log_metric(f"{prefixe}_ece", calib.ece)
        for ventile in rapport.ventilation_test:
            mlflow.log_metric(f"test_{ventile.type_bac}_modele_mae_ponderee", ventile.modele.mae_ponderee)
            mlflow.log_metric(f"test_{ventile.type_bac}_baseline_mae_ponderee", ventile.baseline.mae_ponderee)
        mlflow.log_artifact(str(rapport.chemin_figure))


def executer(settings: Settings | None = None, dossier_figures: Path | None = None) -> RapportEvaluation:
    """Entraîne (E22) puis évalue (E23) : calibration, ECE, ventilation par type de baccalauréat.

    `dossier_figures` : `reports/figures/` du dépôt par défaut ; paramétrable
    pour que les tests écrivent dans un répertoire jetable plutôt que dans le
    dépôt versionné.
    """
    settings = settings or get_settings()
    dossier_figures = dossier_figures or DOSSIER_FIGURES_DEFAUT
    n_tranches = settings.evaluation.n_tranches_calibration

    resultat = train.entrainer_et_evaluer(settings)
    split = settings.modele.split

    prediction_baseline_validation = predictions_baseline_couverture_egale(
        resultat.table, COLONNE_TAUX_PRECEDENT, resultat.moyenne_groupe, split.validation
    )
    prediction_baseline_test = predictions_baseline_couverture_egale(
        resultat.table, COLONNE_TAUX_PRECEDENT, resultat.moyenne_groupe, split.test
    )

    jeu_validation, jeu_test = resultat.jeu_validation, resultat.jeu_test
    calibration_modele_validation = calibration(
        jeu_validation.y, jeu_validation.poids, resultat.prediction_validation, n_tranches, "validation"
    )
    calibration_modele_test = calibration(
        jeu_test.y, jeu_test.poids, resultat.prediction_test, n_tranches, "test"
    )
    calibration_baseline_validation = calibration(
        jeu_validation.y, jeu_validation.poids, prediction_baseline_validation, n_tranches, "validation"
    )
    calibration_baseline_test = calibration(
        jeu_test.y, jeu_test.poids, prediction_baseline_test, n_tranches, "test"
    )

    chemin_figure = _tracer_calibration(
        calibration_modele_test, calibration_baseline_test, dossier_figures / NOM_FIGURE_CALIBRATION
    )

    rapport = RapportEvaluation(
        scores_validation=resultat.rapport.scores_validation,
        scores_test=resultat.rapport.scores_test,
        baseline_validation=resultat.rapport.baseline_validation,
        baseline_test=resultat.rapport.baseline_test,
        calibration_modele_validation=calibration_modele_validation,
        calibration_modele_test=calibration_modele_test,
        calibration_baseline_validation=calibration_baseline_validation,
        calibration_baseline_test=calibration_baseline_test,
        ventilation_validation=ventiler_par_type_bac(
            resultat.jeu_validation, resultat.prediction_validation, prediction_baseline_validation, "validation"
        ),
        ventilation_test=ventiler_par_type_bac(
            resultat.jeu_test, resultat.prediction_test, prediction_baseline_test, "test"
        ),
        chemin_figure=chemin_figure,
    )

    _journaliser_mlflow(rapport, settings)
    return rapport


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rapport = executer()
    LOGGER.info("Évaluation (E23) terminée.\n%s", rapport.resume())
    return 0


if __name__ == "__main__":
    sys.exit(main())
