"""Liste des départements de l'écran conseiller : route `/departements` et artefact des libellés.

La liste doit être exactement l'ensemble des codes présents dans le catalogue de la session
courante : ni un département sans formation, ni un département oublié.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from edumatch.api.deps import get_etat_matching
from edumatch.api.main import create_app
from edumatch.api.state import EtatMatching, _artefacts_debouches_indisponibles
from edumatch.matching import departements as dep
from tests.unit.test_api_matching import (  # _authentification réexportée comme fixture
    IDENTIFIANT_TEST,
    MOT_DE_PASSE_TEST,
    _authentification,  # noqa: F401
    _en_tete_basic,
)

# Comptes conseillers configurés pour tout le module (fixture de test_api_matching).
pytestmark = pytest.mark.usefixtures("_authentification")

CODES_CATALOGUE = ["75", "2A", "01", "974", "99", "75", "13", "2B", "20"]


def _etat(libelles: dict[str, str]) -> EtatMatching:
    catalogue = pd.DataFrame(
        {"dep": CODES_CATALOGUE, "cod_aff_form": [f"F{i}" for i in range(len(CODES_CATALOGUE))]}
    )
    return EtatMatching(
        settings=None,
        session_courante=2025,
        catalogue=catalogue,
        artefacts_debouches=_artefacts_debouches_indisponibles(),
        debouches_disponible=False,
        motif_indisponibilite_debouches="sans objet",
        libelles_departements=libelles,
    )


def _client(etat: EtatMatching, avec_identifiants: bool = True) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_etat_matching] = lambda: etat
    en_tetes = _en_tete_basic(IDENTIFIANT_TEST, MOT_DE_PASSE_TEST) if avec_identifiants else {}
    return TestClient(app, headers=en_tetes)


LIBELLES = {
    "75": "Paris",
    "2A": "Corse-du-Sud",
    "2B": "Haute-Corse",
    "01": "Ain",
    "974": "La Réunion",
    "99": "Etranger",
    "13": "Bouches-du-Rhône",
}


def test_liste_egale_aux_valeurs_distinctes_du_catalogue() -> None:
    corps = _client(_etat(LIBELLES)).get("/departements").json()
    codes = [d["code"] for d in corps["departements"]]
    assert set(codes) == set(CODES_CATALOGUE)
    assert len(codes) == len(set(CODES_CATALOGUE))  # chaque code une seule fois
    assert corps["session"] == 2025


def test_ordre_administratif_corse_puis_outre_mer_puis_etranger() -> None:
    corps = _client(_etat(LIBELLES)).get("/departements").json()
    assert [d["code"] for d in corps["departements"]] == [
        "01",
        "13",
        "20",
        "2A",
        "2B",
        "75",
        "974",
        "99",
    ]


def test_libelle_present_ou_null_jamais_invente() -> None:
    corps = _client(_etat(LIBELLES)).get("/departements").json()
    par_code = {d["code"]: d["libelle"] for d in corps["departements"]}
    assert corps["libelles_disponibles"] is True
    assert par_code["75"] == "Paris"
    assert par_code["20"] is None  # code du catalogue sans libellé dans la source : laissé vide


def test_sans_artefact_les_codes_seuls_et_le_drapeau() -> None:
    corps = _client(_etat({})).get("/departements").json()
    assert corps["libelles_disponibles"] is False
    assert all(d["libelle"] is None for d in corps["departements"])
    assert len(corps["departements"]) == len(set(CODES_CATALOGUE))


def test_route_authentifiee_comme_lecran() -> None:
    assert _client(_etat(LIBELLES), avec_identifiants=False).get("/departements").status_code == 401


def test_chaque_code_propose_est_accepte_par_matching() -> None:
    """Toute valeur du menu doit passer la validation de `ProfilRequete.departement`."""
    from edumatch.api.schemas import ProfilRequete

    for code in dep.trier_codes(CODES_CATALOGUE):
        ProfilRequete(type_bac="bg", boursier=False, departement=code)


# ─── Artefact des libellés ───────────────────────────────────────────────────


def _silver() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "session": [2021, 2021, 2025, 2025, 2025],
            "dep": ["09", "08", "09", "08", "09"],
            "dep_lib": ["Ardennes", "Ardennes", "Ariège", "Ardennes", "Ariège"],
        }
    )


def test_libelles_pris_dans_la_seule_session_courante() -> None:
    """Le fichier source de 2021 libelle le 09 « Ardennes » : la session courante l'ignore."""
    libelles = dep.extraire_libelles(_silver(), 2025)
    assert dict(zip(libelles["dep"], libelles["dep_lib"], strict=True)) == {
        "08": "Ardennes",
        "09": "Ariège",
    }
    assert set(libelles["session"]) == {2025}


def test_deux_libelles_pour_un_code_arretent_lextraction() -> None:
    silver = pd.concat(
        [_silver(), pd.DataFrame({"session": [2025], "dep": ["09"], "dep_lib": ["Ariege"]})]
    )
    with pytest.raises(dep.ErreurLibellesDepartements, match="09"):
        dep.extraire_libelles(silver, 2025)


def test_artefact_dune_autre_session_ignore(tmp_path: Path) -> None:
    settings = SimpleNamespace(processed_dir=tmp_path)
    chemin = dep.chemin_libelles(settings)
    chemin.parent.mkdir(parents=True)
    dep.extraire_libelles(_silver(), 2025).to_parquet(chemin, index=False)
    assert dep.charger_libelles(settings, 2025) == {"08": "Ardennes", "09": "Ariège"}
    assert dep.charger_libelles(settings, 2026) == {}


def test_artefact_absent_donne_un_dictionnaire_vide(tmp_path: Path) -> None:
    assert dep.charger_libelles(SimpleNamespace(processed_dir=tmp_path), 2025) == {}


def test_etat_sans_libelles_reste_constructible() -> None:
    """Le champ est optionnel : les fixtures existantes d'`EtatMatching` ne changent pas."""
    champ = {f.name: f for f in dataclasses.fields(EtatMatching)}["libelles_departements"]
    assert champ.default_factory() == {}
