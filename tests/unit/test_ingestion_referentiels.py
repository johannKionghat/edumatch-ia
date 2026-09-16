"""Tests du volet IDÉO du connecteur référentiels (src/edumatch/ingestion/referentiels.py).

Aucun accès réseau : la couche HTTP est remplacée par une session factice.
Couvre : téléchargement nominal et manifeste, idempotence, forçage, écriture
atomique face à une interruption, fichier corrompu, jeu non configuré,
contrôle de contrat d'encodage, et hiérarchie d'erreur transitoire/définitive
partagée avec Parcoursup et Sirene.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Self

import pytest
import requests

from edumatch.config import load_settings
from edumatch.ingestion._flux import ErreurDefinitive, ErreurFluxVide, ErreurTransitoire
from edumatch.ingestion._referentiels_communs import verifier_encodage
from edumatch.ingestion.referentiels import (
    ErreurConfigurationReferentiels,
    ErreurContratReferentiels,
    ErreurReseauReferentiels,
    ErreurTelechargementReferentiels,
    telecharger_ideo,
    telecharger_tous_ideo,
)

CONTENU_CSV_UTF8 = '"code";"libellé"\n"A01";"formation générale"\n'.encode()


class _ReponseFactice:
    """Reproduit l'interface de `requests.Response` utile ici : contexte, statut, flux."""

    def __init__(self, blocs: list[bytes], erreur_en_cours_de_flux: Exception | None = None) -> None:
        self._blocs = blocs
        self._erreur = erreur_en_cours_de_flux

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        yield from self._blocs
        if self._erreur is not None:
            raise self._erreur

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


class SessionFactice:
    """Remplace `requests.Session` : compte les appels, sert un contenu fixe ou une panne."""

    def __init__(self, contenu: bytes = CONTENU_CSV_UTF8, erreur_en_cours_de_flux: Exception | None = None) -> None:
        self.contenu = contenu
        self.erreur_en_cours_de_flux = erreur_en_cours_de_flux
        self.appels = 0

    def get(self, url: str, stream: bool = True, timeout: float | None = None) -> _ReponseFactice:
        self.appels += 1
        return _ReponseFactice([self.contenu], self.erreur_en_cours_de_flux)


class _ReponseErreurHttp:
    def raise_for_status(self) -> None:
        raise requests.exceptions.HTTPError("404 Client Error: Not Found")

    def iter_content(self, chunk_size: int):
        yield b""

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


class SessionErreurHttp:
    def get(self, url: str, stream: bool = True, timeout: float | None = None) -> _ReponseErreurHttp:
        return _ReponseErreurHttp()


@pytest.fixture()
def settings_test(configs_dir_isole: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Configuration résolue, données externes isolées sous tmp_path.

    `configs_dir_isole` déclare un seul jeu IDÉO (`formations`), suffisant
    pour les tests qui ne portent pas sur la désambiguïsation entre jeux.
    """
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(tmp_path / "data"))
    return load_settings("dev", configs_dir=configs_dir_isole)


# ─── Téléchargement nominal, manifeste, licence et encodage déclarés ────────


def test_telecharge_ecrit_le_fichier_et_le_manifeste(settings_test) -> None:
    session = SessionFactice()
    resultat = telecharger_ideo("formations", settings=settings_test, session=session)

    assert resultat.telecharge is True
    assert resultat.source == "ideo"
    assert resultat.chemin.read_bytes() == CONTENU_CSV_UTF8
    assert resultat.encodage == "utf-8"
    assert resultat.delimiteur == ";"
    assert resultat.licence == "ODbL (odc-odbl)"
    assert session.appels == 1

    manifeste = json.loads((settings_test.external_dir / "referentiels" / "manifeste.json").read_text())
    entree = manifeste["ideo:formations"]
    assert entree["url"] == "https://exemple.test/ideo/formations.csv"
    assert entree["licence"] == "ODbL (odc-odbl)"
    assert entree["encodage"] == "utf-8"
    assert entree["taille_octets"] == len(CONTENU_CSV_UTF8)
    assert entree["empreinte_sha256"] == resultat.empreinte_sha256
    assert "date_telechargement" in entree


def test_jeu_non_configure_leve_une_erreur_explicite(settings_test) -> None:
    with pytest.raises(ErreurTelechargementReferentiels, match="metiers"):
        telecharger_ideo("metiers", settings=settings_test, session=SessionFactice())


# ─── Idempotence ──────────────────────────────────────────────────────────────


def test_second_appel_ne_retelecharge_pas(settings_test) -> None:
    session = SessionFactice()
    telecharger_ideo("formations", settings=settings_test, session=session)
    resultat_second = telecharger_ideo("formations", settings=settings_test, session=session)

    assert session.appels == 1, "le second appel n'aurait pas dû déclencher de requête HTTP"
    assert resultat_second.telecharge is False


def test_forcer_retelecharge_meme_si_le_fichier_est_intact(settings_test) -> None:
    session = SessionFactice()
    telecharger_ideo("formations", settings=settings_test, session=session)
    telecharger_ideo("formations", settings=settings_test, session=session, forcer=True)

    assert session.appels == 2


def test_fichier_corrompu_est_retelecharge(settings_test) -> None:
    session = SessionFactice()
    resultat = telecharger_ideo("formations", settings=settings_test, session=session)
    resultat.chemin.write_bytes(b"contenu corrompu, ne correspond plus au manifeste")

    telecharger_ideo("formations", settings=settings_test, session=session)

    assert session.appels == 2, "un fichier corrompu doit être retéléchargé"
    assert resultat.chemin.read_bytes() == CONTENU_CSV_UTF8


# ─── Écriture atomique et erreurs réseau ─────────────────────────────────────


def test_interruption_ne_laisse_aucun_fichier_final_utilisable(settings_test) -> None:
    session = SessionFactice(erreur_en_cours_de_flux=requests.exceptions.ConnectionError("coupure"))

    with pytest.raises(ErreurTelechargementReferentiels):
        telecharger_ideo("formations", settings=settings_test, session=session)

    dossier = settings_test.external_dir / "referentiels" / "ideo"
    fichiers_presents = list(dossier.glob("formations*")) if dossier.exists() else []
    assert fichiers_presents == [], f"fichier(s) résiduel(s) après interruption : {fichiers_presents}"


def test_erreur_http_ne_laisse_aucun_fichier(settings_test) -> None:
    with pytest.raises(ErreurTelechargementReferentiels, match="formations"):
        telecharger_ideo("formations", settings=settings_test, session=SessionErreurHttp())

    dossier = settings_test.external_dir / "referentiels" / "ideo"
    fichiers_presents = list(dossier.glob("formations*")) if dossier.exists() else []
    assert fichiers_presents == [], f"fichier(s) résiduel(s) après erreur HTTP : {fichiers_presents}"


# ─── Contrat d'encodage ───────────────────────────────────────────────────────


def test_fichier_qui_ne_decode_pas_selon_lencodage_declare_leve_une_erreur_de_contrat(settings_test) -> None:
    """Un fichier dont le contenu ne respecte pas l'encodage déclaré est un changement de contrat.

    Simule le cas réel qui a motivé ce contrôle : une source déclarée UTF-8
    (ici configurée ainsi) qui renverrait en réalité des octets non
    décodables selon ce jeu de caractères — un octet seul 0xff n'est valide
    dans aucune séquence UTF-8.
    """
    session = SessionFactice(contenu=b"\xff\xfe pas de l'utf-8 valide")

    with pytest.raises(ErreurContratReferentiels, match="utf-8"):
        telecharger_ideo("formations", settings=settings_test, session=session)


def test_verifier_encodage_ne_detecte_pas_un_fichier_utf8_declare_a_tort_en_latin1(tmp_path: Path) -> None:
    """Limite honnête du contrôle de contrat : il ne protège que dans un sens.

    `verifier_encodage` ne fait qu'essayer de décoder les octets selon
    l'encodage déclaré. Latin-1 accepte n'importe quelle suite d'octets — il
    n'existe aucun octet qu'il refuse de décoder. Un fichier réellement écrit
    en UTF-8, mais dont la configuration déclarerait (à tort) l'encodage
    latin-1, passe donc ce contrôle sans la moindre erreur, alors que le
    contenu relu serait un mojibake (« comptabilitÃ© » plutôt que
    « comptabilité »). Le contrôle protège efficacement le sens inverse — un
    fichier réellement en Latin-1 déclaré à tort en UTF-8, voir le test
    ci-dessus — mais ne garantit rien ici. C'est une limite du mécanisme, pas
    un bug : aucun contrôle par décodage seul ne peut la lever, une source
    encodée en latin-1 étant par construction indécidable de l'UTF-8 sans
    connaître son contenu attendu.
    """
    chemin = tmp_path / "export.csv"
    chemin.write_bytes("comptabilité".encode())

    verifier_encodage(chemin, "latin-1", "test")  # ne lève rien : mojibake silencieux

    assert chemin.read_bytes().decode("latin-1") != "comptabilité"


# ─── Corps vide — un HTTP 200 sans octet n'est pas un téléchargement réussi ──


def test_corps_vide_leve_erreur_flux_vide_sans_fichier_residuel(settings_test) -> None:
    """Bénéficie du correctif posé une seule fois dans `_flux.telecharger_en_flux`."""
    session = SessionFactice(contenu=b"")

    with pytest.raises(ErreurFluxVide):
        telecharger_ideo("formations", settings=settings_test, session=session)

    dossier = settings_test.external_dir / "referentiels" / "ideo"
    fichiers_presents = list(dossier.glob("formations*")) if dossier.exists() else []
    assert fichiers_presents == [], f"fichier(s) résiduel(s) après corps vide : {fichiers_presents}"


# ─── Plusieurs jeux ───────────────────────────────────────────────────────────


def test_telecharger_tous_ideo_traite_chaque_jeu_configure(configs_dir_isole: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_yaml = (configs_dir_isole / "base.yaml").read_text(encoding="utf-8")
    base_yaml_deux_jeux = base_yaml.replace(
        '        formations:\n          url: "https://exemple.test/ideo/formations.csv"\n'
        "          encodage: utf-8\n"
        '          delimiteur: ";"\n'
        '          licence: "ODbL (odc-odbl)"\n',
        '        formations:\n          url: "https://exemple.test/ideo/formations.csv"\n'
        "          encodage: utf-8\n"
        '          delimiteur: ";"\n'
        '          licence: "ODbL (odc-odbl)"\n'
        "        metiers:\n"
        '          url: "https://exemple.test/ideo/metiers.csv"\n'
        "          encodage: utf-8\n"
        '          delimiteur: ";"\n'
        '          licence: "ODbL (odc-odbl)"\n',
    )
    assert base_yaml_deux_jeux != base_yaml, "le remplacement n'a rien trouvé : le fixture conftest a changé"
    (configs_dir_isole / "base.yaml").write_text(base_yaml_deux_jeux, encoding="utf-8")
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(tmp_path / "data"))
    settings = load_settings("dev", configs_dir=configs_dir_isole)

    session = SessionFactice()
    resultats = telecharger_tous_ideo(settings=settings, session=session)

    assert [r.jeu for r in resultats] == ["formations", "metiers"]
    assert session.appels == 2


# ─── Aucune URL en dur ────────────────────────────────────────────────────────


def test_aucune_url_ideo_en_dur() -> None:
    """Les URL de téléchargement IDÉO ne doivent venir que de la configuration."""
    source = (
        Path(__file__).resolve().parents[2] / "src" / "edumatch" / "ingestion" / "referentiels.py"
    ).read_text(encoding="utf-8")

    assert "api.opendata.onisep.fr" not in source


# ─── Transitoire contre définitif — même vocabulaire que Parcoursup et Sirene ─


def test_jeu_non_configure_leve_lerreur_configuration_definitive(settings_test) -> None:
    with pytest.raises(ErreurConfigurationReferentiels) as excinfo:
        telecharger_ideo("metiers", settings=settings_test, session=SessionFactice())

    assert isinstance(excinfo.value, ErreurTelechargementReferentiels)
    assert isinstance(excinfo.value, ErreurDefinitive)
    assert not isinstance(excinfo.value, ErreurTransitoire)


def test_coupure_reseau_leve_lerreur_reseau_transitoire(settings_test) -> None:
    session = SessionFactice(erreur_en_cours_de_flux=requests.exceptions.ConnectionError("coupure"))

    with pytest.raises(ErreurReseauReferentiels) as excinfo:
        telecharger_ideo("formations", settings=settings_test, session=session)

    assert isinstance(excinfo.value, ErreurTransitoire)
    assert not isinstance(excinfo.value, ErreurDefinitive)


def test_fichier_hors_contrat_leve_lerreur_definitive_pas_transitoire(settings_test) -> None:
    session = SessionFactice(contenu=b"\xff\xfe")

    with pytest.raises(ErreurContratReferentiels) as excinfo:
        telecharger_ideo("formations", settings=settings_test, session=session)

    assert isinstance(excinfo.value, ErreurDefinitive)
    assert not isinstance(excinfo.value, ErreurTransitoire)
