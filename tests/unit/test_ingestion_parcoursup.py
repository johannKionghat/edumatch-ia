"""Tests du connecteur Parcoursup (src/edumatch/ingestion/parcoursup.py).

Aucun accès réseau : la couche HTTP est remplacée par une session factice
injectée via le paramètre `session`, déjà prévu dans la signature des
fonctions testées. Couvre : téléchargement nominal et manifeste de
traçabilité, idempotence, forçage, écriture atomique face à une interruption,
détection d'un fichier corrompu, et absence de valeur en dur.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

from edumatch.config import load_settings
from edumatch.ingestion._flux import ErreurDefinitive, ErreurTransitoire
from edumatch.ingestion.parcoursup import (
    ErreurConfigurationParcoursup,
    ErreurReseauParcoursup,
    ErreurTelechargementParcoursup,
    telecharger_millesime,
    telecharger_tous,
)

CONTENU_CSV = b"cod_uai;fili;capa_fin\n0751234A;BTS;30\n"


class _ReponseFactice:
    """Reproduit l'interface de `requests.Response` utile ici : contexte, statut, flux."""

    def __init__(self, blocs: list[bytes], erreur_en_cours_de_flux: Exception | None = None) -> None:
        self._blocs = blocs
        self._erreur = erreur_en_cours_de_flux

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):  # noqa: ARG002 - signature imposée par requests
        for bloc in self._blocs:
            yield bloc
        if self._erreur is not None:
            raise self._erreur

    def __enter__(self) -> "_ReponseFactice":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


class SessionFactice:
    """Remplace `requests.Session` : compte les appels, sert un contenu fixe ou une panne."""

    def __init__(
        self,
        contenu: bytes = CONTENU_CSV,
        erreur_en_cours_de_flux: Exception | None = None,
    ) -> None:
        self.contenu = contenu
        self.erreur_en_cours_de_flux = erreur_en_cours_de_flux
        self.appels = 0

    def get(self, url: str, stream: bool = True, timeout: float | None = None) -> _ReponseFactice:  # noqa: ARG002
        self.appels += 1
        return _ReponseFactice([self.contenu], self.erreur_en_cours_de_flux)


@pytest.fixture()
def settings_test(configs_dir_isole: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Configuration résolue, données brutes isolées sous tmp_path.

    Réutilise `configs_dir_isole` (déjà défini pour les tests de config) :
    trois millésimes 2020-2022 avec leurs identifiants factices.
    """
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(tmp_path / "data"))
    return load_settings("dev", configs_dir=configs_dir_isole)


# ─── Téléchargement nominal et manifeste de traçabilité ──────────────────────


def test_telecharge_ecrit_le_fichier_et_le_manifeste(settings_test) -> None:
    session = SessionFactice()
    resultat = telecharger_millesime(2020, settings=settings_test, session=session)

    assert resultat.telecharge is True
    assert resultat.chemin.exists()
    assert resultat.chemin.read_bytes() == CONTENU_CSV
    assert session.appels == 1

    manifeste = json.loads((settings_test.raw_dir / "parcoursup" / "manifeste.json").read_text())
    entree = manifeste["2020"]
    assert entree["identifiant"] == "fr-esr-parcoursup_2020"
    assert entree["url"] == (
        "https://exemple.test/datasets/fr-esr-parcoursup_2020/exports/csv?delimiter=%3B"
    )
    assert entree["taille_octets"] == len(CONTENU_CSV)
    assert entree["empreinte_sha256"] == resultat.empreinte_sha256
    assert "date_telechargement" in entree


def test_millesime_non_configure_leve_une_erreur_explicite(settings_test) -> None:
    with pytest.raises(ErreurTelechargementParcoursup, match="1999"):
        telecharger_millesime(1999, settings=settings_test, session=SessionFactice())


# ─── Idempotence ──────────────────────────────────────────────────────────────


def test_second_appel_ne_retelecharge_pas(settings_test) -> None:
    session = SessionFactice()
    telecharger_millesime(2020, settings=settings_test, session=session)
    resultat_second = telecharger_millesime(2020, settings=settings_test, session=session)

    assert session.appels == 1, "le second appel n'aurait pas dû déclencher de requête HTTP"
    assert resultat_second.telecharge is False
    assert resultat_second.empreinte_sha256


def test_forcer_retelecharge_meme_si_le_fichier_est_intact(settings_test) -> None:
    session = SessionFactice()
    telecharger_millesime(2020, settings=settings_test, session=session)
    telecharger_millesime(2020, settings=settings_test, session=session, forcer=True)

    assert session.appels == 2


def test_fichier_corrompu_est_retelecharge(settings_test) -> None:
    """Un fichier présent mais dont l'empreinte diverge du manifeste n'est pas considéré intact.

    Simule une corruption après coup (disque défaillant, écriture externe) :
    l'idempotence doit s'appuyer sur l'empreinte, pas seulement la présence
    du fichier.
    """
    session = SessionFactice()
    resultat = telecharger_millesime(2020, settings=settings_test, session=session)
    resultat.chemin.write_bytes(b"contenu corrompu, ne correspond plus au manifeste")

    telecharger_millesime(2020, settings=settings_test, session=session)

    assert session.appels == 2, "un fichier corrompu doit être retéléchargé"
    assert resultat.chemin.read_bytes() == CONTENU_CSV


# ─── Écriture atomique ────────────────────────────────────────────────────────


def test_interruption_ne_laisse_aucun_fichier_final_utilisable(settings_test) -> None:
    """Une coupure réseau en cours de flux ne doit laisser ni fichier final, ni fichier `.part`.

    C'est la garantie qui protège l'immuabilité de `data/raw/` : un
    consommateur qui liste ce dossier ne doit jamais y trouver un fichier
    tronqué qu'il croirait complet.
    """
    session = SessionFactice(erreur_en_cours_de_flux=requests.exceptions.ConnectionError("coupure"))

    with pytest.raises(ErreurTelechargementParcoursup):
        telecharger_millesime(2020, settings=settings_test, session=session)

    dossier = settings_test.raw_dir / "parcoursup"
    fichiers_presents = list(dossier.glob("parcoursup_2020*"))
    assert fichiers_presents == [], f"fichier(s) résiduel(s) après interruption : {fichiers_presents}"


# ─── Réponse HTTP en erreur ───────────────────────────────────────────────────


class _ReponseErreurHttp:
    """Simule une réponse HTTP en échec (404, 500…) : l'erreur survient dès
    `raise_for_status`, avant toute lecture de flux — donc avant même que
    `_telecharger_en_flux` n'ouvre le fichier `.part` en écriture.
    """

    def raise_for_status(self) -> None:
        raise requests.exceptions.HTTPError("404 Client Error: Not Found")

    def iter_content(self, chunk_size: int):  # noqa: ARG002 - signature imposée par requests
        yield b""  # jamais atteint : raise_for_status lève avant

    def __enter__(self) -> "_ReponseErreurHttp":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


class SessionErreurHttp:
    """Session factice dont chaque appel renvoie une réponse en erreur HTTP."""

    def get(self, url: str, stream: bool = True, timeout: float | None = None) -> _ReponseErreurHttp:  # noqa: ARG002
        return _ReponseErreurHttp()


def test_erreur_http_leve_une_erreur_explicite_et_ne_laisse_aucun_fichier(settings_test) -> None:
    """Un 404/500 (levé par `raise_for_status`, avant toute écriture) est traduit
    en erreur explicite du module, sans fichier résiduel ni `.part`.

    Distinct du test de coupure en cours de flux : ici l'échec survient avant
    l'ouverture du fichier de destination, pas pendant l'écriture.
    """
    with pytest.raises(ErreurTelechargementParcoursup, match="2020"):
        telecharger_millesime(2020, settings=settings_test, session=SessionErreurHttp())

    dossier = settings_test.raw_dir / "parcoursup"
    fichiers_presents = list(dossier.glob("parcoursup_2020*")) if dossier.exists() else []
    assert fichiers_presents == [], f"fichier(s) résiduel(s) après erreur HTTP : {fichiers_presents}"


# ─── Manifeste corrompu ────────────────────────────────────────────────────────


def test_manifeste_illisible_est_ignore_et_reconstruit(settings_test) -> None:
    """Un manifeste présent mais dont le contenu n'est pas du JSON valide ne doit
    jamais faire échouer le module, ni faire croire à tort qu'un fichier est
    intact : il est traité comme absent, et reconstruit au prochain
    téléchargement.
    """
    session = SessionFactice()
    resultat = telecharger_millesime(2020, settings=settings_test, session=session)
    chemin_manifeste = settings_test.raw_dir / "parcoursup" / "manifeste.json"
    chemin_manifeste.write_text("{ceci n'est pas du json valide", encoding="utf-8")

    resultat_second = telecharger_millesime(2020, settings=settings_test, session=session)

    assert session.appels == 2, "un manifeste illisible doit être traité comme une absence de preuve"
    assert resultat_second.telecharge is True
    manifeste_reconstruit = json.loads(chemin_manifeste.read_text(encoding="utf-8"))
    assert "2020" in manifeste_reconstruit
    assert resultat.chemin.exists()


def test_manifeste_corrompu_est_mis_en_quarantaine_et_signale(settings_test, caplog) -> None:
    """La perte de traçabilité d'un manifeste corrompu ne doit jamais être silencieuse.

    Le manifeste est un cache reconstructible : sa corruption ne bloque pas la
    chaîne (l'empreinte SHA-256 garantit l'intégrité réelle des CSV, pas le
    manifeste). Mais quand il portait la trace de plusieurs millésimes déjà
    téléchargés, cette trace disparaît de l'index actif — ce test prouve que
    la disparition est journalisée au niveau ERREUR et que le fichier fautif
    est conservé sous un nom distinct, pas silencieusement écrasé.
    """
    session = SessionFactice()
    telecharger_millesime(2020, settings=settings_test, session=session)
    telecharger_millesime(2021, settings=settings_test, session=session)
    dossier = settings_test.raw_dir / "parcoursup"
    chemin_manifeste = dossier / "manifeste.json"
    contenu_avant_corruption = chemin_manifeste.read_text(encoding="utf-8")
    assert '"2020"' in contenu_avant_corruption and '"2021"' in contenu_avant_corruption

    contenu_corrompu = "{ceci n'est pas du json valide, manifeste illisible"
    chemin_manifeste.write_text(contenu_corrompu, encoding="utf-8")

    with caplog.at_level("ERROR"):
        telecharger_millesime(2022, settings=settings_test, session=session)

    # La perte est visible dans les journaux, pas seulement dans un
    # comportement observable indirectement.
    assert any(
        enregistrement.levelname == "ERROR" and "illisible" in enregistrement.message
        for enregistrement in caplog.records
    ), "la corruption du manifeste doit être journalisée au niveau ERREUR"

    # Le fichier fautif est conservé, pas écrasé : un opérateur peut le
    # retrouver et tenter d'en récupérer manuellement les entrées perdues.
    fichiers_quarantaine = list(dossier.glob("manifeste.json.corrompu-*"))
    assert len(fichiers_quarantaine) == 1, "le manifeste corrompu doit être mis en quarantaine une fois"
    assert fichiers_quarantaine[0].read_text(encoding="utf-8") == contenu_corrompu

    # Un nouveau manifeste, sain, est reconstruit à l'emplacement habituel.
    nouveau_manifeste = json.loads(chemin_manifeste.read_text(encoding="utf-8"))
    assert "2022" in nouveau_manifeste


# ─── Plusieurs millésimes ─────────────────────────────────────────────────────


def test_telecharger_tous_traite_chaque_millesime_configure(settings_test) -> None:
    session = SessionFactice()
    resultats = telecharger_tous(settings=settings_test, session=session)

    assert [r.millesime for r in resultats] == [2020, 2021, 2022]
    assert session.appels == 3
    assert all(r.chemin.exists() for r in resultats)


# ─── Aucune valeur en dur ─────────────────────────────────────────────────────


def test_aucun_identifiant_ni_url_de_jeu_de_donnees_en_dur() -> None:
    """Les identifiants de millésime et l'hôte du portail ne doivent venir que de la configuration."""
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "edumatch"
        / "ingestion"
        / "parcoursup.py"
    ).read_text(encoding="utf-8")

    assert "fr-esr-parcoursup" not in source
    assert "data.enseignementsup-recherche.gouv.fr" not in source


# ─── Transitoire contre définitif — même vocabulaire que Sirene ─────────────
#
# Le DAG Airflow (E33) doit pouvoir choisir entre retenter et alerter sans
# connaître le connecteur en cause : ces tests prouvent que Parcoursup lève
# la même hiérarchie que Sirene (`ErreurTransitoire` / `ErreurDefinitive` de
# `_flux.py`), pas seulement sa propre base `ErreurTelechargementParcoursup`.


def test_millesime_non_configure_leve_lerreur_configuration_definitive(settings_test) -> None:
    with pytest.raises(ErreurConfigurationParcoursup) as excinfo:
        telecharger_millesime(1999, settings=settings_test, session=SessionFactice())

    assert isinstance(excinfo.value, ErreurTelechargementParcoursup)
    assert isinstance(excinfo.value, ErreurDefinitive)
    assert not isinstance(excinfo.value, ErreurTransitoire)


def test_coupure_reseau_leve_lerreur_reseau_transitoire(settings_test) -> None:
    session = SessionFactice(erreur_en_cours_de_flux=requests.exceptions.ConnectionError("coupure"))

    with pytest.raises(ErreurReseauParcoursup) as excinfo:
        telecharger_millesime(2020, settings=settings_test, session=session)

    assert isinstance(excinfo.value, ErreurTelechargementParcoursup)
    assert isinstance(excinfo.value, ErreurTransitoire)
    assert not isinstance(excinfo.value, ErreurDefinitive)


def test_erreur_http_pendant_le_telechargement_leve_lerreur_reseau_transitoire(settings_test) -> None:
    with pytest.raises(ErreurReseauParcoursup) as excinfo:
        telecharger_millesime(2020, settings=settings_test, session=SessionErreurHttp())

    assert isinstance(excinfo.value, ErreurTransitoire)
