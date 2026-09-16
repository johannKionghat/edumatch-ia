"""Configuration commune à toute la suite de tests."""

import os

import pytest

from edumatch.config import get_settings


def pytest_configure(config: pytest.Config) -> None:
    """Retire EDUMATCH_ENV avant toute fixture, y compris de portée module.

    Les tests ne doivent pas dépendre de l'environnement du poste ou de la CI.
    """
    os.environ.pop("EDUMATCH_ENV", None)


@pytest.fixture(autouse=True)
def environnement_isole(monkeypatch: pytest.MonkeyPatch):
    """Repart d'une configuration propre à chaque test.

    Un test qui a besoin d'un environnement précis le fixe lui-même.
    """
    monkeypatch.delenv("EDUMATCH_ENV", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
