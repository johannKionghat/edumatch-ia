# ADR 0008 — Conserver les lignes d'entrepreneur individuel dans l'échantillon Sirene, sous intérêt légitime

**Date** : 2026-08-29 · **Statut** : accepté

## Contexte

`data/samples/` (E08) porte un échantillon de 500 lignes de
`StockUniteLegale` et `StockUniteLegaleHistorique`, tiré du stock Sirene
complet pour faire tourner la suite de tests sans les 4,6 Go de sources. Les
9 colonnes d'identité directe de personne physique (`nomUniteLegale`,
`prenom1UniteLegale`, `sexeUniteLegale`, etc.) en sont exclues.

Cela ne suffit pas à rendre l'échantillon anonyme. Vérifié sur l'échantillon
lui-même : 282 de ses 500 lignes portent la catégorie juridique 1000
(entrepreneur individuel, sans personnalité juridique distincte de la
personne qui le crée), et 239 sont en statut diffusible. Une jointure sur le
SIREN entre le nom retiré ici et `denominationUsuelleEtablissement` /
`enseigne1Etablissement` — conservées sans restriction dans
`StockEtablissementHistorique`, échantillonné pour un autre usage — restitue
l'identité des 239 sur 239 diffusibles. La jointure ne demande aucun moyen
hors de portée : elle se fait avec le fichier source public lui-même, déjà
téléchargé pour produire l'échantillon. C'est donc une **pseudonymisation**
(RGPD art. 4.5), pas une anonymisation : la donnée reste dans le champ
d'application du RGPD, quelle que soit la Licence Ouverte v2.0 qui couvre par
ailleurs sa réutilisation — les deux régimes se cumulent, la licence ne
vaut jamais base légale.

## Options envisagées

1. **Exclure les lignes d'entrepreneur individuel de l'échantillon** —
   écartée : sur le fichier source complet, ces lignes représentent 56,4 % de
   `StockUniteLegale` (16 890 687 sur 29 922 486, catégorie juridique 1000).
   Les retirer romprait la représentativité même de l'échantillon — le
   critère que l'échantillonnage systématique cherche justement à préserver
   — et masquerait, dans la suite de tests, la moitié de la diversité réelle
   des catégories juridiques que le pipeline doit savoir traiter.
2. **Hacher ou tronquer le SIREN dans l'échantillon** — écartée : le SIREN
   est un identifiant à 9 chiffres. Un espace de 10⁹ valeurs se force par
   recherche exhaustive en quelques secondes sur un poste ordinaire ; un
   hachage sans sel n'apporte aucune protection réelle, et un hachage salé
   casserait la jointure avec `StockEtablissement*` que l'échantillon doit
   justement pouvoir exercer (tests de schéma inter-fichiers).
3. **Fabriquer une valeur de substitution plausible** (nom, SIREN fictifs) —
   écartée sans discussion possible : une donnée simulée présentée comme
   réelle est interdite dans ce projet, quel que soit le contexte, et
   fausserait au surplus la distribution réelle des catégories juridiques.
4. **Conserver les lignes telles quelles, sous une base légale RGPD
   explicite** — retenue.

## Décision

Option 4. Base légale : **intérêt légitime** (RGPD art. 6.1.f), avec sa mise
en balance écrite dans `data/samples/README.md` — intérêt poursuivi (tests
représentatifs sans dépendance à 4,6 Go non versionnés), nécessité (aucune
alternative sans perte de représentativité ni recours à une donnée simulée),
proportionnalité (500 lignes sur 29 à 96 millions par fichier, 9 colonnes
d'identité directe déjà retirées), absence d'impact additionnel sur la
personne (la source complète est déjà une base publique librement
téléchargeable), attente raisonnable et droit d'opposition (un entrepreneur
individuel sait sa dénomination commerciale publique ; le droit d'opposition
s'exerce auprès de l'INSEE, répercuté au stock suivant — un retrait avéré sur
une ligne déjà commitée exigerait de réécrire l'historique Git, pas
seulement un nouveau commit).

Les 43 lignes en statut « P » (non diffusible) restent masquées `[ND]` par
l'INSEE à la source (art. A123-96 du code de commerce) : aucune n'a été
reconstruite ni contournée.

## Conséquences

- L'échantillon Sirene reste, et le sera tant que la source elle-même contient
  des entrepreneurs individuels, une **donnée personnelle au sens du RGPD** :
  ce point doit être repris explicitement dans le registre des traitements et
  des sources (E40), pas seulement laissé dans cette page.
- La minimisation (9 colonnes retirées) est réelle et documentée, mais elle
  ne dispense pas de la base légale : les deux sont nécessaires, ni l'une ni
  l'autre ne suffit seule.
- Un contrôle automatisé (`tests/data/test_echantillons_conformite.py`, liste
  blanche par fichier) empêche qu'une régénération future réintroduise une
  colonne d'identité directe par erreur — il ne change rien au statut
  pseudonymisé des lignes qui restent.

**Ce qui ferait reconsidérer cette décision** : si l'échantillon devait un
jour porter une variable supplémentaire propre à la personne physique
(revenu, âge, situation familiale — rien de tel n'est prévu ni nécessaire au
projet), ou si son volume devait dépasser quelques milliers de lignes au
point de rendre la proportionnalité moins évidente à défendre. Dans l'un ou
l'autre cas, l'option 1 (exclusion des lignes d'entrepreneur individuel)
redeviendrait la première à réexaminer, au prix assumé d'une perte de
représentativité sur les catégories juridiques.
