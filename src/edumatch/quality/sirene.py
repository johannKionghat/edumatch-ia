"""Contrôles qualité de `StockEtablissement` (E14), en flux, projection sur 9 colonnes.

Le fichier complet porte 43,9 millions de lignes et 54 colonnes (2,2 Go en
Parquet) : on ne le charge jamais entièrement en mémoire pour le valider, pas
plus qu'on ne le nettoie ligne à ligne. Ce module lit par lots
(`pyarrow.ParquetFile.iter_batches`), en ne décodant que les 9 colonnes utiles
au projet (`01-donnees/sources.md`) — la même projection que le job Spark
d'agrégation (E17), appliquée ici à la validation plutôt qu'au calcul.

Grâce à cette projection, les contrôles ne s'appuient pas sur Pandera comme
`quality/parcoursup.py` : un DataFrame Pandera couvrirait un lot, pas le
fichier entier, et les compteurs de complétude devraient de toute façon être
accumulés lot par lot à la main — Pandera n'apporterait alors rien qu'un
compteur `dict` ordinaire ne fasse aussi bien, pour un coût de dépendance
identique. Voir `edumatch.quality.__init__` pour l'arbitrage complet.

Trois nuances mesurées sur l'échantillon versionné et le fichier réel avant
d'écrire ces contrôles :

1. `trancheEffectifsEtablissement` porte le code `NN` (« non renseigné ») sur
   475 des 500 lignes de l'échantillon : ce n'est pas une valeur manquante,
   c'est une valeur documentée. Elle n'est donc jamais soumise au seuil de
   complétude.
2. `activitePrincipaleNAF25Etablissement` est vide sur 296 des 500 lignes de
   l'échantillon : la colonne n'existe dans le répertoire que depuis le
   16/12/2025, en anticipation de la bascule complète vers la nomenclature
   NAF 2025 (janvier 2027). Vide n'y signifie pas incomplet, pas plus que
   `acc_term` côté Parcoursup.
3. Le format du code NAF (`68.20B`, deux chiffres, un point, deux chiffres et
   une lettre) ne s'applique qu'à la nomenclature `NAFRev2` :
   `nomenclatureActivitePrincipaleEtablissement` porte aussi `NAF1993`,
   `NAP` et `NAFRev1` sur des établissements plus anciens, dont les codes ont
   un format différent (`70.3C`, `67.01`...). Un motif unique appliqué à
   toutes les nomenclatures aurait signalé à tort 111 des 500 lignes de
   l'échantillon.
4. `dateCreationEtablissement` postérieure à aujourd'hui n'est pas en soi une
   anomalie : une entreprise française peut être immatriculée par anticipation
   de son démarrage réel. Mesuré sur le fichier complet (43 896 818 lignes) :
   **10 613 dates dans les cinq ans à venir** (immatriculations anticipées
   plausibles, jusqu'à quelques mois), contre **5 dates au-delà** — dont une à
   l'année 5015, qui n'a plus rien d'une anticipation administrative. Le seuil
   de cinq ans sépare les deux régimes ; en deçà, avertissement ; au-delà,
   blocage.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from edumatch.config import Settings, get_settings
from edumatch.quality._diagnostic import Anomalie, Gravite, RapportControle, fusionner
from edumatch.quality._fraicheur import controler_fraicheur

COLONNES_UTILES: tuple[str, ...] = (
    "siret",
    "activitePrincipaleEtablissement",
    "nomenclatureActivitePrincipaleEtablissement",
    "activitePrincipaleNAF25Etablissement",
    "codeCommuneEtablissement",
    "trancheEffectifsEtablissement",
    "etatAdministratifEtablissement",
    "caractereEmployeurEtablissement",
    "dateCreationEtablissement",
)

# Colonnes structurellement complètes par construction : le SIRET est la clé
# de la ligne, l'état administratif conditionne tout le reste du fichier.
# Les autres colonnes utiles ont une raison documentée d'être partiellement
# vides (voir le docstring du module) et ne sont jamais soumises au seuil.
COLONNES_COMPLETUDE_OBLIGATOIRE: tuple[str, ...] = (
    "siret",
    "etatAdministratifEtablissement",
)

ETATS_ADMINISTRATIFS_VALIDES = frozenset({"A", "F"})
CARACTERES_EMPLOYEUR_VALIDES = frozenset({"O", "N", None})
NOMENCLATURE_ACTUELLE = "NAFRev2"

# Une entreprise peut être immatriculée par anticipation de son démarrage
# réel : une date de création future n'est donc pas en soi une anomalie.
# Mesuré sur le fichier complet, la limite entre anticipation plausible et
# corruption se voit nettement : 10 613 dates dans les cinq ans à venir,
# 5 au-delà (dont une à l'année 5015).
HORIZON_ANTICIPATION_ANS = 5


MOTIF_NAF_REV2 = r"^\d{2}\.\d{2}[A-Za-z]$"


class _Compteur:
    """Accumule, lot par lot, ce qu'il faut pour juger un fichier sans le garder en mémoire.

    Chaque lot est converti en `pandas.DataFrame` et traité avec des
    opérations vectorisées (`.str`, comparaisons de séries) plutôt qu'une
    boucle `for` ligne à ligne : sur les 43,9 millions de lignes du fichier
    réel, une boucle Python pure ne termine pas en un temps raisonnable — un
    premier essai, chronométré, a dépassé la minute sans finir. C'est le même
    principe que la note de projection du module : on réduit le travail
    (9 colonnes, pas 54) et on vectorise ce qui reste, on n'itère jamais en
    Python interprété sur des dizaines de millions de lignes.
    """

    def __init__(self) -> None:
        self.total = 0
        self.non_vides: dict[str, int] = {c: 0 for c in COLONNES_UTILES}
        self.siret_non_conformes = 0
        self.etats_invalides = 0
        self.caracteres_invalides = 0
        self.naf_rev2_non_conformes = 0
        self.dates_futures_proches = 0
        self.dates_futures_implausibles = 0

    def observer_lot(self, lot) -> None:
        trame = lot.to_pandas()
        self.total += len(trame)
        for nom in COLONNES_UTILES:
            self.non_vides[nom] += int(trame[nom].notna().sum())
        self._observer_domaines(trame)

    def _observer_domaines(self, trame: pd.DataFrame) -> None:
        siret = trame["siret"]
        conforme = siret.str.fullmatch(r"\d{14}")
        self.siret_non_conformes += int((siret.notna() & ~conforme.fillna(False)).sum())

        etat = trame["etatAdministratifEtablissement"]
        self.etats_invalides += int((etat.notna() & ~etat.isin(ETATS_ADMINISTRATIFS_VALIDES)).sum())

        caractere = trame["caractereEmployeurEtablissement"]
        self.caracteres_invalides += int((~caractere.isin(CARACTERES_EMPLOYEUR_VALIDES)).sum())

        est_rev2 = trame["nomenclatureActivitePrincipaleEtablissement"] == NOMENCLATURE_ACTUELLE
        code = trame["activitePrincipaleEtablissement"]
        conforme_naf = code.str.fullmatch(MOTIF_NAF_REV2)
        self.naf_rev2_non_conformes += int(
            (est_rev2 & code.notna() & ~conforme_naf.fillna(False)).sum()
        )

        dates = pd.to_datetime(trame["dateCreationEtablissement"], errors="coerce")
        aujourdhui = pd.Timestamp(date.today())
        horizon = aujourdhui + pd.DateOffset(years=HORIZON_ANTICIPATION_ANS)
        futures = dates > aujourdhui
        self.dates_futures_proches += int((futures & (dates <= horizon)).sum())
        self.dates_futures_implausibles += int((futures & (dates > horizon)).sum())


def controler_fichier(chemin: Path, seuil_completude: float) -> RapportControle:
    """Contrôle schéma, complétude et cohérence d'un fichier Sirene, en un seul passage en flux."""
    fichier = pq.ParquetFile(chemin)
    colonnes_absentes = [c for c in COLONNES_UTILES if c not in fichier.schema_arrow.names]
    if colonnes_absentes:
        return RapportControle(
            source="sirene",
            anomalies=(
                Anomalie(
                    "sirene",
                    "schema",
                    Gravite.BLOQUANT,
                    f"{chemin.name} : colonne(s) absente(s) — {colonnes_absentes}.",
                ),
            ),
        )
    compteur = _Compteur()
    for lot in fichier.iter_batches(columns=list(COLONNES_UTILES)):
        compteur.observer_lot(lot)
    return _rapport_depuis_compteur(chemin.name, compteur, seuil_completude)


def _rapport_depuis_compteur(nom_fichier: str, compteur: _Compteur, seuil: float) -> RapportControle:
    anomalies: list[Anomalie] = []
    anomalies += _anomalies_completude(nom_fichier, compteur, seuil)
    anomalies += _anomalies_domaine(nom_fichier, compteur)
    return RapportControle(source="sirene", anomalies=tuple(anomalies))


def _anomalies_completude(nom_fichier: str, compteur: _Compteur, seuil: float) -> list[Anomalie]:
    if compteur.total == 0:
        return [Anomalie("sirene", "completude", Gravite.BLOQUANT, f"{nom_fichier} : 0 ligne lue.")]
    anomalies = []
    for colonne in COLONNES_COMPLETUDE_OBLIGATOIRE:
        taux = compteur.non_vides[colonne] / compteur.total
        if taux < seuil:
            anomalies.append(
                Anomalie(
                    "sirene",
                    "completude",
                    Gravite.BLOQUANT,
                    f"{nom_fichier} : {colonne} renseignée à {taux:.2%}, sous le seuil de {seuil:.0%}.",
                )
            )
    return anomalies


def _anomalies_domaine(nom_fichier: str, compteur: _Compteur) -> list[Anomalie]:
    regles_bloquantes = (
        (compteur.siret_non_conformes, "siret non conforme (14 chiffres attendus)"),
        (compteur.etats_invalides, "etatAdministratifEtablissement hors {A, F}"),
        (compteur.caracteres_invalides, "caractereEmployeurEtablissement hors {O, N, vide}"),
        (compteur.naf_rev2_non_conformes, "activitePrincipaleEtablissement non conforme au format NAFRev2"),
        (
            compteur.dates_futures_implausibles,
            f"dateCreationEtablissement à plus de {HORIZON_ANTICIPATION_ANS} ans dans le futur",
        ),
    )
    anomalies = [
        Anomalie("sirene", "coherence", Gravite.BLOQUANT, f"{nom_fichier} : {nb} ligne(s) — {libelle}.")
        for nb, libelle in regles_bloquantes
        if nb > 0
    ]
    if compteur.dates_futures_proches > 0:
        anomalies.append(
            Anomalie(
                "sirene",
                "coherence",
                Gravite.AVERTISSEMENT,
                f"{nom_fichier} : {compteur.dates_futures_proches} ligne(s) — dateCreationEtablissement "
                f"dans le futur, mais à moins de {HORIZON_ANTICIPATION_ANS} ans (immatriculation "
                "anticipée plausible).",
            )
        )
    return anomalies


def controler_fraicheur_sirene(settings: Settings, manifeste: dict[str, dict[str, object]]) -> RapportControle:
    """Fraîcheur de chaque fichier stock, sur `date_publication_stock` (pas la date de collecte locale)."""
    dates = {
        fichier: manifeste.get(fichier, {}).get("date_publication_stock")
        for fichier in settings.donnees.sirene.fichiers
    }
    anomalies = controler_fraicheur(
        "sirene", dates, settings.qualite.sirene.age_max_jours_avertissement
    )
    return RapportControle(source="sirene", anomalies=tuple(anomalies))


# Seul StockEtablissement porte les 9 colonnes utiles au projet (débouchés,
# job Spark E17) : les schémas/complétude/cohérence de ce module lui sont
# spécifiques. `StockEtablissementHistorique`, `StockUniteLegale` et
# `StockUniteLegaleHistorique` ont des colonnes différentes (`siren`, pas de
# `siret` pour l'unité légale...) et ne sont, à ce stade du projet, soumis
# qu'au contrôle de fraîcheur (même cadence de republication mensuelle) — un
# contrôle de schéma dédié à ces trois fichiers n'est pas construit tant
# qu'aucun traitement du pipeline ne les lit encore (voir E18).
FICHIER_CONTROLE_APPROFONDI = "StockEtablissement"


def controler_tous(settings: Settings | None = None) -> RapportControle:
    settings = settings or get_settings()
    dossier = settings.raw_dir / "sirene"
    manifeste_chemin = dossier / "manifeste.json"
    manifeste = (
        json.loads(manifeste_chemin.read_text(encoding="utf-8")) if manifeste_chemin.exists() else {}
    )
    rapports = []
    chemin_etablissement = dossier / f"{FICHIER_CONTROLE_APPROFONDI}.parquet"
    if FICHIER_CONTROLE_APPROFONDI in settings.donnees.sirene.fichiers and chemin_etablissement.exists():
        rapports.append(controler_fichier(chemin_etablissement, settings.qualite.sirene.seuil_completude))
    rapports.append(controler_fraicheur_sirene(settings, manifeste))
    return fusionner("sirene", *rapports)
