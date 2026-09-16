"""Audit d'équité du modèle d'accessibilité (E26) : quatre dimensions, ratio d'impact disparate.

## Ce que ce module fait, et ce qu'il ne refait pas

`models/train.py` (E22) entraîne le modèle et le juge globalement ; ce module
ne relance rien : il appelle `train.entrainer_et_evaluer` — même protocole,
même split temporel, même modèle déjà arrêté sur la validation — pour
récupérer les prédictions déjà calculées sur le seul test 2025, puis les
ventile selon quatre dimensions (`configs/base.yaml`, `equite.dimensions`) :
type de baccalauréat, statut de boursier, territoire, genre.

Le genre **n'est jamais une variable du modèle** (ADR 0011, invariant du
projet) : il n'apparaît dans aucune colonne de `modele.variables` et n'a donc
jamais l'occasion d'entrer dans l'entraînement. Ce module ne le lit que pour
l'audit, directement dans la table silver (E15), qui porte — comme toute
colonne source Parcoursup, y compris celles classées `exclues` — les
compteurs de candidatures et d'admissions par sexe (`voe_tot_f`, `acc_tot_f`)
que la liste blanche de `train.py` ne laisse jamais atteindre le modèle.
C'est tout l'intérêt de la démarche : mesurer si un système qui ne reçoit
jamais le genre en entrée produit malgré tout un traitement différent selon
le genre, par la médiation d'un substitut (la filière, notamment — ADR 0011
chiffre sa corrélation résiduelle à 19,5 %).

## La conversion d'un taux continu en décision : le choix assumé

Le ratio d'impact disparate (la règle des quatre cinquièmes) se définit sur
une décision binaire — sélectionné ou non — alors que la cible de ce modèle
est un taux continu dans [0, 1] (ADR 0009). `SEUIL_DECISION_RECOMMANDATION`
convertit l'un en l'autre : une cellule est comptée « recommandée » si le
taux prédit est au moins de 50 %, c'est-à-dire si le modèle annonce plus
d'une chance sur deux d'admission. Ce seuil a été préféré à un partage par
médiane (qui produirait toujours exactement 50 % de cellules « positives »
dans chaque groupe par construction, masquant tout écart réel d'accessibilité
entre groupes) parce qu'il conserve un sens absolu, indépendant de la
distribution du groupe observé — condition nécessaire pour que le ratio
mesure un écart réel plutôt qu'un artefact du découpage.

Le taux de sélection par groupe est pondéré par l'effectif de la cellule
(`nb_voe_pp`), pas compté cellule par cellule : il répond à la question
« quelle part des candidats de ce groupe reçoit une recommandation
favorable », pas « quelle part des cellules de ce groupe », cohérent avec la
pondération qui gouverne le reste du projet (ADR 0009).

## Le piège déjà rencontré sur ce chiffre précis, et sa correction

Une formation sans aucun admis (`acc_tot == 0`) a une part de femmes parmi
les admis égale à 0 % par construction, pas parce qu'elle serait masculine.
Ce module ne classe donc jamais le genre d'une formation sur sa composition
**parmi les admis** (circulaire de toute façon : c'est en partie ce que le
modèle prédit) mais sur sa composition **parmi les candidats**
(`voe_tot_f / voe_tot`), et réserve une catégorie à part
(`CATEGORIE_GENRE_INDETERMINEE`) aux formations sans aucun vœu — jamais
confondues avec une formation réellement peu féminisée.
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
import pyarrow.parquet as pq

from edumatch.config import PROJECT_ROOT, Settings, get_settings
from edumatch.features.label import calculer_taux
from edumatch.models import train
from edumatch.models.metrics import (
    calibration,
    mae_non_ponderee,
    mae_ponderee,
    predictions_baseline_couverture_egale,
)
from edumatch.models.train import COLONNE_TAUX_PRECEDENT

LOGGER = logging.getLogger(__name__)

DOSSIER_FIGURES_DEFAUT = PROJECT_ROOT / "reports" / "figures"
NOM_FIGURE_IMPACT_DISPARATE = "e26-impact-disparate.png"
NOM_FIGURE_CALIBRATION_GENRE = "e26-calibration-genre.png"
NOM_FIGURE_SUBSTITUTS = "e26-substituts-genre.png"

# Réutilise le nom de fichier déjà fixé par `transform.run` / `features.build`
# (E15) — redéfini ici plutôt qu'importé, par le même principe que ces deux
# modules : celui qui consomme un chemin ne doit pas dépendre de celui qui
# l'écrit pour une simple constante de nom de fichier.
NOM_FICHIER_SILVER = "silver.parquet"

# ─── Dette de configuration assumée ─────────────────────────────────────────
#
# Ces trois seuils relèvent, comme `equite.seuil_impact_disparate` (déjà dans
# `configs/base.yaml`), d'une configuration externalisée plutôt que d'une
# constante de module. Ils restent ici pour cette étape : `configs/base.yaml`
# est modifié par un autre travail au moment où ce module est écrit, et la
# consigne d'isolation de cette tâche interdit d'y toucher. Dette déclarée,
# à résorber en déplaçant ces trois valeurs dans la section `equite` dès que
# ce fichier redevient libre — sans changer les valeurs elles-mêmes, qui
# restent celles utilisées ici.
SEUIL_DECISION_RECOMMANDATION: float = 0.50
BORNES_COMPOSITION_GENRE: tuple[float, float] = (0.20, 0.80)
N_CELLULES_MIN_FIABLE: int = 30

# Territoire : `region_etab_aff` (28 modalités sur la session 2025) plutôt que
# `dep` (106 modalités) — la dimension la plus fine produirait de nombreux
# groupes sous le seuil de fiabilité (`N_CELLULES_MIN_FIABLE`), rendant leur
# ratio d'impact disparate individuellement peu interprétable. `dep` reste
# disponible dans la table assemblée pour qui veut descendre au grain fin.
TERRITOIRE_COLONNE = "region_etab_aff"

# Colonnes de `modele.variables` (licites, donc déjà vues par le modèle) dont
# la corrélation résiduelle avec le genre est testée (ADR 0011 : la filière
# reconstitue 19,5 % du genre). `acad_mies` et `etablissement_origine` sont
# les deux substituts nommés par `configs/base.yaml` (`equite.substituts_a_tester`);
# `etablissement_origine` (`cod_uai`) n'est testable que pour mémoire : il est
# exclu de la table de variables précisément parce qu'il est un substitut
# (ADR 0013, motif `substitut`), il n'a donc jamais l'occasion de fuiter par
# ce canal, et ce module ne va pas le rechercher dans la table silver rien
# que pour un test qui ne dirait rien du modèle réellement entraîné.
COLONNES_SUBSTITUTS_TESTEES: tuple[str, ...] = ("fili", "acad_mies", "dep", "region_etab_aff")

CATEGORIE_GENRE_MINORITAIRE = "moins_de_20pct_femmes_parmi_les_candidats"
CATEGORIE_GENRE_MIXTE = "mixte_20_a_80pct_femmes_parmi_les_candidats"
CATEGORIE_GENRE_MAJORITAIRE = "plus_de_80pct_femmes_parmi_les_candidats"
CATEGORIE_GENRE_INDETERMINEE = "sans_candidature_denominateur_nul"

# La définition d'équité privilégiée par cet audit — calibration par groupe :
# à taux annoncé égal, la fréquence réellement observée doit être la même
# quel que soit le groupe. Choisie plutôt que la parité démographique (les
# taux d'admission diffèrent légitimement entre bac général, technologique et
# professionnel : les forcer à l'égalité fausserait une différence réelle de
# sélectivité) et plutôt que les cotes égalisées (mathématiquement
# incompatibles avec la calibration par groupe dès que les taux de base
# diffèrent entre groupes — Kleinberg, Mullainathan, Raghavan ; Chouldechova,
# 2016-2017 — et ce système annonce une probabilité, jamais une décision
# binaire, ce qui rend la calibration le bon niveau d'exigence). Ce que ce
# choix renonce à garantir : l'égalité du taux de vrais positifs entre
# groupes (égalité des chances) et l'égalité du taux de recommandation
# (parité démographique) — assumé, voir l'argumentaire de restitution.
DEFINITION_EQUITE_RETENUE = "calibration_par_groupe"


class ErreurAuditEquite(RuntimeError):
    """L'audit ne peut pas continuer sans violer une garantie attendue.

    Définitive : une session de test qui n'est pas unique, une table silver
    absente, ou une colonne attendue manquante ne se résolvent pas en
    relançant l'audit à l'identique.
    """


def chemin_silver(settings: Settings) -> Path:
    """Emplacement de la table silver (E15) — seule source qui porte encore les colonnes de genre."""
    return settings.interim_dir / "parcoursup" / NOM_FICHIER_SILVER


def _session_test(settings: Settings) -> int:
    """La session unique de test (ADR 0012) : cet audit ne porte que sur elle, jamais sur la validation."""
    sessions = settings.modele.split.test
    if len(sessions) != 1:
        raise ErreurAuditEquite(
            f"L'audit d'équité (E26) suppose un test réduit à une seule session ; "
            f"`modele.split.test` en porte {len(sessions)} ({sessions})."
        )
    return sessions[0]


def classer_composition_genre(composition_candidate: pd.Series) -> pd.Series:
    """Range chaque formation dans l'une des quatre catégories de composition candidate par genre.

    `composition_candidate` manquante (formation sans aucun vœu recensé,
    dénominateur nul) -> `CATEGORIE_GENRE_INDETERMINEE`, jamais assimilée à
    une composition connue et basse (voir docstring du module, le piège déjà
    rencontré sur ce chiffre précis).
    """
    basse, haute = BORNES_COMPOSITION_GENRE
    bucket = pd.Series(CATEGORIE_GENRE_INDETERMINEE, index=composition_candidate.index, dtype="object")
    connue = composition_candidate.notna()
    bucket.loc[connue & (composition_candidate < basse)] = CATEGORIE_GENRE_MINORITAIRE
    bucket.loc[connue & (composition_candidate >= basse) & (composition_candidate <= haute)] = (
        CATEGORIE_GENRE_MIXTE
    )
    bucket.loc[connue & (composition_candidate > haute)] = CATEGORIE_GENRE_MAJORITAIRE
    return bucket


def charger_composition_genre(settings: Settings) -> pd.DataFrame:
    """La composition par genre de chaque formation de la session de test, lue dans la table silver (E15).

    Deux ratios distincts, jamais confondus (voir docstring du module) :
    `composition_candidate` (`voe_tot_f / voe_tot`), qui sert à classer le
    genre de la formation, et `composition_admise` (`acc_tot_f / acc_tot`),
    gardée à titre descriptif pour vérifier, sur la session de test, l'écart
    d'admission entre sexes déjà mesuré en phase d'exploration (E11).
    """
    session_test = _session_test(settings)
    chemin = chemin_silver(settings)
    if not chemin.exists():
        raise ErreurAuditEquite(f"{chemin} est introuvable : exécuter `make silver` (E15) avant l'audit d'équité.")

    colonnes = ["session", "cod_aff_form", "voe_tot", "voe_tot_f", "acc_tot", "acc_tot_f"]
    silver = pq.read_table(chemin, columns=colonnes).to_pandas()
    silver = silver.loc[silver["session"] == session_test].copy()
    if silver.empty:
        raise ErreurAuditEquite(f"Aucune ligne silver pour la session de test {session_test}.")

    composition_candidate, _ = calculer_taux(silver["voe_tot_f"], silver["voe_tot"])
    composition_admise, _ = calculer_taux(silver["acc_tot_f"], silver["acc_tot"])

    composition = pd.DataFrame(
        {
            "cod_aff_form": silver["cod_aff_form"].astype("string").astype(str),
            "composition_candidate": composition_candidate.astype("float64"),
            "composition_admise": composition_admise.astype("float64"),
        }
    )
    composition["bucket_genre"] = classer_composition_genre(composition["composition_candidate"])
    return composition


def construire_table_predictions(settings: Settings) -> tuple[pd.DataFrame, train.ResultatEntrainement]:
    """Une ligne par cellule de test, avec la prédiction du modèle et celle de la baseline à couverture égale.

    Rejoue exactement le protocole d'entraînement (E22) via
    `train.entrainer_et_evaluer` — même modèle, même split, même
    `random_state` — pour que cet audit ne juge jamais un modèle différent de
    celui qu'E22/E23 rapportent. `cod_aff_form` n'est pas une variable du
    modèle (ADR 0013, catégorie `cles`) : elle est relue depuis
    `resultat.table`, alignée par index sur `jeu_test.X`, jamais depuis une
    colonne de `jeu_test.X` lui-même qui ne la porte pas.
    """
    resultat = train.entrainer_et_evaluer(settings)
    index_test = resultat.jeu_test.X.index
    lignes = resultat.table.loc[index_test]

    colonnes_requises = ("cod_aff_form", "type_bac", "boursier", "dep", "region_etab_aff", "acad_mies", "fili")
    manquantes = [colonne for colonne in colonnes_requises if colonne not in lignes.columns]
    if manquantes:
        raise ErreurAuditEquite(
            f"Colonne(s) {manquantes} absente(s) de la table de variables (E20) : "
            "audit d'équité impossible sans elles."
        )

    prediction_baseline = predictions_baseline_couverture_egale(
        resultat.table, COLONNE_TAUX_PRECEDENT, resultat.moyenne_groupe, settings.modele.split.test
    )

    table = pd.DataFrame(
        {
            "cod_aff_form": lignes["cod_aff_form"].astype("string").astype(str).to_numpy(),
            "type_bac": lignes["type_bac"].astype(str).to_numpy(),
            "boursier": lignes["boursier"].astype(bool).to_numpy(),
            "dep": lignes["dep"].astype(str).to_numpy(),
            "region_etab_aff": lignes["region_etab_aff"].astype(str).fillna("(manquant)").to_numpy(),
            "acad_mies": lignes["acad_mies"].astype(str).to_numpy(),
            "fili": lignes["fili"].astype(str).to_numpy(),
            "effectif": resultat.jeu_test.poids.to_numpy(),
            "taux_observe": resultat.jeu_test.y.to_numpy(),
            "prediction_modele": np.asarray(resultat.prediction_test, dtype="float64"),
            "prediction_baseline": prediction_baseline.to_numpy(dtype="float64"),
        }
    )
    return table, resultat


def assembler_table_audit(settings: Settings) -> tuple[pd.DataFrame, train.ResultatEntrainement]:
    """La table de cellules de test enrichie du bucket de genre de sa formation (jointure gauche)."""
    table, resultat = construire_table_predictions(settings)
    composition = charger_composition_genre(settings)
    fusion = table.merge(composition, on="cod_aff_form", how="left")
    fusion["bucket_genre"] = fusion["bucket_genre"].fillna(CATEGORIE_GENRE_INDETERMINEE)
    return fusion, resultat


@dataclass(frozen=True)
class VentilationGroupe:
    """L'erreur du modèle et celle de la baseline, sur le seul sous-ensemble d'un groupe d'une dimension."""

    dimension: str
    groupe: str
    n_cellules: int
    effectif_total: float
    fiable: bool
    mae_ponderee_modele: float
    mae_non_ponderee_modele: float
    mae_ponderee_baseline: float
    ece_modele: float
    ece_baseline: float
    taux_selection_modele: float
    taux_selection_baseline: float

    def resume(self) -> str:
        alerte = f"  [effectif insuffisant, n<{N_CELLULES_MIN_FIABLE}]" if not self.fiable else ""
        return (
            f"  {self.dimension:10s} {self.groupe:42s} n={self.n_cellules:6d} effectif={self.effectif_total:9.0f}  "
            f"mae_modele={self.mae_ponderee_modele:.4f} mae_baseline={self.mae_ponderee_baseline:.4f}  "
            f"ece_modele={self.ece_modele:.4f} ece_baseline={self.ece_baseline:.4f}  "
            f"selection_modele={self.taux_selection_modele:.1%} selection_baseline={self.taux_selection_baseline:.1%}"
            f"{alerte}"
        )


def ventiler_dimension(table: pd.DataFrame, colonne: str, dimension_nom: str, n_tranches: int) -> list[VentilationGroupe]:
    """Erreur, calibration et taux de sélection du modèle et de la baseline, groupe par groupe.

    Une cellule sans effectif ne peut pas exister ici (`features.label`
    l'interdit en amont), `effectif_total` est donc toujours strictement
    positif pour un groupe non vide.
    """
    resultats = []
    for groupe, sous in table.groupby(colonne, observed=True):
        n_cellules = len(sous)
        effectif_total = float(sous["effectif"].sum())
        ece_modele = calibration(
            sous["taux_observe"], sous["effectif"], sous["prediction_modele"], n_tranches, str(groupe)
        ).ece
        ece_baseline = calibration(
            sous["taux_observe"], sous["effectif"], sous["prediction_baseline"], n_tranches, str(groupe)
        ).ece
        poids = sous["effectif"].to_numpy(dtype="float64")
        selection_modele = sous["prediction_modele"].to_numpy() >= SEUIL_DECISION_RECOMMANDATION
        selection_baseline = sous["prediction_baseline"].to_numpy() >= SEUIL_DECISION_RECOMMANDATION
        resultats.append(
            VentilationGroupe(
                dimension=dimension_nom,
                groupe=str(groupe),
                n_cellules=n_cellules,
                effectif_total=effectif_total,
                fiable=n_cellules >= N_CELLULES_MIN_FIABLE,
                mae_ponderee_modele=mae_ponderee(sous["taux_observe"], sous["prediction_modele"], sous["effectif"]),
                mae_non_ponderee_modele=mae_non_ponderee(sous["taux_observe"], sous["prediction_modele"]),
                mae_ponderee_baseline=mae_ponderee(sous["taux_observe"], sous["prediction_baseline"], sous["effectif"]),
                ece_modele=ece_modele,
                ece_baseline=ece_baseline,
                taux_selection_modele=float((poids * selection_modele).sum() / effectif_total),
                taux_selection_baseline=float((poids * selection_baseline).sum() / effectif_total),
            )
        )
    return sorted(resultats, key=lambda v: v.groupe)


@dataclass(frozen=True)
class RatioImpactDisparate:
    """Le ratio d'impact disparate de chaque groupe d'une dimension, modèle et baseline, sur les groupes fiables.

    Référence = le groupe au taux de sélection le plus élevé parmi les
    groupes fiables (`N_CELLULES_MIN_FIABLE`) : c'est la forme usuelle de la
    règle des quatre cinquièmes — chaque groupe est jugé relativement au
    groupe le plus favorisé, pas à une valeur absolue arbitraire.
    """

    dimension: str
    seuil: float
    ratios_modele: dict[str, float]
    ratios_baseline: dict[str, float]
    groupes_exclus_effectif_insuffisant: tuple[str, ...]

    def groupes_sous_le_seuil_modele(self) -> list[str]:
        """Un ratio `NaN` (aucune sélection nulle part sur ce périmètre) n'est jamais compté comme sous le seuil :
        il est indéfini, pas mauvais — voir `_ratios_relatifs_au_maximum`."""
        return [
            groupe
            for groupe, ratio in self.ratios_modele.items()
            if not np.isnan(ratio) and ratio < self.seuil
        ]

    def groupes_sous_le_seuil_baseline(self) -> list[str]:
        return [
            groupe
            for groupe, ratio in self.ratios_baseline.items()
            if not np.isnan(ratio) and ratio < self.seuil
        ]

    @staticmethod
    def _marque(ratio: float, seuil: float) -> str:
        if np.isnan(ratio):  # aucune sélection positive dans aucun groupe fiable de cette dimension
            return "INDÉFINI (aucune sélection)"
        return "OK" if ratio >= seuil else "SOUS LE SEUIL"

    def resume(self) -> str:
        lignes = [f"  {self.dimension} (seuil={self.seuil:.0%}) :"]
        for groupe in sorted(self.ratios_modele):
            marque_m = self._marque(self.ratios_modele[groupe], self.seuil)
            marque_b = self._marque(self.ratios_baseline[groupe], self.seuil)
            lignes.append(
                f"    {groupe:42s} modele={self.ratios_modele[groupe]:.2f} ({marque_m})   "
                f"baseline={self.ratios_baseline[groupe]:.2f} ({marque_b})"
            )
        if self.groupes_exclus_effectif_insuffisant:
            lignes.append(
                f"    Exclu(s) du ratio (effectif insuffisant) : "
                f"{', '.join(self.groupes_exclus_effectif_insuffisant)}"
            )
        return "\n".join(lignes)


def _ratios_relatifs_au_maximum(valeurs: dict[str, float]) -> dict[str, float]:
    """`{groupe: valeur / max(valeurs)}`, ou `NaN` pour tous si aucun groupe n'a de sélection positive.

    Un maximum nul signifie qu'aucune cellule d'aucun groupe fiable ne
    franchit `SEUIL_DECISION_RECOMMANDATION` — un plancher ou un modèle qui
    ne recommande jamais rien sur ce périmètre. Le ratio de la règle des
    quatre cinquièmes n'a alors pas de sens (0/0) : `NaN` le dit
    explicitement plutôt qu'une exception qui interromprait tout l'audit
    pour un seul groupe dégénéré, ou qu'un ratio à 1 qui masquerait
    l'absence totale de sélection.
    """
    maximum = max(valeurs.values())
    if maximum == 0.0:
        return {groupe: float("nan") for groupe in valeurs}
    return {groupe: valeur / maximum for groupe, valeur in valeurs.items()}


def ratio_impact_disparate_dimension(
    ventilations: list[VentilationGroupe], dimension_nom: str, seuil: float
) -> RatioImpactDisparate:
    """Le ratio d'impact disparate (règle des quatre cinquièmes) d'une dimension, sur ses groupes fiables."""
    fiables = [v for v in ventilations if v.fiable]
    exclus = tuple(v.groupe for v in ventilations if not v.fiable)
    if not fiables:
        raise ErreurAuditEquite(
            f"Aucun groupe fiable (n>={N_CELLULES_MIN_FIABLE}) pour la dimension {dimension_nom} : "
            "ratio d'impact disparate incalculable."
        )
    return RatioImpactDisparate(
        dimension=dimension_nom,
        seuil=seuil,
        ratios_modele=_ratios_relatifs_au_maximum({v.groupe: v.taux_selection_modele for v in fiables}),
        ratios_baseline=_ratios_relatifs_au_maximum({v.groupe: v.taux_selection_baseline for v in fiables}),
        groupes_exclus_effectif_insuffisant=exclus,
    )


def eta_carre(valeur: pd.Series, groupe: pd.Series) -> float:
    """Part de la variance de `valeur` expliquée par l'appartenance à `groupe` (rapport de corrélation).

    Mesure symétrique de celle qu'invoque l'ADR 0011 pour chiffrer que la
    filière « reconstitue » 19,5 % du genre : la part de variance totale de
    la composition candidate qui se retrouve entre les moyennes de groupe
    plutôt qu'à l'intérieur de chaque groupe. 0 : aucun lien entre le
    substitut et le genre. 1 : connaître le groupe suffit à connaître
    exactement la composition de la formation.
    """
    valide = valeur.notna()
    v, g = valeur[valide], groupe[valide]
    if v.empty:
        return float("nan")
    moyenne_totale = v.mean()
    ss_total = float(((v - moyenne_totale) ** 2).sum())
    if ss_total == 0.0:
        return 0.0
    moyennes_groupe = v.groupby(g).transform("mean")
    ss_between = float(((moyennes_groupe - moyenne_totale) ** 2).sum())
    return ss_between / ss_total


def calculer_correlations_substituts(table_audit: pd.DataFrame, colonnes: tuple[str, ...] = COLONNES_SUBSTITUTS_TESTEES) -> dict[str, float]:
    """Le rapport de corrélation (`eta_carre`) entre chaque substitut candidat et la composition par genre.

    Calculé au grain de la formation (une ligne par `cod_aff_form`), pas au
    grain de la cellule : `fili`, `acad_mies`, `dep`, `region_etab_aff` sont
    des attributs de catalogue identiques pour toutes les cellules d'une
    même formation (`session_courante`, ADR 0013) ; les compter une fois par
    cellule surpondèrerait les formations qui déclinent le plus de profils
    `(type_bac, boursier)`.
    """
    formations = table_audit.drop_duplicates("cod_aff_form")
    return {colonne: eta_carre(formations["composition_candidate"], formations[colonne]) for colonne in colonnes}


def _tracer_impact_disparate(ratios: dict[str, RatioImpactDisparate], destination: Path) -> Path:
    """Un sous-graphique par dimension : le ratio d'impact disparate de chaque groupe, modèle et baseline."""
    figure, axes = plt.subplots(2, 2, figsize=(13, 10))
    for axe, (nom_dimension, ratio) in zip(axes.ravel(), ratios.items(), strict=False):
        groupes = sorted(ratio.ratios_modele)
        positions = np.arange(len(groupes))
        largeur = 0.35
        axe.bar(positions - largeur / 2, [ratio.ratios_modele[g] for g in groupes], largeur, label="Modèle", color="tab:blue")
        axe.bar(positions + largeur / 2, [ratio.ratios_baseline[g] for g in groupes], largeur, label="Baseline", color="tab:orange")
        axe.axhline(ratio.seuil, color="red", linestyle="--", linewidth=1, label=f"Seuil {ratio.seuil:.0%}")
        axe.set_xticks(positions)
        axe.set_xticklabels(groupes, rotation=45, ha="right", fontsize=7)
        axe.set_ylim(0.0, 1.15)
        axe.set_title(nom_dimension)
        axe.set_ylabel("Ratio d'impact disparate")
        axe.legend(fontsize=7)
    figure.suptitle("Ratio d'impact disparate par dimension — test 2025 (E26)")
    figure.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=150)
    plt.close(figure)
    return destination


def _tracer_calibration_genre(table_audit: pd.DataFrame, n_tranches: int, destination: Path) -> Path:
    """La calibration du modèle, séparément pour chaque bucket de composition candidate par genre.

    Sert directement la définition d'équité retenue par cet audit
    (calibration par groupe, voir docstring du module) : elle ne se lit pas
    sur une MAE agrégée, elle se voit ici, bucket par bucket.
    """
    figure, axe = plt.subplots(figsize=(7, 7))
    axe.plot([0, 1], [0, 1], linestyle="--", color="grey", label="Calibration parfaite")
    couleurs = {
        CATEGORIE_GENRE_MINORITAIRE: "tab:red",
        CATEGORIE_GENRE_MIXTE: "tab:green",
        CATEGORIE_GENRE_MAJORITAIRE: "tab:purple",
        CATEGORIE_GENRE_INDETERMINEE: "tab:grey",
    }
    for bucket, sous in table_audit.groupby("bucket_genre"):
        if len(sous) < N_CELLULES_MIN_FIABLE:
            continue
        rapport = calibration(sous["taux_observe"], sous["effectif"], sous["prediction_modele"], n_tranches, bucket)
        if not rapport.points:
            continue
        x = [p.prediction_moyenne for p in rapport.points]
        y = [p.observe_moyen for p in rapport.points]
        poids_max = max(p.poids for p in rapport.points)
        tailles = [max(20.0, p.poids / max(1.0, poids_max) * 400.0) for p in rapport.points]
        axe.scatter(x, y, s=tailles, c=couleurs.get(bucket, "black"), alpha=0.75, label=f"{bucket} (ECE={rapport.ece:.4f})")
    axe.set_xlabel("Taux prédit moyen (par tranche, pondéré par l'effectif)")
    axe.set_ylabel("Taux observé moyen (par tranche, pondéré par l'effectif)")
    axe.set_xlim(0.0, 1.0)
    axe.set_ylim(0.0, 1.0)
    axe.set_title("Calibration du modèle par composition de genre — test 2025 (E26)")
    axe.legend(loc="upper left", fontsize=7)
    figure.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=150)
    plt.close(figure)
    return destination


def _tracer_substituts(correlations: dict[str, float], destination: Path) -> Path:
    """Le rapport de corrélation (`eta_carre`) de chaque substitut candidat avec la composition par genre."""
    figure, axe = plt.subplots(figsize=(7, 5))
    noms = list(correlations)
    valeurs = [correlations[nom] for nom in noms]
    axe.bar(noms, valeurs, color="tab:blue")
    axe.set_ylim(0.0, 1.0)
    axe.set_ylabel("Rapport de corrélation (eta²) avec la composition de genre")
    axe.set_title("Substituts du genre parmi les variables licites du modèle (E26)")
    for indice, valeur in enumerate(valeurs):
        axe.text(indice, valeur + 0.01, f"{valeur:.1%}", ha="center", fontsize=8)
    figure.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=150)
    plt.close(figure)
    return destination


@dataclass(frozen=True)
class RapportEquite:
    """Ce que `make fairness` (E26) a produit, à déclarer tel quel — modèle discriminant ou non."""

    ventilations: dict[str, list[VentilationGroupe]]
    ratios: dict[str, RatioImpactDisparate]
    correlations_substituts: dict[str, float]
    ecart_admission_genre_median: float
    part_formations_ecart_genre_sous_5_points: float
    n_formations_indeterminees_genre: int
    chemin_figure_impact_disparate: Path
    chemin_figure_calibration_genre: Path
    chemin_figure_substituts: Path

    def resume(self) -> str:
        lignes = [
            f"Définition d'équité retenue : {DEFINITION_EQUITE_RETENUE} (voir l'argumentaire du module).",
            "",
            "Écart d'admission observé entre sexes, à l'intérieur d'une même formation, test 2025 :",
            (
                f"  écart médian = {self.ecart_admission_genre_median:+.4f}  "
                f"part des formations à moins de 5 points d'écart = "
                f"{self.part_formations_ecart_genre_sous_5_points:.1%}  "
                f"({self.n_formations_indeterminees_genre} formation(s) sans candidature "
                f"des deux sexes, exclue(s))"
            ),
            "",
            "Ventilation de l'erreur et de la sélection par dimension :",
        ]
        for dimension, groupes in self.ventilations.items():
            lignes.append(f"  --- {dimension} ---")
            for groupe in groupes:
                lignes.append(groupe.resume())
        lignes.append("")
        lignes.append("Ratio d'impact disparate (règle des quatre cinquièmes) :")
        for ratio in self.ratios.values():
            lignes.append(ratio.resume())
        lignes.append("")
        lignes.append("Substituts du genre parmi les variables licites (rapport de corrélation eta²) :")
        for colonne, valeur in self.correlations_substituts.items():
            lignes.append(f"  {colonne:20s} eta²={valeur:.3f}")
        lignes.append("")
        lignes.append(f"Figures : {self.chemin_figure_impact_disparate}, {self.chemin_figure_calibration_genre}, "
                       f"{self.chemin_figure_substituts}")
        return "\n".join(lignes)


def mesurer_ecart_admission_genre(settings: Settings) -> tuple[float, float, int]:
    """L'écart d'admission entre sexes à l'intérieur d'une même formation, sur la seule session de test.

    Reproduit, restreint au test 2025, la vérification déjà conduite en
    phase d'exploration (E11) : `écart = taux d'admission des femmes -
    taux d'admission des hommes`, tous deux calculés sur `acc_tot_f` /
    `voe_tot_f` et `(acc_tot - acc_tot_f)` / `(voe_tot - voe_tot_f)`. Une
    formation où l'un des deux sexes n'a émis aucun vœu (dénominateur nul)
    est exclue du calcul, jamais comptée à égalité avec un écart nul mesuré.
    """
    session_test = _session_test(settings)
    chemin = chemin_silver(settings)
    colonnes = ["session", "cod_aff_form", "voe_tot", "voe_tot_f", "acc_tot", "acc_tot_f"]
    silver = pq.read_table(chemin, columns=colonnes).to_pandas()
    silver = silver.loc[silver["session"] == session_test].copy()

    voe_h = silver["voe_tot"].astype("Float64") - silver["voe_tot_f"].astype("Float64")
    acc_h = silver["acc_tot"].astype("Float64") - silver["acc_tot_f"].astype("Float64")
    taux_f, _ = calculer_taux(silver["acc_tot_f"], silver["voe_tot_f"])
    taux_h, _ = calculer_taux(acc_h, voe_h)

    ecart = (taux_f.astype("float64") - taux_h.astype("float64"))
    valide = ecart.notna()
    n_indeterminees = int((~valide).sum())
    ecart_valide = ecart[valide]
    if ecart_valide.empty:
        raise ErreurAuditEquite("Aucune formation avec candidatures des deux sexes sur la session de test.")
    return float(ecart_valide.median()), float((ecart_valide.abs() < 0.05).mean()), n_indeterminees


def executer(settings: Settings | None = None, dossier_figures: Path | None = None) -> RapportEquite:
    """Point d'entrée de `make fairness` (E26) : entraîne (E22), ventile, calcule les ratios, trace les figures.

    `dossier_figures` : `reports/figures/` du dépôt par défaut ; paramétrable
    pour que les tests écrivent dans un répertoire jetable.
    """
    settings = settings or get_settings()
    dossier_figures = dossier_figures or DOSSIER_FIGURES_DEFAUT
    n_tranches = settings.evaluation.n_tranches_calibration
    seuil = settings.equite.seuil_impact_disparate

    table_audit, _ = assembler_table_audit(settings)

    dimensions = {
        "type_bac": "type_bac",
        "boursier": "boursier",
        "territoire": TERRITOIRE_COLONNE,
        "genre": "bucket_genre",
    }
    ventilations = {
        nom: ventiler_dimension(table_audit, colonne, nom, n_tranches) for nom, colonne in dimensions.items()
    }
    ratios = {
        nom: ratio_impact_disparate_dimension(groupes, nom, seuil) for nom, groupes in ventilations.items()
    }
    correlations = calculer_correlations_substituts(table_audit)
    ecart_median, part_sous_5_points, n_indeterminees = mesurer_ecart_admission_genre(settings)

    chemin_impact = _tracer_impact_disparate(ratios, dossier_figures / NOM_FIGURE_IMPACT_DISPARATE)
    chemin_calibration = _tracer_calibration_genre(table_audit, n_tranches, dossier_figures / NOM_FIGURE_CALIBRATION_GENRE)
    chemin_substituts = _tracer_substituts(correlations, dossier_figures / NOM_FIGURE_SUBSTITUTS)

    rapport = RapportEquite(
        ventilations=ventilations,
        ratios=ratios,
        correlations_substituts=correlations,
        ecart_admission_genre_median=ecart_median,
        part_formations_ecart_genre_sous_5_points=part_sous_5_points,
        n_formations_indeterminees_genre=n_indeterminees,
        chemin_figure_impact_disparate=chemin_impact,
        chemin_figure_calibration_genre=chemin_calibration,
        chemin_figure_substituts=chemin_substituts,
    )
    _journaliser_mlflow(rapport, settings)
    return rapport


def _journaliser_mlflow(rapport: RapportEquite, settings: Settings) -> None:
    """Enregistre l'audit dans MLflow : ratios, ECE par groupe, figures en artefacts.

    Même politique que les autres étapes du module `models` : l'absence de
    `mlflow_tracking_uri` ou du paquet est journalisée, pas masquée — l'audit
    déjà calculé ne dépend jamais de ce suivi pour exister.
    """
    if not settings.mlflow_tracking_uri:
        LOGGER.warning("MLFLOW_TRACKING_URI non configuré : audit d'équité non journalisé dans MLflow (E26).")
        return
    try:
        import mlflow
    except ImportError:
        LOGGER.warning("Le paquet mlflow n'est pas installé dans cet environnement : audit non journalisé.")
        return

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment("edumatch-accessibilite")
    with mlflow.start_run(run_name="audit-equite"):
        mlflow.set_tag("etape", "E26")
        mlflow.log_param("definition_equite_retenue", DEFINITION_EQUITE_RETENUE)
        mlflow.log_param("seuil_decision_recommandation", SEUIL_DECISION_RECOMMANDATION)
        mlflow.log_metric("ecart_admission_genre_median", rapport.ecart_admission_genre_median)
        mlflow.log_metric("part_formations_ecart_genre_sous_5_points", rapport.part_formations_ecart_genre_sous_5_points)
        for nom, ratio in rapport.ratios.items():
            # `nanmin` : un ratio `NaN` (aucune sélection nulle part, voir
            # `_ratios_relatifs_au_maximum`) ne doit pas invalider tout le minimum.
            mlflow.log_metric(f"{nom}_ratio_min_modele", float(np.nanmin(list(ratio.ratios_modele.values()))))
            mlflow.log_metric(f"{nom}_ratio_min_baseline", float(np.nanmin(list(ratio.ratios_baseline.values()))))
        for colonne, valeur in rapport.correlations_substituts.items():
            mlflow.log_metric(f"eta2_{colonne}", valeur)
        for chemin in (
            rapport.chemin_figure_impact_disparate,
            rapport.chemin_figure_calibration_genre,
            rapport.chemin_figure_substituts,
        ):
            mlflow.log_artifact(str(chemin))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rapport = executer()
    LOGGER.info("Audit d'équité (E26) terminé.\n%s", rapport.resume())
    return 0


if __name__ == "__main__":
    sys.exit(main())
