"""Tâches unitaires du DAG (E33) : la frontière stable entre l'orchestration et le code métier.

Chaque fonction appelle directement le point d'entrée déjà testé du module
correspondant — `telecharger_tous()` pour l'ingestion, `executer()` pour la
qualité, la transformation et les modules avals, `purger()` pour la purge
d'audit — sans réimplémenter la moindre règle. Le seul apport de ce module
est de figer une signature uniforme, `f(settings) -> résultat`, appelable
aussi bien par un `PythonOperator` Airflow (`pipelines/edumatch_pipeline.py`)
que par un test qui n'installe pas Airflow.

Une tâche fait une chose : chacune ne fait qu'un seul appel au module métier,
jamais deux étapes combinées, pour que son échec reste isolé et que sa
reprise (`orchestration/reprise.py`) rejoue exactement le grain qui a
échoué — jamais plus, jamais moins.
"""

from __future__ import annotations

import logging
from typing import Any

from edumatch.api import audit_purge
from edumatch.config import Settings, get_settings
from edumatch.features import build as features_build
from edumatch.ingestion import parcoursup, referentiels, sirene
from edumatch.quality import run as quality_run
from edumatch.quality._diagnostic import RapportControle
from edumatch.referentiel import naf_rome_formation
from edumatch.spark import run_sirene_agregats
from edumatch.transform import run as transform_run
from edumatch.transform import run_etoile

LOGGER = logging.getLogger(__name__)


def ingerer_parcoursup(settings: Settings | None = None) -> list[Any]:
    """Télécharge les millésimes Parcoursup manquants ou modifiés (E05).

    Idempotente par construction : un millésime déjà présent et intact
    (empreinte SHA-256 identique au manifeste) n'est pas retéléchargé.
    """
    settings = settings or get_settings()
    return parcoursup.telecharger_tous(settings=settings)


def ingerer_sirene(settings: Settings | None = None) -> list[Any]:
    """Résout le catalogue Sirene et télécharge les quatre fichiers stock (E06)."""
    settings = settings or get_settings()
    return sirene.telecharger_tous(settings=settings)


def ingerer_referentiels(settings: Settings | None = None) -> list[Any]:
    """Télécharge IDÉO, l'export RNCP du jour et la table ROME/NAF France Travail (E07)."""
    settings = settings or get_settings()
    return referentiels.telecharger_tous(settings=settings)


def controler_qualite(settings: Settings | None = None) -> RapportControle:
    """Exécute les contrôles qualité des trois sources et arrête la chaîne s'ils bloquent (E14).

    `RapportControle.lever_si_bloquant()` lève `ErreurQualiteBloquante`, qui
    hérite d'`ErreurDefinitive` (`quality/_diagnostic.py`) : la reprise
    (`reprise.py`) ne la retente jamais, elle alerte directement. Dans le DAG
    Airflow, cette tâche en échec empêche mécaniquement l'exécution des
    tâches placées après elle (`trigger_rule` par défaut : `all_success`) —
    c'est ce qui réalise le blocage, pas une vérification supplémentaire
    écrite ici.
    """
    settings = settings or get_settings()
    rapport = quality_run.executer(settings)
    rapport.lever_si_bloquant()
    return rapport


def transformer_silver(settings: Settings | None = None) -> Any:
    """Réconcilie les huit millésimes Parcoursup, bronze vers silver (E15)."""
    settings = settings or get_settings()
    return transform_run.executer(settings)


def construire_gold(settings: Settings | None = None) -> Any:
    """Construit le modèle en étoile gold depuis silver (E16)."""
    settings = settings or get_settings()
    return run_etoile.executer(settings)


def agreger_sirene(settings: Settings | None = None) -> Any:
    """Agrège Sirene par commune x NAF, projection et filtrage à la lecture (E17)."""
    settings = settings or get_settings()
    return run_sirene_agregats.executer(settings)


def reconcilier_naf_rome(settings: Settings | None = None) -> Any:
    """Construit la table NAF -> ROME -> formation et mesure sa couverture (E18)."""
    settings = settings or get_settings()
    table, rapport = naf_rome_formation.construire_et_mesurer(settings)
    naf_rome_formation.ecrire_table_et_rapport(settings, table, rapport)
    return rapport


def construire_variables(settings: Settings | None = None) -> Any:
    """Construit la table de variables d'apprentissage depuis gold (E20)."""
    settings = settings or get_settings()
    return features_build.executer(settings)


def purger_audit(settings: Settings | None = None) -> Any:
    """Applique réellement les trois paliers de conservation du journal d'inférence (E30, art. 12).

    `simulation=False` explicite : le mode par défaut de `audit_purge.purger`
    est une simulation qui ne modifie rien, précisément pour qu'un appel
    accidentel ne purge jamais de donnée. Une tâche planifiée qui se
    contenterait de cette simulation par défaut ne purgerait jamais rien :
    c'est exactement le manque que cette tâche referme.
    """
    settings = settings or get_settings()
    return audit_purge.purger(settings, simulation=False)
