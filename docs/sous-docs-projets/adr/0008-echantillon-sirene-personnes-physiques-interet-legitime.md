# ADR 0008 — Conserver les lignes d'entrepreneur individuel dans l'échantillon Sirene, sous intérêt légitime

Statut : accepté (2026-08-29)

## Contexte

`data/samples/` (E08) porte un échantillon de 500 lignes de
`StockUniteLegale` et `StockUniteLegaleHistorique`, tiré du stock Sirene
complet pour faire tourner la suite de tests sans les 4,6 Go de sources. Les
9 colonnes d'identité directe de personne physique (nom, prénom, sexe...) en
sont exclues, mais cela ne suffit pas à rendre l'échantillon anonyme : 282 de
ses 500 lignes portent la catégorie juridique 1000 (entrepreneur individuel,
sans personnalité juridique distincte), et 239 sont en statut diffusible. Une
jointure sur le SIREN entre le nom retiré ici et la dénomination usuelle ou
l'enseigne, conservées sans restriction dans `StockEtablissementHistorique`,
restitue l'identité des 239 sur 239 diffusibles, avec le seul fichier source
public déjà téléchargé. C'est donc une pseudonymisation (RGPD art. 4.5), pas
une anonymisation : la donnée reste dans le champ du RGPD, quelle que soit la
Licence Ouverte v2.0 qui couvre par ailleurs sa réutilisation — les deux
régimes se cumulent, la licence ne vaut jamais base légale.

## Décision

Je conserve les lignes telles quelles, sous une base légale RGPD explicite :
l'intérêt légitime (art. 6.1.f), avec sa mise en balance écrite dans
`data/samples/README.md` (intérêt poursuivi, nécessité, proportionnalité —
500 lignes sur 29 à 96 millions par fichier, 9 colonnes d'identité déjà
retirées —, absence d'impact additionnel, attente raisonnable et droit
d'opposition). Les 43 lignes en statut « P » (non diffusible) restent
masquées `[ND]` par l'INSEE à la source : aucune n'a été reconstruite ni
contournée.

## Alternatives écartées

- Exclure les lignes d'entrepreneur individuel : elles représentent 56,4 %
  de `StockUniteLegale` sur le fichier complet (16 890 687 sur
  29 922 486) ; les retirer romprait la représentativité et masquerait la
  moitié de la diversité réelle des catégories juridiques.
- Hacher ou tronquer le SIREN : c'est un identifiant à 9 chiffres, un espace
  de 10⁹ valeurs se force en quelques secondes ; un hachage salé casserait en
  plus la jointure inter-fichiers que l'échantillon doit exercer.
- Fabriquer une valeur de substitution plausible : une donnée simulée
  présentée comme réelle est interdite dans ce projet, et ça fausserait la
  distribution réelle des catégories juridiques.

## Conséquences

L'échantillon Sirene reste une donnée personnelle au sens du RGPD tant que
la source elle-même contient des entrepreneurs individuels : à reprendre
explicitement dans le registre des traitements et des sources (E40). La
minimisation (9 colonnes retirées) est réelle mais ne dispense pas de la base
légale. Un contrôle automatisé
(`tests/data/test_echantillons_conformite.py`) empêche qu'une régénération
future réintroduise une colonne d'identité directe par erreur.

Je reviendrais sur ce choix si l'échantillon devait porter une variable
supplémentaire propre à la personne physique (revenu, âge, situation
familiale — rien de tel n'est prévu), ou si son volume dépassait quelques
milliers de lignes.
