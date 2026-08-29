# ADR 0012 — Révision du protocole d'évaluation : six sessions exploitables, conservation de 2020

**Date** : 2026-08-29 · **Statut** : accepté · remplace la répartition
temporelle (entraînement 2018-2023) évoquée avant l'analyse de stabilité

## Contexte

L'analyse de stabilité inter-millésimes
(`notebooks/04-jgk-eda-stabilite-millesimes.ipynb`, E12) établit que le
numérateur du label ventilé par type de baccalauréat
(`prop_tot_{bg|bt|bp}[_brs]`) n'existe qu'à partir de la session 2020. Le
label, tel que défini en E09 et l'ADR 0009, n'est donc calculable que sur
**six sessions (2020-2025)**, pas huit. La répartition temporelle envisagée
jusqu'ici (entraînement 2018-2023) aurait placé deux sessions sans cible
réelle dans le jeu d'entraînement — une violation directe du critère 4.2
(cible observée, non simulée) pour ces deux sessions.

Le volume exploitable réel est de **440 030 cellules** sur 2020-2025
(67 768 · 71 080 · 72 784 · 74 831 · 76 408 · 77 159), contre 560 000 à
625 000 annoncés en supposant huit sessions utilisables.

Deux ruptures de série affectent par ailleurs les variables candidates sur
cette période, sans affecter le label lui-même : les mentions au
baccalauréat (2020, barème d'examen modifié) et la part de vœux boursiers
(rupture en 2019-2020, puis retour proche du niveau antérieur en 2025).

## Options envisagées

1. **Maintenir 2018-2023 en entraînement en tolérant l'absence de cible sur
   2018-2019** — écartée : viole le critère 4.2, une cible absente ne peut
   pas être remplacée par une valeur simulée ou par un proxy non documenté.
2. **Construire un label de substitution pour 2018-2019 à partir de
   `acc_bg`** (candidats inscrits) — écartée : `acc` compte l'acceptation, pas
   l'admission (voir ADR 0009, option écartée pour la même raison sur toutes
   les sessions) ; un label composite selon la disponibilité de la donnée
   serait incohérent avec lui-même d'une session à l'autre.
3. **Restreindre l'entraînement aux six sessions où le label existe
   (2020-2025), avec un split temporel classique 4 / 1 / 1** — retenue :
   entraînement 2020-2023, validation 2024, test 2025.
4. **Écarter également 2020 de l'entraînement**, en raison de la rupture sur
   les mentions — écartée après vérification : l'anomalie porte sur des
   variables candidates dérivées des mentions, pas sur la cible (tension
   médiane et masses aux bornes du label alignées sur les autres sessions).
   Écarter 2020 aurait réduit l'entraînement d'un quart sans fondement
   mesuré sur le label lui-même.
5. **Écarter 2020 pour les seules variables de mention, en la conservant
   pour le reste** — retenue, en corollaire de l'option 3.

## Décision

- **Split** : entraînement 2020-2023 (286 463 cellules), validation 2024
  (76 408), test 2025 (77 159).
- **2020 est conservée** dans l'entraînement, avec les variables dérivées
  des mentions écartées ou explicitement signalées comme contaminées pour
  2020 et 2021.
- **Trois réserves écrites** avant tout résultat de modèle, détaillées dans
  `04-modele/evaluation.md` : mentions contaminées 2020-2021, métriques
  ventilées par statut boursier (rupture 2019-2020 puis 2025), dégradation
  attendue entre validation et test à ne pas imputer d'emblée au modèle (la
  cible elle-même n'est pas stationnaire, voir plus bas).

## Conséquences

- Le volume d'entraînement disponible (286 463 cellules) est inférieur à ce
  qu'aurait donné huit sessions, mais chaque cellule utilisée porte une
  cible réellement observée — c'est la condition du critère 4.2, non
  négociable même au prix du volume.
- La cible n'est pas stationnaire dans le temps : le taux agrégé baisse de
  40,5 % à 36,7 % entre 2020 et 2025 pendant que la moyenne des taux par
  formation monte de 0,491 à 0,522 (le catalogue s'élargit de formations
  plus petites et moins tendues). Un suivi de dérive du modèle (E34) doit
  utiliser la même définition que celle apprise par le modèle — la moyenne
  par formation — sous peine de conclure à l'inverse de la réalité.
- Toute documentation ou communication future citant « huit sessions » pour
  le volume du label doit être corrigée vers six ; le fichier Parcoursup
  brut, lui, couvre bien huit sessions (E03, E05) — la distinction entre
  volume brut et volume exploitable pour le label doit être maintenue
  explicitement partout où le chiffre est cité.
- **Ce qui ferait reconsidérer** : si un export rétrospectif de Parcoursup
  publiait un jour le numérateur ventilé par type de bac pour 2018-2019 (peu
  probable, l'absence tient au format de publication de ces deux
  millésimes), le split pourrait être étendu en conséquence.

**Reproduit par** : `notebooks/04-jgk-eda-stabilite-millesimes.ipynb`,
sections sur la disponibilité du numérateur par session et sur les ruptures
de série, sur `data/raw/parcoursup/` (tous millésimes).
