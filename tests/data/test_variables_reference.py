"""Contrat de données : le classement des variables couvre exactement les colonnes réelles.

La section `modele.variables` de `configs/base.yaml` décide du sort de chaque
colonne du fichier Parcoursup (retenue sur la session prédite, retenue décalée
d'une session, retenue sous réserve, ou exclue avec son motif). Les arbitrages
sont dans `docs/decisions.html#adr-0013`.

Ces tests vérifient deux choses que la relecture ne garantit pas :

1. **Aucune variable retenue n'est absente des fichiers sources.** Une colonne
   mal orthographiée dans la configuration serait silencieusement lue comme
   vide au moment de construire les variables.
2. **Aucune colonne source n'échappe au classement.** Si un millésime futur
   ajoute une colonne, ce test échoue tant qu'elle n'a pas été examinée et
   classée. C'est le point important : une colonne non classée n'entre pas
   dans le modèle par inadvertance, elle bloque la chaîne.

La référence est lue dans `data/samples/parcoursup/`, versionné, pour que ces
contrôles tournent sans les fichiers bruts complets.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from edumatch.config import Settings, load_settings


@pytest.fixture(scope="module")
def settings() -> Settings:
    # `prod` déclare les huit millésimes ; `dev` n'en déclare que deux et
    # laisserait 45 colonnes hors du champ du contrôle.
    return load_settings("prod")


def _entetes(chemin: Path) -> list[str]:
    """En-têtes d'un CSV Parcoursup, sans en parser le contenu."""
    with chemin.open(encoding="utf-8-sig") as fichier:
        return next(csv.reader(fichier, delimiter=";"))


@pytest.fixture(scope="module")
def colonnes_reelles(settings: Settings) -> set[str]:
    """Union des colonnes vues au moins une fois sur les millésimes déclarés."""
    dossier = settings.samples_dir / "parcoursup"
    colonnes: set[str] = set()
    for millesime in settings.donnees.parcoursup.millesimes:
        fichier = dossier / f"parcoursup_{millesime}.csv"
        assert fichier.exists(), (
            f"Échantillon manquant : {fichier}. Le régénérer avec `make samples`."
        )
        colonnes |= set(_entetes(fichier))
    return colonnes


def test_toute_colonne_citee_existe_dans_les_fichiers_sources(
    settings: Settings, colonnes_reelles: set[str]
) -> None:
    """Une colonne déclarée mais inexistante serait lue comme vide, sans erreur."""
    citees = settings.modele.variables.colonnes_sources
    inexistantes = sorted(citees - colonnes_reelles)
    assert not inexistantes, (
        "modele.variables cite des colonnes absentes de tous les millésimes "
        f"Parcoursup : {inexistantes}. Faute de frappe, ou colonne disparue de "
        "la source."
    )


def test_toute_colonne_source_est_classee(
    settings: Settings, colonnes_reelles: set[str]
) -> None:
    """Une colonne non classée doit bloquer, jamais entrer dans le modèle par défaut."""
    citees = settings.modele.variables.colonnes_sources
    non_classees = sorted(colonnes_reelles - citees)
    assert not non_classees, (
        f"Colonne(s) Parcoursup jamais classée(s) : {non_classees}. Décider de "
        "leur sort dans modele.variables (retenue, décalée, sous réserve, ou "
        "exclue avec motif) et consigner l'arbitrage dans un ADR avant de "
        "poursuivre."
    )


def test_les_dimensions_de_cellule_ne_sont_pas_des_colonnes(
    settings: Settings, colonnes_reelles: set[str]
) -> None:
    """`type_bac` et `boursier` viennent de la structure du label, pas du fichier.

    Les confondre avec des colonnes ferait croire qu'elles se lisent, alors
    qu'elles se construisent en dépliant chaque formation en six cellules.
    """
    dimensions = set(settings.modele.variables.dimensions_cellule)
    confusion = sorted(dimensions & colonnes_reelles)
    assert not confusion, (
        f"{confusion} figure(nt) à la fois comme dimension de cellule et comme "
        "colonne du fichier source : lever l'ambiguïté."
    )


def test_aucun_resultat_de_campagne_n_est_lu_sur_la_session_predite(
    settings: Settings,
) -> None:
    """Anti-fuite : la liste blanche de la session prédite ne contient aucun compteur.

    Le critère n'est pas « postérieur à l'admission » mais « inconnu au moment
    où le lycéen formule ses vœux ». Tout ce qui compte des vœux, des
    propositions, des admis, des rangs ou des taux d'accès n'existe qu'à la
    clôture de la campagne : ces préfixes ne doivent jamais apparaître dans
    `session_courante`.

    Le contrôle est volontairement grossier — il travaille sur des préfixes de
    nom, pas sur une compréhension de la sémantique. Il attrape l'ajout
    distrait d'une colonne de résultat à la liste blanche ; il ne prouve pas
    que les neuf colonnes retenues sont, elles, réellement publiées avant la
    campagne. Cette part relève de l'ADR, pas d'un test.
    """
    prefixes_de_resultat = (
        "prop_tot",
        "acc_",
        "pct_",
        "voe_tot",
        "nb_voe_",
        "nb_cla_",
        "ran_grp",
        "rang_der",
        "taux_acces",
        "taux_adm",
        "part_acces",
    )
    fautives = sorted(
        colonne
        for colonne in settings.modele.variables.session_courante
        if colonne.startswith(prefixes_de_resultat)
    )
    assert not fautives, (
        f"{fautives} décri(ven)t le résultat de la campagne et ne peu(ven)t pas "
        "être lue(s) sur la session prédite : la déplacer vers "
        "modele.variables.decalees."
    )
