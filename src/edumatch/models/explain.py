"""Explicabilité du modèle d'accessibilité : TreeSHAP, précalculé par cellule.

## Pourquoi TreeSHAP, et pourquoi précalculé

`models/train.py` justifie LightGBM par l'explicabilité exacte que permet
TreeSHAP sur un modèle à arbres. Ce module encaisse cette promesse. Sur un
réseau de neurones, une valeur de Shapley exacte serait hors de portée (coût
exponentiel dans le nombre de variables), il faudrait se contenter d'une
approximation (KernelSHAP, LIME) ; sur LightGBM, TreeSHAP la calcule
**exactement**, en temps polynomial, en exploitant la structure des arbres
plutôt qu'en ré-échantillonnant des coalitions de variables.

Le nombre de cellules est fini — 440 030 sur les huit millésimes réels
(`04-modele/variables.md`) — donc le coût est borné à l'avance, contrairement
à un flux de requêtes illimité : c'est ce qui rend un **précalcul complet**
raisonnable plutôt qu'un calcul à la demande à chaque appel de l'API. Mesuré
ici : environ 930 cellules/seconde en mono-processus, ~8 minutes et ~85 Mo
pour les 440 030 cellules (48 variables en flottant 32 bits). Détail et
recommandation dans `RapportExplicabilite.recommandation_precalcul`.

## Ce que ce module ne fait pas

Il n'entraîne rien : il appelle `train.entrainer_et_evaluer`, comme
`evaluate.py` et `courbe_apprentissage.py` avant lui. Il ne
conduit pas l'audit d'équité : le poids des substituts du genre dans
l'explication globale, plus bas, est un **signal transmis** à cet audit, pas
une conclusion à sa place — voir l'ADR 0011.

## Le cas des variables corrélées, à surveiller ici précisément

`taux_session_precedente` est le quotient de deux variables déjà
présentes séparément : `prop_tot` (numérateur, admis N-1) et `nb_voe_pp`
(dénominateur, vœux N-1) — les trois sont corrélées par construction. Un
ensemble d'arbres retrouve la même information en coupant sur le quotient ou
en combinant des coupures sur numérateur et dénominateur : TreeSHAP répartit
le crédit selon l'usage réel qu'en font les arbres, pas selon une « cause
première » qui n'existe pas dans un ensemble d'arbres. Mesuré ici : les trois
variables réunies pèsent bien plus que `taux_session_precedente` seule (voir
`importance_globale`) — un rappel concret qu'une valeur de Shapley corrélée à
d'autres ne se lit jamais isolément.

## Limites de SHAP, à ne jamais taire

- Une valeur de Shapley contribue **au modèle**, pas à la réalité : elle
  explique ce que LightGBM a appris, pas pourquoi un candidat est admis. Ce
  n'est pas une preuve causale.
- Avec des variables corrélées, le partage du crédit est mathématiquement
  défini (les quatre axiomes de Shapley) mais peut être contre-intuitif : il
  dépend de la structure des arbres, pas d'une hiérarchie de causes.
- Une explication locale ne se généralise pas à une autre : d'où la vue
  globale, qui répond à une question différente.
- La moyenne des |SHAP| (l'importance globale) n'est pas une importance
  causale : c'est une moyenne de contributions à des prédictions, pondérée
  par l'effectif comme le reste de l'évaluation (`modele.ponderation`).
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")  # aucun serveur d'affichage sur les postes de calcul et en CI
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from edumatch.config import PROJECT_ROOT, Settings, get_settings
from edumatch.models import train
from edumatch.models.jeux import preparer_matrice

LOGGER = logging.getLogger(__name__)

NOM_EXPERIENCE_MLFLOW = "edumatch-accessibilite"

DOSSIER_FIGURES_DEFAUT = PROJECT_ROOT / "reports" / "figures"
NOM_FIGURE_IMPORTANCE = "importance-globale.png"

# Où vit le précalcul par cellule (le pendant de `features.build.SOUS_DOSSIER`,
# côté explicabilité plutôt que côté variables).
SOUS_DOSSIER_PRECALCUL = "explicabilite"
NOM_FICHIER_PRECALCUL = "explications_locales.parquet"

# Les quatre variables mesurées comme substituts du genre encore présentes
# dans le jeu de variables du modèle (ADR 0011). `cod_uai` et `ville_etab`,
# les deux substituts les plus forts mesurés, sont déjà exclus du modèle
# (`modele.variables.exclues`, motif "substitut") : ils ne peuvent donc pas
# apparaître ici. Liste redéfinie ici plutôt qu'importée de la configuration
# (`equite.substituts_a_tester` ne porte que les intitulés génériques
# "academie" / "etablissement_origine") pour pointer les noms de colonnes
# réels du jeu de variables, tels que mesurés par l'ADR 0011.
SUBSTITUTS_GENRE_DANS_LE_MODELE: tuple[str, ...] = ("fili", "select_form", "dep", "acad_mies")


class ErreurExplicabilite(RuntimeError):
    """L'explicabilité ne peut pas continuer sans violer une garantie attendue."""


@dataclass(frozen=True)
class ContributionVariable:
    """Le poids d'une variable dans l'explication globale : moyenne des valeurs
    absolues de SHAP, pondérée par l'effectif de la cellule.
    """

    nom: str
    importance: float
    part: float

    def resume(self) -> str:
        return f"{self.nom:32s} importance={self.importance:.5f}  part={self.part:.2%}"


@dataclass(frozen=True)
class ExempleLocal:
    """Une cellule réelle, sa prédiction et les variables qui l'expliquent.

    `contributions` : les variables triées par contribution absolue
    décroissante, chacune avec sa valeur brute et sa contribution SHAP signée
    — positive pousse la prédiction au-dessus de la valeur de base, négative
    en dessous.
    """

    session: int
    cod_aff_form: str
    type_bac: str
    boursier: bool
    effectif: float
    taux_observe: float
    prediction: float
    valeur_base: float
    contributions: list[tuple[str, object, float]]

    def resume(self) -> str:
        lignes = [
            (
                f"Cellule {self.cod_aff_form} — session {self.session}, "
                f"bac {self.type_bac}{' boursier' if self.boursier else ''}, "
                f"effectif={self.effectif:.0f} vœux"
            ),
            f"  Valeur de base (moyenne sur le jeu d'entraînement) : {self.valeur_base:.3f}",
            f"  Prédiction : {self.prediction:.3f}  —  Taux observé : {self.taux_observe:.3f}",
            "  Ce qui explique l'écart à la valeur de base, par ordre d'importance :",
        ]
        for nom, valeur, contribution in self.contributions:
            signe = "+" if contribution >= 0 else ""
            lignes.append(f"    {nom:28s} valeur={valeur!r:<20}  contribution={signe}{contribution:.4f}")
        return "\n".join(lignes)


@dataclass(frozen=True)
class RapportExplicabilite:
    """Ce que `make explain` a produit, à déclarer tel quel."""

    importance_globale: list[ContributionVariable]
    part_substituts_genre: dict[str, float]
    chemin_figure: Path
    exemple_haut: ExempleLocal
    exemple_bas: ExempleLocal
    n_cellules_precalculees: int
    duree_precalcul_secondes: float
    taille_octets_precalcul: int
    chemin_precalcul: Path

    def recommandation_precalcul(self) -> str:
        """Le précalcul complet est-il réaliste ? Verdict chiffré, pas supposé.

        Seuils de lecture, non configurables : ce n'est pas un paramètre
        métier mais un repère de communication (moins de 30 minutes et moins
        de 500 Mo tiennent sans discussion dans un job batch nocturne).
        """
        minutes = self.duree_precalcul_secondes / 60.0
        mega_octets = self.taille_octets_precalcul / 1_000_000.0
        if minutes <= 30.0 and mega_octets <= 500.0:
            verdict = "réaliste : un job batch après chaque réentraînement suffit"
        else:
            verdict = (
                "à restreindre : passer au calcul à la demande pour les cellules interrogées, "
                "précalculer seulement les plus consultées"
            )
        return (
            f"Précalcul complet mesuré sur {self.n_cellules_precalculees} cellules : "
            f"{minutes:.1f} min, {mega_octets:.1f} Mo -> {verdict}."
        )

    def resume(self) -> str:
        lignes = ["Explicabilité globale, TreeSHAP, moyenne pondérée par l'effectif :"]
        for contribution in self.importance_globale[:10]:
            lignes.append(f"  {contribution.resume()}")
        lignes.append("")
        lignes.append("Part des substituts du genre mesurés par l'ADR 0011, encore dans le modèle :")
        for nom, part in self.part_substituts_genre.items():
            lignes.append(f"  {nom:16s} part={part:.2%}")
        lignes.append("")
        lignes.append("Exemple local — prédiction haute :")
        lignes.append(self.exemple_haut.resume())
        lignes.append("")
        lignes.append("Exemple local — prédiction basse :")
        lignes.append(self.exemple_bas.resume())
        lignes.append("")
        lignes.append(self.recommandation_precalcul())
        lignes.append(f"Figure d'importance globale : {self.chemin_figure}")
        lignes.append(f"Précalcul par cellule : {self.chemin_precalcul}")
        return "\n".join(lignes)


def construire_explainer(modele: lgb.LGBMRegressor) -> shap.TreeExplainer:
    """L'explainer TreeSHAP du modèle entraîné.

    `shap.TreeExplainer` calcule les valeurs de Shapley **exactement** sur un
    modèle à base d'arbres, en parcourant leur structure — c'est l'algorithme
    TreeSHAP (Lundberg et al., 2020), en temps polynomial dans la profondeur
    des arbres plutôt qu'exponentiel dans le nombre de variables. Le mode de
    perturbation par défaut (`tree_path_dependent`) n'exige pas de jeu de
    données de référence séparé : il utilise la répartition des observations
    dans les feuilles, déjà connue du modèle entraîné.
    """
    return shap.TreeExplainer(modele)


def calculer_valeurs_shap(
    explainer: shap.TreeExplainer, matrice: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    """Les valeurs de Shapley et la valeur de base, pour chaque ligne de `matrice`.

    Retourne `(valeurs, base)` : `valeurs` a la forme (n_lignes, n_variables),
    `base` la forme (n_lignes,), conservée par ligne même si elle est
    identique pour toutes (moyenne de la cible sur l'échantillon
    d'arrière-plan) — l'appelant n'a pas à supposer cette invariance.
    `prédiction = base + somme(valeurs)` est l'axiome d'efficacité des
    valeurs de Shapley, vérifié par test à la précision flottante près.
    """
    explication = explainer(matrice)
    valeurs = np.asarray(explication.values, dtype="float64")
    base = np.asarray(explication.base_values, dtype="float64")
    if base.ndim == 0:
        base = np.full(len(matrice), float(base))
    return valeurs, base


def importance_globale(
    valeurs_shap: np.ndarray, poids: pd.Series, colonnes: list[str]
) -> list[ContributionVariable]:
    """Le classement des variables par contribution globale, décroissant.

    Moyenne des |SHAP| pondérée par l'effectif de la cellule
    (`modele.ponderation`), cohérent avec la MAE pondérée qui gouverne le
    reste de l'évaluation. Ce n'est **pas** une importance causale (docstring
    du module) : une moyenne de contributions à des prédictions.
    """
    if valeurs_shap.shape[1] != len(colonnes):
        raise ErreurExplicabilite(
            f"{valeurs_shap.shape[1]} colonnes de valeurs SHAP pour {len(colonnes)} noms de variable : "
            "les deux doivent correspondre terme à terme."
        )
    poids_array = poids.to_numpy(dtype="float64")
    poids_total = poids_array.sum()
    if poids_total <= 0:
        raise ErreurExplicabilite("Le poids total des cellules est nul : importance globale indéfinie.")
    moyenne_ponderee = (np.abs(valeurs_shap) * poids_array[:, None]).sum(axis=0) / poids_total
    total = moyenne_ponderee.sum()
    paires = [
        ContributionVariable(nom=nom, importance=float(valeur), part=float(valeur) / total if total > 0 else 0.0)
        for nom, valeur in zip(colonnes, moyenne_ponderee, strict=False)
    ]
    return sorted(paires, key=lambda contribution: contribution.importance, reverse=True)


def part_substituts_genre(importance: list[ContributionVariable]) -> dict[str, float]:
    """La part de l'explication globale portée par chaque substitut du genre encore dans le modèle.

    Signal transmis à l'audit d'équité, pas une conclusion : l'ADR 0011
    mesure la corrélation de ces variables avec le genre, pas leur poids dans
    le modèle — deux questions différentes, à ne pas confondre.
    """
    par_nom = {contribution.nom: contribution.part for contribution in importance}
    return {nom: par_nom.get(nom, 0.0) for nom in SUBSTITUTS_GENRE_DANS_LE_MODELE}


def tracer_importance_globale(
    importance: list[ContributionVariable], chemin: Path, top_n: int
) -> Path:
    """Diagramme en barres horizontales des `top_n` variables les plus contributives."""
    retenues = importance[:top_n]
    chemin.parent.mkdir(parents=True, exist_ok=True)

    figure, axe = plt.subplots(figsize=(8, max(4, 0.35 * len(retenues))))
    noms = [contribution.nom for contribution in reversed(retenues)]
    valeurs = [contribution.importance for contribution in reversed(retenues)]
    axe.barh(noms, valeurs, color="tab:blue")
    axe.set_xlabel("Moyenne des |valeurs de Shapley|, pondérée par l'effectif")
    axe.set_title(f"Explicabilité globale — TreeSHAP, {len(importance)} variables")
    figure.tight_layout()

    figure.savefig(chemin, dpi=150)
    plt.close(figure)
    return chemin


def _cles_cellule(table: pd.DataFrame) -> pd.DataFrame:
    """Les colonnes qui identifient une cellule sans ambiguïté, pour le précalcul et les exemples."""
    return table[["session", "cod_aff_form", "type_bac", "boursier"]]


def construire_table_precalcul(
    table: pd.DataFrame, colonnes: list[str], valeurs_shap: np.ndarray, base: np.ndarray, prediction: np.ndarray
) -> pd.DataFrame:
    """La table du précalcul par cellule : clés, prédiction, valeur de base, une colonne SHAP par variable.

    `float32` pour les colonnes SHAP et la prédiction : la précision de la
    valeur de Shapley n'a pas besoin du double, et le format divise par deux
    la taille du fichier (voir la mesure dans `RapportExplicabilite`).
    """
    precalcul = _cles_cellule(table).reset_index(drop=True)
    precalcul["prediction"] = prediction.astype("float32")
    precalcul["valeur_base"] = base.astype("float32")
    for indice, nom in enumerate(colonnes):
        precalcul[f"shap__{nom}"] = valeurs_shap[:, indice].astype("float32")
    return precalcul


def ecrire_precalcul(precalcul: pd.DataFrame, chemin: Path) -> Path:
    """Écrit le précalcul par cellule en Parquet, colonnaire — adapté à une lecture par variable."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    precalcul.to_parquet(chemin, index=False)
    return chemin


def _exemple_depuis_ligne(
    table: pd.DataFrame,
    indice: int,
    colonnes: list[str],
    valeurs_shap: np.ndarray,
    base: np.ndarray,
    prediction: np.ndarray,
    n_contributions: int = 8,
) -> ExempleLocal:
    """Construit l'exemple local commenté d'une ligne, ses `n_contributions` variables les plus fortes."""
    ligne = table.iloc[indice]
    contribs = valeurs_shap[indice]
    ordre = np.argsort(-np.abs(contribs))[:n_contributions]
    contributions = [(colonnes[j], ligne[colonnes[j]], float(contribs[j])) for j in ordre]
    return ExempleLocal(
        session=int(ligne["session"]),
        cod_aff_form=str(ligne["cod_aff_form"]),
        type_bac=str(ligne["type_bac"]),
        boursier=bool(ligne["boursier"]),
        effectif=float(ligne["effectif"]),
        taux_observe=float(ligne["taux"]),
        prediction=float(prediction[indice]),
        valeur_base=float(base[indice]),
        contributions=contributions,
    )


def choisir_exemples(
    table: pd.DataFrame,
    colonnes: list[str],
    valeurs_shap: np.ndarray,
    base: np.ndarray,
    prediction: np.ndarray,
    effectif_minimal: int,
) -> tuple[ExempleLocal, ExempleLocal]:
    """La cellule à la prédiction la plus haute et celle à la plus basse, parmi les cellules stables.

    Restreint aux cellules d'effectif >= `effectif_minimal`
    (`explicabilite.effectif_minimal_exemple`) : sous ce seuil, une seule
    proposition de plus ou de moins fait basculer le taux observé, et
    l'exemple illustrerait le bruit d'échantillonnage plutôt que le
    comportement du modèle.
    """
    effectifs = table["effectif"].to_numpy(dtype="float64")
    eligibles = np.where(effectifs >= effectif_minimal)[0]
    if eligibles.size == 0:
        raise ErreurExplicabilite(
            f"Aucune cellule d'effectif >= {effectif_minimal} : impossible de choisir un exemple stable."
        )
    predictions_eligibles = prediction[eligibles]
    indice_haut = int(eligibles[np.argmax(predictions_eligibles)])
    indice_bas = int(eligibles[np.argmin(predictions_eligibles)])
    exemple_haut = _exemple_depuis_ligne(table, indice_haut, colonnes, valeurs_shap, base, prediction)
    exemple_bas = _exemple_depuis_ligne(table, indice_bas, colonnes, valeurs_shap, base, prediction)
    return exemple_haut, exemple_bas


def _journaliser_mlflow(rapport: RapportExplicabilite, settings: Settings) -> None:
    """Enregistre l'explicabilité dans MLflow : importance globale, figure, précalcul en artefact.

    Même politique que les autres étapes du modèle : l'absence de
    `mlflow_tracking_uri` ou du paquet est journalisée, pas masquée.
    """
    if not settings.mlflow_tracking_uri:
        LOGGER.warning("MLFLOW_TRACKING_URI non configuré : explicabilité non journalisée dans MLflow.")
        return
    try:
        import mlflow
    except ImportError:
        LOGGER.warning("Le paquet mlflow n'est pas installé dans cet environnement : explicabilité non journalisée.")
        return

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(NOM_EXPERIENCE_MLFLOW)
    with mlflow.start_run(run_name="explicabilite-shap-e25"):
        mlflow.set_tag("etape", "explain")
        for rang, contribution in enumerate(rapport.importance_globale[:20], start=1):
            mlflow.log_metric(f"shap_importance_rang_{rang:02d}_{contribution.nom}", contribution.importance)
        for nom, part in rapport.part_substituts_genre.items():
            mlflow.log_metric(f"shap_part_substitut_{nom}", part)
        mlflow.log_metric("precalcul_n_cellules", rapport.n_cellules_precalculees)
        mlflow.log_metric("precalcul_duree_secondes", rapport.duree_precalcul_secondes)
        mlflow.log_metric("precalcul_taille_octets", rapport.taille_octets_precalcul)
        mlflow.log_artifact(str(rapport.chemin_figure))


def executer(
    settings: Settings | None = None,
    dossier_figures: Path | None = None,
    dossier_precalcul: Path | None = None,
) -> RapportExplicabilite:
    """Entraîne, explique par TreeSHAP et précalcule par cellule.

    `dossier_figures` / `dossier_precalcul` : `reports/figures/` et
    `data/processed/explicabilite/` du dépôt par défaut ; paramétrables pour
    que les tests écrivent dans un répertoire jetable (même convention que
    `models.evaluate.executer` et `models.courbe_apprentissage.executer`).
    """
    settings = settings or get_settings()
    dossier_figures = dossier_figures or DOSSIER_FIGURES_DEFAUT
    dossier_precalcul = dossier_precalcul or (settings.processed_dir / SOUS_DOSSIER_PRECALCUL)

    resultat = train.entrainer_et_evaluer(settings)
    matrice_complete = preparer_matrice(resultat.table, resultat.colonnes)
    poids_complet = resultat.table["effectif"].astype("float64")

    explainer = construire_explainer(resultat.modele)

    debut = time.monotonic()
    valeurs_shap, base = calculer_valeurs_shap(explainer, matrice_complete)
    duree = time.monotonic() - debut
    prediction = base + valeurs_shap.sum(axis=1)

    importance = importance_globale(valeurs_shap, poids_complet, resultat.colonnes)
    part_substituts = part_substituts_genre(importance)
    chemin_figure = tracer_importance_globale(
        importance, dossier_figures / NOM_FIGURE_IMPORTANCE, settings.explicabilite.top_n_figure
    )

    exemple_haut, exemple_bas = choisir_exemples(
        resultat.table,
        resultat.colonnes,
        valeurs_shap,
        base,
        prediction,
        settings.explicabilite.effectif_minimal_exemple,
    )

    precalcul = construire_table_precalcul(resultat.table, resultat.colonnes, valeurs_shap, base, prediction)
    chemin_precalcul = ecrire_precalcul(precalcul, dossier_precalcul / NOM_FICHIER_PRECALCUL)
    taille_octets = chemin_precalcul.stat().st_size

    rapport = RapportExplicabilite(
        importance_globale=importance,
        part_substituts_genre=part_substituts,
        chemin_figure=chemin_figure,
        exemple_haut=exemple_haut,
        exemple_bas=exemple_bas,
        n_cellules_precalculees=len(precalcul),
        duree_precalcul_secondes=duree,
        taille_octets_precalcul=taille_octets,
        chemin_precalcul=chemin_precalcul,
    )

    _journaliser_mlflow(rapport, settings)
    return rapport


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rapport = executer()
    LOGGER.info("Explicabilité terminée.\n%s", rapport.resume())
    return 0


if __name__ == "__main__":
    sys.exit(main())
