# `data/samples/` — échantillons versionnés

Seule exception versionnée de `data/` (voir `.gitignore`). Quelques centaines
de lignes par source : de quoi faire tourner la suite de tests sans
télécharger les sources complètes (82 Mo pour Parcoursup, 4,6 Go pour les
quatre fichiers Sirene retenus, quelques dizaines de mégaoctets pour les
référentiels).

Généré par `src/edumatch/ingestion/echantillons.py`
(`python -m edumatch.ingestion.echantillons`, ou `make samples`). Un
échantillon qu'on ne sait pas régénérer serait un artefact opaque : ce script
lit uniquement `data/raw/` et `data/external/`, il ne les modifie ni ne les
supprime jamais.

Producteurs des données reprises ici : **INSEE** (base Sirene), **MESR**
(Parcoursup), **France Compétences** (RNCP), **ONISEP** (base IDÉO), **France
Travail** (table de correspondance ROME/NAF, E18). Le détail
de chaque source — URL exacte, date de la donnée d'origine, empreinte du
fichier source — est dans `manifeste.json`, section « Provenance » plus bas.

## Méthode d'échantillonnage

Systématique, à pas fixe, **sans graine aléatoire** : un index retenu tous
les `total // cible` lignes, à partir de la première. Ni les N premières
lignes d'un fichier (Sirene est trié par SIREN : ce serait un échantillon des
plus anciens numéros, pas un échantillon représentatif), ni un tirage
aléatoire (qui pourrait, par malchance, manquer les extrémités du fichier).
Un fichier source inchangé produit toujours exactement le même échantillon,
vérifié par empreinte SHA-256 sur deux générations successives.

## Ce que chaque échantillon contient

| Source | Lignes / total | Méthode | Licence |
|---|---:|---|---|
| Parcoursup, 8 millésimes (2018→2025) | 40 par millésime, sur 10 697 à 14 252 | Systématique | Licence Ouverte v2.0 |
| Sirene — StockEtablissement | 500, sur 43 896 818 | Systématique, 9 colonnes sur 54 | Licence Ouverte v2.0 |
| Sirene — StockEtablissementHistorique | 500, sur 95 865 102 | Systématique, colonnes complètes | Licence Ouverte v2.0 |
| Sirene — StockUniteLegale | 500, sur 29 922 486 | Systématique, colonnes d'identité directe exclues | Licence Ouverte v2.0 |
| Sirene — StockUniteLegaleHistorique | 500, sur 71 355 318 | Systématique, colonnes d'identité directe exclues | Licence Ouverte v2.0 |
| IDÉO (4 jeux) | 300 par jeu | Systématique | **ODbL (odc-odbl)** |
| RNCP | 300, sur 30 484 | Systématique | Licence Ouverte v2.0 |
| RNCP — correspondance fiche/ROME (E18) | 300, sur 67 768 | Systématique | Licence Ouverte v2.0 |
| France Travail — correspondance ROME/NAF (E18) | intégral, 112 Ko | Copie complète (structure hiérarchique, non ré-échantillonnable ligne à ligne) | Licence Ouverte v2.0 |

Le détail (chemin source, nombre de lignes source, colonnes retenues et
exclues, empreinte SHA-256 du fichier écrit, **et désormais l'URL, la date et
l'empreinte du fichier source lui-même**) est dans `manifeste.json`, régénéré
à chaque exécution du script.

Les huit millésimes Parcoursup sont tous présents, pas seulement le dernier :
c'est ce qui permet de tester la réconciliation de schéma (85 colonnes en
2018, 92 en 2019, 115 en 2020, 118 de 2021 à 2025) sans télécharger les
8 CSV complets.

## Régime juridique des échantillons Sirene — pseudonymisation, pas anonymisation

Les colonnes d'identité directe (nom, prénoms, pseudonyme, sexe) sont
**exclues** de `StockUniteLegale` et `StockUniteLegaleHistorique` :

```
sexeUniteLegale, prenom1UniteLegale, prenom2UniteLegale, prenom3UniteLegale,
prenom4UniteLegale, prenomUsuelUniteLegale, pseudonymeUniteLegale,
nomUniteLegale, nomUsageUniteLegale
```

Retirer ces colonnes **ne rend pas l'échantillon anonyme**. Ce README l'a
affirmé à tort dans une version antérieure pour `StockEtablissement` et
`StockEtablissementHistorique` — l'erreur mérite d'être dite explicitement,
pas seulement corrigée en silence.

**Le fait.** Plus de la moitié des lignes de `StockUniteLegale` sont des
entrepreneurs individuels : 56,4 % exactement, vérifié sur le fichier source
complet (16 890 687 lignes de catégorie juridique 1000 sur 29 922 486). Une
entreprise individuelle n'a pas de personnalité juridique distincte de la
personne qui la crée. Sa dénomination commerciale (`denominationUsuelleEtablissement`,
`enseigne1Etablissement`, conservées dans `StockEtablissementHistorique`,
échantillonné sans restriction de colonnes) porte donc très souvent son
patronyme. Le SIREN étant conservé dans tous les fichiers, une simple
jointure entre le nom retiré ici et la dénomination conservée là restitue
l'identité. Vérifié sur le fichier source complet, pas supposé : en joignant
`nomUniteLegale`/`prenom1UniteLegale` (colonnes exclues de l'échantillon) à
`denominationUsuelleEtablissement`/`enseigne1Etablissement` (colonnes
conservées) sur le SIREN, le nom réapparaît en clair par dizaines de
milliers de correspondances — par exemple SIREN 006341887, `RENE BLANC` côté
unité légale, dénomination d'établissement `BLANC RENE` ; SIREN 006841621,
`GILBERT JUGY`, dénomination `SALLE DE JEUX JUGY`.

**La qualification correcte.**

| | Anonymisation | Pseudonymisation (le cas ici) |
|---|---|---|
| Définition | Ré-identification rendue **impossible**, y compris par recoupement | Ré-identification possible via une **information supplémentaire** |
| Effet RGPD | La donnée sort du champ du RGPD | La donnée **reste** une donnée personnelle (RGPD art. 4.5, considérant 26) |
| Ici | — | L'information supplémentaire est le fichier source public **lui-même**, déjà téléchargé pour produire cet échantillon : la jointure ne demande aucun moyen hors de portée |

L'exclusion des neuf colonnes d'identité directe est donc une mesure de
**minimisation** réelle et utile (elle retire ce qu'un usage de test n'a
jamais besoin de lire), mais elle ne change pas le régime juridique de
l'ensemble : cet échantillon reste une donnée personnelle au sens du RGPD, et
la section suivante en tire la conséquence — une base légale, pas seulement
un principe.

### Les colonnes techniques de Sirene hors des 9 retenues

Adresse complète, coordonnées Lambert, codes cedex : présentes dans le
fichier source mais absentes du projet lui-même (voir les 9 colonnes utiles
de `StockEtablissement` dans `src/edumatch/ingestion/echantillons.py`).
Minimiser l'échantillon à ce que le projet lit réellement limite la surface
de données à maintenir, sans rapport avec le sujet des personnes physiques
traité ci-dessus.

## Base légale (RGPD art. 6) — pas seulement la minimisation

La minimisation (RGPD art. 5.1.c) dit *comment* traiter une donnée
personnelle une fois qu'on a le droit de la traiter. Elle ne dit pas *si* on
a ce droit : c'est l'objet de l'article 6, et la section précédente établit
que cette question se pose bien ici.

**Base retenue : intérêt légitime (RGPD art. 6.1.f).** Mise en balance :

1. **Intérêt poursuivi** — faire tourner une suite de tests représentative de
   la structure réelle des données (types, valeurs, proportions de
   catégories juridiques) sans dépendre de 4,6 Go de fichiers non versionnés.
2. **Nécessité** — aucune alternative : une donnée simulée est interdite par
   ce projet quel que soit le contexte, et ne détecterait de toute façon pas
   une dérive de schéma de la source réelle (c'est arrivé : colonne
   `activitePrincipaleNAF25Etablissement`, ajoutée par l'INSEE le
   16/12/2025, sans préavis).
3. **Proportionnalité** — 500 lignes sur 29 à 96 millions par fichier Sirene
   (de l'ordre de 0,001 à 0,002 % de chaque source), 9 colonnes personnelles
   directes retirées sur les colonnes disponibles, poids total de
   `data/samples/` maintenu sous 10 Mo (`test_poids_total_reste_raisonnable`).
4. **Impact non additionnel sur la personne** — la source Sirene complète est
   déjà, par construction, une base publique librement téléchargeable par
   quiconque (Licence Ouverte v2.0) ; cet extrait ne rend accessible à un
   tiers aucune information que la source ne rendait pas déjà accessible.
5. **Attente raisonnable et droit d'opposition** — un entrepreneur individuel
   inscrit à Sirene sait que sa dénomination commerciale est publique. Le
   droit d'opposition (RGPD art. 21) s'exerce auprès de l'INSEE, qui gère la
   diffusion de la base source (statut « non diffusible », déjà visible dans
   les données sous la forme `[ND]`) ; voir « Durée de validité et retrait »
   plus bas pour la répercussion sur ce dépôt.

**La Licence Ouverte v2.0 ne vaut jamais base légale.** Elle règle le droit de
réutiliser une information publique (propriété intellectuelle, droit
*sui generis* des bases de données) — un régime distinct du droit des
données personnelles. Les deux se **cumulent** : être autorisé à réutiliser
la base Sirene par la licence n'autorise pas, à lui seul, à y traiter des
données personnelles ; il faut en plus une base légale RGPD, ici l'intérêt
légitime démontré ci-dessus.

## Licence ODbL des jeux IDÉO — ce qu'elle impose ici

Les quatre jeux ONISEP (IDÉO) sont sous **ODbL (Open Database License) v1.0**,
pas Licence Ouverte. Texte intégral :
<https://opendatacommons.org/licenses/odbl/1-0/>. L'ODbL impose le partage à
l'identique sur toute base dérivée redistribuée ; un extrait redistribué dans
ce dépôt en est une, même minuscule. La licence n'interdit pas l'extrait,
elle impose trois conditions, réunies ici :

1. **Attribution** — producteur : **ONISEP**, base IDÉO
   (<https://api.opendata.onisep.fr>) ; URL de téléchargement et date de
   collecte de chaque jeu consignées dans `manifeste.json` (champs `url`,
   `date_source`).
2. **Partage à l'identique** — les quatre fichiers CSV de
   `data/samples/referentiels/ideo/` restent eux-mêmes sous ODbL, quelle que
   soit la licence du reste du dépôt (le code est sous licence MIT, voir le
   `LICENSE` à la racine) : un tiers qui les réutilise doit respecter la même
   licence sur sa propre redistribution. Le texte de la licence les
   accompagne directement dans `data/samples/referentiels/ideo/LICENSE`, pour
   qu'un tiers qui ne récupère que ce dossier l'emporte avec les données.
3. **Pas de mesure technique restrictive** — aucun verrou n'est appliqué à
   ces fichiers, un tiers peut les rouvrir et les redistribuer librement sous
   ODbL.

Le RNCP, Parcoursup et Sirene n'ont pas cette contrainte : Licence Ouverte
v2.0.

## Coexistence des licences du dépôt

Le code de ce dépôt (`src/`, `tests/`, `pipelines/`, `configs/`, etc.) est
sous licence **MIT** (`LICENSE` à la racine). Les données de
`data/samples/` restent sous leur licence d'origine — Licence Ouverte v2.0 ou
ODbL selon la source, jamais MIT. Code et données ne sont donc pas sous la
même licence : un lecteur qui réutilise le dépôt doit appliquer la licence
propre à chaque partie qu'il reprend.

## Durée de validité et procédure de retrait

**Durée de validité.** Cet extrait est figé au moment de sa génération ; la
base Sirene source, elle, évolue en continu (créations, cessations,
changements de statut de diffusion). Cet échantillon est régénéré à chaque
nouveau stock Sirene utilisé pour le projet, et **au plus tard avant la
remise du dépôt au jury**, pour limiter l'écart entre l'extrait versionné et
l'état réel de la base publique.

**Droit d'opposition et retrait.** Un entrepreneur individuel peut à tout
moment demander à l'INSEE le passage de son établissement en statut « non
diffusible » ; l'INSEE le répercute au stock suivant, disponible au
téléchargement. Un fichier déjà commité dans Git, lui, ne suit pas cette mise
à jour automatiquement : une demande de retrait avérée sur une ligne présente
dans `data/samples/` exigerait de retirer la ligne **et de réécrire
l'historique Git** (`git filter-repo` ou équivalent, puis synchronisation
forcée du dépôt distant), pas seulement un nouveau commit — ce projet a déjà
constaté qu'un objet Git supprimé par un commit ordinaire reste résoluble par
son SHA tant que l'historique n'est pas réécrit et le dépôt distant
resynchronisé.

## Reproductibilité

```
python -m edumatch.ingestion.echantillons
```

Régénère l'intégralité de ce dossier depuis `data/raw/` et `data/external/`,
en configuration `prod` (jamais `dev`, qui réduit Parcoursup à deux
millésimes pour itérer plus vite — un choix incompatible avec le besoin de
cette étape). Nécessite les sources complètes déjà téléchargées
(`python -m edumatch.ingestion.parcoursup`, `sirene`, `referentiels`).

Un contrôle automatisé (`tests/data/test_echantillons_conformite.py`) fait
échouer la suite de tests si une colonne hors liste blanche apparaît dans un
fichier Sirene régénéré ; une garde équivalente, exécutée avant toute
publication, est décrite dans la politique de vérification du dépôt.
