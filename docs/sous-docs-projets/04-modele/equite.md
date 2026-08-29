# Équité — matière établie à ce jour

Ce document sera complété en E26 (`models/fairness.py`, quatre dimensions,
ratio d'impact disparate, résultats sur les prédictions du modèle entraîné).
Ce qui suit est ce que l'analyse exploratoire (E11) établit déjà : où
l'inégalité se situe réellement dans les données, et quels substituts du
genre existent dans les variables candidates du modèle.

Source : `notebooks/03-jgk-eda-equite-substituts.ipynb`.

## Où se situe l'inégalité observée

**À l'admission, à formation égale, l'écart entre femmes et hommes est
proche de nul.** Sur les 11 099 formations recevant au moins 30 vœux de
chaque sexe, l'écart médian du taux d'admission est de **−0,04 point**,
inférieur à 5 points dans **83,8 %** des cas ; les femmes sont avantagées
dans 48,8 % des formations, les hommes dans 50,8 %. **L'inégalité observée
dans le système d'orientation ne se joue donc pas au moment de l'admission,
mais en amont, dans la formulation des vœux** — hors du périmètre que le
modèle peut corriger, puisqu'il n'intervient pas sur ce choix.

Réserve de méthode à conserver : le fichier source ne ventile par sexe que
les admis, pas l'ensemble des vœux formulés. Cette comparaison porte donc sur
une quantité un peu différente de celle qu'utilise le label du modèle
(propositions rapportées aux vœux, toutes cellules), et ne doit pas être
présentée comme une mesure directe du même objet.

**La féminisation du catalogue est polarisée**, pas répartie en cloche :
19,7 % des formations comptent moins de 20 % de femmes parmi leurs admis
(2 775 formations, sur dénominateur non nul — voir l'encadré de correction
ci-dessous), 17,9 % en comptent plus de 80 %, et seulement 21,5 % se situent
entre 40 % et 60 %. La part globale de femmes admises, toutes formations
confondues, est de 56,3 %.

## ⚠️ Une correction de chiffre : lire un pourcentage avec son dénominateur

Le chiffre de 2 954 formations à moins de 20 % de femmes, retenu jusqu'ici,
incluait 179 formations qui n'admettent **aucun** candidat. Sur un
dénominateur nul, `pct_f` vaut mécaniquement 0 %, et ces formations se
trouvaient comptées comme extrêmement peu féminisées alors qu'elles ne
disent rien sur la féminisation d'un processus d'admission qui n'a pas eu
lieu. Le chiffre corrigé, dénominateur non nul, est **2 775 (19,7 %)**. La
leçon retenue pour la suite du projet, notamment pour l'audit d'équité
(E26) : tout ratio calculé par sous-groupe doit être accompagné de l'effectif
du sous-groupe, et un sous-groupe à effectif nul ou très faible doit être
signalé plutôt que rapporté à égalité avec les autres.

## Les substituts du genre — mesurés, pas supposés

Le genre n'entre jamais dans le modèle (invariant du projet). La question
posée en E11 est différente : **quelles variables candidates du modèle
permettent de reconstituer le genre par un autre chemin ?** Une variable
fortement corrélée au genre agit comme un substitut, même en l'absence de
toute variable de genre déclarée.

Mesure retenue : information mutuelle entre chaque variable candidate et le
sexe des admis, **corrigée du nombre de modalités de la variable par
permutation** (5 tirages aléatoires, graine fixée à 42, pour estimer la part
d'information mutuelle imputable au seul hasard de cardinalité).

| Variable | Observé | Hasard (permutation) | Net |
|---|---:|---:|---:|
| `cod_uai` (établissement) | 57,5 % | 28,5 % | **28,9 %** |
| `fili` (filière) | 19,6 % | 0,1 % | **19,5 %** |
| `ville_etab` | 19,1 % | 8,9 % | **10,2 %** |
| `select_form` (sélectivité) | 5,6 % | 0,0 % | **5,6 %** |
| `dep` (département) | 3,1 % | 0,8 % | **2,3 %** |
| `acad_mies` (académie) | 1,6 % | 0,2 % | **1,4 %** |

## ⚠️ Une mesure d'association non corrigée aurait trompé

Sans la correction par permutation, `cod_uai` — qui compte plusieurs
milliers de modalités distinctes — aurait affiché un pouvoir explicatif
proche du double de sa valeur réelle : une variable à haute cardinalité
capte mécaniquement de l'information mutuelle avec n'importe quelle cible,
y compris une cible sans rapport, simplement parce qu'elle offre davantage
de façons de séparer les observations. La leçon retenue pour toute mesure
d'association future dans ce projet (ablation E27, corrélations de dérive
E34) : ne jamais comparer des variables de cardinalité différente sans
correction de ce biais.

## La contradiction qui structure le dispositif d'équité

L'hypothèse de départ du projet désignait l'académie et l'établissement
d'origine comme substituts principaux à surveiller. La mesure infirme cette
hypothèse sur l'académie : elle n'explique que **1,4 %** du genre, une fois
la cardinalité corrigée. Le deuxième substitut le plus puissant, après
l'établissement, est la **filière** (19,5 %) — une variable qui ne peut pas
être retirée du modèle sans détruire sa capacité à distinguer un BTS d'une
CPGE, c'est-à-dire sans détruire le modèle lui-même.

**Conséquence assumée** : le modèle reconstituera partiellement le genre
par la filière, quoi qu'il arrive. L'exclusion de la variable de genre à
l'entrée est **nécessaire mais insuffisante** pour garantir l'absence de
discrimination indirecte. Le dispositif d'équité du projet repose donc sur
trois niveaux, et non sur le seul retrait de la variable :

1. **Exclusion à l'entrée** — le genre n'est jamais une variable du modèle
   (invariant du projet, vérifié par test).
2. **Mesure des substituts** — ce carnet, à rejouer à chaque évolution
   notable du catalogue de variables (E20).
3. **Audit a posteriori sur les prédictions** (E26) — puisque l'exclusion ne
   suffit pas, la seule vérification qui compte in fine porte sur l'écart de
   prédiction entre sous-groupes de genre, mesuré sur les sorties réelles du
   modèle entraîné, pas sur ses entrées.

## L'arbitrage tranché en E13, sur les deux substituts les plus forts

La décision de variables (E13, ADR 0013) a dû trancher, colonne par colonne,
ce que ce carnet mesurait encore sous forme de constat. Deux arbitrages
méritent d'être rapportés ici, parce qu'ils engagent directement l'équité :

**`cod_uai` (28,9 % net) est exclu du modèle**, pour deux raisons
indépendantes l'une de l'autre : sa cardinalité (4 058 établissements, un
risque de mémorisation qui existe indépendamment de toute question d'équité)
et son statut de premier substitut du genre mesuré. L'indépendance des deux
raisons importe : un arbitrage qui ne tiendrait que par l'argument d'équité
s'effondrerait si un futur audit montrait un impact disparate faible.
L'information d'établissement ne disparaît pas entièrement pour autant — les
variables décalées, attachées à la formation, en portent une partie —, ce qui
confirme que l'exclusion seule ne suffit pas et que le niveau 2 (mesure des
substituts) doit être rejoué sur le jeu de variables final.

**`fili` (19,5 % net) est retenue, malgré tout.** La retirer détruirait
l'objet même du système, qui doit comparer des formations entre elles, sans
rendre le modèle aveugle au genre : la ségrégation par filière existe dans le
catalogue lui-même, avec ou sans le modèle. C'est une position assumée,
compensée par l'audit a posteriori de niveau 3. Le seuil qui la ferait
rouvrir : un impact disparate significatif porté par la filière, mesuré une
fois le modèle entraîné (E26).

Détail complet des deux arbitrages : `04-modele/specification.md` et
l'ADR 0013.

## Ce qui reste à faire (E26)

- Ratio d'impact disparate sur les prédictions, par sexe, académie et
  établissement.
- Vérifier si l'écart mesuré à l'admission (quasi nul) se retrouve dans les
  prédictions du modèle, ou si la filière réintroduit un écart que
  l'admission observée ne présentait pas.
- Rejouer la mesure de substituts (ce carnet) sur l'ensemble de variables
  finalement retenu en E20 (`04-modele/specification.md`), qui diffère de ce
  qui a été exploré ici : `cod_uai` et `ville_etab` en sont désormais exclus.

---
*Mise à jour : 2026-08-29, commit `f7c1449`.*
