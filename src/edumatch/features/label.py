"""Calcul du label et de sa pondération d'entraînement (E19).

## Ce que ce module porte, et pourquoi il existe

Deux choses, décidées ensemble par l'ADR 0009 mais nées à deux moments
différents du plan d'exécution du projet :

1. **La formule du taux** — `prop_tot / nb_voe_pp`, bornée à 1 — était déjà
   codée dans `edumatch.transform.etoile` (E16), qui en avait besoin avant que
   cette étape n'existe. Ce module en devient l'unique définition : `etoile.py`
   l'importe désormais au lieu de la recalculer, pour qu'une formule ne
   diverge jamais silencieusement entre la couche gold et les étapes en aval
   (variables, entraînement, audit). Le comportement n'a pas changé d'une
   virgule — voir `docs/sous-docs-projets/adr/0009-definition-et-bornage-du-label.md`
   pour l'arbitrage complet, non rouvert ici.

2. **La pondération par effectif** est le véritable ajout de cette étape :
   l'ADR 0009 l'a décidée (décision 3, poids = effectif de la cellule,
   `nb_voe_pp`, nommé `effectif_cellule` dans `configs/base.yaml`,
   `modele.ponderation`) mais ne l'avait codée nulle part.

## La pondération : la forme retenue, mesurée avant confirmation

L'ADR nomme explicitement le poids « effectif de la cellule (`nb_voe_pp`) » —
c'est-à-dire l'effectif brut, pas une racine ni un plafond. Avant de
l'appliquer tel quel, la concentration qu'il fait porter au 1 % de cellules
les plus grosses a été mesurée sur les 440 030 cellules réelles
(`data/processed/parcoursup/fait_admission.parquet`, sessions 2020-2025), et
comparée à trois alternatives qui n'ont jamais été retenues mais qui
cadrent le choix :

    effectif (nb_voe_pp)   : min 1, p25=9, médiane=30, p75=97,
                              p90=287, p99=1868, max=16 483

    part du poids total captée par le 1 % de cellules les plus grosses
    (4 400 cellules sur 440 030) selon la forme du poids :
        brut (nb_voe_pp)     : 25,9 %
        racine carrée        :  7,2 %
        log(1 + n)           :  2,3 %
        plafonné au p99      : 15,4 %

Le brut concentre nettement plus que les trois alternatives, mais reste très
loin de dominer l'entraînement (1 % des cellules ne capte pas la majorité du
poids) et c'est la seule des quatre formes qui traduit fidèlement l'écart de
fiabilité statistique entre une cellule à 3 vœux et une cellule à 500 — c'est
exactement la raison pour laquelle l'ADR 0009 écarte le poids égal (option 4)
et retient l'effectif brut (option 5). Retenu tel quel : la mesure confirme
la décision, elle ne la rouvre pas.

**Le seuil qui ferait reconsidérer** (déjà écrit dans l'ADR) : si l'audit
d'équité (E26) montre que ce quart de poids concentré défavorise
structurellement un profil (bac professionnel, notamment, où 21,6 % des
formations n'émettent aucune proposition) — il faudrait alors revoir la
pondération, pas la définition du taux.
"""

from __future__ import annotations

import pandas as pd

# Borne supérieure du taux (ADR 0009) : un dépassement vient de propositions
# réémises après désistement, pas d'une valeur aberrante à corriger.
BORNE_SUPERIEURE_TAUX: float = 1.0


class ErreurLabel(RuntimeError):
    """Le label ou son poids ne respectent pas une garantie attendue.

    Définitive : ni un dénominateur négatif, ni un effectif manquant ou nul
    ne se résolvent en relançant le calcul à l'identique — la donnée en
    amont (silver, gold) doit être corrigée.
    """


def calculer_taux(numerateur: pd.Series, denominateur: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Le taux d'admission d'une cellule : `numerateur / denominateur`, borné à 1 (ADR 0009).

    Extrait à l'identique de `edumatch.transform.etoile.construire_fait_admission`
    (E16) : même expression, même comportement aux limites, y compris ceux
    que la construction du gold ne rencontre jamais en pratique parce que
    `base_exploitable` filtre en amont (dénominateur nul ou manquant,
    numérateur manquant) mais que cette fonction, réutilisable, doit tout de
    même définir sans ambiguïté :

    - dénominateur nul, numérateur non nul  -> division infinie, bornée à 1,
      signalée par `taux_depasse_1`
    - dénominateur nul, numérateur nul      -> indéterminé, `<NA>`
    - numérateur manquant ou dénominateur manquant -> `<NA>`, propagé
    - numérateur supérieur au dénominateur  -> borné à 1, `taux_depasse_1`

    Retourne `(taux, taux_depasse_1)`, chacun aligné sur l'index d'entrée.
    """
    taux_brut = numerateur.astype("Float64") / denominateur.astype("Float64")
    taux = taux_brut.clip(upper=BORNE_SUPERIEURE_TAUX)
    taux_depasse_1 = taux_brut > BORNE_SUPERIEURE_TAUX
    return taux, taux_depasse_1


def poids_effectif(effectif: pd.Series) -> pd.Series:
    """Le poids d'entraînement d'une cellule : son effectif brut (`nb_voe_pp`, ADR 0009).

    Ni racine, ni plafond : voir la mesure de concentration dans le docstring
    du module, qui confirme ce choix plutôt que de le rouvrir. Le poids n'est
    pas normalisé ici (somme à 1, division par la moyenne) — la normalisation,
    si elle est utile, relève de l'entraînement (E22), pas du calcul du label.
    """
    return effectif.astype("Float64")


def verifier_label(taux: pd.Series, poids: pd.Series) -> None:
    """Les garanties du label exigées par le plan d'exécution : lève `ErreurLabel` sinon.

    - `taux` dans [0, 1] pour toute valeur renseignée (les valeurs manquantes
      sont tolérées ici : c'est `base_exploitable`, en amont, qui décide
      qu'une cellule sans label n'entre pas dans `fait_admission`)
    - `poids` strictement positif pour toute valeur renseignée
    - aucune cellule sans poids (un effectif manquant ne peut pas produire un
      poids d'entraînement, contrairement à un taux qui peut légitimement
      être indéterminé avant filtrage)
    """
    taux_valide = taux.dropna()
    hors_bornes = (taux_valide < 0.0) | (taux_valide > BORNE_SUPERIEURE_TAUX)
    if hors_bornes.any():
        raise ErreurLabel(
            f"{int(hors_bornes.sum())} valeur(s) de taux hors de [0, {BORNE_SUPERIEURE_TAUX}]."
        )

    if poids.isna().any():
        raise ErreurLabel(f"{int(poids.isna().sum())} cellule(s) sans effectif, donc sans poids.")

    if (poids <= 0.0).any():
        raise ErreurLabel(f"{int((poids <= 0.0).sum())} poids non strictement positif(s).")
