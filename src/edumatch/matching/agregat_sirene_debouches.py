"""Agrégat Sirene département x division NAF, k-anonymisé — le grain territorial du
terme de débouchés (`matching/debouches.py`, qui consomme ce module et documente la mesure
d'ensemble : l'obstacle de la chaîne NAF/ROME/formation, le choix d'appariement textuel, ce
que le terme expose ou pas).

## Le grain territorial : k-anonymat et le filtre `diffusible`

`docs/risques-aipd.html` (R2) a tranché : k = 5,
au grain **département x NAF**, jamais au grain commune (qui perdrait
90,6 % des cellules et 46,9 % des établissements réels pour la même
protection). Ce module construit directement l'agrégat à ce grain, sans
jamais matérialiser ni exposer le grain commune.

Une contrainte, pas un choix, réduit encore la finesse : la chaîne
NAF/ROME/formation ne résout jamais plus finement que la **division**
NAF (2 caractères) — limite de la table France Travail ROME/NAF. Le terme
de débouchés ne peut donc jamais exploiter le grain département x NAF à 5
caractères que R2 mesure par ailleurs : il n'y a rien à y rattacher. Le
grain retenu ici, département x **division** NAF, est de toute façon celui
que R2 identifie comme le plus sûr (10,4 % des cellules perdues à k=5,
contre 35,0 % à 5 caractères, sur le même département).

`filtres.diffusible` (`configs/base.yaml`, `donnees.sirene.filtres`) est
déclaré mais **non appliqué** par l'agrégat commune x NAF
(`spark/definitions.py` le documente explicitement). Ce module l'applique :
mesuré sur le fichier Sirene complet, 20 488 établissements
actifs-employeurs (0,85 % des 2 423 308 rattachés à une commune) portent un
statut non diffusible et sont exclus ici — du même ordre de grandeur que les
20 501 (0,84 %) déjà mesurés par la gouvernance sur le grain commune.

## Ce que ce module ne fait jamais

Il ne renvoie jamais un nombre d'établissements sous le seuil de
k-anonymat, même pour distinguer un zéro réel d'une cellule supprimée : les
deux cas sont distingués par un ensemble binaire d'*existence* (au moins un
établissement, sans son effectif exact), jamais par l'effectif intermédiaire
lui-même — voir `appliquer_k_anonymat`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

ETAT_ACTIF = "A"
VALEUR_EMPLOYEUR = "O"
VALEUR_DIFFUSIBLE = "O"

COLONNES_SIRENE_DEBOUCHES: tuple[str, ...] = (
    "codeCommuneEtablissement",
    "activitePrincipaleEtablissement",
    "etatAdministratifEtablissement",
    "caractereEmployeurEtablissement",
    "statutDiffusionEtablissement",
)

# DOM/TOM : le département est porté par les trois premiers caractères du
# code commune (ex. "97105" -> "971"), pas les deux premiers comme en
# métropole et en Corse ("2A004" -> "2A" fonctionne déjà avec la règle à
# deux caractères, aucun cas particulier n'est nécessaire pour la Corse).
_PREFIXES_DOM_TOM: tuple[str, ...] = ("97", "98")


def departement_depuis_commune(code_commune: str | None) -> str | None:
    """Département INSEE porté par un code commune (5 caractères) — voir le docstring du module.

    Vérifié par comparaison d'ordre de grandeur avec `docs/risques-aipd.html` (R2) :
    55 091 cellules département x NAF (5 caractères) mesurées par cette règle
    contre 52 493 dans le tableau de la gouvernance — écart de 4,7 %, sans
    effet sur la décision qu'il documente (méthode de rattachement légèrement
    différente, non retracée par la gouvernance).
    """
    if not code_commune or len(code_commune) < 2:
        return None
    if code_commune[:2] in _PREFIXES_DOM_TOM:
        return code_commune[:3] if len(code_commune) >= 3 else None
    return code_commune[:2]


@dataclass(frozen=True)
class RapportKAnonymat:
    """Ce que le seuil de k-anonymat coûte, mesuré, jamais supposé (R2)."""

    grain: str
    k: int
    cellules_totales: int
    cellules_supprimees: int
    etablissements_totaux: int
    etablissements_perdus: int

    @property
    def part_cellules_supprimees(self) -> float:
        return self.cellules_supprimees / self.cellules_totales if self.cellules_totales else 0.0

    @property
    def part_etablissements_perdus(self) -> float:
        return self.etablissements_perdus / self.etablissements_totaux if self.etablissements_totaux else 0.0

    def en_dict(self) -> dict[str, object]:
        return {
            "grain": self.grain,
            "k": self.k,
            "cellules_totales": self.cellules_totales,
            "cellules_supprimees": self.cellules_supprimees,
            "part_cellules_supprimees": round(self.part_cellules_supprimees, 4),
            "etablissements_totaux": self.etablissements_totaux,
            "etablissements_perdus": self.etablissements_perdus,
            "part_etablissements_perdus": round(self.part_etablissements_perdus, 4),
        }


def construire_agregat_departement_naf(chemin_sirene: Path) -> pl.DataFrame:
    """Lit `StockEtablissement.parquet` en projection sur 5 colonnes et agrège au grain
    (département, division NAF) — actif, employeur, **diffusible** (voir le docstring du module
    pour l'écart mesuré avec l'agrégat commune x NAF, qui n'applique pas ce filtre).
    """
    lf = pl.scan_parquet(chemin_sirene).select(list(COLONNES_SIRENE_DEBOUCHES))
    lf = lf.filter(
        (pl.col("etatAdministratifEtablissement") == ETAT_ACTIF)
        & (pl.col("caractereEmployeurEtablissement") == VALEUR_EMPLOYEUR)
        & (pl.col("statutDiffusionEtablissement") == VALEUR_DIFFUSIBLE)
        & pl.col("codeCommuneEtablissement").is_not_null()
    )
    lf = lf.with_columns(
        pl.col("codeCommuneEtablissement")
        .map_elements(departement_depuis_commune, return_dtype=pl.Utf8)
        .alias("departement"),
        pl.col("activitePrincipaleEtablissement").str.slice(0, 2).alias("naf_division"),
    )
    lf = lf.filter(pl.col("departement").is_not_null())
    resultat = (
        lf.group_by(["departement", "naf_division"])
        .agg(pl.len().cast(pl.Int64).alias("nb_actifs_employeurs_diffusibles"))
        .sort(["departement", "naf_division"])
        .collect()
    )
    return resultat


def appliquer_k_anonymat(agregat: pl.DataFrame, k: int) -> tuple[pl.DataFrame, pl.DataFrame, RapportKAnonymat]:
    """Applique le seuil de k-anonymat (R2) et retourne trois choses distinctes :

    1. `conserve` — les cellules à effectif >= k, avec leur effectif : la
       seule table où l'appelant peut lire un nombre d'établissements.
    2. `cellules_non_vides` — l'ensemble (département, division NAF) qui a
       au moins un établissement, **sans effectif** : sert uniquement à
       distinguer un zéro réel (formation sans aucun débouché mesuré) d'une
       cellule supprimée par le seuil, sans jamais exposer un effectif
       inférieur à k.
    3. le rapport de ce que le seuil a coûté.
    """
    cellules_non_vides = agregat.select("departement", "naf_division")
    conserve = agregat.filter(pl.col("nb_actifs_employeurs_diffusibles") >= k)
    supprimees = agregat.filter(pl.col("nb_actifs_employeurs_diffusibles") < k)
    rapport = RapportKAnonymat(
        grain="departement x division_naf",
        k=k,
        cellules_totales=agregat.height,
        cellules_supprimees=supprimees.height,
        etablissements_totaux=int(agregat["nb_actifs_employeurs_diffusibles"].sum()),
        etablissements_perdus=int(supprimees["nb_actifs_employeurs_diffusibles"].sum()),
    )
    return conserve, cellules_non_vides, rapport
