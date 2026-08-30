# Spécification du modèle — cible, variables, protocole

**Critères du Bloc 4 concernés** : 4.1 (algorithme adapté aux données et au
cahier des charges) et 4.3 (protocole d'évaluation temporel, sans fuite). La
définition et le bornage de la cible sont traités dans `01-donnees/label.md` ;
le protocole d'évaluation et le split dans `evaluation.md`. Ce document couvre
ce que ces deux pièces supposent en amont : **quelles variables entrent dans
le modèle, et selon quel critère je les ai triées.**

Analyse produite en E13, à partir des quatre carnets d'exploration
(`notebooks/01` à `04-jgk-eda-*.ipynb`). Décision complète, avec les options
écartées et les motifs détaillés colonne par colonne : ADR 0013.

## Le critère de tri

La question qui décide du sort d'une colonne n'est **pas** « cette variable
est-elle postérieure à la décision d'admission ». Une variable comme
`voe_tot` (le nombre total de vœux reçus) précède chronologiquement
l'admission, et reste pourtant inutilisable : un lycéen qui formule ses vœux
en janvier ne peut pas la connaître, puisqu'elle se construit au fil de la
campagne dont il fait lui-même partie.

Le critère retenu est donc : **la variable est-elle connue au moment où le
lycéen formule ses vœux ?** C'est pour cela que la plupart des compteurs de
Parcoursup (vœux, propositions, admis, capacité) ne sont pas exclus mais
**décalés d'une session** : la même colonne est une fuite lue sur la session
courante, et une information légitime lue sur la session précédente.

## Le classement des 128 colonnes

Périmètre mesuré sur les huit millésimes réellement téléchargés : **128
colonnes vues au moins une fois**, de 85 (session 2018) à 118 (2021-2025),
dont 83 communes aux huit sessions.

| Catégorie | Colonnes | Principe |
|---|---:|---|
| Liste blanche, session prédite | 9 | Attributs de catalogue publiés avant la campagne : filière, type de formation, sélectivité, statut de l'établissement, territoire |
| Décalées d'une session | 35 | Compteurs de capacité, vœux, propositions, admis, académie d'origine, calendrier |
| Mentions, retenues sous réserve | 8 | Écartées du jeu de référence par défaut — contamination du contrôle continu 2020 |
| Exclusions définitives | 73 | Interdites (4), substituts (3), instables (22), non complètes (10), hors périmètre (10), redondantes (23), à cardinalité excessive (1) |
| **Total** | **128** | **Sans reste : chaque colonne vue au moins une fois est classée** |

À ces colonnes s'ajoutent les deux dimensions qui découpent chaque formation
en cellules — type de baccalauréat et statut de boursier (`01-donnees/label.md`,
ADR 0009) — qui ne viennent d'aucune colonne mais de la structure du label
elle-même. Le modèle doit savoir quelle cellule il prédit, faute de quoi il
prédirait une moyenne de six situations hétérogènes (écart médian de
8,5 points entre bac général et bac professionnel, jusqu'à 42,3 points en
CPGE — `04-modele/evaluation.md`).

### La liste blanche — pourquoi ce sens plutôt que l'exclusion

J'ai retenu une **liste blanche des colonnes autorisées sur la session
prédite**, et non une liste d'exclusion. Une liste d'exclusion admet par
défaut : une colonne ajoutée par un millésime futur entrerait dans le modèle
sans avoir été examinée. La liste blanche refuse par défaut, et la chaîne
s'arrête tant qu'une colonne nouvelle n'a pas été classée. Neuf colonnes
seulement sont autorisées sur la session prédite : la filière, le type de
formation, la sélectivité, le statut du contrat, le type d'établissement, le
département, l'académie et la région. Aucune ne compte de vœux, de
propositions ni d'admis.

### Les motifs d'exclusion, comptés

| Motif | Nb | Ce qu'il signifie |
|---|---:|---|
| Redondance | 23 | Recalculable depuis une colonne retenue |
| Instabilité | 22 | Disponibilité qui change à l'intérieur de la fenêtre d'entraînement 2020-2025 |
| Complétude non aléatoire | 10 | Absence qui code une information (filière), pas un manque |
| Hors périmètre | 10 | Décrit une population que le label ne couvre pas (phase complémentaire, autres terminales) |
| Interdite | 4 | Ventilation par sexe — le genre ne sert qu'à l'audit a posteriori |
| Substitut du genre | 3 | Voir `equite.md` |
| Cardinalité excessive | 1 | Quasi-identifiant, pas une variable |

## Une hypothèse vérifiée, puis corrigée : la redondance des pourcentages

La règle de tri des variables de pourcentage était simple à énoncer : je
retiens les effectifs, j'écarte les pourcentages qui s'en déduisent. Encore
fallait-il vérifier la relation, pas la supposer. Ma première hypothèse —
`pct_bours = acc_brs / acc_tot` — s'est révélée fausse à la mesure : écart
médian de 3,4 points, jusqu'à 97,5 points au maximum. Le dénominateur réel
est `acc_neobac` (les néo-bacheliers), pas l'ensemble des admis.

Reconstitution vérifiée des 19 colonnes de pourcentage sur la session 2025,
écart maximal de 0,500 point dans tous les cas — c'est-à-dire l'arrondi au
point entier, rien de plus :

| Dénominateur | Colonnes concernées |
|---|---|
| `acc_neobac` | `pct_bours`, `pct_bg`, `pct_bt`, `pct_bp`, `pct_bg_mention`, `pct_bt_mention`, `pct_bp_mention`, `pct_tb`, `pct_b`, `pct_ab`, `pct_sansmention`, `pct_mention_nonrenseignee`, `pct_tbf`, `pct_aca_orig`, `pct_aca_orig_idf` |
| `acc_tot` | `pct_neobac`, `pct_f`, `pct_acc_debutpp`, `pct_acc_datebac`, `pct_acc_finpp` |

La leçon retenue pour la suite du projet : un pourcentage ne se rattache
jamais à son dénominateur par la ressemblance de son nom. `pct_bours` et
`pct_neobac` se ressemblent et ne se rapportent pas à la même population.

## L'arbitrage `cod_uai` — deux raisons indépendantes

`cod_uai` (l'identifiant d'établissement) est écarté pour deux raisons qui
tiennent chacune séparément :

- **Cardinalité** : 4 058 établissements. Le modèle mémoriserait
  l'établissement plutôt que d'apprendre une règle transférable, et tout
  établissement absent de l'entraînement deviendrait imprédictible. Ce motif
  vaut indépendamment de toute considération d'équité.
- **Substitut du genre** : `cod_uai` est la variable la plus fortement
  associée au genre dans le catalogue mesuré, 28,9 % de pouvoir explicatif
  net une fois la cardinalité corrigée (`equite.md`).

L'indépendance des deux raisons est ce qui rend l'arbitrage solide : s'il ne
tenait que par l'argument d'équité, il s'effondrerait le jour où l'audit
montrerait un impact disparate faible. Il tient aussi par la cardinalité,
seule.

L'information d'établissement ne disparaît pas entièrement pour autant : les
variables décalées sont attachées à la formation, donc indirectement à son
établissement. Exclure `cod_uai` réduit le canal le plus direct, cela ne rend
pas le modèle aveugle à l'établissement — d'où la nécessité du niveau 2 du
dispositif d'équité (`equite.md`).

## La filière — retenue malgré 19,5 % de pouvoir explicatif sur le genre

La filière (`fili`) reconstitue 19,5 % du genre, le deuxième plus fort
pouvoir explicatif mesuré après `cod_uai`. Je la retiens malgré cela : la
retirer détruirait l'objet même du système, qui doit comparer des formations
entre elles, sans rendre le modèle aveugle au genre — la ségrégation par
filière existe dans le catalogue lui-même, avec ou sans le modèle.

C'est une position assumée, pas un oubli, compensée par l'audit d'équité
a posteriori (`equite.md`). Le seuil qui la ferait rouvrir : un impact
disparate significatif porté par la filière, mesuré une fois le modèle
entraîné.

## Ce qui reste ouvert

Trois points ne sont pas tranchés à ce stade et sont suivis dans
`reste-a-faire.md` :

1. **`capa_fin`** : classée décalée par prudence, faute de preuve que la
   capacité affichée pendant la campagne coïncide avec la colonne publiée
   ensuite sous ce nom.
2. **Le taux décalé manque pour la session cible 2020**, `prop_tot_*` par
   type de bac n'existant pas en 2019. Valeurs laissées manquantes de façon
   explicite, sans imputation — LightGBM traite nativement l'absence.
3. **Le contrôle automatique de non-fuite travaille sur des noms de
   colonnes, pas sur leur sémantique** : il empêche l'ajout distrait d'un
   compteur à la liste blanche, il ne prouve pas que les 9 colonnes retenues
   sont réellement publiées avant l'ouverture de la campagne. Cette preuve-là
   relève de l'ADR 0013, pas d'un test automatisé.

La construction effective de la table de variables à partir de ce classement
— le mécanisme du décalage, le contrat anti-fuite et sa validation par
mutation, le traitement des cellules sans antécédent — est documentée dans
`variables.md` (E20).

## Où vit la décision dans le dépôt

Le classement des 128 colonnes est écrit dans `configs/base.yaml`
(section `modele.variables`), typé par `VariablesConfig` dans
`src/edumatch/config.py`, et vérifié par quatre contrôles dans
`tests/data/test_variables_reference.py` : toute colonne citée existe
réellement, toute colonne d'un millésime est classée, aucune colonne de
résultat de campagne ne figure dans la liste blanche, et aucune colonne
n'appartient à deux catégories à la fois. Les quatre contrôles ont été
vérifiés par mutation, pas par relecture.

---
*Mise à jour : 2026-08-30 (E20, ajout du renvoi vers `variables.md`), commit `a5ae188`.*
