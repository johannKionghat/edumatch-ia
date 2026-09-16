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

## La baseline (E21) : le plancher mesuré avant d'entraîner

`src/edumatch/models/baseline.py` ne contient aucun paramètre appris : il
applique une règle fixe à la table de variables produite en E20 et note le
résultat. C'est la référence à laquelle le modèle appris (E22-E23) devra se
comparer.

**La règle retenue par `configs/base.yaml`** (`taux_session_precedente`) :
pour une cellule `(formation, type de baccalauréat, boursier)` à la session
N, je prédis le taux observé de cette même cellule à la session N-1. Elle
réutilise `features.label.calculer_taux` — même bornage à 1, même traitement
du dénominateur nul — pour que la baseline et la cible qu'elle prédit soient
définies de façon rigoureusement identique.

**Pourquoi une baseline sans paramètre peut légitimement toucher le jeu de
test.** La règle qui interdit de regarder deux fois le test protège contre
l'ajustement implicite : comparer plusieurs variantes d'un modèle appris sur
le test, puis retenir la meilleure, revient à entraîner sur le test sans le
dire. Une règle qui n'a rien à ajuster n'a rien à sur-ajuster — son score sur
le test est précisément le chiffre que le modèle appris devra battre à la
fin, et le mesurer maintenant plutôt qu'après coup rend la comparaison
honnête. Ce qui resterait interdit : comparer ici plusieurs variantes du
futur modèle LightGBM sur ce même jeu de test pour en choisir une.

### Résultat, par session et par périmètre agrégé

MAE pondérée par l'effectif de la cellule (ADR 0009), mesurée sur les
440 030 cellules réelles (E20) :

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
mêmes valeurs — c'est cette double vérification, et non la seule lecture du
code, qui rend le chiffre défendable.

**Le plancher est haut, et c'est une information sur le problème, pas un
embarras.** Reconduire simplement le taux de l'an dernier prédit à ±6,6
points en moyenne pondérée sur validation + test : la cible est fortement
auto-corrélée d'une session à l'autre. Une baseline difficile à battre
signifie que le signal utile qu'un modèle appris peut ajouter est plus étroit
qu'il n'y paraît — c'est précisément ce que l'étape suivante doit mesurer
honnêtement plutôt que suggérer implicitement qu'un modèle appris fait
toujours mieux qu'une règle simple.

### Le plancher retenu est le meilleur de trois règles triviales, pas la première venue

Deux règles plus naïves, mesurées à côté, toutes deux en fenêtre expansive
(la moyenne ne porte jamais sur la session cible ni sur une session future,
même exigence anti-fuite que le split lui-même, ADR 0012) :

| Règle | MAE pondérée, validation + test |
|---|---:|
| Moyenne pondérée par groupe `(type de bac, boursier)` | 0,2098 |
| Moyenne globale, sans distinction de groupe | 0,2124 |

Le taux de la session précédente les bat d'un facteur proche de trois : la
persistance d'une cellule à l'autre porte beaucoup plus d'information que la
seule appartenance à un groupe large. C'est ce comparatif, et non la seule
intuition que « l'an dernier » est une bonne référence, qui justifie de
retenir cette règle comme plancher officiel.

### Le seuil posé avant d'entraîner

Pour justifier d'exister, le modèle appris (E22-E23) doit descendre
**nettement sous 0,0664** de MAE pondérée sur le périmètre validation + test
à couverture comparable (92,6 %), et sous **0,0713** à couverture complète
(100 %, repli inclus). Poser ce seuil maintenant, avant de voir le résultat
de l'entraînement, est ce qui rend la comparaison à venir honnête : un seuil
choisi après coup se plie toujours au résultat qu'on veut montrer.

### Deux limites déclarées, mesurées plutôt que masquées

1. **La session 2020 n'est prédictible par aucune baseline temporelle.**
   Couverture nulle, mesurée et vérifiée par un test dédié
   (`test_premiere_session_de_la_fenetre_labellisee_n_a_aucun_score`) :
   aucune session antérieure ne porte le numérateur du label ventilé par
   type de baccalauréat (ADR 0012). Ce n'est pas un défaut du code, c'est une
   propriété du protocole temporel lui-même.
2. **Les cellules sans antécédent reçoivent un repli par moyenne de groupe
   en fenêtre expansive** — jamais une moyenne calculée sur tout
   l'entraînement, qui aurait utilisé des labels postérieurs à la session
   prédite. Le score est donné avec et sans ce repli (lignes « validation +
   test » et « validation + test, repli inclus » du tableau ci-dessus) :
   la couverture passe de 92,6 % à 100 %, et la MAE pondérée se dégrade de
   0,0664 à 0,0713, ce qui chiffre exactement le coût du repli plutôt que de
   le laisser implicite.

## E22 — l'entraînement, résultat mitigé et rapporté tel quel

`src/edumatch/models/train.py` sépare la table de variables (E20) selon le
split ci-dessus, entraîne un LightGBM pondéré par l'effectif de la cellule
(ADR 0009), et arrête ses hyperparamètres sur la seule MAE pondérée de
validation — le test 2025 n'est touché qu'une fois, à la fin, avec les
hyperparamètres déjà figés.

MAE pondérée, comparée au plancher **à couverture égale** (100 % des
cellules, plancher avec repli de l'E21) :

| Périmètre | Modèle | Plancher (E21, à couverture égale) | Verdict |
|---|---:|---:|---|
| Validation 2024 | **0,0690** | 0,0727 | le modèle passe devant |
| Test 2025 | **0,0758** | 0,0701 | le modèle reste derrière |

Le résultat est mitigé et se lit comme tel : en validation le modèle bat le
plancher, en test il perd contre une règle qui ne suppose rien. Donner le
taux de la session précédente comme variable explicite plutôt que comme seul
concurrent réduit l'écart en test de moitié (0,0119 à 0,0057) sans le
combler — cette variable arrive première en importance de gain, avec un gain
sept fois supérieur à la deuxième. L'hypothèse testée était qu'un ensemble
d'arbres n'apprend pas nativement un quotient ; la donner explicitement le
confirme en partie.

**Une erreur de méthode a été trouvée et corrigée dans le code, pas
seulement commentée.** La première mesure comparait le modèle — qui prédit
les 77 159 cellules de test — à un plancher qui n'en couvrait que 92,9 %,
jugé sur son seul sous-ensemble facile, ce qui exagérait l'écart en sa
faveur. La comparaison à couverture égale fait désormais partie du rapport
d'entraînement produit par `train.py`, et les chiffres du plancher sont
réenregistrés à chaque exécution : refaire cette erreur suppose de la voir.

**Ce qui reste n'est pas un défaut d'apprentissage, c'est un défaut de
généralisation temporelle** : le modèle capte des régularités de 2020-2023
qui ne se reconduisent pas en 2025, là où une règle qui ne suppose rien
encaisse mieux la dérive — cohérent avec la non-stationnarité de la cible
déjà mesurée en E12 (la moyenne des taux par formation remonte jusqu'en 2024
avant de refléchir en 2025).

## E23 — calibration : le modèle perd sur les deux tableaux en test

`src/edumatch/models/evaluate.py` calcule l'erreur de calibration attendue
(ECE), pondérée par l'effectif, sur 10 tranches de taux prédit
(`modele.n_tranches_calibration`).

| Périmètre | ECE modèle | ECE plancher | Verdict |
|---|---:|---:|---|
| Validation 2024 | **0,0030** | 0,0141 | dix fois mieux que le plancher |
| Test 2025 | **0,0371** | 0,0322 | la calibration s'effondre, pire que le plancher |

En validation le modèle est remarquablement bien calibré. En test, il
devient sur-confiant sur toute la plage médiane des probabilités : il annonce
0,55 quand la réalité observée est 0,49. Il reste bien calibré aux extrêmes.
**Le modèle perd donc sur les deux tableaux en test, précision et
calibration, sans qu'aucun des deux ne rattrape l'autre.** Ventilée par
filière, son erreur reste systématiquement supérieure à celle du plancher,
l'écart se creusant pour le bac professionnel.

## E24 — courbe d'apprentissage : ce n'est pas un manque de données

`src/edumatch/models/courbe_apprentissage.py` mesure la MAE pondérée de
validation à 10, 25, 50 et 100 % du volume d'entraînement. L'échantillonnage
est stratifié **par session**, pas par recul de la fenêtre temporelle — pour
ne pas mélanger l'effet du volume disponible et celui de la proximité
temporelle avec la session cible, deux causes que la question posée par
cette étape doit distinguer.

| Volume | 10 % | 25 % | 50 % | 100 % |
|---|---:|---:|---:|---:|
| MAE validation | 0,0758 | 0,0723 | 0,0705 | **0,0698** |

L'écart entre entraînement et validation se referme de 0,0164 à 0,0039, et le
gain marginal se divise par deux à chaque doublement du volume (0,0035 puis
0,0018 puis 0,0007) : le modèle a déjà extrait presque tout ce que la fenêtre
2020-2023 peut lui apprendre.

**Conclusion convergente, établie deux fois par deux chemins différents**
(la dégradation en test d'un côté, la courbe d'apprentissage de l'autre) :
ce n'est pas un manque de données, c'est une dérive temporelle. Chercher plus
de volume ne comblerait pas l'écart mesuré en test, et la fenêtre labellisée
est de toute façon bornée à six sessions (ADR 0012). La réponse relève de la
surveillance de dérive et du réentraînement régulier (E33-E34), pas de la
collecte.

## Ce qui reste à faire (E27)

- Ablation : apport mesuré de chaque source, dont Sirene — voir
  `reste-a-faire.md` pour un obstacle déjà identifié sur la chaîne de
  nomenclatures.

---
*Mise à jour : 2026-08-30, commits `7a70366` (E22), `3c7d08c` (E23-E24).*
