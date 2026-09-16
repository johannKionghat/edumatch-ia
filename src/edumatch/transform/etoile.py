"""Modèle en étoile de la couche gold Parcoursup (E16) : silver -> faits et dimensions.

## Le grain — la décision qui commande tout le reste

Silver (`stg_parcoursup`, E15) a une ligne par **formation-session**
(`session`, `cod_aff_form`). Ce n'est pas le grain de l'analyse : le label
(ADR 0009) vit à la maille de la **cellule**, c'est-à-dire une formation
croisée avec un type de baccalauréat et un statut de boursier. Une
formation-session silver se **déplie** donc en jusqu'à six cellules — les
catégories `bg`, `bg_brs`, `bt`, `bt_brs`, `bp`, `bp_brs` que porte déjà le
fichier source (`nb_voe_pp_bg`, `prop_tot_bg`, etc.).

**Le grain de la table de faits `fait_admission` est donc :**

    (session, cod_aff_form, type_bac, boursier)

une ligne = une cellule dont le label est calculable. Une cellule est
« exploitable » exactement au sens déjà mesuré (`04-modele/...`, ADR 0009,
0012) : son dénominateur (`nb_voe_pp_{categorie}`) est renseigné et non nul,
et son numérateur (`prop_tot_{categorie}`) est renseigné. Cette condition
n'est écrite nulle part avec un millésime en dur (« 2020 ») : les sessions
2018 et 2019 en sortent naturellement, puisque `prop_tot_*` n'y existe pas
(ADR 0012) — le filtre est sur la donnée, pas sur une date arbitraire.

Volumétrie de référence, mesurée sur les données réelles avant d'écrire ce
module (voir le rapport retourné par `construire_etoile`, comparé aux
chiffres déjà connus) : **440 030 cellules exploitables sur les sessions
2020 à 2025** (67 768 / 71 080 / 72 784 / 74 831 / 76 408 / 77 159).

## Dépliage de 2018 et 2019 : décision et justification

2018 et 2019 n'ont **aucune cellule exploitable** (label non calculable,
ADR 0012) : elles ne produisent donc aucune ligne de `fait_admission`, par
construction du filtre ci-dessus, sans qu'il ait fallu les exclure
explicitement par millésime. Elles ne sont pour autant pas absentes de la
couche gold : `dim_session` les porte, avec un indicateur explicite
(`label_disponible = False`), pour que le lignage documente pourquoi la
table de faits ne les cite jamais — plutôt que de laisser un lecteur du
schéma se demander où sont passées deux des huit sessions ingérées.

## Les dimensions retenues, et une écartée

- **`dim_session`** — le millésime. Grain : une ligne par session vue dans
  silver (huit lignes, 2018 à 2025).
- **`dim_formation`** — la formation, en **SCD 2** : `capa_fin`, `fili`,
  les libellés de filière, `select_form`, `contrat_etab`, `tri` et
  `cod_uai` peuvent changer d'une session à l'autre pour la même formation
  (`cod_aff_form` stable, vérifié **dans silver** : 10 826 formations
  présentes dans les 6 sessions 2020-2025, sur 16 960 vues au moins une
  fois). Attention au périmètre : ces deux chiffres comptent le catalogue
  silver. `dim_formation`, elle, ne retient que les formations ayant au
  moins une cellule exploitable, soit **16 618** formations distinctes et
  43 858 versions — 342 formations du catalogue 2020-2025 n'ont aucune
  cellule dont le label soit calculable. Une nouvelle version est créée
  seulement quand au moins un de ces attributs change ; sinon les sessions
  consécutives sont regroupées dans la même version (`session_debut`,
  `session_fin`). **`cod_uai` et le futur `ville_etab` de `dim_territoire`
  sont des attributs de dimension, jamais des variables du modèle** (ADR
  0011, ADR 0013) : ils servent à l'analyse et à la supervision, pas à
  l'entraînement — la distinction est structurelle, pas seulement une
  case cochée quelque part.
- **`dim_territoire`** — `dep`, `ville_etab`, avec `dep_lib`, `acad_mies`,
  `region_etab_aff` en attributs descriptifs. Séparée de `dim_formation`
  pour accepter la redondance de l'étoile (plusieurs formations partagent
  un territoire) plutôt que de la faire flocon : le grain est celui du
  territoire, pas de la formation.
- **`dim_profil_candidat`** — six lignes fixes, une par combinaison
  `(type_bac, boursier)`. Ce n'est pas une colonne du fichier source : elle
  est portée par la structure même du label (ADR 0009), au même titre que
  dans silver (`schema.yml` de `stg_parcoursup`).

**Écartée** : une dimension « établissement » distincte de `dim_formation`
a été envisagée puis abandonnée. `cod_uai` identifie l'établissement
gérant, mais aucune formation de ce fichier ne change d'établissement
gérant d'une session sur l'autre dans les données observées, et le
retour Jedha (§5 de mes notes de cadrage) sanctionne explicitement la
surarchitecture : une dimension sans second grain qui la justifie n'est
qu'une colonne de plus dans `dim_formation`.

## Le label : la formule vit dans `features/label.py` (E19), pas ici

`fait_admission` porte `nb_voe_pp` (effectif, sert aussi de pondération),
`prop_tot` (brut) et `taux` — `prop_tot / nb_voe_pp`, **borné à 1**, formule
arrêtée par l'ADR 0009. Ce module ne la recalcule plus lui-même : il appelle
`edumatch.features.label.calculer_taux`, qui en porte l'unique définition
depuis E19. Avant E19, elle était codée ici même, le gold en avait besoin
avant que l'étape dédiée n'existe ; la garder dupliquée à deux endroits
aurait fait courir le risque qu'elle y diverge un jour sans que personne ne
le remarque. `taux_depasse_1` conserve, en clair, les cellules où le brut
dépassait 1 avant bornage (8,9 % sur le bac général en 2025, ADR 0009).

Ce module ne porte plus, et `features/label.py` (E19) porte désormais : la
pondération à l'entraînement (poids = effectif de la cellule, ADR 0009), et
toute décision non encore arrêtée (seuil d'exclusion de petites cellules —
actuellement aucun, ADR 0009).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from edumatch.features.label import calculer_taux
from edumatch.ingestion._flux import ecriture_atomique
from edumatch.transform.reconciliation import COLONNE_CLE, COLONNE_SESSION

# Les six catégories déjà présentes dans le fichier Parcoursup, une par
# combinaison (type de baccalauréat, statut de boursier). Ce n'est pas une
# liste arbitraire : ce sont les six suffixes `nb_voe_pp_*` / `prop_tot_*`
# du fichier source, ADR 0009.
CATEGORIES: tuple[str, ...] = ("bg", "bg_brs", "bt", "bt_brs", "bp", "bp_brs")

# Attributs de `dim_formation` suivis en SCD 2 : une nouvelle version naît
# quand l'un d'eux change pour une même formation (`cod_aff_form`).
COLONNES_FORMATION_SCD2: tuple[str, ...] = (
    "fili",
    "form_lib_voe_acc",
    "fil_lib_voe_acc",
    "select_form",
    "contrat_etab",
    "tri",
    "capa_fin",
    "cod_uai",
)

# Attributs descriptifs de `dim_territoire`, purement informatifs (aucune
# évolution suivie : académie et région d'un département ne varient pas
# dans les données observées).
COLONNES_TERRITOIRE_DESCRIPTIVES: tuple[str, ...] = ("dep_lib", "acad_mies", "region_etab_aff")
COLONNES_TERRITOIRE_NATURELLES: tuple[str, ...] = ("dep", "ville_etab")

LIBELLES_TYPE_BAC: dict[str, str] = {
    "bg": "Général",
    "bt": "Technologique",
    "bp": "Professionnel",
}


def _categorie_vers_profil(categorie: str) -> tuple[str, bool]:
    """`"bg_brs"` -> ("bg", True) ; `"bt"` -> ("bt", False)."""
    boursier = categorie.endswith("_brs")
    type_bac = categorie[: -len("_brs")] if boursier else categorie
    return type_bac, boursier


class ErreurEtoile(RuntimeError):
    """La construction du modèle en étoile ne peut pas produire un gold valide.

    Définitive au sens de `edumatch.ingestion._flux.ErreurDefinitive` : une
    violation de grain sur `fait_admission` ou une référence orpheline entre
    faits et dimensions ne se résout jamais en relançant à l'identique — il
    faut corriger silver ou ce module.
    """


@dataclass(frozen=True)
class RapportEtoile:
    """Les volumétries réellement obtenues, à confronter aux chiffres déjà mesurés (§2 de mes notes)."""

    lignes_fait_par_session: dict[int, int]
    nombre_formations: int
    nombre_versions_formation: int
    nombre_territoires: int
    sessions_sans_label: tuple[int, ...]

    @property
    def lignes_fait_totales(self) -> int:
        return sum(self.lignes_fait_par_session.values())

    def resume(self) -> str:
        lignes = [
            (
                f"{self.lignes_fait_totales} cellules exploitables (fait_admission), "
                f"{self.nombre_formations} formations ({self.nombre_versions_formation} versions SCD2), "
                f"{self.nombre_territoires} territoires."
            ),
        ]
        for session in sorted(self.lignes_fait_par_session):
            lignes.append(f"  session {session} : {self.lignes_fait_par_session[session]} cellules")
        if self.sessions_sans_label:
            lignes.append(
                f"  sans label (attendu, ADR 0012) : {', '.join(map(str, self.sessions_sans_label))}"
            )
        return "\n".join(lignes)


def base_exploitable(silver: pd.DataFrame) -> pd.DataFrame:
    """Les lignes silver avec clé, portant au moins une cellule exploitable.

    C'est le périmètre qui alimente à la fois `fait_admission` et les
    dimensions : construire les dimensions sur ce même sous-ensemble garantit
    qu'aucune ligne de dimension n'est orpheline (jamais référencée par un
    fait) — la propriété vérifiée par
    `tests/data/test_transform_etoile.py::test_aucune_dimension_orpheline`.
    """
    avec_cle = silver[silver[COLONNE_CLE].notna()]
    masque = pd.Series(False, index=avec_cle.index)
    for categorie in CATEGORIES:
        denominateur = avec_cle[f"nb_voe_pp_{categorie}"]
        numerateur = avec_cle[f"prop_tot_{categorie}"]
        masque = masque | (denominateur.notna() & (denominateur > 0) & numerateur.notna())
    return avec_cle[masque].reset_index(drop=True)


def construire_dim_session(silver: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par session vue dans silver, y compris 2018-2019 (sans label)."""
    sessions_avec_label = set(base[COLONNE_SESSION].unique())
    sessions = sorted(silver[COLONNE_SESSION].dropna().unique())
    return pd.DataFrame(
        {
            "session": sessions,
            "label_disponible": [s in sessions_avec_label for s in sessions],
        }
    )


def _signature(ligne: pd.Series, colonnes: tuple[str, ...]) -> tuple:
    """Une clé de comparaison stable, où deux valeurs manquantes sont égales entre elles.

    `pd.NA == pd.NA` ne renvoie pas `True` : comparer directement des tuples
    de valeurs brutes échouerait à détecter deux versions identiques dès
    qu'un attribut suivi est manquant. `str()` normalise sans ambiguïté
    (`"<NA>"` pour toute valeur manquante, quel que soit son type).
    """
    return tuple(str(ligne[colonne]) for colonne in colonnes)


def construire_dim_formation(base: pd.DataFrame) -> pd.DataFrame:
    """SCD 2 sur `cod_aff_form` : une nouvelle version quand un attribut suivi change.

    Les sessions non représentées dans `base` pour une formation donnée (par
    exemple une session où elle n'a aucune cellule exploitable) ne sont pas
    interpolées : `session_fin` documente la dernière session **observée**
    avec cet état, pas une garantie de continuité sur les sessions absentes.
    """
    colonnes = [COLONNE_SESSION, COLONNE_CLE, *COLONNES_FORMATION_SCD2]
    par_ligne = (
        base[colonnes]
        .drop_duplicates(subset=[COLONNE_SESSION, COLONNE_CLE])
        .sort_values([COLONNE_CLE, COLONNE_SESSION], kind="stable")
    )

    versions: list[dict] = []
    for cod_aff_form, groupe in par_ligne.groupby(COLONNE_CLE, sort=True):
        groupe = groupe.sort_values(COLONNE_SESSION, kind="stable")
        debut = None
        fin = None
        signature_courante = None
        valeurs_courantes = None
        for _, ligne in groupe.iterrows():
            signature = _signature(ligne, COLONNES_FORMATION_SCD2)
            if signature_courante is None:
                debut = fin = ligne[COLONNE_SESSION]
                signature_courante = signature
                valeurs_courantes = ligne
            elif signature == signature_courante:
                fin = ligne[COLONNE_SESSION]
            else:
                versions.append(
                    {
                        "cod_aff_form": cod_aff_form,
                        "session_debut": debut,
                        "session_fin": fin,
                        **{c: valeurs_courantes[c] for c in COLONNES_FORMATION_SCD2},
                    }
                )
                debut = fin = ligne[COLONNE_SESSION]
                signature_courante = signature
                valeurs_courantes = ligne
        versions.append(
            {
                "cod_aff_form": cod_aff_form,
                "session_debut": debut,
                "session_fin": fin,
                **{c: valeurs_courantes[c] for c in COLONNES_FORMATION_SCD2},
            }
        )

    dim = pd.DataFrame(versions).sort_values(
        ["cod_aff_form", "session_debut"], kind="stable"
    ).reset_index(drop=True)
    dim.insert(0, "sk_formation", dim.index + 1)
    return dim


def _deplier_versions_par_session(dim_formation: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par (session, cod_aff_form) -> sk_formation, pour joindre le fait à sa version SCD2."""
    lignes = [
        {"session": session, "cod_aff_form": version["cod_aff_form"], "sk_formation": version["sk_formation"]}
        for _, version in dim_formation.iterrows()
        for session in range(int(version["session_debut"]), int(version["session_fin"]) + 1)
    ]
    return pd.DataFrame(lignes)


def construire_dim_territoire(base: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par couple (`dep`, `ville_etab`) distinct — attributs descriptifs, SCD 1 (pas d'historique utile)."""
    colonnes = [*COLONNES_TERRITOIRE_NATURELLES, *COLONNES_TERRITOIRE_DESCRIPTIVES]
    dim = (
        base[colonnes]
        .sort_values(colonnes, na_position="first", kind="stable")
        .drop_duplicates(subset=list(COLONNES_TERRITOIRE_NATURELLES), keep="first")
        .reset_index(drop=True)
    )
    dim.insert(0, "sk_territoire", dim.index + 1)
    return dim


def construire_dim_profil_candidat() -> pd.DataFrame:
    """Six lignes fixes : le produit cartésien (type de bac x boursier), pas une colonne source."""
    lignes = [
        {
            "sk_profil": indice + 1,
            "type_bac": type_bac,
            "boursier": boursier,
            "libelle_type_bac": LIBELLES_TYPE_BAC[type_bac],
        }
        for indice, (type_bac, boursier) in enumerate(
            _categorie_vers_profil(categorie) for categorie in CATEGORIES
        )
    ]
    return pd.DataFrame(lignes)


def construire_fait_admission(
    base: pd.DataFrame,
    dim_formation: pd.DataFrame,
    dim_territoire: pd.DataFrame,
    dim_profil: pd.DataFrame,
) -> pd.DataFrame:
    """Déplie chaque formation-session exploitable en une ligne par cellule (session, formation, profil).

    Grain vérifié par construction : `base` respecte déjà (session,
    cod_aff_form) unique (garanti par silver), et chaque catégorie ne peut
    produire qu'une ligne par ligne de `base`, donc le triplet (session,
    sk_formation, sk_profil) ne peut pas se dupliquer — revérifié
    explicitement plus bas, pas seulement supposé.
    """
    blocs: list[pd.DataFrame] = []
    for categorie in CATEGORIES:
        denominateur = base[f"nb_voe_pp_{categorie}"]
        numerateur = base[f"prop_tot_{categorie}"]
        masque = denominateur.notna() & (denominateur > 0) & numerateur.notna()
        type_bac, boursier = _categorie_vers_profil(categorie)
        bloc = pd.DataFrame(
            {
                COLONNE_SESSION: base.loc[masque, COLONNE_SESSION].to_numpy(),
                COLONNE_CLE: base.loc[masque, COLONNE_CLE].to_numpy(),
                "dep": base.loc[masque, "dep"].to_numpy(),
                "ville_etab": base.loc[masque, "ville_etab"].to_numpy(),
                "type_bac": type_bac,
                "boursier": boursier,
                "nb_voe_pp": denominateur[masque].astype("Int64").to_numpy(),
                "prop_tot": numerateur[masque].astype("Int64").to_numpy(),
            }
        )
        blocs.append(bloc)

    fait = pd.concat(blocs, ignore_index=True)
    nombre_cellules_avant_jointure = len(fait)

    def _joindre_sans_fan_out(
        fait: pd.DataFrame, dimension: pd.DataFrame, cles: list[str], nom_dimension: str
    ) -> pd.DataFrame:
        """`fait.merge(..., how="left")`, mais lève si la dimension fait gonfler le nombre de lignes.

        Une jointure qui change le nombre de lignes ne peut venir que d'une
        dimension portant, pour une même clé naturelle, plusieurs lignes
        candidates (deux versions SCD 2 de `dim_formation` dont les plages de
        validité se recouvrent, ou une clé dupliquée dans `dim_territoire` /
        `dim_profil_candidat`) : chaque cellule se verrait alors résoudre
        PLUSIEURS clés de substitution possibles. Un simple contrôle « pas de
        doublon sur le grain final » ne détecterait pas ce cas : les lignes
        fabriquées en trop portent, par construction, des clés de substitution
        différentes.
        """
        resultat = fait.merge(dimension, on=cles, how="left")
        if len(resultat) != len(fait):
            raise ErreurEtoile(
                f"Résolution de {nom_dimension} ambiguë : {len(resultat)} lignes obtenues pour "
                f"{len(fait)} cellules avant jointure. La dimension porte au moins deux lignes "
                f"pour une même clé naturelle {cles}."
            )
        return resultat

    lookup_formation = _deplier_versions_par_session(dim_formation)
    fait = _joindre_sans_fan_out(fait, lookup_formation, [COLONNE_SESSION, COLONNE_CLE], "formation")
    fait = _joindre_sans_fan_out(
        fait, dim_territoire[["dep", "ville_etab", "sk_territoire"]], ["dep", "ville_etab"], "territoire"
    )
    fait = _joindre_sans_fan_out(
        fait, dim_profil[["type_bac", "boursier", "sk_profil"]], ["type_bac", "boursier"], "profil"
    )
    assert len(fait) == nombre_cellules_avant_jointure  # garanti par les trois jointures ci-dessus

    orphelins_formation = fait["sk_formation"].isna()
    orphelins_territoire = fait["sk_territoire"].isna()
    if orphelins_formation.any() or orphelins_territoire.any():
        raise ErreurEtoile(
            f"{int(orphelins_formation.sum())} cellule(s) sans version de formation résolue, "
            f"{int(orphelins_territoire.sum())} sans territoire résolu : dimension incomplète "
            "par rapport aux faits, ce qui romprait l'intégrité référentielle."
        )

    fait["effectif"] = fait["nb_voe_pp"]
    fait["taux"], fait["taux_depasse_1"] = calculer_taux(fait["prop_tot"], fait["nb_voe_pp"])

    fait = fait[
        [
            COLONNE_SESSION,
            "sk_formation",
            "sk_territoire",
            "sk_profil",
            "nb_voe_pp",
            "prop_tot",
            "effectif",
            "taux",
            "taux_depasse_1",
        ]
    ].astype({"sk_formation": "Int64", "sk_territoire": "Int64", "sk_profil": "Int64"})

    doublons = fait.duplicated(subset=[COLONNE_SESSION, "sk_formation", "sk_profil"])
    if doublons.any():
        raise ErreurEtoile(
            f"{int(doublons.sum())} violation(s) du grain (session, formation, profil) de fait_admission."
        )

    return fait.sort_values([COLONNE_SESSION, "sk_formation", "sk_profil"], kind="stable").reset_index(
        drop=True
    )


@dataclass(frozen=True)
class Etoile:
    """Les cinq tables gold, prêtes à être écrites en Parquet."""

    dim_session: pd.DataFrame
    dim_formation: pd.DataFrame
    dim_territoire: pd.DataFrame
    dim_profil_candidat: pd.DataFrame
    fait_admission: pd.DataFrame
    rapport: RapportEtoile


def construire_etoile(silver: pd.DataFrame) -> Etoile:
    """Construit les cinq tables gold à partir de la table silver réconciliée (E15)."""
    base = base_exploitable(silver)

    dim_session = construire_dim_session(silver, base)
    dim_formation = construire_dim_formation(base)
    dim_territoire = construire_dim_territoire(base)
    dim_profil = construire_dim_profil_candidat()
    fait = construire_fait_admission(base, dim_formation, dim_territoire, dim_profil)

    rapport = RapportEtoile(
        lignes_fait_par_session={
            int(session): int(count)
            for session, count in fait[COLONNE_SESSION].value_counts().sort_index().items()
        },
        nombre_formations=int(dim_formation[COLONNE_CLE].nunique()),
        nombre_versions_formation=len(dim_formation),
        nombre_territoires=len(dim_territoire),
        sessions_sans_label=tuple(
            sorted(int(s) for s in dim_session.loc[~dim_session["label_disponible"], "session"])
        ),
    )
    return Etoile(
        dim_session=dim_session,
        dim_formation=dim_formation,
        dim_territoire=dim_territoire,
        dim_profil_candidat=dim_profil,
        fait_admission=fait,
        rapport=rapport,
    )


NOMS_TABLES: tuple[str, ...] = (
    "dim_session",
    "dim_formation",
    "dim_territoire",
    "dim_profil_candidat",
    "fait_admission",
)


def ecrire_etoile(etoile: Etoile, dossier: Path) -> None:
    """Écrit les cinq tables en Parquet, chacune par fichier temporaire renommé (idempotence).

    Même primitive que silver (`edumatch.transform.reconciliation.ecrire_silver`) :
    `ecriture_atomique` garantit qu'un lecteur concurrent, ou une reprise
    après coupure, ne voit jamais un fichier gold à moitié écrit.
    """
    for nom in NOMS_TABLES:
        table = getattr(etoile, nom)
        bloc_arrow = pa.Table.from_pandas(table, preserve_index=False)
        with ecriture_atomique(dossier / f"{nom}.parquet", mode="wb") as flux:
            pq.write_table(bloc_arrow, flux, compression="snappy")
