"""Tests du connecteur Sirene (src/edumatch/ingestion/sirene.py).

Aucun accès réseau : la couche HTTP est remplacée par une session factice.
Couvre la différence structurante avec Parcoursup — la résolution d'URL
depuis le catalogue, jamais une URL de fichier en dur — ainsi que
l'idempotence, l'écriture atomique et le manifeste, déjà exigées pour tout
connecteur du projet.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
import requests

from edumatch.config import load_settings
from edumatch.ingestion.sirene import (
    ErreurTelechargementSirene,
    RessourceCatalogue,
    resoudre_ressources,
    telecharger_fichier,
    telecharger_tous,
)

CONTENU_PARQUET = b"\x50\x41\x52\x31faux-contenu-parquet"

URL_STOCK_ETABLISSEMENT = "https://exemple.test/resources/stock-etablissement-parquet"


def _ressource(titre: str, format_: str, url: str, last_modified: str = "2026-08-01T07:46:40+00:00", filesize: int = 12345) -> dict:
    return {"title": titre, "format": format_, "url": url, "last_modified": last_modified, "filesize": filesize}


def _catalogue(resources: list[dict]) -> dict:
    return {"last_update": "2026-08-01T07:49:50+00:00", "frequency": "monthly", "resources": resources}


CATALOGUE_NOMINAL = _catalogue(
    [
        _ressource("Sirene : Fichier StockEtablissement - 01 août 2026", "zip", "https://exemple.test/zip"),
        _ressource(
            "Sirene : Fichier StockEtablissement - 01 août 2026 (format parquet)",
            "parquet",
            URL_STOCK_ETABLISSEMENT,
        ),
    ]
)


class _ReponseJson:
    """Réponse factice pour l'appel au catalogue : pas de flux, juste un JSON."""

    def __init__(self, corps: dict, statut_en_erreur: bool = False) -> None:
        self._corps = corps
        self._statut_en_erreur = statut_en_erreur

    def raise_for_status(self) -> None:
        if self._statut_en_erreur:
            raise requests.exceptions.HTTPError("404 Client Error: Not Found")

    def json(self) -> dict:
        return self._corps


class _ReponseFlux:
    """Réponse factice pour le téléchargement d'un fichier : contexte, statut, flux."""

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

    def __enter__(self) -> "_ReponseFlux":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


class SessionFactice:
    """Sert le catalogue factice sur l'URL du catalogue, un contenu fixe sur toute autre URL.

    Distingue les deux usages par la présence de `stream=True` (téléchargement
    de fichier) plutôt que par un routage d'URL explicite : c'est exactement
    ce que fait le code réel, qui appelle `session.get` deux fois avec des
    intentions différentes.
    """

    def __init__(
        self,
        catalogue: dict = CATALOGUE_NOMINAL,
        catalogue_en_erreur: bool = False,
        contenu_fichier: bytes = CONTENU_PARQUET,
        erreur_en_cours_de_flux: Exception | None = None,
    ) -> None:
        self.catalogue = catalogue
        self.catalogue_en_erreur = catalogue_en_erreur
        self.contenu_fichier = contenu_fichier
        self.erreur_en_cours_de_flux = erreur_en_cours_de_flux
        self.appels_catalogue = 0
        self.appels_fichier = 0

    def get(self, url: str, stream: bool = False, timeout: float | None = None):  # noqa: ARG002
        if stream:
            self.appels_fichier += 1
            return _ReponseFlux([self.contenu_fichier], self.erreur_en_cours_de_flux)
        self.appels_catalogue += 1
        return _ReponseJson(self.catalogue, statut_en_erreur=self.catalogue_en_erreur)


@pytest.fixture()
def settings_test(configs_dir_isole: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Configuration résolue, données brutes isolées sous tmp_path.

    `configs_dir_isole` déclare un seul fichier Sirene (`StockEtablissement`),
    suffisant pour les tests qui ne portent pas spécifiquement sur la
    désambiguïsation entre plusieurs fichiers.
    """
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(tmp_path / "data"))
    return load_settings("dev", configs_dir=configs_dir_isole)


# ─── Résolution du catalogue — le cœur de la différence avec Parcoursup ──────


def test_resoudre_ressources_retient_lentree_parquet_pas_le_zip(settings_test) -> None:
    session = SessionFactice()
    ressources = resoudre_ressources(settings=settings_test, session=session)

    assert len(ressources) == 1
    assert ressources[0].fichier == "StockEtablissement"
    assert ressources[0].url == URL_STOCK_ETABLISSEMENT
    assert ressources[0].date_publication == "2026-08-01T07:46:40+00:00"
    assert session.appels_catalogue == 1
    assert session.appels_fichier == 0, "résoudre une URL ne doit déclencher aucun téléchargement de fichier"


def test_resoudre_ressources_ne_confond_pas_un_fichier_avec_son_prefixe(configs_dir_isole: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """StockEtablissement et StockEtablissementHistorique partagent un préfixe : la résolution ne doit pas les confondre."""
    base_yaml = (configs_dir_isole / "base.yaml").read_text(encoding="utf-8")
    base_yaml_deux_fichiers = base_yaml.replace(
        "fichiers: [StockEtablissement]",
        "fichiers: [StockEtablissement, StockEtablissementHistorique]",
    )
    (configs_dir_isole / "base.yaml").write_text(base_yaml_deux_fichiers, encoding="utf-8")
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(tmp_path / "data"))
    settings = load_settings("dev", configs_dir=configs_dir_isole)

    catalogue = _catalogue(
        [
            _ressource("Sirene : Fichier StockEtablissement - 01 août 2026 (format parquet)", "parquet", "https://exemple.test/etab"),
            _ressource(
                "Sirene : Fichier StockEtablissementHistorique - 01 août 2026 (format parquet)",
                "parquet",
                "https://exemple.test/etab-historique",
            ),
        ]
    )
    session = SessionFactice(catalogue=catalogue)
    ressources = resoudre_ressources(settings=settings, session=session)

    par_fichier = {r.fichier: r.url for r in ressources}
    assert par_fichier["StockEtablissement"] == "https://exemple.test/etab"
    assert par_fichier["StockEtablissementHistorique"] == "https://exemple.test/etab-historique"


def test_resoudre_ressources_leve_si_le_fichier_est_absent_du_catalogue(settings_test) -> None:
    catalogue_sans_le_fichier = _catalogue([_ressource("Sirene : Fichier AutreFichier - 01 août 2026 (format parquet)", "parquet", "https://exemple.test/autre")])
    session = SessionFactice(catalogue=catalogue_sans_le_fichier)

    with pytest.raises(ErreurTelechargementSirene, match="StockEtablissement"):
        resoudre_ressources(settings=settings_test, session=session)


def test_resoudre_ressources_leve_si_le_catalogue_est_injoignable(settings_test) -> None:
    session = SessionFactice(catalogue_en_erreur=True)

    with pytest.raises(ErreurTelechargementSirene):
        resoudre_ressources(settings=settings_test, session=session)


def test_resoudre_ressources_leve_si_plusieurs_ressources_correspondent(settings_test) -> None:
    catalogue_ambigu = _catalogue(
        [
            _ressource("Sirene : Fichier StockEtablissement - 01 août 2026 (format parquet)", "parquet", "https://exemple.test/a"),
            _ressource("Sirene : Fichier StockEtablissement - 01 août 2026 (format parquet) (bis)", "parquet", "https://exemple.test/b"),
        ]
    )
    # Les deux titres commencent tous deux par « Fichier StockEtablissement - » : ambiguïté volontaire pour ce test.
    session = SessionFactice(catalogue=catalogue_ambigu)

    with pytest.raises(ErreurTelechargementSirene, match="résolution ambiguë"):
        resoudre_ressources(settings=settings_test, session=session)


# ─── Téléchargement, idempotence, manifeste ─────────────────────────────────


def test_telecharge_ecrit_le_fichier_et_le_manifeste_avec_la_date_de_stock(settings_test) -> None:
    session = SessionFactice()
    ressources = resoudre_ressources(settings=settings_test, session=session)
    resultat = telecharger_fichier(ressources[0], settings=settings_test, session=session)

    assert resultat.telecharge is True
    assert resultat.chemin.read_bytes() == CONTENU_PARQUET
    assert session.appels_fichier == 1

    manifeste = json.loads((settings_test.raw_dir / "sirene" / "manifeste.json").read_text())
    entree = manifeste["StockEtablissement"]
    assert entree["url"] == URL_STOCK_ETABLISSEMENT
    assert entree["date_publication_stock"] == "2026-08-01T07:46:40+00:00", (
        "le manifeste doit porter la date du stock, pas seulement l'URL : "
        "un volume Sirene sans sa date n'est pas reproductible"
    )
    assert entree["taille_octets"] == len(CONTENU_PARQUET)
    assert entree["empreinte_sha256"] == resultat.empreinte_sha256
    assert "date_telechargement" in entree


def test_second_appel_ne_retelecharge_pas(settings_test) -> None:
    session = SessionFactice()
    ressources = resoudre_ressources(settings=settings_test, session=session)
    telecharger_fichier(ressources[0], settings=settings_test, session=session)
    resultat_second = telecharger_fichier(ressources[0], settings=settings_test, session=session)

    assert session.appels_fichier == 1, "le second appel n'aurait pas dû retélécharger le fichier"
    assert resultat_second.telecharge is False


def test_forcer_retelecharge_meme_si_le_fichier_est_intact(settings_test) -> None:
    session = SessionFactice()
    ressources = resoudre_ressources(settings=settings_test, session=session)
    telecharger_fichier(ressources[0], settings=settings_test, session=session)
    telecharger_fichier(ressources[0], settings=settings_test, session=session, forcer=True)

    assert session.appels_fichier == 2


def test_telechargement_journalise_la_progression(settings_test, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """Sirene délègue la journalisation de progression à `_flux.telecharger_en_flux` via un rappel.

    L'intervalle réel (10 s) rendrait le test non déterministe sans attendre :
    on le ramène à zéro pour que le rappel se déclenche à coup sûr sur l'unique
    bloc servi par `SessionFactice`.
    """
    monkeypatch.setattr("edumatch.ingestion.sirene.INTERVALLE_JOURNAL_PROGRESSION_SECONDES", 0)
    session = SessionFactice(contenu_fichier=b"x" * 30)
    ressources = resoudre_ressources(settings=settings_test, session=session)

    with caplog.at_level(logging.INFO, logger="edumatch.ingestion.sirene"):
        telecharger_fichier(ressources[0], settings=settings_test, session=session)

    messages = [enregistrement.message for enregistrement in caplog.records]
    assert any("en cours" in message and "StockEtablissement" in message for message in messages), messages
    assert any("terminé" in message and "StockEtablissement" in message for message in messages), messages


def test_fichier_corrompu_est_retelecharge(settings_test) -> None:
    session = SessionFactice()
    ressources = resoudre_ressources(settings=settings_test, session=session)
    resultat = telecharger_fichier(ressources[0], settings=settings_test, session=session)
    resultat.chemin.write_bytes(b"contenu corrompu, ne correspond plus au manifeste")

    telecharger_fichier(ressources[0], settings=settings_test, session=session)

    assert session.appels_fichier == 2, "un fichier corrompu doit être retéléchargé"
    assert resultat.chemin.read_bytes() == CONTENU_PARQUET


# ─── Écriture atomique et erreurs réseau ─────────────────────────────────────


def test_interruption_ne_laisse_aucun_fichier_final_utilisable(settings_test) -> None:
    session = SessionFactice(erreur_en_cours_de_flux=requests.exceptions.ConnectionError("coupure"))
    ressources = resoudre_ressources(settings=settings_test, session=session)

    with pytest.raises(ErreurTelechargementSirene):
        telecharger_fichier(ressources[0], settings=settings_test, session=session)

    dossier = settings_test.raw_dir / "sirene"
    fichiers_presents = list(dossier.glob("StockEtablissement*")) if dossier.exists() else []
    assert fichiers_presents == [], f"fichier(s) résiduel(s) après interruption : {fichiers_presents}"


def test_ressource_hors_manifeste_directement_construite_leve_erreur_http(settings_test) -> None:
    """Une ressource résolue « à la main » (sans passer par le catalogue), dont l'URL renvoie une erreur HTTP."""

    class SessionErreurHttp:
        def get(self, url: str, stream: bool = False, timeout: float | None = None):  # noqa: ARG002
            return _ReponseHttpEnErreur()

    class _ReponseHttpEnErreur:
        def raise_for_status(self) -> None:
            raise requests.exceptions.HTTPError("500 Server Error")

        def iter_content(self, chunk_size: int):  # noqa: ARG002
            yield b""

        def __enter__(self) -> "_ReponseHttpEnErreur":
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    ressource = RessourceCatalogue(
        fichier="StockEtablissement",
        url="https://exemple.test/en-panne",
        date_publication="2026-08-01T07:46:40+00:00",
        taille_octets_annoncee=1000,
    )

    with pytest.raises(ErreurTelechargementSirene, match="StockEtablissement"):
        telecharger_fichier(ressource, settings=settings_test, session=SessionErreurHttp())

    dossier = settings_test.raw_dir / "sirene"
    fichiers_presents = list(dossier.glob("StockEtablissement*")) if dossier.exists() else []
    assert fichiers_presents == [], f"fichier(s) résiduel(s) après erreur HTTP : {fichiers_presents}"


# ─── Plusieurs fichiers ───────────────────────────────────────────────────────


def test_telecharger_tous_resout_le_catalogue_une_seule_fois(settings_test) -> None:
    session = SessionFactice()
    resultats = telecharger_tous(settings=settings_test, session=session)

    assert [r.fichier for r in resultats] == ["StockEtablissement"]
    assert session.appels_catalogue == 1
    assert session.appels_fichier == 1


# ─── Aucune URL ni identifiant de fichier en dur ─────────────────────────────


def test_aucune_url_ni_identifiant_de_jeu_de_donnees_en_dur() -> None:
    """Contrairement à Parcoursup, Sirene n'a pas de gabarit d'URL fixe : rien ici ne doit en coder un."""
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "edumatch"
        / "ingestion"
        / "sirene.py"
    ).read_text(encoding="utf-8")

    assert "www.data.gouv.fr" not in source
    assert "base-sirene-des-entreprises" not in source
    assert "static.data.gouv.fr" not in source

# ─── Cas dégradés du catalogue — trous corrigés en revue de qualité ──────────
#
# Ces scénarios sont réels : un catalogue distant peut répondre avec un JSON
# syntaxiquement valide mais structurellement inattendu (schéma changé, champ
# retiré, type différent). `resoudre_ressources` valide désormais la forme de
# la réponse champ par champ et lève `ErreurTelechargementSirene` en nommant
# le champ fautif, plutôt que de laisser s'échapper une KeyError, une
# AttributeError ou une TypeError que le DAG d'orchestration ne capturerait pas.


def test_resoudre_ressources_leve_une_erreur_controlee_si_la_ressource_na_pas_durl(settings_test) -> None:
    catalogue_sans_url = _catalogue(
        [
            {
                "title": "Sirene : Fichier StockEtablissement - 01 août 2026 (format parquet)",
                "format": "parquet",
                # champ "url" absent : cas réel d'un catalogue qui a changé de schéma
            }
        ]
    )
    session = SessionFactice(catalogue=catalogue_sans_url)

    with pytest.raises(ErreurTelechargementSirene, match="url"):
        resoudre_ressources(settings=settings_test, session=session)


def test_resoudre_ressources_leve_une_erreur_controlee_si_lurl_est_vide(settings_test) -> None:
    """Une URL présente mais vide n'est pas exploitable : même contrat qu'une URL absente."""
    catalogue_url_vide = _catalogue(
        [
            {
                "title": "Sirene : Fichier StockEtablissement - 01 août 2026 (format parquet)",
                "format": "parquet",
                "url": "",
            }
        ]
    )
    session = SessionFactice(catalogue=catalogue_url_vide)

    with pytest.raises(ErreurTelechargementSirene, match="url"):
        resoudre_ressources(settings=settings_test, session=session)


def test_resoudre_ressources_leve_une_erreur_controlee_si_le_catalogue_nest_pas_un_dict(settings_test) -> None:
    session = SessionFactice(catalogue=[])  # JSON inattendu : une liste plutôt qu'un objet

    with pytest.raises(ErreurTelechargementSirene, match="objet JSON"):
        resoudre_ressources(settings=settings_test, session=session)


def test_resoudre_ressources_leve_une_erreur_controlee_si_resources_est_nul(settings_test) -> None:
    session = SessionFactice(catalogue={"resources": None})

    with pytest.raises(ErreurTelechargementSirene, match="StockEtablissement"):
        resoudre_ressources(settings=settings_test, session=session)


def test_resoudre_ressources_leve_une_erreur_controlee_si_resources_nest_pas_une_liste(settings_test) -> None:
    """Cas réel supplémentaire : 'resources' d'un type inattendu (dict au lieu de liste)."""
    session = SessionFactice(catalogue={"resources": {"non": "une liste"}})

    with pytest.raises(ErreurTelechargementSirene, match="'resources'"):
        resoudre_ressources(settings=settings_test, session=session)


def test_resoudre_ressources_leve_une_erreur_controlee_si_une_ressource_nest_pas_un_objet(settings_test) -> None:
    """Cas réel supplémentaire : la liste 'resources' contient un élément qui n'est pas un objet JSON."""
    session = SessionFactice(catalogue={"resources": ["pas un objet"]})

    with pytest.raises(ErreurTelechargementSirene, match="index 0"):
        resoudre_ressources(settings=settings_test, session=session)


# ─── date de publication du stock — même exigence que pour l'URL ────────────
#
# Un stock Sirene grossit chaque mois : un volume sans la date du stock
# auquel il se rapporte n'est pas reproductible. `last_modified` est donc
# vérifié avec la même rigueur que `url`, sans jamais se rabattre sur une
# chaîne vide ni sur la date du jour.


def test_resoudre_ressources_leve_une_erreur_controlee_si_last_modified_est_absent(settings_test) -> None:
    catalogue_sans_date = _catalogue(
        [
            {
                "title": "Sirene : Fichier StockEtablissement - 01 août 2026 (format parquet)",
                "format": "parquet",
                "url": URL_STOCK_ETABLISSEMENT,
                # champ "last_modified" absent : le catalogue a pu changer de schéma
            }
        ]
    )
    session = SessionFactice(catalogue=catalogue_sans_date)

    with pytest.raises(ErreurTelechargementSirene, match="last_modified"):
        resoudre_ressources(settings=settings_test, session=session)


def test_resoudre_ressources_leve_une_erreur_controlee_si_last_modified_est_vide(settings_test) -> None:
    """Une date présente mais vide n'est pas exploitable : même contrat qu'une date absente."""
    catalogue_date_vide = _catalogue(
        [
            {
                "title": "Sirene : Fichier StockEtablissement - 01 août 2026 (format parquet)",
                "format": "parquet",
                "url": URL_STOCK_ETABLISSEMENT,
                "last_modified": "",
            }
        ]
    )
    session = SessionFactice(catalogue=catalogue_date_vide)

    with pytest.raises(ErreurTelechargementSirene, match="last_modified"):
        resoudre_ressources(settings=settings_test, session=session)
