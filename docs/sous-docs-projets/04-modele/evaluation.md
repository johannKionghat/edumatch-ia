# Évaluation — matière établie à ce jour

Ce document sera complété en E23 (`models/evaluate.py`, MAE pondérée, courbe
de calibration, ECE). Ce qui suit est ce que l'analyse exploratoire du label
(E09) et l'analyse de stabilité inter-millésimes (E12) imposent déjà au
protocole, avant l'écriture du code d'évaluation et avant celle du split
(E22).

Sources : `notebooks/01-jgk-eda-label.ipynb`,
`notebooks/04-jgk-eda-stabilite-millesimes.ipynb`. Définition et bornage du
label : `01-donnees/label.md` et l'ADR 0009. Révision du protocole :
l'ADR 0012.

## Le protocole temporel révisé (critère 4.3)

**Le numérateur du label ventilé par type de baccalauréat n'existe qu'à
partir de la session 2020** (`prop_tot_{bg|bt|bp}[_brs]`, vérifié absent en
2018 et 2019 sur le fichier source). Le label n'est donc calculable que sur
**six sessions**, et non huit. Un protocole qui aurait inclus 2018-2019 dans
l'entraînement aurait placé deux sessions sans cible réelle dans le jeu
d'apprentissage — invalidant le critère 4.2 (cible observée, non simulée)
pour ces deux sessions.

**Split retenu** :

| Rôle | Sessions | Cellules exploitables |
|---|---|---:|
| Entraînement | 2020-2023 | 286 463 (67 768 + 71 080 + 72 784 + 74 831) |
| Validation | 2024 | 76 408 |
| Test | 2025 | 77 159 |
| **Total exploitable** | **2020-2025** | **440 030** |

Le split reste strictement temporel (invariant : aucune information
postérieure à la session d'entraînement n'y entre) — mais borné aux six
sessions où le label existe réellement, et non aux huit sessions du fichier
brut.

## Trois réserves écrites avant tout résultat de modèle

Ces réserves sont posées **avant** l'entraînement (E22), pour qu'un résultat
favorable ou défavorable ne soit pas interprété à tort comme une performance
ou une faiblesse du modèle alors qu'il tient à la donnée elle-même.

1. **Mentions écartées ou signalées pour 2020-2021.** La part de mentions
   très bien passe de 7,4 % à 11,8 % en 2020 (modification du barème
   d'examen cette année-là), et le retour à la normale est lent (encore
   29,8 % de sans-mention en 2021, contre 43,4 % avant 2020). Toute variable
   dérivée des mentions est contaminée pour ces deux sessions d'entraînement
   — à exclure, ou à signaler explicitement si conservée.
2. **Métriques ventilées par statut de boursier.** La part de vœux boursiers
   connaît une rupture en 2019-2020 (12,5 % → 16,3 %) puis retombe à 13,8 %
   en 2025 — proche du niveau d'avant 2020, mais après quatre sessions de
   stabilité à 16,3 %. Les cellules `_brs` du jeu de test 2025 ne décrivent
   donc pas tout à fait la même population que celles de l'entraînement
   2020-2023. Une métrique agrégée masquerait cet écart : la calibration et
   l'erreur doivent être rapportées séparément pour les cellules boursières.
3. **Dégradation attendue entre validation (2024) et test (2025), à ne pas
   imputer d'emblée au modèle.** Le taux agrégé baisse d'une session à
   l'autre pendant que la moyenne des taux par formation continue de monter
   jusqu'en 2024 avant de refléchir en 2025 (0,522 → 0,534 → 0,522, mesuré
   sur trois sessions) — la cible elle-même n'est pas stationnaire (E12). Une
   perte de performance sur le test doit d'abord être confrontée à ce
   mouvement de la cible avant d'être attribuée à un défaut du modèle.

**La session 2020 est conservée dans l'entraînement**, malgré la rupture sur
les mentions : l'anomalie porte sur des variables candidates, pas sur la
cible elle-même (tension médiane 11,8 vœux par place, alignée sur les autres
sessions ; masses aux bornes du label dans la norme observée les autres
années). L'écarter aurait réduit le jeu d'entraînement d'un quart sans
fondement mesuré sur le label.

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
*Mise à jour : 2026-08-29, commit `be2787c`.*
