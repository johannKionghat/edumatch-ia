# Ce qui est déjà établi — amorce avant E40

Ce dossier accueillera le plan de gouvernance (E40 à E44 du plan d'exécution
du projet) : registre des traitements, registre des sources, AIPD, Model
Card, matrice de risques, correspondance AI Act. **Rien de tout cela n'est
encore écrit ici** — écrire ces documents avant leur étape romprait l'ordre
du plan, qui exige d'avoir traité les données (E14-E20) et le modèle
(E21-E27) avant de gouverner leur usage en connaissance de cause.

Cette page ne fait qu'indexer la matière déjà produite ailleurs dans le
dépôt, au fil des étapes d'ingestion, pour qu'elle ne se perde pas d'ici E40.

## Licences par source — déjà identifiées

| Source | Licence | Implication | Où c'est établi |
|---|---|---|---|
| Parcoursup (MESR) | Licence Ouverte v2.0 | Réutilisation libre, attribution | `01-donnees/sources.md` |
| Sirene (INSEE) | Licence Ouverte v2.0 | Réutilisation libre, attribution | `01-donnees/sources.md` |
| RNCP (France Compétences) | Licence Ouverte v2.0 | Réutilisation libre, attribution | `01-donnees/sources.md` |
| IDÉO (ONISEP) | **ODbL v1.0** | Partage à l'identique obligatoire sur toute base dérivée redistribuée | `01-donnees/sources.md`, `data/samples/referentiels/ideo/LICENSE` |

Chaque manifeste d'ingestion (`data/raw/*/manifeste.json`,
`data/external/referentiels/manifeste.json`, `data/samples/manifeste.json`)
enregistre la licence de chaque fichier individuellement, en plus de cette
table : le registre des sources (E40) pourra s'appuyer directement sur ces
manifestes plutôt que de retranscrire les licences à la main.

## Base légale déjà établie pour un traitement — les échantillons de test

Le seul traitement de données personnelles identifié à ce jour dans le
dépôt est `data/samples/` (E08) : un échantillon versionné de Sirene
contient, malgré l'exclusion des 9 colonnes d'identité directe, des lignes
d'entrepreneur individuel ré-identifiables par jointure avec le fichier
source public. Qualification, mise en balance et base légale (intérêt
légitime, art. 6.1.f) sont écrites en détail dans
`01-donnees/echantillons.md` et l'ADR 0008 — à reprendre telles quelles dans
le registre des traitements (E40), pas à refaire.

Aucun autre traitement de données personnelles n'existe encore dans le
dépôt à ce stade : ni modèle entraîné, ni API, ni journalisation.

## Attribution des quatre producteurs

INSEE (Sirene), MESR (Parcoursup), France Compétences (RNCP), ONISEP (IDÉO).
Le détail par producteur — URL de la source, date de collecte, empreinte du
fichier source — est dans `data/samples/manifeste.json` et dans les
manifestes de chaque connecteur.

## Ce qui reste hors de cette page

Tout le reste du plan de gouvernance (rôles et responsabilités, AIPD,
Model Card, matrice de risques, correspondance AI Act, procédure d'audit) :
non commencé, prévu à E40-E44. Voir `reste-a-faire.md` pour le détail des
livrables attendus par bloc.
