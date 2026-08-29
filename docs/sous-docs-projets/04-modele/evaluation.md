# Évaluation — matière établie à ce jour

Ce document sera complété en E23 (`models/evaluate.py`, MAE pondérée, courbe
de calibration, ECE). Ce qui suit est ce que l'analyse exploratoire du label
(E09) impose déjà au protocole, avant l'écriture du code d'évaluation.

Source : `notebooks/01-jgk-eda-label.ipynb`. Définition et bornage du label :
`01-donnees/label.md` et l'ADR 0009.

## Ce que la distribution du label impose

Le taux d'admission par cellule, une fois borné à 1, n'est pas distribué
normalement. Il est étalé sur tout l'intervalle [0, 1], avec deux masses non
négligeables aux bornes :

| Cellule | Taux nul | Taux à 1 |
|---|---:|---:|
| Bac général | 1,2 % | 13,1 % |
| Bac technologique | 12,9 % | 11,8 % |
| Bac professionnel | 21,6 % (2 779 formations) | 13,1 % |

Ces masses ne sont pas du bruit à lisser : une formation très sélective qui
n'admet aucun bachelier professionnel produit un vrai zéro, une formation en
tension nulle qui accepte tous les vœux produit un vrai un. Le décalage entre
moyenne et médiane (0,522 contre 0,498 pour le bac général, l'écart se creusant
pour le professionnel) confirme l'asymétrie.

## Conséquences pour le choix des métriques

- **Erreur absolue moyenne pondérée** par l'effectif de la cellule, plutôt
  qu'une erreur quadratique. Une cible bornée avec masses aux extrêmes rend
  l'erreur quadratique moins lisible et plus sensible aux cellules à faible
  effectif, déjà traitées par la pondération (ADR 0009) plutôt que par
  exclusion.
- **La calibration doit être vérifiée explicitement**, pas seulement
  l'erreur moyenne. Un modèle peut afficher une bonne erreur moyenne tout en
  plaçant mal les valeurs extrêmes — précisément celles qui intéressent un
  candidat qui veut savoir s'il a une chance réelle ou aucune.
- **La comparaison entre types de bac ne se résume pas à une moyenne unique**
  par filière : la progression bac général → technologique → professionnel
  est le cœur de l'enjeu d'équité du projet (E26), à quantifier avant de
  conclure sur le modèle.

## Ce qui reste à faire (E21 à E24)

- Baseline : taux de la session précédente (E21), à mesurer avant tout
  entraînement — c'est le plancher de comparaison.
- Split temporel strict, sans fuite (E22).
- MAE pondérée, courbe de calibration, ECE (E23).
- Courbe d'apprentissage à 10/25/50/100 % du volume (E24).

---
*Mise à jour : 2026-08-29, commit `7bcd5ef`.*
