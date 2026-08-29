"""Réconciliation bronze vers silver des huit millésimes Parcoursup (E15).

Ce module ne connaît qu'un DataFrame par millésime — chargé depuis un CSV
(`reconcilier`) ou déjà chargé par un moteur tiers, DuckDB en particulier
(`reconcilier_dataframes`, utilisée par le modèle dbt de `../dbt/`). C'est
volontaire : la seule chose qui distingue les deux appelants est *comment*
le CSV est lu, jamais la façon dont il est réconcilié.

Trois opérations, dans l'ordre, appliquées à chaque millésime avant l'union :

1. **Reconstruction de la clé.** `cod_aff_form` n'existe pas en 2018 et 2019 :
   elle se retrouve dans le paramètre `g_ta_cod` de l'URL portée par
   `lien_form_psup` (ADR 0010), vérifiée exacte partout où les deux
   coexistent. Couverture mesurée : 92,4 % (2018), 94,6 % (2019) — le reste
   des lignes garde une clé manquante, ce n'est pas une erreur de ce module,
   c'est un fait de la source.
2. **Harmonisation du schéma.** Les 128 colonnes classées dans
   `modele.variables` (ADR 0013) sont la référence : chacune apparaît dans le
   résultat, qu'elle existe ou non dans le millésime traité. Une colonne
   absente d'un millésime donné (parce que non encore publiée) devient une
   colonne remplie de valeurs manquantes — jamais une colonne absente du
   schéma final, ce qui romprait l'union des huit millésimes en un seul bloc.
3. **Typage.** Générique, pas une table de 128 lignes à tenir à jour à la
   main : une colonne est numérique si elle se convertit *sans perte* (aucune
   valeur non vide ne devient manquante) sur l'ensemble des huit millésimes,
   entière si toutes ses valeurs non nulles sont des entiers, sinon décimale.
   Toute autre colonne reste texte. Deux catégories de colonnes sont exclues
   de cette règle et forcées en texte, parce qu'elles se prêteraient à une
   fausse conversion numérique sans le vouloir : les clés (`cles`) et les
   attributs de catalogue de la liste blanche (`session_courante`), qui sont
   par construction des codes et des libellés, jamais des quantités.

   La règle explique aussi le piège déjà rencontré ailleurs dans ce projet
   (`edumatch.quality.parcoursup`) : `dep` porte `2A` et `2B` pour la Corse.
   Sans le forçage ci-dessus, `dep` se convertirait presque partout en entier
   (2A/2B produiraient les deux seules valeurs manquantes du millésime) — la
   règle « aucune perte » suffirait déjà à la garder en texte, le forçage
   explicite n'est donc pas redondant avec le hasard des données, il rend la
   décision indépendante de ce hasard.

Ce que ce module ne fait pas : il ne calcule pas le label (E19), il ne décide
pas quelles colonnes entrent dans le modèle (déjà fait, ADR 0013) — il rend
disponible, sous un schéma stable et typé, la totalité des colonnes déjà
classées, pour que ces deux étapes n'aient plus à lire un CSV brut.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from edumatch.config import VariablesConfig
from edumatch.ingestion._flux import ecriture_atomique

# Extrait l'identifiant de fiche formation du paramètre `g_ta_cod` de l'URL
# portée par `lien_form_psup` (ADR 0010). Vérifié exact sur les millésimes où
# `cod_aff_form` existe déjà : les deux valeurs coïncident systématiquement.
MOTIF_G_TA_COD = re.compile(r"g_ta_cod=(\d+)")

# Nom de la colonne clé et de la colonne de reconstruction : cités une seule
# fois ici, jamais recopiés en dur ailleurs dans ce module.
COLONNE_CLE = "cod_aff_form"
COLONNE_LIEN = "lien_form_psup"
COLONNE_SESSION = "session"


class ErreurReconciliationParcoursup(RuntimeError):
    """La réconciliation ne peut pas produire une table silver valide.

    Deux causes possibles, toutes deux définitives au sens de
    `edumatch.ingestion._flux.ErreurDefinitive` : aucun fichier bronze
    disponible, ou une violation du grain `(session, cod_aff_form)` — deux
    lignes de la même session portant la même clé non manquante, ce que la
    définition du grain interdit par construction. Aucune des deux ne se
    résout en retentant : il faut soit fournir les fichiers, soit corriger la
    cause de la collision.
    """


@dataclass(frozen=True)
class RapportReconciliation:
    """Ce que la réconciliation a réellement constaté, millésime par millésime.

    Sert à la fois de preuve (E15 exige une couverture « mesurée et
    déclarée », pas supposée) et de journal d'exécution : `run.py` l'affiche
    à la fin de chaque passage.
    """

    lignes_par_session: dict[int, int]
    colonnes_manquantes_par_session: dict[int, tuple[str, ...]]
    taux_cle_reconstruite_par_session: dict[int, float | None]
    nombre_colonnes_harmonisees: int
    lignes_sans_label_disponible: int

    @property
    def lignes_totales(self) -> int:
        return sum(self.lignes_par_session.values())

    def resume(self) -> str:
        """Une restitution lisible en une poignée de lignes, pour le journal."""
        lignes = [
            f"{self.lignes_totales} lignes sur {len(self.lignes_par_session)} session(s), "
            f"{self.nombre_colonnes_harmonisees} colonnes harmonisées.",
        ]
        for session in sorted(self.lignes_par_session):
            detail = [f"{self.lignes_par_session[session]} lignes"]
            manquantes = self.colonnes_manquantes_par_session.get(session, ())
            if manquantes:
                detail.append(f"{len(manquantes)} colonne(s) non encore publiée(s)")
            taux = self.taux_cle_reconstruite_par_session.get(session)
            if taux is not None:
                detail.append(f"clé reconstruite à {taux:.1%}")
            lignes.append(f"  session {session} : " + ", ".join(detail))
        lignes.append(
            f"{self.lignes_sans_label_disponible} ligne(s) sans label calculable "
            "(sessions 2018-2019, ADR 0012) — attendu, pas une anomalie."
        )
        return "\n".join(lignes)


def _charger_millesime(chemin: Path) -> pd.DataFrame:
    """Charge un millésime en texte brut, colonne par colonne, sans inférence de type.

    Même convention que `edumatch.quality.parcoursup._charger` : forcer
    `dtype=str` évite qu'une colonne soit typée différemment d'un millésime à
    l'autre selon les valeurs qu'elle contient cette année-là. Le typage de
    ce module s'applique ensuite, une fois les huit millésimes réunis.
    """
    return pd.read_csv(chemin, delimiter=";", dtype=str, encoding="utf-8-sig")


def _reconstruire_cle(brut: pd.DataFrame) -> tuple[pd.Series, float | None]:
    """Renvoie la colonne clé et, si elle a dû être reconstruite, son taux de couverture.

    `None` en seconde position signifie que `cod_aff_form` existait déjà dans
    le fichier : aucune reconstruction n'a eu lieu, la question de sa
    couverture par reconstruction ne se pose pas pour ce millésime.
    """
    if COLONNE_CLE in brut.columns:
        return brut[COLONNE_CLE], None
    if COLONNE_LIEN not in brut.columns:
        # Ni la clé ni sa source de reconstruction : millésime imprévu, la
        # colonne reste entièrement manquante plutôt que de lever une
        # exception qui interromprait la réconciliation des autres millésimes.
        return pd.Series([pd.NA] * len(brut), index=brut.index, dtype="object"), 0.0
    reconstruite = brut[COLONNE_LIEN].str.extract(MOTIF_G_TA_COD, expand=False)
    taux = float(reconstruite.notna().mean()) if len(brut) else 0.0
    return reconstruite, taux


def _harmoniser_schema(
    brut: pd.DataFrame, cle: pd.Series, colonnes_attendues: list[str]
) -> pd.DataFrame:
    """Construit une trame portant exactement `colonnes_attendues`, dans cet ordre.

    Une colonne absente du fichier source devient une colonne de valeurs
    manquantes plutôt qu'une absence de colonne : c'est ce qui permet
    d'empiler les huit millésimes en un seul bloc, malgré leurs 85 à 118
    colonnes respectives.
    """
    manquante = pd.Series([pd.NA] * len(brut), index=brut.index, dtype="object")
    colonnes = {
        colonne: cle
        if colonne == COLONNE_CLE
        else brut[colonne]
        if colonne in brut.columns
        else manquante
        for colonne in colonnes_attendues
    }
    return pd.DataFrame(colonnes, index=brut.index)


def _typer_colonne(serie: pd.Series) -> pd.Series:
    """Numérique si la conversion ne perd aucune valeur, texte sinon.

    « Ne perd aucune valeur » se vérifie en comparant le nombre de valeurs
    manquantes avant et après `pd.to_numeric(errors="coerce")` : si une seule
    valeur non vide échoue à se convertir, elle deviendrait une valeur
    manquante *fabriquée* par ce module, ce qu'aucune colonne texte de ce
    fichier ne mérite. Entière si, une fois convertie, chaque valeur non
    manquante est un entier exact ; décimale sinon (les colonnes `pct_*`).
    """
    manquantes_avant = int(serie.isna().sum())
    convertie = pd.to_numeric(serie, errors="coerce")
    manquantes_apres = int(convertie.isna().sum())
    if manquantes_apres > manquantes_avant:
        return serie.astype("string")
    non_manquantes = convertie.dropna()
    if not non_manquantes.empty and (non_manquantes == non_manquantes.round()).all():
        return convertie.astype("Int64")
    return convertie.astype("Float64")


def _typer_table(table: pd.DataFrame, colonnes_texte_forcees: set[str]) -> pd.DataFrame:
    """Applique `_typer_colonne` colonne par colonne, sauf pour les colonnes forcées en texte.

    `colonnes_texte_forcees` couvre les clés et les attributs de catalogue de
    la liste blanche (`session_courante`, ADR 0013) : des codes et des
    libellés, jamais des quantités, quand bien même certains ressembleraient
    à des nombres pour un millésime donné (un code de département sans
    Corse, par exemple).
    """
    for colonne in table.columns:
        if colonne == COLONNE_SESSION:
            continue
        if colonne in colonnes_texte_forcees:
            table[colonne] = table[colonne].astype("string")
        else:
            table[colonne] = _typer_colonne(table[colonne])
    return table


def reconcilier_dataframes(
    bruts: Mapping[int, pd.DataFrame], variables: VariablesConfig
) -> tuple[pd.DataFrame, RapportReconciliation]:
    """Réconcilie des millésimes déjà chargés en mémoire, quelle qu'en soit la provenance.

    Utilisée directement par `reconcilier` (chargement CSV via pandas) et par
    le modèle dbt (`../dbt/models/silver/stg_parcoursup.py`, chargement CSV
    via DuckDB) : les deux moteurs livrent un DataFrame par millésime, cette
    fonction ne connaît que ça.
    """
    colonnes_attendues = sorted(variables.colonnes_sources - {COLONNE_SESSION})
    colonnes_texte_forcees = (set(variables.cles) | set(variables.session_courante)) - {
        COLONNE_SESSION
    }

    blocs: list[pd.DataFrame] = []
    lignes_par_session: dict[int, int] = {}
    colonnes_manquantes_par_session: dict[int, tuple[str, ...]] = {}
    taux_cle_par_session: dict[int, float | None] = {}

    for millesime in sorted(bruts):
        brut = bruts[millesime]
        cle, taux_reconstruction = _reconstruire_cle(brut)
        harmonise = _harmoniser_schema(brut, cle, colonnes_attendues)
        session = pd.Series(millesime, index=brut.index, name=COLONNE_SESSION)
        bloc = pd.concat([session, harmonise], axis=1)
        blocs.append(bloc)

        lignes_par_session[millesime] = len(brut)
        colonnes_manquantes_par_session[millesime] = tuple(
            colonne
            for colonne in colonnes_attendues
            if colonne != COLONNE_CLE and colonne not in brut.columns
        )
        taux_cle_par_session[millesime] = taux_reconstruction

    if not blocs:
        raise ErreurReconciliationParcoursup(
            "Aucun millésime à réconcilier : la correspondance session -> DataFrame est vide."
        )

    table = pd.concat(blocs, ignore_index=True)
    table = _typer_table(table, colonnes_texte_forcees)
    table = table.sort_values(
        [COLONNE_SESSION, COLONNE_CLE], na_position="last", kind="stable"
    ).reset_index(drop=True)

    avec_cle = table[table[COLONNE_CLE].notna()]
    doublons = avec_cle.duplicated(subset=[COLONNE_SESSION, COLONNE_CLE])
    if doublons.any():
        exemples = avec_cle.loc[doublons, [COLONNE_SESSION, COLONNE_CLE]].head(5)
        raise ErreurReconciliationParcoursup(
            f"{int(doublons.sum())} violation(s) du grain (session, cod_aff_form) : "
            f"clé dupliquée au sein d'une même session, par exemple :\n{exemples}"
        )

    rapport = RapportReconciliation(
        lignes_par_session=lignes_par_session,
        colonnes_manquantes_par_session=colonnes_manquantes_par_session,
        taux_cle_reconstruite_par_session=taux_cle_par_session,
        nombre_colonnes_harmonisees=len(colonnes_attendues) + 1,  # + session
        lignes_sans_label_disponible=int((table[COLONNE_SESSION] < 2020).sum()),
    )
    return table, rapport


def reconcilier(
    chemins: Mapping[int, Path], variables: VariablesConfig
) -> tuple[pd.DataFrame, RapportReconciliation]:
    """Charge chaque millésime depuis son CSV puis délègue à `reconcilier_dataframes`."""
    if not chemins:
        raise ErreurReconciliationParcoursup(
            "Aucun fichier bronze fourni : la correspondance session -> chemin est vide."
        )
    bruts = {millesime: _charger_millesime(chemin) for millesime, chemin in chemins.items()}
    return reconcilier_dataframes(bruts, variables)


def ecrire_silver(table: pd.DataFrame, destination: Path) -> None:
    """Écrit la table silver en Parquet, par fichier temporaire renommé (idempotence).

    Réutilise `edumatch.ingestion._flux.ecriture_atomique`, déjà responsable
    de cette garantie pour les connecteurs : un lecteur concurrent ne voit
    jamais un fichier à moitié écrit, et une interruption au milieu de
    l'écriture ne laisse aucun fichier tronqué sous le nom final. Le format
    Parquet est retenu pour silver comme pour bronze Sirene (E06) : colonnaire,
    typé, compressé — silver est déjà destiné à être relu par colonnes,
    jamais réécrit ligne à ligne.
    """
    bloc_arrow = pa.Table.from_pandas(table, preserve_index=False)
    with ecriture_atomique(destination, mode="wb") as flux:
        pq.write_table(bloc_arrow, flux, compression="snappy")
