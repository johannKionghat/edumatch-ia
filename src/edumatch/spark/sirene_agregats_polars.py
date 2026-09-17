"""Agrégat Sirene commune x NAF, moteur Polars — le chemin réellement emprunté en local.

## Pourquoi ce module existe à côté d'un vrai job Spark

`sirene_agregats.py` (même dossier) porte l'implémentation PySpark exigée par
le cahier des charges du projet et par le critère « structures adaptées au
volume » : elle est réelle, testée, et c'est elle qui tourne sur un cluster.
Mais l'honnêteté du choix technique impose de le confronter à l'alternative la
plus simple, pas de l'écarter par principe.

**Mesuré sur ce poste, fichier complet (`StockEtablissement.parquet`,
43 896 818 lignes, 2,2 Go, mêmes neuf colonnes, même filtre, même
regroupement) :**

| Moteur | Démarrage | Lecture + filtre + regroupement | Total |
|---|---:|---:|---:|
| Polars (`scan_parquet`, lazy) | — (pas de session à amorcer) | 18,2 s | **18,2 s** |
| PySpark (`local[*]`, JVM locale) | 18,0 s | 69,0 s | **87,0 s** |

Même résultat exact des deux côtés (vérifié ligne à ligne sur les deux
compteurs : 2 423 308 actifs-employeurs, 1 929 179 cellules commune x NAF) —
la comparaison porte donc sur la vitesse, pas sur un écart de logique.

Sur ce volume (2,2 Go, 43,9 M lignes, un calcul intermédiaire de quelques
gigaoctets), Spark est près de cinq fois plus lent que Polars : la JVM,
l'ordonnancement des tâches et le shuffle entre exécuteurs locaux coûtent plus
qu'ils ne rapportent tant que le travail tient sur un seul nœud. Ce n'est pas
propre à ce poste : c'est le seuil documenté dans l'architecture du projet
(quelques dizaines de gigaoctets de calcul intermédiaire) qui justifie un
moteur distribué, pas le nombre de lignes brutes.

**Diagnostic supplémentaire, propre à ce poste** : l'écriture Parquet par
`DataFrameWriter` de PySpark échoue ici avec
`HADOOP_HOME and hadoop.home.dir are unset` — Spark sous Windows a besoin de
`winutils.exe` pour la sémantique de commit de fichier façon HDFS, y compris
en écriture locale. La lecture n'est pas affectée (seule l'écriture appelle ce
composant). C'est pourquoi `sirene_agregats.py` matérialise son résultat en le
ramenant au pilote (`toPandas`, l'agrégat ne pèse plus que quelques centaines
de Mo) puis en réutilisant l'écrivain atomique du projet, plutôt que d'écrire
directement depuis les exécuteurs Spark — un choix cohérent avec le principe
medallion (le gold est petit), pas un contournement du problème Windows : sur
le cluster de production (Linux), l'écriture directe par Spark fonctionnerait
aussi, mais réutiliser la même primitive d'écriture qu'ailleurs dans le projet
reste préférable pour l'idempotence, quel que soit l'OS.

## La décision retenue, et son seuil de bascule

`execution.moteur_volume` (déjà présent dans `configs/*.yaml` : `local` en
dev/staging, `cluster` en prod) pilote le choix : `local` exécute ce module
(Polars), `cluster` exécute `sirene_agregats.py` (Spark) — voir
`run_sirene_agregats.py`. Le volume actuel (4,6 Go pour les quatre fichiers
Sirene retenus, dont 2,2 Go pour celui agrégé ici) ne franchit pas le seuil de
quelques dizaines de gigaoctets de travail intermédiaire qui justifierait
Spark en pratique. Ce qui ferait changer d'avis : la fusion des quatre
fichiers Sirene (le stock complet grossit chaque mois, l'historique cumulé
dépasse déjà 95 millions de lignes pour `StockEtablissementHistorique` seul),
ou un calcul qui ne tient plus dans la mémoire d'un poste de développement —
pas une préférence pour l'un des deux moteurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq

from edumatch.ingestion._flux import ecriture_atomique
from edumatch.spark.definitions import (
    COLONNE_COMMUNE,
    COLONNE_DATE_CREATION,
    COLONNE_EMPLOYEUR,
    COLONNE_ETAT,
    COLONNE_NAF25,
    COLONNE_TRANCHE,
    COLONNES_PROJECTION,
    COLONNES_SORTIE,
    ETAT_FERME,
    GRAIN,
    PALIERS_EFFECTIFS,
    SEUIL_ANNEES_CREATION_RECENTE,
    TRANCHES_VERS_PALIER,
    FiltresSirene,
)

NOM_FICHIER_SORTIE = "agregats_commune_naf.parquet"


@dataclass(frozen=True)
class RapportAgregation:
    """Volumétrie de l'agrégat produit — à confronter aux chiffres déjà mesurés."""

    nombre_cellules: int
    nb_actifs_employeurs: int
    nb_fermes_employeurs: int
    date_reference: date

    def resume(self) -> str:
        return (
            f"{self.nombre_cellules} cellules (commune x NAF), "
            f"{self.nb_actifs_employeurs} actifs-employeurs, "
            f"{self.nb_fermes_employeurs} fermés-employeurs, "
            f"référence au {self.date_reference.isoformat()}."
        )


def _colonne_palier() -> pl.Expr:
    """`trancheEffectifsEtablissement` -> son palier (§ `TRANCHES_VERS_PALIER`), sinon `None`.

    `NN` (non renseignée) et tout code non listé (aucun observé à ce jour,
    voir le contrôle qualité) tombent dans `None` : ils ne comptent dans
    aucun des six paliers de sortie, ce qui laisse leur nombre calculable par
    différence (`nb_actifs_employeurs` moins la somme des six paliers) plutôt
    que de forcer une hypothèse sur un code qui n'existe pas encore.
    """
    return pl.col(COLONNE_TRANCHE).replace_strict(TRANCHES_VERS_PALIER, default=None)


def agreger_polars(chemin: Path, date_reference: date, filtres: FiltresSirene) -> pl.DataFrame:
    """Lit `chemin` en projection sur les 9 colonnes utiles et produit l'agrégat commune x NAF.

    Args:
        chemin: le fichier `StockEtablissement.parquet`, complet ou
            échantillon — la fonction ne connaît pas sa taille, seulement son
            schéma.
        date_reference: date à laquelle l'ancienneté est calculée. Toujours
            la date de publication du stock Sirene (`date_publication_stock`
            du manifeste, résolue par l'appelant), jamais `date.today()` : un
            job rejoué plus tard sur le même stock doit produire le même
            résultat (idempotence), ce qu'une date d'exécution romprait.
        filtres: résolus depuis la configuration (`resoudre_filtres`).

    Le filtre `etatAdministratifEtablissement` retient à la fois l'état
    configuré (`filtres.etat_actif`, `'A'` aujourd'hui) et l'état fermé
    (`ETAT_FERME`, `'F'`) — voir la note sur les cessations dans
    `edumatch.spark.definitions`. Les lignes sans commune connue sont exclues
    : sans commune, une ligne ne peut pas être placée sur le grain de cet
    agrégat, quel que soit son état.
    """
    lf = pl.scan_parquet(chemin).select(list(COLONNES_PROJECTION))
    lf = lf.filter(pl.col(COLONNE_COMMUNE).is_not_null())
    if filtres.filtrer_employeur:
        lf = lf.filter(pl.col(COLONNE_EMPLOYEUR) == filtres.valeur_employeur)
    lf = lf.filter(pl.col(COLONNE_ETAT).is_in([filtres.etat_actif, ETAT_FERME]))

    lf = lf.with_columns(
        [
            (pl.col(COLONNE_ETAT) == filtres.etat_actif).alias("_est_actif"),
            _colonne_palier().alias("_palier"),
            pl.col(COLONNE_NAF25).is_not_null().alias("_naf25_renseigne"),
            (
                (pl.lit(date_reference) - pl.col(COLONNE_DATE_CREATION)).dt.total_days() / 365.25
            ).alias("_age_annees"),
        ]
    )

    aggregations = [
        pl.col("_est_actif").sum().cast(pl.Int64).alias("nb_actifs_employeurs"),
        (~pl.col("_est_actif")).sum().cast(pl.Int64).alias("nb_fermes_employeurs"),
    ]
    for palier in PALIERS_EFFECTIFS:
        aggregations.append(
            (pl.col("_est_actif") & (pl.col("_palier") == palier))
            .sum()
            .cast(pl.Int64)
            .alias(f"nb_tranche_{palier}")
        )
    aggregations.append(
        (pl.col("_est_actif") & pl.col("_naf25_renseigne")).sum().cast(pl.Int64).alias("nb_naf25_renseigne")
    )
    aggregations.append(
        pl.col("_age_annees").filter(pl.col("_est_actif")).mean().alias("age_moyen_annees")
    )
    aggregations.append(
        (pl.col("_est_actif") & (pl.col("_age_annees") <= SEUIL_ANNEES_CREATION_RECENTE))
        .sum()
        .cast(pl.Int64)
        .alias("nb_crees_moins_3ans")
    )

    resultat = (
        lf.group_by(list(GRAIN))
        .agg(aggregations)
        .with_columns(pl.lit(date_reference).alias("date_reference"))
        .sort(list(GRAIN))
        .collect()
    )
    return resultat.select(list(COLONNES_SORTIE))


def rapport_depuis_agregat(agregat: pl.DataFrame, date_reference: date) -> RapportAgregation:
    return RapportAgregation(
        nombre_cellules=agregat.height,
        nb_actifs_employeurs=int(agregat["nb_actifs_employeurs"].sum()),
        nb_fermes_employeurs=int(agregat["nb_fermes_employeurs"].sum()),
        date_reference=date_reference,
    )


def ecrire_agregats(agregat: pl.DataFrame, destination: Path) -> None:
    """Écrit l'agrégat en Parquet, par fichier temporaire renommé (idempotence).

    Même primitive que la couche gold Parcoursup
    (`edumatch.transform.etoile.ecrire_etoile`) : un lecteur concurrent ou une
    reprise après coupure ne voit jamais un fichier à moitié écrit.
    """
    table = agregat.to_arrow()
    with ecriture_atomique(destination / NOM_FICHIER_SORTIE, mode="wb") as flux:
        pq.write_table(table, flux, compression="snappy")
