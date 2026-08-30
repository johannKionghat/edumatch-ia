# ADR 0016 — Polars en exécution courante, Spark implémenté et branché sur le mode cluster

**Date** : 2026-08-30 · **Statut** : accepté

## Contexte

L'agrégat Sirene commune × NAF (E17) doit lire `StockEtablissement.parquet`
(43 896 818 lignes, 54 colonnes, 2,20 Go), le réduire à 9 colonnes, filtrer et
regrouper en 1 929 179 cellules. Le critère 2.4 du bloc 2 exige des
« structures adaptées au volume », et le plan d'exécution du projet prévoit
explicitement un job Spark à cette étape.

Mesuré sur ce poste, même fichier, mêmes 9 colonnes, même filtre, même
regroupement :

| Moteur | Démarrage | Lecture + filtre + regroupement | Total |
|---|---:|---:|---:|
| Polars (`scan_parquet`, lazy) | — | 18,2 s | **18,2 s** |
| PySpark (`local[*]`, JVM locale) | 18,0 s | 69,0 s | **87,0 s** |

Résultat identique des deux côtés (2 423 308 actifs-employeurs,
1 929 179 cellules) : la comparaison porte sur la vitesse, pas sur la
logique. **Spark est 4,8× plus lent que Polars sur ce volume.** La JVM,
l'ordonnancement des tâches et le shuffle entre exécuteurs locaux coûtent
plus qu'ils ne rapportent tant que le calcul tient sur un seul nœud.

Ce qui empêche de conclure « Spark est inutile » malgré cette mesure :
`StockEtablissementHistorique`, une des quatre sources Sirene déjà retenues,
compte à lui seul 95 865 102 lignes, et le stock Sirene est republié — donc
grossit — chaque mois. Une fusion future de plusieurs de ces fichiers
produirait un calcul intermédiaire d'un autre ordre de grandeur qu'un simple
comptage par groupe sur un seul fichier.

## Options envisagées

1. **Spark partout, y compris en développement local** — écartée : la mesure
   dit que c'est 4,8× plus lent pour un résultat identique, sans aucun
   bénéfice sur ce volume. Imposer ce coût à chaque exécution locale et à
   chaque test ne se justifie par rien de mesurable aujourd'hui.
2. **Polars partout, Spark jamais implémenté** — écartée : le critère 2.4 du
   bloc 2 demande une structure distribuée réelle, pas une promesse écrite
   dans une ADR. Se contenter de Polars laisserait le critère non prouvé, et
   la trajectoire de volume (historique à 95,9 M lignes, republication
   mensuelle) rend la question du passage à l'échelle réelle, pas
   hypothétique.
3. **Les deux moteurs, sélectionnés par la configuration existante
   (`execution.moteur_volume`)** — retenue.

## Décision

Option 3. `execution.moteur_volume: local` (dev, staging) exécute le moteur
Polars ; `execution.moteur_volume: cluster` (prod) exécute le moteur Spark.
Les deux implémentations partagent un seul module de définitions (grain,
colonnes, règles métier, table de correspondance des tranches d'effectifs) :
une correction de règle ne peut pas s'appliquer à un moteur sans que l'autre
diverge en silence — vérifié par un test qui compare les deux sorties ligne à
ligne sur le même échantillon.

## Conséquences

- Le chemin réellement emprunté aujourd'hui, en développement comme en
  intégration continue, est Polars : c'est le plus rapide et le plus simple
  sur le volume actuel, et c'est assumé comme tel plutôt que caché derrière
  un choix « par défaut » qui laisserait croire que Spark tourne partout.
- Le job Spark existe, est testé et produit le même résultat que Polars sur
  le même échantillon (`test_executer_moteur_cluster_ecrit_le_meme_resultat`)
  : le critère 2.4 est prouvé par du code qui s'exécute, pas par une
  intention.
- Limite de plateforme assumée, sans rapport avec l'arbitrage moteur : sur ce
  poste Windows, l'écrivain Parquet natif de Spark échoue faute de
  `winutils.exe`. Le résultat, déjà réduit à 12,6 Mo, est donc ramené au
  pilote puis écrit par la primitive atomique du projet — un choix qui reste
  valide sur le cluster de production Linux, où l'écriture directe par Spark
  fonctionnerait aussi.
- **Le seuil qui ferait reconsidérer cette décision** : la fusion de
  plusieurs des quatre fichiers Sirene retenus (le stock courant avec
  l'historique, qui dépasse déjà 95,9 M lignes), ou tout calcul dont le
  travail intermédiaire ne tient plus dans la mémoire d'un poste de
  développement — pas une préférence pour l'un des deux moteurs. Tant que ce
  seuil n'est pas franchi, Polars reste le chemin de production réel.
