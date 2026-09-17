"""Contrôles qualité des référentiels ONISEP (IDÉO) et RNCP/RS.

Volumétrie modeste (quelques Mo, quelques dizaines de milliers de lignes au
plus) : chaque fichier est chargé entièrement, comme pour Parcoursup. Les
noms de colonnes IDÉO portent des accents et des espaces
(`"libellé formation principal"`) : ce module les compare après
normalisation (minuscules, accents retirés) plutôt que de recopier le nom
accentué en dur dans le code — un choix qui dépend de l'encodage du terminal
ou de l'éditeur utilisé pour écrire ce fichier serait fragile d'un poste à
l'autre, ce qu'une normalisation ASCII évite.

Deux hypothèses de cohérence ont été écrites puis retirées avant d'écrire ce
module, faute de tenir sur l'échantillon réel : ni le nombre de colonnes RNCP
« Date_Fin_Enregistrement vide ⇔ Actif = ACTIVE », ni l'ordre chronologique
entre `Date_Decision` et `Date_dernier_jo` sur toutes les lignes comparables
n'ont résisté à la vérification. Elles ne figurent donc pas ici : un contrôle
non vérifié sur des données réelles n'a pas sa place dans une chaîne qui
bloque.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from edumatch.config import Settings, get_settings
from edumatch.quality._diagnostic import Anomalie, Gravite, RapportControle, fusionner
from edumatch.quality._fraicheur import controler_fraicheur

# Nombre de colonnes attendu par jeu IDÉO, mesuré sur les fichiers réellement
# téléchargés le 2026-08-29 (voir 01-donnees/sources.md).
COLONNES_ATTENDUES_IDEO: dict[str, int] = {
    "formations": 16,
    "metiers": 13,
    "structures_secondaire": 30,
    "structures_superieur": 29,
}

# Colonne toujours renseignée par jeu IDÉO, vérifiée sans exception sur les
# 300 lignes de chaque échantillon versionné. Sert d'ancre de complétude
# tolérante à l'accentuation (voir `_normaliser`) plutôt qu'un identifiant
# technique (« code UAI » n'atteint que 96 % de complétude, mesuré, et ne
# convient donc pas).
COLONNE_ANCRE_IDEO: dict[str, str] = {
    "formations": "libelle formation principal",
    "metiers": "libelle metier",
    "structures_secondaire": "nom",
    "structures_superieur": "nom",
}

COLONNES_RNCP_ATTENDUES = 16
COLONNES_RNCP_OBLIGATOIRES: tuple[str, ...] = ("Id_Fiche", "Numero_Fiche", "Intitule", "Actif")
ACTIF_VALEURS_VALIDES = frozenset({"ACTIVE", "INACTIVE"})
MOTIF_NUMERO_FICHE = re.compile(r"^(RNCP|RS)\d+$")
COLONNES_RNCP_DATES: tuple[str, ...] = (
    "Date_dernier_jo",
    "Date_Decision",
    "Date_Fin_Enregistrement",
    "Date_Effet",
)


def _normaliser(texte: str) -> str:
    """Minuscules, sans accents : `"Libellé Formation"` devient `"libelle formation"`."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return sans_accents.strip().lower()


def _lire_csv(chemin: Path, encodage: str, delimiteur: str) -> list[dict[str, str]]:
    with chemin.open(encoding=encodage, newline="") as fichier:
        return list(csv.DictReader(fichier, delimiter=delimiteur))


# ─── IDÉO ─────────────────────────────────────────────────────────────────


def controler_ideo_jeu(chemin: Path, jeu: str, seuil_completude: float) -> RapportControle:
    """Schéma (nombre de colonnes) et complétude (colonne ancre) d'un jeu IDÉO.

    Lu en `utf-8-sig`, pas `utf-8` (la valeur déclarée dans
    `donnees.referentiels.ideo.jeux.*.encodage`) : les quatre fichiers réels
    téléchargés le 2026-08-29 portent un BOM UTF-8 (`\\xef\\xbb\\xbf`) en tête.
    `utf-8-sig` le retire s'il est présent et se comporte à l'identique
    de `utf-8` s'il est absent — sans ce choix, le premier en-tête de colonne
    (`code NSF`, `libellé métier`...) reste préfixé du caractère invisible
    U+FEFF et ne correspond plus à aucune colonne attendue, un faux positif
    de schéma constaté en le vérifiant sur les fichiers réels, pas supposé.
    """
    lignes = _lire_csv(chemin, "utf-8-sig", ";")
    anomalies: list[Anomalie] = []
    anomalies += _controler_nombre_colonnes_ideo(chemin.name, jeu, lignes)
    anomalies += _controler_completude_ideo(chemin.name, jeu, lignes, seuil_completude)
    return RapportControle(source="referentiels", anomalies=tuple(anomalies))


def _controler_nombre_colonnes_ideo(nom_fichier: str, jeu: str, lignes: list[dict]) -> list[Anomalie]:
    attendu = COLONNES_ATTENDUES_IDEO.get(jeu)
    if attendu is None or not lignes:
        return []
    observe = len(lignes[0])
    if observe != attendu:
        return [
            Anomalie(
                "referentiels",
                "schema",
                Gravite.BLOQUANT,
                f"IDÉO {jeu} ({nom_fichier}) : {observe} colonne(s), {attendu} attendue(s).",
            )
        ]
    return []


def _controler_completude_ideo(
    nom_fichier: str, jeu: str, lignes: list[dict], seuil: float
) -> list[Anomalie]:
    ancre = COLONNE_ANCRE_IDEO.get(jeu)
    if ancre is None or not lignes:
        return []
    colonnes_normalisees = {_normaliser(nom): nom for nom in lignes[0]}
    colonne_reelle = colonnes_normalisees.get(ancre)
    if colonne_reelle is None:
        return [
            Anomalie(
                "referentiels",
                "schema",
                Gravite.BLOQUANT,
                f"IDÉO {jeu} ({nom_fichier}) : colonne ancre {ancre!r} introuvable.",
            )
        ]
    remplies = sum(1 for ligne in lignes if ligne[colonne_reelle])
    taux = remplies / len(lignes)
    if taux < seuil:
        return [
            Anomalie(
                "referentiels",
                "completude",
                Gravite.BLOQUANT,
                f"IDÉO {jeu} ({nom_fichier}) : {colonne_reelle!r} renseignée à {taux:.2%}, "
                f"sous le seuil de {seuil:.0%}.",
            )
        ]
    return []


# ─── RNCP ───────────────────────────────────────────────────────────────────


def controler_rncp(chemin: Path, encodage: str, delimiteur: str, seuil_completude: float) -> RapportControle:
    """Schéma, complétude et cohérence de l'export RNCP/RS du jour."""
    lignes = _lire_csv(chemin, encodage, delimiteur)
    anomalies: list[Anomalie] = []
    anomalies += _controler_schema_rncp(chemin.name, lignes)
    if not anomalies:
        anomalies += _controler_completude_rncp(chemin.name, lignes, seuil_completude)
        anomalies += _controler_coherence_rncp(chemin.name, lignes)
    return RapportControle(source="referentiels", anomalies=tuple(anomalies))


def _controler_schema_rncp(nom_fichier: str, lignes: list[dict]) -> list[Anomalie]:
    if not lignes:
        return [Anomalie("referentiels", "schema", Gravite.BLOQUANT, f"RNCP ({nom_fichier}) : fichier vide.")]
    manquantes = [c for c in COLONNES_RNCP_OBLIGATOIRES if c not in lignes[0]]
    if manquantes:
        return [
            Anomalie(
                "referentiels",
                "schema",
                Gravite.BLOQUANT,
                f"RNCP ({nom_fichier}) : colonne(s) obligatoire(s) absente(s) — {manquantes}.",
            )
        ]
    if len(lignes[0]) != COLONNES_RNCP_ATTENDUES:
        return [
            Anomalie(
                "referentiels",
                "schema",
                Gravite.BLOQUANT,
                f"RNCP ({nom_fichier}) : {len(lignes[0])} colonne(s), {COLONNES_RNCP_ATTENDUES} attendue(s).",
            )
        ]
    return []


def _controler_completude_rncp(nom_fichier: str, lignes: list[dict], seuil: float) -> list[Anomalie]:
    anomalies = []
    for colonne in COLONNES_RNCP_OBLIGATOIRES:
        taux = sum(1 for ligne in lignes if ligne[colonne]) / len(lignes)
        if taux < seuil:
            anomalies.append(
                Anomalie(
                    "referentiels",
                    "completude",
                    Gravite.BLOQUANT,
                    f"RNCP ({nom_fichier}) : {colonne} renseignée à {taux:.2%}, sous le seuil de {seuil:.0%}.",
                )
            )
    return anomalies


def _controler_coherence_rncp(nom_fichier: str, lignes: list[dict]) -> list[Anomalie]:
    anomalies: list[Anomalie] = []
    actifs_invalides = sum(1 for ligne in lignes if ligne["Actif"] not in ACTIF_VALEURS_VALIDES)
    if actifs_invalides:
        anomalies.append(
            Anomalie(
                "referentiels",
                "coherence",
                Gravite.BLOQUANT,
                f"RNCP ({nom_fichier}) : {actifs_invalides} ligne(s) — Actif hors {{ACTIVE, INACTIVE}}.",
            )
        )
    numeros_invalides = sum(
        1 for ligne in lignes if not MOTIF_NUMERO_FICHE.match(ligne["Numero_Fiche"])
    )
    if numeros_invalides:
        anomalies.append(
            Anomalie(
                "referentiels",
                "coherence",
                Gravite.BLOQUANT,
                f"RNCP ({nom_fichier}) : {numeros_invalides} Numero_Fiche hors du motif RNCP<n>/RS<n>.",
            )
        )
    anomalies += _controler_dates_rncp(nom_fichier, lignes)
    return anomalies


def _controler_dates_rncp(nom_fichier: str, lignes: list[dict]) -> list[Anomalie]:
    illisibles = 0
    for ligne in lignes:
        for colonne in COLONNES_RNCP_DATES:
            valeur = ligne.get(colonne, "")
            if valeur and _date_rncp(valeur) is None:
                illisibles += 1
    if not illisibles:
        return []
    return [
        Anomalie(
            "referentiels",
            "coherence",
            Gravite.BLOQUANT,
            f"RNCP ({nom_fichier}) : {illisibles} date(s) non conforme(s) au format JJ/MM/AAAA.",
        )
    ]


def _date_rncp(valeur: str) -> datetime | None:
    """Ne sert qu'à vérifier que `valeur` est une date calendaire JJ/MM/AAAA valide :
    le résultat n'est jamais comparé ni combiné à un autre instant, donc l'absence de
    fuseau ne pose pas de risque réel ici."""
    try:
        return datetime.strptime(valeur, "%d/%m/%Y")  # noqa: DTZ007
    except ValueError:
        return None


# ─── Fraîcheur et orchestration ─────────────────────────────────────────────


def controler_fraicheur_referentiels(
    settings: Settings, manifeste: dict[str, dict[str, object]]
) -> RapportControle:
    """IDÉO (URL fixe, `date_telechargement`) et RNCP (export daté, `date_publication`)."""
    seuils = settings.qualite.referentiels
    dates_ideo = {
        f"ideo:{jeu}": manifeste.get(f"ideo:{jeu}", {}).get("date_telechargement")
        for jeu in settings.donnees.referentiels.ideo.jeux
    }
    anomalies = controler_fraicheur("referentiels", dates_ideo, seuils.age_max_jours_avertissement_ideo)
    anomalies += _controler_fraicheur_rncp(manifeste, seuils.age_max_jours_avertissement_rncp)
    return RapportControle(source="referentiels", anomalies=tuple(anomalies))


def _controler_fraicheur_rncp(
    manifeste: dict[str, dict[str, object]], age_max_jours: float
) -> list[Anomalie]:
    """Ne contrôle que l'export le plus récent : chaque export du jour est une archive à part (ADR 0007)."""
    entrees_rncp = {cle: valeur for cle, valeur in manifeste.items() if cle.startswith("rncp:")}
    if not entrees_rncp:
        return controler_fraicheur("referentiels", {"rncp": None}, age_max_jours)
    plus_recente = max(entrees_rncp, key=lambda cle: entrees_rncp[cle].get("date_publication", ""))
    date_publication = entrees_rncp[plus_recente].get("date_publication")
    return controler_fraicheur("referentiels", {plus_recente: date_publication}, age_max_jours)


def controler_tous(settings: Settings | None = None) -> RapportControle:
    settings = settings or get_settings()
    dossier = settings.external_dir / "referentiels"
    manifeste_chemin = dossier / "manifeste.json"
    manifeste = (
        json.loads(manifeste_chemin.read_text(encoding="utf-8")) if manifeste_chemin.exists() else {}
    )
    rapports = _rapports_ideo(settings, dossier) + _rapports_rncp(settings, dossier)
    rapports.append(controler_fraicheur_referentiels(settings, manifeste))
    return fusionner("referentiels", *rapports)


def _rapports_ideo(settings: Settings, dossier: Path) -> list[RapportControle]:
    seuil = settings.qualite.referentiels.seuil_completude
    rapports = []
    for jeu in settings.donnees.referentiels.ideo.jeux:
        chemin = dossier / "ideo" / f"{jeu}.csv"
        if chemin.exists():
            rapports.append(controler_ideo_jeu(chemin, jeu, seuil))
    return rapports


def _rapports_rncp(settings: Settings, dossier: Path) -> list[RapportControle]:
    config = settings.donnees.referentiels.rncp
    fichiers = sorted((dossier / "rncp").glob("rncp_*.csv")) if (dossier / "rncp").exists() else []
    seuil = settings.qualite.referentiels.seuil_completude
    return [controler_rncp(f, config.encodage, config.delimiteur, seuil) for f in fichiers]
