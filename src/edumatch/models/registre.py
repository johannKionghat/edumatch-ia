"""Enregistrement d'une version au registre de modèles MLflow (critère 4.10, seconde moitié).

## Ce que ce module fait, et ce qu'il ne fait pas

`models/train.py` journalise déjà chaque exécution dans le **suivi
d'expériences** MLflow : paramètres, métriques, artefact modèle. Ce que le
suivi ne fait pas, c'est le **registre de modèles** — un objet distinct, où
une exécution devient une *version nommée*, comparable dans le temps,
retrouvable par un nom stable plutôt que par un identifiant d'exécution.

Ce module comble ce trou : il prend l'exécution d'entraînement retenue par la
configuration courante (`settings.modele.inclure_taux_precedent`) et
l'enregistre comme version du modèle `edumatch-accessibilite`, avec :

- une étiquette (`ETIQUETTE_STATUT`) qui déclare, en clair, que ce modèle
  **ne bat pas le plancher** (`session_precedente_avec_repli`, mesuré à
  couverture égale) sur le test 2025 — MAE pondérée 0,0758 contre 0,0701,
  calibration ECE 0,0371 contre 0,0322 ;
- une description qui reprend ces chiffres, lus depuis l'exécution elle-même
  plutôt que recopiés en dur ;
- le commit Git associé (`tags.commit_git`, déjà posé par `train.py`).

Il **n'attribue aucun alias ni aucun stade de production** : rien ici ne fait
de ce modèle celui qui sert `/matching` (c'est le catalogue précalculé par
`train.exporter_catalogue_predictions`, indépendant du registre, qui joue ce
rôle aujourd'hui — voir `api/state.py`). Promouvoir une version qui perd
contre la règle triviale serait une affirmation chiffrée non vérifiée : le
critère 4.10 demande la traçabilité d'un registre, pas la victoire d'un
modèle qui n'est pas encore prêt.

## Pourquoi chercher l'exécution plutôt que de la recevoir en argument par défaut

`enregistrer_version_modele` accepte un `run_id` explicite pour les tests et
pour rejouer un enregistrement précis, mais son usage normal (`make
register-model`) ne le connaît pas : il retrouve la dernière exécution
`FINISHED` de `models.train` (`tags.etape == "train"`) dont la variante
correspond à la configuration active (`tags.variante`), dans l'expérience
`edumatch-accessibilite`. C'est la même logique de sélection que
`models.evaluate` applique déjà à l'entraînement lui-même (même protocole,
même split) — appliquée ici au choix de l'exécution à enregistrer plutôt qu'à
relancer un calcul.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

from edumatch.config import Settings, get_settings
from edumatch.models.train import NOM_EXPERIENCE_MLFLOW

LOGGER = logging.getLogger(__name__)

# Nom stable du modèle au registre — indépendant du nom de l'exécution
# (`lightgbm-pondere-<variante>`), qui lui peut changer d'une exécution à
# l'autre.
NOM_MODELE_REGISTRE = "edumatch-accessibilite"

ETIQUETTE_STATUT = "statut_evaluation"
ETIQUETTE_COMMIT = "commit_git"
ETIQUETTE_RUN_SOURCE = "run_id_source"

VALEUR_STATUT_NON_RETENU = (
    "ne bat pas le plancher (session precedente a couverture egale) sur le test 2025 : "
    "non retenu pour un usage reel, enregistre pour la tracabilite du registre (critere 4.10)"
)


class ErreurRegistreModele(RuntimeError):
    """Rien à enregistrer : aucune exécution d'entraînement adéquate, ou registre indisponible.

    Définitive au sens de `models.jeux.ErreurJeuxDonnees` : relancer à
    l'identique sans corriger la cause (MLflow non configuré, aucune
    exécution `train` journalisée) donnerait la même erreur.
    """


@dataclass(frozen=True)
class RapportEnregistrement:
    """Ce que `make register-model` a produit, à déclarer tel quel."""

    nom_modele: str
    version: str
    run_id: str
    commit_git: str | None
    test_mae_ponderee: float | None
    baseline_test_mae_ponderee: float | None

    def resume(self) -> str:
        ecart = None
        if self.test_mae_ponderee is not None and self.baseline_test_mae_ponderee is not None:
            ecart = self.test_mae_ponderee - self.baseline_test_mae_ponderee
        lignes = [
            f"Version {self.version} de « {self.nom_modele} » enregistrée depuis l'exécution {self.run_id}.",
            f"  Commit source     : {self.commit_git or 'inconnu'}",
            f"  MAE pondérée test : {self.test_mae_ponderee!r} (modèle) contre "
            f"{self.baseline_test_mae_ponderee!r} (plancher, couverture égale)"
            + (f" — écart {ecart:+.4f}" if ecart is not None else ""),
            "  Aucun alias, aucun stade de production attribué : le modèle ne bat pas le plancher.",
        ]
        return "\n".join(lignes)


def _dernier_run_entrainement(client: mlflow.tracking.MlflowClient, settings: Settings):  # noqa: F821
    """La dernière exécution `FINISHED` de `models.train` pour la variante active de la configuration."""
    experience = client.get_experiment_by_name(NOM_EXPERIENCE_MLFLOW)
    if experience is None:
        raise ErreurRegistreModele(
            f"Aucune expérience « {NOM_EXPERIENCE_MLFLOW} » dans ce magasin MLflow : "
            "exécuter `make train` avant `make register-model`."
        )
    variante = "avec-taux-precedent" if settings.modele.inclure_taux_precedent else "sans-taux-precedent"
    runs = client.search_runs(
        experiment_ids=[experience.experiment_id],
        filter_string=(f"tags.etape = 'train' and tags.variante = '{variante}' and status = 'FINISHED'"),
        order_by=["start_time DESC"],
        max_results=1,
    )
    if not runs:
        raise ErreurRegistreModele(
            f"Aucune exécution `train` terminée pour la variante « {variante} » : exécuter `make train`."
        )
    return runs[0]


def enregistrer_version_modele(
    run_id: str | None = None, settings: Settings | None = None
) -> RapportEnregistrement:
    """Enregistre au registre l'artefact `modele` d'une exécution `models.train`.

    Sans `run_id`, retrouve la dernière exécution qui correspond à la
    configuration active (voir `_dernier_run_entrainement`). Avec un
    `run_id`, enregistre exactement cette exécution — utile pour un test ou
    pour rejouer l'enregistrement d'une exécution précise, jamais pour en
    choisir une au hasard : l'appelant reste responsable de son choix.

    Lève `ErreurRegistreModele` si le suivi n'est pas configuré, si le
    paquet MLflow est absent, ou si aucune exécution adéquate n'existe —
    jamais de repli silencieux sur un enregistrement partiel.
    """
    settings = settings or get_settings()
    if not settings.mlflow_tracking_uri:
        raise ErreurRegistreModele(
            "MLFLOW_TRACKING_URI non configuré : rien à enregistrer (voir .env.example)."
        )
    try:
        import mlflow
        from mlflow.tracking import MlflowClient
    except ImportError as erreur:
        raise ErreurRegistreModele("Le paquet mlflow n'est pas installé dans cet environnement.") from erreur

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)

    if run_id is None:
        run = _dernier_run_entrainement(client, settings)
        run_id = run.info.run_id
    else:
        run = client.get_run(run_id)

    commit = run.data.tags.get(ETIQUETTE_COMMIT)
    test_mae = run.data.metrics.get("test_mae_ponderee")
    baseline_test_mae = run.data.metrics.get("baseline_test_mae_ponderee")

    description = (
        "LightGBM pondéré, issu de l'exécution "
        f"{run_id} (commit {commit or 'inconnu'}). "
        f"MAE pondérée sur le test 2025 : {test_mae!r} ; plancher (session précédente, "
        f"repli sur moyenne de groupe, couverture égale) sur le même périmètre : "
        f"{baseline_test_mae!r}. Ce modèle ne bat pas le plancher sur le test : il est "
        "enregistré pour la traçabilité du registre, jamais promu, jamais servi en production."
    )

    version = mlflow.register_model(
        model_uri=f"runs:/{run_id}/modele",
        name=NOM_MODELE_REGISTRE,
        tags={
            ETIQUETTE_COMMIT: commit or "inconnu",
            ETIQUETTE_RUN_SOURCE: run_id,
            ETIQUETTE_STATUT: VALEUR_STATUT_NON_RETENU,
        },
    )
    client.update_model_version(name=NOM_MODELE_REGISTRE, version=version.version, description=description)

    return RapportEnregistrement(
        nom_modele=NOM_MODELE_REGISTRE,
        version=str(version.version),
        run_id=run_id,
        commit_git=commit,
        test_mae_ponderee=test_mae,
        baseline_test_mae_ponderee=baseline_test_mae,
    )


def main() -> int:
    """Point d'entrée de `make register-model`."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rapport = enregistrer_version_modele()
    LOGGER.info("Enregistrement au registre (4.10) terminé.\n%s", rapport.resume())
    return 0


if __name__ == "__main__":
    sys.exit(main())
