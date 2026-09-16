"""Construction de la table de variables d'entraînement (E20) : `make features`.

## Ce que ce module fait, et rien de plus

`transform/etoile.py` (E16) a produit le grain de l'apprentissage — une ligne
`fait_admission` par cellule `(session, formation, type de baccalauréat,
boursier)`, avec son label (`taux`, `features/label.py`, E19). Ce module lui
attache les variables explicatives, en respectant **exactement** le
classement colonne par colonne arrêté par l'ADR 0013 et porté par
`configs/base.yaml`, section `modele.variables` (`VariablesConfig`). Il ne
réinterprète jamais ce classement : il le lit, et refuse de continuer si une
colonne qu'il s'apprête à produire n'y figure pas (`_verifier_colonnes_licites`).

Trois familles de colonnes, jamais mélangées :

- les deux **dimensions de la cellule** (`type_bac`, `boursier`), qui ne
  viennent d'aucun fichier : elles sont résolues depuis `dim_profil_candidat`
  via `sk_profil` ;
- les neuf colonnes de **`session_courante`** (ADR 0013 §1), lues sur la
  session que le modèle prédit — jointure `(session, cod_aff_form)` avec la
  table silver, sans décalage ;
- les colonnes **`decalees`** (35, ADR 0013 §2), lues sur la session
  **précédente** : la table silver est jointe une seconde fois, après avoir
  translaté sa colonne `session` de `+1`, pour que la ligne silver du
  millésime N-1 se retrouve alignée sur la ligne de sortie de la session N.
  C'est ce mécanisme, et lui seul, qui protège de la fuite temporelle
  (ADR 0010) : une jointure qui oublierait la translation ramènerait la
  valeur de la session N, invisible dans les métriques et démasquée
  seulement en production. `tests/data/test_features_build_antifuite.py`
  le vérifie sur une donnée où la valeur diffère entre N-1 et N — sinon le
  test passerait même si la translation était absente.

Les huit colonnes de mention (`decalees_sous_reserve`) restent, par défaut,
hors de la table produite : l'ADR 0013 les écarte tant que l'ablation (E27)
n'a pas démontré un gain. `inclure_sous_reserve=True` les réintroduit sans
dupliquer le classement — c'est le seul paramètre que ce module expose au delà
de la configuration.

## L'absence d'antécédent : mesurée, jamais comblée

Deux cas produisent une cellule sans ligne silver correspondante à la
session N-1, et dans les deux cas la valeur reste manquante (`<NA>`), jamais
imputée : combler fabriquerait un antécédent qui n'existe pas.

1. La session cible 2020 : son millésime N-1 est 2019, où `prop_tot_*`
   n'existe pas encore (ADR 0012, ADR 0013 §6). Toutes les cellules de la
   session 2020 sont donc dépourvues d'antécédent pour les variables issues
   de `prop_tot*`, `acc_*`, etc.
2. Une formation apparue pour la première fois à la session N n'a, par
   définition, aucune ligne silver en N-1.

`RapportVariables.cellules_sans_antecedent` compte les cellules dans ce cas
(join de recherche N-1 sans correspondance) ; `taux_manquant_par_variable`
détaille, colonne par colonne, la part de valeurs manquantes réellement
observée — LightGBM (ADR 0009, ADR 0013) traite nativement l'absence, ce
module ne fait rien pour la masquer.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from edumatch.config import Settings, VariablesConfig, get_settings
from edumatch.ingestion._flux import ecriture_atomique
from edumatch.transform.reconciliation import COLONNE_CLE, COLONNE_SESSION

LOGGER = logging.getLogger(__name__)

CLE_JOINTURE: tuple[str, str] = (COLONNE_SESSION, COLONNE_CLE)

SOUS_DOSSIER = "parcoursup"
NOM_FICHIER_SILVER = "silver.parquet"
NOM_FICHIER_VARIABLES = "variables.parquet"

# Colonnes de `fait_admission` conservées telles quelles : le label et ses
# clés de substitution, pour la traçabilité et pour que ce module reste la
# seule étape qui joint variables et label. `sk_territoire` n'est pas repris
# ici : `dep` (via `session_courante`) porte déjà la maille territoriale
# utile aux variables, `sk_territoire` ne sert qu'au lignage du gold.
COLONNES_FAIT_CONSERVEES: tuple[str, ...] = ("sk_formation", "sk_profil", "effectif", "taux", "taux_depasse_1")


class ErreurConstructionVariables(RuntimeError):
    """La table de variables ne peut pas être construite sans violer une garantie attendue.

    Définitive : une jointure ambiguë (fan-out), une colonne hors classement,
    ou une clé non résolue ne se règlent pas en relançant à l'identique — il
    faut corriger le gold, silver, ou `modele.variables`.
    """


class ErreurVariablesSourceAbsente(RuntimeError):
    """Silver ou le gold ne sont pas encore disponibles : E15/E16 doivent tourner d'abord."""


@dataclass(frozen=True)
class RapportVariables:
    """Volumétrie et complétude réellement obtenues, à déclarer telles quelles (E20)."""

    lignes: int
    nombre_variables: int
    cellules_par_session: dict[int, int]
    cellules_sans_antecedent: int
    taux_manquant_par_variable: dict[str, float]

    def resume(self) -> str:
        lignes = [
            (
                f"{self.lignes} cellules, {self.nombre_variables} variables, "
                f"{self.cellules_sans_antecedent} cellule(s) sans antécédent décalé (session N-1)."
            ),
        ]
        for session in sorted(self.cellules_par_session):
            lignes.append(f"  session {session} : {self.cellules_par_session[session]} cellules")
        pires = sorted(self.taux_manquant_par_variable.items(), key=lambda item: item[1], reverse=True)
        if pires and pires[0][1] > 0:
            lignes.append("  valeurs manquantes les plus fréquentes :")
            for colonne, taux in pires[:5]:
                if taux <= 0:
                    break
                lignes.append(f"    {colonne} : {taux:.1%}")
        return "\n".join(lignes)


def _joindre_sans_fan_out(gauche: pd.DataFrame, droite: pd.DataFrame, cles: list[str], nom: str) -> pd.DataFrame:
    """`gauche.merge(droite, on=cles, how="left")`, mais lève si `droite` fait gonfler le nombre de lignes.

    Même garde-fou que `transform.etoile._joindre_sans_fan_out` (E16), réécrit
    ici plutôt qu'importé : c'est une fonction privée de ce module-là, et la
    dupliquer coûte moins cher que de rendre publique une API interne d'un
    autre module pour un usage aussi ponctuel. Une jointure qui change le
    nombre de lignes ne peut venir que d'une source portant, pour une même
    clé, plusieurs lignes candidates — chaque ligne de `gauche` se verrait
    alors résoudre plusieurs valeurs possibles, silencieusement, si ce
    contrôle n'existait pas.
    """
    resultat = gauche.merge(droite, on=cles, how="left")
    if len(resultat) != len(gauche):
        raise ErreurConstructionVariables(
            f"Résolution de {nom} ambiguë : {len(resultat)} lignes obtenues pour "
            f"{len(gauche)} lignes avant jointure. La source porte au moins deux "
            f"lignes pour une même clé {cles}."
        )
    return resultat


def _verifier_colonnes_licites(colonnes: list[str], variables: VariablesConfig) -> None:
    """Refuse toute colonne qui ne relèverait ni des dimensions, ni de la liste blanche, ni des décalées.

    Défense en profondeur : la construction ne lit déjà que les colonnes
    listées par `VariablesConfig`, donc ce contrôle ne devrait jamais se
    déclencher en usage normal. Il existe pour la même raison que les
    contrôles qualité du plan d'exécution du projet — un échec doit bloquer,
    pas être supposé impossible.
    """
    licites = (
        set(variables.dimensions_cellule)
        | set(variables.session_courante)
        | set(variables.decalees)
        | set(variables.decalees_sous_reserve)
    )
    illicites = sorted(set(colonnes) - licites)
    if illicites:
        raise ErreurConstructionVariables(
            f"Colonne(s) {illicites} ne relève(nt) ni de la liste blanche, ni des "
            "variables décalées, ni des dimensions de cellule (ADR 0013) : "
            "construction refusée."
        )


def _ajouter_cle_formation(fait: pd.DataFrame, dim_formation: pd.DataFrame) -> pd.DataFrame:
    """Résout `cod_aff_form` depuis `sk_formation` : la clé silver dont dépend tout le reste."""
    lookup = dim_formation[["sk_formation", COLONNE_CLE]]
    if lookup["sk_formation"].duplicated().any():
        raise ErreurConstructionVariables(
            "dim_formation porte des sk_formation dupliqués : impossible de "
            "résoudre cod_aff_form sans ambiguïté."
        )
    resultat = _joindre_sans_fan_out(fait, lookup, ["sk_formation"], "dim_formation (cod_aff_form)")
    if resultat[COLONNE_CLE].isna().any():
        raise ErreurConstructionVariables(
            f"{int(resultat[COLONNE_CLE].isna().sum())} cellule(s) référencent un "
            "sk_formation absent de dim_formation : intégrité référentielle rompue "
            "entre le gold et cette étape."
        )
    return resultat


def _ajouter_dimensions_cellule(
    fait_avec_cle: pd.DataFrame, dim_profil: pd.DataFrame, variables: VariablesConfig
) -> pd.DataFrame:
    """Résout `type_bac` et `boursier` depuis `sk_profil` : elles ne viennent d'aucune colonne source (ADR 0013)."""
    colonnes = list(variables.dimensions_cellule)
    lookup = dim_profil[["sk_profil", *colonnes]]
    if lookup["sk_profil"].duplicated().any():
        raise ErreurConstructionVariables(
            "dim_profil_candidat porte des sk_profil dupliqués : impossible de "
            "résoudre les dimensions de cellule sans ambiguïté."
        )
    return _joindre_sans_fan_out(fait_avec_cle, lookup, ["sk_profil"], "dim_profil_candidat (dimensions de cellule)")


def _ajouter_colonnes_session_courante(base: pd.DataFrame, silver: pd.DataFrame, colonnes: list[str]) -> pd.DataFrame:
    """Jointure `(session, cod_aff_form)` **sans décalage** : la liste blanche, lue sur la session prédite."""
    if not colonnes:
        return base
    lookup = silver[[*CLE_JOINTURE, *colonnes]].drop_duplicates(subset=list(CLE_JOINTURE))
    return _joindre_sans_fan_out(base, lookup, list(CLE_JOINTURE), "silver (session courante)")


def _ajouter_colonnes_decalees(
    base: pd.DataFrame, silver: pd.DataFrame, colonnes: list[str]
) -> tuple[pd.DataFrame, pd.Series]:
    """Jointure `(session, cod_aff_form)` **avec la table silver translatée de +1 session**.

    C'est le cœur du mécanisme anti-fuite : une ligne silver du millésime
    N-1 porte `session = N-1` ; on la recherche pour une cellule de sortie où
    `session = N` en ajoutant 1 à sa colonne `session` avant la jointure,
    plutôt qu'en soustrayant 1 côté cellule — les deux sont équivalents,
    celui-ci laisse `base` intacte pour les jointures suivantes.

    Retourne la table enrichie et un indicateur booléen (une ligne silver
    N-1 a-t-elle été trouvée), qui sert à compter les cellules sans
    antécédent sans confondre « aucune ligne trouvée » et « ligne trouvée,
    valeur manquante dans la colonne elle-même ».
    """
    if not colonnes:
        base = base.copy()
        return base, pd.Series(True, index=base.index)
    decale = silver[[*CLE_JOINTURE, *colonnes]].copy()
    decale[COLONNE_SESSION] = decale[COLONNE_SESSION] + 1
    decale = decale.drop_duplicates(subset=list(CLE_JOINTURE))
    marqueur = "_antecedent_disponible"
    decale[marqueur] = True
    resultat = _joindre_sans_fan_out(base, decale, list(CLE_JOINTURE), "silver translatée (session N-1)")
    a_antecedent = resultat[marqueur].fillna(False).astype(bool)
    resultat = resultat.drop(columns=marqueur)
    return resultat, a_antecedent


def _colonnes_a_construire(variables: VariablesConfig, inclure_sous_reserve: bool) -> tuple[list[str], list[str]]:
    """Calcule `(colonnes_decalees, colonnes_variables)` et refuse tout conflit de nommage.

    Deux contrôles avant la moindre jointure : chaque colonne demandée relève
    d'une catégorie licite de `modele.variables` (`_verifier_colonnes_licites`),
    et aucune ne porte le même nom qu'une colonne déjà conservée de
    `fait_admission` — `nb_voe_pp` et `prop_tot`, le numérateur et le
    dénominateur bruts du label sur la session prédite, portent par malchance
    de nommage les mêmes noms que deux colonnes `decalees` (ADR 0013 §2, la
    même colonne source, lue à un autre moment). Sans ce contrôle, la
    jointure décalée renommerait silencieusement les deux (`_x` / `_y`) au
    lieu d'échouer franchement sur l'ambiguïté.
    """
    colonnes_decalees = list(variables.decalees)
    if inclure_sous_reserve:
        colonnes_decalees = colonnes_decalees + list(variables.decalees_sous_reserve)

    colonnes_variables = [*variables.dimensions_cellule, *variables.session_courante, *colonnes_decalees]
    _verifier_colonnes_licites(colonnes_variables, variables)

    conflits = set(colonnes_variables) & (set(COLONNES_FAIT_CONSERVEES) | {COLONNE_SESSION, COLONNE_CLE})
    if conflits:
        raise ErreurConstructionVariables(
            f"Colonne(s) {sorted(conflits)} homonyme(s) entre `modele.variables` et les "
            "colonnes conservées de fait_admission : la jointure les renommerait "
            "silencieusement (`_x`/`_y`) au lieu d'échouer franchement."
        )
    return colonnes_decalees, colonnes_variables


def _rapport_variables(
    table: pd.DataFrame, colonnes_variables: list[str], a_antecedent: pd.Series
) -> RapportVariables:
    """Volumétrie et complétude mesurées sur la table produite, à déclarer telles quelles (E20)."""
    cellules_par_session = {
        int(session): int(compte) for session, compte in table[COLONNE_SESSION].value_counts().sort_index().items()
    }
    taux_manquant_par_variable = {colonne: float(table[colonne].isna().mean()) for colonne in colonnes_variables}
    return RapportVariables(
        lignes=len(table),
        nombre_variables=len(colonnes_variables),
        cellules_par_session=cellules_par_session,
        cellules_sans_antecedent=int((~a_antecedent).sum()),
        taux_manquant_par_variable=taux_manquant_par_variable,
    )


def construire_table_apprentissage(
    fait_admission: pd.DataFrame,
    dim_formation: pd.DataFrame,
    dim_profil: pd.DataFrame,
    silver: pd.DataFrame,
    variables: VariablesConfig,
    inclure_sous_reserve: bool = False,
) -> tuple[pd.DataFrame, RapportVariables]:
    """Assemble la table de variables : dimensions de cellule + liste blanche + décalées + label.

    Une ligne en entrée (`fait_admission`) produit exactement une ligne en
    sortie : aucune des jointures n'est autorisée à en fabriquer davantage
    (`_joindre_sans_fan_out`), et chaque colonne produite doit relever d'une
    catégorie licite de `modele.variables` (`_verifier_colonnes_licites`).
    """
    colonnes_decalees, colonnes_variables = _colonnes_a_construire(variables, inclure_sous_reserve)
    nombre_avant = len(fait_admission)

    fait_admission = fait_admission[[COLONNE_SESSION, *COLONNES_FAIT_CONSERVEES]]
    base = _ajouter_cle_formation(fait_admission, dim_formation)
    base = _ajouter_dimensions_cellule(base, dim_profil, variables)
    base = _ajouter_colonnes_session_courante(base, silver, list(variables.session_courante))
    base, a_antecedent = _ajouter_colonnes_decalees(base, silver, colonnes_decalees)

    if len(base) != nombre_avant:
        raise ErreurConstructionVariables(
            f"{len(base)} lignes obtenues pour {nombre_avant} cellules en entrée : "
            "une jointure a modifié le nombre de lignes malgré les garde-fous."
        )

    colonnes_sortie = [COLONNE_SESSION, COLONNE_CLE, *COLONNES_FAIT_CONSERVEES, *colonnes_variables]
    table = base[colonnes_sortie].sort_values([COLONNE_SESSION, COLONNE_CLE], kind="stable").reset_index(drop=True)

    return table, _rapport_variables(table, colonnes_variables, a_antecedent)


def _chemin_silver(settings: Settings) -> Path:
    return settings.interim_dir / SOUS_DOSSIER / NOM_FICHIER_SILVER


def _dossier_gold(settings: Settings) -> Path:
    return settings.processed_dir / SOUS_DOSSIER


def executer(settings: Settings | None = None) -> RapportVariables:
    """Construit et écrit la table de variables. Retourne le rapport de volumétrie et de complétude."""
    settings = settings or get_settings()
    chemin_silver = _chemin_silver(settings)
    dossier_gold = _dossier_gold(settings)
    chemins_requis = {
        "silver": chemin_silver,
        "fait_admission": dossier_gold / "fait_admission.parquet",
        "dim_formation": dossier_gold / "dim_formation.parquet",
        "dim_profil_candidat": dossier_gold / "dim_profil_candidat.parquet",
    }
    manquants = {nom: chemin for nom, chemin in chemins_requis.items() if not chemin.exists()}
    if manquants:
        raise ErreurVariablesSourceAbsente(
            "Fichier(s) manquant(s) : "
            + ", ".join(f"{nom} ({chemin})" for nom, chemin in manquants.items())
            + ". Exécuter `make transform` (E15) puis `make gold` (E16) avant `make features`."
        )

    silver = pq.read_table(chemins_requis["silver"]).to_pandas()
    fait_admission = pq.read_table(chemins_requis["fait_admission"]).to_pandas()
    dim_formation = pq.read_table(chemins_requis["dim_formation"]).to_pandas()
    dim_profil = pq.read_table(chemins_requis["dim_profil_candidat"]).to_pandas()

    table, rapport = construire_table_apprentissage(
        fait_admission, dim_formation, dim_profil, silver, settings.modele.variables
    )

    destination = dossier_gold / NOM_FICHIER_VARIABLES
    bloc_arrow = pa.Table.from_pandas(table, preserve_index=False)
    with ecriture_atomique(destination, mode="wb") as flux:
        pq.write_table(bloc_arrow, flux, compression="snappy")
    return rapport


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rapport = executer()
    LOGGER.info("Construction des variables (E20) terminée.\n%s", rapport.resume())
    return 0


if __name__ == "__main__":
    sys.exit(main())
