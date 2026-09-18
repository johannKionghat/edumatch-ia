"""Structure du graphe Airflow : dépendances entre tâches, un DAG par cadence.

Conditionné à la présence d'Airflow (`pytest.importorskip`) : ce paquet n'est
pas une dépendance du projet par défaut (voir l'extra `airflow` de
`pyproject.toml`) pour ne pas alourdir l'environnement de développement d'une
dépendance lourde dont seul ce test a besoin. Sans lui, ce module est ignoré
et la suite reste verte — la logique métier de chaque tâche, elle, est
vérifiée sans conditionner quoi que ce soit (`tests/unit/test_orchestration_*.py`,
`tests/integration/test_pipeline_enchainement.py`).

Ce que ce test NE prouve PAS : que le DAG s'exécute avec succès dans un vrai
conteneur Airflow planifié (base de métadonnées, workers, connexions). Cela
reste à démontrer sur l'environnement Airflow complet (panne provoquée
filmée) — voir le docstring de `pipelines/edumatch_pipeline.py` sur la
lacune assumée du `docker-compose.yml` actuel (image sans le paquet
`edumatch` installé).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

airflow = pytest.importorskip("airflow", reason="apache-airflow non installé (extra 'airflow')")

PIPELINES_DIR = Path(__file__).resolve().parents[2] / "pipelines"


@pytest.fixture()
def module_pipeline():
    """Importe `pipelines/edumatch_pipeline.py` en module autonome, sans le rendre paquet."""
    sys.path.insert(0, str(PIPELINES_DIR))
    try:
        import edumatch_pipeline  # type: ignore[import-not-found]

        yield edumatch_pipeline
    finally:
        sys.path.remove(str(PIPELINES_DIR))
        sys.modules.pop("edumatch_pipeline", None)


def _ids_taches(dag) -> set[str]:
    return {tache.task_id for tache in dag.tasks}


def test_quatre_dag_sont_definis(module_pipeline) -> None:
    assert module_pipeline.dag_parcoursup.dag_id == "edumatch_parcoursup"
    assert module_pipeline.dag_sirene.dag_id == "edumatch_sirene"
    assert module_pipeline.dag_referentiels.dag_id == "edumatch_referentiels"
    assert module_pipeline.dag_audit_purge.dag_id == "edumatch_audit_purge"


def test_dag_parcoursup_enchaine_les_huit_etapes_dans_l_ordre(module_pipeline) -> None:
    dag = module_pipeline.dag_parcoursup
    assert _ids_taches(dag) == {
        "ingerer_parcoursup",
        "controler_qualite",
        "transformer_silver",
        "construire_gold",
        "construire_variables",
        "detecter_derive",
        "reentrainer_modele",
        "evaluer_modele",
    }
    def aval(id_tache: str) -> list[str]:
        return [t.task_id for t in dag.get_task(id_tache).downstream_list]

    assert aval("ingerer_parcoursup") == ["controler_qualite"]
    assert aval("controler_qualite") == ["transformer_silver"]
    assert aval("transformer_silver") == ["construire_gold"]
    assert aval("construire_gold") == ["construire_variables"]
    assert aval("construire_variables") == ["detecter_derive"]
    assert aval("detecter_derive") == ["reentrainer_modele"]
    assert aval("reentrainer_modele") == ["evaluer_modele"]
    assert dag.get_task("evaluer_modele").downstream_list == []


def test_dag_parcoursup_le_reentrainement_depend_transitivement_du_controle_qualite(
    module_pipeline,
) -> None:
    """Le blocage qualité doit couvrir le réentraînement : `trigger_rule` par défaut
    (`all_success`) empêche `reentrainer_modele` de s'exécuter si `controler_qualite` a
    échoué, sans code supplémentaire ici — c'est ce que ce test vérifie au niveau du
    graphe plutôt que de le supposer."""
    dag = module_pipeline.dag_parcoursup
    amont_reentrainement = {t.task_id for t in dag.get_task("reentrainer_modele").upstream_list}
    # Pas nécessairement direct : c'est la fermeture transitive qui doit inclure la qualité.
    ancetres = set()
    a_visiter = list(amont_reentrainement)
    while a_visiter:
        tache_id = a_visiter.pop()
        if tache_id in ancetres:
            continue
        ancetres.add(tache_id)
        a_visiter.extend(t.task_id for t in dag.get_task(tache_id).upstream_list)
    assert "controler_qualite" in ancetres


def test_dag_sirene_enchaine_ingestion_qualite_agregat(module_pipeline) -> None:
    dag = module_pipeline.dag_sirene
    assert _ids_taches(dag) == {"ingerer_sirene", "controler_qualite", "agreger_sirene"}
    aval = [t.task_id for t in dag.get_task("controler_qualite").downstream_list]
    assert aval == ["agreger_sirene"]


def test_dag_referentiels_enchaine_ingestion_qualite_naf_rome(module_pipeline) -> None:
    dag = module_pipeline.dag_referentiels
    assert _ids_taches(dag) == {"ingerer_referentiels", "controler_qualite", "reconcilier_naf_rome"}


def test_dag_audit_purge_porte_la_purge_d_inference_et_de_supervision(module_pipeline) -> None:
    """Le journal d'inférence (T5) et celui de supervision (T6) sont purgés par deux tâches
    distinctes du même DAG quotidien — voir `taches.purger_audit` et
    `taches.purger_supervision`, dont le contrat (appel réel, `simulation=False`) est
    vérifié indépendamment d'Airflow par `tests/unit/test_orchestration_taches_purge.py`."""
    dag = module_pipeline.dag_audit_purge
    assert _ids_taches(dag) == {"purger_audit", "purger_supervision"}


def test_aucun_dag_ne_retente_au_niveau_airflow(module_pipeline) -> None:
    """`retries=0` explicite sur les quatre DAG : la reprise transitoire/définitive est
    décidée par `orchestration.reprise`, pas par le retry natif d'Airflow (voir le
    docstring du module)."""
    for dag in (
        module_pipeline.dag_parcoursup,
        module_pipeline.dag_sirene,
        module_pipeline.dag_referentiels,
        module_pipeline.dag_audit_purge,
    ):
        for tache in dag.tasks:
            assert tache.retries == 0


def test_planification_reflete_la_configuration(module_pipeline) -> None:
    from edumatch.config import get_settings

    planification = get_settings().orchestration.planification
    assert module_pipeline.dag_parcoursup.schedule_interval == planification.parcoursup
    assert module_pipeline.dag_sirene.schedule_interval == planification.sirene
    assert module_pipeline.dag_referentiels.schedule_interval == planification.referentiels
    assert module_pipeline.dag_audit_purge.schedule_interval == planification.purge_audit


def test_aucun_dag_ne_rattrape_le_passe(module_pipeline) -> None:
    """`catchup=False` : une reprise de service après une longue coupure ne doit pas
    déclencher un rattrapage massif non désiré (voir `rules` d'orchestration, capteur de
    rattrapage à savoir désactiver)."""
    for dag in (
        module_pipeline.dag_parcoursup,
        module_pipeline.dag_sirene,
        module_pipeline.dag_referentiels,
        module_pipeline.dag_audit_purge,
    ):
        assert dag.catchup is False
