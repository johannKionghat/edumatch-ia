# ADR 0007 — Un fichier par date de publication pour l'export RNCP, jamais un fichier unique écrasé

**Date** : 2026-08-29 · **Statut** : accepté

## Contexte

Le connecteur des référentiels (E07) télécharge, en plus des quatre jeux
ONISEP à URL fixe, l'export RNCP/RS de France Compétences. Cet export est
republié **chaque jour** : contrairement à Parcoursup (un fichier par session,
jamais réédité) ou à Sirene (un stock complet republié chaque mois), le
contenu change quotidiennement — fiches ajoutées, retirées, statuts modifiés.
Vérifié le 2026-08-29 : l'export du jour compte 30 484 fiches (7 000 actives),
contre 36 000 annoncées à tort la veille dans la documentation (chiffre
faussé par l'outil de comptage, pas par une évolution réelle de la source —
voir `01-donnees/sources.md`).

Une table dérivée du RNCP (la réconciliation NAF↔ROME↔formation, E18) sera
construite à partir d'un export donné. Il faut pouvoir savoir, après coup,
sur quelle version du référentiel une exécution passée s'est appuyée.

## Options envisagées

1. **Fichier unique, écrasé à chaque republication** (la mécanique retenue
   pour Sirene, avec la date conservée seulement dans le manifeste) —
   écartée : un stock Sirene grossit mensuellement mais reste globalement
   comparable d'un mois à l'autre pour l'usage qu'en fait le projet (agrégats
   par commune × NAF). Le RNCP sert de table de réconciliation directe :
   si le fichier est écrasé, l'export qui a servi à construire une table
   dérivée un jour donné n'existe plus le lendemain, et rien ne permet de
   revérifier ou de rejouer cette construction.
2. **Retéléchargement systématique à chaque exécution, sans persistance
   nommée** — écartée : viole le principe d'immuabilité de la couche brute
   (`data/raw/` — ici `data/external/`) et le critère 3.6 (idempotence) : une
   tâche qui retélécharge à chaque appel, même quand rien n'a changé, n'est
   pas idempotente au sens du projet.
3. **Un fichier par date de publication** (`rncp_AAAA-MM-JJ.csv`), jamais
   écrasé, une entrée de manifeste par date — retenue.

## Décision

Option 3. `_referentiels_rncp.resoudre_ressource` lit la date de publication
rendue par le catalogue (`last_modified`) et `chemin_destination` en dérive le
nom de fichier. L'idempotence porte sur « ai-je déjà l'export de cette date »,
pas sur « le contenu a-t-il changé » : une réexécution le même jour ne
retélécharge rien (la ressource résolue porte la même date), une réexécution
un autre jour crée un nouveau fichier sans toucher aux précédents.

## Conséquences

- **Chaque export utilisé par une table dérivée reste vérifiable après coup**,
  y compris longtemps après sa publication — c'est ce qui manque à un fichier
  écrasé.
- **Accumulation dans le temps assumée, non traitée ici** : au rythme observé
  aujourd'hui (~9 Mo par export), une exécution quotidienne prolongée dans un
  DAG (E33) accumulerait de l'ordre de 3,3 Go par an. Une politique de
  rétention (purge, archivage, ou compression des exports anciens) sera
  nécessaire si cette tâche est un jour programmée à cette cadence sur une
  longue durée — hors du périmètre de l'ingestion, qui garantit la
  disponibilité de l'instantané, pas sa purge.
- **Différent du choix Sirene, pour une raison assumée** : Sirene grossit mais
  ne sert pas de table de réconciliation figée dans le temps de la même façon
  ; le RNCP le fait. Le même principe (dater le stock plutôt que se fier au
  seul contenu) est appliqué aux deux, mais seul le RNCP en tire un fichier
  par date plutôt qu'un fichier unique — la cadence de republication
  quotidienne, combinée à l'usage direct en table de réconciliation, justifie
  la différence.

**Ce qui ferait reconsidérer** : si le pipeline n'a in fine besoin que du
dernier export en date (pas d'un historique), et que le volume accumulé sans
politique de rétention devient un problème opérationnel avant qu'une telle
politique n'ait été écrite — auquel cas il faudrait soit écrire la politique
de rétention en priorité, soit revenir à un fichier unique en acceptant de
perdre la traçabilité historique.
