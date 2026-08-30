"""Tests du volet RNCP du connecteur référentiels (src/edumatch/ingestion/_referentiels_rncp.py).

Aucun accès réseau. Couvre le cœur de la différence avec IDÉO, Parcoursup et
Sirene : un export **republié chaque jour**, résolu par date de publication
plutôt que par empreinte seule — deux appels le même jour ne retéléchargent
rien, deux appels à deux dates différentes produisent deux fichiers distincts,
aucun des deux n'écrasant l'autre. Couvre aussi l'extraction du CSV standard
depuis l'archive ZIP et le contrôle de contrat d'encodage.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
import requests

from edumatch.config import load_settings
from edumatch.ingestion._flux import ErreurDefinitive, ErreurTransitoire
from edumatch.ingestion._referentiels_rncp import (
    chemin_destination_rome,
    resoudre_ressource,
    telecharger,
    telecharger_rome,
)
from edumatch.ingestion.referentiels import (
    ErreurCatalogueReferentiels,
    ErreurContratReferentiels,
    ErreurReseauReferentiels,
    ErreurTelechargementReferentiels,
)

NOM_CSV_STANDARD = "export_fiches_CSV_Standard_2026_08_29.csv"
CONTENU_CSV_UTF8 = '"Id_Fiche";"Intitule"\n"RNCP1";"Assistant(e) en comptabilité"\n'.encode("utf-8")


def _zip_avec(nom_membre: str, contenu: bytes) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, mode="w") as archive:
        archive.writestr(nom_membre, contenu)
    return tampon.getvalue()


NOM_CSV_ROME = "export_fiches_CSV_Rome_2026_08_29.csv"
CONTENU_ROME_UTF8 = '"Numero_Fiche";"Codes_Rome_Code";"Codes_Rome_Libelle"\n"RNCP1";"M1607";"Secrétariat"\n'.encode(
    "utf-8"
)


def _zip_avec_deux_membres(membres: dict[str, bytes]) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, mode="w") as archive:
        for nom, contenu in membres.items():
            archive.writestr(nom, contenu)
    return tampon.getvalue()


# Contient les deux membres réels de l'archive quotidienne (voir E18) : le
# CSV standard et le fichier de codes ROME. Les tests du CSV standard, plus
# haut dans ce fichier, restent valides puisqu'ils ne filtrent que sur le
# motif du membre standard — ajouter le membre ROME ne les affecte pas.
ZIP_NOMINAL = _zip_avec_deux_membres({NOM_CSV_STANDARD: CONTENU_CSV_UTF8, NOM_CSV_ROME: CONTENU_ROME_UTF8})

URL_CATALOGUE = "https://exemple.test/api/1/datasets/repertoire-national-des-certifications-professionnelles-et-repertoire-specifique/"
URL_ZIP_29 = "https://exemple.test/export-fiches-csv-2026-08-29.zip"
URL_ZIP_28 = "https://exemple.test/export-fiches-csv-2026-08-28.zip"


def _ressource(titre: str, format_: str, url: str, last_modified: str) -> dict:
    return {"title": titre, "format": format_, "url": url, "last_modified": last_modified}


def _catalogue(resources: list[dict]) -> dict:
    return {"resources": resources}


CATALOGUE_NOMINAL = _catalogue(
    [
        _ressource("export-fiches-csv-2026-08-28.zip", "zip", URL_ZIP_28, "2026-08-28T02:00:10.105000+00:00"),
        _ressource("export-fiches-csv-2026-08-29.zip", "zip", URL_ZIP_29, "2026-08-29T02:00:12.883000+00:00"),
    ]
)


class _ReponseJson:
    def __init__(self, corps: dict, statut_en_erreur: bool = False) -> None:
        self._corps = corps
        self._statut_en_erreur = statut_en_erreur

    def raise_for_status(self) -> None:
        if self._statut_en_erreur:
            raise requests.exceptions.HTTPError("404 Client Error: Not Found")

    def json(self) -> dict:
        return self._corps


class _ReponseZip:
    def __init__(self, contenu: bytes, statut_en_erreur: bool = False) -> None:
        self.content = contenu
        self._statut_en_erreur = statut_en_erreur

    def raise_for_status(self) -> None:
        if self._statut_en_erreur:
            raise requests.exceptions.HTTPError("500 Server Error")


class SessionFactice:
    """Sert le catalogue factice sur l'URL du catalogue, une archive ZIP sur toute autre URL."""

    def __init__(
        self,
        catalogue: dict = CATALOGUE_NOMINAL,
        catalogue_en_erreur: bool = False,
        contenu_zip: bytes = ZIP_NOMINAL,
        zip_en_erreur: bool = False,
    ) -> None:
        self.catalogue = catalogue
        self.catalogue_en_erreur = catalogue_en_erreur
        self.contenu_zip = contenu_zip
        self.zip_en_erreur = zip_en_erreur
        self.appels_catalogue = 0
        self.appels_zip = 0

    def get(self, url: str, timeout: float | None = None):  # noqa: ARG002
        if url == URL_CATALOGUE:
            self.appels_catalogue += 1
            return _ReponseJson(self.catalogue, statut_en_erreur=self.catalogue_en_erreur)
        self.appels_zip += 1
        return _ReponseZip(self.contenu_zip, statut_en_erreur=self.zip_en_erreur)


@pytest.fixture()
def settings_test(configs_dir_isole: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(tmp_path / "data"))
    return load_settings("dev", configs_dir=configs_dir_isole)


# ─── Résolution du catalogue : retient l'export le plus récent ─────────────


def test_resoudre_ressource_retient_lexport_le_plus_recent(settings_test) -> None:
    session = SessionFactice()
    ressource = resoudre_ressource(settings_test, session=session)

    assert ressource.url == URL_ZIP_29
    assert ressource.date_publication == "2026-08-29T02:00:12.883000+00:00"
    assert ressource.date_publication_jour == "2026-08-29"
    assert session.appels_catalogue == 1
    assert session.appels_zip == 0, "résoudre une ressource ne doit déclencher aucun téléchargement"


def test_resoudre_ressource_ignore_les_ressources_dun_autre_format(settings_test) -> None:
    catalogue = _catalogue(
        [
            _ressource("export-fiches-csv-2026-08-29.csv", "csv", "https://exemple.test/pas-larchive", "2026-08-29T09:00:00+00:00"),
            _ressource("export-fiches-csv-2026-08-28.zip", "zip", URL_ZIP_28, "2026-08-28T02:00:10+00:00"),
        ]
    )
    session = SessionFactice(catalogue=catalogue)
    ressource = resoudre_ressource(settings_test, session=session)

    assert ressource.url == URL_ZIP_28


def test_resoudre_ressource_leve_si_aucune_ressource_ne_correspond(settings_test) -> None:
    session = SessionFactice(catalogue=_catalogue([]))

    with pytest.raises(ErreurCatalogueReferentiels, match="export-fiches-csv-"):
        resoudre_ressource(settings_test, session=session)


def test_resoudre_ressource_leve_si_le_catalogue_est_injoignable(settings_test) -> None:
    session = SessionFactice(catalogue_en_erreur=True)

    with pytest.raises(ErreurReseauReferentiels):
        resoudre_ressource(settings_test, session=session)


def test_resoudre_ressource_leve_si_le_catalogue_nest_pas_un_objet(settings_test) -> None:
    session = SessionFactice(catalogue=[])

    with pytest.raises(ErreurCatalogueReferentiels, match="objet JSON"):
        resoudre_ressource(settings_test, session=session)


def test_resoudre_ressource_leve_si_lurl_est_absente(settings_test) -> None:
    catalogue = _catalogue(
        [{"title": "export-fiches-csv-2026-08-29.zip", "format": "zip", "last_modified": "2026-08-29T00:00:00+00:00"}]
    )
    session = SessionFactice(catalogue=catalogue)

    with pytest.raises(ErreurCatalogueReferentiels, match="url"):
        resoudre_ressource(settings_test, session=session)


def test_resoudre_ressource_leve_si_last_modified_est_non_exploitable(settings_test) -> None:
    catalogue = _catalogue(
        [{"title": "export-fiches-csv-2026-08-29.zip", "format": "zip", "url": URL_ZIP_29, "last_modified": "pas-une-date"}]
    )
    session = SessionFactice(catalogue=catalogue)

    with pytest.raises(ErreurCatalogueReferentiels, match="last_modified"):
        resoudre_ressource(settings_test, session=session)


# ─── Téléchargement, extraction du CSV standard, manifeste ─────────────────


def test_telecharge_extrait_le_csv_standard_et_ecrit_le_manifeste(settings_test) -> None:
    session = SessionFactice()
    ressource = resoudre_ressource(settings_test, session=session)
    resultat = telecharger(ressource, settings_test, session=session)

    assert resultat.telecharge is True
    assert resultat.source == "rncp"
    assert resultat.chemin.name == "rncp_2026-08-29.csv"
    assert resultat.chemin.read_bytes() == CONTENU_CSV_UTF8
    assert resultat.licence == "Licence Ouverte v2.0"
    assert resultat.encodage == "utf-8"
    assert session.appels_zip == 1

    manifeste = json.loads((settings_test.external_dir / "referentiels" / "manifeste.json").read_text())
    entree = manifeste["rncp:2026-08-29"]
    assert entree["date_publication_jour"] == "2026-08-29"
    assert entree["date_publication"] == "2026-08-29T02:00:12.883000+00:00"
    assert entree["licence"] == "Licence Ouverte v2.0"


# ─── Idempotence par date de publication — le cœur de cette étape ──────────


def test_second_appel_meme_jour_ne_retelecharge_pas(settings_test) -> None:
    session = SessionFactice()
    ressource = resoudre_ressource(settings_test, session=session)
    telecharger(ressource, settings_test, session=session)
    resultat_second = telecharger(ressource, settings_test, session=session)

    assert session.appels_zip == 1, "un second appel pour la même date ne doit pas retélécharger"
    assert resultat_second.telecharge is False


def test_deux_dates_differentes_produisent_deux_fichiers_distincts(settings_test) -> None:
    """Contrairement à Sirene (un seul fichier courant, écrasé chaque mois), chaque export
    RNCP est conservé : l'ancien fichier doit encore exister après la publication du jour
    suivant, pour que toute transformation qui l'a consommé reste rejouable.
    """
    session = SessionFactice()
    ressource_du_29 = resoudre_ressource(settings_test, session=session)
    resultat_29 = telecharger(ressource_du_29, settings_test, session=session)

    catalogue_le_lendemain = _catalogue(
        [_ressource("export-fiches-csv-2026-08-30.zip", "zip", "https://exemple.test/export-fiches-csv-2026-08-30.zip", "2026-08-30T02:00:00+00:00")]
    )
    session_lendemain = SessionFactice(catalogue=catalogue_le_lendemain, contenu_zip=_zip_avec("export_fiches_CSV_Standard_2026_08_30.csv", b'"Id_Fiche";"Intitule"\n"RNCP2";"Autre"\n'))
    ressource_du_30 = resoudre_ressource(settings_test, session=session_lendemain)
    resultat_30 = telecharger(ressource_du_30, settings_test, session=session_lendemain)

    assert resultat_29.chemin != resultat_30.chemin
    assert resultat_29.chemin.exists(), "l'export de la veille ne doit pas être écrasé par celui du jour"
    assert resultat_30.chemin.exists()


def test_fichier_corrompu_est_retelecharge(settings_test) -> None:
    """Un fichier présent mais dont l'empreinte diverge du manifeste n'est pas considéré intact.

    Équivalent, côté RNCP, du test du même nom pour IDÉO
    (`test_ingestion_referentiels.py`) : la seule présence du fichier sous le
    nom attendu (`rncp_2026-08-29.csv`) ne suffit pas à conclure à son
    intégrité, y compris quand la date de publication résolue est identique
    au fichier déjà sur disque — c'est l'empreinte SHA-256 du manifeste qui
    tranche, pas `Path.exists()`.
    """
    session = SessionFactice()
    ressource = resoudre_ressource(settings_test, session=session)
    resultat = telecharger(ressource, settings_test, session=session)
    resultat.chemin.write_bytes(b"contenu corrompu, ne correspond plus au manifeste")

    telecharger(ressource, settings_test, session=session)

    assert session.appels_zip == 2, "un fichier corrompu doit être retéléchargé, même publié le même jour"
    assert resultat.chemin.read_bytes() == CONTENU_CSV_UTF8


def test_forcer_retelecharge_meme_si_le_fichier_est_intact(settings_test) -> None:
    session = SessionFactice()
    ressource = resoudre_ressource(settings_test, session=session)
    telecharger(ressource, settings_test, session=session)
    telecharger(ressource, settings_test, session=session, forcer=True)

    assert session.appels_zip == 2


# ─── Contrat d'extraction et d'encodage ───────────────────────────────────────


def test_archive_sans_le_fichier_standard_leve_une_erreur_catalogue(settings_test) -> None:
    session = SessionFactice(contenu_zip=_zip_avec("autre_fichier.csv", b"contenu"))
    ressource = resoudre_ressource(settings_test, session=session)

    with pytest.raises(ErreurCatalogueReferentiels, match="Aucun fichier"):
        telecharger(ressource, settings_test, session=session)


def test_archive_avec_deux_fichiers_standard_leve_une_erreur_dambiguite(settings_test) -> None:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, mode="w") as archive:
        archive.writestr("export_fiches_CSV_Standard_2026_08_29.csv", CONTENU_CSV_UTF8)
        archive.writestr("export_fiches_CSV_Standard_2026_08_29_bis.csv", CONTENU_CSV_UTF8)
    session = SessionFactice(contenu_zip=tampon.getvalue())
    ressource = resoudre_ressource(settings_test, session=session)

    with pytest.raises(ErreurCatalogueReferentiels, match="ambiguë"):
        telecharger(ressource, settings_test, session=session)


def test_archive_corrompue_leve_une_erreur_catalogue_pas_badzipfile_brute(settings_test) -> None:
    """Une archive tronquée ou corrompue ne doit jamais laisser fuir `zipfile.BadZipFile` :
    c'est ce que corrige ce test — sans lui il échoue avec l'exception brute de la
    bibliothèque, hors du vocabulaire d'erreur du connecteur.
    """
    session = SessionFactice(contenu_zip=b"PK\x03\x04 ceci n'est pas une archive ZIP valide")
    ressource = resoudre_ressource(settings_test, session=session)

    with pytest.raises(ErreurCatalogueReferentiels, match="illisible") as excinfo:
        telecharger(ressource, settings_test, session=session)

    assert isinstance(excinfo.value.__cause__, zipfile.BadZipFile), "la cause d'origine doit être préservée (from)"
    assert isinstance(excinfo.value, ErreurDefinitive)
    assert not isinstance(excinfo.value, ErreurTransitoire)


def test_csv_qui_ne_decode_pas_selon_lencodage_declare_leve_une_erreur_de_contrat(settings_test) -> None:
    """Reproduit le cas réel documenté dans _referentiels_communs.verifier_encodage :
    un CSV extrait dont les octets ne respectent pas l'encodage déclaré (ici UTF-8).
    """
    session = SessionFactice(contenu_zip=_zip_avec(NOM_CSV_STANDARD, b"\xff\xfe pas de l'utf-8 valide"))
    ressource = resoudre_ressource(settings_test, session=session)

    with pytest.raises(ErreurContratReferentiels, match="utf-8"):
        telecharger(ressource, settings_test, session=session)


# ─── Erreurs réseau ─────────────────────────────────────────────────────────


def test_erreur_http_pendant_le_telechargement_de_larchive_leve_une_erreur_transitoire(settings_test) -> None:
    session = SessionFactice(zip_en_erreur=True)
    ressource = resoudre_ressource(settings_test, session=session)

    with pytest.raises(ErreurReseauReferentiels):
        telecharger(ressource, settings_test, session=session)


# ─── Transitoire contre définitif — même vocabulaire que Parcoursup, Sirene, IDÉO ─


def test_erreur_catalogue_est_definitive_pas_transitoire(settings_test) -> None:
    with pytest.raises(ErreurCatalogueReferentiels) as excinfo:
        resoudre_ressource(settings_test, session=SessionFactice(catalogue=_catalogue([])))

    assert isinstance(excinfo.value, ErreurTelechargementReferentiels)
    assert isinstance(excinfo.value, ErreurDefinitive)
    assert not isinstance(excinfo.value, ErreurTransitoire)


def test_erreur_reseau_est_transitoire_pas_definitive(settings_test) -> None:
    with pytest.raises(ErreurReseauReferentiels) as excinfo:
        resoudre_ressource(settings_test, session=SessionFactice(catalogue_en_erreur=True))

    assert isinstance(excinfo.value, ErreurTransitoire)
    assert not isinstance(excinfo.value, ErreurDefinitive)


# ─── Aucune URL de fichier en dur ─────────────────────────────────────────────


def test_aucune_url_rncp_en_dur() -> None:
    """Comme Sirene, RNCP n'a pas de gabarit d'URL fixe pour l'archive : rien ici ne doit en coder une."""
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "edumatch"
        / "ingestion"
        / "_referentiels_rncp.py"
    ).read_text(encoding="utf-8")

    assert "static.data.gouv.fr" not in source
    assert "repertoire-national-des-certifications" not in source


# ─── Membre ROME de la même archive (E18) ──────────────────────────────────


def test_telecharger_rome_extrait_le_fichier_rome_et_ecrit_le_manifeste(settings_test) -> None:
    """Le membre ROME est un fichier distinct du CSV standard, avec sa propre clé de manifeste."""
    session = SessionFactice()
    ressource = resoudre_ressource(settings_test, session=session)
    resultat = telecharger_rome(ressource, settings_test, session=session)

    assert resultat.telecharge is True
    assert resultat.source == "rncp"
    assert resultat.jeu == "rncp_rome"
    assert resultat.chemin == chemin_destination_rome(settings_test, "2026-08-29")
    assert resultat.chemin.name == "rncp_rome_2026-08-29.csv"
    assert resultat.chemin.read_bytes() == CONTENU_ROME_UTF8

    manifeste = json.loads((settings_test.external_dir / "referentiels" / "manifeste.json").read_text())
    assert "rncp_rome:2026-08-29" in manifeste
    assert "rncp:2026-08-29" not in manifeste, "telecharger_rome seul ne doit pas écrire la clé du CSV standard"


def test_telecharger_rome_et_telecharger_standard_coexistent_dans_le_meme_manifeste(settings_test) -> None:
    """Les deux membres de la même archive quotidienne s'écrivent côte à côte, sans se chevaucher."""
    session = SessionFactice()
    ressource = resoudre_ressource(settings_test, session=session)
    resultat_standard = telecharger(ressource, settings_test, session=session)
    resultat_rome = telecharger_rome(ressource, settings_test, session=session)

    assert resultat_standard.chemin != resultat_rome.chemin
    assert resultat_standard.chemin.exists() and resultat_rome.chemin.exists()
    assert session.appels_zip == 2, "chaque membre déclenche son propre téléchargement de l'archive (voir docstring)"


def test_telecharger_rome_second_appel_meme_jour_ne_retelecharge_pas(settings_test) -> None:
    session = SessionFactice()
    ressource = resoudre_ressource(settings_test, session=session)
    telecharger_rome(ressource, settings_test, session=session)
    resultat_second = telecharger_rome(ressource, settings_test, session=session)

    assert session.appels_zip == 1
    assert resultat_second.telecharge is False


def test_archive_sans_le_membre_rome_leve_une_erreur_catalogue(settings_test) -> None:
    session = SessionFactice(contenu_zip=_zip_avec(NOM_CSV_STANDARD, CONTENU_CSV_UTF8))
    ressource = resoudre_ressource(settings_test, session=session)

    with pytest.raises(ErreurCatalogueReferentiels, match="Aucun fichier"):
        telecharger_rome(ressource, settings_test, session=session)
