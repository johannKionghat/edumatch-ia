# Les variables d'entraînement — construction et contrat anti-fuite

**Critère du Bloc 4 concerné (4.1, et 4.3 pour la partie anti-fuite)** :
l'algorithme reçoit des variables cohérentes avec le cahier des charges, et le
protocole d'évaluation est sans fuite temporelle. Ce document décrit ce que
produit `src/edumatch/features/build.py`, comment le décalage temporel est
appliqué et vérifié, et ce qui reste manquant sans être comblé.

Le classement colonne par colonne — ce qui entre, ce qui est exclu et
pourquoi — est arrêté par l'**ADR 0013** et n'est pas reproduit ici. Cette
page documente uniquement l'application de ce classement : le code qui lit
`modele.variables` dans `configs/base.yaml`, assemble la table, et refuse de
continuer si le classement n'est pas respecté.

## Le jeu produit

Sur les huit millésimes réels (`make features` équivalent :
`PYTHONPATH=src python -m edumatch.features.build`) :

| | Valeur |
|---|---:|
| Lignes (cellules) | 440 030 |
| Variables | 46 |
| — dont dimensions de cellule | 2 |
| — dont liste blanche (session prédite) | 9 |
| — dont décalées (session N-1) | 35 |
| Cellules sans antécédent décalé | 28 425 (6,46 %) |
| Colonne la plus souvent manquante | `ran_grp1`, 20,7 % |

Une ligne en entrée (`fait_admission`, le grain du gold produit par l'ADR
0015) produit exactement une ligne en sortie : 440 030 en entrée, 440 030 en
sortie. Aucune jointure de la construction n'est autorisée à changer ce
nombre — `_joindre_sans_fan_out` lève si une source porte plusieurs lignes
pour une même clé, ce qui aurait sinon dupliqué silencieusement des cellules.

Le jeu de mention (huit colonnes `acc_*mention*`, ADR 0013 §3) reste hors de
la table par défaut : `inclure_sous_reserve=True` les ajoute, réservé à
l'ablation (étape à venir du plan d'exécution du projet) qui décidera si leur
gain justifie le risque de contamination des sessions cibles 2021 et 2022.

## Le mécanisme du décalage temporel

Le principe (ADR 0010, appliqué par l'ADR 0013) : une variable ne peut entrer
dans le modèle que si elle est connue au moment où le lycéen formule son
vœu. Deux traitements, jamais mélangés :

- la **liste blanche** (9 colonnes de catalogue — filière, sélectivité,
  académie…) est lue par jointure directe `(session, cod_aff_form)` sur la
  session prédite elle-même : ce sont des attributs déjà publiés au moment du
  vœu ;
- les **35 colonnes décalées** (tous les compteurs de campagne — capacité,
  vœux, admis, rangs) sont lues sur la session **précédente**. La table
  silver est translatée de `+1` sur sa colonne `session` avant la seconde
  jointure : une ligne silver `session = 2024` porte alors `session = 2025`
  et se retrouve alignée sur la cellule de sortie de la session 2025.

Translater la table plutôt que de soustraire 1 côté cellules est un choix
d'implémentation, pas une décision de fond : les deux sont équivalents, et
celui-ci laisse la table de base intacte pour les jointures suivantes.

## Le contrat anti-fuite, et sa validation par mutation

C'est le point le plus critique de l'étape, et celui qui distingue un test
qui prouve quelque chose d'un test qui se contente de vérifier une
apparence.

Un test qui vérifierait seulement la **présence** des bonnes colonnes en
sortie ne prouverait rien : il passerait aussi bien si la jointure décalée
lisait par erreur la session prédite au lieu de la précédente, tant que les
deux sessions portent la même valeur dans les données de test. Le test doit
donc construire une donnée où la valeur **diffère franchement** entre N-1 et
N, pour que l'erreur, si elle existe, se voie.

`tests/data/test_features_build_antifuite.py` fait exactement cela : les
mêmes colonnes (`capa_fin`, `voe_tot`) portent une valeur ordinaire à la
session 2024 (40, 500) et une valeur extrême, impossible à confondre avec la
première, à la session 2025 (999999, 999999). Le test affirme que la table
produite porte 40 et 500, jamais 999999.

**Chacune des trois garanties a été vérifiée par mutation du code**, en plus
des mutations déjà rapportées lors du développement : le code a été modifié
pour casser volontairement la garantie visée, la suite de tests relancée pour
observer quel test échoue, puis le code restauré.

| Mutation | Résultat observé |
|---|---|
| Décalage ramené de `+1` à `+0` (les colonnes « décalées » sont lues sur la session prédite elle-même) | 4 tests échouent — tous ceux qui reposent sur le décalage, dont `test_les_variables_decalees_proviennent_reellement_de_la_session_precedente` — et 342 restent verts |
| `pct_f` (colonne de genre, ADR 0013 §4) et `cod_uai` (substitut, ADR 0013 §5) réintroduits de force dans les colonnes produites | `test_aucune_colonne_de_genre_n_est_presente` échoue, et `test_cod_uai_est_absent_du_jeu_construit` échoue |
| Code restauré après chaque mutation | Suite revenue à 346 tests, 346 succès |

Le premier résultat est celui qui compte le plus : seuls les tests qui
dépendent réellement du décalage échouent, les 342 autres restent verts. Un
test qui aurait échoué en même temps que des tests sans rapport avec le
décalage n'aurait rien démontré de spécifique.

## L'absence d'antécédent : mesurée, jamais comblée

28 425 cellules sur 440 030 (6,46 %) n'ont aucune ligne silver correspondante
à la session N-1, pour deux raisons distinctes :

1. la session cible 2020, dont le millésime N-1 est 2019 — année où
   `prop_tot` n'est pas encore ventilé par type de baccalauréat (ADR 0012,
   ADR 0013 §6) : toutes les cellules de la session 2020 sont concernées pour
   les variables qui en dérivent ;
2. une formation apparue pour la première fois à la session N n'a, par
   construction, aucune ligne silver en N-1.

Dans les deux cas, la valeur reste `<NA>`, jamais imputée. Combler
fabriquerait un antécédent qui n'a pas existé, et LightGBM (ADR 0009,
ADR 0013) traite nativement l'absence — il n'y a donc aucune raison technique
de la masquer. La colonne la plus touchée par des valeurs manquantes,
`ran_grp1`, l'est à 20,7 %, pour des raisons de complétude propres à la
colonne elle-même et non liées au décalage.

## Un piège de nommage bloqué explicitement

`fait_admission` porte déjà, sur la session prédite, `nb_voe_pp` et
`prop_tot` — le numérateur et le dénominateur bruts du label (`features/label.py`,
E19). Ce sont, par malchance de nommage, les mêmes noms que deux colonnes
`decalees` de l'ADR 0013 (la même colonne source, lue à N-1).

Sans contrôle, une jointure pandas standard aurait résolu ce conflit en
renommant silencieusement les deux colonnes (`_x`, `_y`) plutôt que
d'échouer. Le résultat étant exécutable sans erreur, une variable de résultat
de campagne aurait pu se retrouver du mauvais côté du contrat anti-fuite sans
qu'aucun signal ne le révèle — exactement le type de défaut qu'aucun test de
présence de colonnes n'aurait détecté.

La construction refuse désormais explicitement toute homonymie entre les
colonnes de `modele.variables` et les colonnes conservées de
`fait_admission` (`_colonnes_a_construire`), avant la moindre jointure.

## Liste blanche, jamais liste noire

Toute colonne que la construction s'apprête à produire doit relever d'une
des catégories déclarées par `modele.variables` — dimensions de cellule,
liste blanche, décalées, ou décalées sous réserve
(`_verifier_colonnes_licites`). Une colonne qui n'y figurerait pas
n'entrerait jamais par défaut ; la construction s'arrête. C'est une défense
en profondeur : la construction ne lit déjà que les colonnes listées par la
configuration, ce contrôle ne devrait donc jamais se déclencher en usage
normal, mais son absence transformerait une faute de configuration silencieuse
en fuite silencieuse.

## Reproduction

```bash
PYTHONPATH=src python -m edumatch.features.build
```

Écrit `data/processed/parcoursup/variables.parquet` et journalise le rapport
de volumétrie et de complétude (`RapportVariables.resume()`).

```bash
python -m pytest tests/unit/test_features_build.py tests/data/test_features_build_antifuite.py tests/data/test_features_build_run.py -v
```

Suite complète du dépôt : 346 tests, 346 succès (327 avant cette étape, 19
nouveaux). Les mutations décrites plus haut ont été appliquées puis
retirées : elles ne laissent aucun test supplémentaire, seulement la preuve
que les tests existants sont discriminants.

## Limites assumées

- Le classement colonne par colonne n'est pas rouvert ici : voir l'ADR 0013
  pour les 73 exclusions, l'arbitrage sur `cod_uai`, et le point non tranché
  sur `capa_fin`.
- Les huit colonnes de mention restent en réserve, non incluses par défaut :
  leur apport n'est mesurable qu'à l'ablation, étape encore à venir du plan
  d'exécution du projet.
- La construction ne recalcule aucun des dix-neuf pourcentages redondants
  listés par l'ADR 0013 : seules les colonnes sources retenues entrent dans
  le jeu produit à ce stade.

---
*Mise à jour : 2026-08-30 (E20), commit `e34f22a`.*
