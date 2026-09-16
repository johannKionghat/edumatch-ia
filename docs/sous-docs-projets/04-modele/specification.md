# Spécification du modèle — cible, variables, protocole

Blocs 4.1 et 4.3. La cible est définie dans `01-donnees/label.md`, le
protocole d'évaluation et le split dans `evaluation.md`. Ici je documente
quelles variables entrent dans le modèle et selon quel critère je les ai
triées.

Analyse faite en E13, décision détaillée dans l'ADR 0013.

## Le critère de tri

Je ne me suis pas contenté de me demander si une variable est postérieure à
l'admission. `voe_tot` (le nombre total de vœux reçus) précède
chronologiquement l'admission, mais un lycéen qui formule ses vœux en
janvier ne peut pas la connaître : elle se construit pendant la campagne.

Le critère retenu : **la variable est-elle connue au moment où le lycéen
formule ses vœux ?** C'est pour ça que la plupart des compteurs Parcoursup
(vœux, propositions, admis, capacité) ne sont pas exclus mais **décalés d'une
session** : la même colonne fuite si on la lit sur la session courante, elle
est légitime si on la lit sur la session précédente.

## Le classement des 128 colonnes

Sur les huit millésimes téléchargés : 128 colonnes vues au moins une fois (de
85 en 2018 à 118 en 2021-2025, dont 83 communes aux huit sessions).

| Catégorie | Colonnes | Principe |
|---|---:|---|
| Liste blanche, session prédite | 9 | Attributs de catalogue publiés avant la campagne : filière, type de formation, sélectivité, statut de l'établissement, territoire |
| Décalées d'une session | 35 | Compteurs de capacité, vœux, propositions, admis, académie d'origine, calendrier |
| Mentions, retenues sous réserve | 8 | Écartées par défaut — contamination du contrôle continu 2020 |
| Exclusions définitives | 73 | Interdites (4), substituts (3), instables (22), non complètes (10), hors périmètre (10), redondantes (23), à cardinalité excessive (1) |
| **Total** | **128** | Chaque colonne vue au moins une fois est classée |

À ces colonnes s'ajoutent les deux dimensions qui découpent chaque formation
en cellules — type de baccalauréat et statut de boursier (`01-donnees/label.md`,
ADR 0009). Sans elles le modèle prédirait une moyenne de six situations très
différentes (écart médian de 8,5 points entre bac général et bac
professionnel, jusqu'à 42,3 points en CPGE, voir `evaluation.md`).

### Liste blanche plutôt que liste noire

J'ai choisi une **liste blanche** des colonnes autorisées sur la session
prédite, pas une liste d'exclusion. Une liste d'exclusion laisse passer par
défaut une colonne ajoutée par un futur millésime, sans qu'elle ait été
examinée. La liste blanche refuse par défaut. Neuf colonnes seulement sont
autorisées sur la session prédite : filière, type de formation, sélectivité,
statut du contrat, type d'établissement, département, académie, région.
Aucune ne compte de vœux, de propositions ni d'admis.

### Les motifs d'exclusion

| Motif | Nb | Ce qu'il signifie |
|---|---:|---|
| Redondance | 23 | Recalculable depuis une colonne retenue |
| Instabilité | 22 | Disponibilité qui change dans la fenêtre 2020-2025 |
| Complétude non aléatoire | 10 | Absence qui code une information (filière), pas un manque |
| Hors périmètre | 10 | Décrit une population que le label ne couvre pas (phase complémentaire, autres terminales) |
| Interdite | 4 | Ventilation par sexe — le genre ne sert qu'à l'audit a posteriori |
| Substitut du genre | 3 | Voir `equite.md` |
| Cardinalité excessive | 1 | Quasi-identifiant, pas une variable |

## La redondance des pourcentages : une hypothèse fausse corrigée

Ma première hypothèse pour reconstituer les pourcentages était simple :
`pct_bours = acc_brs / acc_tot`. Vérifiée sur les chiffres, elle était fausse
(écart médian de 3,4 points, jusqu'à 97,5 au maximum). Le vrai dénominateur
est `acc_neobac` (les néo-bacheliers), pas l'ensemble des admis.

Reconstitution vérifiée des 19 colonnes de pourcentage sur 2025, écart
maximal de 0,5 point (l'arrondi, rien de plus) :

| Dénominateur | Colonnes concernées |
|---|---|
| `acc_neobac` | `pct_bours`, `pct_bg`, `pct_bt`, `pct_bp`, `pct_bg_mention`, `pct_bt_mention`, `pct_bp_mention`, `pct_tb`, `pct_b`, `pct_ab`, `pct_sansmention`, `pct_mention_nonrenseignee`, `pct_tbf`, `pct_aca_orig`, `pct_aca_orig_idf` |
| `acc_tot` | `pct_neobac`, `pct_f`, `pct_acc_debutpp`, `pct_acc_datebac`, `pct_acc_finpp` |

Leçon retenue : un pourcentage ne se rattache pas à son dénominateur par la
ressemblance de son nom. `pct_bours` et `pct_neobac` se ressemblent et ne
portent pas sur la même population.

## `cod_uai` écarté pour deux raisons indépendantes

`cod_uai` (l'identifiant d'établissement) est écarté pour deux raisons qui
tiennent chacune seule :

- **Cardinalité** : 4 058 établissements. Le modèle mémoriserait
  l'établissement au lieu d'apprendre une règle transférable, et tout
  établissement absent de l'entraînement deviendrait imprédictible.
- **Substitut du genre** : `cod_uai` est la variable la plus fortement
  associée au genre du catalogue, 28,9 % de pouvoir explicatif net une fois
  la cardinalité corrigée (`equite.md`).

Les deux raisons sont indépendantes : si l'exclusion ne tenait que par
l'équité, elle s'effondrerait le jour où l'audit montrerait un impact
disparate faible. Elle tient aussi par la cardinalité seule.

L'information d'établissement ne disparaît pas totalement : les variables
décalées sont attachées à la formation, donc indirectement à son
établissement. D'où la nécessité du niveau 2 du dispositif d'équité
(`equite.md`).

## La filière retenue malgré 19,5 % de pouvoir explicatif sur le genre

`fili` (la filière) reconstitue 19,5 % du genre, le deuxième plus fort score
après `cod_uai`. Je la retiens quand même : la retirer détruirait l'objet
même du système, qui doit comparer des formations entre elles. La
ségrégation par filière existe dans le catalogue lui-même, avec ou sans le
modèle. C'est compensé par l'audit d'équité a posteriori (`equite.md`). Le
seuil qui ferait rouvrir cette décision : un impact disparate significatif
porté par la filière, mesuré une fois le modèle entraîné.

## Ce qui reste ouvert

Points non tranchés :

1. **`capa_fin`** : classée décalée par prudence, faute de preuve que la
   capacité affichée pendant la campagne coïncide avec la colonne publiée
   ensuite sous ce nom.
2. **Le taux décalé manque pour la session cible 2020**, `prop_tot_*` par
   type de bac n'existant pas en 2019. Valeurs laissées manquantes,
   LightGBM traitant nativement l'absence.
3. **Le contrôle automatique de non-fuite travaille sur des noms de
   colonnes, pas sur leur sens** : il empêche l'ajout distrait d'un compteur
   à la liste blanche, il ne prouve pas que les 9 colonnes retenues sont
   réellement publiées avant l'ouverture de la campagne. Cette preuve relève
   de l'ADR 0013, pas d'un test automatisé.

La construction de la table de variables à partir de ce classement — le
mécanisme du décalage, le contrat anti-fuite et sa validation — est
documentée dans `variables.md` (E20).

## Où vit la décision dans le dépôt

Le classement des 128 colonnes est écrit dans `configs/base.yaml`
(section `modele.variables`), typé par `VariablesConfig` dans
`src/edumatch/config.py`, et vérifié par quatre contrôles dans
`tests/data/test_variables_reference.py` : toute colonne citée existe
réellement, toute colonne d'un millésime est classée, aucune colonne de
résultat de campagne ne figure dans la liste blanche, aucune colonne
n'appartient à deux catégories à la fois. Les quatre contrôles ont été
vérifiés par mutation du code.

---
*Mise à jour : 2026-08-30 (E20), commit `e34f22a`.*
