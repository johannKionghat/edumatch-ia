# ADR 0012 — Révision du protocole d'évaluation : six sessions exploitables, conservation de 2020

Statut : accepté (2026-08-29) · remplace la répartition temporelle
(entraînement 2018-2023) envisagée avant l'analyse de stabilité

## Contexte

L'analyse de stabilité inter-millésimes
(`04-jgk-eda-stabilite-millesimes.ipynb`, E12) établit que le numérateur du
label ventilé par type de baccalauréat (`prop_tot_{bg|bt|bp}[_brs]`) n'existe
qu'à partir de la session 2020. Le label n'est donc calculable que sur six
sessions (2020-2025), pas huit. La répartition envisagée jusqu'ici
(entraînement 2018-2023) aurait placé deux sessions sans cible réelle dans le
jeu d'entraînement, en violation du critère 4.2 (cible observée, non
simulée). Le volume exploitable réel est de 440 030 cellules sur 2020-2025
(67 768 · 71 080 · 72 784 · 74 831 · 76 408 · 77 159), contre 560 000 à
625 000 annoncés en supposant huit sessions. Deux ruptures de série
affectent par ailleurs des variables candidates sur cette période, sans
toucher le label : les mentions au baccalauréat (2020, barème modifié) et la
part de vœux boursiers (rupture 2019-2020, retour proche du niveau antérieur
en 2025).

## Décision

Split entraînement 2020-2023 (286 463 cellules), validation 2024 (76 408),
test 2025 (77 159). 2020 est conservée dans l'entraînement, avec les
variables dérivées des mentions écartées ou signalées comme contaminées pour
2020 et 2021. Trois réserves écrites avant tout résultat de modèle
(détaillées dans `04-modele/evaluation.md`) : mentions contaminées
2020-2021, métriques ventilées par statut boursier à interpréter avec
prudence, dégradation attendue entre validation et test à ne pas imputer
d'emblée au modèle.

## Alternatives écartées

- Maintenir 2018-2023 en tolérant l'absence de cible sur 2018-2019 : viole
  le critère 4.2.
- Construire un label de substitution pour 2018-2019 à partir de `acc_bg` :
  `acc` mesure l'acceptation, pas l'admission (même raison qu'à l'ADR 0009).
- Écarter aussi 2020 de l'entraînement en raison de la rupture sur les
  mentions : vérifié après coup, l'anomalie porte sur des variables dérivées
  des mentions, pas sur la cible elle-même (tension médiane et masses aux
  bornes alignées sur les autres sessions). Écarter 2020 aurait réduit
  l'entraînement d'un quart sans fondement mesuré.

## Conséquences

Le volume d'entraînement (286 463 cellules) est inférieur à ce qu'aurait
donné huit sessions, mais chaque cellule utilisée porte une cible réellement
observée. La cible n'est pas stationnaire : le taux agrégé baisse de 40,5 %
à 36,7 % entre 2020 et 2025 pendant que la moyenne des taux par formation
monte de 0,491 à 0,522. Le suivi de dérive (E34) doit utiliser la même
définition que celle apprise par le modèle — la moyenne par formation — sous
peine de conclure à l'inverse de la réalité. Toute documentation citant
« huit sessions » pour le volume du label doit être corrigée vers six ; le
fichier Parcoursup brut, lui, couvre bien huit sessions.

Je reviendrais sur ce split si un export rétrospectif de Parcoursup
publiait un jour le numérateur ventilé par type de bac pour 2018-2019.

Reproduit par `notebooks/04-jgk-eda-stabilite-millesimes.ipynb`, sur
`data/raw/parcoursup/` (tous millésimes).
