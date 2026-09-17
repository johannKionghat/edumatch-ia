"""Génère les échantillons versionnés de `data/samples/`.

`data/samples/` est la seule exception versionnée de `data/` (voir
`.gitignore`) : quelques centaines de lignes par source, suffisantes pour que
la suite de tests tourne sans télécharger les 4,6 Go de sources complètes.
Ce module lit `data/raw/` et `data/external/`, déjà peuplés par les
connecteurs (`parcoursup.py`, `sirene.py`, `referentiels.py`), et écrit dans
`data/samples/` — il ne modifie ni ne supprime jamais rien dans `raw/` ou
`external/`.

Méthode d'échantillonnage — systématique, pas aléatoire, pas les N premières
lignes :

    Un tirage des N premières lignes serait biaisé si la source est triée
    (Sirene l'est, par SIREN). Un tirage aléatoire pourrait, par malchance,
    ne prendre que le centre du fichier et manquer les extrémités. Un pas
    fixe (« une ligne sur K », K calculé pour viser la taille demandée)
    balaie tout le fichier, retombe toujours sur la même ligne pour un
    fichier inchangé, et ne dépend d'aucune graine aléatoire.

Minimisation des données personnelles (RGPD art. 5) — le sujet réel de cette
étape, et sa qualification juridique exacte :

    `StockUniteLegale` et `StockUniteLegaleHistorique` portent le nom, les
    prénoms, le pseudonyme et le sexe des entrepreneurs individuels : des
    personnes physiques. Un échantillon de test n'a besoin ni de deviner
    à qui appartient une ligne, ni de vérifier l'orthographe d'un prénom :
    il vérifie un schéma, des types, des valeurs. Ces colonnes directes
    d'identité sont donc exclues du fichier écrit, pas remplacées par une
    valeur inventée — inventer un faux nom serait une donnée simulée,
    interdite par ailleurs dans ce projet.

    Retirer ces neuf colonnes ne rend PAS l'échantillon anonyme, et cette
    docstring l'a longtemps affirmé à tort pour `StockEtablissement` et
    `StockEtablissementHistorique`. Une entreprise individuelle n'a pas de
    personnalité juridique distincte de la personne qui la crée : sa
    dénomination commerciale porte très souvent son patronyme
    (`denominationUsuelleEtablissement`, `enseigne1Etablissement` — retenues
    ici, notamment dans `StockEtablissementHistorique`, échantillonné sans
    restriction de colonnes). Vérifié sur le fichier source complet : 56,4 %
    des lignes de `StockUniteLegale` (16 890 687 sur 29 922 486) portent la
    catégorie juridique 1000, entrepreneur individuel ; en joignant sur le
    SIREN les colonnes de nom retirées ici avec les dénominations conservées
    dans `StockEtablissementHistorique`, le nom réapparaît en clair dans des
    dizaines de milliers de cas (ex. SIREN 006341887 → « RENE BLANC » côté
    unité légale, dénomination d'établissement « BLANC RENE »). Le SIREN
    étant conservé dans les deux fichiers, cette jointure ne demande aucun
    moyen hors de portée : elle se fait avec le fichier source public
    lui-même, déjà téléchargé pour produire cet échantillon.

    La qualification correcte est donc **pseudonymisation** (RGPD art. 4.5) :
    l'attribution à une personne précise exige une information
    supplémentaire (ici, la jointure SIREN vers le fichier source), pas
    **anonymisation** — qui exigerait que la ré-identification soit
    impossible, y compris par recoupement avec la source. L'échantillon
    reste donc dans le champ d'application du RGPD, et le régime de licence
    de réutilisation (Licence Ouverte v2.0) ne s'y substitue pas : voir
    `data/samples/README.md`, section « Base légale ».

Licence ODbL des jeux ONISEP (IDÉO) :

    L'ODbL impose le partage à l'identique sur toute base dérivée
    redistribuée. Un extrait, même minuscule, redistribué dans ce dépôt en
    est une. La condition n'interdit pas l'extrait : elle impose trois
    choses, réunies dans `data/samples/README.md` — l'attribution de la
    source, la mention explicite que CET extrait précis reste sous ODbL
    (le dépôt dans son ensemble n'a pas besoin d'être sous ODbL, seule la
    donnée elle-même l'est), et l'absence de toute mesure qui restreindrait
    un tiers à la réutiliser. Le RNCP, en Licence Ouverte v2.0, n'a pas
    cette contrainte.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from edumatch.config import Settings, load_settings
from edumatch.ingestion._echantillons_communs import EchantillonResultat
from edumatch.ingestion._echantillons_communs import ecrire_csv as _ecrire_csv
from edumatch.ingestion._echantillons_communs import empreinte as _empreinte
from edumatch.ingestion._echantillons_communs import indices_systematiques as _indices_systematiques
from edumatch.ingestion._echantillons_communs import lire_csv as _lire_csv
from edumatch.ingestion._echantillons_communs import manifeste_source as _manifeste_source
from edumatch.ingestion.echantillons_referentiels import (
    generer_echantillon_france_travail,
    generer_echantillon_rncp,
    generer_echantillon_rncp_rome,
    generer_echantillons_ideo,
)

LOGGER = logging.getLogger(__name__)

# ─── Politique de minimisation — voir docstring du module ────────────────────

COLONNES_PERSONNELLES_UNITE_LEGALE: frozenset[str] = frozenset(
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

# Les 9 colonnes utiles de StockEtablissement pour le job Spark d'agrégation
# — voir docs/donnees.html. L'échantillon
# n'a pas besoin des 45 autres : elles ne seront jamais lues en production.
COLONNES_ETABLISSEMENT: tuple[str, ...] = (
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

FICHIERS_SIRENE_SANS_RESTRICTION: frozenset[str] = frozenset(
    {"StockEtablissementHistorique"}
)


def _provenance_parcoursup(settings: Settings, annee: int) -> dict[str, str]:
    manifeste = _manifeste_source(settings.raw_dir / "parcoursup" / "manifeste.json")
    entree = manifeste.get(str(annee))
    if entree is None:
        raise KeyError(f"Aucune entrée pour le millésime {annee} dans le manifeste Parcoursup.")
    # Parcoursup ne publie pas de date de mise à jour distincte de la date de
    # collecte : date_telechargement est la seule date disponible.
    return {
        "url": entree["url"],
        "date_source": entree["date_telechargement"],
        "empreinte_sha256_source": entree["empreinte_sha256"],
    }


def _provenance_sirene(settings: Settings, fichier: str) -> dict[str, str]:
    manifeste = _manifeste_source(settings.raw_dir / "sirene" / "manifeste.json")
    entree = manifeste.get(fichier)
    if entree is None:
        raise KeyError(f"Aucune entrée pour {fichier} dans le manifeste Sirene.")
    return {
        "url": entree["url"],
        "date_source": entree["date_publication_stock"],
        "empreinte_sha256_source": entree["empreinte_sha256"],
    }


def _echantillonner_parquet(
    chemin: Path, colonnes: list[str], cible: int, taille_lot: int
) -> tuple[pa.Table, int]:
    """Échantillonnage systématique d'un Parquet, en flux (jamais chargé en entier).

    Lit le fichier par lots de `taille_lot` lignes, en ne décodant que les
    colonnes demandées (projection) : c'est ce qui rend la lecture d'un
    fichier de plusieurs gigaoctets praticable pour produire un échantillon
    de quelques centaines de lignes.
    """
    fichier = pq.ParquetFile(chemin)
    total = fichier.metadata.num_rows
    indices_restants = _indices_systematiques(total, cible)
    if not indices_restants:
        return pa.table({c: [] for c in colonnes}), total

    morceaux: list[pa.Table] = []
    vus = 0
    for lot in fichier.iter_batches(batch_size=taille_lot, columns=colonnes):
        n = lot.num_rows
        locaux = [i - vus for i in indices_restants if vus <= i < vus + n]
        if locaux:
            morceaux.append(pa.Table.from_batches([lot]).take(pa.array(locaux, type=pa.int64())))
            indices_restants = indices_restants[len(locaux) :]
        vus += n
        if not indices_restants:
            break
    table = pa.concat_tables(morceaux) if morceaux else pa.table({c: [] for c in colonnes})
    return table, total


def generer_echantillon_parcoursup(settings: Settings) -> list[EchantillonResultat]:
    """Un échantillon par millésime : c'est la diversité de schéma (85 à 118 colonnes) qui compte ici."""
    cfg = settings.donnees.parcoursup
    cible = settings.donnees.echantillons_test.lignes_par_millesime_parcoursup
    resultats: list[EchantillonResultat] = []
    for annee in cfg.millesimes:
        source = settings.raw_dir / "parcoursup" / f"parcoursup_{annee}.csv"
        if not source.exists():
            LOGGER.warning("Parcoursup %s introuvable, millésime ignoré : %s", annee, source)
            continue
        # utf-8-sig : les 8 CSV Parcoursup portent un BOM en tête de fichier
        # (vérifié : EF BB BF avant "session" sur 2018) — non déclaré en
        # configuration (aucun champ d'encodage pour Parcoursup), donc
        # constaté ici. Sans le -sig, le BOM resterait collé au nom de la
        # première colonne ("﻿session" au lieu de "session").
        entete, lignes = _lire_csv(source, "utf-8-sig", cfg.delimiteur)
        indices = _indices_systematiques(len(lignes), cible)
        lignes_retenues = [lignes[i] for i in indices]
        sortie = settings.samples_dir / "parcoursup" / f"parcoursup_{annee}.csv"
        _ecrire_csv(sortie, entete, lignes_retenues, cfg.delimiteur)
        resultats.append(
            EchantillonResultat(
                source=f"parcoursup_{annee}",
                chemin_source=source,
                chemin_sortie=sortie,
                lignes_source=len(lignes),
                lignes_echantillon=len(lignes_retenues),
                colonnes_retenues=entete,
                colonnes_exclues=[],
                licence="Licence Ouverte v2.0",
                empreinte_sha256=_empreinte(sortie),
                **_provenance_parcoursup(settings, annee),
            )
        )
    return resultats


def _colonnes_sirene(fichier: str, colonnes_disponibles: list[str]) -> tuple[list[str], list[str]]:
    """Colonnes retenues et exclues pour un fichier Sirene donné — voir docstring du module."""
    if fichier == "StockEtablissement":
        retenues = [c for c in COLONNES_ETABLISSEMENT if c in colonnes_disponibles]
        return retenues, [c for c in colonnes_disponibles if c not in retenues]
    if fichier in FICHIERS_SIRENE_SANS_RESTRICTION:
        return list(colonnes_disponibles), []
    exclues = [c for c in colonnes_disponibles if c in COLONNES_PERSONNELLES_UNITE_LEGALE]
    retenues = [c for c in colonnes_disponibles if c not in COLONNES_PERSONNELLES_UNITE_LEGALE]
    return retenues, exclues


def generer_echantillons_sirene(settings: Settings) -> list[EchantillonResultat]:
    """Un échantillon Parquet par fichier Sirene, colonnes personnelles exclues (voir docstring)."""
    cfg = settings.donnees.sirene
    cible = settings.donnees.echantillons_test.lignes_par_fichier_sirene
    taille_lot = settings.donnees.echantillons_test.taille_lot_sirene
    resultats: list[EchantillonResultat] = []
    for fichier in cfg.fichiers:
        source = settings.raw_dir / "sirene" / f"{fichier}.parquet"
        if not source.exists():
            LOGGER.warning("Sirene %s introuvable, fichier ignoré : %s", fichier, source)
            continue
        colonnes_disponibles = pq.ParquetFile(source).schema_arrow.names
        retenues, exclues = _colonnes_sirene(fichier, colonnes_disponibles)
        table, total = _echantillonner_parquet(source, retenues, cible, taille_lot)
        sortie = settings.samples_dir / "sirene" / f"{fichier}.parquet"
        sortie.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, sortie)
        resultats.append(
            EchantillonResultat(
                source=fichier,
                chemin_source=source,
                chemin_sortie=sortie,
                lignes_source=total,
                lignes_echantillon=table.num_rows,
                colonnes_retenues=retenues,
                colonnes_exclues=exclues,
                licence="Licence Ouverte v2.0",
                empreinte_sha256=_empreinte(sortie),
                **_provenance_sirene(settings, fichier),
            )
        )
    return resultats


def _ecrire_manifeste(settings: Settings, resultats: list[EchantillonResultat]) -> Path:
    """Consigne provenance, méthode et licence de chaque échantillon — le lignage de `data/samples/`."""
    manifeste = {
        "date_generation": datetime.now(UTC).isoformat(),
        "methode": "echantillonnage systematique a pas fixe, sans graine aleatoire",
        "echantillons": [
            {
                "source": r.source,
                "chemin_source": str(r.chemin_source.relative_to(settings.data_root)),
                "chemin_sortie": str(r.chemin_sortie.relative_to(settings.samples_dir)),
                "lignes_source": r.lignes_source,
                "lignes_echantillon": r.lignes_echantillon,
                "colonnes_retenues": r.colonnes_retenues,
                "colonnes_exclues": r.colonnes_exclues,
                "licence": r.licence,
                "url": r.url,
                "date_source": r.date_source,
                "empreinte_sha256_source": r.empreinte_sha256_source,
                "empreinte_sha256": r.empreinte_sha256,
            }
            for r in resultats
        ],
    }
    chemin = settings.samples_dir / "manifeste.json"
    chemin.write_text(json.dumps(manifeste, indent=2, ensure_ascii=False), encoding="utf-8")
    return chemin


def generer_tous_les_echantillons(settings: Settings | None = None) -> list[EchantillonResultat]:
    """Point d'entrée : régénère l'intégralité de `data/samples/` depuis `raw/` et `external/`.

    Sans `settings` explicite, charge la configuration `prod` — jamais `dev`,
    qui réduit `donnees.parcoursup.millesimes` à deux années pour itérer plus
    vite. Un échantillon généré sous `dev` perdrait justement ce que cette
    étape doit couvrir : la diversité de schéma sur les huit millésimes
    (85 à 118 colonnes selon l'année).
    """
    parametres = settings or load_settings("prod")
    resultats: list[EchantillonResultat] = []
    resultats += generer_echantillon_parcoursup(parametres)
    resultats += generer_echantillons_sirene(parametres)
    resultats += generer_echantillons_ideo(parametres)
    resultats += generer_echantillon_rncp(parametres)
    resultats += generer_echantillon_rncp_rome(parametres)
    resultats += generer_echantillon_france_travail(parametres)
    _ecrire_manifeste(parametres, resultats)
    return resultats


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    resultats = generer_tous_les_echantillons()
    total_lignes = sum(r.lignes_echantillon for r in resultats)
    LOGGER.info("%d échantillons générés, %d lignes au total.", len(resultats), total_lignes)


if __name__ == "__main__":
    main()
