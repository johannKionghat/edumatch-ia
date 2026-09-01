"""DAG Airflow (E33) : orchestre exactement la chaîne déjà portée par `Makefile`.

Ce fichier n'est chargé que par le planificateur Airflow (le conteneur
`airflow` de `docker-compose.yml`) : il importe `airflow`, une dépendance
volontairement absente de l'environnement de développement et de test tant
qu'aucune image dédiée ne l'installe (voir l'extra `airflow` de
`pyproject.toml`). Toute la logique métier de chaque tâche est portée par
`edumatch.orchestration.taches` et `edumatch.orchestration.reprise`,
testables sans Airflow ; ce fichier ne fait que les assembler en graphe —
aucune règle n'est réimplémentée ici.

Quatre DAG distincts, un par cadence réelle de source (`orchestration.planification`
dans `configs/base.yaml`), plutôt qu'un DAG unique cadencé sur la source la
plus fréquente : Parcoursup publie une campagne par an, Sirene republie son
stock chaque mois, les référentiels (l'export RNCP surtout) chaque jour. Un
DAG unique quotidien aurait retéléchargé Parcoursup et Sirene à chaque
exécution — sans casser l'idempotence (l'ingestion ignore un fichier déjà
intact), mais en réexécutant `make quality` et en consommant un créneau
d'ordonnancement pour rien 29 jours sur 30 pour Sirene, 364 sur 365 pour
Parcoursup.

Chaque tâche appelle `executer_avec_reprise` : la reprise (retenter une
erreur transitoire, alerter sur une erreur définitive) est décidée par ce
code Python, pas par le mécanisme de retry natif d'Airflow — `retries=0` est
donc posé explicitement dans `ARGUMENTS_PAR_DEFAUT` ci-dessous. Le retry natif
d'Airflow retenterait aveuglément n'importe quelle exception, y compris un
schéma cassé ou un contrôle qualité bloquant ; le vocabulaire commun
`ErreurTransitoire` / `ErreurDefinitive` (`edumatch.ingestion._flux`) est
justement là pour empêcher cette confusion.

Un échec de `controler_qualite` est une `ErreurQualiteBloquante`, rangée du
côté définitif (`quality/_diagnostic.py`) : la tâche échoue sans reprise, et
Airflow n'exécute alors aucune tâche placée après elle dans le graphe
(`trigger_rule` par défaut de chaque opérateur : `all_success`) — c'est ce
mécanisme, natif à Airflow, qui réalise le blocage qualité au niveau du DAG,
sans code supplémentaire ici.
"""

from __future__ import annotations

from datetime import datetime, timezone

from airflow import DAG
from airflow.operators.python import PythonOperator

from edumatch.config import Settings, get_settings
from edumatch.orchestration import taches
from edumatch.orchestration.reprise import executer_avec_reprise, politique_depuis_settings

# Date de départ commune aux quatre DAG : antérieure à la mise en service
# réelle, sans conséquence puisque `catchup=False` sur chacun (voir plus bas)
# — aucun rattrapage rétroactif n'est déclenché à l'activation.
DATE_DEPART = datetime(2026, 1, 1, tzinfo=timezone.utc)

ARGUMENTS_PAR_DEFAUT = {
    "owner": "edumatch",
    # La reprise transitoire/définitive est décidée dans le code de la
    # tâche (voir le docstring du module) : le retry natif d'Airflow est
    # explicitement désactivé plutôt que laissé à sa valeur par défaut.
    "retries": 0,
}

_SETTINGS = get_settings()
_PLANIFICATION = _SETTINGS.orchestration.planification


def _construire_operateur(dag: DAG, id_tache: str, fonction) -> PythonOperator:
    """Enveloppe une fonction de `taches.py` dans `executer_avec_reprise`.

    La politique de reprise est relue depuis la configuration à l'exécution
    de la tâche (pas à l'import de ce module) : `get_settings()` est mis en
    cache pour le processus, donc ce n'est pas un coût par tâche, et cela
    garantit qu'un `airflow tasks test` reflète toujours la configuration
    active plutôt qu'une valeur figée à l'analyse du DAG.
    """

    def _executer_la_tache() -> None:
        settings: Settings = get_settings()
        politique = politique_depuis_settings(settings)
        executer_avec_reprise(
            lambda: fonction(settings),
            politique=politique,
            nom_tache=id_tache,
        )

    return PythonOperator(task_id=id_tache, python_callable=_executer_la_tache, dag=dag)


with DAG(
    dag_id="edumatch_parcoursup",
    description="Ingestion, qualité, étoile et variables Parcoursup (E05, E14-E16, E20).",
    schedule=_PLANIFICATION.parcoursup,
    start_date=DATE_DEPART,
    catchup=False,
    default_args=ARGUMENTS_PAR_DEFAUT,
    tags=["edumatch", "parcoursup"],
) as dag_parcoursup:
    t_ingestion = _construire_operateur(
        dag_parcoursup, "ingerer_parcoursup", taches.ingerer_parcoursup
    )
    t_qualite = _construire_operateur(dag_parcoursup, "controler_qualite", taches.controler_qualite)
    t_silver = _construire_operateur(
        dag_parcoursup, "transformer_silver", taches.transformer_silver
    )
    t_gold = _construire_operateur(dag_parcoursup, "construire_gold", taches.construire_gold)
    t_variables = _construire_operateur(
        dag_parcoursup, "construire_variables", taches.construire_variables
    )
    t_ingestion >> t_qualite >> t_silver >> t_gold >> t_variables


with DAG(
    dag_id="edumatch_sirene",
    description="Ingestion et agrégat commune x NAF de Sirene (E06, E14, E17).",
    schedule=_PLANIFICATION.sirene,
    start_date=DATE_DEPART,
    catchup=False,
    default_args=ARGUMENTS_PAR_DEFAUT,
    tags=["edumatch", "sirene"],
) as dag_sirene:
    t_ingestion = _construire_operateur(dag_sirene, "ingerer_sirene", taches.ingerer_sirene)
    t_qualite = _construire_operateur(dag_sirene, "controler_qualite", taches.controler_qualite)
    t_agregats = _construire_operateur(dag_sirene, "agreger_sirene", taches.agreger_sirene)
    t_ingestion >> t_qualite >> t_agregats


with DAG(
    dag_id="edumatch_referentiels",
    description=(
        "Ingestion des référentiels ONISEP/RNCP/France Travail et réconciliation "
        "NAF -> ROME -> formation (E07, E14, E18)."
    ),
    schedule=_PLANIFICATION.referentiels,
    start_date=DATE_DEPART,
    catchup=False,
    default_args=ARGUMENTS_PAR_DEFAUT,
    tags=["edumatch", "referentiels"],
) as dag_referentiels:
    t_ingestion = _construire_operateur(
        dag_referentiels, "ingerer_referentiels", taches.ingerer_referentiels
    )
    t_qualite = _construire_operateur(
        dag_referentiels, "controler_qualite", taches.controler_qualite
    )
    t_naf_rome = _construire_operateur(
        dag_referentiels, "reconcilier_naf_rome", taches.reconcilier_naf_rome
    )
    t_ingestion >> t_qualite >> t_naf_rome


with DAG(
    dag_id="edumatch_audit_purge",
    description="Purge planifiée du journal d'inférence, article 12 du règlement sur l'IA (E30).",
    schedule=_PLANIFICATION.purge_audit,
    start_date=DATE_DEPART,
    catchup=False,
    default_args=ARGUMENTS_PAR_DEFAUT,
    tags=["edumatch", "gouvernance"],
) as dag_audit_purge:
    t_purge = _construire_operateur(dag_audit_purge, "purger_audit", taches.purger_audit)
