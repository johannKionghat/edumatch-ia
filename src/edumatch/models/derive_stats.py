"""Statistiques de dérive : indice de stabilité de population (PSI) et test de
Kolmogorov-Smirnov, séparées de `models/derive.py` pour la même raison que `metrics.py`
est séparé de `train.py` — un calcul générique, indépendant de la table de variables et
du modèle, réutilisable et testable seul.

## PSI, et pourquoi un jeu de fonctions par type de variable

L'indice de stabilité de population compare deux distributions en les découpant en
tranches, puis en sommant `(p_comparaison - p_reference) * ln(p_comparaison / p_reference)`
sur chaque tranche (`_psi_depuis_proportions`). Il n'existe qu'une seule formule ; ce qui
diffère selon le type de variable, c'est la façon de construire les tranches :

- **numérique** (`psi_numerique`) : tranches de quantile de la référence — la même
  granularité que le diagramme de fiabilité (`evaluation.n_tranches_calibration`,
  `models.metrics.calibration`), pour la même raison (assez fin, pas de tranches vides) ;
- **catégorielle** (`psi_categorielle`) : une tranche par modalité, les moins fréquentes de
  la référence regroupées sous une modalité `__autre__` au-delà de `top_k` (voir
  `DeriveConfig.top_k_categories_psi`) — sans ce plafond, une colonne à forte cardinalité
  (`fil_lib_voe_acc`, 712 modalités) ferait dominer le PSI par un simple renouvellement de
  libellés plutôt que par un déplacement réel de la distribution.

## La dérive amont, mesurée et non pas seulement citée

`canoniser_categorie` neutralise les variations de forme d'un même libellé — accent,
casse, tiret contre espace (« Grand Est » / « Grand-Est », « formation sélective » /
« formation sélective ») — avant de comparer deux sessions Parcoursup. Mesuré sur les
données réelles de ce dépôt (`region_etab_aff`, `select_form`), ce n'est pas une
précaution théorique : sans cette neutralisation, le PSI de `region_etab_aff` entre
l'entraînement et le test 2025 vaut 4,99 (une dérive massive), et 0,76 après
neutralisation — la moitié de l'écart mesuré n'est qu'un changement de graphie d'une
session à l'autre, pas un déplacement géographique réel des formations. C'est la
dérive amont du plan de détection : une source qui change de format produit
exactement les mêmes symptômes qu'un changement du monde réel (voir `derive.py` pour la
suite du diagnostic sur ces deux variables, et le compte rendu de l'étape pour le
détail des modalités en cause).

`psi_categorielle` neutralise systématiquement : c'est la mesure utilisée pour décider
d'un réentraînement, jamais le PSI brut, dont l'écart révèle une instabilité de forme du
pipeline en amont — utile à signaler, jamais à laisser déclencher un réentraînement.
"""

from __future__ import annotations

import unicodedata

import numpy as np
import pandas as pd

# Plancher de proportion avant le logarithme du PSI : une tranche à zéro dans l'une des
# deux distributions rendrait le ratio infini ou nul. Valeur usuelle de la littérature du
# score de crédit (où le PSI est né) : assez petite pour ne quasiment rien changer à une
# tranche déjà peuplée, assez grande pour qu'une tranche vide ne domine jamais la somme.
_PLANCHER_PROPORTION = 1e-4

CATEGORIE_MANQUANTE = "__manquant__"
CATEGORIE_AUTRE = "__autre__"

TYPES_PANDAS_CATEGORIELS: tuple[str, ...] = ("string", "str", "object", "bool", "boolean")


def est_categorielle(serie: pd.Series) -> bool:
    """Vrai si `serie` doit être traitée comme catégorielle plutôt que numérique.

    Mêmes familles de types que `models.jeux.preparer_matrice` (LightGBM) : une colonne
    `string`/`object`/`bool`/`boolean` est catégorielle, une colonne `Int64`/`Float64` est
    numérique. Les deux modules doivent s'accorder sur cette frontière, sans quoi la
    dérive mesurée ne porterait pas sur le même découpage que celui vu par le modèle.
    """
    return str(serie.dtype) in TYPES_PANDAS_CATEGORIELS


def canoniser_categorie(valeur: object) -> str:
    """Neutralise accent, casse et séparateur avant comparaison (voir docstring du module).

    `NFKD` décompose un caractère accentué en lettre de base plus diacritique
    (`unicodedata.combining`), que ce plancher supprime ; la casse et les séparateurs
    (tiret, tiret bas) sont ensuite uniformisés en espace simple. `pandas.NA` et `None`
    deviennent `CATEGORIE_MANQUANTE` : l'absence est une modalité comparable comme une
    autre entre deux sessions, jamais une exception.
    """
    if valeur is None or valeur is pd.NA:
        return CATEGORIE_MANQUANTE
    texte = unicodedata.normalize("NFKD", str(valeur))
    texte = "".join(caractere for caractere in texte if not unicodedata.combining(caractere))
    texte = texte.lower().replace("-", " ").replace("_", " ")
    return " ".join(texte.split()) or CATEGORIE_MANQUANTE


def _psi_depuis_proportions(proportions_reference: np.ndarray, proportions_comparaison: np.ndarray) -> float:
    """`sum((p_comp - p_ref) * ln(p_comp / p_ref))`, les deux vecteurs déjà alignés tranche à tranche."""
    p_ref = np.clip(proportions_reference, _PLANCHER_PROPORTION, None)
    p_comp = np.clip(proportions_comparaison, _PLANCHER_PROPORTION, None)
    return float(np.sum((p_comp - p_ref) * np.log(p_comp / p_ref)))


def _bornes_quantiles(reference: np.ndarray, n_tranches: int) -> np.ndarray:
    """Bornes de `n_tranches` tranches de quantile de `reference`, ouvertes aux extrémités.

    `np.unique` retire les bornes dupliquées qu'une distribution très concentrée (beaucoup
    de valeurs identiques) produirait sinon — une variable dont plus de `1/n_tranches` des
    valeurs de référence sont égales à zéro (fréquent ici : `nb_voe_pp_bp_brs`, une petite
    population de boursiers en professionnel) a donc moins de `n_tranches` bornes réelles,
    jamais des tranches vides comblées artificiellement.
    """
    quantiles = np.linspace(0.0, 1.0, n_tranches + 1)
    bornes = np.unique(np.quantile(reference, quantiles))
    if bornes.size < 2:
        return np.array([])
    bornes[0] = -np.inf
    bornes[-1] = np.inf
    return bornes


def psi_numerique(reference: pd.Series, comparaison: pd.Series, n_tranches: int) -> float:
    """PSI d'une variable numérique, tranches de quantile de `reference`.

    Une référence sans variation (moins de deux bornes distinctes une fois les doublons
    retirés — une colonne constante sur la fenêtre d'entraînement) ou une des deux séries
    entièrement manquante rendent la comparaison sans objet : `0.0`, jamais une erreur qui
    interromprait la mesure des 45 autres variables.
    """
    ref = reference.dropna().to_numpy(dtype="float64")
    comp = comparaison.dropna().to_numpy(dtype="float64")
    if ref.size == 0 or comp.size == 0:
        return 0.0
    bornes = _bornes_quantiles(ref, n_tranches)
    if bornes.size < 2:
        return 0.0
    tranches_ref = pd.Series(pd.cut(ref, bornes, include_lowest=True))
    tranches_comp = pd.Series(pd.cut(comp, bornes, include_lowest=True))
    proportions_ref = tranches_ref.value_counts(sort=False) / ref.size
    proportions_comp = tranches_comp.value_counts(sort=False) / comp.size
    proportions_comp = proportions_comp.reindex(proportions_ref.index, fill_value=0.0)
    return _psi_depuis_proportions(proportions_ref.to_numpy(), proportions_comp.to_numpy())


def psi_categorielle(reference: pd.Series, comparaison: pd.Series, top_k: int) -> float:
    """PSI d'une variable catégorielle, catégories canonisées et plafonnées à `top_k` (voir docstring du module)."""
    ref = reference.map(canoniser_categorie)
    comp = comparaison.map(canoniser_categorie)
    if ref.empty or comp.empty:
        return 0.0
    frequentes = ref.value_counts().head(top_k).index
    ref_regroupee = ref.where(ref.isin(frequentes), CATEGORIE_AUTRE)
    comp_regroupee = comp.where(comp.isin(frequentes), CATEGORIE_AUTRE)
    categories = sorted(set(ref_regroupee.unique()) | set(comp_regroupee.unique()))
    proportions_ref = ref_regroupee.value_counts(normalize=True).reindex(categories, fill_value=0.0)
    proportions_comp = comp_regroupee.value_counts(normalize=True).reindex(categories, fill_value=0.0)
    return _psi_depuis_proportions(proportions_ref.to_numpy(), proportions_comp.to_numpy())


def ks_numerique(reference: pd.Series, comparaison: pd.Series) -> float | None:
    """Statistique de Kolmogorov-Smirnov (écart maximal entre fonctions de répartition empiriques).

    `None` pour une variable catégorielle (pas d'ordre entre modalités, la notion de
    fonction de répartition n'a pas de sens) ou une série vide — jamais une valeur inventée
    pour compléter le rapport. Purement informatif ici (voir `derive.py`) : seul le PSI
    gouverne le déclenchement du réentraînement (`DeriveConfig.seuil_reentrainement`),
    parce que c'est la mesure que `configs/base.yaml` documente comme telle ; le KS est
    rapporté à titre de second regard sur la même paire de distributions, sensible à la
    forme plutôt qu'au découpage en tranches.
    """
    ref = np.sort(reference.dropna().to_numpy(dtype="float64"))
    comp = np.sort(comparaison.dropna().to_numpy(dtype="float64"))
    if ref.size == 0 or comp.size == 0:
        return None
    grille = np.union1d(ref, comp)
    cdf_ref = np.searchsorted(ref, grille, side="right") / ref.size
    cdf_comp = np.searchsorted(comp, grille, side="right") / comp.size
    return float(np.max(np.abs(cdf_ref - cdf_comp)))
