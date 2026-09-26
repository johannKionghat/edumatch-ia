"""Le script d'initialisation de la base Airflow : aucune variable psql dans un bloc entre dollars.

`psql` ne substitue pas ses variables (`:'nom'`) à l'intérieur d'une chaîne entre dollars. La
création du rôle était écrite dans un tel bloc : il partait tel quel vers PostgreSQL, qui
répondait « syntax error at or near ":" ». Le rôle applicatif n'était donc pas créé, et
l'initialisation d'Airflow échouait ensuite sur une authentification refusée. Constaté le
26 septembre 2026, à la première mise en service réelle de la pile de production.

Les commentaires SQL sont retirés avant analyse : ils citent le défaut en exemple, et cet
exemple ne doit pas être confondu avec du code exécutable.
"""

from __future__ import annotations

import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "docker" / "postgres" / "init-airflow.sql"
CODE = re.sub(r"^\s*--.*$", "", SCRIPT.read_text(encoding="utf-8"), flags=re.M)


def test_aucune_variable_psql_dans_un_bloc_entre_dollars() -> None:
    blocs = re.findall(r"\$[A-Za-z_]*\$.*?\$[A-Za-z_]*\$", CODE, flags=re.DOTALL)
    for bloc in blocs:
        assert ":'" not in bloc and ':"' not in bloc, (
            "variable psql jamais substituée dans un bloc entre dollars"
        )


def test_le_role_est_cree_par_gexec_et_reste_conditionnel() -> None:
    creation = re.search(r"SELECT format\('CREATE ROLE.*?gexec", CODE, flags=re.DOTALL)
    assert creation, "la création du rôle doit être un SELECT format(...) suivi de gexec"
    assert "WHERE NOT EXISTS" in creation.group(0), "la création doit rester conditionnelle"


def test_les_identifiants_viennent_de_l_environnement() -> None:
    assert CODE.count("getenv") >= 3
    for variable in ("AIRFLOW_DB_USER", "AIRFLOW_DB_PASSWORD", "AIRFLOW_DB_NAME"):
        assert variable in CODE, f"{variable} doit être lue de l'environnement"


def test_aucun_mot_de_passe_en_dur() -> None:
    assert "PASSWORD '" not in CODE, "le mot de passe ne vient que de l'environnement"
