# ADR 0004 — Primitives d'ingestion mutualisées avant duplication, manifeste corrompu mis en quarantaine

Statut : accepté (2026-08-28)

## Contexte

Le connecteur Parcoursup (E05) est le premier des trois connecteurs
d'ingestion prévus (Parcoursup, Sirene, référentiels). Tous les trois doivent
garantir la même chose : téléchargement en flux, empreinte SHA-256, écriture
atomique, manifeste de traçabilité. Seule la résolution d'URL varie vraiment
d'une source à l'autre. Deux décisions ont dû être arbitrées en écrivant ce
premier connecteur.

## Décision

1. J'extrais les primitives génériques dans `_flux.py` dès ce premier
   connecteur, plutôt que d'attendre une troisième occurrence : la
   mutualisation n'est pas une conjecture, elle est déjà écrite dans le plan
   d'exécution (E06 et E07 répéteront flux HTTP, empreinte, écriture
   atomique, manifeste). `parcoursup.py` ne porte plus que ce qui lui est
   propre (gabarit d'URL, orchestration des 8 millésimes).
2. Un manifeste illisible est traité comme vide par `lire_manifeste()` — la
   chaîne continue — mais le fichier fautif est déplacé vers
   `manifeste.json.corrompu-{horodatage}` et l'incident journalisé au niveau
   erreur, plutôt qu'écrasé en silence.

## Alternatives écartées

- Mutualiser seulement après trois occurrences (règle classique contre
  l'abstraction prématurée) : ici la duplication à venir est déjà connue,
  attendre ne réduit aucun risque, ça reporte un refactoring certain.
- Écraser silencieusement un manifeste illisible : un JSON qui devient
  illisible est un incident (disque plein, processus tué en cours
  d'écriture) ; le laisser disparaître sans trace interdit tout diagnostic.
- Bloquer la chaîne sur un manifeste corrompu : le manifeste n'est pas la
  source de vérité de l'intégrité (l'empreinte SHA-256 recalculée à chaque
  passage l'est) ; le faire bloquer romprait la règle « le manifeste ne
  bloque jamais » pour un gain nul.

## Conséquences

Le deuxième connecteur (Sirene, E06) s'appuie sur du code déjà testé plutôt
que de dupliquer puis refactorer sous pression. Risque assumé : `_flux.py`
n'a encore qu'un seul appelant réel, son interface pourrait devoir bouger à
l'usage. Un manifeste corrompu entraîne un retéléchargement complet des
millésimes déjà présents (perte de l'idempotence pour ce passage, pas de
perte de données), mais laisse une trace exploitable.

Un rapport de revue de code avait signalé un risque de perte d'entrées du
manifeste en fonctionnement normal ; reproduit avant correction, le risque
n'existait qu'en cas de manifeste déjà corrompu — exactement le cas couvert
ci-dessus. Aucun correctif supplémentaire n'a donc été nécessaire.

Je reviendrais sur la mutualisation si l'écriture du connecteur Sirene
révélait qu'une primitive supposée commune doit en réalité être générique. Je
reviendrais sur la quarantaine si la fréquence réelle de corruption s'avérait
non négligeable, avec alors une sauvegarde du manifeste avant écriture.
