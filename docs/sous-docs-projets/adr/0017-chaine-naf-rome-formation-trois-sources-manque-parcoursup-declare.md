# ADR 0017 — Chaîne NAF ↔ ROME ↔ formation sur trois sources réelles, manque Parcoursup déclaré

Statut : accepté (2026-08-30)

## Contexte

Le terme « débouchés » du score de matching (E28) doit relier une formation
à une activité économique (code NAF de l'agrégat Sirene, E17). Aucune table
officielle ne relie directement NAF et formation. NAF décrit l'activité d'un
établissement, ROME (France Travail) décrit un métier, RNCP relie une
certification à un ou plusieurs métiers ROME, IDÉO (ONISEP) relie une
formation à une certification RNCP — trois sources publiques, déjà
vérifiées séparément (Licence Ouverte v2.0 pour RNCP et France Travail,
ODbL pour IDÉO). Mesuré sur les exports du 2026-08-30 : 3 857 formations
IDÉO sur 5 869 portent un code RNCP (65,72 %) ; l'export ROME couvre 100 %
de ses fiches ; 93,47 % des formations avec RNCP trouvent leur fiche dans
l'export ROME ; 92,31 % des codes ROME de l'export RNCP se retrouvent dans
la table France Travail ; au total, la chaîne complète (formation IDÉO
jusqu'à une division NAF) atteint 61,42 % (3 605 / 5 869). Aucun des huit
millésimes Parcoursup, ni `dim_formation`, ne porte de code RNCP, NSF ou
ROME (vérifié par inspection directe des colonnes) : la chaîne relie donc
IDÉO à la NAF, pas Parcoursup à la NAF.

## Décision

Je construis `naf_rome_formation.csv` sur les trois sources réelles
disponibles, en déclarant le maillon Parcoursup manquant. Il relie une
formation IDÉO à une ou plusieurs divisions NAF, via RNCP et ROME. La
colonne d'état de certification (`rncp_actif`) est exposée, pas filtrée à
cette étape.

## Alternatives écartées

- Appariement textuel des libellés (Parcoursup contre IDÉO) : une
  correspondance floue, pas une jointure sur clé — une table qui aurait
  l'air complète, avec un maillon deviné, serait pire qu'une table
  partielle assumée.
- Construire la correspondance à la sous-classe NAF (5 caractères) : aucune
  source publique ne relie ROME à la sous-classe, en inventer une plus fine
  reviendrait à fabriquer de la donnée.

## Conséquences

61,42 % du référentiel IDÉO atteint une division NAF ; 38,58 % n'a aucun
débouché calculable dans l'état actuel des sources. Le raccordement à
Parcoursup reste à faire et n'est pas simulé : tant qu'il n'existe pas,
aucun score de matching ne peut s'appuyer sur cette chaîne sans un maillon
supplémentaire. La correspondance ROME/NAF reste à la division, ce qui fait
perdre la granularité fine de l'activité.

Je reviendrais sur ce choix si France Travail ou l'INSEE publiait une table
ROME ↔ NAF à la sous-classe, ou si un futur millésime Parcoursup faisait
apparaître un identifiant de certification.
