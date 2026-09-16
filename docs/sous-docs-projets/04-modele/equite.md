# Équité — les quatre dimensions, résultats

Bloc 4.15. Ce document couvre deux temps : l'analyse exploratoire sur les
données brutes, qui établit où l'inégalité se situe et quels substituts du
genre existent parmi les variables candidates, puis l'audit sur les
prédictions du modèle réellement entraîné (`src/edumatch/models/fairness.py`),
qui vérifie si l'exclusion du genre à l'entrée suffit en pratique.

Source : `notebooks/03-jgk-eda-equite-substituts.ipynb`.

## Où se situe l'inégalité observée

À l'admission, à formation égale, l'écart entre femmes et hommes est proche
de nul. Sur les 11 099 formations recevant au moins 30 vœux de chaque sexe,
l'écart médian du taux d'admission est de −0,04 point, inférieur à 5 points
dans 83,8 % des cas ; les femmes sont avantagées dans 48,8 % des formations,
les hommes dans 50,8 %. L'inégalité observée dans le système d'orientation
ne se joue donc pas au moment de l'admission, mais en amont, dans la
formulation des vœux — hors du périmètre que le modèle peut corriger,
puisqu'il n'intervient pas sur ce choix.

Réserve de méthode : le fichier source ne ventile par sexe que les admis,
pas l'ensemble des vœux formulés. Cette comparaison porte donc sur une
quantité un peu différente de celle qu'utilise le label du modèle
(propositions rapportées aux vœux, toutes cellules).

La féminisation du catalogue est polarisée, pas répartie en cloche : 19,7 %
des formations comptent moins de 20 % de femmes parmi leurs admis (2 775
formations, sur dénominateur non nul, voir plus bas), 17,9 % en comptent
plus de 80 %, et seulement 21,5 % se situent entre 40 % et 60 %. La part
globale de femmes admises, toutes formations confondues, est de 56,3 %.

## Une correction de chiffre : lire un pourcentage avec son dénominateur

Le chiffre de 2 954 formations à moins de 20 % de femmes, retenu jusqu'ici,
incluait 179 formations qui n'admettent aucun candidat. Sur un dénominateur
nul, `pct_f` vaut mécaniquement 0 %, et ces formations se trouvaient
comptées comme extrêmement peu féminisées alors qu'elles ne disent rien sur
un processus d'admission qui n'a pas eu lieu. Le chiffre corrigé,
dénominateur non nul, est 2 775 (19,7 %). Leçon retenue pour la suite : tout
ratio par sous-groupe doit être accompagné de l'effectif du sous-groupe, et
un sous-groupe à effectif nul ou très faible doit être signalé plutôt que
rapporté à égalité avec les autres.

## Les substituts du genre — mesurés, pas supposés

Le genre n'entre jamais dans le modèle. La question posée ici est
différente : quelles variables candidates du modèle permettent de
reconstituer le genre par un autre chemin ? Une variable fortement corrélée
au genre agit comme un substitut, même en l'absence de toute variable de
genre déclarée.

Mesure retenue : information mutuelle entre chaque variable candidate et le
sexe des admis, corrigée du nombre de modalités de la variable par
permutation (5 tirages aléatoires, graine fixée à 42, pour estimer la part
d'information mutuelle imputable au seul hasard de cardinalité).

| Variable | Observé | Hasard (permutation) | Net |
|---|---:|---:|---:|
| `cod_uai` (établissement) | 57,5 % | 28,5 % | **28,9 %** |
| `fili` (filière) | 19,6 % | 0,1 % | **19,5 %** |
| `ville_etab` | 19,1 % | 8,9 % | **10,2 %** |
| `select_form` (sélectivité) | 5,6 % | 0,0 % | **5,6 %** |
| `dep` (département) | 3,1 % | 0,8 % | **2,3 %** |
| `acad_mies` (académie) | 1,6 % | 0,2 % | **1,4 %** |

Sans la correction par permutation, `cod_uai` — qui compte plusieurs
milliers de modalités — aurait affiché un pouvoir explicatif proche du
double de sa valeur réelle : une variable à haute cardinalité capte
mécaniquement de l'information mutuelle avec n'importe quelle cible,
simplement parce qu'elle offre plus de façons de séparer les observations.
Leçon retenue pour toute mesure d'association future dans ce projet
(ablation, dérive) : ne jamais comparer des variables de cardinalité
différente sans corriger ce biais.

## La contradiction qui structure le dispositif d'équité

L'hypothèse de départ désignait l'académie et l'établissement d'origine
comme substituts principaux à surveiller. La mesure infirme cette hypothèse
sur l'académie : elle n'explique que 1,4 % du genre, une fois la cardinalité
corrigée. Le deuxième substitut le plus puissant, après l'établissement, est
la filière (19,5 %) — une variable qu'on ne peut pas retirer du modèle sans
détruire sa capacité à distinguer un BTS d'une CPGE.

Conséquence assumée : le modèle reconstituera partiellement le genre par la
filière, quoi qu'il arrive. Exclure la variable de genre à l'entrée est
nécessaire mais insuffisant pour garantir l'absence de discrimination
indirecte. Le dispositif d'équité repose donc sur trois niveaux :

1. **Exclusion à l'entrée** — le genre n'est jamais une variable du modèle
   (vérifié par test).
2. **Mesure des substituts** — ce carnet, à rejouer à chaque évolution
   notable du catalogue de variables.
3. **Audit a posteriori sur les prédictions** — puisque l'exclusion ne
   suffit pas, la vérification qui compte porte sur l'écart de prédiction
   entre sous-groupes de genre, mesuré sur les sorties réelles du modèle
   entraîné, pas sur ses entrées.

## Les deux arbitrages sur les substituts les plus forts

**`cod_uai` (28,9 % net) est exclu du modèle**, pour deux raisons
indépendantes : sa cardinalité (4 058 établissements, un risque de
mémorisation qui existe indépendamment de toute question d'équité) et son
statut de premier substitut du genre mesuré. L'information d'établissement
ne disparaît pas entièrement — les variables décalées, attachées à la
formation, en portent une partie — ce qui confirme que l'exclusion seule ne
suffit pas.

**`fili` (19,5 % net) est retenue, malgré tout.** La retirer détruirait
l'objet même du système, qui doit comparer des formations entre elles : la
ségrégation par filière existe dans le catalogue lui-même, avec ou sans le
modèle. C'est compensé par l'audit a posteriori. Le seuil qui la ferait
rouvrir : un impact disparate significatif porté par la filière, mesuré une
fois le modèle entraîné.

Détail complet des deux arbitrages : `specification.md` et l'ADR 0013.

## L'audit sur les prédictions réelles

`src/edumatch/models/fairness.py` ne relance rien : il appelle la même
fonction d'entraînement (même split, même modèle déjà arrêté sur la
validation) pour récupérer les prédictions du test 2025, puis les ventile
selon les quatre dimensions de `configs/base.yaml` (`equite.dimensions`) :
type de baccalauréat, statut de boursier, territoire, genre.

Le genre n'entre jamais dans le modèle ; ce module ne le lit que pour
l'audit, à partir des compteurs de vœux et d'admissions par sexe déjà
présents dans la table silver mais jamais transmis au modèle. Le genre
d'une formation est construit sur la composition des candidats
(`voe_tot_f / voe_tot`), jamais sur celle des admis, qui est en partie ce
que le modèle prédit.

### La définition d'équité retenue, et ce qu'elle sacrifie

Définition privilégiée : la calibration par groupe — un taux prédit de 60 %
doit correspondre à un taux observé de 60 % dans chaque groupe, quel que
soit le groupe. Ce choix est incompatible avec deux autres définitions
courantes d'équité, la parité démographique (même taux de recommandation
pour chaque groupe) et les cotes égalisées (même taux de vrais positifs pour
chaque groupe), dès que les taux de base diffèrent entre groupes. C'est un
théorème d'impossibilité — ces trois critères ne peuvent pas être satisfaits
en même temps, sauf cas dégénéré — pas un choix de goût. Ce que ce choix
sacrifie : ni l'égalité des taux de recommandation entre groupes, ni
l'égalité des vrais positifs entre groupes ne sont garanties par ce
dispositif.

### Le passage d'un taux continu à une décision

Le ratio d'impact disparate (règle des quatre cinquièmes : le taux de
sélection du groupe le moins favorisé ne doit pas être inférieur à 80 % de
celui du groupe le plus favorisé) se définit sur une décision binaire, alors
que la cible du modèle est un taux continu dans [0, 1]. Une cellule est
comptée « recommandée » si le taux prédit atteint au moins 50 %, plutôt
qu'un partage par médiane qui produirait toujours 50 % de cellules
positives dans chaque groupe par construction et masquerait tout écart réel.
Le taux de sélection par groupe est pondéré par l'effectif de la cellule,
cohérent avec la pondération qui gouverne le reste du projet.

### Résultat, non atténué : un écart réel qui passe sous le seuil légal

Sur les formations à plus de 80 % de candidates femmes :

| | Modèle | Plancher |
|---|---:|---:|
| ECE (formations très féminisées) | **0,066** | 0,048 |
| ECE (autres formations) | 0,032 à 0,034 | — |
| Ratio d'impact disparate | **0,76** | 0,63 |

Le modèle sur-annonce les chances d'admission sur les formations très
féminisées — une erreur de calibration presque deux fois supérieure à celle
mesurée ailleurs — et le plancher y est mieux calibré que le modèle appris.
Le ratio d'impact disparate de ce groupe reste sous le seuil des quatre
cinquièmes (`equite.seuil_impact_disparate`, 0,80), à 0,76, même si le
modèle améliore nettement le 0,63 du plancher.

**Le système n'est donc pas équitable sur cette dimension.** Il fait mieux
que le plancher sur la sélection, moins bien sur la calibration — les deux
verdicts doivent être rapportés ensemble, aucun ne rachète l'autre.

### Les substituts, mesurés sur les prédictions

Les substituts identifiés plus haut (filière 19,5 % net, département 2,3 %
net, sur le genre observé) se retrouvent dans l'explication SHAP du modèle
(`explicabilite.md`) : ensemble ils totalisent 14,2 % de l'explication
globale, alors que le genre n'entre jamais en entrée. Le département y pèse
le plus lourd dans l'explication du modèle tout en étant le plus faible en
corrélation au genre : importance au modèle et corrélation à un attribut
protégé sont deux axes distincts. Une variable peut compter beaucoup pour le
modèle sans être un vecteur important de discrimination indirecte, et
inversement.

### Ce que confirme le dispositif à trois niveaux

L'exclusion à l'entrée (niveau 1) ne suffisait pas à garantir l'absence de
traitement différencié, et cet audit le prouve concrètement. Le seuil qui
rouvrirait l'arbitrage sur la filière (« un impact disparate significatif
porté par la filière ») est désormais observé — la suite du projet (Model
Card, plan de gouvernance) doit porter ce résultat sans l'atténuer.

## Ce qui reste ouvert

- Réconcilier l'écart de méthode déjà identifié entre l'analyse exploratoire
  (83,8 % de formations à moins de 5 points d'écart d'admission) et l'audit
  (73,4 % rapporté par `fairness.py`) — un filtre d'effectif probablement
  différent entre les deux mesures. Point ouvert.
- Rejouer la mesure de substituts sur le jeu de variables final si un
  prochain cycle d'entraînement en change la composition.

---
*Mise à jour : 2026-08-30, commit `e8417bb`.*
