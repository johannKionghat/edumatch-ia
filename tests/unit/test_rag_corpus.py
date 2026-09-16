"""Tests du corpus documentaire de l'assistant (src/edumatch/rag/corpus.py).

Fixtures écrites à la main dans `tmp_path`, jamais les fichiers réels de
`data/samples/` (ceux-ci sont couverts par `tests/data/test_rag_corpus_reel.py`) :
ce module isole chaque règle — colonnes retenues, citation par ligne, les
deux formats de manifeste, jeu inconnu, fichier absent.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from edumatch.config import IdeoJeuConfig
from edumatch.rag.corpus import ErreurCorpusRag, charger_corpus

LIGNE_FORMATION_VALIDE: dict[str, str] = {
    "libellé formation principal": "BTS comptabilité et gestion",
    "libellé type formation": "formation de BTS",
    "durée": "2 ans",
    "niveau de sortie indicatif": "bac + 2",
    "code RNCP": "RNCP12345",
    "niveau de certification": "5",
    "libellé niveau de certification": "niveau 5",
    "tutelle": "Éducation nationale",
    "URL et ID Onisep": "https://www.onisep.fr/http/redirection/formation/slug/FOR.1",
    "domaine/sous-domaine": "gestion des entreprises, comptabilité/comptabilité",
    "date création": "01/01/2020",
    "date de modification": "01/01/2020",
}

LIGNE_METIER_VALIDE: dict[str, str] = {
    "libellé métier": "comptable",
    "lien site onisep.fr": "https://www.onisep.fr/http/redirection/metier/slug/MET.1",
    "nom publication": "Travailler dans la gestion",
    "collection": "Parcours",
    "année": "2023",
    "gencod": "9782273000000",
    "GFE": "GFE F : gestion, comptabilité",
    "code ROME": "M1203",
    "libellé ROME": "comptabilité",
    "lien ROME": "https://candidat.francetravail.fr/metierscope/fiche-metier/M1203",
    "domaine/sous-domaine": "gestion des entreprises, comptabilité/comptabilité",
    "date création": "01/01/2020",
    "date de modification": "01/01/2020",
}


def _ecrire_csv(chemin: Path, lignes: list[dict[str, str]]) -> None:
    colonnes = sorted({colonne for ligne in lignes for colonne in ligne})
    with chemin.open("w", encoding="utf-8-sig", newline="") as fichier:
        ecrivain = csv.DictWriter(fichier, fieldnames=colonnes, delimiter=";", restval="")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)


@pytest.fixture()
def config_jeux() -> dict[str, IdeoJeuConfig]:
    return {
        "formations": IdeoJeuConfig(
            url="https://exemple.test/ideo/formations.csv", encodage="utf-8", delimiteur=";", licence="ODbL (odc-odbl)"
        ),
        "metiers": IdeoJeuConfig(
            url="https://exemple.test/ideo/metiers.csv", encodage="utf-8", delimiteur=";", licence="ODbL (odc-odbl)"
        ),
    }


@pytest.fixture()
def dossier_ideo(tmp_path: Path) -> Path:
    dossier = tmp_path / "ideo"
    dossier.mkdir()
    _ecrire_csv(dossier / "formations.csv", [dict(LIGNE_FORMATION_VALIDE)])
    _ecrire_csv(dossier / "metiers.csv", [dict(LIGNE_METIER_VALIDE)])
    return dossier


def test_charger_corpus_produit_un_document_par_ligne(
    dossier_ideo: Path, config_jeux: dict[str, IdeoJeuConfig]
) -> None:
    documents = charger_corpus(dossier_ideo, config_jeux, ("formations", "metiers"))
    assert len(documents) == 2
    jeux = {document.jeu for document in documents}
    assert jeux == {"formations", "metiers"}


def test_le_texte_reprend_les_colonnes_declarees_dans_l_ordre(
    dossier_ideo: Path, config_jeux: dict[str, IdeoJeuConfig]
) -> None:
    documents = charger_corpus(dossier_ideo, config_jeux, ("formations",))
    (document,) = documents
    assert document.texte.startswith("BTS comptabilité et gestion — formation de BTS — 2 ans")
    # Le code RNCP n'est pas une colonne de COLONNES_TEXTE : il ne doit pas apparaître dans le
    # texte indexé, seulement servir de clé de réconciliation ailleurs (E18).
    assert "RNCP12345" not in document.texte


def test_url_de_la_ligne_prime_sur_l_url_du_jeu(dossier_ideo: Path, config_jeux: dict[str, IdeoJeuConfig]) -> None:
    documents = charger_corpus(dossier_ideo, config_jeux, ("formations",))
    (document,) = documents
    assert document.url == "https://www.onisep.fr/http/redirection/formation/slug/FOR.1"


def test_url_du_jeu_sert_de_repli_si_la_ligne_n_en_porte_pas(
    tmp_path: Path, config_jeux: dict[str, IdeoJeuConfig]
) -> None:
    dossier = tmp_path / "ideo"
    dossier.mkdir()
    ligne = dict(LIGNE_FORMATION_VALIDE)
    ligne["URL et ID Onisep"] = ""
    _ecrire_csv(dossier / "formations.csv", [ligne])
    _ecrire_csv(dossier / "metiers.csv", [dict(LIGNE_METIER_VALIDE)])

    documents = charger_corpus(dossier, config_jeux, ("formations",))
    (document,) = documents
    assert document.url == "https://exemple.test/ideo/formations.csv"


def test_licence_reprise_de_la_configuration_du_jeu(dossier_ideo: Path, config_jeux: dict[str, IdeoJeuConfig]) -> None:
    documents = charger_corpus(dossier_ideo, config_jeux, ("formations",))
    assert all(document.licence == "ODbL (odc-odbl)" for document in documents)


def test_jeu_demande_mais_non_configure_leve_erreur(dossier_ideo: Path) -> None:
    with pytest.raises(ErreurCorpusRag, match="absent de"):
        charger_corpus(dossier_ideo, {}, ("formations",))


def test_jeu_non_indexable_leve_erreur(tmp_path: Path, config_jeux: dict[str, IdeoJeuConfig]) -> None:
    """`structures_secondaire` n'a pas de colonnes de texte déclarées : voir COLONNES_TEXTE."""
    dossier = tmp_path / "ideo"
    dossier.mkdir()
    config_jeux["structures_secondaire"] = IdeoJeuConfig(
        url="https://exemple.test/ideo/structures.csv", encodage="utf-8", delimiteur=";", licence="ODbL (odc-odbl)"
    )
    _ecrire_csv(dossier / "structures_secondaire.csv", [{"nom": "Lycée X"}])
    with pytest.raises(ErreurCorpusRag, match="non indexable"):
        charger_corpus(dossier, config_jeux, ("structures_secondaire",))


def test_fichier_absent_leve_erreur_explicite(tmp_path: Path, config_jeux: dict[str, IdeoJeuConfig]) -> None:
    dossier = tmp_path / "ideo_vide"
    dossier.mkdir()
    with pytest.raises(ErreurCorpusRag, match="introuvable"):
        charger_corpus(dossier, config_jeux, ("formations",))


def test_colonne_attendue_absente_leve_erreur_de_contrat(tmp_path: Path, config_jeux: dict[str, IdeoJeuConfig]) -> None:
    dossier = tmp_path / "ideo"
    dossier.mkdir()
    ligne = dict(LIGNE_FORMATION_VALIDE)
    del ligne["libellé formation principal"]
    _ecrire_csv(dossier / "formations.csv", [ligne])
    with pytest.raises(ErreurCorpusRag, match="Colonnes attendues absentes"):
        charger_corpus(dossier, config_jeux, ("formations",))


def test_ligne_sans_aucun_champ_textuel_est_ignoree(tmp_path: Path, config_jeux: dict[str, IdeoJeuConfig]) -> None:
    dossier = tmp_path / "ideo"
    dossier.mkdir()
    ligne_vide = dict.fromkeys(LIGNE_FORMATION_VALIDE, "")
    _ecrire_csv(dossier / "formations.csv", [ligne_vide, dict(LIGNE_FORMATION_VALIDE)])
    documents = charger_corpus(dossier, config_jeux, ("formations",))
    assert len(documents) == 1


# ─── Date de collecte : les deux formats de manifeste du dépôt ──────────────


def test_date_collecte_depuis_le_manifeste_des_referentiels_complets(
    dossier_ideo: Path, config_jeux: dict[str, IdeoJeuConfig]
) -> None:
    manifeste = dossier_ideo.parent / "manifeste.json"
    manifeste.write_text(
        json.dumps({"ideo:formations": {"date_telechargement": "2026-08-29T04:10:05+00:00"}}), encoding="utf-8"
    )
    documents = charger_corpus(dossier_ideo, config_jeux, ("formations",), manifeste)
    assert all(document.date_collecte == "2026-08-29T04:10:05+00:00" for document in documents)


def test_date_collecte_depuis_le_manifeste_des_echantillons(
    dossier_ideo: Path, config_jeux: dict[str, IdeoJeuConfig]
) -> None:
    manifeste = dossier_ideo.parent / "manifeste.json"
    manifeste.write_text(
        json.dumps({"echantillons": [{"source": "ideo_formations", "date_source": "2026-08-29T04:10:05+00:00"}]}),
        encoding="utf-8",
    )
    documents = charger_corpus(dossier_ideo, config_jeux, ("formations",), manifeste)
    assert all(document.date_collecte == "2026-08-29T04:10:05+00:00" for document in documents)


def test_manifeste_absent_ne_bloque_pas_et_declare_l_absence(
    dossier_ideo: Path, config_jeux: dict[str, IdeoJeuConfig]
) -> None:
    documents = charger_corpus(dossier_ideo, config_jeux, ("formations",), dossier_ideo.parent / "absent.json")
    assert all(document.date_collecte is None for document in documents)
