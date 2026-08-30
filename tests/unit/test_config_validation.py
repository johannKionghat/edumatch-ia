"""Tests de validation de la configuration (src/edumatch/config.py).

Couvre : resolution et rejet de EDUMATCH_DATA_ROOT, contradiction entre
l'argument explicite de load_settings et la variable EDUMATCH_ENV, typage des
valeurs YAML, anti-fuite du split temporel, et chemins derives.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from edumatch.config import (
    PROJECT_ROOT,
    ConfigurationError,
    load_settings,
)

from _config_fixtures import BASE_YAML

def test_variable_environnement_data_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    chemin_force = tmp_path / "donnees-edumatch"
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(chemin_force))
    settings = load_settings("dev")
    assert settings.data_root == chemin_force


def test_data_root_par_defaut_pointe_vers_data_du_depot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans EDUMATCH_DATA_ROOT, la racine des données est data/ à l'intérieur du dépôt.

    C'est la structure canonique du projet : les données font partie du
    dépôt (ignorées par Git, sauf data/samples/). La variable ne sert qu'à
    surcharger ce défaut là où le dépôt applicatif n'est pas l'endroit où
    vivent les données — déploiement, conteneur, CI.
    """
    monkeypatch.delenv("EDUMATCH_DATA_ROOT", raising=False)
    settings = load_settings("dev")
    assert settings.data_root == PROJECT_ROOT / "data"
    assert settings.data_root.is_absolute()
    assert settings.raw_dir == PROJECT_ROOT / "data" / "raw"
    assert settings.samples_dir == PROJECT_ROOT / "data" / "samples"
def test_data_root_vide_leve_configurationerror(monkeypatch: pytest.MonkeyPatch) -> None:
    """EDUMATCH_DATA_ROOT="" doit être refusée, pas silencieusement résolue en '.'.

    C'est le bloquant signalé en revue qualité : une variable définie mais
    vide n'est pas une variable absente. Sans ce contrôle, `Path("")` vaut
    le répertoire courant, ce qui peut placer les données sous le dépôt.
    """
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", "")
    with pytest.raises(ConfigurationError, match="vide"):
        load_settings("dev")


def test_data_root_blanche_leve_configurationerror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", "   ")
    with pytest.raises(ConfigurationError, match="vide"):
        load_settings("dev")


def test_data_root_relative_leve_configurationerror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", "relatif/chemin")
    with pytest.raises(ConfigurationError, match="relatif"):
        load_settings("dev")


def test_data_root_vide_via_fichier_dotenv_leve_configurationerror(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Le même contrôle doit s'appliquer quand la valeur vide vient d'un fichier .env, pas d'un export shell.

    Régression : `load_settings()` déléguait la validation à un pré-contrôle
    qui ne lisait que `os.environ`, aveugle à un `.env`. Un
    `EDUMATCH_DATA_ROOT=` vide déposé dans `.env` remontait alors une
    `ValidationError` Pydantic brute au lieu de la `ConfigurationError`
    promise par ce module. `load_settings()` est désormais le point unique
    de traduction, quelle que soit la provenance de la valeur.
    """
    monkeypatch.delenv("EDUMATCH_DATA_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("EDUMATCH_DATA_ROOT=" + chr(10), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="EDUMATCH_DATA_ROOT"):
        load_settings("dev")
def test_argument_explicite_contredisant_edumatch_env_leve_configurationerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Régression : l'objet ne doit jamais annoncer un environnement différent de son contenu.

    Avant correction, `EDUMATCH_ENV=dev` + `load_settings("prod")` chargeait
    le YAML de prod mais `Settings.env` valait `dev` (la variable
    d'environnement l'emportait sur le YAML pour ce seul champ) : l'objet
    mentait sur ce qu'il contenait. C'est désormais un échec explicite,
    plutôt qu'une réconciliation silencieuse.
    """
    monkeypatch.setenv("EDUMATCH_ENV", "dev")
    with pytest.raises(ConfigurationError, match="EDUMATCH_ENV"):
        load_settings("prod")


def test_argument_explicite_coherent_avec_edumatch_env_fonctionne(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un argument explicite qui confirme EDUMATCH_ENV n'est pas une contradiction."""
    monkeypatch.setenv("EDUMATCH_ENV", "prod")
    settings = load_settings("prod")
    assert settings.env == "prod"
    assert settings.execution.moteur_volume == "cluster"
def test_type_invalide_leve_validationerror(configs_dir_isole: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un learning_rate hors bornes (]0, 1]) doit être rejeté, avec le champ nommé."""
    monkeypatch.setenv("EDUMATCH_MODELE__HYPERPARAMETRES__LEARNING_RATE", "3.5")
    with pytest.raises(ValidationError) as exc_info:
        load_settings("dev", configs_dir=configs_dir_isole)
    assert "learning_rate" in str(exc_info.value)


def test_split_non_temporel_leve_validationerror(configs_dir_isole: Path) -> None:
    """Un split qui partage un millésime entre deux jeux doit être détecté (anti-fuite)."""
    contenu = yaml.safe_load(BASE_YAML)
    contenu["modele"]["split"]["validation"] = [2021]  # déjà dans "entrainement"
    (configs_dir_isole / "base.yaml").write_text(yaml.dump(contenu), encoding="utf-8")
    with pytest.raises(ValidationError, match="disjoint"):
        load_settings("dev", configs_dir=configs_dir_isole)
def test_chemins_derives_de_data_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(tmp_path))
    settings = load_settings("dev")
    assert settings.raw_dir == tmp_path / "raw"
    assert settings.interim_dir == tmp_path / "interim"
    assert settings.processed_dir == tmp_path / "processed"
    assert settings.external_dir == tmp_path / "external"


def test_samples_dir_reste_dans_le_depot_quelle_que_soit_data_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """data/samples est versionné : il ne doit jamais dépendre de EDUMATCH_DATA_ROOT."""
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(tmp_path))
    settings = load_settings("dev")
    assert settings.samples_dir == PROJECT_ROOT / "data" / "samples"
    assert tmp_path not in settings.samples_dir.parents


def test_colonne_dans_deux_categories_leve_validationerror(configs_dir_isole: Path) -> None:
    """Une colonne à la fois retenue sur la session courante et exclue doit être rejetée.

    C'est la faute qui rouvrirait la fuite : la construction des variables
    lirait sur la session prédite une colonne que la documentation annonce
    écartée.
    """
    contenu = yaml.safe_load(BASE_YAML)
    contenu["modele"]["variables"]["exclues"]["fili"] = "substitut"  # déjà retenue
    (configs_dir_isole / "base.yaml").write_text(yaml.dump(contenu), encoding="utf-8")
    with pytest.raises(ValidationError, match="une seule catégorie"):
        load_settings("dev", configs_dir=configs_dir_isole)


def test_colonne_en_double_dans_une_categorie_leve_validationerror(
    configs_dir_isole: Path,
) -> None:
    """Un doublon dans une liste est une erreur de fusion, pas une redite anodine."""
    contenu = yaml.safe_load(BASE_YAML)
    contenu["modele"]["variables"]["decalees"].append("voe_tot")
    (configs_dir_isole / "base.yaml").write_text(yaml.dump(contenu), encoding="utf-8")
    with pytest.raises(ValidationError, match="doublons"):
        load_settings("dev", configs_dir=configs_dir_isole)


def test_motif_d_exclusion_inconnu_leve_validationerror(configs_dir_isole: Path) -> None:
    """Le motif d'exclusion est contraint : « on verra plus tard » n'est pas un motif."""
    contenu = yaml.safe_load(BASE_YAML)
    contenu["modele"]["variables"]["exclues"]["cod_uai"] = "pas_utile"
    (configs_dir_isole / "base.yaml").write_text(yaml.dump(contenu), encoding="utf-8")
    with pytest.raises(ValidationError, match="cod_uai"):
        load_settings("dev", configs_dir=configs_dir_isole)


def test_le_split_ne_contient_aucune_session_sans_cible(configs_dir_isole: Path) -> None:
    """Le label n'existe qu'à partir de 2020 : 2018 et 2019 ne peuvent pas entraîner.

    Ce test porte sur le vrai `configs/base.yaml`, pas sur le YAML de test :
    c'est la valeur réellement utilisée qui doit être juste. Le millésime
    plancher est écrit en dur ici, et c'est délibéré — un test qui lirait sa
    référence dans le fichier qu'il contrôle ne prouverait rien.
    """
    settings = load_settings("prod")
    millesimes_utilises = (
        settings.modele.split.entrainement
        + settings.modele.split.validation
        + settings.modele.split.test
    )
    sans_cible = sorted(m for m in millesimes_utilises if m < 2020)
    assert not sans_cible, (
        f"Le split déclare la ou les session(s) {sans_cible}, dont le numérateur "
        "du label (prop_tot ventilé par type de baccalauréat) n'existe pas. "
        "Voir adr/0012."
    )
