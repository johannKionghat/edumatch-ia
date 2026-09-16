# Évaluation — protocole, baseline, entraînement, calibration

Bloc 4.3 (protocole temporel, sans fuite), 4.4 (baseline), 4.5 (métriques et
calibration), 4.6 (courbe d'apprentissage).

Sources : `notebooks/01-jgk-eda-label.ipynb`,
`notebooks/04-jgk-eda-stabilite-millesimes.ipynb`. Label :
`01-donnees/label.md`, ADR 0009. Split : ADR 0012.

## Le protocole temporel

Le numérateur du label ventilé par type de baccalauréat
(`prop_tot_{bg|bt|bp}[_brs]`) n'existe qu'à partir de la session 2020,
vérifié absent en 2018 et 2019 sur le fichier source. Le label n'est donc
calculable que sur six sessions, pas huit. Inclure 2018-2019 dans
l'entraînement aurait mis deux sessions sans cible réelle dans le jeu
d'apprentissage, ce qui viole le critère 4.2 (cible observée, pas simulée).

**Split retenu** :

| Rôle | Sessions | Cellules exploitables |
|---|---|---:|
| Entraînement | 2020-2023 | 286 463 (67 768 + 71 080 + 72 784 + 74 831) |
| Validation | 2024 | 76 408 |
| Test | 2025 | 77 159 |
| **Total exploitable** | **2020-2025** | **440 030** |

Le split est strictement temporel : aucune information postérieure à la
session d'entraînement n'y entre. C'est ce qu'on appelle une fuite de
données — utiliser, même indirectement, une information qui n'existait pas
encore au moment de la décision prédite. Ici le split est borné aux six
sessions où le label existe réellement.

## Trois réserves posées avant tout résultat

Je les écris avant l'entraînement pour qu'un résultat bon ou mauvais ne soit
pas attribué à tort au modèle alors qu'il tient à la donnée.

1. **Mentions faussées en 2020-2021.** La part de mentions très bien passe
   de 7,4 % à 11,8 % en 2020 (changement de barème d'examen), et le retour à
   la normale est lent (29,8 % de sans-mention en 2021, contre 43,4 % avant
   2020). Toute variable dérivée des mentions est contaminée pour ces deux
   sessions d'entraînement.
2. **Métriques par statut de boursier.** La part de vœux boursiers passe de
   12,5 % à 16,3 % en 2019-2020, puis retombe à 13,8 % en 2025. Les cellules
   boursières du test 2025 ne décrivent donc pas tout à fait la même
   population que celles de l'entraînement. La calibration et l'erreur sont
   rapportées séparément pour ces cellules.
3. **Dégradation attendue entre validation (2024) et test (2025), à ne pas
   imputer d'emblée au modèle.** La moyenne des taux par formation monte
   jusqu'en 2024 puis redescend en 2025 (0,522 → 0,534 → 0,522) : la cible
   elle-même n'est pas stable dans le temps. Une perte de performance sur le
   test doit d'abord être confrontée à ce mouvement avant d'être attribuée
   au modèle.

La session 2020 est conservée dans l'entraînement malgré la rupture sur les
mentions : l'anomalie porte sur des variables candidates, pas sur la cible
(tension médiane 11,8 vœux par place, alignée sur les autres sessions).
L'écarter aurait réduit le jeu d'entraînement d'un quart sans raison mesurée
sur le label.

## Ce que la distribution du label impose

Le taux d'admission par cellule n'est pas distribué normalement. Il est
étalé sur tout l'intervalle [0, 1], avec deux masses non négligeables aux
bornes :

| Cellule | Taux nul | Taux à 1 |
|---|---:|---:|
| Bac général | 1,2 % | 13,1 % |
| Bac technologique | 12,9 % | 11,8 % |
| Bac professionnel | 21,6 % (2 779 formations) | 13,1 % |

Ces masses ne sont pas du bruit : une formation très sélective qui n'admet
aucun bachelier professionnel produit un vrai zéro, une formation en tension
nulle produit un vrai un.

Conséquences pour les métriques :

- **Erreur absolue moyenne pondérée** par l'effectif de la cellule, plutôt
  qu'une erreur quadratique, moins lisible sur une cible bornée avec masses
  aux extrêmes et plus sensible aux cellules à faible effectif (déjà
  traitées par la pondération, ADR 0009).
- **La calibration doit être vérifiée explicitement.** Un modèle bien
  calibré est un modèle dont les probabilités annoncées correspondent aux
  fréquences réellement observées : s'il annonce 60 % de chances
  d'admission, environ 60 % des cellules concernées doivent effectivement
  être admises. Un modèle peut avoir une bonne erreur moyenne tout en
  plaçant mal les cas extrêmes, ceux qui intéressent le plus un candidat.
- **La comparaison entre types de bac** ne se résume pas à une moyenne
  unique : la progression bac général → technologique → professionnel est le
  cœur de l'enjeu d'équité du projet (`equite.md`).

## La baseline : le plancher mesuré avant d'entraîner

`src/edumatch/models/baseline.py` n'a aucun paramètre appris : il applique
une règle fixe et note le résultat. C'est la référence que le modèle appris
doit battre.

**Règle retenue** (`configs/base.yaml`, `taux_session_precedente`) : pour une
cellule à la session N, je prédis le taux observé de cette même cellule à la
session N-1. Elle réutilise `features.label.calculer_taux`, avec le même
bornage et le même traitement du dénominateur nul que le label lui-même.

Une baseline sans paramètre peut légitimement toucher le jeu de test parce
qu'elle n'a rien à ajuster : ce qui est interdit, c'est de comparer
plusieurs variantes d'un modèle appris sur le test et de retenir la
meilleure — ça revient à entraîner sur le test sans le dire.

### Résultat, par session

MAE pondérée par l'effectif de la cellule, sur les 440 030 cellules réelles :

| Périmètre | Couverture | MAE pondérée | MAE brute |
|---|---:|---:|---:|
| 2020 | 0 % | — | — |
| 2021 | 89,9 % | 0,0811 | 0,1434 |
| 2022 | 91,5 % | 0,0761 | 0,1381 |
| 2023 | 92,1 % | 0,0686 | 0,1387 |
| 2024 (validation) | 92,3 % | 0,0676 | 0,1364 |
| 2025 (test) | 92,9 % | 0,0654 | 0,1269 |
| validation + test | 92,6 % | **0,0664** | 0,1316 |
| validation + test, repli inclus | 100 % | **0,0713** | 0,1477 |

J'ai recalculé ces chiffres indépendamment du code livré et je retrouve les
mêmes valeurs.

**Le plancher est haut, et c'est une information sur le problème.**
Reconduire simplement le taux de l'an dernier prédit à ±6,6 points en
moyenne pondérée sur validation + test : la cible est fortement
auto-corrélée d'une session à l'autre. Une baseline difficile à battre
signifie que la marge de progression pour un modèle appris est plus étroite
qu'il n'y paraît.

Deux règles plus naïves, mesurées à côté, en fenêtre expansive (la moyenne
ne porte jamais sur la session cible ni sur une session future) :

| Règle | MAE pondérée, validation + test |
|---|---:|
| Moyenne pondérée par groupe (type de bac, boursier) | 0,2098 |
| Moyenne globale, sans distinction de groupe | 0,2124 |

Le taux de la session précédente les bat d'un facteur proche de trois : la
persistance d'une cellule porte beaucoup plus d'information que la seule
appartenance à un groupe large.

### Le seuil posé avant d'entraîner

Pour justifier d'exister, le modèle appris doit descendre nettement sous
0,0664 de MAE pondérée sur validation + test à couverture comparable
(92,6 %), et sous 0,0713 à couverture complète (100 %, repli inclus). Poser
ce seuil maintenant, avant de voir le résultat de l'entraînement, rend la
comparaison honnête.

### Deux limites déclarées

1. **La session 2020 n'est prédictible par aucune baseline temporelle**
   (couverture 0 %, vérifié par `test_premiere_session_de_la_fenetre_labellisee_n_a_aucun_score`) :
   aucune session antérieure ne porte le numérateur ventilé par type de bac.
   C'est une propriété du protocole, pas un défaut du code.
2. **Les cellules sans antécédent reçoivent un repli par moyenne de groupe**
   en fenêtre expansive, jamais une moyenne calculée sur tout
   l'entraînement (qui utiliserait des labels postérieurs à la session
   prédite). Avec ce repli la couverture passe de 92,6 % à 100 %, et la MAE
   pondérée se dégrade de 0,0664 à 0,0713 : c'est le coût exact du repli.

## L'entraînement : résultat mitigé

`src/edumatch/models/train.py` sépare la table de variables selon le split
ci-dessus, entraîne un LightGBM pondéré par l'effectif de la cellule, et
arrête ses hyperparamètres sur la seule MAE pondérée de validation — le test
2025 n'est touché qu'une fois, à la fin.

MAE pondérée, comparée au plancher à couverture égale (100 %, plancher avec
repli) :

| Périmètre | Modèle | Plancher (à couverture égale) | Verdict |
|---|---:|---:|---|
| Validation 2024 | **0,0690** | 0,0727 | le modèle passe devant |
| Test 2025 | **0,0758** | 0,0701 | le modèle reste derrière |

Le résultat est mitigé : en validation le modèle bat le plancher, en test il
perd contre une règle qui ne suppose rien. Donner le taux de la session
précédente comme variable explicite plutôt que de laisser le modèle
apprendre ce quotient seul réduit l'écart en test de moitié (de 0,0119 à
0,0057) sans le combler ; cette variable arrive première en importance de
gain, avec un gain sept fois supérieur à la deuxième. Un ensemble d'arbres
n'apprend pas naturellement un quotient — le donner explicitement confirme
en partie cette hypothèse.

Une erreur de méthode a été trouvée et corrigée dans le code : la première
mesure comparait le modèle (qui prédit les 77 159 cellules de test) à un
plancher qui n'en couvrait que 92,9 %, jugé sur son seul sous-ensemble
facile, ce qui exagérait l'écart en sa faveur. La comparaison à couverture
égale fait maintenant partie du rapport d'entraînement.

Ce qui reste n'est pas un défaut d'apprentissage, c'est un défaut de
généralisation temporelle : le modèle capte des régularités de 2020-2023 qui
ne se reconduisent pas en 2025, là où une règle qui ne suppose rien encaisse
mieux la dérive — cohérent avec la non-stationnarité de la cible déjà
observée (la moyenne des taux par formation remonte jusqu'en 2024 avant de
redescendre en 2025).

## Calibration : le modèle perd sur les deux tableaux en test

`src/edumatch/models/evaluate.py` calcule l'erreur de calibration attendue
(ECE), pondérée par l'effectif, sur 10 tranches de taux prédit. L'ECE mesure
l'écart moyen entre le taux annoncé et le taux réellement observé dans
chaque tranche : plus il est bas, mieux le modèle est calibré.

| Périmètre | ECE modèle | ECE plancher | Verdict |
|---|---:|---:|---|
| Validation 2024 | **0,0030** | 0,0141 | dix fois mieux que le plancher |
| Test 2025 | **0,0371** | 0,0322 | la calibration s'effondre, pire que le plancher |

En validation le modèle est très bien calibré. En test, il devient
sur-confiant sur toute la plage médiane : il annonce 0,55 quand la réalité
observée est 0,49. Il reste bien calibré aux extrêmes. Le modèle perd donc
sur les deux tableaux en test, précision et calibration, sans qu'aucun des
deux ne rattrape l'autre. Ventilée par filière, son erreur reste
systématiquement supérieure à celle du plancher, l'écart se creusant pour le
bac professionnel.

## Courbe d'apprentissage : ce n'est pas un manque de données

`src/edumatch/models/courbe_apprentissage.py` mesure la MAE pondérée de
validation à 10, 25, 50 et 100 % du volume d'entraînement. L'échantillonnage
est stratifié par session, pas par recul de la fenêtre temporelle, pour ne
pas mélanger l'effet du volume et celui de la proximité temporelle avec la
session cible.

| Volume | 10 % | 25 % | 50 % | 100 % |
|---|---:|---:|---:|---:|
| MAE validation | 0,0758 | 0,0723 | 0,0705 | **0,0698** |

L'écart entre entraînement et validation se referme de 0,0164 à 0,0039, et
le gain marginal se divise par deux à chaque doublement du volume (0,0035
puis 0,0018 puis 0,0007) : le modèle a déjà extrait presque tout ce que la
fenêtre 2020-2023 peut lui apprendre.

Deux chemins différents (la dégradation en test, et cette courbe) mènent à
la même conclusion : ce n'est pas un manque de données, c'est une dérive
temporelle. Plus de volume ne comblerait pas l'écart mesuré en test, et la
fenêtre labellisée est de toute façon bornée à six sessions. La réponse
relève de la surveillance de dérive et du réentraînement régulier, pas de la
collecte.

## Ce qui reste à faire

- Ablation : apport mesuré de chaque source, dont Sirene — voir
  `ablation.md` pour un obstacle déjà identifié sur la chaîne de
  nomenclatures.

---
*Mise à jour : 2026-08-30, commits `7a70366` (entraînement), `3c7d08c` (calibration et courbe d'apprentissage).*
