# Model Card, EduMatch-IA, terme d'accessibilité

**Critère servi** : Bloc 1, 1.9, livrable obligatoire · **Version** : 1.0 ·
**Date** : 2026-09-15 · **Format** : Mitchell et al., 2018 (*Model Cards for
Model Reporting*).

Ce document n'est pas une fiche produit. Le résultat central est énoncé dès
l'ouverture : sur la session de test 2025, le modèle appris ne bat pas la
règle de référence qu'il devait battre, ni en précision, ni en calibration,
ni dans la quasi-totalité des sous-populations.

---

## 1. Détails du modèle

| | |
|---|---|
| **Nom** | EduMatch-IA, terme d'accessibilité |
| **Version** | commit d'entraînement `7a70366`, hyperparamètres figés par `configs/base.yaml` |
| **Date** | entraîné le 2026-08-30, audité en équité et explicabilité le même jour, dérive mesurée le 2026-09-01 |
| **Type** | Régression de gradient boosté sur arbres, LightGBM, `LGBMRegressor` |
| **Sortie** | Taux d'admission estimé dans [0, 1] pour une cellule (formation, session, type de baccalauréat, statut de boursier), écrêté par `matching/score.py::borner_accessibilite` |
| **Hyperparamètres** | `num_leaves` 31, `max_depth` 8, `learning_rate` 0,05, `min_child_samples` 20, `reg_alpha` 0,1, `reg_lambda` 0,1, `n_estimators` 2 000, arrêt anticipé à 100 tours, réglé sur la seule validation 2024 |
| **Pondération** | Chaque cellule pèse son effectif de vœux (ADR 0009) : une cellule à 3 vœux ne vaut pas une cellule à 500 |
| **Code** | `src/edumatch/models/train.py`, `evaluate.py`, `explain.py`, `fairness.py`, `ablation.py`, `derive.py` |
| **Suivi d'expériences** | MLflow, expérience `edumatch-accessibilite`, paramètres, métriques et empreinte du commit à chaque exécution |
| **Registre de modèles** | Version 1 de `edumatch-accessibilite`, enregistrée par `models/registre.py`. Aucun alias de production posé : l'étiquette `statut_evaluation` dit en clair qu'elle ne bat pas le plancher en test, voir §6.1 |
| **Licence des données d'entraînement** | Licence Ouverte v2.0 (Etalab), voir `registre-sources.md` |
| **Contact** | Le responsable du modèle et le délégué à la protection des données (`plan-gouvernance.md` §3) |

**Pourquoi LightGBM.** Les données sont tabulaires, hétérogènes, avec des
valeurs manquantes structurelles (6,46 % des cellules sans antécédent N-1).
Un réseau de neurones aurait exigé une imputation injustifiée et n'aurait pas
permis d'explication exacte : TreeSHAP calcule les valeurs de Shapley de
façon exacte sur un modèle à arbres, en temps polynomial, là où un réseau
imposerait une approximation. L'explicabilité étant une obligation juridique,
ce point a tranché.

## 2. Usage prévu

Assister un conseiller d'orientation qui accompagne un lycéen de terminale
dans la construction de sa liste de vœux : pour chaque formation, une
estimation du taux d'admission de la catégorie du lycéen, avec les facteurs
qui portent cette estimation. Utilisateurs prévus : conseillers et personnels
d'accompagnement du déployeur. Le lycéen est destinataire, jamais opérateur
direct dans le périmètre construit.

Le modèle prédit la propriété d'une cellule, pas d'une personne. Phrase à
employer : « le taux d'admission observé, l'an dernier, des bacheliers
technologiques boursiers dans cette formation était de X %, il est estimé à
Y % cette année », jamais « vous avez Y % de chances ».

**Usages hors périmètre, explicitement proscrits**

| Usage | Pourquoi |
|---|---|
| Prendre ou préparer une décision d'admission | Le modèle prédit un taux de cohorte, jamais un dossier individuel |
| Restituer une probabilité individuelle | Aucune variable individuelle : même bac, même statut, même département donnent le même chiffre |
| Déconseiller une formation | Le système ordonne, n'interdit pas (`aipd.md` §6.2) |
| Servir un public de moins de quinze ans | Rouvrirait l'analyse d'impact, consentement parental requis |
| Alimenter un classement public d'établissements | L'accessibilité n'est pas la qualité, l'agrégation produirait un palmarès infondé |
| Fonctionner sans supervision humaine | L'écran conseiller et l'écartement motivé sont constitutifs, pas une option |

## 3. Facteurs

Quatre dimensions déclarées (`configs/base.yaml`, `equite.dimensions`) : type
de baccalauréat et statut de boursier (dimensions du label lui-même),
territoire (19 modalités), et genre sous forme de mixité des candidats
(`voe_tot_f / voe_tot`, jamais la composition des admis), en trois groupes :
moins de 20 % de candidates, mixte 20-80 %, plus de 80 %.

Le genre n'est jamais une entrée du modèle, invariant vérifié par
`tests/data/test_features_build_antifuite.py`, discriminance établie par
mutation. Il est lu par le seul module d'audit, depuis la table silver, pour
la seule finalité de mesure d'équité : c'est la résolution du paradoxe où
mesurer l'équité exige l'attribut protégé alors que la minimisation pousse à
ne pas le collecter.

Toutes les mesures portent sur la session 2025, jamais consultée pendant le
réglage, et comparent le modèle à la règle de référence à couverture égale
(100 % des cellules, la référence disposant d'un repli par moyenne de groupe
en fenêtre expansive pour les cellules sans antécédent).

## 4. Métriques

| Métrique | Définition | Pourquoi |
|---|---|---|
| MAE pondérée | Erreur absolue moyenne entre taux prédit et observé, pondérée par l'effectif de vœux | La cible est bornée dans [0, 1] avec des masses aux extrêmes, moins sensible aux cellules à faible effectif que l'erreur quadratique |
| ECE | Écart moyen pondéré entre taux prédit et observé sur 10 tranches de 0,1 | Ce qui compte quand on annonce une probabilité à une personne : une bonne erreur moyenne peut cacher de mauvaises valeurs extrêmes |
| Ratio d'impact disparate | Taux de sélection du groupe rapporté au groupe le mieux servi, seuil des quatre cinquièmes (0,80) | Règle usuelle de non-discrimination ; le seuil de décision est 0,50, pas la médiane, qui masquerait tout écart |
| PSI | Déplacement d'une distribution entre deux périodes | Signal précoce de dérive sur entrées et sorties, pas un substitut à la mesure de performance réelle (ADR 0018) |

**Seuils** : `equite.seuil_impact_disparate` 0,80 ;
`SEUIL_DECISION_RECOMMANDATION` 0,50 ; `modele.derive.seuil_reentrainement`
0,20 en PSI médian.

## 5. Données d'entraînement et d'évaluation

| | |
|---|---|
| **Source** | Parcoursup, MESR, millésimes 2018-2025, Licence Ouverte v2.0 |
| **Nature** | Comptages agrégés par formation et session, aucune donnée personnelle |
| **Grain** | (formation, session, type de baccalauréat, statut de boursier) |
| **Label** | `taux = prop_tot_{bg\|bt\|bp}[_brs] / nb_voe_pp_{bg\|bt\|bp}[_brs]`, borné à 1 (ADR 0009), observé, jamais simulé |
| **Fenêtre exploitable** | Six sessions, 2020-2025, 440 030 cellules. Le numérateur ventilé par type de bac n'existe pas avant 2020 (ADR 0012) |
| **Split** | Strictement temporel : entraînement 2020-2023 (286 463 cellules), validation 2024 (76 408), test 2025 (77 159) |
| **Variables** | 46 : 2 dimensions de cellule, 9 attributs de catalogue sur la session prédite (liste blanche), 35 compteurs sur la session précédente |
| **Valeurs manquantes** | 28 425 cellules (6,46 %) sans antécédent N-1, jamais imputées, LightGBM traite l'absence nativement. Colonne la plus touchée : `ran_grp1`, 20,7 % |

**Protection anti-fuite.** Le critère de tri est « inconnu du lycéen au
moment où il formule son vœu », plus large que « postérieur à la décision »,
car un compteur de vœux précède l'admission et reste une fuite. 9 colonnes
autorisées sur la session prédite, 35 décalées d'une session, 73 exclusions
motivées (ADR 0013). Le test construit une donnée où la valeur de session N
(999999) est impossible à confondre avec N-1 (40) : ramener le décalage de +1
à 0 fait échouer 4 tests sur 342.

**Ce que le jeu d'entraînement ne représente pas** : 2018-2019, absents
faute de cible ; les formations hors Parcoursup ; les mentions au
baccalauréat, écartées pour 2020-2021 dont le barème a changé ; tout candidat
n'ayant formulé aucun vœu.

## 6. Analyse quantitative, performance ventilée par sous-population

Mesures sur le test 2025 (`models/fairness.py`), à couverture égale entre
modèle et référence. « MAE » désigne la MAE pondérée par l'effectif.

### 6.1 Résultat global

| Périmètre | MAE modèle | MAE référence | ECE modèle | ECE référence |
|---|---:|---:|---:|---:|
| Validation 2024 | 0,0690 | 0,0727 | 0,0030 | 0,0141 |
| Test 2025 | 0,0758 | 0,0701 | 0,0371 | 0,0322 |

Le modèle bat la référence en validation et la perd en test, sur les deux
métriques. En test, il devient sur-confiant sur la plage médiane (0,55 pour
une réalité de 0,49), restant bien calibré aux extrêmes.

### 6.2 Par type de baccalauréat

| Groupe | n cellules | Effectif | MAE modèle | MAE référence | ECE modèle | ECE référence | Ratio modèle | Ratio référence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Général | 26 578 | 7 703 737 | 0,0691 | 0,0642 | 0,0331 | 0,0286 | 1,00 | 1,00 |
| Technologique | 25 805 | 2 276 816 | 0,0845 | 0,0800 | 0,0428 | 0,0394 | 0,66 | 0,67 |
| Professionnel | 24 776 | 1 292 925 | 0,0940 | 0,0875 | 0,0520 | 0,0451 | 0,58 | 0,62 |

L'erreur et la mauvaise calibration croissent du bac général au bac
professionnel : les candidats de bac professionnel reçoivent l'estimation la
moins fiable. Le ratio (0,58) est très en dessous du seuil, mais la
référence échoue au même seuil (0,62), un écart structurel au système
d'orientation. Nuance : le modèle l'amplifie légèrement.

### 6.3 Par statut de boursier

| Groupe | n cellules | Effectif | MAE modèle | MAE référence | ECE modèle | ECE référence | Ratio modèle | Ratio référence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Non boursier | 39 926 | 9 511 460 | 0,0730 | 0,0674 | 0,0365 | 0,0306 | 1,00 | 1,00 |
| Boursier | 37 233 | 1 762 018 | 0,0862 | 0,0845 | 0,0401 | 0,0410 | 0,88 | 0,92 |

Seule case où le modèle bat la référence : la calibration des cellules
boursières. Les deux passent le seuil des quatre cinquièmes, le modèle
restant en deçà de la référence. La part de vœux boursiers a connu une
rupture de série (16,3 % à 13,8 % en 2025) : les cellules boursières du test
ne décrivent pas la même population que l'entraînement.

### 6.4 Par mixité de la formation, la dimension la plus sensible

Groupes construits sur la composition des candidats, jamais des admis.

| Groupe | n cellules | Effectif | MAE modèle | MAE référence | ECE modèle | ECE référence | Ratio modèle | Ratio référence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Mixte, 20-80 % de candidates | 54 009 | 8 797 404 | 0,0704 | 0,0671 | 0,0319 | 0,0288 | 0,73 | 0,72 |
| Moins de 20 % de candidates | 12 171 | 793 776 | 0,0943 | 0,0957 | 0,0341 | 0,0416 | 1,00 | 1,00 |
| Plus de 80 % de candidates | 10 979 | 1 682 298 | 0,0906 | 0,0733 | 0,0656 | 0,0475 | 0,76 | 0,63 |

Résultat central de l'audit d'équité, non atténué : sur les formations à plus
de 80 % de candidates, le modèle sur-annonce les chances d'admission, son
erreur de calibration est le double des autres groupes et supérieure à la
référence, et son erreur de prédiction y est la plus dégradée du document
(24 % de plus que la référence).

Deux verdicts opposés, rapportés ensemble : sur le ratio d'impact disparate,
le modèle améliore nettement la référence (0,76 contre 0,63) tout en restant
sous le seuil ; sur la calibration par groupe, il la dégrade.

La définition d'équité privilégiée est la calibration par groupe, déclarée
avant la mesure, incompatible avec la parité démographique dès que les taux
de base diffèrent (théorème d'impossibilité, pas un arbitrage de goût). Elle
ne garantit ni l'égalité des taux de recommandation, ni l'égalité des vrais
positifs entre groupes. Sur cette définition, le système n'est pas équitable
sur cette dimension, et la référence y est plus équitable que le modèle.

### 6.5 Par territoire

19 modalités (18 régions plus « manquant », 521 cellules sans région
renseignée, conservée telle quelle). Extraits, du meilleur au pire pour le
modèle :

| Région | n cellules | MAE modèle | MAE référence | ECE modèle | Ratio modèle | Ratio référence |
|---|---:|---:|---:|---:|---:|---:|
| Réunion | 1 373 | 0,0705 | 0,0761 | 0,0204 | 0,93 | 0,79 |
| Martinique | 705 | 0,1131 | 0,1194 | 0,0390 | 0,68 | 0,69 |
| Corse | 419 | 0,0910 | 0,0942 | 0,0334 | 1,00 | 1,00 |
| Île-de-France | 14 466 | 0,0693 | 0,0666 | 0,0471 | 0,26 | 0,24 |
| Auvergne-Rhône-Alpes | 9 380 | 0,0704 | 0,0624 | 0,0314 | 0,51 | 0,43 |
| Guadeloupe | 736 | 0,1134 | 0,1055 | 0,0432 | 0,91 | 0,87 |
| Mayotte | 246 | 0,0654 | 0,0610 | 0,0423 | 0,25 | 0,25 |

Le modèle ne bat la référence que dans 3 territoires sur 19 (Réunion,
Martinique, Corse, parmi les plus petits effectifs). Les ratios très bas
d'Île-de-France et de Mayotte (0,25) sont des faits sur le système
d'orientation, pas sur le modèle : la référence affiche les mêmes valeurs
(0,24 et 0,25), une sélectivité réelle mesurée sur les données. Les outre-mer
portent les erreurs absolues les plus élevées (Guadeloupe 0,1134, Martinique
0,1131) : une estimation y est structurellement moins fiable.

### 6.6 Bilan

Sur 27 sous-populations mesurées (3 types de bac, 2 statuts de boursier, 3
groupes de mixité, 19 territoires), le modèle appris fait mieux que la règle
de référence dans 4 : les formations à moins de 20 % de candidates femmes, et
trois régions à faible effectif. Il perd les 23 autres.

## 7. Explicabilité

`models/explain.py`, TreeSHAP, valeurs de Shapley exactes. L'axiome
d'efficacité (contributions + valeur de base = prédiction) est vérifié à
2,1 × 10⁻¹⁵ près sur le modèle réel, et par un test indépendant sur un
modèle jouet dont la prédiction est connue.

Précalcul complet des 440 030 cellules : 8,3 minutes, 99,8 Mo. Le nombre de
cellules étant fini et connu, le précalcul en lot après chaque
réentraînement borne la latence de l'API par une lecture de fichier.

| Variable | Part de l'explication globale |
|---|---:|
| Taux de la session précédente | 33,5 % |
| `nb_voe_pp` (nombre de vœux, session précédente) | 9,1 % |
| Libellé de filière | 8,4 % |
| Département | 7,5 % |
| Capacité de la formation | 6,0 % |
| `prop_tot` (nombre d'admis, session précédente) | 5,7 % |

Les trois premières lignes de compteurs sont corrélées par construction (le
taux est le quotient des deux autres) et totalisent 48,3 % : une seule
information partagée en trois. Les substituts du genre (`fili`,
`select_form`, `dep`, `acad_mies`) totalisent 14,2 % de l'explication, alors
que le genre n'entre jamais dans le modèle : c'est la mesure concrète de la
discrimination indirecte possible.

**Limites de SHAP** : une valeur de Shapley explique le modèle, pas la
réalité, ce n'est pas une preuve causale. Avec des variables corrélées, le
partage du crédit est défini mathématiquement mais peut rester
contre-intuitif. Une explication locale ne se généralise pas à une autre
cellule. L'importance de gain de LightGBM et l'importance TreeSHAP ne
mesurent pas la même chose (facteur sept sur le taux précédent) : elles ne
doivent jamais être citées l'une pour l'autre.

## 8. Considérations éthiques

1. Le genre n'entre jamais dans le modèle, et cela ne suffit pas : la
   filière reconstitue 19,5 % du genre. Retirer les quatre substituts coûte
   +0,0006 de MAE et dégrade le ratio du groupe le plus féminisé (0,66 →
   0,62 en validation), l'information étant diffuse. L'exclusion de
   variables ne peut pas être le seul levier d'équité.
2. Risque de renoncement : une estimation basse ou mal comprise peut faire
   renoncer un adolescent, effet invisible. La calibration prime donc sur
   l'erreur moyenne.
3. Boucle de rétroaction : le dénominateur du label est le nombre de vœux,
   la grandeur influencée. Risque identifié, instrumenté partiellement par
   la dérive des prédictions, non mesuré faute de millésime post-déploiement.
4. Le statut de boursier n'est pas une donnée sensible au sens de l'article
   9 : c'est une donnée personnelle à forte portée sociale et une dimension
   du label, la masquer donnerait à un boursier une estimation calculée sur
   une population qui n'est pas la sienne.
5. Le contrôle humain est constitutif : écartement motivé bloqué côté
   client et serveur, facteurs présentés à côté du score, mise en garde
   portée par chaque réponse de l'API. Le taux d'écartement n'est pas encore
   mesuré.

## 9. Mises en garde, limites et recommandations

**Ce que ce modèle ne doit pas faire croire.** Il n'est pas meilleur que « le
taux de l'an dernier » : sur 2025, il est moins bon, conclusion du test de
nécessité de `aipd.md` §3.1. Il n'est pas individuel : même bac, même statut,
même territoire donnent le même chiffre. Il n'est pas causal : ni le modèle
ni SHAP ne disent pourquoi une personne est admise.

**Dérive, pas manque de données.** Deux mesures convergent : la courbe
d'apprentissage (10/25/50/100 % du volume) donne une MAE de validation
0,0758 → 0,0723 → 0,0705 → 0,0698, le gain marginal se divisant par deux à
chaque doublement, l'écart entraînement-validation se refermant de 0,0164 à
0,0039, le modèle ayant extrait presque tout ce que 2020-2023 pouvait lui
apprendre. La cible elle-même n'est pas stationnaire : la moyenne des taux
par formation monte jusqu'en 2024 puis fléchit en 2025 (0,522 → 0,534 →
0,522) pendant que le taux agrégé baisse. Chercher plus de volume ne
comblerait pas l'écart, la fenêtre labellisée étant bornée à six sessions ;
la réponse relève du réentraînement régulier, pas de la collecte.

**Surveillance de dérive, et son aveu.** PSI, seuil 0,20, appliqué à la
médiane des 46 variables et non au maximum, sans quoi il se déclencherait en
permanence à cause de deux variables dont la dérive n'est qu'un changement
de libellé à la source (`region_etab_aff` 0,75, `select_form` 0,35). Aveu à
porter : au seuil retenu, le dispositif n'aurait pas détecté la dégradation
validation → test (dérive de la cible 0,0115, des prédictions 0,0174 puis
0,0296, un ordre de grandeur sous le seuil), cohérent avec une dérive du
concept, où P(Y|X) se déforme sans que les distributions marginales bougent,
invisible au PSI.

**Les deux autres termes du score.** Débouchés : couverture de 1,4 %, la
chaîne de nomenclatures ne reliant aucune formation Parcoursup par la clé.
Seul un appariement textuel exact fonctionne, 7 libellés sur 712 (1,0 %),
6 017 lignes sur 440 030 (1,4 %), relus à la main ; pour le reste, le terme
est marqué indisponible avec son motif. L'ablation de la source Sirene est
impossible : Sirene n'étant jamais entré dans la table de variables, il
n'existe rien à retirer, ce n'est pas un apport nul mesuré mais une mesure
sans objet.

**Réconciliation d'un chiffre divergent entre deux documents.** L'analyse
exploratoire annonçait un écart d'admission femmes/hommes sous 5 points dans
83,8 % des cas ; l'audit d'équité rapportait 73,4 % sur ce qui paraissait le
même objet. Recalculé sur la table silver, session 2025, l'écart s'explique
par le filtre d'effectif :

| Filtre appliqué | Formations retenues | Écart médian | Part sous 5 points |
|---|---:|---:|---:|
| Au moins 30 vœux de chaque sexe (analyse exploratoire) | 11 099 | −0,0004 | 83,79 % |
| Dénominateur non nul seulement (audit d'équité) | 14 159 | −0,0007 | 73,37 % |

Les deux chiffres sont justes, ils ne portent pas sur la même population :
les 3 060 formations ajoutées sont de petites formations, au taux par sexe
plus volatil. Chiffre retenu pour cette Model Card : 73,4 % sur 14 159
formations, le périmètre réel recommandé ; 83,8 % reste une mesure de la
même grandeur sur les formations à effectif suffisant, à citer avec son
filtre. Leçon : un ratio par sous-groupe se cite toujours avec l'effectif de
son sous-groupe.

## 10. Conditions de mise à jour et de retrait

| Événement | Conséquence |
|---|---|
| Publication d'un nouveau millésime Parcoursup | Réentraînement, réévaluation complète, révision de cette Model Card |
| PSI médian des 46 variables, de la cible ou des prédictions au-delà de 0,20 | Alerte, examen de cause amont avant réentraînement |
| Ajout ou retrait d'une variable | Mesure des substituts et audit d'équité rejoués, Model Card révisée, AIPD rouverte si l'équité est touchée |
| Bascule de nomenclature NAF (attendue début 2027) | Recalcul de l'agrégat territorial, revue du terme de débouchés |
| Écart d'équité aggravé sur une dimension | Retrait du terme appris du service, retour à la règle de référence |

**Reproduction des chiffres de ce document**

```bash
PYTHONPATH=src python -m edumatch.models.train        # 6.1, entraînement et comparaison
PYTHONPATH=src python -m edumatch.models.evaluate     # 6.1, calibration
PYTHONPATH=src python -m edumatch.models.fairness     # 6.2 à 6.5, 9.5
PYTHONPATH=src python -m edumatch.models.explain      # 7
PYTHONPATH=src python -m edumatch.models.ablation     # 8.1, 9.4
PYTHONPATH=src python -m edumatch.models.derive       # 9.3
PYTHONPATH=src python -m edumatch.models.registre     # registre de modèles
```

---
*Étape E42, version 1.0 du 2026-09-15, chiffres mesurés sur le test 2025,
ventilés par 27 sous-populations, rapportés y compris quand ils sont
défavorables au modèle.*
