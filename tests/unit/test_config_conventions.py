"""Tests de conventions de code sur src/edumatch/config.py.

Verifie qu'aucun seuil, hyperparametre ou nom de fichier metier n'est ecrit en
dur dans le module : ces valeurs ne doivent exister que dans configs/*.yaml.
La detection procede par analyse de l'arbre syntaxique, afin de resister aux
formes calculees (4 / 5) ou concatenees ("Stock" + "Etablissement").
"""

from __future__ import annotations

import ast
import math

import yaml

from edumatch.config import CONFIGS_DIR, PROJECT_ROOT


# ─── Aucun littéral métier en dur dans config.py ─────────────────────────────
#
# Portée assumée de ce contrôle, et de sa limite, avant le code lui-même :
#
# Une simple recherche du littéral décimal exact (chercher "0.8" dans le
# texte source) est contournable trivialement : `4 / 5` ou `100 * 0.008`
# valent 0.8 sans jamais faire apparaître "0.8" dans le fichier, de même
# qu'une chaîne "Stock" + "Etablissement" ne contient jamais la sous-chaîne
# "StockEtablissement". C'est précisément ce que la revue qualité a
# démontré par mutation : le test précédent, fondé sur une recherche de
# texte, passait quand même sur une copie du fichier contenant ces quatre
# contournements.
#
# Le contrôle ci-dessous analyse donc l'arbre syntaxique (`ast`) de
# config.py et replie récursivement toute expression composée UNIQUEMENT de
# littéraux (constantes combinées par +, -, *, / ou //) pour en calculer la
# valeur réelle, avant de la comparer à la liste des valeurs métier
# interdites.
#
# Limite assumée, à ne pas surestimer : ce repliement ne « voit » que des
# expressions entièrement littérales. Une valeur obtenue via une variable,
# un import, un appel de fonction (ex. `round(x, 2)`, une lecture de
# fichier, un calcul dépendant d'un paramètre d'exécution) n'est PAS
# détectée — ni une évasion plus sophistiquée et délibérée (encodage,
# obscurcissement). Ce contrôle durcit une garantie déjà utile contre
# l'erreur ordinaire (recopier une valeur du YAML par commodité) et contre
# les formes de contournement les plus immédiates ; il ne prétend pas à
# l'exhaustivité contre un contournement délibéré et motivé — aucune
# analyse statique ne le peut en général.

_NON_PLIABLE = object()


def _plier_litteral(noeud: ast.AST) -> object:
    """Réduit un nœud AST composé uniquement de littéraux à sa valeur Python.

    Retourne `_NON_PLIABLE` dès que le nœud (ou l'un de ses opérandes) n'est
    pas une constante ou une combinaison arithmétique de constantes —
    c'est-à-dire dès qu'une variable, un appel ou un nom quelconque
    intervient.
    """
    if isinstance(noeud, ast.Constant):
        return noeud.value
    if isinstance(noeud, ast.BinOp):
        gauche = _plier_litteral(noeud.left)
        droite = _plier_litteral(noeud.right)
        if gauche is _NON_PLIABLE or droite is _NON_PLIABLE:
            return _NON_PLIABLE
        try:
            if isinstance(noeud.op, ast.Add):
                return gauche + droite
            if isinstance(noeud.op, ast.Sub):
                return gauche - droite
            if isinstance(noeud.op, ast.Mult):
                return gauche * droite
            if isinstance(noeud.op, ast.Div):
                return gauche / droite
            if isinstance(noeud.op, ast.FloorDiv):
                return gauche // droite
        except (TypeError, ZeroDivisionError):
            return _NON_PLIABLE
    return _NON_PLIABLE


def _reperer_litteraux_interdits(
    source: str, valeurs_numeriques_interdites: set[float], chaines_interdites: set[str]
) -> list[tuple[object, str]]:
    """Repère, dans `source`, toute expression purement littérale qui vaut une valeur interdite.

    Couvre les constantes directes (`31`) comme les combinaisons
    arithmétiques de constantes (`4 / 5`) et les concaténations de chaînes
    littérales (`"Stock" + "Etablissement"`). Voir la note en tête de
    section pour ce que cette détection ne couvre pas.
    """
    arbre = ast.parse(source)
    trouves: list[tuple[object, str]] = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.Constant, ast.BinOp)):
            continue
        valeur = _plier_litteral(noeud)
        if valeur is _NON_PLIABLE or isinstance(valeur, bool):
            continue
        if isinstance(valeur, (int, float)):
            for interdite in valeurs_numeriques_interdites:
                if math.isclose(valeur, interdite, rel_tol=1e-9, abs_tol=1e-9):
                    trouves.append((valeur, ast.dump(noeud)))
                    break
        elif isinstance(valeur, str) and valeur in chaines_interdites:
            trouves.append((valeur, ast.dump(noeud)))
    return trouves


def _valeurs_metier_distinctives(base_yaml: dict) -> set[float]:
    """Valeurs de configs/base.yaml assez distinctives pour qu'une coïncidence soit improbable.

    On exclut volontairement 0, 1, 8, 20 ou 100 : ce sont aussi des bornes
    de validation génériques légitimement présentes dans config.py (ex.
    `le=100` pour un pourcentage), donc les inclure produirait des faux
    positifs sans rapport avec une fuite de valeur métier.
    """
    return {
        base_yaml["modele"]["hyperparametres"]["num_leaves"],  # 31
        base_yaml["modele"]["hyperparametres"]["learning_rate"],  # 0.05
        base_yaml["modele"]["hyperparametres"]["n_estimators"],  # 2000
        base_yaml["equite"]["seuil_impact_disparate"],  # 0.80
        base_yaml["derive"]["seuil_reentrainement"],  # 0.20
        base_yaml["api"]["slo_latence_p95_ms"],  # 300
        min(base_yaml["donnees"]["parcoursup"]["millesimes"]),  # 2018
        max(base_yaml["donnees"]["parcoursup"]["millesimes"]),  # 2025
    }


def _chaines_metier_distinctives(base_yaml: dict) -> set[str]:
    """Chaînes de configs/base.yaml qui n'ont aucune raison d'être recopiées dans le code."""
    return set(base_yaml["donnees"]["sirene"]["fichiers"])


def test_aucun_littéral_métier_en_dur_dans_config_py() -> None:
    """Les seuils, hyperparamètres et noms de fichiers Sirene ne doivent exister que dans les YAML."""
    source = (PROJECT_ROOT / "src" / "edumatch" / "config.py").read_text(encoding="utf-8")
    base_yaml = yaml.safe_load((CONFIGS_DIR / "base.yaml").read_text(encoding="utf-8"))

    trouves = _reperer_litteraux_interdits(
        source,
        _valeurs_metier_distinctives(base_yaml),
        _chaines_metier_distinctives(base_yaml),
    )

    assert not trouves, (
        f"Littéral(aux) métier trouvé(s) en dur dans config.py : {trouves}. "
        "Ces valeurs doivent venir exclusivement de configs/*.yaml."
    )


def test_detection_resiste_aux_contournements_par_mutation() -> None:
    """Preuve que le repliement AST attrape ce qu'une simple recherche de texte manquait.

    Reproduit, sur un extrait de code synthétique (pas le vrai config.py),
    les quatre formes de contournement observées en revue qualité : un
    seuil d'équité écrit `4 / 5` au lieu de `0.80`, un seuil de dérive écrit
    `20 / 100` au lieu de `0.20`, un SLO écrit `30 * 10` au lieu de `300`,
    et un nom de fichier Sirene reconstruit par concaténation de littéraux.
    Les quatre doivent être détectés.
    """
    source_mutee = (
        "def _exemple() -> None:\n"
        "    seuil_impact_disparate = 4 / 5\n"
        "    seuil_reentrainement = 20 / 100\n"
        "    slo_latence_p95_ms = 30 * 10\n"
        "    fichier_sirene = \"Stock\" + \"Etablissement\"\n"
        "    return seuil_impact_disparate, seuil_reentrainement, "
        "slo_latence_p95_ms, fichier_sirene\n"
    )
    trouves = _reperer_litteraux_interdits(
        source_mutee,
        {0.80, 0.20, 300},
        {"StockEtablissement"},
    )
    valeurs_trouvees = {v for v, _ in trouves}
    assert 0.80 in valeurs_trouvees, "4 / 5 n'a pas été reconnu comme équivalent à 0.80"
    assert 0.20 in valeurs_trouvees, "20 / 100 n'a pas été reconnu comme équivalent à 0.20"
    assert 300 in valeurs_trouvees, "30 * 10 n'a pas été reconnu comme équivalent à 300"
    assert "StockEtablissement" in valeurs_trouvees, (
        "\"Stock\" + \"Etablissement\" n'a pas été reconnu comme équivalent à \"StockEtablissement\""
    )


def test_detection_ne_signale_pas_une_variable_ou_un_appel() -> None:
    """Contre-preuve : une valeur non purement littérale n'est délibérément pas signalée.

    C'est la limite assumée du contrôle (voir la note en tête de section) :
    `n_estimators * 2` où `n_estimators` est une variable n'est pas une
    fuite de valeur YAML recopiée en dur, et ne doit donc pas être signalé,
    même si le résultat numérique final coïncide avec une valeur interdite.
    """
    source = "def _exemple(n_estimators: int) -> int:\n    return n_estimators * 2\n"
    trouves = _reperer_litteraux_interdits(source, {4000.0}, set())
    assert trouves == []
