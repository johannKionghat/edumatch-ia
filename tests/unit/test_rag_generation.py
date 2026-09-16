"""Tests de la génération optionnelle (src/edumatch/rag/generation.py).

Aucun appel réseau, dans aucun de ces tests : l'absence du paquet
`mistralai` est simulée par `monkeypatch.setitem(sys.modules, ...)`, jamais
supposée de l'environnement d'exécution (l'extra `pip install -e ".[rag]"`
pourrait être installé ou non selon le poste) — c'est le comportement de
dégradation qui est testé, jamais un appel réel au réseau.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import ClassVar

import pytest

from edumatch.config import load_settings
from edumatch.rag.generation import (
    ClientGenerationMistral,
    ErreurGeneration,
    client_generation_depuis_settings,
)


def test_sans_cle_le_client_est_none(configs_dir_isole: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    settings = load_settings("dev", configs_dir=configs_dir_isole)
    assert client_generation_depuis_settings(settings) is None


def test_avec_cle_un_client_mistral_est_construit_sans_appel_reseau(
    configs_dir_isole: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Construire le client ne doit jamais appeler le réseau ni importer `mistralai` : seul
    `.generer()` le fait, voir `ClientGenerationMistral.generer`."""
    monkeypatch.setenv("MISTRAL_API_KEY", "cle-factice-de-test")
    settings = load_settings("dev", configs_dir=configs_dir_isole)
    client = client_generation_depuis_settings(settings)
    assert isinstance(client, ClientGenerationMistral)


def test_generer_sans_le_paquet_mistralai_degrade_explicitement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Paquet absent, simulé de façon déterministe (`sys.modules["mistralai"] = None` force
    `ImportError` sur `from mistralai import ...`, que le paquet soit réellement installé sur
    ce poste ou non) : l'appel doit lever une erreur explicite et actionnable, jamais un
    plantage obscur ni une réponse inventée."""
    monkeypatch.setitem(sys.modules, "mistralai", None)
    client = ClientGenerationMistral(cle_api="cle-factice-de-test", modele="mistral-small-latest")
    with pytest.raises(ErreurGeneration, match="mistralai"):
        client.generer("Quelle formation pour devenir comptable ?", ["un passage de test"])


def _fausse_mistralai(complete) -> types.ModuleType:
    """Construit un faux module `mistralai` en mémoire, avec un client dont `chat.complete`
    est le callable fourni — aucun accès réseau, aucun paquet réel requis."""

    class FauxMistral:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.chat = self

        def complete(self, **kwargs: object) -> object:
            return complete(**kwargs)

    module = types.ModuleType("mistralai")
    module.Mistral = FauxMistral  # type: ignore[attr-defined]
    return module


def test_generer_avec_paquet_present_mais_appel_en_echec_degrade_explicitement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _complete_qui_echoue(**kwargs: object) -> object:
        raise RuntimeError("connexion refusée (simulation locale, aucun appel réseau réel)")

    monkeypatch.setitem(sys.modules, "mistralai", _fausse_mistralai(_complete_qui_echoue))
    client = ClientGenerationMistral(cle_api="cle-factice-de-test", modele="mistral-small-latest")
    with pytest.raises(ErreurGeneration, match="échoué"):
        client.generer("Quelle formation pour devenir comptable ?", ["un passage de test"])


def test_generer_avec_paquet_present_et_reponse_valide_retourne_le_texte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Message:
        content = "Réponse fondée sur l'extrait fourni."

    class Choix:
        message = Message()

    class Reponse:
        choices: ClassVar = [Choix()]

    monkeypatch.setitem(sys.modules, "mistralai", _fausse_mistralai(lambda **_: Reponse()))
    client = ClientGenerationMistral(cle_api="cle-factice-de-test", modele="mistral-small-latest")
    texte = client.generer("Quelle formation pour devenir comptable ?", ["un passage de test"])
    assert texte == "Réponse fondée sur l'extrait fourni."
