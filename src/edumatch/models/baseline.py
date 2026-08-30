"""La baseline (E21) : le taux de la même cellule à la session précédente.

## Pourquoi cette étape, et pourquoi elle compte

Un score de modèle n'a de sens que rapporté à un plancher. Ce module mesure
ce plancher — il n'entraîne rien, il applique une règle fixe et la note.
`configs/base.yaml`, section `evaluation.baseline`, la nomme
`taux_session_precedente` : pour une cellule `(formation, type de
baccalauréat, boursier)` à la session N, la prédiction est le taux observé
de cette même cellule à la session N-1.

Deux limites structurelles, mesurées ici plutôt que supposées :

1. **Cellules sans antécédent** — une formation absente de la session N-1
   (nouvelle, ou dont le code a changé) n'a simplement rien à prédire. Ce
   module ne comble jamais ce trou par une valeur inventée : il mesure le
   score **avec et sans** ces cellules, et fournit un repli assumé et
   documenté pour produire une couverture totale, comparable à un modèle qui
   prédit toujours quelque chose.
2. **La toute première session de la fenêtre labellisée** — pour cette
   session, aucune session antérieure ne porte de label (ADR 0012 : le
   numérateur ventilé par type de baccalauréat n'existe qu'à partir de la
   session où la fenêtre commence). Aucune baseline temporelle, aussi
   triviale soit-elle, ne peut y prédire quoi que ce soit sans regarder en
   avant. Ce n'est pas une faute du code : c'est une propriété du protocole
   temporel lui-même, et elle est déclarée telle quelle plutôt que masquée.

## Les trois règles mesurées

- `session_precedente` — la baseline retenue par `configs/base.yaml`.
- `moyenne_groupe_expansive` — la moyenne pondérée du taux, par
  `(type_bac, boursier)`, sur **toutes les sessions strictement antérieures**
  à la session prédite (fenêtre expansive : jamais la session cible, jamais
  une session future). Sert de repli à la première, et de second plancher
  plus naïf en elle-même.
- `moyenne_globale_expansive` — la même moyenne, sans distinction de groupe :
  le plancher le plus trivial des trois.

Les deux dernières ne violent jamais le protocole temporel : une moyenne
calculée sur les sessions < N est disponible avant que la session N ne se
joue, exactement comme la règle qu'elle sert de repli.

## Ce que ce module ne fait pas

Il ne choisit pas la baseline officielle pour E23 à la place du lecteur : il
mesure les quatre variantes (`session_precedente`, sa version à couverture
complète, et les deux moyennes), sur chaque session et sur les périmètres
agrégés utiles (les six sessions labellisées, et le périmètre
validation + test du protocole arrêté par l'ADR 0012), et les restitue
telles quelles.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from edumatch.config import Settings, get_settings
from edumatch.features.build import NOM_FICHIER_VARIABLES, SOUS_DOSSIER
from edumatch.features.label import calculer_taux

LOGGER = logging.getLogger(__name__)

# Les six combinaisons (type de baccalauréat, statut de boursier) que porte
# le fichier source, cf. `transform.etoile.CATEGORIES` — redéfini ici plutôt
# qu'importé : `etoile` construit le gold, ce module le consomme, et les deux
# n'ont pas besoin de dépendre l'un de l'autre pour cette seule constante.
CATEGORIES: tuple[str, ...] = ("bg", "bg_brs", "bt", "bt_brs", "bp", "bp_brs")
COLONNES_GROUPE: tuple[str, ...] = ("type_bac", "boursier")

VARIANTE_PRECEDENTE = "session_precedente"
VARIANTE_PRECEDENTE_AVEC_REPLI = "session_precedente_avec_repli"
VARIANTE_MOYENNE_GROUPE = "moyenne_groupe_expansive"
VARIANTE_MOYENNE_GLOBALE = "moyenne_globale_expansive"


class ErreurBaseline(RuntimeError):
    """La table de variables ne porte pas les colonnes que la baseline exige.

    Définitive : `make features` (E20) doit avoir produit une table conforme
    au classement de `modele.variables` avant que ce module ne puisse
    s'exécuter.
    """


def _categorie(type_bac: pd.Series, boursier: pd.Series) -> pd.Series:
    """`("bg", True)` -> `"bg_brs"` ; `("bt", False)` -> `"bt"`.

    Inverse de `etoile._categorie_vers_profil`.
    """
    return type_bac.astype(str) + boursier.map({True: "_brs", False: ""}).astype(str)


def predire_session_precedente(table: pd.DataFrame) -> pd.Series:
    """La baseline retenue : le taux de la même cellule à la session N-1.

    Réutilise `features.label.calculer_taux` — même bornage, même traitement
    des cas limites (0/0 indéterminé, dénominateur nul borné à 1) que le
    label lui-même, pour que la baseline et la cible qu'elle prédit soient
    définies de façon rigoureusement identique. Le numérateur et le
    dénominateur viennent des colonnes `decalees` (ADR 0013 §2) —
    `prop_tot_{categorie}` et `nb_voe_pp_{categorie}` — déjà lues sur la
    session N-1 par `features.build`, jamais recalculées ici.

    Absente (`<NA>`) quand la formation n'a pas de ligne silver en N-1, ou
    quand la session prédite est la première de la fenêtre labellisée
    (ADR 0012) : dans les deux cas, `prop_tot_{categorie}` est manquant, et
    l'absence se propage sans être comblée.
    """
    categorie = _categorie(table["type_bac"], table["boursier"])
    prediction = pd.Series(np.nan, index=table.index, dtype="float64")
    for cat in CATEGORIES:
        masque = categorie == cat
        if not masque.any():
            continue
        colonne_numerateur, colonne_denominateur = f"prop_tot_{cat}", f"nb_voe_pp_{cat}"
        if colonne_numerateur not in table.columns or colonne_denominateur not in table.columns:
            raise ErreurBaseline(
                f"Colonne(s) {colonne_numerateur!r} / {colonne_denominateur!r} absente(s) de "
                "la table de variables : `make features` (E20) doit produire les colonnes "
                "décalées de `modele.variables.decalees` (ADR 0013)."
            )
        numerateur = table.loc[masque, colonne_numerateur]
        denominateur = table.loc[masque, colonne_denominateur]
        taux, _ = calculer_taux(numerateur, denominateur)
        prediction.loc[masque] = taux.astype("float64")
    return prediction


def _moyennes_ponderees_par_groupe(passe: pd.DataFrame, groupes: tuple[str, ...]) -> pd.Series:
    """Moyenne du taux pondérée par l'effectif sur `passe`, groupée par `groupes`.

    `groupes` vide : moyenne globale, sans distinction.
    """
    poids = passe["effectif"].astype("float64")
    pondere = passe["taux"].astype("float64") * poids
    if not groupes:
        total_poids = poids.sum()
        valeur = pondere.sum() / total_poids if total_poids > 0 else np.nan
        return pd.Series([valeur], index=[None])
    agrege = pd.DataFrame({"pondere": pondere, "poids": poids, **{g: passe[g] for g in groupes}})
    somme = agrege.groupby(list(groupes))[["pondere", "poids"]].sum()
    return somme["pondere"] / somme["poids"].replace(0.0, np.nan)


def predire_moyenne_expansive(table: pd.DataFrame, groupes: tuple[str, ...]) -> pd.Series:
    """Moyenne pondérée du taux sur toutes les sessions strictement antérieures à la cible.

    Fenêtre expansive plutôt que fixe (train 2020-2023 uniquement) : la
    règle reste valide quelle que soit la session prédite, sans jamais
    regarder une session égale ou postérieure à celle-ci — c'est la même
    exigence anti-fuite que celle qui gouverne le split (ADR 0012), appliquée
    à un plancher qui n'a besoin d'aucun ajustement pour rester honnête.

    Absente pour la toute première session présente dans `table` : aucune
    session antérieure ne porte de label, il n'existe alors aucune moyenne
    passée à calculer (voir le docstring du module).
    """
    prediction = pd.Series(np.nan, index=table.index, dtype="float64")
    for session in sorted(table["session"].unique()):
        passe = table[table["session"] < session]
        if passe.empty:
            continue
        cible = table["session"] == session
        moyennes = _moyennes_ponderees_par_groupe(passe, groupes)
        if not groupes:
            prediction.loc[cible] = moyennes.iloc[0]
        else:
            cles = table.loc[cible, list(groupes)]
            index_cles = cles[groupes[0]] if len(groupes) == 1 else pd.MultiIndex.from_frame(cles)
            valeurs = index_cles.map(moyennes)
            prediction.loc[cible] = valeurs.to_numpy(dtype="float64", na_value=np.nan)
    return prediction


@dataclass(frozen=True)
class ScoreBaseline:
    """Le score d'une variante de baseline sur un périmètre de sessions donné, tel que mesuré."""

    variante: str
    perimetre: str
    n_cellules: int
    couverture: float
    mae_ponderee: float | None
    mae_non_ponderee: float | None

    def resume(self) -> str:
        if self.mae_ponderee is None:
            return f"{self.variante:32s} {self.perimetre:16s} aucune cellule prédite"
        return (
            f"{self.variante:32s} {self.perimetre:16s} "
            f"couverture={self.couverture:6.1%}  "
            f"mae_ponderee={self.mae_ponderee:.4f}  mae_non_ponderee={self.mae_non_ponderee:.4f}"
        )


@dataclass(frozen=True)
class RapportBaseline:
    """L'ensemble des scores mesurés, à déclarer tels quels (E21)."""

    scores: list[ScoreBaseline]

    def score(self, variante: str, perimetre: str) -> ScoreBaseline:
        for score in self.scores:
            if score.variante == variante and score.perimetre == perimetre:
                return score
        raise KeyError(f"Aucun score pour variante={variante!r}, perimetre={perimetre!r}.")

    def resume(self) -> str:
        return "\n".join(score.resume() for score in self.scores)


def _score_sur_sous_ensemble(
    sous_table: pd.DataFrame, prediction: pd.Series, variante: str, perimetre: str
) -> ScoreBaseline:
    observe = sous_table["taux"].astype("float64")
    poids = sous_table["effectif"].astype("float64")
    masque = prediction.notna()
    couverture = float(masque.mean()) if len(sous_table) else 0.0
    if not masque.any():
        return ScoreBaseline(variante, perimetre, len(sous_table), couverture, None, None)
    ecarts = (observe[masque] - prediction[masque]).abs()
    poids_valide = poids[masque]
    mae_ponderee = float((ecarts * poids_valide).sum() / poids_valide.sum())
    mae_non_ponderee = float(ecarts.mean())
    return ScoreBaseline(
        variante, perimetre, len(sous_table), couverture, mae_ponderee, mae_non_ponderee
    )


def _perimetres(table: pd.DataFrame, settings: Settings) -> dict[str, pd.Series]:
    """Les masques de sessions sur lesquels chaque variante est notée.

    Une entrée par session isolée (pour voir l'évolution d'une année sur
    l'autre), plus deux agrégats : toutes les sessions sauf la première de la
    fenêtre labellisée (structurellement sans plancher possible, voir le
    docstring du module), et le périmètre validation + test du protocole
    arrêté par l'ADR 0012 — celui qui compte pour la comparaison à E22/E23.
    """
    sessions = sorted(table["session"].unique())
    perimetres = {str(session): table["session"] == session for session in sessions}
    if len(sessions) > 1:
        perimetres[f"{sessions[1]}-{sessions[-1]}"] = table["session"] >= sessions[1]
    sessions_officielles = set(settings.modele.split.validation) | set(settings.modele.split.test)
    perimetres["validation+test"] = table["session"].isin(sessions_officielles)
    return perimetres


def evaluer(table: pd.DataFrame, settings: Settings) -> RapportBaseline:
    """Mesure les quatre variantes de baseline sur chaque périmètre de sessions. N'entraîne rien."""
    precedente = predire_session_precedente(table)
    moyenne_groupe = predire_moyenne_expansive(table, COLONNES_GROUPE)
    moyenne_globale = predire_moyenne_expansive(table, ())
    predictions = {
        VARIANTE_PRECEDENTE: precedente,
        VARIANTE_PRECEDENTE_AVEC_REPLI: precedente.fillna(moyenne_groupe),
        VARIANTE_MOYENNE_GROUPE: moyenne_groupe,
        VARIANTE_MOYENNE_GLOBALE: moyenne_globale,
    }
    perimetres = _perimetres(table, settings)
    scores = [
        _score_sur_sous_ensemble(table.loc[masque], prediction.loc[masque], variante, perimetre)
        for variante, prediction in predictions.items()
        for perimetre, masque in perimetres.items()
    ]
    return RapportBaseline(scores=scores)


def _chemin_variables(settings: Settings) -> Path:
    return settings.processed_dir / SOUS_DOSSIER / NOM_FICHIER_VARIABLES


def executer(settings: Settings | None = None) -> RapportBaseline:
    """Charge la table de variables (E20) et mesure la baseline. Retourne le rapport complet."""
    settings = settings or get_settings()
    chemin = _chemin_variables(settings)
    if not chemin.exists():
        raise ErreurBaseline(
            f"{chemin} est introuvable : exécuter `make features` (E20) avant `make baseline`."
        )

    colonnes_requises = {"session", "type_bac", "boursier", "taux", "effectif"}
    table = pq.read_table(chemin).to_pandas()
    manquantes = colonnes_requises - set(table.columns)
    if manquantes:
        raise ErreurBaseline(
            f"Colonne(s) {sorted(manquantes)} absente(s) de {chemin} : "
            "table de variables non conforme."
        )

    return evaluer(table, settings)


def _journaliser_mlflow(rapport: RapportBaseline, settings: Settings) -> None:
    """Enregistre le périmètre `validation+test` dans MLflow, si le suivi est configuré.

    Le suivi d'expériences doit commencer à la première expérience, pas
    après (principe 4 de `structure-projet.md`) — cette baseline en est une,
    même sans paramètre à ajuster. L'absence de `mlflow_tracking_uri` ou du
    paquet lui-même n'est pas masquée : elle est journalisée et le calcul du
    score, qui ne dépend pas de MLflow, se poursuit sans lui.
    """
    if not settings.mlflow_tracking_uri:
        LOGGER.warning(
            "MLFLOW_TRACKING_URI non configuré : baseline non journalisée dans MLflow (E21)."
        )
        return
    try:
        import mlflow
    except ImportError:
        LOGGER.warning(
            "Le paquet mlflow n'est pas installé dans cet environnement : baseline non journalisée."
        )
        return

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment("edumatch-accessibilite")
    with mlflow.start_run(run_name="baseline-session-precedente"):
        mlflow.set_tag("etape", "E21")
        variantes_a_journaliser = (
            VARIANTE_PRECEDENTE_AVEC_REPLI,
            VARIANTE_MOYENNE_GROUPE,
            VARIANTE_MOYENNE_GLOBALE,
        )
        for variante in variantes_a_journaliser:
            score = rapport.score(variante, "validation+test")
            if score.mae_ponderee is not None:
                mlflow.log_metric(f"{variante}_mae_ponderee", score.mae_ponderee)
                mlflow.log_metric(f"{variante}_mae_non_ponderee", score.mae_non_ponderee)
                mlflow.log_metric(f"{variante}_couverture", score.couverture)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    rapport = executer(settings)
    LOGGER.info("Baseline (E21) mesurée.\n%s", rapport.resume())
    _journaliser_mlflow(rapport, settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
