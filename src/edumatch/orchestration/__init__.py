"""Logique d'orchestration du pipeline (E33), indépendante d'Airflow.

Ce paquet porte tout ce qui doit rester testable sans installer Airflow :
la politique de reprise (`reprise.py`) et les tâches unitaires (`taches.py`),
qui appellent directement les points d'entrée déjà testés de l'ingestion,
des contrôles qualité, de la transformation et des modules avals.

`pipelines/edumatch_pipeline.py`, à la racine du dépôt, est le seul fichier
qui importe `airflow` : il assemble ces fonctions en graphe. Rien ici n'en
dépend, dans un sens comme dans l'autre.
"""
