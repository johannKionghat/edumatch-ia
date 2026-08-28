"""Tests de chargement de la configuration (src/edumatch/config.py).

Couvre : chargement nominal des vrais YAML du dépôt, héritage d'un fichier
d'environnement sur base.yaml, précédence des trois couches de surcharge, et
échec explicite quand un fichier est absent, malformé, ou porte une clé
inconnue.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from edumatch.config import ConfigurationError, get_settings, load_settings

from conftest import BASE_YAML

# ─── Chargement nominal ──────────────────────────────────────────────────────


def test_chargement_nominal_environnement_dev_reel() -> None:
    """La vraie configuration du dépôt (configs/dev.yaml) doit se charger sans erreur."""
    settings = load_settings("dev")
    assert settings.env == "dev"
    assert settings.projet.nom == "edumatch-ia"
    # dev.yaml réduit les millésimes à des fins d'itération rapide.
    assert settings.donnees.parcoursup.millesimes == [2024, 2025]


def test_chargement_nominal_prod() -> None:
    settings = load_settings("prod")
    assert settings.execution.moteur_volume == "cluster"
    assert settings.api.autoscaling is not None
    assert settings.api.autoscaling.max == 12


def test_get_settings_est_mis_en_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_settings() ne doit relire les YAML qu'une fois par processus."""
    get_settings.cache_clear()
    monkeypatch.setenv("EDUMATCH_ENV", "dev")
    premier = get_settings()
    second = get_settings()
    assert premier is second
    get_settings.cache_clear()


# ─── Héritage et précédence des trois couches ────────────────────────────────


def test_environnement_surcharge_base(configs_dir_isole: Path) -> None:
    """dev.yaml doit l'emporter sur base.yaml pour les clés qu'il redéfinit."""
    settings = load_settings("dev", configs_dir=configs_dir_isole)
    # Surchargé par dev.yaml :
    assert settings.modele.hyperparametres.n_estimators == 5
    # Non surchargé : la valeur de base.yaml doit rester intacte.
    assert settings.modele.hyperparametres.num_leaves == 31


def test_variable_environnement_bat_le_yaml(
    configs_dir_isole: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Une variable d'environnement doit l'emporter sur base.yaml ET sur dev.yaml.

    C'est le cœur de la précédence documentée dans config.py : base <
    environnement < variable d'environnement. On surcharge ici un champ que
    dev.yaml a lui-même déjà surchargé (n_estimators), pour prouver que la
    variable d'environnement gagne même face à la surcharge la plus proche.
    """
    monkeypatch.setenv("EDUMATCH_MODELE__HYPERPARAMETRES__N_ESTIMATORS", "999")
    settings = load_settings("dev", configs_dir=configs_dir_isole)
    assert settings.modele.hyperparametres.n_estimators == 999


# ─── Échec explicite : fichier absent, héritage incorrect, YAML malformé,
#     clé inconnue ────────────────────────────────────────────────────────


def test_environnement_inconnu_leve_configurationerror(configs_dir_isole: Path) -> None:
    with pytest.raises(ConfigurationError, match="invalide"):
        load_settings("preprod", configs_dir=configs_dir_isole)


def test_fichier_environnement_absent_leve_configurationerror(tmp_path: Path) -> None:
    dossier = tmp_path / "configs_incomplet"
    dossier.mkdir()
    (dossier / "base.yaml").write_text(BASE_YAML, encoding="utf-8")
    # dev.yaml volontairement absent.
    with pytest.raises(ConfigurationError, match="introuvable"):
        load_settings("dev", configs_dir=dossier)


def test_herite_de_incorrect_leve_configurationerror(tmp_path: Path) -> None:
    dossier = tmp_path / "configs_mauvais_heritage"
    dossier.mkdir()
    (dossier / "base.yaml").write_text(BASE_YAML, encoding="utf-8")
    (dossier / "dev.yaml").write_text("herite_de: autre.yaml\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="herite_de"):
        load_settings("dev", configs_dir=dossier)


def test_yaml_malforme_leve_configurationerror(tmp_path: Path) -> None:
    """Un YAML syntaxiquement invalide doit être annoncé comme tel, pas laisser fuir un traceback pyyaml.

    `_charger_yaml()` doit envelopper `yaml.YAMLError` dans une
    `ConfigurationError` nommant le fichier fautif, au même titre que les
    autres erreurs de ce module.
    """
    dossier = tmp_path / "configs_yaml_casse"
    dossier.mkdir()
    (dossier / "base.yaml").write_text("projet: [a, b\n", encoding="utf-8")  # séquence non fermée
    (dossier / "dev.yaml").write_text("herite_de: base.yaml\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="malformé"):
        load_settings("dev", configs_dir=dossier)


def test_champ_yaml_inconnu_leve_validationerror(configs_dir_isole: Path) -> None:
    """extra='forbid' doit rejeter une clé YAML non déclarée dans le schéma."""
    contenu = yaml.safe_load(BASE_YAML)
    contenu["projet"]["cle_inconnue"] = "surprise"
    (configs_dir_isole / "base.yaml").write_text(yaml.dump(contenu), encoding="utf-8")
    with pytest.raises(ValidationError, match="cle_inconnue"):
        load_settings("dev", configs_dir=configs_dir_isole)
