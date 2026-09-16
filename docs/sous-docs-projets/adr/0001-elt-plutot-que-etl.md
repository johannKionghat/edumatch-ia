# ADR 0001 — ELT plutôt qu'ETL

Statut : accepté (2026-08-24)

## Contexte

Trois sources publiques hétérogènes (Parcoursup, Sirene, référentiels), huit
millésimes aux schémas qui ont évolué, et des règles de nettoyage appelées à
changer pendant la construction.

## Décision

ELT : je charge le brut en couche bronze et je transforme ensuite avec dbt.

## Alternatives écartées

- ETL (transformer avant de charger) : la couche brute ne serait pas
  conservée, et modifier une règle de nettoyage obligerait à retélécharger les
  sources.

## Conséquences

Le lignage brut → final est conservé, ce qu'exige le critère 3.8 du bloc 3. Le
coût de stockage du brut est négligeable ici (Parcoursup 82 Mo mesurés, Sirene
4,63 Go). La couche bronze est immuable : je n'y écris jamais deux fois le
même fichier.

Je reviendrais sur ce choix si la volumétrie brute dépassait plusieurs
téraoctets, au point de rendre ce stockage coûteux.
