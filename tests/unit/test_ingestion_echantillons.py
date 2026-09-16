"""Tests du générateur d'échantillons (src/edumatch/ingestion/echantillons.py).

Aucun accès aux 4,6 Go de sources réelles : chaque test construit ses propres
fichiers minuscules (CSV, Parquet) dans un dossier temporaire. Couvre le cœur
du sujet de l'étape : l'exclusion des colonnes personnelles de Sirene, le
déterminisme de l'échantillonnage systématique, et le respect du BOM des CSV
sources.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from edumatch.config import Settings, load_settings
from edumatch.ingestion.echantillons import (
    COLONNES_ETABLISSEMENT,
    COLONNES_PERSONNELLES_UNITE_LEGALE,
    _colonnes_sirene,
    _echantillonner_parquet,
    _indices_systematiques,
    _lire_csv,
    _provenance_parcoursup,
    generer_tous_les_echantillons,
)

# ─── _indices_systematiques : le cœur du déterminisme ────────────────────────


def test_indices_systematiques_deterministe() -> None:
    """Deux appels avec les mêmes arguments retournent exactement la même liste."""
    assert _indices_systematiques(43_896_818, 500) == _indices_systematiques(43_896_818, 500)


def test_indices_systematiques_balaie_tout_le_fichier() -> None:
    """Le dernier index retenu doit être proche de la fin, pas seulement en tête (pas les N premières lignes)."""
    indices = _indices_systematiques(1000, 10)
    assert indices[0] == 0
    assert indices[-1] >= 900  # pas = 100, dernier index = 900


def test_indices_systematiques_cas_limites() -> None:
    assert _indices_systematiques(0, 10) == []
    assert _indices_systematiques(10, 0) == []
    assert _indices_systematiques(3, 100) == [0, 1, 2]  # moins de lignes que la cible : tout est retenu


# ─── Minimisation Sirene : le sujet de fond de l'étape ───────────────────────


def test_colonnes_sirene_exclut_les_colonnes_personnelles_unite_legale() -> None:
    disponibles = list(COLONNES_PERSONNELLES_UNITE_LEGALE) + ["siren", "dateCreationUniteLegale"]
    retenues, exclues = _colonnes_sirene("StockUniteLegale", disponibles)
    assert set(retenues) == {"siren", "dateCreationUniteLegale"}
    assert set(exclues) == COLONNES_PERSONNELLES_UNITE_LEGALE


def test_colonnes_sirene_etablissement_se_limite_aux_9_colonnes_utiles() -> None:
    disponibles = list(COLONNES_ETABLISSEMENT) + ["enseigne1Etablissement", "libelleVoieEtablissement"]
    retenues, exclues = _colonnes_sirene("StockEtablissement", disponibles)
    assert set(retenues) == set(COLONNES_ETABLISSEMENT)
    assert "enseigne1Etablissement" in exclues


def test_colonnes_sirene_historique_etablissement_sans_restriction() -> None:
    """Pas de colonne personnelle sur ce fichier : aucune restriction à appliquer."""
    disponibles = ["siret", "dateFin", "enseigne1Etablissement"]
    retenues, exclues = _colonnes_sirene("StockEtablissementHistorique", disponibles)
    assert retenues == disponibles
    assert exclues == []


# ─── Échantillonnage Parquet en flux ──────────────────────────────────────────


def _ecrire_parquet_synthetique(chemin: Path, n_lignes: int, colonnes: dict[str, list]) -> None:
    table = pa.table(colonnes)
    pq.write_table(table, chemin)


def test_echantillonner_parquet_respecte_la_cible_et_le_pas(tmp_path: Path) -> None:
    n = 1000
    chemin = tmp_path / "source.parquet"
    _ecrire_parquet_synthetique(chemin, n, {"id": list(range(n)), "valeur": [str(i) for i in range(n)]})

    table, total = _echantillonner_parquet(chemin, ["id", "valeur"], cible=50, taille_lot=97)

    assert total == n
    assert table.num_rows == 50
    # Les identifiants retenus doivent être un sous-ensemble régulier de 0..999,
    # jamais les 50 premiers (id 0..49) : preuve que ce n'est pas "les N premières lignes".
    ids = table.column("id").to_pylist()
    assert ids[0] == 0
    assert ids[-1] >= 950
    assert ids == sorted(ids)


def test_echantillonner_parquet_deterministe_a_travers_deux_appels(tmp_path: Path) -> None:
    n = 733  # nombre premier, pour ne pas retomber sur un pas trivial
    chemin = tmp_path / "source.parquet"
    _ecrire_parquet_synthetique(chemin, n, {"id": list(range(n))})

    table1, _ = _echantillonner_parquet(chemin, ["id"], cible=30, taille_lot=50)
    table2, _ = _echantillonner_parquet(chemin, ["id"], cible=30, taille_lot=50)

    assert table1.column("id").to_pylist() == table2.column("id").to_pylist()


def test_echantillonner_parquet_fichier_vide(tmp_path: Path) -> None:
    chemin = tmp_path / "vide.parquet"
    _ecrire_parquet_synthetique(chemin, 0, {"id": [], "valeur": []})
    table, total = _echantillonner_parquet(chemin, ["id", "valeur"], cible=50, taille_lot=100)
    assert total == 0
    assert table.num_rows == 0


# ─── Lecture CSV : BOM et champs multi-lignes entre guillemets ───────────────


def test_lire_csv_respecte_les_champs_multilignes_entre_guillemets(tmp_path: Path) -> None:
    """Le piège déjà rencontré sur le RNCP : un retour à la ligne interne à un champ cité n'est pas une nouvelle ligne."""
    chemin = tmp_path / "multi.csv"
    chemin.write_text('"a";"b"\n"1";"texte\nsur deux lignes"\n"2";"simple"\n', encoding="utf-8", newline="")

    entete, lignes = _lire_csv(chemin, "utf-8", ";")

    assert entete == ["a", "b"]
    assert len(lignes) == 2  # pas 3 : le retour à la ligne interne n'a pas été compté comme une ligne


def test_lire_csv_utf8_sig_retire_le_bom(tmp_path: Path) -> None:
    chemin = tmp_path / "avec_bom.csv"
    chemin.write_bytes("﻿session;cod_uai\n1;A\n".encode())

    entete, _ = _lire_csv(chemin, "utf-8-sig", ";")

    assert entete[0] == "session"  # pas "﻿session"


# ─── Bout en bout, sur un jeu de données synthétique minuscule ───────────────


@pytest.fixture()
def settings_synthetiques(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Un Settings réel (schéma de configuration complet), pointé vers des sources minuscules et jetables."""
    racine = tmp_path / "donnees"
    (racine / "raw" / "parcoursup").mkdir(parents=True)
    (racine / "raw" / "sirene").mkdir(parents=True)
    (racine / "external" / "referentiels" / "ideo").mkdir(parents=True)
    (racine / "external" / "referentiels" / "rncp").mkdir(parents=True)

    # Parcoursup : deux millésimes, BOM sur l'un des deux comme la vraie source.
    (racine / "raw" / "parcoursup" / "parcoursup_2024.csv").write_bytes(
        "﻿session;cod_uai;capa_fin\n2024;A1;10\n2024;A2;20\n2024;A3;30\n".encode()
    )
    (racine / "raw" / "parcoursup" / "parcoursup_2025.csv").write_text(
        "session;cod_uai;capa_fin;nouvelle_colonne\n2025;A1;10;x\n2025;A2;20;y\n", encoding="utf-8"
    )

    # Sirene : StockEtablissement (colonnes utiles seulement présentes) et
    # StockUniteLegale (avec colonnes personnelles, à exclure).
    pq.write_table(
        pa.table(
            {
                "siret": [str(i) for i in range(20)],
                "activitePrincipaleEtablissement": ["47.11Z"] * 20,
                "etatAdministratifEtablissement": ["A"] * 20,
            }
        ),
        racine / "raw" / "sirene" / "StockEtablissement.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "siren": [str(i) for i in range(20)],
                "nomUniteLegale": [f"NOM{i}" for i in range(20)],
                "sexeUniteLegale": ["M"] * 20,
                "categorieJuridiqueUniteLegale": ["1000"] * 20,
            }
        ),
        racine / "raw" / "sirene" / "StockUniteLegale.parquet",
    )

    # IDÉO : un seul jeu, "formations", avec BOM.
    (racine / "external" / "referentiels" / "ideo" / "formations.csv").write_bytes(
        "﻿\"code NSF\";\"libellé\"\n\"310\";\"commerce\"\n\"320\";\"informatique\"\n".encode()
    )

    # RNCP : un export, avec un champ multi-lignes.
    (racine / "external" / "referentiels" / "rncp" / "rncp_2026-08-29.csv").write_text(
        '"Id_Fiche";"Intitule"\n"1";"simple"\n"2";"sur\ndeux lignes"\n', encoding="utf-8", newline=""
    )

    # Manifestes de collecte synthétiques : R3, la provenance (url, date, empreinte
    # de la source) doit être reprise depuis ces fichiers, jamais versionnés,
    # jamais inventée.
    (racine / "raw" / "parcoursup" / "manifeste.json").write_text(
        json.dumps(
            {
                "2024": {
                    "url": "https://exemple.test/parcoursup-2024.csv",
                    "date_telechargement": "2026-01-01T00:00:00+00:00",
                    "empreinte_sha256": "a" * 64,
                },
                "2025": {
                    "url": "https://exemple.test/parcoursup-2025.csv",
                    "date_telechargement": "2026-01-02T00:00:00+00:00",
                    "empreinte_sha256": "b" * 64,
                },
            }
        ),
        encoding="utf-8",
    )
    (racine / "raw" / "sirene" / "manifeste.json").write_text(
        json.dumps(
            {
                "StockEtablissement": {
                    "url": "https://exemple.test/StockEtablissement.parquet",
                    "date_publication_stock": "2026-01-01T00:00:00+00:00",
                    "empreinte_sha256": "c" * 64,
                },
                "StockUniteLegale": {
                    "url": "https://exemple.test/StockUniteLegale.parquet",
                    "date_publication_stock": "2026-01-01T00:00:00+00:00",
                    "empreinte_sha256": "d" * 64,
                },
            }
        ),
        encoding="utf-8",
    )
    (racine / "external" / "referentiels" / "manifeste.json").write_text(
        json.dumps(
            {
                "ideo:formations": {
                    "url": "https://exemple.test/ideo-formations.csv",
                    "date_telechargement": "2026-01-01T00:00:00+00:00",
                    "empreinte_sha256": "e" * 64,
                },
                "rncp:2026-08-29": {
                    "url": "https://exemple.test/rncp.csv",
                    "date_publication": "2026-08-29T00:00:00+00:00",
                    "empreinte_sha256": "f" * 64,
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("EDUMATCH_DATA_ROOT", str(racine))
    return load_settings("prod")


class _ParametresAvecSamplesDir:
    """Enveloppe un Settings réel : seul `samples_dir` est redéfini, vers un dossier jetable de test."""

    def __init__(self, settings: Settings, samples_dir: Path) -> None:
        self._settings = settings
        self._samples_dir = samples_dir

    def __getattr__(self, nom: str) -> object:
        return getattr(self._settings, nom)

    @property
    def samples_dir(self) -> Path:
        return self._samples_dir


def test_generer_tous_les_echantillons_bout_en_bout(tmp_path: Path, settings_synthetiques: Settings) -> None:
    """Sur un jeu synthétique minuscule, mais avec la configuration réelle de champs et de fichiers du projet."""
    sortie = tmp_path / "echantillons"
    parametres = _ParametresAvecSamplesDir(settings_synthetiques, sortie)

    resultats = generer_tous_les_echantillons(parametres)

    sources = {r.source for r in resultats}
    assert "parcoursup_2024" in sources
    assert "parcoursup_2025" in sources
    assert "StockEtablissement" in sources
    assert "StockUniteLegale" in sources
    assert "ideo_formations" in sources
    assert "rncp" in sources

    # R3 : chaque résultat porte la provenance de la source (url, date, empreinte),
    # reprise du manifeste de collecte — pas inventée, pas absente.
    for resultat in resultats:
        assert resultat.url.startswith("https://exemple.test/")
        assert resultat.date_source
        assert len(resultat.empreinte_sha256_source) == 64

    # Le BOM ne doit fuiter dans aucun en-tête écrit.
    for chemin in [sortie / "parcoursup" / "parcoursup_2024.csv", sortie / "referentiels" / "ideo" / "formations.csv"]:
        premiere_ligne = chemin.read_text(encoding="utf-8").splitlines()[0]
        assert not premiere_ligne.startswith("﻿")

    # Aucune colonne personnelle dans l'échantillon StockUniteLegale.
    table_ul = pq.read_table(sortie / "sirene" / "StockUniteLegale.parquet")
    assert COLONNES_PERSONNELLES_UNITE_LEGALE.isdisjoint(table_ul.schema.names)
    assert "siren" in table_ul.schema.names  # les colonnes non personnelles restent

    # Le manifeste existe et documente chaque échantillon.
    manifeste = json.loads((sortie / "manifeste.json").read_text(encoding="utf-8"))
    assert len(manifeste["echantillons"]) == len(resultats)


def test_provenance_manquante_bloque_plutot_que_de_produire_un_manifeste_incomplet(
    settings_synthetiques: Settings,
) -> None:
    """R3 : pas de fallback silencieux — un manifeste source absent ou incomplet doit arrêter la génération."""
    (settings_synthetiques.raw_dir / "parcoursup" / "manifeste.json").unlink()
    with pytest.raises(FileNotFoundError):
        _provenance_parcoursup(settings_synthetiques, 2024)


def test_regeneration_est_deterministe_sur_jeu_synthetique(tmp_path: Path, settings_synthetiques: Settings) -> None:
    """Preuve du déterminisme demandé par l'étape : deux générations produisent des fichiers identiques."""
    sortie1 = tmp_path / "run1"
    sortie2 = tmp_path / "run2"
    generer_tous_les_echantillons(_ParametresAvecSamplesDir(settings_synthetiques, sortie1))
    generer_tous_les_echantillons(_ParametresAvecSamplesDir(settings_synthetiques, sortie2))

    fichiers1 = sorted(p.relative_to(sortie1) for p in sortie1.rglob("*") if p.is_file() and p.name != "manifeste.json")
    fichiers2 = sorted(p.relative_to(sortie2) for p in sortie2.rglob("*") if p.is_file() and p.name != "manifeste.json")
    assert fichiers1 == fichiers2
    for relatif in fichiers1:
        assert (sortie1 / relatif).read_bytes() == (sortie2 / relatif).read_bytes()
