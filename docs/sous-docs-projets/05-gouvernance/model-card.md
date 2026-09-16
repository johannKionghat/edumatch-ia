# Model Card — EduMatch-IA, terme d'accessibilité

**Critère servi** : Bloc 1, 1.9 — livrable obligatoire · **Version** : 1.0 ·
**Date** : 2026-09-15 · **Format** : Mitchell et al., 2018 (*Model Cards for
Model Reporting*).

> **Ce document n'est pas une fiche produit.** Une Model Card qui ne
> présenterait que les chiffres favorables ne servirait à rien : elle
> laisserait un déployeur croire à une qualité qui n'est pas mesurée. Le
> résultat central de celle-ci est donc énoncé dès l'ouverture, et non
> enfoui : **sur la session de test 2025, le modèle appris ne bat pas la
> règle de référence qu'il devait battre**, ni en précision, ni en
> calibration, ni dans la quasi-totalité des sous-populations.

---

## 1. Détails du modèle

| | |
|---|---|
| **Nom** | EduMatch-IA — terme d'accessibilité |
| **Version** | issue du commit d'entraînement `102cca9`, hyperparamètres figés par `configs/base.yaml` (`modele.hyperparametres`) |
| **Date** | entraîné le 2026-08-30 ; audité en équité et en explicabilité le 2026-08-30 ; dérive mesurée le 2026-09-01 |
| **Type** | Régression de gradient boosté sur arbres — LightGBM, `LGBMRegressor` |
| **Sortie** | Un taux d'admission estimé dans [0, 1] pour une **cellule** `(formation, session, type de baccalauréat, statut de boursier)` — écrêté à l'intervalle par `matching/score.py::borner_accessibilite` |
| **Hyperparamètres** | `num_leaves` 31 · `max_depth` 8 · `learning_rate` 0,05 · `min_child_samples` 20 · `reg_alpha` 0,1 · `reg_lambda` 0,1 · `n_estimators` 2 000 avec arrêt anticipé à 100 tours, réglé sur la seule validation 2024 |
| **Pondération** | Chaque cellule pèse son effectif de vœux (ADR 0009) : une cellule à 3 vœux ne vaut pas une cellule à 500 |
| **Code** | `src/edumatch/models/train.py` (entraînement), `evaluate.py` (calibration), `explain.py` (SHAP), `fairness.py` (équité), `ablation.py`, `derive.py` |
| **Suivi d'expériences** | MLflow, expérience `edumatch-accessibilite` ; chaque exécution enregistre paramètres, métriques et empreinte du commit Git |
| **Registre de modèles** | Version 1 de `edumatch-accessibilite`, enregistrée par `src/edumatch/models/registre.py` (`make register-model`) depuis l'exécution qui porte ces mêmes chiffres. **Aucun alias ni stade de production posé** : l'étiquette `statut_evaluation` et la description de la version disent en clair qu'elle ne bat pas le plancher en test — voir §6.1 |
| **Licence des données d'entraînement** | Licence Ouverte v2.0 (Etalab) — voir `registre-sources.md` |
| **Contact** | Le responsable du modèle et le délégué à la protection des données du projet (rôles définis dans `plan-gouvernance.md` §3) |

**Pourquoi LightGBM, et ce qu'il remplace.** Les données sont tabulaires,
hétérogènes, avec des valeurs manquantes structurelles (6,46 % des cellules
n'ont aucun antécédent à la session N-1). Un réseau de neurones aurait exigé
une imputation que rien ne justifie et n'aurait pas permis d'explication
exacte : **TreeSHAP calcule les valeurs de Shapley exactement sur un modèle à
arbres**, en temps polynomial, là où un réseau imposerait une approximation.
L'explicabilité étant ici une obligation juridique et non un confort, c'est ce
point qui a tranché.

## 2. Usage prévu

**Usage prévu** : assister un **conseiller d'orientation** qui accompagne un
lycéen de terminale dans la construction de sa liste de vœux, en lui donnant,
pour chaque formation candidate, une estimation du taux d'admission de la
catégorie à laquelle le lycéen appartient, accompagnée des facteurs qui
portent cette estimation.

**Utilisateurs prévus** : conseillers d'orientation et personnels
d'accompagnement d'un établissement ou d'un organisme déployeur. Le lycéen est
destinataire de la restitution, jamais opérateur direct du système dans le
périmètre actuellement construit.

**Ce que le modèle prédit exactement** : la propriété d'une **cellule**, pas
d'une personne. La phrase exacte à employer devant un utilisateur est « le taux
d'admission observé, l'an dernier, des bacheliers technologiques boursiers dans
cette formation était de X % ; il est estimé à Y % cette année », jamais « vous
avez Y % de chances ».

### Usages hors périmètre — explicitement proscrits

| Usage | Pourquoi il est proscrit |
|---|---|
| **Prendre ou préparer une décision d'admission** | Le modèle prédit un taux de cohorte ; il n'a jamais vu un dossier individuel. Toute utilisation côté établissement pour trier des candidats serait un détournement de finalité |
| **Restituer une probabilité individuelle** | Le modèle ne dispose d'aucune variable individuelle : deux candidats de même type de bac, même statut de boursier et même département reçoivent le même chiffre |
| **Déconseiller une formation** | Le système ordonne, il n'interdit pas. Une estimation basse présentée comme un déconseil transforme une information en obstacle (`aipd.md` §6.2) |
| **Servir un public de moins de quinze ans** | L'analyse d'impact devrait être rouverte et le consentement parental recueilli (art. 8 RGPD) |
| **Alimenter un classement public d'établissements** | Les estimations portent sur l'accessibilité, pas sur la qualité ; l'agrégation par établissement produirait un palmarès que rien ne fonde |
| **Fonctionner sans supervision humaine** | L'écran conseiller et l'écartement motivé sont constitutifs du dispositif, pas une option |

## 3. Facteurs

**Facteurs pertinents retenus pour la ventilation des résultats** — les quatre
dimensions déclarées par `configs/base.yaml` (`equite.dimensions`) :

1. **Type de baccalauréat** (général, technologique, professionnel) — dimension
   du label lui-même ;
2. **Statut de boursier** — dimension du label lui-même ;
3. **Territoire** (région de l'établissement d'accueil, 19 modalités) ;
4. **Genre**, sous forme de **mixité des candidats d'une formation**
   (`voe_tot_f / voe_tot`, jamais la composition des admis, qui est en partie ce
   que le modèle prédit), en trois groupes : moins de 20 % de candidates femmes,
   mixte 20-80 %, plus de 80 %.

**Le genre n'est jamais une entrée du modèle** — invariant du projet, vérifié
par `tests/data/test_features_build_antifuite.py`, dont la discriminance a été
établie par mutation du code. Il est lu par le seul module d'audit, depuis la
table silver, pour la seule finalité de mesure d'équité. C'est la résolution du
paradoxe classique : mesurer l'équité exige l'attribut protégé, la minimisation
pousse à ne pas le collecter — on le conserve pour l'audit, avec accès
restreint, jamais en entrée.

**Conditions d'évaluation** : toutes les mesures de ce document portent sur la
session **2025**, jamais consultée pendant le réglage des hyperparamètres, et
comparent le modèle à la règle de référence **à couverture égale** (100 % des
cellules, la règle de référence disposant d'un repli par moyenne de groupe en
fenêtre expansive pour les cellules sans antécédent).

## 4. Métriques

| Métrique | Définition | Pourquoi elle |
|---|---|---|
| **MAE pondérée** | Erreur absolue moyenne entre taux prédit et taux observé, pondérée par l'effectif de vœux de la cellule | La cible est bornée dans [0, 1] avec des masses aux deux extrêmes ; une erreur quadratique serait moins lisible et plus sensible aux cellules à faible effectif, déjà traitées par la pondération plutôt que par exclusion |
| **ECE** (erreur de calibration attendue) | Écart moyen, pondéré, entre taux prédit et taux observé sur 10 tranches de 0,1 | **La métrique qui compte le plus quand on annonce une probabilité à une personne.** Un modèle peut avoir une bonne erreur moyenne et placer mal les valeurs extrêmes — précisément celles qui décident d'une candidature |
| **Ratio d'impact disparate** | Taux de sélection du groupe rapporté à celui du groupe le mieux servi, seuil des quatre cinquièmes (0,80) | Règle de lecture usuelle de la non-discrimination. Le passage d'un taux continu à une décision binaire se fait au seuil de 0,50 — plus d'une chance sur deux — et non par la médiane, qui produirait 50 % de positifs par groupe par construction et masquerait tout écart |
| **PSI** (indice de stabilité de population) | Déplacement d'une distribution entre deux périodes | Signal précoce de dérive sur les entrées et les sorties, **pas un substitut à la mesure de performance réelle** (ADR 0018) |

**Seuil de décision** : `equite.seuil_impact_disparate` = 0,80 ;
`SEUIL_DECISION_RECOMMANDATION` = 0,50 ; `modele.derive.seuil_reentrainement`
= 0,20 en PSI médian.

## 5. Données d'entraînement et d'évaluation

| | |
|---|---|
| **Source** | Parcoursup, données publiques du Ministère de l'Enseignement supérieur et de la Recherche, millésimes 2018 à 2025, Licence Ouverte v2.0 |
| **Nature** | **Comptages agrégés par formation et par session. Aucune donnée à caractère personnel n'entre dans l'entraînement** — il n'existe pas de base de dossiers de candidats dans ce projet |
| **Grain** | Une cellule = `(formation, session, type de baccalauréat, statut de boursier)` |
| **Label** | `taux = prop_tot_{bg\|bt\|bp}[_brs] / nb_voe_pp_{bg\|bt\|bp}[_brs]`, borné à 1 (ADR 0009). **Observé, jamais simulé** |
| **Fenêtre exploitable** | **Six sessions, 2020-2025, 440 030 cellules.** Le numérateur ventilé par type de baccalauréat n'existe pas avant 2020 : inclure 2018-2019 aurait placé deux sessions sans cible réelle dans l'apprentissage (ADR 0012) |
| **Split** | Strictement **temporel** : entraînement 2020-2023 (286 463 cellules), validation 2024 (76 408), test 2025 (77 159) |
| **Variables** | **46** — 2 dimensions de cellule, 9 attributs de catalogue lus sur la session prédite (liste blanche), 35 compteurs lus sur la session **précédente** |
| **Valeurs manquantes** | 28 425 cellules (6,46 %) sans antécédent N-1 : **jamais imputées**, LightGBM traite l'absence nativement. Colonne la plus touchée : `ran_grp1`, 20,7 % |

**Protection anti-fuite, et comment elle est prouvée.** Le critère de tri n'est
pas « postérieur à la décision » mais « inconnu du lycéen au moment où il
formule son vœu » — plus large, car un compteur de vœux précède l'admission et
reste une fuite. 9 colonnes autorisées sur la session prédite, 35 décalées
d'une session, 73 exclusions motivées (ADR 0013). Le test ne se contente pas de
vérifier la présence des colonnes : il construit une donnée où la valeur de la
session N (999999) est impossible à confondre avec celle de N-1 (40), et
affirme que la table produite porte la seconde. Ramener le décalage de +1 à 0
fait échouer 4 tests et en laisse 342 verts — un test qui aurait fait tomber
des tests sans rapport n'aurait rien démontré de spécifique.

**Ce que le jeu d'entraînement ne représente pas** : les deux millésimes
2018-2019, absents faute de cible ; les formations hors Parcoursup ; les
mentions au baccalauréat, écartées pour les sessions 2020-2021 dont le barème a
changé ; et, par construction du label, tout candidat qui n'a formulé aucun
vœu.

## 6. Analyse quantitative — performance ventilée par sous-population

Toutes les valeurs ci-dessous sont mesurées sur le **test 2025** par
`src/edumatch/models/fairness.py`, à couverture égale entre le modèle et la
règle de référence. « MAE » désigne la MAE pondérée par l'effectif.

### 6.1 Résultat global

| Périmètre | MAE modèle | MAE référence | ECE modèle | ECE référence |
|---|---:|---:|---:|---:|
| Validation 2024 | **0,0690** | 0,0727 | **0,0030** | 0,0141 |
| **Test 2025** | 0,0758 | **0,0701** | 0,0371 | **0,0322** |

**Le modèle bat la règle de référence en validation et la perd en test, sur les
deux métriques à la fois.** Aucune ne rattrape l'autre. En test, il devient
**sur-confiant sur la plage médiane** : il annonce 0,55 là où la réalité
observée est 0,49 ; il reste bien calibré aux extrêmes.

### 6.2 Par type de baccalauréat

| Groupe | n cellules | Effectif | MAE modèle | MAE référence | ECE modèle | ECE référence | Ratio d'impact disparate — modèle | — référence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Général | 26 578 | 7 703 737 | 0,0691 | **0,0642** | 0,0331 | **0,0286** | 1,00 | 1,00 |
| Technologique | 25 805 | 2 276 816 | 0,0845 | **0,0800** | 0,0428 | **0,0394** | 0,66 | 0,67 |
| **Professionnel** | 24 776 | 1 292 925 | **0,0940** | **0,0875** | **0,0520** | 0,0451 | **0,58** | 0,62 |

**L'erreur croît de façon monotone du bac général au bac professionnel, et la
calibration se dégrade dans le même ordre.** Les candidats de bac professionnel
reçoivent donc l'estimation la moins fiable du système — ceux pour qui
l'orientation est le plus contrainte. Le ratio d'impact disparate y est très en
dessous du seuil (0,58), mais la règle de référence échoue au même seuil (0,62)
: l'écart est **structurel au système d'orientation**, pas produit par le
modèle. **Nuance à ne pas escamoter** : le modèle l'amplifie légèrement
(0,58 contre 0,62).

### 6.3 Par statut de boursier

| Groupe | n cellules | Effectif | MAE modèle | MAE référence | ECE modèle | ECE référence | Ratio — modèle | — référence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Non boursier | 39 926 | 9 511 460 | 0,0730 | **0,0674** | 0,0365 | **0,0306** | 1,00 | 1,00 |
| Boursier | 37 233 | 1 762 018 | 0,0862 | **0,0845** | **0,0401** | 0,0410 | **0,88** | 0,92 |

Seule case du tableau où le modèle fait mieux que la référence : la calibration
des cellules boursières (0,0401 contre 0,0410). Le ratio d'impact disparate
passe le seuil des quatre cinquièmes pour les deux, le modèle restant en deçà
de la référence. Rappel : la part de vœux boursiers a connu une rupture de
série (16,3 % à 13,8 % en 2025) — les cellules boursières du test ne décrivent
pas exactement la même population que celles de l'entraînement, et cette
réserve a été écrite **avant** de mesurer.

### 6.4 Par mixité de la formation — la dimension la plus sensible

Groupes construits sur la composition **des candidats**, jamais des admis.

| Groupe | n cellules | Effectif | MAE modèle | MAE référence | ECE modèle | ECE référence | Ratio — modèle | — référence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Mixte, 20 à 80 % de candidates femmes | 54 009 | 8 797 404 | 0,0704 | **0,0671** | 0,0319 | **0,0288** | 0,73 | 0,72 |
| Moins de 20 % de candidates femmes | 12 171 | 793 776 | **0,0943** | 0,0957 | **0,0341** | 0,0416 | 1,00 | 1,00 |
| **Plus de 80 % de candidates femmes** | 10 979 | 1 682 298 | **0,0906** | **0,0733** | **0,0656** | 0,0475 | **0,76** | 0,63 |

**Le résultat central de l'audit d'équité, non atténué.** Sur les formations à
plus de 80 % de candidates femmes, le modèle **sur-annonce les chances
d'admission** : son erreur de calibration y est le double de celle des autres
groupes (0,0656 contre 0,0319 et 0,0341), et **supérieure à celle de la règle
de référence** (0,0475). Son erreur de prédiction y est aussi la plus dégradée
par rapport à la référence de tout le document (0,0906 contre 0,0733, soit 24 %
de plus).

**Deux verdicts opposés, rapportés ensemble parce qu'aucun ne rachète
l'autre** : sur le **ratio d'impact disparate**, le modèle améliore nettement
la référence (0,76 contre 0,63) tout en restant **sous le seuil légal des
quatre cinquièmes** ; sur la **calibration par groupe**, il la dégrade.

**La définition d'équité privilégiée est la calibration par groupe, et elle a
été déclarée avant la mesure.** Ce choix est incompatible avec la parité
démographique dès que les taux de base diffèrent entre groupes — c'est un
théorème d'impossibilité, pas un arbitrage de goût. Ce qu'il sacrifie
explicitement : ni l'égalité des taux de recommandation, ni l'égalité des vrais
positifs entre groupes ne sont garanties. Sur cette définition, **le système
n'est pas équitable sur cette dimension**, et la règle de référence y est plus
équitable que le modèle appris.

### 6.5 Par territoire

19 modalités de territoire mesurées — 18 régions plus une modalité
« (manquant) », 521 cellules sans région renseignée, conservée telle quelle
plutôt que fondue dans une autre. Extraits, du meilleur au pire pour le
modèle :

| Région | n cellules | MAE modèle | MAE référence | ECE modèle | Ratio — modèle | — référence |
|---|---:|---:|---:|---:|---:|---:|
| Réunion | 1 373 | **0,0705** | 0,0761 | 0,0204 | 0,93 | 0,79 |
| Martinique | 705 | **0,1131** | 0,1194 | 0,0390 | 0,68 | 0,69 |
| Corse | 419 | **0,0910** | 0,0942 | 0,0334 | 1,00 | 1,00 |
| Île-de-France | 14 466 | 0,0693 | **0,0666** | 0,0471 | **0,26** | 0,24 |
| Auvergne-Rhône-Alpes | 9 380 | 0,0704 | **0,0624** | 0,0314 | **0,51** | 0,43 |
| Guadeloupe | 736 | 0,1134 | **0,1055** | 0,0432 | 0,91 | 0,87 |
| Mayotte | 246 | 0,0654 | **0,0610** | 0,0423 | **0,25** | 0,25 |

**Lecture.** Le modèle ne bat la référence que dans **3 territoires sur 19**
(Réunion, Martinique, Corse — parmi les plus petits effectifs du tableau). Les
ratios d'impact disparate très bas d'Île-de-France et de Mayotte (0,25) sont
**des faits sur le système d'orientation, pas sur le modèle** : la référence
affiche exactement les mêmes valeurs (0,24 et 0,25). Ils traduisent une
sélectivité réelle très supérieure dans ces territoires, mesurée sur les
données, pas produite par l'apprentissage. Les outre-mer portent en revanche
les erreurs absolues les plus élevées du modèle (Guadeloupe 0,1134, Martinique
0,1131) — une estimation y est structurellement moins fiable.

### 6.6 Bilan de ventilation, en une phrase défendable

**Sur 27 sous-populations mesurées (3 types de bac, 2 statuts de boursier,
3 groupes de mixité, 19 territoires), le modèle appris fait mieux que la règle
de référence en erreur pondérée dans 4 d'entre elles** : les formations à moins
de 20 % de candidates femmes, et trois régions à faible effectif. Il perd les
23 autres.

## 7. Explicabilité

`src/edumatch/models/explain.py` — **TreeSHAP, valeurs de Shapley exactes**.
L'axiome d'efficacité (contributions + valeur de base = prédiction) est vérifié
à **2,1 × 10⁻¹⁵** près sur le modèle réel, et par un test indépendant sur un
modèle jouet dont la prédiction est connue par construction.

**Précalcul complet** des 440 030 cellules : 8,3 minutes, 99,8 Mo. Le nombre de
cellules étant fini et connu à l'avance, le précalcul en lot après chaque
réentraînement borne la latence de l'API par une lecture de fichier, plutôt que
par l'espérance d'un calcul à la demande.

| Variable | Part de l'explication globale |
|---|---:|
| Taux de la session précédente | **33,5 %** |
| `nb_voe_pp` — nombre de vœux, session précédente | 9,1 % |
| Libellé de filière | 8,4 % |
| Département | 7,5 % |
| Capacité de la formation | 6,0 % |
| `prop_tot` — nombre d'admis, session précédente | 5,7 % |

Les trois premières lignes de compteurs (taux précédent, `nb_voe_pp`,
`prop_tot`) sont corrélées par construction — le taux est le quotient des deux
autres — et totalisent **48,3 %** : c'est **une seule information partagée en
trois**, pas trois signaux indépendants.

**Les substituts du genre (`fili`, `select_form`, `dep`, `acad_mies`)
totalisent 14,2 % de l'explication, alors que le genre n'entre jamais dans le
modèle.** C'est la mesure concrète de la discrimination indirecte possible.

**Limites de SHAP, à ne jamais taire** : une valeur de Shapley explique **le
modèle**, pas la réalité ; ce n'est pas une preuve causale. Avec des variables
corrélées par construction, le partage du crédit est mathématiquement défini
mais peut rester contre-intuitif. Une explication locale ne se généralise pas à
une autre cellule. Enfin, l'importance de gain de LightGBM et l'importance
TreeSHAP ne mesurent pas la même chose : la première fait du taux précédent une
variable sept fois plus importante que la deuxième, la seconde la ramène à
33,5 % — **elles ne doivent jamais être citées l'une pour l'autre**.

## 8. Considérations éthiques

1. **Le genre n'entre jamais dans le modèle, et cela ne suffit pas.** La
   filière reconstitue 19,5 % du genre (information mutuelle corrigée de la
   cardinalité par permutation). Retirer les quatre substituts coûte +0,0006 de
   MAE et **dégrade** le ratio d'impact disparate du groupe le plus féminisé
   (0,66 → 0,62 en validation) : l'information est diffuse, pas concentrée.
   **L'exclusion de variables ne peut pas être le seul levier d'équité.**
2. **Risque de renoncement.** Une estimation basse, ou mal comprise, peut
   conduire un adolescent à ne pas candidater. L'effet est invisible : personne
   ne mesure les candidatures qui n'ont pas eu lieu. C'est pourquoi la
   calibration prime ici sur l'erreur moyenne.
3. **Boucle de rétroaction.** Le dénominateur du label est le nombre de vœux,
   c'est-à-dire exactement la grandeur que le système influence. Un profil
   découragé disparaît du dénominateur et déplace le taux appris l'année
   suivante. Risque identifié, instrumenté partiellement par la mesure de dérive
   des prédictions, **non mesuré** faute de millésime post-déploiement.
4. **Le statut de boursier n'est pas une donnée sensible au sens de
   l'article 9** — il n'y figure pas. C'est une donnée personnelle à forte
   portée sociale, qui commande une vigilance sur la discrimination indirecte,
   et c'est une dimension du label : la masquer donnerait à un boursier une
   estimation calculée sur une population qui n'est pas la sienne.
5. **Le contrôle humain est constitutif.** Écartement motivé, bloqué côté client
   et côté serveur ; facteurs présentés à côté du score ; mise en garde portée
   par chaque réponse de l'API. **Le taux d'écartement n'est pas encore mesuré**
   — un contrôle humain qui n'écarterait jamais rien resterait invisible.

## 9. Mises en garde, limites et recommandations

### 9.1 Ce que ce modèle ne doit pas faire croire

- **Il n'est pas meilleur que « le taux de l'an dernier ».** Sur 2025, il est
  moins bon. Un déployeur qui voudrait la meilleure estimation disponible
  aujourd'hui devrait utiliser la règle de référence, pas le modèle appris.
  C'est la conclusion du test de nécessité conduit dans `aipd.md` §3.1, et le
  motif de l'avis défavorable qui y est rendu sur ce terme.
- **Il n'est pas individuel.** Deux candidats de même type de bac, même statut
  de boursier et même territoire reçoivent le même chiffre.
- **Il n'est pas causal.** Ni le modèle ni SHAP ne disent pourquoi une personne
  est admise.

### 9.2 Diagnostic de la dégradation : dérive, pas manque de données

Établi par **deux mesures indépendantes qui convergent** :

- la **courbe d'apprentissage** (10 / 25 / 50 / 100 % du volume
  d'entraînement) : MAE de validation 0,0758 → 0,0723 → 0,0705 → 0,0698, le
  gain marginal se divisant par deux à chaque doublement, et l'écart
  entraînement-validation se refermant de 0,0164 à 0,0039. Le modèle a extrait
  presque tout ce que la fenêtre 2020-2023 pouvait lui apprendre ;
- la **non-stationnarité de la cible**, mesurée sur huit millésimes : la
  moyenne des taux par formation monte jusqu'en 2024 puis fléchit en 2025
  (0,522 → 0,534 → 0,522) pendant que le taux agrégé baisse. La cible bouge.

**Chercher plus de volume ne comblerait pas l'écart.** La fenêtre labellisée est
de toute façon bornée à six sessions. La réponse relève du réentraînement
régulier et de la surveillance, pas de la collecte.

### 9.3 Surveillance de dérive, et son aveu

PSI, seuil 0,20, appliqué à la **médiane** des 46 variables et non au maximum —
appliqué au maximum, il se déclencherait en permanence à cause de deux
variables dont la dérive n'est qu'un changement de libellé à la source
(`region_etab_aff` 0,75, `select_form` 0,35). Un seuil qui se déclenche en
permanence est désactivé au bout d'un mois.

**Aveu à porter dans cette Model Card** : au seuil retenu, **le dispositif
n'aurait pas détecté la dégradation validation → test** que ce document
rapporte. Dérive de la cible 0,0115, des prédictions 0,0174 puis 0,0296 : un
ordre de grandeur sous le seuil. C'est cohérent avec la nature du phénomène —
une dérive du concept, où P(Y|X) se déforme sans que les distributions
marginales bougent, est par construction invisible au PSI. **Le PSI est un
signal précoce sur les entrées et les sorties, pas un substitut à la mesure de
performance réelle.**

### 9.4 Les deux autres termes du score

Le modèle n'est qu'un terme sur trois du score final `affinité × accessibilité
× débouchés`.

- **Débouchés : couverture de 1,4 %.** La chaîne de nomenclatures NAF ↔ ROME ↔
  formation ne relie aucune formation Parcoursup par la clé — aucun millésime
  ne porte de code RNCP, NSF ou ROME. Seul un appariement textuel exact
  fonctionne : 7 libellés sur 712 (1,0 %), 6 017 lignes sur 440 030 (1,4 %),
  relus à la main. **Pour les 98,6 % restants, le terme est marqué indisponible
  avec son motif, jamais mis à zéro en silence.**
- **L'ablation de la source Sirene est impossible, et ce n'est pas un apport
  nul.** Sirene n'étant jamais entrée dans la table de variables, il n'existe
  rien à retirer. Un écart nul mesuré serait un résultat ; une ablation sans
  objet est une **limite du dispositif**, et doit être présentée comme telle.

### 9.5 Réconciliation d'un chiffre qui divergeait entre deux documents

L'analyse exploratoire annonçait que l'écart d'admission entre femmes et hommes,
à formation égale, reste inférieur à 5 points dans **83,8 %** des cas ; l'audit
d'équité rapportait **73,4 %** sur ce qui paraissait être le même objet. **J'ai
recalculé les deux sur la table silver, session 2025, et l'écart est
entièrement expliqué par le filtre d'effectif** :

| Filtre appliqué | Formations retenues | Écart médian | Part sous 5 points |
|---|---:|---:|---:|
| Au moins 30 vœux de chaque sexe (analyse exploratoire) | 11 099 | −0,0004 | **83,79 %** |
| Dénominateur non nul seulement (audit d'équité) | 14 159 | −0,0007 | **73,37 %** |

**Les deux chiffres sont justes ; ils ne portent pas sur la même population.**
Les 3 060 formations ajoutées par la levée du plancher sont de petites
formations, dont le taux par sexe est mécaniquement plus volatil — d'où une part
plus faible d'écarts inférieurs à 5 points. **Chiffre retenu pour cette Model
Card : 73,4 % sur 14 159 formations**, sans plancher, parce que c'est le
périmètre réel de ce que le système recommande ; le 83,8 % est conservé comme
mesure de la même grandeur sur les formations à effectif suffisant, et doit
toujours être cité avec son filtre. La leçon, déjà tirée une fois dans ce
projet sur un autre chiffre : **un ratio par sous-groupe se cite toujours avec
l'effectif de son sous-groupe.**

## 10. Conditions de mise à jour et de retrait

| Événement | Conséquence |
|---|---|
| Publication d'un nouveau millésime Parcoursup | Réentraînement, réévaluation complète, **révision de cette Model Card** |
| PSI médian des 46 variables, de la cible ou des prédictions au-delà de 0,20 | Alerte, examen de cause amont avant tout réentraînement |
| Ajout ou retrait d'une variable | Mesure des substituts rejouée, audit d'équité rejoué, Model Card révisée, analyse d'impact rouverte si l'équité est touchée |
| Bascule de nomenclature NAF (attendue début 2027) | Recalcul de l'agrégat territorial, revue du terme de débouchés |
| Écart d'équité aggravé sur une dimension | Retrait du terme appris du service, retour à la règle de référence |

**Reproduction des chiffres de ce document** :

```bash
PYTHONPATH=src python -m edumatch.models.train        # 6.1, entraînement et comparaison
PYTHONPATH=src python -m edumatch.models.evaluate     # 6.1, calibration
PYTHONPATH=src python -m edumatch.models.fairness     # 6.2 à 6.5, 9.5
PYTHONPATH=src python -m edumatch.models.explain      # 7
PYTHONPATH=src python -m edumatch.models.ablation     # 8.1, 9.4
PYTHONPATH=src python -m edumatch.models.derive       # 9.3
PYTHONPATH=src python -m edumatch.models.registre      # registre de modèles, ligne « Registre de modèles » ci-dessus
```

---
*Étape E42 · version 1.0 du 2026-09-15 · chiffres mesurés sur le test 2025,
ventilés par 27 sous-populations, et rapportés y compris quand ils sont
défavorables au modèle.*
