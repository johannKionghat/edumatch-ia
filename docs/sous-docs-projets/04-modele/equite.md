# Équité — les quatre dimensions, résultats (E26, critère 4.15)

Ce qui suit couvre deux temps du projet : l'analyse exploratoire sur les
données brutes (E11), qui établit où l'inégalité se situe et quels
substituts du genre existent parmi les variables candidates, puis l'audit
sur les prédictions du modèle réellement entraîné (E26,
`src/edumatch/models/fairness.py`), qui vérifie si l'exclusion du genre à
l'entrée suffit en pratique.

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

## E26 — l'audit sur les prédictions réelles

`src/edumatch/models/fairness.py` ne relance rien : il appelle la même
fonction d'entraînement qu'E22 (même split temporel, même modèle déjà
arrêté sur la validation) pour récupérer les prédictions du seul test 2025,
puis les ventile selon les **quatre dimensions** de `configs/base.yaml`
(`equite.dimensions`) : type de baccalauréat, statut de boursier, territoire,
genre.

Le genre n'entre jamais dans le modèle (ADR 0011, vérifié par test) ; ce
module ne le lit que pour l'audit, à partir des compteurs de vœux et
d'admissions par sexe déjà présents dans la table silver (E15) mais jamais
transmis au modèle. Le genre d'une formation est construit sur la
composition **des candidats** (`voe_tot_f / voe_tot`), jamais sur celle des
admis — qui est en partie ce que le modèle prédit, la même précaution que
celle déjà posée en E11.

### La définition d'équité retenue, et ce qu'elle sacrifie

**Définition privilégiée assumée : la calibration par groupe** — un taux
prédit de 60 % doit correspondre à un taux observé de 60 % dans chaque
groupe, quel que soit le groupe. Ce choix est incompatible avec la parité
démographique et les cotes égalisées dès que les taux de base diffèrent
entre groupes : c'est un théorème (l'impossibilité conjointe de ces critères
d'équité en dehors du cas dégénéré où les groupes ont le même taux de base),
pas un arbitrage de goût. Ce que ce choix sacrifie, écrit explicitement :
ni l'égalité des taux de recommandation entre groupes, ni l'égalité des vrais
positifs entre groupes ne sont garanties par ce dispositif.

### Le passage d'un taux continu à une décision : le seuil assumé

Le ratio d'impact disparate (règle des quatre cinquièmes) se définit sur une
décision binaire, alors que la cible du modèle est un taux continu dans
[0, 1] (ADR 0009). Une cellule est comptée « recommandée » si le taux prédit
atteint au moins 50 % — plus d'une chance sur deux d'admission — plutôt
qu'un partage par médiane, qui produirait toujours 50 % de cellules
positives dans chaque groupe par construction et masquerait tout écart réel.
Le taux de sélection par groupe est pondéré par l'effectif de la cellule,
pas compté cellule par cellule, cohérent avec la pondération qui gouverne le
reste du projet.

### Résultat, non atténué : un écart réel qui passe sous le seuil légal

Sur les formations à plus de 80 % de candidates femmes :

| | Modèle | Plancher (E21) |
|---|---:|---:|
| ECE (formations très féminisées) | **0,066** | 0,048 |
| ECE (autres formations) | 0,032 à 0,034 | — |
| Ratio d'impact disparate | **0,76** | 0,63 |

Le modèle **sur-annonce les chances d'admission** sur les formations très
féminisées — une erreur de calibration presque deux fois supérieure à celle
mesurée ailleurs — et le plancher y est mieux calibré que le modèle appris.
Le ratio d'impact disparate de ce groupe reste **sous le seuil des quatre
cinquièmes retenu** (`equite.seuil_impact_disparate`, 0,80), à 0,76, même si
le modèle améliore nettement le 0,63 du plancher.

**Le système n'est donc pas équitable sur cette dimension.** Il fait mieux
que le plancher sur la sélection (le ratio d'impact disparate), moins bien
sur la calibration — les deux verdicts doivent être rapportés ensemble,
aucun des deux ne rachète l'autre. Ce résultat n'est pas adouci : c'est le
constat que l'audit produit sur les données réelles du test 2025.

### Les substituts, mesurés sur les prédictions

Les substituts identifiés en E11 (filière 19,5 % net, département 2,3 % net,
sur le genre observé) se retrouvent dans l'explication SHAP du modèle
(E25) : ensemble, ils totalisent **14,2 %** de l'explication globale, alors
que le genre n'entre jamais en entrée. Le département y pèse le plus lourd
dans l'explication du modèle tout en étant le plus faible en corrélation au
genre mesurée en E11 — importance au modèle et corrélation à un attribut
protégé sont deux axes distincts, à ne pas confondre : une variable peut
compter beaucoup pour le modèle sans être un vecteur important de
discrimination indirecte, et inversement.

### Ce que ce résultat confirme du dispositif à trois niveaux

L'audit E26 est le troisième niveau du dispositif d'équité posé en E11 :
l'exclusion à l'entrée (niveau 1) ne suffisait pas à garantir l'absence de
traitement différencié, et cet audit le prouve concrètement plutôt que de le
supposer. Le seuil qui rouvrirait l'arbitrage sur la filière (posé en E11 :
« un impact disparate significatif porté par la filière ») est désormais
observé — la suite du projet (Model Card, E42 ; plan de gouvernance, E44)
doit porter ce résultat sans l'atténuer.

## Ce qui reste ouvert après E26

- Réconcilier l'écart de méthode déjà identifié entre l'analyse exploratoire
  (83,8 % de formations à moins de 5 points d'écart d'admission, E11) et
  l'audit (73,4 % rapporté par `fairness.py`) — un filtre d'effectif
  vraisemblablement différent entre les deux mesures, voir
  `reste-a-faire.md`.
- Rejouer la mesure de substituts sur le jeu de variables final si un
  prochain cycle d'entraînement en change la composition.

---
*Mise à jour : 2026-08-30, commit `e8417bb`.*
