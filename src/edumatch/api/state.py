"""État du service de matching et d'explicabilité (E29) : construit une fois au démarrage de
l'API, jamais recalculé par requête.

## Pourquoi un entraînement au démarrage, et pas un modèle chargé depuis un registre

`models/train.entrainer_et_evaluer` (E22) est aujourd'hui la seule voie du
dépôt qui produit à la fois un modèle entraîné et la table de variables
alignée sur ses prédictions : E22 écrit un artefact dans le registre MLflow,
mais rien ne le relit ailleurs dans ce dépôt. `construire_etat_matching`
s'appuie donc sur un entraînement complet exécuté une seule fois, au démarrage
du processus API — jamais par requête, ce qui règle la latence — plutôt que
d'ajouter un chargeur de registre non éprouvé pour cette seule étape.

**Dette assumée, écrite plutôt que masquée** : un déploiement qui redémarre
souvent ré-entraîne à chaque fois. La suite naturelle est un chargeur
`mlflow.lightgbm.load_model` pointé sur la dernière version enregistrée du
registre ; hors périmètre de l'étape E29, qui porte la mise à disposition du
score par une API, pas la gestion du cycle de vie du modèle.

## Le terme de débouchés : jamais un zéro silencieux si son infrastructure manque

`matching/debouches.construire_artefacts` a besoin du stock Sirene complet
(`data/raw/sirene/StockEtablissement.parquet`, ~4,4 Go, non versionné). S'il
est absent — poste de développement sans ce fichier, ou échantillons de test
qui ne portent pas `statutDiffusionEtablissement` (voir
`tests/data/test_matching_debouches_run.py`) — `construire_etat_matching` ne
fait pas échouer tout le service : il retombe sur un jeu d'artefacts vide et
bien typé (`_artefacts_debouches_indisponibles`). Chaque formation reçoit
alors le statut `indisponible_chaine_rompue` de `matching/debouches.py`
(valeur neutre 1,0, `disponible=False`) — jamais un zéro qui ferait
disparaître une recommandation à tort. `EtatMatching.debouches_disponible`
et `.motif_indisponibilite_debouches` portent, en plus, la raison globale de
la dégradation, restituée au niveau de la réponse `/matching` plutôt que
noyée dans le détail par formation.

## L'explicabilité : lue depuis le précalcul, jamais recalculée

`construire_etat_explicabilite` charge le fichier produit par `make explain`
(E25) — `explications_locales.parquet`, ~99,8 Mo pour 440 030 cellules,
~8,3 minutes à produire. Aucun appel à `models.explain` n'a lieu ici : le
calcul à la demande n'est pas réaliste pour une API (voir le docstring de
`models/explain.py`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import polars as pl
from polars.exceptions import ColumnNotFoundError, SchemaError

from edumatch.config import Settings, get_settings
from edumatch.matching.agregat_sirene_debouches import RapportKAnonymat
from edumatch.matching.debouches import (
    ArtefactsDebouches,
    ErreurDebouches,
    RapportCorrespondanceFormation,
    construire_artefacts,
)
from edumatch.models import train
from edumatch.models.explain import NOM_FICHIER_PRECALCUL, SOUS_DOSSIER_PRECALCUL

LOGGER = logging.getLogger(__name__)

# Colonnes du catalogue de la session courante retenues pour le matching :
# les six colonnes requises par `matching.score.recommander`
# (`COLONNES_CATALOGUE_REQUISES`, sans `taux_predit` qui est ajoutée à part)
# plus les deux dimensions de la cellule (`type_bac`, `boursier`), nécessaires
# pour filtrer le catalogue au profil déclaré par le candidat avant de
# scorer — `recommander` lui-même ne filtre jamais sur ces deux colonnes.
COLONNES_CATALOGUE: tuple[str, ...] = (
    "cod_aff_form",
    "fili",
    "fil_lib_voe_acc",
    "form_lib_voe_acc",
    "dep",
    "type_bac",
    "boursier",
)


class ErreurEtatAPI(RuntimeError):
    """L'état du service ne peut pas être construit."""


@dataclass(frozen=True)
class EtatMatching:
    """Tout ce dont les routes `/matching` ont besoin pour scorer une requête sans recalculer
    un modèle ni relire un fichier — voir le docstring du module pour la construction."""

    settings: Settings
    session_courante: int
    catalogue: pd.DataFrame
    artefacts_debouches: ArtefactsDebouches
    debouches_disponible: bool
    motif_indisponibilite_debouches: str | None


@dataclass(frozen=True)
class EtatExplicabilite:
    """Le précalcul SHAP par cellule (E25), chargé une fois — voir le docstring du module."""

    precalcul: pd.DataFrame
    colonnes_shap: tuple[str, ...]
    chemin: Path


def _artefacts_debouches_indisponibles() -> ArtefactsDebouches:
    """Un jeu d'artefacts vide et bien typé : toute cellule devient
    `STATUT_INDISPONIBLE_CHAINE_ROMPUE` (valeur neutre, `disponible=False`), jamais un zéro
    silencieux — voir le docstring du module."""
    return ArtefactsDebouches(
        correspondance_formation=pl.DataFrame(schema={"fil_lib_voe_acc": pl.Utf8, "code_rncp_ideo": pl.Utf8}),
        table_naf_rome_formation=pl.DataFrame(schema={"code_rncp_ideo": pl.Utf8, "naf_division": pl.Utf8}),
        agregat_conserve=pl.DataFrame(
            schema={"departement": pl.Utf8, "naf_division": pl.Utf8, "nb_actifs_employeurs_diffusibles": pl.Int64}
        ),
        cellules_non_vides=pl.DataFrame(schema={"departement": pl.Utf8, "naf_division": pl.Utf8}),
        rapport_k_anonymat=RapportKAnonymat("departement x division_naf", 0, 0, 0, 0, 0),
        rapport_correspondance=RapportCorrespondanceFormation(0, 0, 0, 0, []),
    )


#  Les sources dont dépend `construire_artefacts` (Sirene, IDÉO, RNCP, France
#  Travail) peuvent chacune manquer pour une raison différente, et ne
#  remontent pas toutes la même famille d'exception : `ErreurDebouches`
#  (fichier Sirene absent, `matching/debouches.py`), `FileNotFoundError`
#  (référentiel non téléchargé, `ingestion/referentiels.py`), ou une erreur de
#  schéma Polars (colonne Sirene absente d'un échantillon réduit — le cas de
#  `data/samples/`, voir `tests/data/test_matching_debouches_run.py`). Les
#  trois sont volontairement traitées ici comme la même famille de risque
#  (« la donnée source du terme de débouchés n'est pas exploitable ») : c'est
#  la seule dégradation tolérée par ce service, jamais étendue à `Exception`
#  nue, qui masquerait une vraie faute de programmation ailleurs.
ERREURS_SOURCES_DEBOUCHES_INDISPONIBLES: tuple[type[Exception], ...] = (
    ErreurDebouches,
    FileNotFoundError,
    ColumnNotFoundError,
    SchemaError,
)


def _construire_artefacts_debouches(
    catalogue: pd.DataFrame, settings: Settings
) -> tuple[ArtefactsDebouches, bool, str | None]:
    try:
        artefacts = construire_artefacts(pl.from_pandas(catalogue[["fil_lib_voe_acc"]].drop_duplicates()), settings)
    except ERREURS_SOURCES_DEBOUCHES_INDISPONIBLES as erreur:
        LOGGER.warning(
            "Terme de débouchés indisponible au démarrage de l'API (dégradé, jamais silencieux) : %s: %s",
            type(erreur).__name__,
            erreur,
        )
        return _artefacts_debouches_indisponibles(), False, str(erreur)
    return artefacts, True, None


def construire_etat_matching(settings: Settings | None = None) -> EtatMatching:
    """Entraîne le modèle (E22), construit le catalogue de la session courante et les
    artefacts de débouchés (E28). Coûteux — appelé une seule fois, au démarrage."""
    settings = settings or get_settings()
    resultat = train.entrainer_et_evaluer(settings)

    index_test = resultat.jeu_test.X.index
    catalogue = resultat.table.loc[index_test, list(COLONNES_CATALOGUE)].copy().reset_index(drop=True)
    catalogue["cod_aff_form"] = catalogue["cod_aff_form"].astype(str)
    catalogue["type_bac"] = catalogue["type_bac"].astype(str)
    catalogue["boursier"] = catalogue["boursier"].astype(bool)
    catalogue["taux_predit"] = resultat.prediction_test

    sessions_test = settings.modele.split.test
    if len(sessions_test) != 1:
        raise ErreurEtatAPI(
            f"`modele.split.test` porte {len(sessions_test)} session(s) ({sessions_test}) : "
            "l'API suppose une session de test unique (ADR 0012)."
        )

    artefacts, disponible, motif = _construire_artefacts_debouches(catalogue, settings)

    return EtatMatching(
        settings=settings,
        session_courante=sessions_test[0],
        catalogue=catalogue,
        artefacts_debouches=artefacts,
        debouches_disponible=disponible,
        motif_indisponibilite_debouches=motif,
    )


def construire_etat_explicabilite(settings: Settings | None = None) -> EtatExplicabilite:
    """Charge le précalcul SHAP (E25) écrit par `make explain` — jamais recalculé ici."""
    settings = settings or get_settings()
    chemin = settings.processed_dir / SOUS_DOSSIER_PRECALCUL / NOM_FICHIER_PRECALCUL
    if not chemin.exists():
        raise ErreurEtatAPI(
            f"Précalcul d'explicabilité introuvable sous {settings.processed_dir.name}/{SOUS_DOSSIER_PRECALCUL}/ : "
            "exécuter `make explain` (E25) avant de démarrer l'API."
        )
    precalcul = pd.read_parquet(chemin)
    precalcul["cod_aff_form"] = precalcul["cod_aff_form"].astype(str)
    precalcul["type_bac"] = precalcul["type_bac"].astype(str)
    precalcul["boursier"] = precalcul["boursier"].astype(bool)
    colonnes_shap = tuple(colonne for colonne in precalcul.columns if colonne.startswith("shap__"))
    return EtatExplicabilite(precalcul=precalcul, colonnes_shap=colonnes_shap, chemin=chemin)
