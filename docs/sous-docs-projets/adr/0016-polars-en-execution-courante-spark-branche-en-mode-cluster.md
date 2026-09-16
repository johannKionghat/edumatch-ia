# ADR 0016 — Polars en exécution courante, Spark implémenté et branché sur le mode cluster

Statut : accepté (2026-08-30)

## Contexte

L'agrégat Sirene commune × NAF (E17) doit lire `StockEtablissement.parquet`
(43 896 818 lignes, 54 colonnes, 2,20 Go), le réduire à 9 colonnes, filtrer
et regrouper en 1 929 179 cellules. Le critère 2.4 exige des structures
adaptées au volume, et le plan d'exécution prévoit un job Spark à cette
étape. Mesuré sur ce poste, même fichier, mêmes 9 colonnes, même filtre,
même regroupement : Polars (`scan_parquet`, lazy) prend 18,2 secondes ;
PySpark (`local[*]`) prend 87,0 secondes (18,0 s de démarrage JVM + 69,0 s).
Résultat identique des deux côtés (2 423 308 actifs-employeurs, 1 929 179
cellules) : Spark est 4,8× plus lent que Polars sur ce volume, la JVM et le
shuffle entre exécuteurs locaux coûtant plus qu'ils ne rapportent tant que
le calcul tient sur un seul nœud. Ce qui empêche de conclure « Spark est
inutile » : `StockEtablissementHistorique`, une des quatre sources
retenues, compte 95 865 102 lignes, et le stock est republié — donc
grossit — chaque mois.

## Décision

Les deux moteurs sont implémentés et sélectionnés par la configuration
existante : `execution.moteur_volume: local` (dev, staging) exécute Polars,
`moteur_volume: cluster` (prod) exécute Spark. Les deux partagent un seul
module de définitions (grain, colonnes, règles métier), vérifié par un test
qui compare les deux sorties ligne à ligne sur le même échantillon.

## Alternatives écartées

- Spark partout, y compris en développement local : la mesure dit que c'est
  4,8× plus lent pour un résultat identique, sans aucun bénéfice sur ce
  volume.
- Polars partout, Spark jamais implémenté : le critère 2.4 demande une
  structure distribuée réelle, pas une promesse écrite dans une ADR, et la
  trajectoire de volume (historique à 95,9 M lignes, republication
  mensuelle) rend la question du passage à l'échelle réelle.

## Conséquences

Le chemin réellement emprunté aujourd'hui, en développement comme en
intégration continue, est Polars — assumé comme tel plutôt que caché
derrière un choix « par défaut ». Le job Spark existe, est testé, et
produit le même résultat que Polars sur le même échantillon : le critère
2.4 est prouvé par du code qui s'exécute, pas par une intention. Limite de
plateforme sans rapport avec l'arbitrage moteur : sur ce poste Windows,
l'écrivain Parquet natif de Spark échoue faute de `winutils.exe` ; le
résultat, déjà réduit à 12,6 Mo, est ramené au pilote puis écrit par la
primitive atomique du projet — un choix qui reste valide sur le cluster de
production Linux.

Je reviendrais sur ce choix si la fusion de plusieurs des quatre fichiers
Sirene retenus (le stock courant avec l'historique, qui dépasse déjà 95,9 M
lignes) ou tout calcul dont le travail intermédiaire ne tient plus dans la
mémoire d'un poste de développement se présentait. Tant que ce seuil n'est
pas franchi, Polars reste le chemin de production réel.
