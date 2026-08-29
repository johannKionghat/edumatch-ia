"""Contrôles qualité du fichier brut Parcoursup, un millésime à la fois (E14).

Quatre familles, dans l'ordre du plan d'exécution : schéma, complétude,
cohérence, fraîcheur. Le schéma et la complétude des colonnes de la liste
blanche (`modele.variables.session_courante`) sont exprimés avec **Pandera**,
retenu plutôt que Great Expectations pour ce contrôle précis : un seul
DataFrame en mémoire par millésime (14 252 lignes au plus, 82 Mo pour les
huit fichiers), pas de magasin de contexte ni de suite persistée à gérer,
une déclaration de schéma qui tient dans une fonction. Le raisonnement
complet — l'alternative écartée et son coût mesuré — est dans le docstring
du paquet (`edumatch.quality.__init__`).

Trois pièges déjà rencontrés dans ce projet, et pour lesquels ce module
contient un contrôle dédié plutôt qu'une règle générique qui les aurait ratés
ou, pire, aurait signalé à tort une donnée correcte :

1. `dep` n'est pas un entier : la Corse porte `2A` et `2B`.
2. `acc_term` n'est pas incomplète, elle est **non applicable** — 0 % de
   manque pour BTS et CPGE, 100 % ailleurs, jamais entre les deux (vérifié
   sur les 14 252 lignes de la session 2025). Un contrôle de complétude
   naïf la signalerait à tort.
3. Le dépassement de 1 dans `prop_tot_x / nb_voe_pp_x` est **structurel**
   (réémissions après désistement, ADR 0009), observé jusqu'à un ratio de
   26 sur la session 2025 : le contrôle ne borne donc jamais ce ratio, il ne
   rejette que l'impossible (valeur négative, ou admis compté sans aucun
   vœu).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from edumatch.config import Settings, VariablesConfig, get_settings
from edumatch.quality._diagnostic import Anomalie, Gravite, RapportControle, fusionner
from edumatch.quality._fraicheur import controler_fraicheur

# Colonnes de la liste blanche (modele.variables.session_courante) et clé de
# jointure (cles) apparues seulement à partir d'un certain millésime.
# Mesuré directement sur les huit échantillons versionnés
# (`data/samples/parcoursup/`), reproductible par :
#
#   python -c "
#   import csv
#   for a in range(2018, 2026):
#       with open(f'data/samples/parcoursup/parcoursup_{a}.csv', encoding='utf-8-sig') as f:
#           print(a, next(csv.reader(f, delimiter=';')))"
#
# Ce n'est pas un seuil réglable : c'est un fait d'historique de publication,
# au même titre que le gabarit d'URL Parcoursup. Il n'a donc pas sa place
# dans configs/base.yaml, contrairement aux seuils numériques de
# `Settings.qualite`.
PREMIERE_APPARITION: dict[str, int] = {
    "cod_aff_form": 2020,
    "select_form": 2020,
    "contrat_etab": 2019,
}

# `lien_form_psup` est une clé de reconstruction (ADR 0010), pas un attribut
# de catalogue toujours renseigné : sa couverture documentée est de 92,4 %
# (2018) et 94,6 % (2019), retrouvée à l'identique sur les échantillons
# 2018/2019/2022 lors de l'écriture de ce contrôle (92,5 % à 95,0 %). Exiger
# 99 % la signalerait à tort sur des millésimes entiers. Sa présence reste
# vérifiée par le schéma ; seule sa complétude échappe au seuil commun.
COLONNES_SANS_SEUIL_DE_COMPLETUDE: frozenset[str] = frozenset({"lien_form_psup"})

# `dep` accepte les départements métropolitains et d'outre-mer (1 à 3
# chiffres) et les deux départements corses. Vérifié sans exception sur les
# millésimes 2018, 2020 et 2025 réellement téléchargés (103, 103 et 106
# valeurs distinctes).
MOTIF_DEPARTEMENT = r"^(2A|2B|\d{1,3})$"

# Les 19 colonnes de pourcentage reconstructibles à 0,5 point près (l'arrondi
# au point entier) depuis l'un des deux dénominateurs ci-dessous, tel
# qu'établi et vérifié dans l'ADR 0013. `pct_bours` s'est révélé, à la
# vérification, rapporté à `acc_neobac` et non à `acc_tot` : la table n'a pas
# été recopiée du nom des colonnes, elle a été mesurée colonne par colonne.
RECONSTRUCTION_POURCENTAGES: dict[str, str] = {
    "pct_bours": "acc_neobac",
    "pct_bg": "acc_neobac",
    "pct_bt": "acc_neobac",
    "pct_bp": "acc_neobac",
    "pct_bg_mention": "acc_neobac",
    "pct_bt_mention": "acc_neobac",
    "pct_bp_mention": "acc_neobac",
    "pct_tb": "acc_neobac",
    "pct_b": "acc_neobac",
    "pct_ab": "acc_neobac",
    "pct_sansmention": "acc_neobac",
    "pct_mention_nonrenseignee": "acc_neobac",
    "pct_tbf": "acc_neobac",
    "pct_aca_orig": "acc_neobac",
    "pct_aca_orig_idf": "acc_neobac",
    "pct_neobac": "acc_tot",
    "pct_f": "acc_tot",
    "pct_acc_debutpp": "acc_tot",
    "pct_acc_datebac": "acc_tot",
    "pct_acc_finpp": "acc_tot",
}

# Les six couples (numérateur, dénominateur) du label, déclinés par type de
# baccalauréat et statut de boursier (ADR 0009). Le ratio peut dépasser 1 —
# c'est structurel — mais ne peut jamais être négatif, ni positif avec un
# dénominateur nul.
COUPLES_RATIO_ADMISSION: tuple[tuple[str, str], ...] = tuple(
    (f"prop_tot_{bac}{suffixe}", f"nb_voe_pp_{bac}{suffixe}")
    for bac in ("bg", "bt", "bp")
    for suffixe in ("", "_brs")
)


def _dossier(settings: Settings) -> Path:
    return settings.raw_dir / "parcoursup"


def _charger(chemin: Path) -> pd.DataFrame:
    """Charge un millésime en texte brut : aucune colonne n'est convertie ici.

    Forcer `dtype=str` évite l'inférence de type de pandas, qui déduirait
    silencieusement un type différent d'un millésime à l'autre selon les
    valeurs présentes (`dep` en est l'exemple direct : sans ce choix, un
    millésime sans département corse serait lu en entier, un autre non).
    Chaque contrôle qui a besoin d'une valeur numérique la convertit
    explicitement, sous son propre contrôle d'erreur.
    """
    return pd.read_csv(chemin, delimiter=";", dtype=str, encoding="utf-8-sig")


def _colonnes_attendues(millesime: int, variables: VariablesConfig) -> list[str]:
    """Colonnes de la liste blanche et clés attendues pour CE millésime précis.

    Applique les exceptions historiques de `PREMIERE_APPARITION` : une
    colonne absente d'un millésime antérieur à sa première apparition connue
    n'est pas une anomalie de schéma, c'est un fait déjà documenté (ADR
    0013). L'exiger quand même produirait exactement le faux positif que
    l'énoncé de cette étape demande d'éviter.
    """
    candidates = list(variables.session_courante) + [c for c in variables.cles if c != "cod_aff_form"]
    candidates.append("cod_aff_form")
    return [c for c in candidates if millesime >= PREMIERE_APPARITION.get(c, 0)]


def _schema_pandera(colonnes: list[str]) -> pa.DataFrameSchema:
    """Un schéma Pandera par millésime : présence, type texte, domaine de `dep`.

    La complétude n'y figure délibérément pas : un `pandera.Check` posé sur
    une colonne `nullable=True` s'exécute sur la série **débarrassée de ses
    valeurs nulles** avant même d'être appelé — vérifié en le provoquant
    (98 valeurs sur 100, deux vides, un seuil de 99 % : le contrôle passait
    quand même, la moyenne de complétude calculée à l'intérieur du `Check` ne
    voyait jamais les deux absences). Pandera est donc réservé à ce qu'il
    fait bien ici — présence et domaine — la complétude se calcule à part,
    dans `_controler_completude`, sur le DataFrame complet.
    """

    def _colonne(nom: str) -> pa.Column:
        verifications = [pa.Check.str_matches(MOTIF_DEPARTEMENT)] if nom == "dep" else []
        return pa.Column(str, checks=verifications, nullable=True, required=True)

    return pa.DataFrameSchema({nom: _colonne(nom) for nom in colonnes}, strict=False)


def controler_schema_et_completude(
    chemin: Path, millesime: int, variables: VariablesConfig, seuil_completude: float
) -> RapportControle:
    """Schéma (présence, type, domaine de `dep`) puis complétude de la liste blanche.

    Une seule lecture du fichier sert les deux familles.
    """
    donnees = _charger(chemin)
    colonnes = _colonnes_attendues(millesime, variables)
    schema = _schema_pandera(colonnes)
    try:
        schema.validate(donnees, lazy=True)
    except pa.errors.SchemaErrors as erreur:
        return _rapport_depuis_erreurs_pandera(millesime, erreur)
    anomalies = _controler_completude(millesime, donnees, colonnes, seuil_completude)
    return RapportControle(source="parcoursup", anomalies=tuple(anomalies))


def _rapport_depuis_erreurs_pandera(millesime: int, erreur: pa.errors.SchemaErrors) -> RapportControle:
    anomalies = [
        Anomalie(
            "parcoursup",
            "schema",
            Gravite.BLOQUANT,
            f"millésime {millesime} : {ligne['column']} — {ligne['check']} ({ligne['failure_case']})",
        )
        for ligne in erreur.failure_cases.to_dict(orient="records")
    ]
    return RapportControle(source="parcoursup", anomalies=tuple(anomalies))


def _controler_completude(
    millesime: int, donnees: pd.DataFrame, colonnes: list[str], seuil: float
) -> list[Anomalie]:
    anomalies = []
    for nom in colonnes:
        if nom in COLONNES_SANS_SEUIL_DE_COMPLETUDE:
            continue
        taux = donnees[nom].notna().mean()
        if taux < seuil:
            anomalies.append(
                Anomalie(
                    "parcoursup",
                    "completude",
                    Gravite.BLOQUANT,
                    f"millésime {millesime} : {nom} renseignée à {taux:.2%}, "
                    f"sous le seuil de {seuil:.0%}.",
                )
            )
    return anomalies


def controler_non_applicable_acc_term(chemin: Path) -> RapportControle:
    """`acc_term` n'est pas une valeur manquante : elle est bimodale par filière.

    0 % de manque pour BTS et CPGE, 100 % ailleurs, jamais entre les deux
    (vérifié sur les 14 252 lignes de la session 2025). Un avertissement,
    jamais un blocage : le motif est déjà documenté (ADR 0013, motif
    `completude`), ce contrôle ne fait que le constater à nouveau sur des
    données fraîches, pour repérer le jour où une filière franchirait le
    seuil sans qu'on l'ait décidé.
    """
    donnees = _charger(chemin)
    if "acc_term" not in donnees.columns or "fili" not in donnees.columns:
        return RapportControle(source="parcoursup", anomalies=())
    taux_rempli = donnees.groupby("fili")["acc_term"].apply(lambda s: s.notna().mean())
    ambigues = taux_rempli[(taux_rempli > 0) & (taux_rempli < 1)]
    anomalies = tuple(
        Anomalie(
            "parcoursup",
            "completude",
            Gravite.AVERTISSEMENT,
            f"acc_term renseignée à {taux:.1%} pour la filière {fili!r}, ni 0 % ni 100 % : "
            "le motif « non applicable » (ADR 0013) ne tient peut-être plus.",
        )
        for fili, taux in ambigues.items()
    )
    return RapportControle(source="parcoursup", anomalies=anomalies)


def controler_coherence(chemin: Path, tolerance_pourcentage: float) -> RapportControle:
    """Trois relations, chacune vérifiée sur les huit sessions réellement téléchargées avant d'être inscrite ici.

    - `acc_tot == acc_bg + acc_bt + acc_bp + acc_at` : exacte sur 2018, 2024
      et 2025, mais pas sur 2019-2023 (11 à 21 lignes par session, toujours
      un écart de 1). Rétrogradée en avertissement : voir
      `_controler_somme_admis`.
    - Le ratio admission/vœux ne peut être négatif — mais peut dépasser 1
      (jusqu'à 26 en 2025) et peut porter un dénominateur nul pour un
      numérateur positif (482 cellules en 2025) : aucun des deux derniers
      cas n'est bloqué, voir `_controler_ratios_admission`.
    - Les 19 colonnes de pourcentage se reconstituent à 0,5 point près
      (plus un epsilon flottant) depuis `acc_neobac` ou `acc_tot`.
    """
    donnees = _charger(chemin)
    anomalies: list[Anomalie] = []
    anomalies += _controler_somme_admis(donnees)
    anomalies += _controler_ratios_admission(donnees)
    anomalies += _controler_reconstruction_pourcentages(donnees, tolerance_pourcentage)
    return RapportControle(source="parcoursup", anomalies=tuple(anomalies))


def _to_num(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie, errors="coerce")


def _controler_somme_admis(donnees: pd.DataFrame) -> list[Anomalie]:
    """`acc_tot == acc_bg + acc_bt + acc_bp + acc_at`, presque toujours, jamais garanti.

    Vérifiée d'abord sur la session 2025 (14 252 lignes) : exacte partout.
    Rejouée ensuite sur les huit sessions réellement téléchargées avant
    d'être fixée en bloquante — et là, la règle ne tient plus : 11 à 21
    lignes sur 2019 à 2023 portent un écart, jamais négatif, d'une ampleur
    de 1 à 5 selon la ligne, absent en 2018, 2024 et 2025. La cause la plus
    probable est un baccalauréat hors des quatre catégories dénombrées ici
    (diplôme international, DAEU...), mais aucun champ des fichiers dont je
    dispose ne le confirme. Un écart de cette nature reste donc un
    avertissement, pas un blocage : le signaler à tort empêcherait de
    traiter des sessions entières, pour une hypothèse de cause que je ne
    peux pas vérifier.
    """
    colonnes = ("acc_tot", "acc_bg", "acc_bt", "acc_bp", "acc_at")
    if not set(colonnes).issubset(donnees.columns):
        return []
    valeurs = {c: _to_num(donnees[c]) for c in colonnes}
    comparables = valeurs["acc_tot"].notna() & pd.concat(
        [valeurs[c].notna() for c in colonnes[1:]], axis=1
    ).all(axis=1)
    ecart = valeurs["acc_tot"] - sum(valeurs[c] for c in colonnes[1:])
    violations = comparables & (ecart != 0)
    if not violations.any():
        return []
    return [
        Anomalie(
            "parcoursup",
            "coherence",
            Gravite.AVERTISSEMENT,
            f"acc_tot ≠ acc_bg + acc_bt + acc_bp + acc_at sur {int(violations.sum())} ligne(s) "
            f"(écart maximal observé : {int(ecart[violations].abs().max())}).",
        )
    ]


def _controler_ratios_admission(donnees: pd.DataFrame) -> list[Anomalie]:
    """Seule une valeur négative est traitée comme impossible.

    Une hypothèse plus large a été écrite puis retirée : interdire un
    numérateur positif à dénominateur nul (« un admis sans aucun vœu compté
    dans cette cellule »). Vérifiée sur la session 2025 réelle avant d'être
    conservée, elle s'est révélée fausse — **482 cellules** sur les six
    couples présentent ce cas, bien trop pour une corruption. Explication la
    plus probable : `prop_tot` comptabilise des propositions issues d'autres
    filières de vœux (vœux complémentaires, meilleurs bacheliers...) que
    `nb_voe_pp` ne compte pas dans cette cellule précise — deux compteurs
    Parcoursup qui ne délimitent pas exactement la même population, au même
    titre que le dépassement de 1 (ADR 0009). Seule une valeur négative,
    qu'aucun dénombrement ne peut produire légitimement, reste bloquante.
    """
    anomalies: list[Anomalie] = []
    for numerateur, denominateur in COUPLES_RATIO_ADMISSION:
        if numerateur not in donnees.columns or denominateur not in donnees.columns:
            continue
        negatifs = (_to_num(donnees[numerateur]) < 0) | (_to_num(donnees[denominateur]) < 0)
        if negatifs.fillna(False).any():
            anomalies.append(
                Anomalie(
                    "parcoursup",
                    "coherence",
                    Gravite.BLOQUANT,
                    f"{numerateur}/{denominateur} : {int(negatifs.sum())} valeur(s) négative(s), "
                    "impossible pour un dénombrement.",
                )
            )
    return anomalies


def _controler_reconstruction_pourcentages(
    donnees: pd.DataFrame, tolerance: float
) -> list[Anomalie]:
    """Compare chaque `pct_*` à sa reconstruction, tolérance augmentée d'un epsilon flottant.

    Sans cet epsilon, le contrôle échoue sur les huit sessions réellement
    téléchargées pour un écart mesuré de 0,5000000000000071 — la tolérance
    de 0,5 point elle-même, déformée par l'arithmétique flottante de la
    division, pas une vraie violation. Vérifié ligne par ligne (millésime
    2025, `cod_aff_form` 2235 : `pct_bg` 58,0 contre 23/40×100 =
    57,49999999999999) avant d'ajouter cette marge plutôt que de l'écarter.
    """
    epsilon = 1e-6
    anomalies: list[Anomalie] = []
    for colonne_pct, colonne_base, colonne_denom in _triplets_reconstruction(donnees.columns):
        pct = _to_num(donnees[colonne_pct])
        base = _to_num(donnees[colonne_base])
        denom = _to_num(donnees[colonne_denom])
        recompose = (base / denom * 100).where(denom != 0)
        comparable = pct.notna() & recompose.notna()
        ecart = (pct - recompose).abs()
        violations = comparable & (ecart > tolerance + epsilon)
        if violations.any():
            anomalies.append(
                Anomalie(
                    "parcoursup",
                    "coherence",
                    Gravite.BLOQUANT,
                    f"{colonne_pct} s'écarte de plus de {tolerance} point de sa reconstruction "
                    f"depuis {colonne_denom} sur {int(violations.sum())} ligne(s).",
                )
            )
    return anomalies


def _triplets_reconstruction(colonnes_presentes: pd.Index) -> list[tuple[str, str, str]]:
    """Associe chaque colonne `pct_*` à la colonne d'admis et au dénominateur qui la reconstruisent."""
    triplets = []
    for colonne_pct, colonne_denom in RECONSTRUCTION_POURCENTAGES.items():
        colonne_base = _colonne_base(colonne_pct)
        if {colonne_pct, colonne_base, colonne_denom}.issubset(colonnes_presentes):
            triplets.append((colonne_pct, colonne_base, colonne_denom))
    return triplets


def _colonne_base(colonne_pct: str) -> str:
    """La colonne d'effectif que le pourcentage rapporte, déduite de son nom.

    `pct_f` et `pct_neobac` sont les deux exceptions dont le nom ne
    correspond à aucune colonne `acc_*` directe : elles se rapportent
    respectivement à `acc_tot_f` et `acc_neobac`, déjà couvertes par la table
    `RECONSTRUCTION_POURCENTAGES` elle-même comme dénominateur pour la
    seconde. Pour la première, la colonne de base EST le dénominateur
    interdit (`acc_tot_f`, ventilation par sexe) : elle est donc exclue plus
    haut, `pct_f` ne peut jamais être vérifiée par ce contrôle, seulement
    citée dans l'ADR comme redondante.
    """
    correspondance = {
        "pct_f": "acc_tot_f",
        "pct_neobac": "acc_neobac",
    }
    if colonne_pct in correspondance:
        return correspondance[colonne_pct]
    return "acc_" + colonne_pct.removeprefix("pct_")


def controler_fraicheur_parcoursup(
    settings: Settings, manifeste: dict[str, dict[str, object]]
) -> RapportControle:
    """Fraîcheur du seul millésime le plus récent configuré.

    Les millésimes plus anciens sont des archives immuables par construction
    (bronze) : leur ancienneté est voulue, pas une anomalie. Seule la
    campagne en cours doit être surveillée.
    """
    dernier = max(settings.donnees.parcoursup.millesimes)
    entree = manifeste.get(str(dernier))
    date = entree.get("date_telechargement") if entree else None
    anomalies = controler_fraicheur(
        "parcoursup",
        {f"millesime_{dernier}": date},
        settings.qualite.parcoursup.age_max_jours_avertissement,
    )
    return RapportControle(source="parcoursup", anomalies=tuple(anomalies))


def controler_millesime(chemin: Path, millesime: int, settings: Settings) -> RapportControle:
    """Les trois familles applicables à un fichier déjà sur disque : schéma, complétude, cohérence.

    La fraîcheur se contrôle à part (`controler_fraicheur_parcoursup`) : elle
    porte sur le manifeste, pas sur le contenu d'un fichier précis.
    """
    config_qualite = settings.qualite.parcoursup
    rapports = (
        controler_schema_et_completude(
            chemin, millesime, settings.modele.variables, config_qualite.seuil_completude
        ),
        controler_non_applicable_acc_term(chemin),
        controler_coherence(chemin, config_qualite.tolerance_reconstruction_pourcentage),
    )
    return fusionner("parcoursup", *rapports)


def controler_tous(settings: Settings | None = None) -> RapportControle:
    """Contrôle chaque millésime présent sur disque, puis la fraîcheur du plus récent."""
    settings = settings or get_settings()
    dossier = _dossier(settings)
    manifeste_chemin = dossier / "manifeste.json"
    manifeste = (
        json.loads(manifeste_chemin.read_text(encoding="utf-8")) if manifeste_chemin.exists() else {}
    )

    rapports = [
        controler_millesime(dossier / f"parcoursup_{millesime}.csv", millesime, settings)
        for millesime in settings.donnees.parcoursup.millesimes
        if (dossier / f"parcoursup_{millesime}.csv").exists()
    ]
    rapports.append(controler_fraicheur_parcoursup(settings, manifeste))
    return fusionner("parcoursup", *rapports)
