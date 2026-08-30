"""Agrégat Sirene commune x NAF (E17), moteur Spark — le chemin du cluster de production.

Même agrégation, même grain, mêmes neuf colonnes et mêmes règles métier que
`sirene_agregats_polars.py` (les deux importent leurs définitions communes de
`definitions.py`, pour qu'une correction de règle ne puisse pas s'appliquer à
un seul des deux moteurs sans que l'autre diverge en silence). Ce module
existe pour deux raisons distinctes, aucune des deux n'étant « c'est plus
rapide aujourd'hui » — la mesure dit l'inverse, voir
`sirene_agregats_polars.py` :

1. Le critère 2.4 du bloc 2 (« structures adaptées au volume ») et le plan
   d'exécution du projet exigent un traitement distribué réel, pas une
   promesse. `run_sirene_agregats.py` bascule sur ce module dès que
   `execution.moteur_volume` vaut `cluster` (prod) — configuration déjà
   présente, pas ajoutée pour l'occasion.
2. La trajectoire de volume dépasse déjà, ailleurs dans Sirene, ce qu'un
   poste de développement absorbe confortablement :
   `StockEtablissementHistorique` compte 95 865 102 lignes à lui seul, et le
   stock est republié — donc grossit — chaque mois. Le jour où ce job doit
   fusionner plusieurs de ces fichiers plutôt qu'en projeter un seul, le
   calcul intermédiaire (jointure entre historiques, pas seulement un
   comptage par groupe) peut dépasser le seuil de quelques dizaines de
   gigaoctets où un moteur distribué cesse d'être une option.

## La preuve du filtrage à la lecture (predicate pushdown)

Vérifiée par `df.explain(True)` sur ce job (voir
`tests/data/test_spark_sirene_agregats.py::test_explain_montre_projection_et_pushdown`) :
le plan physique porte `ReadSchema` limité aux neuf colonnes utiles (jamais
les 54 du fichier), et `PushedFilters` liste les conditions déjà traduites en
filtres Parquet (`IsNotNull`, `EqualTo`, `In`) — Spark ne décompresse jamais
les groupes de lignes qui ne peuvent statistiquement pas satisfaire ces
filtres, avant même de les lire en mémoire.

## Écriture : ramenée au pilote, pas laissée aux exécuteurs

`DataFrameWriter.parquet()` échoue sur ce poste de développement (Windows,
sans `winutils.exe` — voir le diagnostic complet dans
`sirene_agregats_polars.py`) : Spark a besoin de la sémantique de commit de
fichier de Hadoop même pour écrire en local. Plutôt que de contourner ce
point par une configuration Hadoop supplémentaire à maintenir sur chaque
poste, ce module convertit le résultat agrégé — déjà réduit à environ
1,9 million de lignes, quelques centaines de Mo, jamais les 43,9 millions de
départ — en Arrow (`toPandas`) puis réutilise l'écrivain atomique du projet.
Le travail distribué (lecture, filtre, `groupBy`, shuffle) reste entièrement
dans Spark ; seule la matérialisation finale, déjà petite, sort du moteur.
Sur le cluster de production (Linux), l'écriture directe par Spark
fonctionnerait aussi — ce choix n'est donc pas un correctif pour Windows,
c'est une cohérence délibérée avec l'écrivain déjà utilisé par
`edumatch.transform.etoile` et par le moteur Polars ci-dessus.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pyspark.sql import Column
from pyspark.sql import DataFrame as SparkDataFrame
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import BooleanType

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
from edumatch.spark.sirene_agregats_polars import NOM_FICHIER_SORTIE, RapportAgregation


def construire_session(nom_application: str = "edumatch-sirene-agregats") -> SparkSession:
    """Session Spark locale, journal réduit au strict nécessaire.

    `local[*]` utilise tous les cœurs disponibles du poste ou du nœud qui
    exécute le job — un vrai déploiement cluster (Scaleway, à partir du J8)
    remplacerait ce seul appel par un maître `spark://` ou `k8s://`, sans
    toucher au reste du module : c'est précisément ce que sépare la
    construction de la session de la logique d'agrégation ci-dessous.
    """
    session = (
        SparkSession.builder.master("local[*]")
        .appName(nom_application)
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    return session


def lire_projection(spark: SparkSession, chemin: Path) -> SparkDataFrame:
    """Lit `chemin` en ne conservant que les 9 colonnes utiles : la projection prouvée par `explain()`."""
    return spark.read.parquet(str(chemin)).select(*COLONNES_PROJECTION)


def _palier_effectifs(colonne: str) -> Column:
    """Traduit `TRANCHES_VERS_PALIER` en cascade `when/otherwise` Spark, colonne par colonne.

    Spark n'a pas d'équivalent direct de `Series.replace_strict` de Polars :
    la cascade explicite reste la traduction la plus lisible d'un dictionnaire
    de correspondance fini, et elle est directement comparée par les tests à
    l'implémentation Polars sur les mêmes données.
    """
    expression = F.lit(None).cast("string")
    for code, palier in TRANCHES_VERS_PALIER.items():
        expression = F.when(F.col(colonne) == code, F.lit(palier)).otherwise(expression)
    return expression


def agreger(df: SparkDataFrame, date_reference: date, filtres: FiltresSirene) -> SparkDataFrame:
    """Applique les mêmes filtres et le même regroupement que `sirene_agregats_polars.agreger_polars`.

    Voir cette dernière pour la justification métier (cessations conservées,
    diffusibilité non appliquée, référence temporelle figée sur la date de
    publication du stock) : ce module ne la répète pas, il la traduit dans
    l'API Spark.
    """
    df = df.filter(F.col(COLONNE_COMMUNE).isNotNull())
    if filtres.filtrer_employeur:
        df = df.filter(F.col(COLONNE_EMPLOYEUR) == filtres.valeur_employeur)
    df = df.filter(F.col(COLONNE_ETAT).isin(filtres.etat_actif, ETAT_FERME))

    df = df.withColumn("_est_actif", (F.col(COLONNE_ETAT) == filtres.etat_actif).cast(BooleanType()))
    df = df.withColumn("_palier", _palier_effectifs(COLONNE_TRANCHE))
    df = df.withColumn("_naf25_renseigne", F.col(COLONNE_NAF25).isNotNull())
    df = df.withColumn(
        "_age_annees",
        F.datediff(F.lit(date_reference), F.col(COLONNE_DATE_CREATION)) / 365.25,
    )

    def _compte_si_actif(condition: Column) -> Column:
        return F.sum((F.col("_est_actif") & condition).cast("int"))

    aggregations = [
        F.sum(F.col("_est_actif").cast("int")).alias("nb_actifs_employeurs"),
        F.sum((~F.col("_est_actif")).cast("int")).alias("nb_fermes_employeurs"),
    ]
    for palier in PALIERS_EFFECTIFS:
        aggregations.append(_compte_si_actif(F.col("_palier") == palier).alias(f"nb_tranche_{palier}"))
    aggregations.append(_compte_si_actif(F.col("_naf25_renseigne")).alias("nb_naf25_renseigne"))
    aggregations.append(
        F.avg(F.when(F.col("_est_actif"), F.col("_age_annees"))).alias("age_moyen_annees")
    )
    aggregations.append(
        _compte_si_actif(F.col("_age_annees") <= SEUIL_ANNEES_CREATION_RECENTE).alias("nb_crees_moins_3ans")
    )

    resultat = df.groupBy(*GRAIN).agg(*aggregations).withColumn(
        "date_reference", F.lit(date_reference)
    )
    return resultat.select(*COLONNES_SORTIE).orderBy(*GRAIN)


def rapport_depuis_agregat(agregat_pandas: pd.DataFrame, date_reference: date) -> RapportAgregation:
    return RapportAgregation(
        nombre_cellules=len(agregat_pandas),
        nb_actifs_employeurs=int(agregat_pandas["nb_actifs_employeurs"].sum()),
        nb_fermes_employeurs=int(agregat_pandas["nb_fermes_employeurs"].sum()),
        date_reference=date_reference,
    )


def ecrire_agregats_spark(resultat: SparkDataFrame, destination: Path) -> pd.DataFrame:
    """Ramène le résultat agrégé (déjà réduit) au pilote et l'écrit avec l'écrivain atomique du projet.

    Voir le docstring de tête pour la raison (l'écriture directe par
    `DataFrameWriter` échoue sur ce poste sans `winutils.exe`). Retourne le
    `DataFrame` pandas écrit, pour que l'appelant puisse en tirer un rapport
    de volumétrie sans relire le fichier qui vient d'être produit.
    """
    trame = resultat.toPandas()
    table = pa.Table.from_pandas(trame, preserve_index=False)
    with ecriture_atomique(destination / NOM_FICHIER_SORTIE, mode="wb") as flux:
        pq.write_table(table, flux, compression="snappy")
    return trame
