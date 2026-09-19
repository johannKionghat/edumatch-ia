"""MLflow est-il réellement utilisable dans cet environnement ?

Contexte : le retrait d'une dépendance en conflit a désinstallé en même temps
une dépendance transitive dont MLflow a besoin (`opentelemetry-proto`).
`import mlflow` échouait alors avec `ModuleNotFoundError:
No module named 'opentelemetry.proto'`. La suite de tests existante est restée
verte pendant toute la panne : chaque test qui touche MLflow le fait via un
`try/except ImportError`, ce qui est correct pour ces tests-là (MLflow y est un
à-côté, pas leur objet), mais laisse un trou — personne ne vérifie que MLflow
lui-même fonctionne.

Ce fichier comble ce trou. Deux tests positifs (import, puis aller-retour de
journalisation sur une base SQLite jetable, comme le fait réellement
`models/train.py`), et deux tests qui prouvent que le mécanisme de détection
n'est pas un vœu pieux : ils reproduisent la panne dans un sous-processus
isolé et vérifient qu'elle est bien détectée, avant de vérifier qu'elle ne
l'est plus dans l'environnement courant.

Aucun de ces tests ne touche `mlflow.db` ni `mlruns/` du dépôt : le magasin de
suivi est un fichier SQLite dans `tmp_path`, détruit avec le test.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# ─── 1. Le test qui aurait détecté la panne ──────────────────────────────────


def test_import_mlflow_reussit() -> None:
    """`import mlflow` doit réussir tel quel, sans filet de sécurité.

    C'est exactement l'opération qui échouait pendant la panne. Un test qui
    l'enroberait d'un `try/except ImportError` ne prouverait rien : il faut
    que l'échec fasse échouer CE test, pas qu'il le rende silencieusement
    inopérant.
    """
    import mlflow  # noqa: F401


# ─── 2. Aller-retour minimal, magasin temporaire ─────────────────────────────


def test_aller_retour_experience_parametre_metrique(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Créer une expérience, journaliser un paramètre et une métrique, relire.

    C'est le geste que fait réellement `models/train.py` :
    `set_tracking_uri`, `set_experiment`, `start_run`, `log_params`,
    `log_metric`. Le magasin est une base SQLite jetable, dans `tmp_path` —
    jamais `mlflow.db` ni `mlruns/` du dépôt. C'est aussi le type de magasin
    réel : depuis MLflow 3, le magasin fichier brut (`file:./mlruns`) est en
    maintenance et refuse les nouvelles écritures par défaut ; la production
    de ce projet journalise déjà vers un serveur adossé à une base (voir
    `docker-compose.yml`, service `mlflow`). Le test ne doit rien laisser
    derrière lui et ne doit pas pouvoir interférer avec un autre test exécuté
    en parallèle ou dans un ordre différent.
    """
    import mlflow

    magasin_sqlite = tmp_path / "mlflow_test.db"
    uri_magasin = f"sqlite:///{magasin_sqlite.as_posix()}"

    # `mlflow.set_tracking_uri` n'agit pas seulement en mémoire : il écrit aussi la variable
    # d'environnement MLFLOW_TRACKING_URI. Restaurer l'ancienne adresse par un second appel à
    # `set_tracking_uri` figeait donc dans l'environnement l'adresse par défaut — le magasin
    # `mlruns/` du dépôt — pour tout le reste de la suite : les tests suivants qui lisent la
    # configuration voyaient une adresse MLflow et se mettaient à journaliser. Déclarer la
    # variable par `monkeypatch` la fait supprimer au démontage, quoi que MLflow y ait écrit.
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri_magasin)
    ancienne_uri = mlflow.get_tracking_uri()
    try:
        mlflow.set_tracking_uri(uri_magasin)
        experience_id = mlflow.create_experiment("edumatch-test-disponibilite")
        mlflow.set_experiment(experiment_id=experience_id)

        with mlflow.start_run(run_name="verification-disponibilite") as run:
            mlflow.log_param("nombre_iterations", 42)
            mlflow.log_metric("mae_ponderee", 0.123)
            id_run = run.info.run_id

        client = mlflow.tracking.MlflowClient(tracking_uri=uri_magasin)
        run_relu = client.get_run(id_run)

        assert run_relu.data.params["nombre_iterations"] == "42"
        assert run_relu.data.metrics["mae_ponderee"] == 0.123
        assert run_relu.info.experiment_id == experience_id
    finally:
        mlflow.set_tracking_uri(ancienne_uri)


# ─── 3. Preuve que le mécanisme de détection n'est pas un vœu pieux ──────────

# Reproduit la panne réelle : `opentelemetry.proto` (et ses sous-modules)
# rendu introuvable, exactement comme après la désinstallation transitive
# constatée. La reproduction se fait par un MetaPathFinder qui refuse de
# résoudre le module, dans un sous-processus dédié : on ne touche jamais
# `sys.modules` du processus de test lui-même, qui doit rester utilisable
# pour les tests suivants, quel que soit leur ordre.
_SCRIPT_IMPORT_MLFLOW = "import mlflow\nprint('IMPORT_MLFLOW_OK')\n"

_SCRIPT_BLOQUEUR_OPENTELEMETRY_PROTO = textwrap.dedent(
    """
    import sys
    import importlib.abc
    import importlib.machinery

    class _LoaderBloquant(importlib.abc.Loader):
        def create_module(self, spec):
            raise ModuleNotFoundError(f"No module named '{spec.name}'")

        def exec_module(self, module):  # pragma: no cover - jamais atteint
            pass

    class _FinderBloquant(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name == "opentelemetry.proto" or name.startswith("opentelemetry.proto."):
                return importlib.machinery.ModuleSpec(name, _LoaderBloquant())
            return None

    sys.meta_path.insert(0, _FinderBloquant())
    """
)


def _executer_dans_sous_processus(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_absence_opentelemetry_proto_casse_bien_import_mlflow() -> None:
    """Reproduit la panne du jour : sans `opentelemetry.proto`, `import mlflow` échoue.

    Ce test échouerait si le mécanisme de blocage utilisé par le test suivant
    ne cassait plus rien — c'est-à-dire s'il devenait un faux négatif. Il
    vérifie donc, avant toute chose, que la reproduction de la panne est
    fidèle : le même `ModuleNotFoundError`, sur le même module, que celui
    constaté ce matin.
    """
    resultat = _executer_dans_sous_processus(
        _SCRIPT_BLOQUEUR_OPENTELEMETRY_PROTO + _SCRIPT_IMPORT_MLFLOW
    )

    assert resultat.returncode != 0, (
        "le sous-processus aurait dû échouer à l'import de mlflow : "
        f"stdout={resultat.stdout!r} stderr={resultat.stderr!r}"
    )
    assert "ModuleNotFoundError" in resultat.stderr
    assert "opentelemetry.proto" in resultat.stderr
    assert "IMPORT_MLFLOW_OK" not in resultat.stdout


def test_import_mlflow_reussit_hors_simulation_de_panne() -> None:
    """Contrôle négatif : sans le bloqueur, le même sous-processus réussit.

    Ce test isole la variable : seule la présence du `MetaPathFinder` du test
    précédent distingue un sous-processus qui échoue d'un sous-processus qui
    réussit. Sans ce contrôle, un échec du test précédent pourrait aussi bien
    venir d'un sous-processus mal formé (mauvais interpréteur, `PYTHONPATH`
    incorrect) que de la panne simulée elle-même.
    """
    resultat = _executer_dans_sous_processus(_SCRIPT_IMPORT_MLFLOW)

    assert resultat.returncode == 0, (
        f"stdout={resultat.stdout!r} stderr={resultat.stderr!r}"
    )
    assert "IMPORT_MLFLOW_OK" in resultat.stdout
