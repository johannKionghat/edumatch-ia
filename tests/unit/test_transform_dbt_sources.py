"""Contrat entre la liste des millésimes et ses trois copies.

`configs/base.yaml` (`donnees.parcoursup.millesimes`) est la référence
unique en Python. dbt ne permet pas de déclarer des sources ni des appels
`dbt.source()` depuis une boucle sur une valeur externe (voir le docstring
de `dbt/models/silver/stg_parcoursup.py`) : la liste est donc recopiée deux
fois, dans `_sources.yml` et dans les appels littéraux du modèle Python. Ce
test échoue si l'une des trois s'écarte des deux autres — sur le même
principe que `tests/data/test_variables_reference.py` pour l'ADR 0013.
"""

from __future__ import annotations

import re

import yaml

from edumatch.config import PROJECT_ROOT, load_settings

DOSSIER_DBT = PROJECT_ROOT / "src" / "edumatch" / "transform" / "dbt"


def _millesimes_configures() -> list[int]:
    return load_settings("prod").donnees.parcoursup.millesimes


def _millesimes_sources_yml() -> list[int]:
    contenu = (DOSSIER_DBT / "models" / "bronze" / "_sources.yml").read_text(encoding="utf-8")
    document = yaml.safe_load(contenu)
    tables = document["sources"][0]["tables"]
    return sorted(int(table["name"].removeprefix("parcoursup_")) for table in tables)


def _millesimes_modele_python() -> list[int]:
    chemin = DOSSIER_DBT / "models" / "silver" / "stg_parcoursup.py"
    contenu = chemin.read_text(encoding="utf-8")
    appels = re.findall(r'dbt\.source\("bronze_parcoursup", "parcoursup_(\d{4})"\)', contenu)
    return sorted(int(annee) for annee in appels)


def test_sources_yml_couvre_exactement_les_millesimes_configures() -> None:
    assert _millesimes_sources_yml() == sorted(_millesimes_configures())


def test_modele_python_couvre_exactement_les_millesimes_configures() -> None:
    assert _millesimes_modele_python() == sorted(_millesimes_configures())
