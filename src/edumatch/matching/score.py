"""Score de matching à trois termes (E28) : affinité x accessibilité x débouchés.

    score = affinité  x  accessibilité  x  débouchés
            règles        MODÈLE APPRIS    agrégats Sirene
            (`affinite`)  (`models/`)      (`debouches`)

Un seul composant est appris — l'accessibilité. Les deux autres sont des
règles déclaratives et un dénombrement Sirene, cohérent avec le principe
d'architecture retenu pour l'ensemble du projet : un seul composant appris.

## Le caractère multiplicatif : un terme nul supprime la recommandation

C'est voulu, pas un effet de bord : une formation inaccessible, ou sans
débouché **mesuré comme nul**, ou hors des préférences exprimées, ne doit
jamais être recommandée, même si les deux autres termes sont excellents.
`tests/unit/test_matching_score.py::test_un_terme_nul_supprime_le_score`
le démontre pour chacun des trois termes séparément.

Effet de bord à présenter honnêtement, jamais à masquer : trois termes
proches de 1 donnent un score proche de 1, mais trois termes à 0,5 chacun
donnent 0,125, pas 0,5. Un score multiplicatif punit sévèrement une
formation moyenne sur les trois critères à la fois — ce n'est pas une
formation « moyenne », c'est une formation qui n'excelle sur aucun des
trois. `ScoreFormation` expose donc toujours les trois termes séparément, à
côté du score global : un conseiller ne doit jamais lire seulement 0,125
sans voir qu'aucun des trois facteurs n'est en cause à lui seul.

## L'accessibilité : bornée, et sa mise en garde rappelée à chaque score

Le modèle (E22) est une régression LightGBM, non contrainte à [0, 1] par
construction, alors que le label qu'il prédit l'est structurellement (ADR
0009). `borner_accessibilite` ramène toute prédiction dans [0, 1] par un
simple écrêtage — la correction naturelle liée à la définition du label,
pas un choix de mise à l'échelle arbitraire.

**Ce terme n'a pas encore battu son plancher.** Mesuré sur le test 2025
(`04-modele/evaluation.md`, E22-E23) : MAE pondérée 0,0758 pour le modèle
contre 0,0701 pour la baseline (le taux de la session précédente, à
couverture égale) — le modèle reste au-dessus du plancher qu'il doit
battre, et sa calibration s'y dégrade également. `MISE_EN_GARDE_ACCESSIBILITE`
est portée par chaque `ScoreFormation` produit ici, pas seulement documentée
en commentaire : l'honnêteté du dossier veut que ce soit écrit là où le
terme est consommé, pas seulement là où il a été mesuré.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from edumatch.config import Settings, get_settings
from edumatch.matching.affinite import ProfilCandidat, TermeAffinite, calculer_affinite
from edumatch.matching.debouches import ArtefactsDebouches, TermeDebouches, calculer_terme_debouches

LOGGER = logging.getLogger(__name__)

MISE_EN_GARDE_ACCESSIBILITE = (
    "L'accessibilité prédite ne bat pas encore la baseline sur le jeu de test 2025 : "
    "MAE pondérée 0,0758 (modèle) contre 0,0701 (taux de la session précédente, à couverture "
    "égale) — voir 04-modele/evaluation.md (E22-E23). La calibration du modèle s'y dégrade "
    "également. Ce terme est utilisable mais pas encore validé au sens du protocole "
    "d'évaluation : à lire comme un ordre de grandeur, pas comme une probabilité fiable, "
    "tant que ce résultat n'a pas été renversé."
)

# Colonnes attendues du catalogue passé à `recommander` — une ligne par cellule
# (formation x type de bac x boursier), les mêmes attributs de catalogue que
# `modele.variables.session_courante` (ADR 0013) plus la prédiction du modèle.
COLONNES_CATALOGUE_REQUISES: tuple[str, ...] = (
    "cod_aff_form",
    "fili",
    "fil_lib_voe_acc",
    "form_lib_voe_acc",
    "dep",
    "taux_predit",
)


class ErreurScore(RuntimeError):
    """Le catalogue passé à `recommander` ne porte pas les colonnes requises."""


def borner_accessibilite(taux_predit: float) -> float:
    """Ramène une prédiction du modèle d'accessibilité dans [0, 1] — voir le docstring du module."""
    return min(1.0, max(0.0, float(taux_predit)))


@dataclass(frozen=True)
class ScoreFormation:
    """Le score d'une formation pour un profil, et le détail des trois termes qui le composent —
    jamais un nombre seul : c'est ce détail qu'un conseiller lit pour expliquer une recommandation
    ou son absence (E31, l'écran de supervision)."""

    identifiant_cellule: str
    score: float
    affinite: TermeAffinite
    accessibilite: float
    accessibilite_brute: float
    debouches: TermeDebouches
    mise_en_garde_accessibilite: str = MISE_EN_GARDE_ACCESSIBILITE


def calculer_score(
    affinite: TermeAffinite,
    accessibilite_predite: float,
    debouches: TermeDebouches,
    identifiant_cellule: str,
) -> ScoreFormation:
    """Combine les trois termes déjà calculés — cette fonction ne recalcule rien, elle multiplie."""
    accessibilite = borner_accessibilite(accessibilite_predite)
    score = affinite.valeur * accessibilite * debouches.valeur
    return ScoreFormation(
        identifiant_cellule=identifiant_cellule,
        score=score,
        affinite=affinite,
        accessibilite=accessibilite,
        accessibilite_brute=float(accessibilite_predite),
        debouches=debouches,
    )


def _verifier_colonnes_catalogue(catalogue: pd.DataFrame) -> None:
    manquantes = set(COLONNES_CATALOGUE_REQUISES) - set(catalogue.columns)
    if manquantes:
        raise ErreurScore(
            f"Colonne(s) {sorted(manquantes)} absente(s) du catalogue passé à `recommander` : "
            f"colonnes requises {COLONNES_CATALOGUE_REQUISES}."
        )


def recommander(
    catalogue: pd.DataFrame,
    profil: ProfilCandidat,
    artefacts_debouches: ArtefactsDebouches,
    settings: Settings | None = None,
    top_n: int = 10,
) -> list[ScoreFormation]:
    """Score chaque ligne de `catalogue` pour `profil` et retourne les `top_n` meilleures.

    `catalogue` : une ligne par cellule (formation x type de bac x boursier),
    colonnes `COLONNES_CATALOGUE_REQUISES` — typiquement un sous-ensemble de
    la table de variables (E20) enrichi de `taux_predit` (la prédiction du
    modèle d'accessibilité, E22, jamais recalculée ici : voir
    `matching/score.py` au niveau du module pour le pourquoi de la
    séparation entraînement / scoring).

    Implémentation ligne à ligne, délibérément simple pour rester lisible et
    défendable devant un jury : à vectoriser (jointures Polars plutôt qu'une
    boucle Python) si l'API (E29) doit scorer un catalogue de dizaines de
    milliers de lignes en dessous du SLO de latence (`api.slo_latence_p95_ms`,
    `configs/base.yaml`) — non fait ici, hors périmètre de ce module.
    """
    settings = settings or get_settings()
    _verifier_colonnes_catalogue(catalogue)

    resultats: list[ScoreFormation] = []
    for ligne in catalogue.itertuples(index=False):
        affinite = calculer_affinite(
            fili=ligne.fili,
            fil_lib_voe_acc=ligne.fil_lib_voe_acc,
            form_lib_voe_acc=ligne.form_lib_voe_acc,
            departement_formation=ligne.dep,
            profil=profil,
            facteur_territoire_hors_zone=settings.matching.facteur_territoire_hors_zone,
        )
        debouches = calculer_terme_debouches(
            fil_lib_voe_acc=ligne.fil_lib_voe_acc,
            departement_candidat=profil.departement,
            correspondance_formation=artefacts_debouches.correspondance_formation,
            table_naf_rome_formation=artefacts_debouches.table_naf_rome_formation,
            agregat_conserve=artefacts_debouches.agregat_conserve,
            cellules_non_vides=artefacts_debouches.cellules_non_vides,
            seuil_saturation=settings.matching.seuil_saturation_etablissements,
        )
        resultats.append(
            calculer_score(
                affinite=affinite,
                accessibilite_predite=ligne.taux_predit,
                debouches=debouches,
                identifiant_cellule=str(ligne.cod_aff_form),
            )
        )
    resultats.sort(key=lambda resultat: resultat.score, reverse=True)
    return resultats[:top_n]
