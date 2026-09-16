"""Fixtures partagées par les tests de src/edumatch/config.py.

Le YAML minimal lui-même vit dans `_config_fixtures.py`, importé sous un nom
non ambigu (voir ce module pour la raison : deux `conftest.py` distincts dans
le dépôt, sans `__init__.py`, ne peuvent pas être distingués par un import
`from conftest import ...` écrit dans un fichier de test).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _config_fixtures import BASE_YAML, DEV_YAML

__all__ = ["BASE_YAML", "DEV_YAML", "configs_dir_isole"]


@pytest.fixture()
def configs_dir_isole(tmp_path: Path) -> Path:
    """Un dossier configs/ jetable, avec base.yaml et dev.yaml minimalistes."""
    dossier = tmp_path / "configs"
    dossier.mkdir()
    (dossier / "base.yaml").write_text(BASE_YAML, encoding="utf-8")
    (dossier / "dev.yaml").write_text(DEV_YAML, encoding="utf-8")
    return dossier
