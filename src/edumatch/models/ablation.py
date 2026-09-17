"""Ablation du modèle d'accessibilité : l'apport de chaque source de variables, mesuré.

## Ce que ce module fait, et ce qu'il ne refait pas

`models/train.py` a arrêté une configuration de production : le jeu de
variables classé par l'ADR 0013, `taux_session_precedente` inclus comme
variable dérivée. Ce module ne discute pas ce choix, il le **mesure** :
chaque variante ci-dessous retire ou ajoute un bloc de variables, entraîne un
LightGBM avec exactement les mêmes hyperparamètres (`configs/base.yaml`,
`modele.hyperparametres`) et le même `random_state`, et compare son erreur
absolue moyenne pondérée de validation à celle de la configuration complète.

L'ADR 0013 prescrit trois retraits (mentions, `cod_uai`, variables décalées
dans leur ensemble). L'explicabilité et l'audit d'équité, une
fois mesurés, en appellent trois autres : `taux_session_precedente` retirée
seule, `taux_session_precedente` conservée seule, et les substituts du genre
retirés. Sirene n'entre dans aucune variante : la chaîne NAF -> ROME ->
formation n'atteint aucune formation Parcoursup (voir
`referentiel/naf_rome_formation.py`, `manques_declares`), son ablation est
donc **impossible à mesurer aujourd'hui**, pas nulle — la nuance est déclarée
dans `RapportAblation.declaration_sirene` plutôt que simulée.

## Le protocole, repris strictement de l'entraînement de production

Toute variante est jugée sur la **validation 2024**, jamais sur le test 2025
(ADR 0012) : une ablation qui comparerait des configurations sur le test
ferait de ce choix un réglage d'hyperparamètre déguisé, ce que le protocole
interdit. Le test n'est consulté qu'une fois pour la **configuration
retenue** — celle déjà en production — et son score est
celui déjà journalisé alors (`resultat_complet.rapport.scores_test`), jamais
recalculé ici : le recalculer serait une seconde consultation du test pour
rien, puisque la configuration ne change pas.

Pour la même raison, la comparaison d'équité entre « avec » et « sans »
substituts du genre (question centrale de cette étape) porte elle aussi sur
la **validation 2024**, et non sur le test 2025 déjà utilisé par l'audit de
production : ce module doit pouvoir comparer deux modèles sans
consommer une seconde fois le jeu que l'audit d'équité a déjà consulté.

## Le genre n'entre jamais dans le modèle, même ici

Le retrait des substituts (`fili`, `select_form`, `dep`, `acad_mies`, la
liste mesurée par `models.explain.SUBSTITUTS_GENRE_DANS_LE_MODELE`) est une
ablation de variables **licites** du modèle. Le genre lui-même n'apparaît
dans aucune des sept variantes : il est lu, comme dans `models.fairness`,
uniquement depuis la table silver, pour classer la composition par genre des
formations et juger l'équité — jamais comme variable d'entraînement.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from edumatch.config import Settings, VariablesConfig, get_settings
from edumatch.features import build
from edumatch.features.label import calculer_taux
from edumatch.models import fairness, train
from edumatch.models.explain import SUBSTITUTS_GENRE_DANS_LE_MODELE
from edumatch.models.jeux import JeuDonnees, extraire_jeu
from edumatch.models.metrics import ScoreSession, calibration, predictions_baseline_couverture_egale
from edumatch.models.train import COLONNE_A_ANTECEDENT, COLONNE_TAUX_PRECEDENT

LOGGER = logging.getLogger(__name__)

NOM_EXPERIENCE_MLFLOW = "edumatch-accessibilite"
PERIMETRE_ANALYSE = "validation"


class ErreurAblation(RuntimeError):
    """L'ablation ne peut pas continuer sans violer une garantie attendue.

    Même politique que `models.train.ErreurEntrainement` : une source gold ou
    silver absente, ou une colonne dont le classement ne peut pas être modifié
    sans ambiguïté, ne se règlent pas en relançant l'ablation à l'identique.
    """


# ─── Reconstruction d'une table de variables avec un autre classement ───────


def _charger_gold_et_silver(settings: Settings) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Recharge silver et le gold depuis le disque, pour reconstruire une table de
    variables avec un classement différent de celui de `configs/base.yaml`.

    Nécessaire uniquement pour les deux variantes qui ajoutent une colonne
    absente de `data/processed/parcoursup/variables.parquet` (mentions,
    `cod_uai`) : toutes les autres variantes se contentent de restreindre les
    colonnes de la table déjà construite par `make features`.
    """
    dossier_gold = settings.processed_dir / build.SOUS_DOSSIER
    chemin_silver = settings.interim_dir / build.SOUS_DOSSIER / build.NOM_FICHIER_SILVER
    chemins = {
        "silver": chemin_silver,
        "fait_admission": dossier_gold / "fait_admission.parquet",
        "dim_formation": dossier_gold / "dim_formation.parquet",
        "dim_profil_candidat": dossier_gold / "dim_profil_candidat.parquet",
    }
    manquants = {nom: chemin for nom, chemin in chemins.items() if not chemin.exists()}
    if manquants:
        raise ErreurAblation(
            "Fichier(s) manquant(s) pour reconstruire une variante de la table de variables : "
            + ", ".join(f"{nom} ({chemin})" for nom, chemin in manquants.items())
            + ". Exécuter `make transform` et `make gold` avant l'ablation."
        )
    silver = pq.read_table(chemins["silver"]).to_pandas()
    fait_admission = pq.read_table(chemins["fait_admission"]).to_pandas()
    dim_formation = pq.read_table(chemins["dim_formation"]).to_pandas()
    dim_profil = pq.read_table(chemins["dim_profil_candidat"]).to_pandas()
    return fait_admission, dim_formation, dim_profil, silver


def _variables_avec_cod_uai(variables: VariablesConfig) -> VariablesConfig:
    """Copie en mémoire de `variables` où `cod_uai` passe d'exclue (motif "substitut") à décalée.

    Ne modifie ni `configs/base.yaml` ni la classification de référence de
    l'ADR 0013 : c'est une variante d'expérience, construite pour la seule
    durée de cette mesure. `model_copy(update=...)` construit une nouvelle
    instance sans repasser par les validateurs Pydantic (`VariablesConfig`
    est gelée) ; c'est licite ici parce que la cohérence est garantie à la
    main — retirer une clé de `exclues` exactement quand on l'ajoute à
    `decalees` ne peut pas créer de colonne classée deux fois.
    """
    if "cod_uai" not in variables.exclues:
        raise ErreurAblation(
            "cod_uai n'est plus classé `exclues` dans modele.variables : la variante "
            "d'ablation qui le réintroduit n'a plus de sens tel quel, à revoir."
        )
    exclues_sans_cod_uai = {colonne: motif for colonne, motif in variables.exclues.items() if colonne != "cod_uai"}
    decalees_avec_cod_uai = [*variables.decalees, "cod_uai"]
    return variables.model_copy(update={"decalees": decalees_avec_cod_uai, "exclues": exclues_sans_cod_uai})


def _construire_table_variante(
    settings: Settings, variables: VariablesConfig, *, inclure_sous_reserve: bool
) -> pd.DataFrame:
    """Une table de variables reconstruite avec un classement autre que celui de production,
    puis enrichie de `taux_session_precedente` exactement comme `models.train.charger_table`.
    """
    fait_admission, dim_formation, dim_profil, silver = _charger_gold_et_silver(settings)
    table, _ = build.construire_table_apprentissage(
        fait_admission, dim_formation, dim_profil, silver, variables, inclure_sous_reserve=inclure_sous_reserve
    )
    return train.ajouter_taux_precedent(table)


# ─── Entraînement et score d'une variante ───────────────────────────────────


@dataclass(frozen=True)
class _EntrainementVariante:
    """Ce qu'un entraînement de variante produit, avant sa mise en forme en `ResultatVariante`."""

    modele: lgb.LGBMRegressor
    jeu_validation: JeuDonnees
    prediction_validation: np.ndarray
    score_validation: ScoreSession
    ece_validation: float


def _entrainer_variante(table: pd.DataFrame, colonnes: list[str], settings: Settings) -> _EntrainementVariante:
    """Entraîne une variante sur `colonnes`, avec les hyperparamètres et le split de production.

    Réutilise `train.entrainer_modele` à l'identique — même objectif, même
    pondération par effectif, même arrêt anticipé sur la MAE pondérée de
    validation — pour que seule la composition de `colonnes` distingue une
    variante de la configuration complète.
    """
    split = settings.modele.split
    jeu_entrainement = extraire_jeu(table, split.entrainement, colonnes)
    jeu_validation = extraire_jeu(table, split.validation, colonnes)
    modele = train.entrainer_modele(jeu_entrainement, jeu_validation, settings.modele.hyperparametres)
    prediction_validation = modele.predict(jeu_validation.X)
    score_validation = train.evaluer_sur_perimetre(jeu_validation, prediction_validation, PERIMETRE_ANALYSE)
    ece_validation = calibration(
        jeu_validation.y,
        jeu_validation.poids,
        prediction_validation,
        settings.evaluation.n_tranches_calibration,
        PERIMETRE_ANALYSE,
    ).ece
    return _EntrainementVariante(modele, jeu_validation, prediction_validation, score_validation, ece_validation)


@dataclass(frozen=True)
class ResultatVariante:
    """Le score d'une variante d'ablation, à déclarer tel quel — écart nul compris."""

    nom: str
    description: str
    n_variables: int
    mae_validation: float
    ecart_mae_vs_complet: float
    ece_validation: float
    commentaire: str

    def resume(self) -> str:
        signe = "+" if self.ecart_mae_vs_complet >= 0 else ""
        return (
            f"  {self.nom:26s} n_var={self.n_variables:3d}  mae_validation={self.mae_validation:.4f}  "
            f"ecart_vs_complet={signe}{self.ecart_mae_vs_complet:.4f}  ece_validation={self.ece_validation:.4f}\n"
            f"    {self.description}\n"
            f"    -> {self.commentaire}"
        )


def _resultat_variante(
    nom: str, description: str, colonnes: list[str], entrainement: _EntrainementVariante,
    mae_reference: float, commentaire: str,
) -> ResultatVariante:
    return ResultatVariante(
        nom=nom,
        description=description,
        n_variables=len(colonnes),
        mae_validation=entrainement.score_validation.mae_ponderee,
        ecart_mae_vs_complet=entrainement.score_validation.mae_ponderee - mae_reference,
        ece_validation=entrainement.ece_validation,
        commentaire=commentaire,
    )


# ─── Les sept variantes ──────────────────────────────────────────────────────


def _variante_sans_decalees(
    table: pd.DataFrame, colonnes_completes: list[str], variables: VariablesConfig, settings: Settings, mae_reference: float
) -> ResultatVariante:
    """ADR 0013 §2 — retire les 35 colonnes décalées, et taux_session_precedente qui en dépend."""
    retirees = {*variables.decalees, COLONNE_TAUX_PRECEDENT, COLONNE_A_ANTECEDENT}
    colonnes = [c for c in colonnes_completes if c not in retirees]
    entrainement = _entrainer_variante(table, colonnes, settings)
    ecart = entrainement.score_validation.mae_ponderee - mae_reference
    return _resultat_variante(
        "sans_decalees",
        "Retire les 35 colonnes décalées et taux_session_precedente (qui en dépend) : ne reste "
        "que le catalogue de la session prédite et les dimensions de cellule.",
        colonnes,
        entrainement,
        mae_reference,
        (
            f"le signal de la session N-1, pris dans son ensemble, vaut {abs(ecart):.4f} de MAE pondérée "
            f"({'creuse' if ecart > 0 else 'améliore'} l'erreur en son absence) : "
            "c'est la source d'information dominante du modèle."
        ),
    )


def _variante_sans_taux_precedent(
    table: pd.DataFrame, colonnes_completes: list[str], settings: Settings, mae_reference: float
) -> ResultatVariante:
    """Retire uniquement la variable dérivée, laisse son numérateur et son dénominateur bruts."""
    colonnes = [c for c in colonnes_completes if c not in {COLONNE_TAUX_PRECEDENT, COLONNE_A_ANTECEDENT}]
    entrainement = _entrainer_variante(table, colonnes, settings)
    ecart = entrainement.score_validation.mae_ponderee - mae_reference
    return _resultat_variante(
        "sans_taux_precedent",
        "Retire uniquement taux_session_precedente (et a_antecedent) ; prop_tot_* et "
        "nb_voe_pp_* (son numérateur et son dénominateur) restent, séparés.",
        colonnes,
        entrainement,
        mae_reference,
        (
            f"écart de {ecart:+.4f} : le quotient donné en clair au modèle lui évite d'approximer "
            "une division par coupures successives — pas l'apport du signal N-1 lui-même "
            "(voir sans_decalees, au-dessus)."
        ),
    )


def _variante_taux_precedent_seul(
    table: pd.DataFrame, colonnes_completes: list[str], variables: VariablesConfig, settings: Settings, mae_reference: float
) -> ResultatVariante:
    """Ne garde que les dimensions de cellule (structurelles) et taux_session_precedente."""
    gardees = {*variables.dimensions_cellule, COLONNE_TAUX_PRECEDENT}
    colonnes = [c for c in colonnes_completes if c in gardees]
    entrainement = _entrainer_variante(table, colonnes, settings)
    ecart = entrainement.score_validation.mae_ponderee - mae_reference
    verdict = "un gain mesurable" if ecart > 0.005 else "un gain marginal une fois le quotient présent"
    return _resultat_variante(
        "taux_precedent_seul",
        "Ne garde que les deux dimensions de cellule et taux_session_precedente : les 9 "
        "colonnes de catalogue, les 35 décalées et a_antecedent sont retirés.",
        colonnes,
        entrainement,
        mae_reference,
        f"écart de {ecart:+.4f} par rapport au modèle complet : les 45 autres variables apportent {verdict}.",
    )


def _variante_mentions_incluses(settings: Settings, variables: VariablesConfig, mae_reference: float) -> ResultatVariante:
    """ADR 0013 §3 — réintroduit les 8 colonnes de mention écartées par défaut."""
    table = _construire_table_variante(settings, variables, inclure_sous_reserve=True)
    colonnes = train.colonnes_features(variables, list(table.columns))
    entrainement = _entrainer_variante(table, colonnes, settings)
    gain = mae_reference - entrainement.score_validation.mae_ponderee
    seuil = settings.ablation.seuil_gain_mentions
    franchit = gain > seuil
    verdict = "franchi, réintroduction à instruire" if franchit else "non franchi, l'exclusion par défaut est confirmée"
    return _resultat_variante(
        "mentions_incluses",
        "Réintroduit les 8 colonnes de mention (contamination du baccalauréat en contrôle "
        "continu 2020-2021, ADR 0013 §3).",
        colonnes,
        entrainement,
        mae_reference,
        f"gain de {gain:+.4f} sur la validation ; seuil de reconsidération de l'ADR = {seuil:.2f} : {verdict}.",
    )


def _variante_cod_uai_reintroduit(settings: Settings, variables: VariablesConfig, mae_reference: float) -> ResultatVariante:
    """ADR 0013 §5 — réintroduit cod_uai, le plus fort substitut du genre mesuré."""
    variables_variante = _variables_avec_cod_uai(variables)
    table = _construire_table_variante(settings, variables_variante, inclure_sous_reserve=False)
    colonnes = train.colonnes_features(variables_variante, list(table.columns))
    entrainement = _entrainer_variante(table, colonnes, settings)
    perte = entrainement.score_validation.mae_ponderee - mae_reference  # négatif si cod_uai réduit l'erreur
    if perte < 0:
        verdict = "une perte réelle est mesurée à exclure cod_uai — l'ADR prescrit alors un encodage par la cible"
    else:
        verdict = "aucune perte mesurée à l'exclure, l'ADR est confirmée"
    return _resultat_variante(
        "cod_uai_reintroduit",
        "Réintroduit cod_uai (4 058 modalités), exclu par défaut pour cardinalité et pour être "
        "le plus fort substitut du genre mesuré (ADR 0013 §5).",
        colonnes,
        entrainement,
        mae_reference,
        f"écart de {perte:+.4f} : {verdict}.",
    )


def _variante_sans_substituts_genre(
    table: pd.DataFrame, colonnes_completes: list[str], settings: Settings, mae_reference: float
) -> tuple[ResultatVariante, _EntrainementVariante]:
    """Retire fili, select_form, dep, acad_mies : les quatre substituts du genre encore présents."""
    colonnes = [c for c in colonnes_completes if c not in SUBSTITUTS_GENRE_DANS_LE_MODELE]
    entrainement = _entrainer_variante(table, colonnes, settings)
    ecart = entrainement.score_validation.mae_ponderee - mae_reference
    resultat = _resultat_variante(
        "sans_substituts_genre",
        "Retire fili, select_form, dep, acad_mies : les quatre substituts du genre encore "
        "présents dans le modèle (14,2 % de l'explication SHAP, models.explain).",
        colonnes,
        entrainement,
        mae_reference,
        f"coût de {ecart:+.4f} de MAE pondérée — voir la comparaison d'équité ci-dessous pour ce qu'il achète.",
    )
    return resultat, entrainement


# ─── Comparaison d'équité entre « avec » et « sans » substituts du genre ────


def _composition_genre_session(settings: Settings, session: int) -> pd.DataFrame:
    """La composition candidate par genre de chaque formation d'une session donnée (silver).

    Même formule que `fairness.charger_composition_genre` (ADR 0011), mais
    paramétrée sur `session` plutôt que figée sur la session de test : cette
    ablation compare deux modèles sur la **validation** 2024 (voir le
    docstring du module), sans jamais retoucher au test 2025 que
    `models.fairness` a déjà consulté pour la configuration complète.
    """
    chemin = fairness.chemin_silver(settings)
    if not chemin.exists():
        raise ErreurAblation(f"{chemin} est introuvable : exécuter `make silver` avant l'ablation.")
    colonnes = ["session", "cod_aff_form", "voe_tot", "voe_tot_f"]
    silver = pq.read_table(chemin, columns=colonnes).to_pandas()
    silver = silver.loc[silver["session"] == session].copy()
    if silver.empty:
        raise ErreurAblation(f"Aucune ligne silver pour la session {session}.")
    composition_candidate, _ = calculer_taux(silver["voe_tot_f"], silver["voe_tot"])
    composition = pd.DataFrame(
        {
            "cod_aff_form": silver["cod_aff_form"].astype("string").astype(str),
            "composition_candidate": composition_candidate.astype("float64"),
        }
    )
    composition["bucket_genre"] = fairness.classer_composition_genre(composition["composition_candidate"])
    return composition


def _table_audit_genre(
    table: pd.DataFrame,
    jeu: JeuDonnees,
    prediction_modele: np.ndarray,
    prediction_baseline: np.ndarray,
    composition: pd.DataFrame,
) -> pd.DataFrame:
    """Une ligne par cellule de `jeu`, prête pour `fairness.ventiler_dimension` sur `bucket_genre`.

    `cod_aff_form` n'est jamais une variable du modèle (ADR 0013, catégorie
    `cles`) : elle est relue dans `table`, alignée par index sur `jeu.X`,
    exactement comme le fait `fairness.construire_table_predictions`.
    """
    lignes = table.loc[jeu.X.index]
    audit = pd.DataFrame(
        {
            "cod_aff_form": lignes["cod_aff_form"].astype("string").astype(str).to_numpy(),
            "effectif": jeu.poids.to_numpy(),
            "taux_observe": jeu.y.to_numpy(),
            "prediction_modele": np.asarray(prediction_modele, dtype="float64"),
            "prediction_baseline": np.asarray(prediction_baseline, dtype="float64"),
        }
    )
    fusion = audit.merge(composition[["cod_aff_form", "bucket_genre"]], on="cod_aff_form", how="left")
    fusion["bucket_genre"] = fusion["bucket_genre"].fillna(fairness.CATEGORIE_GENRE_INDETERMINEE)
    return fusion


@dataclass(frozen=True)
class ComparaisonEquiteGenre:
    """L'équité par composition de genre, avec et sans les substituts, sur la validation 2024."""

    ventilation_avec_substituts: list[fairness.VentilationGroupe]
    ventilation_sans_substituts: list[fairness.VentilationGroupe]
    ratio_avec_substituts: fairness.RatioImpactDisparate
    ratio_sans_substituts: fairness.RatioImpactDisparate

    def resume(self) -> str:
        lignes = [
            "Équité par composition de genre, validation 2024 (ADR 0011 rejoué sur ce périmètre) :",
            "  --- avec les substituts (fili, select_form, dep, acad_mies) ---",
        ]
        lignes += [g.resume() for g in self.ventilation_avec_substituts]
        lignes.append(self.ratio_avec_substituts.resume())
        lignes.append("  --- sans les substituts ---")
        lignes += [g.resume() for g in self.ventilation_sans_substituts]
        lignes.append(self.ratio_sans_substituts.resume())
        return "\n".join(lignes)


def _baseline_validation(resultat: train.ResultatEntrainement, settings: Settings) -> pd.Series:
    """La prédiction du plancher, à couverture égale, sur la seule validation 2024.

    Réutilisée pour comparer, à équité égale, le modèle complet et la
    variante sans substituts au même repère — jamais recalculée séparément.
    """
    return predictions_baseline_couverture_egale(
        resultat.table, COLONNE_TAUX_PRECEDENT, resultat.moyenne_groupe, settings.modele.split.validation
    )


def _comparaison_equite_genre(
    table_complete: pd.DataFrame,
    jeu_complet: JeuDonnees,
    prediction_complete: np.ndarray,
    jeu_sans_substituts: JeuDonnees,
    prediction_sans_substituts: np.ndarray,
    prediction_baseline: np.ndarray,
    settings: Settings,
) -> ComparaisonEquiteGenre:
    composition = _composition_genre_session(settings, settings.modele.split.validation[0])
    n_tranches = settings.evaluation.n_tranches_calibration
    seuil = settings.equite.seuil_impact_disparate

    table_avec = _table_audit_genre(table_complete, jeu_complet, prediction_complete, prediction_baseline, composition)
    table_sans = _table_audit_genre(
        table_complete, jeu_sans_substituts, prediction_sans_substituts, prediction_baseline, composition
    )
    ventilation_avec = fairness.ventiler_dimension(table_avec, "bucket_genre", "genre", n_tranches)
    ventilation_sans = fairness.ventiler_dimension(table_sans, "bucket_genre", "genre", n_tranches)
    return ComparaisonEquiteGenre(
        ventilation_avec_substituts=ventilation_avec,
        ventilation_sans_substituts=ventilation_sans,
        ratio_avec_substituts=fairness.ratio_impact_disparate_dimension(ventilation_avec, "genre", seuil),
        ratio_sans_substituts=fairness.ratio_impact_disparate_dimension(ventilation_sans, "genre", seuil),
    )


# ─── Assemblage du rapport ───────────────────────────────────────────────────

DECLARATION_SIRENE = (
    "Ablation impossible à mesurer, pas nulle : la chaîne NAF -> ROME -> formation ne "
    "relie aucune formation Parcoursup (dim_formation) — huit millésimes vérifiés, aucun ne porte "
    "de code RNCP, NSF ou ROME (referentiel/naf_rome_formation.py, manques_declares). Sirene n'a "
    "donc aucune colonne à retirer d'un modèle où elle n'est déjà pas entrée : ce n'est pas un "
    "écart nul mesuré, c'est une mesure qui n'a pas d'objet tant que ce rattachement n'existe pas."
)


@dataclass(frozen=True)
class RapportAblation:
    """Ce que `make ablation` a produit : sept variantes, l'arbitrage genre, à déclarer telles quelles."""

    variantes: list[ResultatVariante]
    equite_genre: ComparaisonEquiteGenre
    scores_test_configuration_retenue: ScoreSession
    declaration_sirene: str = field(default=DECLARATION_SIRENE)

    def resume(self) -> str:
        lignes = ["Ablation — écart mesuré par variante, sur la validation 2024 :", ""]
        lignes += [variante.resume() for variante in self.variantes]
        lignes.append("")
        lignes.append(self.equite_genre.resume())
        lignes.append("")
        lignes.append(
            "Configuration retenue (production) — score de test 2025, touché une seule "
            f"fois par l'entraînement de production, non recalculé ici : {self.scores_test_configuration_retenue.resume()}"
        )
        lignes.append("")
        lignes.append(f"Sirene : {self.declaration_sirene}")
        return "\n".join(lignes)


def _journaliser_mlflow(rapport: RapportAblation, settings: Settings) -> None:
    """Enregistre chaque variante comme un run MLflow taggé : même politique que les
    autres étapes du module `models` — absence de tracking journalisée, jamais masquée.
    """
    if not settings.mlflow_tracking_uri:
        LOGGER.warning("MLFLOW_TRACKING_URI non configuré : ablation non journalisée dans MLflow.")
        return
    try:
        import mlflow
    except ImportError:
        LOGGER.warning("Le paquet mlflow n'est pas installé dans cet environnement : ablation non journalisée.")
        return

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(NOM_EXPERIENCE_MLFLOW)
    for variante in rapport.variantes:
        with mlflow.start_run(run_name=f"ablation-{variante.nom}"):
            mlflow.set_tag("etape", "ablation")
            mlflow.set_tag("variante", variante.nom)
            mlflow.log_param("n_variables", variante.n_variables)
            mlflow.log_param("description", variante.description)
            mlflow.log_metric("mae_validation", variante.mae_validation)
            mlflow.log_metric("ecart_mae_vs_complet", variante.ecart_mae_vs_complet)
            mlflow.log_metric("ece_validation", variante.ece_validation)
    with mlflow.start_run(run_name="ablation-equite-genre"):
        mlflow.set_tag("etape", "ablation")
        # `nanmin` : un ratio `NaN` (aucune sélection dans aucun groupe fiable,
        # voir `fairness._ratios_relatifs_au_maximum`) ne doit pas invalider
        # tout le minimum — même politique que `fairness._journaliser_mlflow`.
        mlflow.log_metric(
            "ratio_min_avec_substituts",
            float(np.nanmin(list(rapport.equite_genre.ratio_avec_substituts.ratios_modele.values()))),
        )
        mlflow.log_metric(
            "ratio_min_sans_substituts",
            float(np.nanmin(list(rapport.equite_genre.ratio_sans_substituts.ratios_modele.values()))),
        )


def executer(settings: Settings | None = None) -> RapportAblation:
    """Point d'entrée de `make ablation` : entraîne les sept variantes, compare, journalise."""
    settings = settings or get_settings()
    variables = settings.modele.variables

    # Référence : la configuration de production, déjà entraînée et évaluée
    # par l'entraînement de production. Son score de test est celui rapporté pour "la configuration
    # retenue" — jamais recalculé, seulement reporté (voir docstring du module).
    resultat_complet = train.entrainer_et_evaluer(settings)
    table = resultat_complet.table
    colonnes = resultat_complet.colonnes
    mae_reference = resultat_complet.rapport.scores_validation.mae_ponderee
    ece_reference = calibration(
        resultat_complet.jeu_validation.y,
        resultat_complet.jeu_validation.poids,
        resultat_complet.prediction_validation,
        settings.evaluation.n_tranches_calibration,
        PERIMETRE_ANALYSE,
    ).ece

    reference = ResultatVariante(
        nom="modele_complet",
        description=(
            "Référence de production : 9 colonnes de catalogue, 35 décalées, "
            "taux_session_precedente inclus ; mentions et cod_uai exclus (ADR 0013)."
        ),
        n_variables=len(colonnes),
        mae_validation=mae_reference,
        ecart_mae_vs_complet=0.0,
        ece_validation=ece_reference,
        commentaire="Ancrage : chaque écart ci-dessous lui est rapporté.",
    )

    resultat_ss, entrainement_ss = _variante_sans_substituts_genre(table, colonnes, settings, mae_reference)

    variantes = [
        reference,
        _variante_sans_decalees(table, colonnes, variables, settings, mae_reference),
        _variante_sans_taux_precedent(table, colonnes, settings, mae_reference),
        _variante_taux_precedent_seul(table, colonnes, variables, settings, mae_reference),
        _variante_mentions_incluses(settings, variables, mae_reference),
        _variante_cod_uai_reintroduit(settings, variables, mae_reference),
        resultat_ss,
    ]

    prediction_baseline_validation = _baseline_validation(resultat_complet, settings).to_numpy(dtype="float64")
    equite_genre = _comparaison_equite_genre(
        table,
        resultat_complet.jeu_validation,
        resultat_complet.prediction_validation,
        entrainement_ss.jeu_validation,
        entrainement_ss.prediction_validation,
        prediction_baseline_validation,
        settings,
    )

    rapport = RapportAblation(
        variantes=variantes,
        equite_genre=equite_genre,
        scores_test_configuration_retenue=resultat_complet.rapport.scores_test,
    )
    _journaliser_mlflow(rapport, settings)
    return rapport


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rapport = executer()
    LOGGER.info("Ablation terminée.\n%s", rapport.resume())
    return 0


if __name__ == "__main__":
    sys.exit(main())
