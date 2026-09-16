# Ablation — apport mesuré de chaque source

Bloc 4.16. Ce document mesure ce que chaque bloc de variables apporte
réellement au modèle retenu, plutôt que de le supposer, et déclare la seule
mesure que je ne peux pas encore faire : l'apport de Sirene.

Source : `src/edumatch/models/ablation.py`. Le raisonnement complet est
porté par le corps du commit `dc5eadc` ; ce document le reprend sous une
forme consultable.

## Le protocole

Sept variantes, entraînées avec exactement les mêmes hyperparamètres et le
même split que la configuration de production (`configs/base.yaml`,
`modele.hyperparametres`, ADR 0012 pour le split). Seule la composition du
jeu de variables change d'une variante à l'autre.

Chaque variante est jugée sur la validation 2024, jamais sur le test 2025 :
comparer des configurations sur le jeu de test transformerait ce choix en
réglage d'hyperparamètre déguisé, ce que le protocole interdit. Le test
n'est consulté qu'une fois, pour la configuration déjà retenue en production
— son score est rapporté tel quel, jamais recalculé ici.

Pour la même raison, la comparaison d'équité entre le modèle complet et la
variante sans les substituts du genre porte elle aussi sur la validation
2024, et non sur le test 2025 déjà consulté par l'audit de production
(`equite.md`) : un second passage sur ce jeu, pour une question différente,
reste un second passage.

Le genre n'entre dans aucune des sept variantes comme variable d'entrée. Le
retrait des substituts (`fili`, `select_form`, `dep`, `acad_mies`) est un
retrait de variables licites du modèle ; le genre lui-même n'est lu, comme
dans l'audit d'équité, que depuis la table silver, pour classer la
composition des formations et juger l'équité a posteriori.

## Résultats — sept variantes, MAE pondérée de validation

| Variante | Variables | MAE validation | Écart | ECE |
|---|---:|---:|---:|---:|
| modèle complet (référence) | 48 | 0,0698 | 0,0000 | 0,0038 |
| sans les décalées | 11 | 0,1120 | **+0,0422** | 0,0196 |
| sans le taux précédent | 46 | 0,0793 | +0,0095 | 0,0109 |
| taux précédent seul | 3 | 0,0768 | +0,0071 | 0,0088 |
| mentions incluses | 56 | 0,0695 | −0,0003 | 0,0038 |
| `cod_uai` réintroduit | 49 | 0,0699 | +0,0001 | 0,0029 |
| sans les substituts du genre | 44 | 0,0704 | +0,0006 | 0,0049 |

Score de test de la configuration retenue, rapporté et non recalculé : MAE
pondérée 0,0758 (n = 77 159) — valeur enregistrée par le registre
d'expériences, 0,075755 avant arrondi, identique à celle des autres pages du
dossier.

## Premier résultat : l'essentiel de la performance vient du signal N-1

Retirer les 35 variables décalées, et `taux_session_precedente` qui en
dépend, fait passer la MAE pondérée de validation de 0,0698 à 0,1120, soit
+0,0422. C'est de très loin le retrait le plus coûteux.

À l'inverse, passer de 3 variables (les deux dimensions de cellule et
`taux_session_precedente` seul) au jeu complet de 48 ne gagne que 0,0070,
soit environ 9 % relatif de l'erreur du modèle réduit.

L'essentiel de la performance vient de connaître le taux d'admission de
l'an dernier sur la même cellule. Les 45 autres variables affinent la
prédiction, elles ne la portent pas. La différence entre le retrait de
`taux_session_precedente` seul (+0,0095, coût du quotient donné en clair
plutôt qu'à reconstituer depuis son numérateur et son dénominateur bruts) et
le retrait de l'ensemble des décalées (+0,0422, coût du signal N-1 dans son
entier) confirme la lecture : ce n'est pas la mise en forme du quotient qui
porte le modèle, c'est la disponibilité du signal lui-même.

Ce résultat change la lecture du critère 4.16 : le modèle est en grande
partie une règle de persistance affinée par le catalogue, pas 48 signaux
équivalents.

## Deuxième résultat : retirer les substituts du genre ne répare pas l'équité

Retirer les quatre substituts du genre encore présents dans le modèle
(`fili`, `select_form`, `dep`, `acad_mies`, qui totalisent 14,2 % de
l'explication SHAP globale, voir `explicabilite.md`) coûte +0,0006 de MAE
pondérée en validation, un coût quasi nul.

Ce retrait ne rend pas le modèle plus équitable. Sur la validation 2024, le
ratio d'impact disparate du groupe de formations à plus de 80 % de
candidates femmes passe de 0,66 à 0,62 en retirant les substituts — il se
dégrade légèrement, sans franchir le seuil des quatre cinquièmes dans un
sens ou dans l'autre. Les deux autres groupes mesurés restent stables :
mixte 0,82 → 0,83, minoritaire 1,00 → 1,00.

Ce résultat est contre-intuitif et rapporté tel quel : retirer une variable
corrélée au genre aggrave ici, très légèrement, l'écart plutôt que de le
réduire. L'explication tient à ce que l'ADR 0013 avait déjà anticipé au
sujet de `cod_uai` : l'information qui permet au modèle de reconstituer le
genre n'est pas concentrée dans ces quatre colonnes de catalogue, elle est
diffuse dans les variables décalées attachées à la même formation — celles
qui portent l'essentiel du signal. Retirer quatre colonnes ne retire pas ce
canal diffus.

L'exclusion de variables ne peut donc pas être le seul levier d'équité du
projet. Ce résultat conforte le choix déjà fait de fonder l'équité sur la
calibration par groupe, mesurée a posteriori sur les prédictions, plutôt que
sur la seule composition du jeu de variables en entrée. Il vient compléter,
sans le recouvrir, le résultat déjà rapporté sur le test 2025 dans
`equite.md` (ratio d'impact disparate à 0,76 pour le modèle complet, mesuré
sur le périmètre de production) : les deux mesures portent sur des jeux et
des comparaisons différents et ne doivent pas être confondues.

## Troisième résultat : les deux exclusions de l'ADR 0013 sont confirmées

L'ADR 0013 fixait, pour chacune, un seuil de reconsidération.

**Mentions** (`acc_sansmention`, `acc_ab`, `acc_b`, `acc_tb`, etc., écartées
par défaut à cause de la contamination du baccalauréat en contrôle continu
2020-2021) : les réintroduire apporte un gain de 0,0003 sur la validation.
Le seuil de reconsidération de l'ADR est un gain supérieur à 0,01 — non
franchi, exclusion confirmée.

**`cod_uai`** (exclu pour cardinalité et pour être le plus fort substitut du
genre mesuré, 28,9 % net) : le réintroduire dégrade légèrement la MAE
pondérée de validation, +0,0001. Le seuil de reconsidération de l'ADR est
une perte mesurée à l'exclure — c'est l'inverse qui est mesuré : aucune
perte n'est constatée à l'exclure, donc l'exclusion reste confirmée.

Les deux arbitrages traversent l'ablation sans être ébranlés.

## Sirene — ce qui ne peut pas être mesuré aujourd'hui

Le plan d'exécution du projet prévoyait de mesurer l'apport de Sirene par
ablation, au même titre que les autres blocs de variables. Ce n'est pas
possible en l'état : la chaîne de nomenclatures NAF ↔ ROME ↔ formation ne
relie aucune formation Parcoursup — vérifié sur les huit millésimes, aucun
ne porte de code RNCP, NSF ou ROME exploitable par cette chaîne
(`referentiel/naf_rome_formation.py`, `manques_declares`).

Sirene n'a donc jamais eu l'occasion d'entrer dans la table de variables ni
dans le modèle entraîné. Il n'existe, à ce jour, rien à retirer d'un modèle
où cette source n'est pas entrée.

Un écart nul mesuré serait un résultat, comme ceux qu'ont produit les
mentions ou `cod_uai` ci-dessus. Une ablation impossible à réaliser est une
limite du dispositif, pas un résultat sur l'apport de la source : le
critère 4.16 demande l'apport de chaque source mesuré, et pour Sirene cette
mesure reste à faire, conditionnée au rattachement effectif de la chaîne de
nomenclatures. Ce point reste ouvert.

## Ce que je n'ai pas fait

- Je n'ai pas rejoué la comparaison d'équité substituts du genre sur le test
  2025 : elle reste, par construction du protocole, cantonnée à la
  validation pour ne pas consommer une seconde fois le jeu déjà audité.
- Je n'ai pas cherché d'autre variante que les sept prescrites par l'ADR
  0013 et par les résultats d'explicabilité et d'équité (mentions,
  `cod_uai`, décalées, taux précédent seul et sans, substituts du genre).
  Une ablation plus fine, colonne par colonne parmi les décalées, n'a pas
  été conduite : le résultat dominant (le bloc des décalées porte
  l'essentiel de la performance) rend cette décomposition secondaire à ce
  stade.
- Je n'ai pas mesuré l'apport de Sirene, pour la raison exposée ci-dessus.

---
*Mise à jour : 2026-08-31, commit `dc5eadc`.*
