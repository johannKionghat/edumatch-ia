# Les variables d'entraînement — construction et contrat anti-fuite

Blocs 4.1 et 4.3. Ce document décrit ce que produit
`src/edumatch/features/build.py` : comment le décalage temporel est appliqué
et vérifié, et ce qui reste manquant sans être comblé.

Le classement colonne par colonne (ce qui entre, ce qui est exclu, pourquoi)
est dans l'ADR 0013 et n'est pas repris ici. Cette page documente
l'application de ce classement : le code lit `modele.variables` dans
`configs/base.yaml`, assemble la table, et s'arrête si le classement n'est
pas respecté.

## Le jeu produit

Sur les huit millésimes réels (`PYTHONPATH=src python -m edumatch.features.build`) :

| | Valeur |
|---|---:|
| Lignes (cellules) | 440 030 |
| Variables | 46 |
| — dont dimensions de cellule | 2 |
| — dont liste blanche (session prédite) | 9 |
| — dont décalées (session N-1) | 35 |
| Cellules sans antécédent décalé | 28 425 (6,46 %) |
| Colonne la plus souvent manquante | `ran_grp1`, 20,7 % |

Une ligne en entrée (`fait_admission`, ADR 0015) produit exactement une ligne
en sortie : 440 030 en entrée, 440 030 en sortie. `_joindre_sans_fan_out`
arrête le pipeline si une source porte plusieurs lignes pour une même clé,
ce qui dupliquerait silencieusement des cellules sinon.

Le jeu de mention (huit colonnes `acc_*mention*`, ADR 0013 §3) reste hors de
la table par défaut : `inclure_sous_reserve=True` les ajoute, réservé à
l'ablation qui décide si leur gain justifie le risque de contamination des
sessions cibles 2021 et 2022.

## Le mécanisme du décalage temporel

Le principe (ADR 0010, ADR 0013) : une variable n'entre dans le modèle que
si elle est connue au moment où le lycéen formule son vœu. Deux
traitements :

- la **liste blanche** (9 colonnes de catalogue : filière, sélectivité,
  académie…) est lue par jointure directe `(session, cod_aff_form)` sur la
  session prédite elle-même — ce sont des attributs déjà publiés au moment
  du vœu ;
- les **35 colonnes décalées** (tous les compteurs de campagne : capacité,
  vœux, admis, rangs) sont lues sur la session **précédente**. La table
  silver est translatée de `+1` sur sa colonne `session` avant la seconde
  jointure : une ligne silver `session = 2024` porte alors `session = 2025`
  et s'aligne sur la cellule de sortie de la session 2025.

Translater la table plutôt que soustraire 1 côté cellules est un choix
d'implémentation : les deux reviennent au même, celui-ci laisse la table de
base intacte pour les jointures suivantes.

## Le contrat anti-fuite, vérifié par mutation

Un test qui vérifierait juste la **présence** des bonnes colonnes en sortie
ne prouve rien : il passerait même si la jointure décalée lisait par erreur
la session prédite au lieu de la précédente, tant que les deux sessions
portent la même valeur en test. Il faut une donnée où la valeur **diffère
franchement** entre N-1 et N.

`tests/data/test_features_build_antifuite.py` fait ça : `capa_fin` et
`voe_tot` portent une valeur ordinaire à la session 2024 (40, 500) et une
valeur extrême à la session 2025 (999999, 999999). Le test vérifie que la
table produite porte 40 et 500, jamais 999999.

J'ai vérifié les trois garanties par mutation du code : je casse
volontairement le comportement visé, je relance les tests pour voir lequel
échoue, puis je restaure.

| Mutation | Résultat observé |
|---|---|
| Décalage ramené de `+1` à `+0` (les colonnes « décalées » lues sur la session prédite elle-même) | 4 tests échouent — dont `test_les_variables_decalees_proviennent_reellement_de_la_session_precedente` — et 342 restent verts |
| `pct_f` (genre, ADR 0013 §4) et `cod_uai` (substitut, ADR 0013 §5) réintroduits de force | `test_aucune_colonne_de_genre_n_est_presente` et `test_cod_uai_est_absent_du_jeu_construit` échouent |
| Code restauré après chaque mutation | Suite revenue à 346 tests, 346 succès |

Le premier résultat compte le plus : seuls les tests qui dépendent
réellement du décalage échouent, les 342 autres restent verts. Un test qui
aurait échoué avec des tests sans rapport n'aurait rien démontré.

## L'absence d'antécédent : mesurée, jamais comblée

28 425 cellules sur 440 030 (6,46 %) n'ont aucune ligne silver à la session
N-1, pour deux raisons :

1. la session cible 2020, dont le millésime N-1 est 2019 — année où
   `prop_tot` n'est pas encore ventilé par type de bac (ADR 0012, ADR 0013
   §6) ;
2. une formation apparue pour la première fois à la session N n'a par
   construction aucune ligne silver en N-1.

Dans les deux cas la valeur reste `<NA>`, jamais imputée. Combler
fabriquerait un antécédent qui n'a jamais existé, et LightGBM traite
nativement l'absence. La colonne la plus touchée, `ran_grp1`, l'est à
20,7 %, pour des raisons de complétude propres à la colonne, sans lien avec
le décalage.

## Un piège de nommage bloqué explicitement

`fait_admission` porte déjà, sur la session prédite, `nb_voe_pp` et
`prop_tot` — le numérateur et le dénominateur bruts du label
(`features/label.py`, E19). Par malchance de nommage, ce sont les mêmes noms
que deux colonnes `decalees` de l'ADR 0013 (la même colonne source, lue à
N-1).

Sans contrôle, une jointure pandas standard aurait résolu ce conflit en
renommant silencieusement les deux colonnes (`_x`, `_y`) plutôt que
d'échouer, et une variable de résultat de campagne aurait pu se retrouver du
mauvais côté du contrat anti-fuite sans qu'aucun signal ne le révèle. La
construction refuse désormais toute homonymie entre les colonnes de
`modele.variables` et les colonnes conservées de `fait_admission`
(`_colonnes_a_construire`), avant toute jointure.

## Liste blanche, jamais liste noire

Toute colonne que la construction s'apprête à produire doit relever d'une
catégorie déclarée par `modele.variables` — dimensions de cellule, liste
blanche, décalées, ou décalées sous réserve (`_verifier_colonnes_licites`).
Une colonne qui n'y figure pas n'entre jamais par défaut : la construction
s'arrête. En usage normal ce contrôle ne devrait jamais se déclencher, mais
son absence transformerait une faute de configuration en fuite silencieuse.

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

## Limites

- Le classement colonne par colonne n'est pas rouvert ici : voir l'ADR 0013
  pour les 73 exclusions, l'arbitrage sur `cod_uai`, et le point non tranché
  sur `capa_fin`.
- Les huit colonnes de mention restent en réserve, non incluses par défaut :
  leur apport n'est mesurable qu'à l'ablation.
- La construction ne recalcule aucun des dix-neuf pourcentages redondants
  listés par l'ADR 0013 : seules les colonnes sources retenues entrent dans
  le jeu produit à ce stade.

---
*Mise à jour : 2026-08-30 (E20), commit `e34f22a`.*
