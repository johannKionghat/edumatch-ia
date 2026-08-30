# Le label — définition et calcul de la cible

**Critère du Bloc 4 concerné (4.2)** : la cible doit être définie, observée et
non simulée. Ce document expose la définition retenue, les trois alternatives
écartées, et ce que la distribution observée impose au protocole d'évaluation.

Analyse produite dans `notebooks/01-jgk-eda-label.ipynb`, sur le fichier
Parcoursup 2025 (`data/raw/parcoursup/`). Figure exportée dans
`reports/figures/e09-distribution-taux-admission.png`.

## Le grain de l'analyse

Une ligne du fichier Parcoursup est une formation, identifiée par
`cod_aff_form`, pour une session donnée. Clé vérifiée sans doublon ni valeur
manquante : 14 252 valeurs distinctes pour 14 252 lignes en 2025.
`cod_uai` (l'établissement) ne suffit pas à identifier une formation : 4 058
établissements pour 14 252 formations, un même établissement en proposant
plusieurs.

Empilés sur les huit millésimes, la clé devient `(session, cod_aff_form)`.

## Définition du label

Le label est un taux d'admission observé, calculé par cellule
`(formation × session × type de bac × boursier)` :

```
taux = prop_tot_{bg|bt|bp}[_brs] / nb_voe_pp_{bg|bt|bp}[_brs]
```

Six cellules possibles par formation et par session : bac général, technologique
et professionnel, chacun avec ou sans la restriction aux boursiers. Le nombre de
cellules exploitables décroît selon le profil : 96,0 % des formations ont une
cellule « bac général », 83,6 % seulement une cellule « bac professionnel
boursier ». Les six cellules ne couvrent donc pas la même population, et une
comparaison directe entre elles demande de la prudence.

**77 159 cellules pour la session 2025.**

⚠️ **Correction (E12, `notebooks/04-jgk-eda-stabilite-millesimes.ipynb`)** :
le numérateur `prop_tot_*` n'est ventilé par type de baccalauréat qu'à partir
de la session 2020. Le label tel que défini ci-dessus n'est donc calculable
que sur **six sessions (2020-2025), pas huit** — 2018 et 2019 n'ont pas de
cible exploitable. Le total exploitable est de **440 030 cellules**
(67 768 · 71 080 · 72 784 · 74 831 · 76 408 · 77 159 selon la session), et non
560 000 à 625 000 comme annoncé en supposant huit sessions utilisables. Détail
et conséquences pour le split d'entraînement : `04-modele/evaluation.md` et
l'ADR 0012.

## Les deux alternatives écartées, et pourquoi

### `acc / nb_voe_pp` — écartée malgré sa commodité

Cette définition ne dépasse jamais 1 (3 cellules sur 13 685, contre 1 219 pour
la définition retenue). Elle réglerait le problème de bornage d'un trait.

Je l'écarte pourtant. `acc` compte les candidats qui ont **accepté** la
proposition et se sont inscrits, pas ceux qui ont été admis. Un lycéen qui
reçoit une proposition et la décline parce qu'il a mieux ailleurs a bel et bien
été admis. Retenir `acc` reviendrait à mesurer un mélange entre la sélectivité
de la formation et les préférences des candidats : une formation facile
d'accès mais peu désirée obtiendrait un score bas alors qu'elle est accessible.
Le système promet une réponse à « quelles sont mes chances d'être admis »,
pas à « vais-je m'y inscrire ».

### Dénominateur `nb_cla_pp` (classés) au lieu de `nb_voe_pp` (vœux) — écartée

Change la population de référence sans changer la nature du problème de
bornage (le numérateur reste des propositions émises, y compris réémises). Ne
résout rien et complique l'interprétation : le vœu est l'unité qui correspond
à la question posée au candidat au moment de la formulation de son vœu.

## Le dépassement de 1 est structurel, pas un artefact de petits effectifs

**Le label dépasse 1 dans 8,9 % des cellules bac général (1 219 sur 13 685).**
Ce dépassement ne disparaît pas quand les petites cellules sont écartées :
à 100 vœux minimum, 483 cellules sur 7 154 dépassent encore 1.

L'explication tient à ce que comptent réellement les deux termes.
`nb_voe_pp` compte des **vœux**, c'est-à-dire des candidats. `prop_tot` compte
des **propositions émises**, c'est-à-dire des événements : une formation de
100 places émet davantage que 100 propositions au fil de la campagne, puisque
chaque désistement libère une place et déclenche une nouvelle proposition.
Numérateur et dénominateur ne décrivent donc pas la même population.

**Borner à 1 n'est pas une correction de valeurs aberrantes, c'est l'imposition
d'une borne sémantique** à un rapport qui n'est pas un taux au sens strict.
C'est défendable, à condition de le dire ainsi — et de documenter la borne, ce
qui n'était pas fait jusqu'ici (voir l'encadré ci-dessous).

## ⚠️ Une décision de calcul rendue explicite

La moyenne de 0,522 retenue jusqu'ici pour le bac général correspond
**exactement** à la moyenne calculée sur le taux **borné à 1**. La moyenne
brute, sans bornage, vaut 0,545. La borne était donc déjà appliquée dans le
calcul qui a produit 0,522, sans être écrite nulle part — ni dans le code, ni
dans la documentation. Le chiffre n'était pas faux, mais sa provenance exacte
n'était pas vérifiable sans relire le calcul source. Le bornage est désormais
une décision écrite (ADR 0009), et non un effet de bord d'un calcul non
documenté.

## Distribution observée — session 2025

| Cellule | Moyenne | Médiane | Taux nul | Taux à 1 |
|---|---:|---:|---:|---:|
| Bac général | 0,522 | 0,498 | 1,2 % | 13,1 % |
| Bac technologique | 0,433 | 0,381 | 12,9 % | 11,8 % |
| Bac professionnel | 0,405 | 0,333 | **21,6 % (2 779 formations)** | 13,1 % |

Reproduit par la cellule de calcul du carnet, sur `df_2025` filtré aux cellules
à dénominateur non nul.

La distribution n'est pas gaussienne : elle est étalée sur tout l'intervalle,
avec deux masses non négligeables aux bornes. Ces masses ne sont pas du bruit :
une formation très sélective qui n'admet aucun bachelier professionnel produit
un vrai zéro ; une formation en tension nulle qui accepte tous les vœux produit
un vrai un. Le décalage entre moyenne et médiane, plus marqué à mesure que la
filière du bac est moins générale, confirme l'asymétrie et interdit de résumer
la sélectivité d'une cellule par sa seule moyenne.

## Les quatre décisions arrêtées sur le label

Détaillées avec leurs conséquences dans l'ADR 0009 :

1. Conserver `prop_tot / nb_voe_pp` comme définition du taux.
2. Borner le taux à 1, en énonçant explicitement la raison du dépassement.
3. Pondérer par l'effectif de la cellule à l'entraînement, plutôt que traiter
   chaque cellule à poids égal.
4. Ne pas exclure les petites cellules par un seuil d'effectif minimal.

## La cible n'est pas stationnaire dans le temps (E12)

Deux définitions de la difficulté d'admission divergent d'une session à
l'autre : le taux agrégé toutes cellules confondues **baisse** de 40,5 % à
36,7 % entre 2020 et 2025, pendant que la **moyenne des taux par formation**
— la cible réellement apprise par le modèle — **monte** de 0,491 à 0,522
(avec un pic à 0,534 en 2024). L'explication tient au catalogue lui-même : il
passe de 12 760 à 14 252 formations sur la période, et les formations
nouvelles sont en moyenne plus petites et moins tendues, ce qui tire la
moyenne par formation vers le haut sans que chaque formation individuelle ne
devienne plus accessible. Un dispositif de surveillance de dérive qui
suivrait le seul taux agrégé conclurait à l'inverse de la réalité vécue par
un candidat regardant une formation donnée.

Deux ruptures de série, distinctes de la cible elle-même :

- **2020** : la part de mentions très bien passe de 7,4 % à 11,8 % (barème
  d'examen modifié), le retour à la normale est lent (encore 29,8 % de
  sans-mention en 2021). Les variables construites à partir des mentions
  sont contaminées sur 2020 et 2021, la cible ne l'est pas.
- **2019 puis 2025** : la part de vœux boursiers passe de 12,5 % à 13,8 %
  puis à 16,3 % en 2020, stable quatre ans, avant de retomber à 13,8 % en
  2025. Le statut de boursier étant une dimension des cellules de label, les
  cellules `_brs` du jeu de test 2025 ne décrivent pas tout à fait la même
  population que celles de l'entraînement.

Conséquence pour le protocole d'évaluation, détaillée dans
`04-modele/evaluation.md` et l'ADR 0012 : entraînement 2020-2023, validation
2024, test 2025 — avec trois réserves écrites avant tout résultat.

## Ce que cela implique pour l'évaluation du modèle

Détaillé dans `04-modele/evaluation.md` : une cible bornée avec masses aux
extrêmes appelle une erreur absolue moyenne pondérée plutôt qu'une erreur
quadratique, une vérification explicite de la calibration aux bornes, et un
protocole temporel qui tient compte des deux ruptures ci-dessus.

## Un seul lieu de définition du taux (E19)

La formule `taux = prop_tot / nb_voe_pp`, bornée à 1, a d'abord été codée
directement dans la couche gold (`edumatch.transform.etoile`, E16), qui en
avait besoin avant que l'étape dédiée au label n'existe dans le plan
d'exécution du projet. Depuis E19, elle vit dans un seul module,
`src/edumatch/features/label.py` (`calculer_taux`), et `etoile.py` l'appelle
au lieu de la recalculer. Le comportement n'a pas changé d'une virgule — ce
n'est pas une nouvelle décision, c'est une mise en conformité du code avec
l'ADR 0009, déjà arrêtée.

La raison de ce déplacement : une formule dupliquée à deux endroits du dépôt
finit, tôt ou tard, par diverger d'un endroit à l'autre sans que personne ne
le remarque — un correctif appliqué d'un côté, oublié de l'autre. En n'ayant
plus qu'un seul point de définition, la couche gold, la construction des
variables (E20), l'entraînement et l'audit d'équité lisent tous la même
fonction.

**Preuve que l'extraction n'a rien changé au résultat**, mesurée avant puis
après sur `data/processed/parcoursup/fait_admission.parquet` :

| | Avant | Après |
|---|---:|---:|
| Lignes | 440 030 | 440 030 |
| Somme des taux | 201 404,572 630 955 43 | 201 404,572 630 955 43 |
| Cellules à `taux_depasse_1` | 31 900 | 31 900 |
| Empreinte SHA-256 du fichier | `932e2ca7...aa6106fd` | `932e2ca7...aa6106fd` |

Empreinte complète : `932e2ca72461f1e896c4bdac5b500cff4425b098589c8114ef0a0c04aa6106fd`.
Aucune valeur hors de `[0, 1]` avant comme après. C'est cette identité stricte
qui rend l'opération défendable comme un déplacement de code, et non comme un
changement de calcul déguisé.

Un test de non-régression (`tests/data/test_features_label_non_regression.py`)
fixe ce résultat à deux niveaux : un vecteur de cinq cellules figé sur la
fonction isolée (couvre le bornage, la division par zéro et la valeur
manquante), et le pipeline complet rejoué sur les échantillons versionnés du
dépôt (1 280 cellules, somme des taux 558,742 252 776 133 5, 180 192
d'effectif total). Toute dérive future de la formule, volontaire ou non, fait
échouer ce test avant d'atteindre l'entraînement.

## La pondération à l'entraînement : forme retenue et mesure de concentration

L'ADR 0009 (décision 3) arrête le principe — pondérer par l'effectif de la
cellule (`nb_voe_pp`) plutôt que traiter chaque cellule à poids égal — sans
trancher la **forme** exacte du poids. C'était l'un des deux points que E19
devait combler (`poids_effectif` dans `features/label.py`), l'autre étant le
regroupement de la formule décrit ci-dessus.

Avant de retenir l'effectif brut, la concentration de poids qu'il fait porter
au 1 % de cellules les plus grosses a été mesurée sur les 440 030 cellules
réelles, et comparée à trois formes alternatives qui n'ont jamais été
retenues mais qui cadrent le choix :

| Forme du poids | Part du poids total captée par le 1 % de cellules les plus grosses (4 400 / 440 030) |
|---|---:|
| Effectif brut (`nb_voe_pp`) — retenu | **25,9 %** |
| Racine carrée | 7,2 % |
| Plafonné au p99 | 15,4 % |
| Log(1 + n) | 2,3 % |

Effectifs par cellule, pour situer cette concentration : min 1, médiane 30,
p99 1 868, max 16 483.

**Retenu : l'effectif brut**, conforme à l'ADR 0009 (décision 3) et à
`configs/base.yaml` (`modele.ponderation: effectif_cellule`). C'est la seule
des quatre formes qui traduit fidèlement l'écart de fiabilité statistique
entre une cellule à 3 vœux et une cellule à 500 — c'est exactement pour cette
raison que l'ADR 0009 écarte le poids égal (option 4). La mesure confirme la
décision déjà prise, elle ne la rouvre pas.

**Écarté** : le poids égal pour toutes les cellules (biaiserait
l'optimisation vers les petites cellules, nombreuses) ; la racine carrée et
le plafond au p99 (atténuent la concentration, mais aussi l'écart de
fiabilité statistique que la pondération est censée refléter).

**Le seuil qui ferait reconsidérer** (déjà écrit dans l'ADR 0009) : si l'audit
d'équité (E26) montre que cette concentration de poids défavorise
structurellement un profil — le bac professionnel, notamment, où 21,6 % des
formations n'émettent aucune proposition — il faudrait alors revoir la
pondération, jamais la définition du taux.

---
*Mise à jour : 2026-08-30 (E19).*
