"""Détection de dérive du modèle d'accessibilité (E34) : `make derive`.

## Ce que ce module mesure, et sur quelle fenêtre

Trois dérives distinctes (voir aussi `docs/sous-docs-projets/adr/0018-...`), jamais
confondues dans le rapport :

1. **Dérive des variables** — P(X) change-t-il d'une session à l'autre ? Sur les 46
   variables licites du modèle (`modele.variables`, ADR 0013 : les deux dimensions de
   cellule, les neuf colonnes de catalogue, les 35 colonnes décalées), pas sur les deux
   colonnes dérivées de `models.train` (`taux_session_precedente`, `a_antecedent`), qui ne
   sont pas des observations mais un calcul dérivé des variables décalées déjà mesurées.
2. **Dérive de la cible** — P(Y) change-t-il ? Sur `taux`, la même colonne que
   `models.metrics.calibration` (E23) lit pour comparer prédiction et réalité.
3. **Dérive des prédictions** — P(Ŷ) change-t-il ? Le modèle déjà entraîné
   (`models.train.entrainer_et_evaluer`, jamais réentraîné une seconde fois ici) prédit sur
   chaque session ; ce module compare la distribution de ces prédictions, pas leur erreur
   par rapport à la cible (déjà couverte par E23).

Fenêtre : les six sessions où le label existe (2020-2025, ADR 0012) — le fichier
Parcoursup brut en couvre huit (2018-2025), mais les deux premières n'ont pas de cible
observée (ADR 0012) et ne peuvent donc alimenter ni la dérive de la cible ni celle des
prédictions ; les mesurer sur une fenêtre différente selon la dérive romprait la
comparaison entre les trois. Toute mention de « huit millésimes » pour ce rapport renvoie
au constat qualitatif de l'ADR 0012 (réforme du baccalauréat 2020, campagne 2020) : la
fenêtre effectivement mesurée ici est celle où le label existe, six sessions, exactement
celle de l'entraînement et de l'évaluation.

## Deux familles de comparaison

- **Comparaison de production** — la référence (`distribution_entrainement`,
  `DeriveConfig.reference` : les quatre sessions d'entraînement 2020-2023 regroupées)
  contre chacune des deux sessions non vues (validation 2024, test 2025). C'est la mesure
  qui gouverne `reentrainement_recommande`.
- **Comparaison consécutive** — chaque session contre la précédente (2020→2021 …
  2024→2025), cinq paires. Purement diagnostique : elle sert à calibrer ce qu'est une
  dérive "normale" d'une session sur l'autre (voir le compte rendu de l'étape et
  l'ADR 0018 pour la mesure qui a arrêté le seuil), pas à déclencher quoi que ce soit.

## Le déclenchement : sur la médiane des variables, jamais sur leur maximum

`reentrainement_recommande` compare `DeriveConfig.seuil_reentrainement` à la **médiane**
du PSI des 46 variables pour chaque comparaison de production, pas à leur maximum. Mesuré
sur ce dépôt : `region_etab_aff` et `select_form` dépassent seules seuil=0,20 même après
neutralisation des variations de forme (`derive_stats.canoniser_categorie`) — la première
parce que la nomenclature des régions Parcoursup change de libellé plusieurs fois sur la
période (« Centre-Val de Loire » devient « Centre », etc.), la seconde à cause d'un
libellé tronqué propre au seul millésime 2020 (« formation non selec »). Une seule colonne
de nomenclature instable ne dit rien de la distribution du problème dans son ensemble —
elle apparaît d'ailleurs au rang 45 sur 48 de l'importance du modèle (E22) pour
`region_etab_aff`. Prendre le maximum aurait fait dépasser le seuil en permanence pour un
motif qui n'affecte jamais la performance : exactement l'écueil que la consigne de cette
étape demande d'éviter. La liste des variables individuellement au-delà du seuil reste
rapportée (`resume()`), comme diagnostic de dérive amont, jamais comme déclencheur.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # aucun serveur d'affichage sur les postes de calcul et en CI
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from edumatch.config import PROJECT_ROOT, DeriveConfig, Settings, get_settings
from edumatch.models import derive_stats, train
from edumatch.models.jeux import extraire_jeu

LOGGER = logging.getLogger(__name__)

NOM_EXPERIENCE_MLFLOW = "edumatch-derive"

COLONNE_CIBLE = "taux"
LIBELLE_CIBLE = "taux (cible observée)"
LIBELLE_PREDICTION = "taux prédit (sortie du modèle)"

DOSSIER_FIGURES_DEFAUT = PROJECT_ROOT / "reports" / "figures"
NOM_FIGURE_VARIABLES = "derive-variables.png"
NOM_FIGURE_TRAJECTOIRE = "derive-trajectoire.png"

COMPARAISON_VALIDATION = "entrainement -> validation-2024"
COMPARAISON_TEST = "entrainement -> test-2025"


@dataclass(frozen=True)
class ScoreDerive:
    """PSI et KS d'une variable entre une référence et une comparaison données."""

    variable: str
    type_variable: str  # "numerique" ou "categorielle"
    comparaison: str
    n_reference: int
    n_comparaison: int
    psi: float
    ks: float | None
    au_dela_du_seuil: bool

    def resume(self) -> str:
        ks_texte = f"ks={self.ks:.3f}" if self.ks is not None else "ks=n/a (catégorielle)"
        marqueur = "  *** SEUIL DEPASSE ***" if self.au_dela_du_seuil else ""
        return (
            f"[{self.comparaison:28s}] {self.variable:32s} ({self.type_variable:12s}) "
            f"psi={self.psi:.4f}  {ks_texte}{marqueur}"
        )


def mesurer_variable(
    nom: str,
    reference: pd.Series,
    comparaison: pd.Series,
    comparaison_libelle: str,
    cfg: DeriveConfig,
) -> ScoreDerive:
    """PSI (et KS si numérique) d'une variable entre `reference` et `comparaison`.

    Le type (numérique ou catégorielle) est lu sur `reference` (`derive_stats.est_categorielle`) :
    c'est elle qui définit les tranches ou les modalités attendues, la comparaison s'y
    ajuste, jamais l'inverse.
    """
    categorielle = derive_stats.est_categorielle(reference)
    if categorielle:
        psi = derive_stats.psi_categorielle(reference, comparaison, cfg.top_k_categories_psi)
        ks = None
    else:
        psi = derive_stats.psi_numerique(reference, comparaison, cfg.n_tranches_psi)
        ks = derive_stats.ks_numerique(reference, comparaison)
    return ScoreDerive(
        variable=nom,
        type_variable="categorielle" if categorielle else "numerique",
        comparaison=comparaison_libelle,
        n_reference=int(reference.notna().sum()),
        n_comparaison=int(comparaison.notna().sum()),
        psi=psi,
        ks=ks,
        au_dela_du_seuil=psi >= cfg.seuil_reentrainement,
    )


def _mesurer_colonnes(
    reference_df: pd.DataFrame, comparaison_df: pd.DataFrame, colonnes: list[str], libelle: str, cfg: DeriveConfig
) -> list[ScoreDerive]:
    return [mesurer_variable(colonne, reference_df[colonne], comparaison_df[colonne], libelle, cfg) for colonne in colonnes]


@dataclass(frozen=True)
class RapportDerive:
    """Ce que `make derive` (E34) a produit : trois familles de dérive, à déclarer telles quelles."""

    seuil_reentrainement: float
    derive_variables_production: list[ScoreDerive]
    derive_variables_consecutive: list[ScoreDerive]
    derive_cible_production: list[ScoreDerive]
    derive_cible_consecutive: list[ScoreDerive]
    derive_predictions_production: list[ScoreDerive]
    derive_predictions_consecutive: list[ScoreDerive]
    chemin_figure_variables: Path
    chemin_figure_trajectoire: Path

    @property
    def mediane_variables_par_comparaison(self) -> dict[str, float]:
        """La médiane du PSI des 46 variables, par comparaison de production — voir docstring du module."""
        comparaisons = sorted({score.comparaison for score in self.derive_variables_production})
        return {
            comparaison: float(
                np.median([score.psi for score in self.derive_variables_production if score.comparaison == comparaison])
            )
            for comparaison in comparaisons
        }

    @property
    def reentrainement_recommande(self) -> bool:
        """OU logique des trois familles, sur les seules comparaisons de production (voir docstring du module)."""
        variables_derivent = any(
            mediane >= self.seuil_reentrainement for mediane in self.mediane_variables_par_comparaison.values()
        )
        cible_derive = any(score.au_dela_du_seuil for score in self.derive_cible_production)
        predictions_derivent = any(score.au_dela_du_seuil for score in self.derive_predictions_production)
        return variables_derivent or cible_derive or predictions_derivent

    def resume(self) -> str:
        lignes = [f"Seuil de réentraînement (PSI, ADR 0018) : {self.seuil_reentrainement:.2f}", ""]
        lignes.append("Dérive des variables — médiane des 46 variables (catégorielles canonisées) :")
        for comparaison, mediane in self.mediane_variables_par_comparaison.items():
            marqueur = "  *** SEUIL DEPASSE ***" if mediane >= self.seuil_reentrainement else ""
            lignes.append(f"  {comparaison:28s} mediane={mediane:.4f}{marqueur}")
        au_dela = sorted(
            (score for score in self.derive_variables_production if score.au_dela_du_seuil),
            key=lambda score: -score.psi,
        )
        if au_dela:
            lignes.append("  Variables individuellement au-delà du seuil (diagnostic de dérive amont, jamais un déclencheur) :")
            for score in au_dela:
                lignes.append(f"    {score.resume()}")
        lignes.append("")
        lignes.append("Dérive de la cible (taux observé, production) :")
        lignes.extend(f"  {score.resume()}" for score in self.derive_cible_production)
        lignes.append("")
        lignes.append("Dérive des prédictions du modèle (production) :")
        lignes.extend(f"  {score.resume()}" for score in self.derive_predictions_production)
        lignes.append("")
        verdict = "OUI" if self.reentrainement_recommande else "NON"
        lignes.append(f"Réentraînement recommandé : {verdict}")
        lignes.append(f"Figures : {self.chemin_figure_variables.name}, {self.chemin_figure_trajectoire.name}")
        return "\n".join(lignes)


def _tracer_figure_variables(scores_test: list[ScoreDerive], seuil: float, destination: Path) -> Path:
    """Les 15 variables les plus dérivées (entraînement -> test 2025), triées, seuil marqué."""
    classement = sorted(scores_test, key=lambda score: -score.psi)[:15]
    classement = list(reversed(classement))  # barh dessine du bas vers le haut
    couleurs = ["tab:red" if score.au_dela_du_seuil else "tab:blue" for score in classement]

    figure, axe = plt.subplots(figsize=(8, 6))
    axe.barh([score.variable for score in classement], [score.psi for score in classement], color=couleurs)
    axe.axvline(seuil, color="black", linestyle="--", label=f"seuil de réentraînement ({seuil:.2f})")
    axe.set_xlabel("PSI (entraînement 2020-2023 -> test 2025)")
    axe.set_title("Dérive des variables — 15 plus fortes (E34)")
    axe.legend(loc="lower right")
    figure.tight_layout()

    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=150)
    plt.close(figure)
    return destination


def _tracer_figure_trajectoire(
    derive_variables_consecutive: list[ScoreDerive],
    derive_cible_consecutive: list[ScoreDerive],
    derive_predictions_consecutive: list[ScoreDerive],
    seuil: float,
    destination: Path,
) -> Path:
    """PSI session par session (comparaisons consécutives) pour les trois familles, seuil marqué."""
    comparaisons = sorted({score.comparaison for score in derive_variables_consecutive})

    def _serie(scores: list[ScoreDerive], reducteur) -> list[float]:
        return [reducteur([score.psi for score in scores if score.comparaison == comparaison]) for comparaison in comparaisons]

    mediane_variables = _serie(derive_variables_consecutive, np.median)
    cible = _serie(derive_cible_consecutive, lambda valeurs: valeurs[0])
    predictions = _serie(derive_predictions_consecutive, lambda valeurs: valeurs[0])

    figure, axe = plt.subplots(figsize=(8, 5))
    axe.plot(comparaisons, mediane_variables, marker="o", label="variables (médiane des 46)")
    axe.plot(comparaisons, cible, marker="s", label="cible (taux)")
    axe.plot(comparaisons, predictions, marker="^", label="prédictions du modèle")
    axe.axhline(seuil, color="black", linestyle="--", label="seuil de réentraînement")
    axe.set_ylabel("PSI")
    axe.set_title("Dérive session par session, comparaisons consécutives (E34)")
    axe.tick_params(axis="x", rotation=30)
    axe.legend(loc="upper left")
    figure.tight_layout()

    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=150)
    plt.close(figure)
    return destination


def _journaliser_mlflow(rapport: RapportDerive, settings: Settings) -> None:
    """Enregistre le rapport de dérive dans MLflow : médianes, dérive cible/prédictions, verdict, figures.

    Même politique que `models.evaluate._journaliser_mlflow` : l'absence de
    `mlflow_tracking_uri` ou du paquet est journalisée, jamais masquée.
    """
    if not settings.mlflow_tracking_uri:
        LOGGER.warning("MLFLOW_TRACKING_URI non configuré : dérive non journalisée dans MLflow (E34).")
        return
    try:
        import mlflow
    except ImportError:
        LOGGER.warning("Le paquet mlflow n'est pas installé dans cet environnement : dérive non journalisée.")
        return

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(NOM_EXPERIENCE_MLFLOW)
    with mlflow.start_run(run_name="derive-psi-ks"):
        mlflow.set_tag("etape", "E34")
        mlflow.log_param("seuil_reentrainement", rapport.seuil_reentrainement)
        mlflow.log_param("reentrainement_recommande", rapport.reentrainement_recommande)
        for comparaison, mediane in rapport.mediane_variables_par_comparaison.items():
            mlflow.log_metric(f"variables_mediane_psi_{comparaison}", mediane)
        for score in rapport.derive_cible_production:
            mlflow.log_metric(f"cible_psi_{score.comparaison}", score.psi)
        for score in rapport.derive_predictions_production:
            mlflow.log_metric(f"predictions_psi_{score.comparaison}", score.psi)
        mlflow.log_artifact(str(rapport.chemin_figure_variables))
        mlflow.log_artifact(str(rapport.chemin_figure_trajectoire))


def _predictions_par_session(modele: object, table: pd.DataFrame, colonnes: list[str], sessions: list[int]) -> pd.Series:
    """Prédictions du modèle déjà entraîné sur `sessions`, jamais un réentraînement."""
    jeu = extraire_jeu(table, sessions, colonnes)
    return pd.Series(modele.predict(jeu.X), index=jeu.X.index)  # type: ignore[attr-defined]


def _paires_consecutives(table: pd.DataFrame) -> list[tuple[int, int]]:
    sessions = sorted(int(session) for session in table["session"].unique())
    return list(pairwise(sessions))


def _derive_variables(
    table: pd.DataFrame,
    table_reference: pd.DataFrame,
    table_validation: pd.DataFrame,
    table_test: pd.DataFrame,
    paires: list[tuple[int, int]],
    colonnes: list[str],
    cfg: DeriveConfig,
) -> tuple[list[ScoreDerive], list[ScoreDerive]]:
    """Dérive des variables (P(X)) : comparaisons de production puis consécutives."""
    production = _mesurer_colonnes(
        table_reference, table_validation, colonnes, COMPARAISON_VALIDATION, cfg
    ) + _mesurer_colonnes(table_reference, table_test, colonnes, COMPARAISON_TEST, cfg)
    consecutive = [
        score
        for a, b in paires
        for score in _mesurer_colonnes(table[table["session"] == a], table[table["session"] == b], colonnes, f"{a} -> {b}", cfg)
    ]
    return production, consecutive


def _derive_cible(
    table: pd.DataFrame,
    table_reference: pd.DataFrame,
    table_validation: pd.DataFrame,
    table_test: pd.DataFrame,
    paires: list[tuple[int, int]],
    cfg: DeriveConfig,
) -> tuple[list[ScoreDerive], list[ScoreDerive]]:
    """Dérive de la cible (P(Y), `taux`) : comparaisons de production puis consécutives."""
    production = [
        mesurer_variable(LIBELLE_CIBLE, table_reference[COLONNE_CIBLE], table_validation[COLONNE_CIBLE], COMPARAISON_VALIDATION, cfg),
        mesurer_variable(LIBELLE_CIBLE, table_reference[COLONNE_CIBLE], table_test[COLONNE_CIBLE], COMPARAISON_TEST, cfg),
    ]
    consecutive = [
        mesurer_variable(
            LIBELLE_CIBLE, table[table["session"] == a][COLONNE_CIBLE], table[table["session"] == b][COLONNE_CIBLE], f"{a} -> {b}", cfg
        )
        for a, b in paires
    ]
    return production, consecutive


def _derive_predictions(
    resultat: train.ResultatEntrainement,
    table: pd.DataFrame,
    split: object,
    paires: list[tuple[int, int]],
    cfg: DeriveConfig,
) -> tuple[list[ScoreDerive], list[ScoreDerive]]:
    """Dérive des prédictions (P(Ŷ)) : le modèle n'est jamais réentraîné ici, seulement interrogé."""
    colonnes_modele = resultat.colonnes
    prediction_entrainement = _predictions_par_session(resultat.modele, table, colonnes_modele, split.entrainement)
    prediction_validation = pd.Series(resultat.prediction_validation, index=resultat.jeu_validation.X.index)
    prediction_test = pd.Series(resultat.prediction_test, index=resultat.jeu_test.X.index)
    production = [
        mesurer_variable(LIBELLE_PREDICTION, prediction_entrainement, prediction_validation, COMPARAISON_VALIDATION, cfg),
        mesurer_variable(LIBELLE_PREDICTION, prediction_entrainement, prediction_test, COMPARAISON_TEST, cfg),
    ]
    consecutive = [
        mesurer_variable(
            LIBELLE_PREDICTION,
            _predictions_par_session(resultat.modele, table, colonnes_modele, [a]),
            _predictions_par_session(resultat.modele, table, colonnes_modele, [b]),
            f"{a} -> {b}",
            cfg,
        )
        for a, b in paires
    ]
    return production, consecutive


def executer(settings: Settings | None = None, dossier_figures: Path | None = None) -> RapportDerive:
    """Point d'entrée de `make derive` (E34) : entraîne (E22, jamais une seconde fois après)
    puis mesure les trois dérives sur la fenêtre labellisée (voir docstring du module).
    """
    settings = settings or get_settings()
    dossier_figures = dossier_figures or DOSSIER_FIGURES_DEFAUT
    cfg = settings.derive
    variables = settings.modele.variables
    colonnes_variables = [*variables.dimensions_cellule, *variables.session_courante, *variables.decalees]

    resultat = train.entrainer_et_evaluer(settings)
    table = resultat.table
    split = settings.modele.split

    table_reference = table[table["session"].isin(split.entrainement)]
    table_validation = table[table["session"].isin(split.validation)]
    table_test = table[table["session"].isin(split.test)]
    paires = _paires_consecutives(table)

    variables_production, variables_consecutive = _derive_variables(
        table, table_reference, table_validation, table_test, paires, colonnes_variables, cfg
    )
    cible_production, cible_consecutive = _derive_cible(table, table_reference, table_validation, table_test, paires, cfg)
    predictions_production, predictions_consecutive = _derive_predictions(resultat, table, split, paires, cfg)

    scores_variables_test = [score for score in variables_production if score.comparaison == COMPARAISON_TEST]
    chemin_figure_variables = _tracer_figure_variables(
        scores_variables_test, cfg.seuil_reentrainement, dossier_figures / NOM_FIGURE_VARIABLES
    )
    chemin_figure_trajectoire = _tracer_figure_trajectoire(
        variables_consecutive, cible_consecutive, predictions_consecutive, cfg.seuil_reentrainement, dossier_figures / NOM_FIGURE_TRAJECTOIRE
    )

    rapport = RapportDerive(
        seuil_reentrainement=cfg.seuil_reentrainement,
        derive_variables_production=variables_production,
        derive_variables_consecutive=variables_consecutive,
        derive_cible_production=cible_production,
        derive_cible_consecutive=cible_consecutive,
        derive_predictions_production=predictions_production,
        derive_predictions_consecutive=predictions_consecutive,
        chemin_figure_variables=chemin_figure_variables,
        chemin_figure_trajectoire=chemin_figure_trajectoire,
    )

    _journaliser_mlflow(rapport, settings)
    return rapport


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rapport = executer()
    LOGGER.info("Détection de dérive (E34) terminée.\n%s", rapport.resume())
    if rapport.reentrainement_recommande:
        LOGGER.warning("Dérive au-delà du seuil de réentraînement : voir le rapport ci-dessus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
