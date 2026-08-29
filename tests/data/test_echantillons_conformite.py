"""Contrat de `data/samples/` — l'échantillon versionné, pas les sources complètes.

Ce fichier ne lit jamais `data/raw/` ni `data/external/` : c'est précisément
la preuve attendue par l'étape E08. La suite entière doit pouvoir tourner sur
un poste qui n'a jamais téléchargé les 4,6 Go de sources.

Contrôle de colonnes (R5) — liste blanche, pas liste noire importée du code
sous contrôle :

    Un test qui importe `COLONNES_PERSONNELLES_UNITE_LEGALE` depuis
    `edumatch.ingestion.echantillons` et se contente de vérifier qu'aucune
    de ces colonnes n'est présente ne teste rien de son propre chef : si la
    liste est vidée dans le module (par erreur, ou parce qu'une nouvelle
    colonne d'identité apparaît sous un autre nom), le test reste vert. Le
    module se certifierait lui-même.

    Ici, chaque fichier Sirene a sa liste blanche de colonnes attendues,
    écrite en dur dans ce fichier de test, indépendante du code de
    production. Toute colonne absente de cette liste — qu'elle soit
    personnelle ou seulement nouvelle et non examinée — fait échouer le
    test. C'est le sens de « refusée par défaut » : le test ne sait pas
    qu'une colonne est sans risque tant qu'elle n'a pas été ajoutée ici
    explicitement, après examen.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pyarrow.parquet as pq

from edumatch.config import get_settings

SAMPLES_DIR = get_settings().samples_dir

# Liste blanche par fichier Sirene — voir la docstring du module ci-dessus.
# Toute colonne qui n'y figure pas est refusée, y compris une colonne que
# l'INSEE ajouterait sans prévenir (déjà arrivé : NAF25, ajoutée le
# 16/12/2025). Une colonne personnelle ne doit JAMAIS y figurer.
COLONNES_AUTORISEES: dict[str, frozenset[str]] = {
    "StockEtablissement": frozenset(
        {
            "siret",
            "activitePrincipaleEtablissement",
            "nomenclatureActivitePrincipaleEtablissement",
            "activitePrincipaleNAF25Etablissement",
            "codeCommuneEtablissement",
            "trancheEffectifsEtablissement",
            "etatAdministratifEtablissement",
            "caractereEmployeurEtablissement",
            "dateCreationEtablissement",
        }
    ),
    "StockEtablissementHistorique": frozenset(
        {
            "siren",
            "nic",
            "siret",
            "dateFin",
            "dateDebut",
            "etatAdministratifEtablissement",
            "changementEtatAdministratifEtablissement",
            "enseigne1Etablissement",
            "enseigne2Etablissement",
            "enseigne3Etablissement",
            "changementEnseigneEtablissement",
            "denominationUsuelleEtablissement",
            "changementDenominationUsuelleEtablissement",
            "activitePrincipaleEtablissement",
            "nomenclatureActivitePrincipaleEtablissement",
            "changementActivitePrincipaleEtablissement",
            "caractereEmployeurEtablissement",
            "changementCaractereEmployeurEtablissement",
        }
    ),
    "StockUniteLegale": frozenset(
        {
            "siren",
            "statutDiffusionUniteLegale",
            "unitePurgeeUniteLegale",
            "dateCreationUniteLegale",
            "sigleUniteLegale",
            "identifiantAssociationUniteLegale",
            "trancheEffectifsUniteLegale",
            "anneeEffectifsUniteLegale",
            "dateDernierTraitementUniteLegale",
            "nombrePeriodesUniteLegale",
            "categorieEntreprise",
            "anneeCategorieEntreprise",
            "dateDebut",
            "etatAdministratifUniteLegale",
            "denominationUniteLegale",
            "denominationUsuelle1UniteLegale",
            "denominationUsuelle2UniteLegale",
            "denominationUsuelle3UniteLegale",
            "categorieJuridiqueUniteLegale",
            "activitePrincipaleUniteLegale",
            "nomenclatureActivitePrincipaleUniteLegale",
            "nicSiegeUniteLegale",
            "economieSocialeSolidaireUniteLegale",
            "societeMissionUniteLegale",
            "caractereEmployeurUniteLegale",
            "activitePrincipaleNAF25UniteLegale",
        }
    ),
    "StockUniteLegaleHistorique": frozenset(
        {
            "siren",
            "dateFin",
            "dateDebut",
            "etatAdministratifUniteLegale",
            "changementEtatAdministratifUniteLegale",
            "changementNomUniteLegale",
            "changementNomUsageUniteLegale",
            "denominationUniteLegale",
            "changementDenominationUniteLegale",
            "denominationUsuelle1UniteLegale",
            "denominationUsuelle2UniteLegale",
            "denominationUsuelle3UniteLegale",
            "changementDenominationUsuelleUniteLegale",
            "categorieJuridiqueUniteLegale",
            "changementCategorieJuridiqueUniteLegale",
            "activitePrincipaleUniteLegale",
            "nomenclatureActivitePrincipaleUniteLegale",
            "changementActivitePrincipaleUniteLegale",
            "nicSiegeUniteLegale",
            "changementNicSiegeUniteLegale",
            "economieSocialeSolidaireUniteLegale",
            "changementEconomieSocialeSolidaireUniteLegale",
            "societeMissionUniteLegale",
            "changementSocieteMissionUniteLegale",
            "caractereEmployeurUniteLegale",
            "changementCaractereEmployeurUniteLegale",
        }
    ),
}

# Colonnes qui, si elles apparaissaient dans n'importe quel fichier Sirene,
# constitueraient une identité directe de personne physique — rappelées ici
# indépendamment de toute liste du module de production, pour un message
# d'échec explicite plutôt qu'une simple absence de la liste blanche.
COLONNES_IDENTITE_DIRECTE = frozenset(
    {
        "sexeUniteLegale",
        "prenom1UniteLegale",
        "prenom2UniteLegale",
        "prenom3UniteLegale",
        "prenom4UniteLegale",
        "prenomUsuelUniteLegale",
        "pseudonymeUniteLegale",
        "nomUniteLegale",
        "nomUsageUniteLegale",
    }
)


def _lire_manifeste() -> dict:
    return json.loads((SAMPLES_DIR / "manifeste.json").read_text(encoding="utf-8"))


def test_manifeste_existe_et_documente_chaque_echantillon() -> None:
    manifeste = _lire_manifeste()
    assert manifeste["echantillons"], "Le manifeste ne doit pas être vide."
    champs_requis = (
        "source",
        "chemin_source",
        "chemin_sortie",
        "lignes_source",
        "lignes_echantillon",
        "licence",
        "url",
        "date_source",
        "empreinte_sha256_source",
    )
    for entree in manifeste["echantillons"]:
        for champ in champs_requis:
            assert champ in entree, f"Champ manquant dans le manifeste : {champ}"
            assert entree[champ], f"Champ vide dans le manifeste : {champ} ({entree['source']})"


def test_aucune_colonne_hors_liste_blanche_dans_les_fichiers_sirene() -> None:
    """Le sujet central de l'étape : liste blanche, pas liste noire — voir docstring du module."""
    fichiers = sorted((SAMPLES_DIR / "sirene").glob("*.parquet"))
    assert fichiers, "Aucun échantillon Sirene trouvé — la génération a-t-elle été lancée ?"
    for chemin in fichiers:
        nom = chemin.stem
        assert nom in COLONNES_AUTORISEES, f"Fichier Sirene inconnu, sans liste blanche déclarée : {nom}"
        colonnes = set(pq.ParquetFile(chemin).schema_arrow.names)
        inconnues = colonnes - COLONNES_AUTORISEES[nom]
        assert not inconnues, f"{chemin.name} porte des colonnes hors liste blanche : {inconnues}"
        identite = colonnes & COLONNES_IDENTITE_DIRECTE
        assert not identite, f"{chemin.name} contient une colonne d'identité directe : {identite}"


def test_parcoursup_couvre_les_huit_millesimes_et_la_derive_de_schema() -> None:
    """Sans les huit millésimes, la réconciliation de schéma (E15) ne serait pas testable sur cet échantillon."""
    dossier = SAMPLES_DIR / "parcoursup"
    millesimes_presents = {int(p.stem.split("_")[-1]) for p in dossier.glob("parcoursup_*.csv")}
    assert millesimes_presents == set(range(2018, 2026))

    nb_colonnes = {}
    for annee in sorted(millesimes_presents):
        with (dossier / f"parcoursup_{annee}.csv").open(encoding="utf-8", newline="") as flux:
            entete = next(csv.reader(flux, delimiter=";"))
            nb_colonnes[annee] = len(entete)
            assert not entete[0].startswith("﻿"), "Le BOM source ne doit pas rester collé au premier en-tête."

    # La dérive de schéma documentée dans les notes de cadrage doit être visible sur l'échantillon.
    assert nb_colonnes[2018] < nb_colonnes[2019] < nb_colonnes[2020] <= nb_colonnes[2021]
    assert nb_colonnes[2021] == nb_colonnes[2022] == nb_colonnes[2023] == nb_colonnes[2024] == nb_colonnes[2025]


def test_echantillons_sirene_lisibles_et_non_vides() -> None:
    for chemin in sorted((SAMPLES_DIR / "sirene").glob("*.parquet")):
        table = pq.read_table(chemin)
        assert table.num_rows > 0, f"{chemin.name} est vide."


def test_echantillon_rncp_conserve_les_champs_multilignes() -> None:
    """Preuve que la lecture par le module csv, pas par comptage de lignes, a été respectée ici aussi."""
    chemin = SAMPLES_DIR / "referentiels" / "rncp" / "rncp_echantillon.csv"
    with chemin.open(encoding="utf-8", newline="") as flux:
        lignes = list(csv.reader(flux, delimiter=";"))
    entete, corps = lignes[0], lignes[1:]
    assert corps, "L'échantillon RNCP ne doit pas être vide."
    for ligne in corps:
        assert len(ligne) == len(entete), "Une ligne RNCP mal reconstituée trahirait un comptage par ligne physique."


def test_echantillons_ideo_presents_pour_les_quatre_jeux() -> None:
    dossier = SAMPLES_DIR / "referentiels" / "ideo"
    jeux_attendus = {"formations", "metiers", "structures_secondaire", "structures_superieur"}
    presents = {p.stem for p in dossier.glob("*.csv")}
    assert jeux_attendus <= presents


def test_poids_total_reste_raisonnable() -> None:
    """`data/samples/` doit rester une exception versionnée légère, pas un second dépôt de données."""
    poids_octets = sum(p.stat().st_size for p in SAMPLES_DIR.rglob("*") if p.is_file())
    assert poids_octets < 10 * 1024 * 1024, (
        f"data/samples/ pèse {poids_octets / 1024:.0f} Ko : au-delà de 10 Mo, ce n'est plus un échantillon léger."
    )


def test_readme_documente_licence_regime_juridique_et_exclusions() -> None:
    readme = (SAMPLES_DIR / "README.md").read_text(encoding="utf-8")
    mentions_attendues = (
        "ODbL",
        "Licence Ouverte",
        "pseudonymisation",
        "systématique",
        "intérêt légitime",
    )
    for mention in mentions_attendues:
        assert mention.lower() in readme.lower(), f"README de data/samples/ : mention absente : {mention}"


def test_licence_ideo_dediee_presente() -> None:
    """R4 : un tiers qui récupère `referentiels/ideo/` seul doit trouver la licence à côté des CSV."""
    chemin = SAMPLES_DIR / "referentiels" / "ideo" / "LICENSE"
    assert chemin.exists(), "referentiels/ideo/LICENSE absent : la licence ODbL doit accompagner les CSV."
    contenu = chemin.read_text(encoding="utf-8")
    assert "odbl" in contenu.lower() or "opendatacommons" in contenu.lower()
