"""Tâches unitaires du DAG : la frontière stable entre l'orchestration et le code métier.

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

Une exception assumée : `reentrainer_modele` enchaîne `models.train.entrainer_et_evaluer`
et `orchestration.promotion.promouvoir_si_meilleur`. Les séparer en deux tâches Airflow
obligerait à faire transiter le modèle entraîné et ses jeux de validation/test par XCom
(le mécanisme d'échange entre tâches Airflow, qui sérialise sur disque) pour que la
seconde tâche puisse comparer au plancher — coûteux et fragile pour un objet qui contient
un modèle LightGBM. La porte de promotion reste ici un choix de publication d'un même
entraînement, pas une étape métier séparée : elle ne réentraîne rien.
"""

from __future__ import annotations

import logging
from typing import Any

from edumatch.api import audit_purge
from edumatch.config import Settings, get_settings
from edumatch.features import build as features_build
from edumatch.ingestion import parcoursup, referentiels, sirene
from edumatch.models import derive as models_derive
from edumatch.models import evaluate as models_evaluate
from edumatch.models import train as models_train
from edumatch.orchestration import promotion as models_promotion
from edumatch.quality import run as quality_run
from edumatch.quality._diagnostic import RapportControle
from edumatch.referentiel import naf_rome_formation
from edumatch.spark import run_sirene_agregats
from edumatch.transform import run as transform_run
from edumatch.transform import run_etoile

LOGGER = logging.getLogger(__name__)


def ingerer_parcoursup(settings: Settings | None = None) -> list[Any]:
    """Télécharge les millésimes Parcoursup manquants ou modifiés.

    Idempotente par construction : un millésime déjà présent et intact
    (empreinte SHA-256 identique au manifeste) n'est pas retéléchargé.
    """
    settings = settings or get_settings()
    return parcoursup.telecharger_tous(settings=settings)


def ingerer_sirene(settings: Settings | None = None) -> list[Any]:
    """Résout le catalogue Sirene et télécharge les quatre fichiers stock."""
    settings = settings or get_settings()
    return sirene.telecharger_tous(settings=settings)


def ingerer_referentiels(settings: Settings | None = None) -> list[Any]:
    """Télécharge IDÉO, l'export RNCP du jour et la table ROME/NAF France Travail."""
    settings = settings or get_settings()
    return referentiels.telecharger_tous(settings=settings)


def controler_qualite(settings: Settings | None = None) -> RapportControle:
    """Exécute les contrôles qualité des trois sources et arrête la chaîne s'ils bloquent.

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
    """Réconcilie les huit millésimes Parcoursup, bronze vers silver."""
    settings = settings or get_settings()
    return transform_run.executer(settings)


def construire_gold(settings: Settings | None = None) -> Any:
    """Construit le modèle en étoile gold depuis silver."""
    settings = settings or get_settings()
    return run_etoile.executer(settings)


def agreger_sirene(settings: Settings | None = None) -> Any:
    """Agrège Sirene par commune x NAF, projection et filtrage à la lecture."""
    settings = settings or get_settings()
    return run_sirene_agregats.executer(settings)


def reconcilier_naf_rome(settings: Settings | None = None) -> Any:
    """Construit la table NAF -> ROME -> formation et mesure sa couverture."""
    settings = settings or get_settings()
    table, rapport = naf_rome_formation.construire_et_mesurer(settings)
    naf_rome_formation.ecrire_table_et_rapport(settings, table, rapport)
    return rapport


def construire_variables(settings: Settings | None = None) -> Any:
    """Construit la table de variables d'apprentissage depuis gold."""
    settings = settings or get_settings()
    return features_build.executer(settings)


def detecter_derive(settings: Settings | None = None) -> models_derive.RapportDerive:
    """Mesure la dérive des variables, de la cible et des prédictions.

    N'échoue jamais sur une dérive détectée : contrairement à `controler_qualite`
    (une donnée cassée bloque la chaîne), une dérive au-delà du seuil est un
    signal à examiner, pas une panne — elle est seulement journalisée en
    avertissement (`models.derive.main`) pour que le DAG continue et que le
    rapport (figures, MLflow) reste consultable même quand il recommande un
    réentraînement.
    """
    settings = settings or get_settings()
    rapport = models_derive.executer(settings)
    if rapport.reentrainement_recommande:
        LOGGER.warning("Dérive au-delà du seuil de réentraînement : %s", rapport.resume())
    return rapport


def reentrainer_modele(settings: Settings | None = None) -> models_promotion.RapportPromotion:
    """Réentraîne le modèle d'accessibilité et ne publie l'artefact que s'il bat le plancher.

    Appelle `models.train.entrainer_et_evaluer` — même protocole que `make train` : split
    strictement temporel, arrêt anticipé sur la seule validation, test 2025 touché une
    seule fois — puis délègue la décision de publication à
    `orchestration.promotion.promouvoir_si_meilleur`. Cette tâche ne lève jamais sur un
    refus de promotion (voir le docstring de `promotion.py`) : la comparaison au plancher
    est un résultat attendu de l'entraînement, pas une panne du graphe.

    Idempotente par construction : `entrainer_et_evaluer` fixe `random_state`, et la
    publication (si elle a lieu) écrase l'artefact par remplacement atomique — rejouer
    cette tâche sur les mêmes données produit la même décision et, si elle est promue, un
    fichier identique.
    """
    settings = settings or get_settings()
    resultat = models_train.entrainer_et_evaluer(settings)
    return models_promotion.promouvoir_si_meilleur(resultat, settings)


def evaluer_modele(settings: Settings | None = None) -> models_evaluate.RapportEvaluation:
    """Évalue le modèle réentraîné : calibration, ECE, ventilation par type de baccalauréat.

    Rejoue le même protocole que `reentrainer_modele` (`models.evaluate.executer` appelle
    lui-même `models.train.entrainer_et_evaluer`, même random_state, même split) pour
    produire un diagnostic que la seule MAE de `reentrainer_modele` ne donne pas — voir le
    docstring de `models/evaluate.py`. N'a aucune incidence sur la publication de
    l'artefact, décidée uniquement par `reentrainer_modele` : cette tâche ne fait que
    décrire, sous des angles supplémentaires, un entraînement déjà rejoué, et ne bloque
    jamais le graphe.
    """
    settings = settings or get_settings()
    return models_evaluate.executer(settings)


def purger_audit(settings: Settings | None = None) -> Any:
    """Applique réellement les trois paliers de conservation du journal d'inférence (art. 12).

    `simulation=False` explicite : le mode par défaut de `audit_purge.purger`
    est une simulation qui ne modifie rien, précisément pour qu'un appel
    accidentel ne purge jamais de donnée. Une tâche planifiée qui se
    contenterait de cette simulation par défaut ne purgerait jamais rien :
    c'est exactement le manque que cette tâche referme.
    """
    settings = settings or get_settings()
    return audit_purge.purger(settings, simulation=False)


def purger_supervision(settings: Settings | None = None) -> Any:
    """Applique réellement les trois paliers de conservation du journal de supervision (T6).

    Même exigence que `purger_audit` — `simulation=False` explicite — appliquée à
    `audit_purge.purger_feedback`, qui referme le motif de blocage B du registre : une durée
    de conservation documentée (`docs/registres.html#t6`) mais qu'aucune tâche planifiée
    n'appliquait.
    """
    settings = settings or get_settings()
    return audit_purge.purger_feedback(settings, simulation=False)
