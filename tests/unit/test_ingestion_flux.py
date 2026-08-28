"""Tests des primitives partagées d'ingestion (src/edumatch/ingestion/_flux.py).

Ces primitives sont déjà exercées indirectement par les tests du connecteur
Parcoursup. Ce fichier vérifie leur comportement en isolation, puisqu'elles
seront réutilisées telles quelles par les connecteurs Sirene et référentiels :
un test ici couvre ces futurs appelants sans attendre qu'ils existent.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import requests

from edumatch.ingestion._flux import (
    ecriture_atomique,
    empreinte_sha256,
    fichier_intact,
    session_http,
)


# ─── Écriture atomique ────────────────────────────────────────────────────────


def test_ecriture_atomique_renomme_le_fichier_temporaire_a_la_reussite(tmp_path: Path) -> None:
    chemin = tmp_path / "sous_dossier" / "fichier.txt"

    with ecriture_atomique(chemin, mode="w") as flux:
        flux.write("contenu")

    assert chemin.read_text(encoding="utf-8") == "contenu"
    assert not chemin.with_suffix(chemin.suffix + ".part").exists()


def test_ecriture_atomique_ne_laisse_aucun_fichier_apres_une_exception(tmp_path: Path) -> None:
    chemin = tmp_path / "fichier.txt"

    with pytest.raises(ValueError):
        with ecriture_atomique(chemin, mode="w") as flux:
            flux.write("partiel")
            raise ValueError("panne simulée en cours d'écriture")

    assert not chemin.exists()
    assert not chemin.with_suffix(chemin.suffix + ".part").exists()


# ─── Session HTTP ─────────────────────────────────────────────────────────────


class _SessionFermable:
    """Remplace `requests.Session` : ne teste que le contrat qui nous intéresse, la fermeture."""

    def __init__(self) -> None:
        self.fermetures = 0

    def close(self) -> None:
        self.fermetures += 1


def test_session_http_ferme_une_session_creee_localement(monkeypatch: pytest.MonkeyPatch) -> None:
    session_creee = _SessionFermable()
    monkeypatch.setattr(requests, "Session", lambda: session_creee)

    with session_http(None) as session:
        assert session is session_creee
        assert session_creee.fermetures == 0

    assert session_creee.fermetures == 1


def test_session_http_ne_ferme_pas_une_session_fournie() -> None:
    session_fournie = _SessionFermable()

    with session_http(session_fournie) as session:  # type: ignore[arg-type]
        assert session is session_fournie

    assert session_fournie.fermetures == 0


# ─── Empreinte et intégrité ─────────────────────────────────────────────────────


def test_empreinte_sha256_correspond_au_calcul_de_reference(tmp_path: Path) -> None:
    chemin = tmp_path / "fichier.bin"
    contenu = b"contenu de test pour l'empreinte"
    chemin.write_bytes(contenu)

    assert empreinte_sha256(chemin) == hashlib.sha256(contenu).hexdigest()


def test_fichier_intact_faux_si_fichier_absent(tmp_path: Path) -> None:
    assert fichier_intact(tmp_path / "absent.txt", {"empreinte_sha256": "peu importe"}) is False


def test_fichier_intact_faux_sans_entree_de_manifeste(tmp_path: Path) -> None:
    chemin = tmp_path / "fichier.txt"
    chemin.write_text("contenu", encoding="utf-8")

    assert fichier_intact(chemin, None) is False


def test_fichier_intact_vrai_si_empreinte_correspond(tmp_path: Path) -> None:
    chemin = tmp_path / "fichier.txt"
    chemin.write_text("contenu", encoding="utf-8")
    entree = {"empreinte_sha256": empreinte_sha256(chemin)}

    assert fichier_intact(chemin, entree) is True
