# ADR 0001 — ELT plutôt qu'ETL

**Date** : 2026-08-24 · **Statut** : accepté

## Contexte

Trois sources publiques hétérogènes (Parcoursup, Sirene, référentiels), huit
millésimes dont les schémas ont évolué, et des règles de nettoyage qui vont
changer pendant la construction.

## Options envisagées

1. **ETL** — transformer avant de charger. La couche brute n'est pas conservée.
2. **ELT** — charger le brut en couche bronze, transformer ensuite avec dbt.

## Décision

ELT.

## Conséquences

- Modifier une règle de nettoyage ne demande pas de re-télécharger les sources.
- Le lignage brut → final est conservé : exigence du Bloc 3, critère 3.8.
- Coût : stockage du brut, négligeable ici (Parcoursup ~100 Mo, Sirene 4,64 Go).
- La couche bronze est **immuable** : on n'y écrit jamais deux fois le même
  fichier.

**Ce qui ferait reconsidérer** : une volumétrie brute dépassant plusieurs
téraoctets, où le coût de stockage du brut deviendrait significatif.
