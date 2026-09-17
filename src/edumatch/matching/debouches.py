"""Terme « débouchés » du score de matching : un dénombrement Sirene, jamais un modèle.

## L'obstacle, et la mesure qui a tranché

`referentiel/naf_rome_formation.py` relie une **formation IDÉO**
(ONISEP, via son code RNCP) à une division NAF (2 caractères). Aucun des
huit millésimes Parcoursup ne porte de code RNCP, NSF ou ROME (vérifié par
inspection des colonnes) : cette chaîne ne rattache donc **pas** une
formation Parcoursup à une activité NAF. Le seul rapprochement possible est
un appariement textuel des libellés — et ce module le mesure, plutôt que de
le supposer.

**La mesure** (sur `data/processed/parcoursup/variables.parquet`, 440 030
lignes, et `data/external/referentiels/ideo/formations.csv`, complets) : en
comparant `fil_lib_voe_acc` (Parcoursup, normalisé) à `libellé formation
principal` (IDÉO, normalisé), après exclusion des formations IDÉO sans code
RNCP renseigné et des libellés IDÉO ambigus (rattachés à plusieurs codes
RNCP distincts sous le même libellé normalisé), l'appariement exact couvre
**7 des 712 libellés distincts** de la table de variables (1,0 %), soit
**6 017 des 440 030 lignes** (1,4 %). Un échantillon complet des sept
correspondances obtenues (`RapportCorrespondanceFormation.exemples_apparies`)
a été relu à la main : « Diplôme de Comptabilité et de Gestion », « Certificat
de capacité d'Orthoptiste », « Certificat de capacité d'Orthophoniste »,
« Prothésiste dentaire », « DTS Imagerie médicale et radiologie
thérapeutique » et deux intitulés de cadre technique de la mer — sept
intitulés de diplômes d'État très normés, dont la forme ne varie
quasiment pas d'une source à l'autre. C'est précisément ce qui explique à la
fois pourquoi ils s'apparient exactement et pourquoi la quasi-totalité des
autres formations, aux libellés plus librement rédigés par les
établissements (« BTS Comptabilité et gestion » contre « brevet de
technicien supérieur comptabilité et gestion », par exemple), ne
s'apparient pas par égalité stricte.

**Décision, assumée et bornée** : ce module retient cet appariement textuel
**mesuré**, uniquement pour le sous-ensemble où il est fiable (libellé
identique après normalisation, code RNCP renseigné, IDÉO non ambigu), et
déclare le terme **indisponible** — jamais deviné, jamais neutre par erreur
silencieuse — pour les 98,6 % de lignes restantes. C'est un choix d'Option 2
(appariement textuel mesuré), pas d'Option 1 (aucune clé de jointure fiable
trouvée par type de formation seul : `fili` a 12 valeurs, bien trop
grossières pour attacher un débouché sectoriel sans le fabriquer — une
Licence de mathématiques et une Licence d'arts plastiques partageraient le
même débouché) ni d'Option 3 pur (la maille formation individuelle reste
tentée en premier, avec son taux de succès mesuré et vérifié à la main,
avant de replier sur l'indisponibilité déclarée). Une couverture de 1,4 % est
faible, et je le dis comme tel : elle prouve que l'appariement textuel exact
existe et fonctionne pour des intitulés très normés, pas qu'il résout la
rupture de chaîne pour l'ensemble du catalogue — un appariement approché
(distance d'édition, ou une reprise du `code_nsf` IDÉO croisé avec `fili`)
resterait à mesurer avant de conclure qu'aucune amélioration n'est possible.

## Le grain territorial : k-anonymat et le filtre `diffusible`

Extrait dans `matching/agregat_sirene_debouches.py`, que ce module
consomme : k = 5 au grain département x division NAF (décision de la
gouvernance, `risques.md` R2), filtre `diffusible` appliqué (20 488
établissements exclus, mesuré), jamais un effectif sous le seuil exposé —
voir le docstring de ce module pour le détail complet de cette partie.

## Ce que ce terme ne fait jamais

Il ne renvoie jamais un nombre d'établissements sous le seuil de
k-anonymat, même pour distinguer un zéro réel d'une cellule supprimée : les
deux cas sont distingués par un ensemble binaire d'*existence* (au moins un
établissement, sans son effectif exact), jamais par l'effectif intermédiaire
lui-même — voir `agregat_sirene_debouches.appliquer_k_anonymat` et
`calculer_terme_debouches` ci-dessous.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from edumatch.config import Settings, get_settings
from edumatch.ingestion._flux import ecriture_atomique
from edumatch.ingestion._referentiels_communs import dossier_referentiels
from edumatch.matching.agregat_sirene_debouches import (
    RapportKAnonymat,
    appliquer_k_anonymat,
    construire_agregat_departement_naf,
)
from edumatch.referentiel.naf_rome_formation import (
    charger_formations_ideo,
    construire_et_mesurer,
)

LOGGER = logging.getLogger(__name__)

NOM_FICHIER_SOURCE_SIRENE = "StockEtablissement.parquet"
SOUS_DOSSIER_SIRENE = "sirene"
SOUS_DOSSIER_SORTIE = "matching"
NOM_FICHIER_AGREGAT = "agregat_debouches_departement.parquet"
NOM_FICHIER_CORRESPONDANCE = "correspondance_formation_ideo.csv"
NOM_FICHIER_RAPPORT = "debouches_couverture.json"

# Statuts déclarés du terme de débouchés — jamais une valeur neutre non
# expliquée : chaque statut porte une raison différente, lisible par un
# conseiller (`api/static/`) sans avoir à relire ce module.
STATUT_MESURE = "mesure"
STATUT_INDISPONIBLE_TERRITOIRE_NON_RENSEIGNE = "indisponible_territoire_non_renseigne"
STATUT_INDISPONIBLE_CHAINE_ROMPUE = "indisponible_chaine_rompue"
STATUT_INDISPONIBLE_CERTIFICATION_RADIEE = "indisponible_certification_radiee"
STATUT_INDISPONIBLE_K_ANONYMAT = "indisponible_k_anonymat"

# Valeur neutre du terme quand il est indisponible : le score se réduit alors
# à affinité x accessibilité (voir `matching/score.py`), plutôt que de
# fabriquer une correspondance ou de pénaliser une formation dont on ne sait
# simplement rien dire.
VALEUR_NEUTRE = 1.0


class ErreurDebouches(RuntimeError):
    """La source Sirene, la chaîne NAF/ROME/formation ou la correspondance textuelle manquent."""


# ─── Correspondance textuelle Parcoursup <-> IDÉO, mesurée ─────────────────


def normaliser_libelle(libelle: str | None) -> str:
    """Même normalisation que `matching/affinite.normaliser` — minuscule, sans accent, sans
    ponctuation — pour comparer deux libellés de sources différentes sur la même base."""
    if not libelle:
        return ""
    sans_accents = unicodedata.normalize("NFKD", libelle).encode("ascii", "ignore").decode("ascii")
    minuscule = sans_accents.lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", minuscule)).strip()


@dataclass(frozen=True)
class RapportCorrespondanceFormation:
    """Le taux d'appariement mesuré, jamais supposé — voir le docstring du module."""

    n_libelles_parcoursup_distincts: int
    n_libelles_apparies: int
    n_lignes_parcoursup: int
    n_lignes_appariees: int
    exemples_apparies: list[tuple[str, str]] = field(default_factory=list)

    @property
    def taux_appariement_libelles(self) -> float:
        return (
            self.n_libelles_apparies / self.n_libelles_parcoursup_distincts
            if self.n_libelles_parcoursup_distincts
            else 0.0
        )

    @property
    def taux_appariement_lignes(self) -> float:
        return self.n_lignes_appariees / self.n_lignes_parcoursup if self.n_lignes_parcoursup else 0.0

    def en_dict(self) -> dict[str, object]:
        return {
            "n_libelles_parcoursup_distincts": self.n_libelles_parcoursup_distincts,
            "n_libelles_apparies": self.n_libelles_apparies,
            "taux_appariement_libelles": round(self.taux_appariement_libelles, 4),
            "n_lignes_parcoursup": self.n_lignes_parcoursup,
            "n_lignes_appariees": self.n_lignes_appariees,
            "taux_appariement_lignes": round(self.taux_appariement_lignes, 4),
            "exemples_apparies": self.exemples_apparies,
        }


def construire_correspondance_formation_ideo(
    catalogue_parcoursup: pl.DataFrame, formations_ideo: pl.DataFrame
) -> tuple[pl.DataFrame, RapportCorrespondanceFormation]:
    """Apparie `fil_lib_voe_acc` (Parcoursup) à `code_rncp_ideo` (IDÉO) par égalité de libellé
    normalisé. Un libellé IDÉO rattaché à plusieurs codes RNCP distincts sous le même libellé
    normalisé est écarté (jointure 1:N ambiguë, jamais résolue par un choix arbitraire).

    `catalogue_parcoursup` : une colonne `fil_lib_voe_acc` au moins (une ligne
    par cellule de la table de variables — le taux d'appariement est
    mesuré aussi bien par libellé distinct que par ligne, cette dernière
    reflétant le poids réel dans le catalogue).
    `formations_ideo` : la sortie de `referentiel.naf_rome_formation.charger_formations_ideo`
    (colonnes `code_rncp_ideo`, `libelle_formation_ideo`) — **non filtrée** par cette fonction
    source sur la présence d'un code RNCP (voir son docstring) ; ce module filtre donc lui-même
    les lignes sans `code_rncp_ideo` avant l'appariement, sans quoi un libellé IDÉO sans RNCP
    produirait une correspondance vers un code RNCP nul, silencieusement inexploitable en aval.
    """
    lignes_normalisees = catalogue_parcoursup.with_columns(
        pl.col("fil_lib_voe_acc").map_elements(normaliser_libelle, return_dtype=pl.Utf8).alias("libelle_norm")
    )
    libelles_distincts = lignes_normalisees.select("fil_lib_voe_acc", "libelle_norm").unique()
    libelles_distincts = libelles_distincts.filter(pl.col("libelle_norm") != "")

    ideo_norm = (
        formations_ideo.filter(pl.col("code_rncp_ideo").is_not_null() & (pl.col("code_rncp_ideo") != ""))
        .with_columns(
            pl.col("libelle_formation_ideo").map_elements(normaliser_libelle, return_dtype=pl.Utf8).alias("libelle_norm")
        )
        .filter(pl.col("libelle_norm") != "")
    )
    non_ambigu = (
        ideo_norm.group_by("libelle_norm")
        .agg(
            pl.col("code_rncp_ideo").n_unique().alias("n_rncp"),
            pl.col("code_rncp_ideo").first().alias("code_rncp_ideo"),
        )
        .filter(pl.col("n_rncp") == 1)
        .drop("n_rncp")
    )

    correspondance_libelles = libelles_distincts.join(non_ambigu, on="libelle_norm", how="inner").select(
        "fil_lib_voe_acc", "code_rncp_ideo"
    )
    lignes_appariees = lignes_normalisees.join(
        correspondance_libelles, on="fil_lib_voe_acc", how="inner"
    )

    exemples = (
        correspondance_libelles.head(20).select("fil_lib_voe_acc", "code_rncp_ideo").rows()
        if correspondance_libelles.height
        else []
    )
    rapport = RapportCorrespondanceFormation(
        n_libelles_parcoursup_distincts=libelles_distincts.height,
        n_libelles_apparies=correspondance_libelles.height,
        n_lignes_parcoursup=lignes_normalisees.height,
        n_lignes_appariees=lignes_appariees.height,
        exemples_apparies=[(str(a), str(b)) for a, b in exemples],
    )
    return correspondance_libelles, rapport


# ─── Le terme de débouchés, pour une formation et un département ───────────


@dataclass(frozen=True)
class TermeDebouches:
    """Le facteur de débouchés et le détail qui l'explique — voir les constantes `STATUT_*`
    pour les raisons possibles de l'indisponibilité, jamais une valeur neutre non expliquée."""

    valeur: float
    disponible: bool
    statut: str
    naf_divisions: tuple[str, ...] = ()
    n_etablissements: int | None = None
    departement: str | None = None


def calculer_terme_debouches(
    fil_lib_voe_acc: str,
    departement_candidat: str | None,
    correspondance_formation: pl.DataFrame,
    table_naf_rome_formation: pl.DataFrame,
    agregat_conserve: pl.DataFrame,
    cellules_non_vides: pl.DataFrame,
    seuil_saturation: int,
) -> TermeDebouches:
    """Calcule le terme de débouchés d'une formation dans le département visé par le candidat.

    `correspondance_formation` : sortie de `construire_correspondance_formation_ideo`
    (colonnes `fil_lib_voe_acc`, `code_rncp_ideo`).
    `table_naf_rome_formation` : sortie de `construire_table`, **déjà
    filtrée sur `rncp_actif`** par l'appelant (`executer`) — une certification
    radiée n'est jamais un débouché actuel (voir le docstring de la réconciliation NAF/ROME).
    `agregat_conserve`, `cellules_non_vides` : sorties de `appliquer_k_anonymat`.
    """
    if departement_candidat is None:
        return TermeDebouches(
            valeur=VALEUR_NEUTRE, disponible=False, statut=STATUT_INDISPONIBLE_TERRITOIRE_NON_RENSEIGNE
        )

    ligne = correspondance_formation.filter(pl.col("fil_lib_voe_acc") == fil_lib_voe_acc)
    code_rncp = ligne["code_rncp_ideo"][0] if not ligne.is_empty() else None
    if code_rncp is None:
        return TermeDebouches(valeur=VALEUR_NEUTRE, disponible=False, statut=STATUT_INDISPONIBLE_CHAINE_ROMPUE)

    divisions = (
        table_naf_rome_formation.filter(pl.col("code_rncp_ideo") == code_rncp)
        .select("naf_division")
        .unique()
        .to_series()
        .to_list()
    )
    if not divisions:
        # La correspondance textuelle a atteint une fiche RNCP, mais celle-ci n'a plus de
        # débouché actif rattaché (radiée, ou sans division NAF connue) : un zéro réel, pas
        # une indisponibilité — voir le filtrage `rncp_actif` fait par l'appelant.
        return TermeDebouches(
            valeur=0.0,
            disponible=True,
            statut=STATUT_INDISPONIBLE_CERTIFICATION_RADIEE,
            naf_divisions=(),
            n_etablissements=0,
            departement=departement_candidat,
        )

    cellules_conservees = agregat_conserve.filter(
        (pl.col("departement") == departement_candidat) & pl.col("naf_division").is_in(divisions)
    )
    if cellules_conservees.height:
        n = int(cellules_conservees["nb_actifs_employeurs_diffusibles"].sum())
        valeur = min(1.0, n / seuil_saturation) if seuil_saturation > 0 else 1.0
        return TermeDebouches(
            valeur=valeur,
            disponible=True,
            statut=STATUT_MESURE,
            naf_divisions=tuple(divisions),
            n_etablissements=n,
            departement=departement_candidat,
        )

    existe_sans_effectif_lisible = cellules_non_vides.filter(
        (pl.col("departement") == departement_candidat) & pl.col("naf_division").is_in(divisions)
    )
    if existe_sans_effectif_lisible.is_empty():
        # Aucun établissement, à aucun effectif : un zéro réel, mesuré, pas soumis au
        # k-anonymat (l'absence totale n'identifie aucune entité précise).
        return TermeDebouches(
            valeur=0.0,
            disponible=True,
            statut=STATUT_MESURE,
            naf_divisions=tuple(divisions),
            n_etablissements=0,
            departement=departement_candidat,
        )
    # Au moins un établissement existe, mais sous le seuil de k-anonymat : ni son
    # effectif ni son existence exacte ne sont exposés au-delà de ce statut déclaré.
    return TermeDebouches(
        valeur=VALEUR_NEUTRE,
        disponible=False,
        statut=STATUT_INDISPONIBLE_K_ANONYMAT,
        naf_divisions=tuple(divisions),
        departement=departement_candidat,
    )


# ─── Orchestration : chemins réels, écriture des artefacts ─────────────────


def _chemin_source_sirene(settings: Settings) -> Path:
    return settings.raw_dir / SOUS_DOSSIER_SIRENE / NOM_FICHIER_SOURCE_SIRENE


def construire_table_naf_rome_formation_active(settings: Settings) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Réutilise la chaîne NAF/ROME/formation (`referentiel.naf_rome_formation`,
    même sources, même construction) et filtre sur `rncp_actif` : une certification radiée
    n'est jamais un débouché actuel (voir le docstring du module).

    Recharge séparément les formations IDÉO (`charger_formations_ideo`) : `construire_et_mesurer`
    ne les réexpose pas telles quelles, et ce module en a besoin, avec leur libellé, pour la
    correspondance textuelle (`construire_correspondance_formation_ideo`).
    """
    table, _ = construire_et_mesurer(settings)
    cfg_ideo = settings.donnees.referentiels.ideo.jeux["formations"]
    formations = charger_formations_ideo(
        dossier_referentiels(settings) / "ideo" / "formations.csv", cfg_ideo.delimiteur
    )
    return table.filter(pl.col("rncp_actif")), formations


@dataclass(frozen=True)
class ArtefactsDebouches:
    """Tout ce dont `matching/score.py` a besoin pour calculer le terme de débouchés."""

    correspondance_formation: pl.DataFrame
    table_naf_rome_formation: pl.DataFrame
    agregat_conserve: pl.DataFrame
    cellules_non_vides: pl.DataFrame
    rapport_k_anonymat: RapportKAnonymat
    rapport_correspondance: RapportCorrespondanceFormation


def construire_artefacts(catalogue_parcoursup: pl.DataFrame, settings: Settings | None = None) -> ArtefactsDebouches:
    """Point d'entrée réel : construit tout ce que `calculer_terme_debouches` consomme.

    `catalogue_parcoursup` : au moins la colonne `fil_lib_voe_acc`, une ligne
    par cellule (la table de variables, ou un sous-ensemble de test).
    """
    settings = settings or get_settings()
    chemin_sirene = _chemin_source_sirene(settings)
    if not chemin_sirene.exists():
        raise ErreurDebouches(
            f"{chemin_sirene} introuvable : exécuter `python -m edumatch.ingestion.sirene` "
            "avant le terme de débouchés."
        )

    table_active, formations_ideo = construire_table_naf_rome_formation_active(settings)
    correspondance, rapport_correspondance = construire_correspondance_formation_ideo(
        catalogue_parcoursup, formations_ideo
    )

    agregat = construire_agregat_departement_naf(chemin_sirene)
    conserve, cellules_non_vides, rapport_k = appliquer_k_anonymat(agregat, settings.matching.k_anonymat_debouches)

    return ArtefactsDebouches(
        correspondance_formation=correspondance,
        table_naf_rome_formation=table_active,
        agregat_conserve=conserve,
        cellules_non_vides=cellules_non_vides,
        rapport_k_anonymat=rapport_k,
        rapport_correspondance=rapport_correspondance,
    )


def ecrire_artefacts(settings: Settings, artefacts: ArtefactsDebouches) -> tuple[Path, Path, Path]:
    """Écrit l'agrégat conservé, la correspondance et le rapport de couverture (mesuré, pas déclaratif)."""
    dossier = settings.processed_dir / SOUS_DOSSIER_SORTIE
    dossier.mkdir(parents=True, exist_ok=True)

    chemin_agregat = dossier / NOM_FICHIER_AGREGAT
    with ecriture_atomique(chemin_agregat, mode="wb") as flux:
        artefacts.agregat_conserve.write_parquet(flux)

    chemin_correspondance = dossier / NOM_FICHIER_CORRESPONDANCE
    with ecriture_atomique(chemin_correspondance, mode="wb") as flux:
        artefacts.correspondance_formation.write_csv(flux)

    chemin_rapport = dossier / NOM_FICHIER_RAPPORT
    rapport = {
        "k_anonymat": artefacts.rapport_k_anonymat.en_dict(),
        "correspondance_formation_ideo": artefacts.rapport_correspondance.en_dict(),
    }
    chemin_rapport.write_text(json.dumps(rapport, indent=2, ensure_ascii=False), encoding="utf-8")
    return chemin_agregat, chemin_correspondance, chemin_rapport


def executer(settings: Settings | None = None) -> ArtefactsDebouches:
    settings = settings or get_settings()
    chemin_variables = settings.processed_dir / "parcoursup" / "variables.parquet"
    if not chemin_variables.exists():
        raise ErreurDebouches(f"{chemin_variables} introuvable : exécuter `make features` avant ce module.")
    catalogue = pl.read_parquet(chemin_variables, columns=["fil_lib_voe_acc"])
    artefacts = construire_artefacts(catalogue, settings)
    chemin_agregat, chemin_correspondance, chemin_rapport = ecrire_artefacts(settings, artefacts)
    LOGGER.info("Agrégat débouchés écrit : %s", chemin_agregat)
    LOGGER.info("Correspondance formation -> IDÉO écrite : %s", chemin_correspondance)
    LOGGER.info("Rapport de couverture écrit : %s", chemin_rapport)
    LOGGER.info(
        "k-anonymat (k=%d, %s) : %d/%d cellules supprimées (%.1f%%), %d/%d établissements perdus (%.1f%%).",
        artefacts.rapport_k_anonymat.k,
        artefacts.rapport_k_anonymat.grain,
        artefacts.rapport_k_anonymat.cellules_supprimees,
        artefacts.rapport_k_anonymat.cellules_totales,
        artefacts.rapport_k_anonymat.part_cellules_supprimees * 100,
        artefacts.rapport_k_anonymat.etablissements_perdus,
        artefacts.rapport_k_anonymat.etablissements_totaux,
        artefacts.rapport_k_anonymat.part_etablissements_perdus * 100,
    )
    LOGGER.info(
        "Correspondance formation -> IDÉO : %d/%d libellés distincts appariés (%.1f%%), "
        "%d/%d lignes du catalogue couvertes (%.1f%%).",
        artefacts.rapport_correspondance.n_libelles_apparies,
        artefacts.rapport_correspondance.n_libelles_parcoursup_distincts,
        artefacts.rapport_correspondance.taux_appariement_libelles * 100,
        artefacts.rapport_correspondance.n_lignes_appariees,
        artefacts.rapport_correspondance.n_lignes_parcoursup,
        artefacts.rapport_correspondance.taux_appariement_lignes * 100,
    )
    return artefacts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    executer()


if __name__ == "__main__":
    main()
