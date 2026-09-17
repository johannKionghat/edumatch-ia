"""Réconciliation NAF (Sirene) -> ROME (métiers) -> formation.

Diagnostic préalable, mené avant d'écrire une ligne de ce module — voir
`docs/sous-docs-projets/01-donnees/nomenclatures.md` pour le détail complet :
il n'existe aucune table officielle unique reliant directement un code NAF
(l'activité d'un établissement) à un code ROME (un métier France Travail).
La chaîne construite ici assemble donc trois sources publiques réelles,
chacune vérifiée séparément :

    formation IDÉO --(code RNCP)--> fiche RNCP --(export ROME de l'archive
    RNCP)--> code(s) ROME --(table France Travail ROME/NAF)--> division NAF

Un maillon déclaré manquant, pas comblé : cette chaîne rattache une
**formation IDÉO** (le référentiel de certifications d'ONISEP) à une
activité NAF. Elle ne rattache **pas** une formation **Parcoursup**
(`dim_formation`, grain de `fait_admission`) à cette même chaîne : aucun des
huit millésimes Parcoursup ne porte de code RNCP, NSF ou ROME (vérifié par
inspection des colonnes de `data/raw/parcoursup/parcoursup_2025.csv` et de
`data/processed/parcoursup/dim_formation.parquet`). Le seul rapprochement
possible serait un appariement de libellés (`form_lib_voe_acc`, `fil_lib_voe_acc`
côté Parcoursup contre `libellé formation principal` côté IDÉO) : une
correspondance textuelle floue, pas une jointure sur clé — précisément le
type de correspondance ambiguë que ce projet s'interdit d'arbitrer sans
mesure. Ce module ne le fait donc pas ; voir `mesurer_couverture` et le
docstring de fin de fichier pour les options possibles, non mises en œuvre.

Deux pertes de granularité, déclarées, pas masquées :

- **NAF à la division (2 chiffres).** La table France Travail ne relie ROME
  qu'à la division NAF (ex. « 62 » — Programmation, conseil et autres
  activités informatiques), pas à la sous-classe complète (5 caractères, ex.
  « 62.01Z ») que porte `activitePrincipaleEtablissement` dans l'agrégat
  Sirene. Le rattachement à un établissement réel exige de tronquer
  son code NAF à ses deux premiers caractères — un calcul exact, la division
  étant par construction le préfixe de toute sous-classe, pas une
  approximation inventée.
- **Une fiche RNCP peut couvrir plusieurs codes ROME**, et un code ROME peut
  apparaître sous plusieurs divisions NAF : la table finale est donc en
  relation N:N, pas 1:1. Une formation n'a pas « un » débouché NAF mais un
  ensemble, pondérable ou non selon l'usage qui en sera fait en aval (score
  de débouchés).

État de la certification, exposé et non filtré : le répertoire RNCP mêle des
fiches actives et des fiches radiées (colonne `Actif` du CSV standard de
l'export, valeurs `ACTIVE`/`INACTIVE`). Mesuré sur l'export du 2026-08-30 :
25 213 lignes de la table finale rattachées à une fiche `ACTIVE`, 1 145 à une
fiche `INACTIVE`, soit 4,3 % des 26 358 lignes. Une certification radiée
n'est pas un débouché actuel, mais ce n'est pas à cette table d'en décider :
elle expose l'état par une colonne (`rncp_actif`) et le calcul des débouchés
 choisira d'en tenir compte ou non, comme il le fait déjà pour la
pondération N:N ci-dessus.

La double nomenclature NAF (2008/2025) : la table France Travail est
construite sur la nomenclature courante (NAF rev. 2, dite « NAF2008 » dans ce
projet), celle qu'utilise `activitePrincipaleEtablissement`. L'agrégat
Sirene ne porte que le **compte** de lignes dont le NAF2025 est renseigné
(`nb_naf25_renseigne`), jamais le code NAF2025 lui-même : cette table ne peut
donc pas, et n'a pas besoin de, couvrir la NAF2025. Elle devra être reconstruite
après la bascule officielle du répertoire si aucune table France
Travail équivalente n'est republiée sous la nouvelle nomenclature.

Licence : IDÉO est sous ODbL (partage à l'identique obligatoire sur toute
base dérivée redistribuée) ; RNCP et France Travail sont en Licence Ouverte
v2.0. Cette table dérivée, qui intègre des données IDÉO, est donc concernée
par l'ODbL — signalé ici pour que la gouvernance le reprenne,
cette question relevant d'elle, pas de ce module.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
import polars as pl

from edumatch.config import Settings, get_settings
from edumatch.ingestion._referentiels_communs import dossier_referentiels

LOGGER = logging.getLogger(__name__)

# Sentinelle de l'arborescence France Travail : "0 - Transverse aux secteurs"
# n'est pas une division NAF réelle (les divisions NAF vont de 01 à 99, avec
# des trous), c'est un regroupement des métiers non spécifiques à un secteur.
# L'exclure est une lecture fidèle du fichier source, pas une omission.
DIVISION_SENTINELLE_TRANSVERSE = "00"

_MOTIF_CODE_ROME = re.compile(r"^[A-Z]\d{4}$")
_MOTIF_CODE_DIVISION = re.compile(r"^\d{1,2}$")
_MOTIF_NAF_SOUS_CLASSE = re.compile(r"^\d{2}")  # les deux premiers caractères sont toujours la division


class ErreurContratNafRomeFormation(RuntimeError):
    """Une des trois sources n'a plus la forme attendue : colonne absente, feuille introuvable."""


@dataclass(frozen=True)
class RapportMaillon:
    """Couverture mesurée à un maillon précis de la chaîne — jamais un taux global unique."""

    nom: str
    total: int
    retenus: int
    note: str = ""

    @property
    def taux(self) -> float:
        return self.retenus / self.total if self.total else 0.0


@dataclass(frozen=True)
class RapportCouverture:
    """L'ensemble des maillons mesurés, plus les manques déclarés explicitement."""

    maillons: list[RapportMaillon] = field(default_factory=list)
    manques_declares: list[str] = field(default_factory=list)

    def en_dict(self) -> dict[str, object]:
        return {
            "maillons": [
                {"nom": m.nom, "total": m.total, "retenus": m.retenus, "taux": round(m.taux, 4), "note": m.note}
                for m in self.maillons
            ],
            "manques_declares": self.manques_declares,
        }


# ─── Lecture des trois sources ──────────────────────────────────────────────


def _lire_csv_utf8_sig(chemin: Path, delimiteur: str) -> pl.DataFrame:
    """Lit un CSV avec BOM UTF-8, comme `ingestion.echantillons._lire_csv` mais vers un DataFrame.

    IDÉO et RNCP portent tous deux un BOM en tête de fichier (vérifié par
    décodage effectif) : sans `utf-8-sig`, le nom de la première colonne
    resterait préfixé du caractère de BOM.
    """
    texte = chemin.read_text(encoding="utf-8-sig")
    return pl.read_csv(io.StringIO(texte), separator=delimiteur, infer_schema_length=0)


def charger_formations_ideo(chemin: Path, delimiteur: str = ";") -> pl.DataFrame:
    """Formations IDÉO portant un code RNCP renseigné — seules exploitables pour cette chaîne.

    Colonnes retenues : `code RNCP` (clé de jointure vers la fiche RNCP,
    après retrait du préfixe "RNCP"), `code NSF`, le libellé, à titre
    informatif dans la table finale.
    """
    brut = _lire_csv_utf8_sig(chemin, delimiteur)
    colonnes_attendues = {"code RNCP", "code NSF", "libellé formation principal"}
    manquantes = colonnes_attendues - set(brut.columns)
    if manquantes:
        raise ErreurContratNafRomeFormation(
            f"Colonnes attendues absentes de {chemin} : {sorted(manquantes)}. "
            f"Colonnes présentes : {brut.columns}."
        )
    return brut.select(
        pl.col("code RNCP").alias("code_rncp_ideo"),
        pl.col("code NSF").alias("code_nsf"),
        pl.col("libellé formation principal").alias("libelle_formation_ideo"),
    )


def charger_rncp_rome(chemin: Path, delimiteur: str = ";") -> pl.DataFrame:
    """Correspondance fiche RNCP -> code(s) ROME, une ligne par couple (fiche, ROME)."""
    brut = _lire_csv_utf8_sig(chemin, delimiteur)
    colonnes_attendues = {"Numero_Fiche", "Codes_Rome_Code", "Codes_Rome_Libelle"}
    manquantes = colonnes_attendues - set(brut.columns)
    if manquantes:
        raise ErreurContratNafRomeFormation(
            f"Colonnes attendues absentes de {chemin} : {sorted(manquantes)}. "
            f"Colonnes présentes : {brut.columns}."
        )
    return brut.select(
        pl.col("Numero_Fiche").str.strip_prefix("RNCP").alias("code_rncp_fiche"),
        pl.col("Codes_Rome_Code").alias("code_rome"),
        pl.col("Codes_Rome_Libelle").alias("libelle_rome"),
    )


def charger_etat_rncp(chemin: Path, delimiteur: str = ";") -> pl.DataFrame:
    """État actif/radié de chaque fiche RNCP, depuis le CSV standard de l'export du jour.

    Colonne `Actif` de l'export RNCP standard — pas le fichier `rncp_rome_*`
    lu par `charger_rncp_rome`, un membre distinct de la même archive
    quotidienne (voir `ingestion._referentiels_rncp.telecharger` contre
    `telecharger_rome`). Valeurs observées sur l'export du 2026-08-30 :
    exactement `ACTIVE` ou `INACTIVE`, sur les 30 484 fiches, sans valeur
    manquante — vérifié ici, pas supposé.

    Une fiche radiée (`INACTIVE`) n'est pas retirée par cette fonction :
    voir `construire_table`, qui l'expose en colonne plutôt que de filtrer
    à sa place.

    Raises:
        ErreurContratNafRomeFormation: colonne absente, ou une valeur de
            `Actif` hors de `{ACTIVE, INACTIVE}` — la source a changé de
            contrat.
    """
    brut = _lire_csv_utf8_sig(chemin, delimiteur)
    colonnes_attendues = {"Numero_Fiche", "Actif"}
    manquantes = colonnes_attendues - set(brut.columns)
    if manquantes:
        raise ErreurContratNafRomeFormation(
            f"Colonnes attendues absentes de {chemin} : {sorted(manquantes)}. "
            f"Colonnes présentes : {brut.columns}."
        )
    valeurs_inattendues = set(brut["Actif"].unique().to_list()) - {"ACTIVE", "INACTIVE"}
    if valeurs_inattendues:
        raise ErreurContratNafRomeFormation(
            f"Valeurs inattendues dans la colonne 'Actif' de {chemin} : {sorted(valeurs_inattendues)}. "
            "Attendu uniquement 'ACTIVE' ou 'INACTIVE' — le contrat de cette colonne a changé."
        )
    return brut.select(
        pl.col("Numero_Fiche").str.strip_prefix("RNCP").alias("code_rncp"),
        (pl.col("Actif") == "ACTIVE").alias("rncp_actif"),
    )


def charger_correspondance_rome_naf(chemin_xlsx: Path) -> pl.DataFrame:
    """Parcourt l'arborescence "Secteur NAF" du classeur France Travail (ROME -> division NAF).

    Le fichier n'est pas tabulaire : une ligne "division" (code numérique 1-2
    chiffres, libellé) précède les lignes "ROME" (code lettre+4 chiffres) qui
    en dépendent, jusqu'à la division suivante. Ce parcours reconstruit la
    relation (code_rome, naf_division) à partir de cette hiérarchie
    implicite dans les lignes du classeur.

    Raises:
        ErreurContratNafRomeFormation: aucune feuille dont le nom commence
            par "Secteur NAF" — le classeur a changé de structure.
    """
    classeur = openpyxl.load_workbook(chemin_xlsx, read_only=True, data_only=True)
    nom_feuille = next((n for n in classeur.sheetnames if n.lower().startswith("secteur naf")), None)
    if nom_feuille is None:
        raise ErreurContratNafRomeFormation(
            f"Aucune feuille dont le nom commence par 'Secteur NAF' dans {chemin_xlsx} "
            f"(feuilles présentes : {classeur.sheetnames})."
        )
    feuille = classeur[nom_feuille]

    lignes: list[dict[str, str]] = []
    division_courante: str | None = None
    libelle_courant: str | None = None
    for ligne in feuille.iter_rows(values_only=True):
        if not ligne or ligne[0] in (None, ""):
            continue
        code = str(ligne[0]).strip()
        if _MOTIF_CODE_DIVISION.match(code):
            division_courante = code.zfill(2)
            libelle_courant = str(ligne[1]) if len(ligne) > 1 and ligne[1] is not None else ""
            continue
        if _MOTIF_CODE_ROME.match(code) and division_courante is not None:
            if division_courante == DIVISION_SENTINELLE_TRANSVERSE:
                continue  # voir la constante : regroupement transverse, pas une division réelle
            lignes.append(
                {"code_rome": code, "naf_division": division_courante, "naf_division_libelle": libelle_courant or ""}
            )
    if not lignes:
        raise ErreurContratNafRomeFormation(
            f"Aucune ligne (code ROME, division NAF) extraite de la feuille {nom_feuille!r} "
            f"de {chemin_xlsx} : le format des lignes a peut-être changé."
        )
    return pl.DataFrame(lignes)


# ─── Jointure et mesure de couverture ───────────────────────────────────────


def construire_table(
    formations: pl.DataFrame, rncp_rome: pl.DataFrame, rome_naf: pl.DataFrame, etat_rncp: pl.DataFrame
) -> pl.DataFrame:
    """Assemble les trois sources. Une ligne = (formation IDÉO, code ROME, division NAF).

    Jointures internes (`inner`) à chaque étape : une ligne qui ne trouve pas
    de correspondance disparaît de la table finale plutôt que d'y apparaître
    avec des colonnes nulles — c'est `mesurer_couverture`, pas cette
    fonction, qui rend compte de ce qui a été perdu à chaque étape.

    `etat_rncp` (colonnes `code_rncp`, `rncp_actif`, voir `charger_etat_rncp`)
    est rejoint différemment, par une jointure `left` : contrairement aux
    trois jointures ci-dessus, aucune ligne n'est retirée faute de
    correspondance. L'état d'une certification (active ou radiée) est une
    information à exposer, pas un critère de sélection décidé à cette étape
    — le choix d'exclure les fiches radiées relève du calcul des débouchés.
    Une fiche présente dans l'export ROME du jour mais absente du CSV
    standard du même jour (aucun cas observé sur les exports du 2026-08-30,
    les deux fichiers provenant de la même archive) laisserait `rncp_actif`
    à `null` — un état inconnu déclaré comme tel, jamais confondu avec
    `False`.
    """
    formation_vers_rome = formations.join(
        rncp_rome, left_on="code_rncp_ideo", right_on="code_rncp_fiche", how="inner"
    )
    chaine = formation_vers_rome.join(rome_naf, on="code_rome", how="inner")
    chaine = chaine.join(etat_rncp, left_on="code_rncp_ideo", right_on="code_rncp", how="left")
    return chaine.select(
        "code_rncp_ideo",
        "libelle_formation_ideo",
        "code_nsf",
        "code_rome",
        "libelle_rome",
        "naf_division",
        "naf_division_libelle",
        "rncp_actif",
    )


def mesurer_couverture(
    formations: pl.DataFrame, rncp_rome: pl.DataFrame, rome_naf: pl.DataFrame, table_finale: pl.DataFrame
) -> RapportCouverture:
    """Un maillon par jointure, jamais un taux global : voir le docstring du module."""
    n_formations_total = formations.height
    # `infer_schema_length=0` (lecture volontairement non typée, voir `_lire_csv_utf8_sig`)
    # laisse un champ vide comme chaîne vide "", pas comme null : les deux sont exclus ici,
    # explicitement, plutôt que de compter sur une conversion implicite de polars.
    n_formations_avec_rncp = formations.filter(
        pl.col("code_rncp_ideo").is_not_null() & (pl.col("code_rncp_ideo") != "")
    ).height
    n_fiches_rncp_avec_rome = rncp_rome.select("code_rncp_fiche").unique().height
    n_formations_avec_rome = table_finale.select("code_rncp_ideo").unique().height
    codes_rome_export = set(rncp_rome.select("code_rome").unique().to_series().to_list())
    codes_rome_naf = set(rome_naf.select("code_rome").unique().to_series().to_list())
    n_rome_dans_export = len(codes_rome_export)
    n_rome_export_couverts_naf = len(codes_rome_export & codes_rome_naf)
    n_rome_finaux = table_finale.select("code_rome").unique().height

    n_lignes_finales = table_finale.height
    n_lignes_actives = table_finale.filter(pl.col("rncp_actif")).height
    n_lignes_etat_inconnu = table_finale.filter(pl.col("rncp_actif").is_null()).height
    n_formations_finales = table_finale.select("code_rncp_ideo").unique().height
    n_formations_actives = table_finale.filter(pl.col("rncp_actif")).select("code_rncp_ideo").unique().height

    maillons = [
        RapportMaillon(
            "formation_ideo -> code_rncp_renseigne",
            n_formations_total,
            n_formations_avec_rncp,
            "formations IDÉO portant un code RNCP, sur l'ensemble du référentiel",
        ),
        RapportMaillon(
            "rncp_fiche -> au_moins_un_code_rome",
            n_fiches_rncp_avec_rome,
            n_fiches_rncp_avec_rome,
            "toutes les fiches de l'export ROME couvrent par construction au moins un code ROME",
        ),
        RapportMaillon(
            "formation_ideo(avec_rncp) -> rattachee_a_un_rome",
            n_formations_avec_rncp,
            n_formations_avec_rome,
            "formations avec code RNCP dont la fiche existe dans l'export ROME du jour",
        ),
        RapportMaillon(
            "code_rome(export_rncp) -> couvert_par_naf",
            n_rome_dans_export,
            n_rome_export_couverts_naf,
            "codes ROME distincts de l'export RNCP du jour, retrouvés dans la table France "
            "Travail ROME/NAF (intersection des deux ensembles de codes)",
        ),
        RapportMaillon(
            "formation_ideo -> chaine_complete_jusqu_a_naf",
            n_formations_total,
            table_finale.select("code_rncp_ideo").unique().height,
            "part de l'ensemble du référentiel IDÉO qui atteint une division NAF par la chaîne complète",
        ),
        RapportMaillon(
            "table_finale -> lignes_rattachees_a_certification_active",
            n_lignes_finales,
            n_lignes_actives,
            "colonne 'Actif' de l'export RNCP standard du jour, exposée en 'rncp_actif' sans filtrage ; "
            f"lignes d'état inconnu (fiche absente du CSV standard du même jour) : {n_lignes_etat_inconnu}",
        ),
        RapportMaillon(
            "table_finale -> formations_distinctes_rattachees_a_certification_active",
            n_formations_finales,
            n_formations_actives,
            "formations IDÉO de la table finale dont la fiche RNCP est active (non radiée) ce jour",
        ),
    ]
    manques = [
        (
            "Aucune formation Parcoursup (dim_formation) n'est reliée à cette chaîne : aucun des "
            "huit millésimes ne porte de code RNCP, NSF ou ROME. Seul un appariement textuel des "
            "libellés serait possible, non arbitré ici (voir le docstring du module)."
        ),
        (
            "La correspondance ROME/NAF n'est qu'au niveau division (2 chiffres) : le rattachement "
            "à un établissement Sirene (sous-classe, 5 caractères) perd la granularité fine de "
            "l'activité."
        ),
    ]
    LOGGER.info("Couverture NAF/ROME/formation : %d code(s) ROME rattachés en sortie.", n_rome_finaux)
    return RapportCouverture(maillons=maillons, manques_declares=manques)


def mesurer_couverture_naf_sirene(codes_naf: list[str], divisions_couvertes: set[str]) -> RapportMaillon:
    """Couverture de la table France Travail vis-à-vis des codes NAF réellement présents dans Sirene.

    `codes_naf` : les codes NAF distincts de `activitePrincipaleEtablissement`
    dans l'agrégat commune x NAF — pas un échantillon, la population
    réelle du champ. `divisions_couvertes` : les divisions présentes dans la
    table France Travail (`naf_division` de `charger_correspondance_rome_naf`).

    Un code NAF dont les deux premiers caractères ne sont pas deux chiffres
    (aucun cas connu dans l'agrégat vérifié, mais défendu explicitement) est
    compté comme non résolu, pas ignoré silencieusement.
    """
    divisions_naf = {c[:2] for c in codes_naf if _MOTIF_NAF_SOUS_CLASSE.match(c)}
    couvertes = divisions_naf & divisions_couvertes
    return RapportMaillon(
        "division_naf(sirene) -> couverte_par_france_travail",
        len(divisions_naf),
        len(couvertes),
        f"divisions non couvertes : {sorted(divisions_naf - divisions_couvertes)}",
    )


def _diviser_naf(code_naf: str) -> str | None:
    """Les deux premiers caractères d'un code NAF sont toujours sa division — vrai en rev.1 et rev.2."""
    if len(code_naf) >= 2 and code_naf[:2].isdigit():
        return code_naf[:2]
    return None


# ─── Orchestration : chemins réels, écriture du livrable ───────────────────


def _dernier_export_rncp_rome(settings: Settings) -> Path:
    dossier = dossier_referentiels(settings) / "rncp"
    exports = sorted(dossier.glob("rncp_rome_*.csv"))
    if not exports:
        raise FileNotFoundError(
            f"Aucun export rncp_rome_*.csv dans {dossier} : lancer "
            "ingestion._referentiels_rncp.telecharger_rome avant cette étape."
        )
    return exports[-1]  # tri lexicographique = tri chronologique (AAAA-MM-JJ)


def _dernier_export_rncp_standard(settings: Settings) -> Path:
    """Le CSV standard (`rncp_AAAA-MM-JJ.csv`), distinct du membre ROME (`rncp_rome_*.csv`)
    du même dossier — d'où l'exclusion explicite de ce préfixe plutôt qu'un simple glob."""
    dossier = dossier_referentiels(settings) / "rncp"
    exports = sorted(p for p in dossier.glob("rncp_*.csv") if not p.name.startswith("rncp_rome_"))
    if not exports:
        raise FileNotFoundError(
            f"Aucun export rncp_*.csv (CSV standard) dans {dossier} : lancer "
            "ingestion._referentiels_rncp.telecharger avant cette étape."
        )
    return exports[-1]  # tri lexicographique = tri chronologique (AAAA-MM-JJ)


def construire_et_mesurer(settings: Settings | None = None) -> tuple[pl.DataFrame, RapportCouverture]:
    """Point d'entrée réel : lit les quatre sources déjà téléchargées, construit et mesure."""
    settings = settings or get_settings()
    cfg_ideo = settings.donnees.referentiels.ideo.jeux["formations"]
    formations = charger_formations_ideo(
        dossier_referentiels(settings) / "ideo" / "formations.csv", cfg_ideo.delimiteur
    )
    delimiteur_rncp = settings.donnees.referentiels.rncp.delimiteur
    rncp_rome = charger_rncp_rome(_dernier_export_rncp_rome(settings), delimiteur_rncp)
    etat_rncp = charger_etat_rncp(_dernier_export_rncp_standard(settings), delimiteur_rncp)
    rome_naf = charger_correspondance_rome_naf(dossier_referentiels(settings) / "france_travail" / "rome_naf.xlsx")

    table = construire_table(formations, rncp_rome, rome_naf, etat_rncp)
    rapport = mesurer_couverture(formations, rncp_rome, rome_naf, table)
    return table, rapport


def ecrire_table_et_rapport(settings: Settings, table: pl.DataFrame, rapport: RapportCouverture) -> tuple[Path, Path]:
    """Écrit la table (CSV — quelques milliers de lignes, un référentiel de lecture, pas un
    entrepôt analytique : voir le choix de format documenté dans le dossier de certification)
    et le rapport de couverture, à côté, sans lequel le chiffre ne serait pas déclaré."""
    dossier = settings.processed_dir / "referentiel"
    dossier.mkdir(parents=True, exist_ok=True)
    chemin_table = dossier / "naf_rome_formation.csv"
    chemin_rapport = dossier / "naf_rome_formation_couverture.json"

    with chemin_table.open("w", encoding="utf-8", newline="") as flux:
        ecrivain = csv.writer(flux, delimiter=";")
        ecrivain.writerow(table.columns)
        ecrivain.writerows(table.iter_rows())

    chemin_rapport.write_text(json.dumps(rapport.en_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return chemin_table, chemin_rapport


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    table, rapport = construire_et_mesurer()
    chemin_table, chemin_rapport = ecrire_table_et_rapport(get_settings(), table, rapport)
    LOGGER.info("Table écrite : %s (%d lignes)", chemin_table, table.height)
    LOGGER.info("Rapport de couverture écrit : %s", chemin_rapport)
    for maillon in rapport.maillons:
        LOGGER.info("  %s : %d/%d (%.1f%%)", maillon.nom, maillon.retenus, maillon.total, maillon.taux * 100)
    for manque in rapport.manques_declares:
        LOGGER.warning("Manque déclaré : %s", manque)


if __name__ == "__main__":
    main()
