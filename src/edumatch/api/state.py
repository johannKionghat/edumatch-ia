"""État du service de matching et d'explicabilité (E29) : construit une fois au démarrage de
l'API, jamais recalculé par requête.

## Pourquoi un artefact précalculé, et pas un modèle chargé à chaque démarrage

Aucune route de l'API n'a besoin de l'objet modèle lui-même : `/matching`
(`api/routes/matching.py`) ne consulte que `EtatMatching.catalogue`, déjà
muni de sa colonne `taux_predit` ; `/explain` lit un fichier SHAP précalculé
(voir plus bas). Le modèle n'existe donc que pour produire, une fois, ce
catalogue — exactement ce que fait déjà `make explain` pour le SHAP.

`construire_etat_matching` cherche d'abord l'artefact que
`models.train.exporter_catalogue_predictions` écrit à la fin de `make train`
(ou de `docker/Dockerfile.train`) : `processed_dir/matching/catalogue_predictions.parquet`,
sous `EDUMATCH_DATA_ROOT` (déjà configurable par variable d'environnement,
donc montable en volume Kubernetes sans changement de code). Trouvé, il est
simplement lu — quelques dizaines de millisecondes pour 77 159 lignes,
contre les minutes d'un entraînement complet.

**Ce que ça règle, ce que ça ne règle pas** : un déploiement qui redémarre
souvent — un pod recréé par le `HorizontalPodAutoscaler`, un retour arrière —
ne réentraîne plus rien tant que l'artefact est monté. La dette qui demeure
est en amont : rien ne recharge cet artefact *pendant* que l'API tourne si un
nouvel entraînement le remplace ; un redémarrage du pod reste nécessaire.
Cela reste hors périmètre de E29/E35, qui portent la mise à disposition du
score, pas le rechargement à chaud d'un modèle vivant.

**Le repli qui subsiste, volontairement** : si l'artefact est absent —
poste de développement qui n'a encore jamais lancé `make train` — la
fonction retombe sur un entraînement complet, journalisé en
avertissement plutôt que masqué. C'est le seul cas où l'API entraîne encore
au démarrage, et il est explicite.

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


def _chemin_catalogue_predictions(settings: Settings) -> Path:
    return settings.processed_dir / train.SOUS_DOSSIER_CATALOGUE_PREDICTIONS / train.NOM_FICHIER_CATALOGUE_PREDICTIONS


def _charger_catalogue_predictions(settings: Settings) -> pd.DataFrame:
    """Le catalogue de la session de test, prédictions incluses — lu depuis l'artefact
    précalculé par `make train` si présent, sinon entraîné à la volée (voir le docstring du
    module pour ce que ce repli signifie et pourquoi il est journalisé, pas masqué)."""
    chemin = _chemin_catalogue_predictions(settings)
    if chemin.exists():
        LOGGER.info("Catalogue de prédictions chargé depuis l'artefact précalculé %s : aucun réentraînement.", chemin)
        catalogue = pd.read_parquet(chemin)
        catalogue["cod_aff_form"] = catalogue["cod_aff_form"].astype(str)
        catalogue["type_bac"] = catalogue["type_bac"].astype(str)
        catalogue["boursier"] = catalogue["boursier"].astype(bool)
        return catalogue
    LOGGER.warning(
        "Artefact %s introuvable : entraînement complet au démarrage (poste de développement "
        "sans `make train` préalable ; en production, cet artefact est produit par "
        "`docker/Dockerfile.train` et monté en volume — voir docker-compose.yml).",
        chemin,
    )
    resultat = train.entrainer_et_evaluer(settings)
    return train.construire_catalogue_predictions(resultat)


def construire_etat_matching(settings: Settings | None = None) -> EtatMatching:
    """Charge le catalogue de la session courante (déjà prédit, voir ci-dessus) et construit les
    artefacts de débouchés (E28). Appelé une seule fois, au démarrage du processus."""
    settings = settings or get_settings()

    sessions_test = settings.modele.split.test
    if len(sessions_test) != 1:
        raise ErreurEtatAPI(
            f"`modele.split.test` porte {len(sessions_test)} session(s) ({sessions_test}) : "
            "l'API suppose une session de test unique (ADR 0012)."
        )

    catalogue = _charger_catalogue_predictions(settings)
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
