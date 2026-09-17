"""Courbe d'apprentissage du modèle d'accessibilité (E24) : le volume suffit-il ?

## La question posée, et pourquoi une courbe plutôt qu'une affirmation

L'entraînement (E22) montre un modèle qui bat le plancher en validation 2024
mais reste derrière en test 2025 (voir `models/train.py`,
`HYPERPARAMETRES_EXPLORES`). Deux causes distinctes produisent le même
symptôme et ne se soignent pas de la même façon :

- **manque de volume** — l'entraînement et la validation n'ont pas fini de
  converger ; ajouter des données réduirait encore l'écart ;
- **dérive temporelle** — les deux courbes ont déjà rejoint un plateau ; le
  problème n'est pas la quantité de passé disponible, c'est que ce passé ne
  décrit plus assez bien 2025.

Ce module entraîne le même modèle (mêmes hyperparamètres que
`configs/base.yaml`, jamais réglés ici une seconde fois) sur 10, 25, 50 puis
100 % du jeu d'entraînement, et mesure à chaque palier la MAE pondérée sur ce
sous-ensemble d'entraînement et sur la validation 2024 entière — jamais sur
le test 2025, qui n'a pas sa place dans un diagnostic de volume.

## Comment le sous-échantillonnage respecte le protocole temporel

Il y a deux façons de retirer 90 % du volume d'entraînement :

1. **Reculer la fenêtre** — entraîner sur une seule des quatre sessions
   (2023 pour ~25 %) plutôt que sur les quatre (2020-2023). Cela répond à
   une question différente : « la session la plus récente suffit-elle,
   seule ? » — un mélange de deux effets, le volume ET la proximité
   temporelle avec la période prédite, qu'on ne peut plus démêler ensuite.
2. **Réduire à l'intérieur de chaque session** — retenu ici. Chaque palier
   `p` conserve un tirage aléatoire de `p` % des cellules **de chaque
   session** d'entraînement (`DataFrame.groupby("session").sample`), donc la
   même période 2020-2023 reste représentée à chaque palier, dans les mêmes
   proportions. Seul le nombre de cellules varie : la courbe isole
   l'effet du volume de l'effet de la fenêtre temporelle, ce que l'option 1
   ne permet pas.

Le tirage est fait par cellule, avec une graine fixe
(reproductibilité) : la même cellule n'apparaît jamais deux fois dans un même
palier, et aucune cellule de validation ou de test n'est jamais touchée par
ce sous-échantillonnage — il porte exclusivement sur les sessions
d'entraînement du split (ADR 0012), déjà strictement antérieures à la
validation.

## Ce que ce module réutilise, et ne recalcule jamais deux fois

La table de variables (E20), les colonnes licites (E22, `colonnes_features`),
la préparation des types (`preparer_matrice`), l'ajout du taux précédent
(`ajouter_taux_precedent`) et la formule de MAE pondérée (`metrics.py`, E22)
sont importés tels quels depuis `models.train` et `models.metrics` — jamais
réécrits ici. Seuls le sous-échantillonnage par palier et le tracé sont
propres à ce module.

## Dette assumée

Les paliers (10, 25, 50, 100 %) sont des constantes de ce module plutôt
qu'une entrée de `configs/base.yaml` : un travail parallèle modifie ce
fichier au moment de l'écriture de ce module (E23, évaluation et
calibration). Les y ajouter est un simple déplacement, sans risque
d'incohérence — mais qui doit attendre que ce fichier ne soit plus en cours
de modification par un autre travail.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # aucun serveur d'affichage sur les postes de calcul et en CI
import matplotlib.pyplot as plt
import pandas as pd

from edumatch.config import PROJECT_ROOT, Settings, get_settings
from edumatch.features.label import poids_effectif
from edumatch.models.jeux import JeuDonnees, preparer_matrice
from edumatch.models.metrics import mae_ponderee
from edumatch.models.train import charger_table, entrainer_modele, preparer_jeux

LOGGER = logging.getLogger(__name__)

DOSSIER_FIGURES_DEFAUT = PROJECT_ROOT / "reports" / "figures"
NOM_FIGURE = "courbe-apprentissage.png"

# Les quatre paliers demandés par le plan d'exécution (E24). 1.0 rejoue
# exactement l'entraînement complet de E22 : aucune donnée n'est retirée.
PALIERS: tuple[float, ...] = (0.10, 0.25, 0.50, 1.00)

GRAINE_ECHANTILLONNAGE = 42

NOM_EXPERIENCE_MLFLOW = "edumatch-accessibilite"


class ErreurCourbeApprentissage(RuntimeError):
    """La courbe ne peut pas être produite sans violer une garantie attendue."""


@dataclass(frozen=True)
class PointCourbe:
    """Le résultat d'un palier : la fraction retenue, son volume, et les deux MAE pondérées."""

    fraction: float
    n_cellules_entrainement: int
    meilleure_iteration: int
    mae_entrainement: float
    mae_validation: float

    def resume(self) -> str:
        return (
            f"{self.fraction * 100:5.0f} %  n_train={self.n_cellules_entrainement:6d}  "
            f"arbres={self.meilleure_iteration:4d}  "
            f"mae_entrainement={self.mae_entrainement:.4f}  mae_validation={self.mae_validation:.4f}"
        )


@dataclass(frozen=True)
class RapportCourbeApprentissage:
    """Ce que `make courbe-apprentissage` (E24) produit, à déclarer tel quel."""

    points: list[PointCourbe]
    chemin_figure: Path

    def resume(self) -> str:
        lignes = ["Courbe d'apprentissage (E24), MAE pondérée par palier de volume d'entraînement :"]
        lignes.extend(f"  {point.resume()}" for point in self.points)
        lignes.append(f"  figure : {self.chemin_figure}")
        return "\n".join(lignes)


def echantillonner_par_session(
    table_entrainement: pd.DataFrame, fraction: float, graine: int = GRAINE_ECHANTILLONNAGE
) -> pd.DataFrame:
    """Un tirage de `fraction` des cellules, à l'intérieur de chaque session, sans remise.

    Stratifié par session (`groupby("session").sample`) plutôt qu'un tirage
    global : sans cette précaution, un tirage aléatoire uniforme pourrait,
    par chance, sous-représenter une des quatre sessions d'entraînement à un
    palier donné et faire varier la composition temporelle en même temps que
    le volume — exactement ce que ce module doit éviter (voir le docstring
    du module, §2).

    `fraction == 1.0` retourne la table telle quelle plutôt que de rappeler
    `sample` : un tirage à 100 % doit être identique, ligne pour ligne, à
    l'entraînement complet de E22, jamais un réordonnancement aléatoire de
    la même table.
    """
    if not 0.0 < fraction <= 1.0:
        raise ErreurCourbeApprentissage(f"fraction={fraction} hors de l'intervalle (0, 1].")
    if fraction == 1.0:
        return table_entrainement
    return table_entrainement.groupby("session", group_keys=False).sample(frac=fraction, random_state=graine)


def _jeu_depuis_table(table: pd.DataFrame, colonnes: list[str]) -> JeuDonnees:
    """Reconstruit un `JeuDonnees` depuis une sous-table déjà filtrée — voir `models.train._extraire_jeu`.

    Réimplémenté ici plutôt qu'importé : `train._extraire_jeu` est un détail
    privé du module d'entraînement (préfixe `_`), et il filtre par liste de
    sessions plutôt que de prendre une table déjà filtrée — deux usages
    distincts pour la même construction élémentaire.
    """
    return JeuDonnees(
        X=preparer_matrice(table, colonnes),
        y=table["taux"].astype("float64"),
        poids=poids_effectif(table["effectif"]).astype("float64"),
        sessions=table["session"],
    )


def calculer_courbe(settings: Settings) -> list[PointCourbe]:
    """Entraîne le modèle sur chaque palier de `PALIERS` et mesure les deux MAE pondérées.

    Mêmes hyperparamètres et même arrêt anticipé sur la validation qu'en E22
    (`settings.modele.hyperparametres`) : seul le volume d'entraînement
    varie d'un palier à l'autre, jamais le réglage du modèle — sinon la
    courbe mêlerait l'effet du volume à un effet de réglage, et perdrait sa
    valeur de diagnostic.
    """
    table = charger_table(settings)
    colonnes, jeu_entrainement_complet, jeu_validation, _jeu_test = preparer_jeux(table, settings)
    table_entrainement = table[table["session"].isin(settings.modele.split.entrainement)]

    points: list[PointCourbe] = []
    for fraction in PALIERS:
        sous_table = echantillonner_par_session(table_entrainement, fraction)
        jeu = _jeu_depuis_table(sous_table, colonnes) if fraction < 1.0 else jeu_entrainement_complet
        modele = entrainer_modele(jeu, jeu_validation, settings.modele.hyperparametres)

        prediction_entrainement = modele.predict(jeu.X)
        prediction_validation = modele.predict(jeu_validation.X)

        points.append(
            PointCourbe(
                fraction=fraction,
                n_cellules_entrainement=len(jeu.y),
                meilleure_iteration=int(modele.best_iteration_ or settings.modele.hyperparametres.n_estimators),
                mae_entrainement=mae_ponderee(jeu.y, prediction_entrainement, jeu.poids),
                mae_validation=mae_ponderee(jeu_validation.y, prediction_validation, jeu_validation.poids),
            )
        )
        LOGGER.info("Palier %.0f %% : %s", fraction * 100, points[-1].resume())
    return points


def tracer_courbe(points: list[PointCourbe], chemin: Path) -> Path:
    """Trace les deux courbes (entraînement, validation) et écrit le PNG à `chemin`."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fractions_pct = [point.fraction * 100 for point in points]

    figure, axe = plt.subplots(figsize=(7, 5))
    axe.plot(fractions_pct, [p.mae_entrainement for p in points], marker="o", label="MAE pondérée — entraînement")
    axe.plot(fractions_pct, [p.mae_validation for p in points], marker="o", label="MAE pondérée — validation 2024")
    axe.set_xlabel("Part du jeu d'entraînement utilisée (%)")
    axe.set_ylabel("Erreur absolue moyenne pondérée par l'effectif")
    axe.set_title("Courbe d'apprentissage (E24) — le volume d'entraînement suffit-il ?")
    axe.set_xticks(fractions_pct)
    axe.legend()
    axe.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(chemin, dpi=150)
    plt.close(figure)
    return chemin


def _journaliser_mlflow(points: list[PointCourbe], settings: Settings, chemin_figure: Path) -> None:
    """Enregistre les points de la courbe dans MLflow, même politique que `models.train`.

    Absence de `mlflow_tracking_uri` ou du paquet : journalisée, pas
    masquée — la courbe est déjà calculée et tracée avant cet appel.
    """
    if not settings.mlflow_tracking_uri:
        LOGGER.warning("MLFLOW_TRACKING_URI non configuré : courbe d'apprentissage non journalisée dans MLflow (E24).")
        return
    try:
        import mlflow
    except ImportError:
        LOGGER.warning("Le paquet mlflow n'est pas installé dans cet environnement : courbe non journalisée.")
        return

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(NOM_EXPERIENCE_MLFLOW)
    with mlflow.start_run(run_name="courbe-apprentissage-e24"):
        mlflow.set_tag("etape", "E24")
        for point in points:
            suffixe = f"{int(point.fraction * 100)}pct"
            mlflow.log_metric(f"mae_entrainement_{suffixe}", point.mae_entrainement)
            mlflow.log_metric(f"mae_validation_{suffixe}", point.mae_validation)
            mlflow.log_metric(f"n_cellules_{suffixe}", point.n_cellules_entrainement)
        mlflow.log_artifact(str(chemin_figure))


def executer(settings: Settings | None = None, dossier_figures: Path | None = None) -> RapportCourbeApprentissage:
    """Point d'entrée de `make courbe-apprentissage` (E24) : le rapport complet, figure comprise.

    `dossier_figures` : `reports/figures/` du dépôt par défaut ; paramétrable
    pour que les tests écrivent dans un répertoire jetable plutôt que dans le
    dépôt versionné (même convention que `models.evaluate.executer`).
    """
    settings = settings or get_settings()
    dossier_figures = dossier_figures or DOSSIER_FIGURES_DEFAUT

    points = calculer_courbe(settings)
    chemin_figure = tracer_courbe(points, dossier_figures / NOM_FIGURE)
    _journaliser_mlflow(points, settings, chemin_figure)

    return RapportCourbeApprentissage(points=points, chemin_figure=chemin_figure)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rapport = executer()
    LOGGER.info("Courbe d'apprentissage (E24) terminée.\n%s", rapport.resume())
    return 0


if __name__ == "__main__":
    sys.exit(main())
