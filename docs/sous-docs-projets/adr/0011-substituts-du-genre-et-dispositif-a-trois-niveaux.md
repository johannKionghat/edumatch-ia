# ADR 0011 — Substituts du genre mesurés et dispositif d'équité à trois niveaux

**Date** : 2026-08-29 · **Statut** : accepté

## Contexte

L'invariant du projet exclut le genre des variables du modèle et prévoit de
tester les substituts potentiels pour corrélation résiduelle. L'hypothèse de
départ, formulée avant toute mesure, désignait l'académie et l'établissement
d'origine comme substituts principaux à surveiller.

L'analyse d'équité (`notebooks/03-jgk-eda-equite-substituts.ipynb`, E11)
mesure l'information mutuelle entre six variables candidates et le sexe des
admis, **corrigée du nombre de modalités par permutation** (5 tirages,
graine 42) — une correction nécessaire : une variable à haute cardinalité
capte mécaniquement de l'information mutuelle avec n'importe quelle cible.
Résultat net, après correction : `cod_uai` 28,9 % · `fili` (filière) 19,5 % ·
`ville_etab` 10,2 % · `select_form` 5,6 % · `dep` 2,3 % · `acad_mies`
(académie) 1,4 %.

Ce résultat **infirme l'hypothèse de départ** : l'académie n'explique que
1,4 % du genre, loin d'être le principal substitut. Le deuxième substitut le
plus puissant est la **filière**, à 19,5 % — une variable indispensable au
modèle, qu'on ne peut pas retirer sans détruire sa capacité à distinguer les
formations entre elles.

## Options envisagées

1. **Retirer aussi la filière du modèle, par précaution** — écartée : la
   filière est une variable structurante de l'accessibilité (voir E10, écart
   médian de +1,1 à +42,3 points selon la filière) ; la retirer détruirait
   la capacité prédictive du modèle sur son objet même, pour un gain
   d'équité qui reste à démontrer plutôt qu'à supposer.
2. **Se fier au seul retrait des variables de genre et de ses substituts
   directs, sans audit a posteriori** — écartée : la mesure montre que
   l'exclusion ne suffit pas puisque la filière, indispensable, reconstitue
   déjà 19,5 % du genre. S'arrêter là laisserait une discrimination
   indirecte non détectée.
3. **Ajouter un audit a posteriori sur les prédictions, en plus de
   l'exclusion et de la mesure des substituts** — retenue.
4. **Ne surveiller que l'académie**, comme prévu initialement — écartée : la
   mesure la place au dernier rang des six variables testées ; s'y limiter
   aurait laissé la filière, l'établissement et la ville hors surveillance.

## Décision

Dispositif d'équité à **trois niveaux**, aucun ne suffisant seul :

1. **Exclusion à l'entrée** — le genre n'est jamais une variable du modèle,
   vérifiée par test.
2. **Mesure des substituts** — la table ci-dessus, à rejouer à chaque
   évolution notable du jeu de variables retenu en E20.
3. **Audit a posteriori sur les prédictions** (E26) — ratio d'impact
   disparate mesuré sur les sorties réelles du modèle entraîné, seule
   vérification qui porte sur ce qui compte effectivement : l'écart de
   traitement produit, pas les corrélations d'entrée.

## Conséquences

- L'audit d'équité (E26) doit être conçu pour détecter un écart de
  prédiction par sexe **même en l'absence de toute variable de genre** —
  c'est précisément le scénario que ce résultat rend probable, via la
  filière.
- La mesure de substituts doit être rejouée sur le jeu de variables
  finalement retenu en E20 (qui peut différer de celui exploré ici), avec la
  même correction de cardinalité.
- Toute mesure d'association future dans le projet (ablation E27, dérive
  E34) doit appliquer la même correction par permutation avant de comparer
  des variables de cardinalité différente — l'absence de correction avait
  ici doublé artificiellement le score de `cod_uai`.
- **Ce qui ferait reconsidérer** : si l'audit d'équité (E26) montrait un
  ratio d'impact disparate significatif porté par la filière, la décision de
  conserver la filière comme variable devrait être réexaminée en mettant en
  balance la perte de performance contre le gain d'équité mesuré — pas
  tranchée par défaut dans un sens ou dans l'autre.

**Reproduit par** : `notebooks/03-jgk-eda-equite-substituts.ipynb`, section
sur l'information mutuelle corrigée par permutation, sur
`data/raw/parcoursup/` (session 2025).
