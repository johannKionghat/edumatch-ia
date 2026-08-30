# ADR 0017 — Chaîne NAF ↔ ROME ↔ formation sur trois sources réelles, manque Parcoursup déclaré

**Date** : 2026-08-30 · **Statut** : accepté

## Contexte

Le terme « débouchés » du score de matching (E28) doit relier une formation à
une activité économique (code NAF de l'agrégat Sirene, E17). Aucune table
officielle ne relie directement NAF et formation. Diagnostic mené avant
d'écrire une ligne de code : NAF décrit l'activité d'un établissement, ROME
(France Travail) décrit un métier, RNCP relie une certification à un ou
plusieurs métiers ROME, IDÉO (ONISEP) relie une formation à une certification
RNCP. Trois sources publiques, déjà vérifiées séparément (Licence Ouverte
v2.0 pour RNCP et France Travail, ODbL pour IDÉO), permettent d'assembler la
chaîne complète.

Mesuré sur les exports du 2026-08-30 :

| Maillon | Retenus / total | Taux |
|---|---|---:|
| formations IDÉO portant un code RNCP | 3 857 / 5 869 | 65,72 % |
| fiches de l'export ROME couvrant au moins un code ROME | 24 424 / 24 424 | 100 % |
| formations avec RNCP dont la fiche existe dans l'export ROME | 3 605 / 3 857 | 93,47 % |
| codes ROME de l'export RNCP retrouvés dans la table France Travail | 528 / 572 | 92,31 % |
| **chaîne complète, formation IDÉO jusqu'à une division NAF** | 3 605 / 5 869 | **61,42 %** |

Aucun des huit millésimes Parcoursup, ni `dim_formation`, ne porte de code
RNCP, NSF ou ROME (vérifié par inspection directe des colonnes). Cette chaîne
relie donc IDÉO à la NAF, pas Parcoursup à la NAF.

## Options envisagées

1. **Appariement textuel des libellés** (`form_lib_voe_acc`, `fil_lib_voe_acc`
   côté Parcoursup contre le libellé de formation côté IDÉO) — écartée : ce
   serait une correspondance floue, pas une jointure sur clé. Exactement le
   type de correspondance ambiguë que ce projet s'interdit d'arbitrer sans
   mesure (invariant du projet sur les affirmations non vérifiées). Une table
   qui aurait l'air complète, avec un maillon deviné, serait pire qu'une table
   partielle assumée.
2. **Construire la correspondance à la sous-classe NAF (5 caractères)** —
   écartée : aucune source publique ne relie ROME à la sous-classe. La table
   France Travail retenue ne descend qu'à la division (2 chiffres) ; en
   inventer une plus fine reviendrait à fabriquer de la donnée.
3. **Construire la chaîne sur les trois sources réelles disponibles, en
   déclarant le maillon Parcoursup manquant** — retenue.

## Décision

Option 3. `naf_rome_formation.csv` relie une formation IDÉO à une ou
plusieurs divisions NAF, via RNCP et ROME. Le rattachement à Parcoursup n'est
pas fait. La colonne d'état de certification (`rncp_actif`) est exposée, pas
filtrée à cette étape : son usage relève du calcul des débouchés (E28).

## Conséquences

- 61,42 % du référentiel IDÉO atteint une division NAF par la chaîne
  complète ; 38,58 % n'a aucun débouché NAF calculable dans l'état actuel des
  sources.
- Le raccordement à Parcoursup reste à faire et n'est pas simulé : tant qu'il
  n'existe pas, aucun score de matching ne peut s'appuyer sur cette chaîne
  sans un maillon supplémentaire, hors du périmètre de cette étape.
- La correspondance ROME/NAF reste à la division : le rattachement à un
  établissement Sirene (sous-classe) perd la granularité fine de l'activité.
- **Le seuil qui ferait reconsidérer cette décision** : la publication d'une
  table ROME ↔ NAF à la sous-classe par France Travail ou l'INSEE, ou
  l'apparition d'un identifiant de certification (RNCP, NSF ou ROME) dans un
  futur millésime Parcoursup. Tant qu'aucun de ces deux faits ne se produit,
  le manque reste déclaré plutôt que comblé par un appariement textuel.
