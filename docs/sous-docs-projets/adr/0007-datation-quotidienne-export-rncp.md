# ADR 0007 — Un fichier par date de publication pour l'export RNCP, jamais un fichier unique écrasé

Statut : accepté (2026-08-29)

## Contexte

Le connecteur des référentiels (E07) télécharge, en plus des quatre jeux
ONISEP à URL fixe, l'export RNCP/RS de France Compétences, republié chaque
jour. Contrairement à Parcoursup (un fichier par session, jamais réédité) ou
à Sirene (un stock complet republié chaque mois), le contenu change
quotidiennement. Vérifié le 2026-08-29 : l'export du jour compte 30 484
fiches (7 000 actives), contre 36 000 annoncées à tort la veille dans la
documentation — un chiffre faussé par l'outil de comptage, pas par une
évolution réelle de la source. Une table dérivée (la réconciliation
NAF↔ROME↔formation, E18) sera construite à partir d'un export donné : il faut
pouvoir savoir après coup sur quelle version une exécution passée s'est
appuyée.

## Décision

Un fichier par date de publication (`rncp_AAAA-MM-JJ.csv`), jamais écrasé,
une entrée de manifeste par date. `_referentiels_rncp.resoudre_ressource` lit
la date de publication rendue par le catalogue et en dérive le nom du
fichier. L'idempotence porte sur « ai-je déjà l'export de cette date », pas
sur « le contenu a-t-il changé » : une réexécution le même jour ne
retélécharge rien, une réexécution un autre jour crée un nouveau fichier sans
toucher aux précédents.

## Alternatives écartées

- Fichier unique écrasé à chaque republication (comme pour Sirene) : le
  RNCP sert de table de réconciliation directe ; si le fichier est écrasé,
  l'export qui a servi à construire une table un jour donné n'existe plus le
  lendemain, et rien ne permet de rejouer cette construction.
- Retéléchargement systématique à chaque exécution, sans persistance
  nommée : viole l'immuabilité de la couche brute et l'idempotence
  (critère 3.6).

## Conséquences

Chaque export utilisé par une table dérivée reste vérifiable après coup, y
compris longtemps après sa publication. Accumulation assumée : au rythme
observé (~9 Mo par export), une exécution quotidienne prolongée dans un DAG
accumulerait de l'ordre de 3,3 Go par an — une politique de rétention sera
nécessaire si cette cadence est un jour programmée dans la durée, mais c'est
hors du périmètre de l'ingestion, qui garantit la disponibilité de
l'instantané, pas sa purge. Le même principe (dater le stock plutôt que se
fier au seul contenu) s'applique à Sirene et au RNCP, mais seul le RNCP en
tire un fichier par date : sa cadence quotidienne et son usage direct en
table de réconciliation justifient la différence.

Je reviendrais sur ce choix si le pipeline n'avait in fine besoin que du
dernier export (pas d'un historique) et que le volume accumulé devenait un
problème avant qu'une politique de rétention soit écrite.
