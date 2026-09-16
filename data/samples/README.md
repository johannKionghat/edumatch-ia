# `data/samples/` — échantillons versionnés

Seule exception versionnée de `data/` (voir `.gitignore`). Quelques
centaines de lignes par source : de quoi faire tourner la suite de tests
sans télécharger les sources complètes (82 Mo pour Parcoursup, 4,6 Go pour
les quatre fichiers Sirene retenus, quelques dizaines de mégaoctets pour
les référentiels).

Généré par `src/edumatch/ingestion/echantillons.py`
(`python -m edumatch.ingestion.echantillons`, ou `make samples`). Ce script
lit uniquement `data/raw/` et `data/external/`, il ne les modifie ni ne les
supprime jamais — un échantillon qu'on ne sait pas régénérer serait un
artefact opaque.

Producteurs des données reprises ici : **INSEE** (base Sirene), **MESR**
(Parcoursup), **France Compétences** (RNCP), **ONISEP** (base IDÉO),
**France Travail** (table de correspondance ROME/NAF). Le détail de chaque
source — URL, date de collecte, empreinte du fichier — est dans
`manifeste.json`.

## Méthode d'échantillonnage

Systématique, à pas fixe, sans graine aléatoire : un index retenu tous les
`total // cible` lignes, à partir de la première. Ni les N premières lignes
(Sirene est trié par SIREN, ce serait un échantillon des plus anciens
numéros), ni un tirage aléatoire (qui pourrait manquer les extrémités du
fichier). Un fichier source inchangé produit toujours le même échantillon,
vérifié par empreinte SHA-256 sur deux générations successives.

## Ce que chaque échantillon contient

| Source | Lignes / total | Méthode | Licence |
|---|---:|---|---|
| Parcoursup, 8 millésimes (2018→2025) | 40 par millésime, sur 10 697 à 14 252 | Systématique | Licence Ouverte v2.0 |
| Sirene — StockEtablissement | 500, sur 43 896 818 | Systématique, 9 colonnes sur 54 | Licence Ouverte v2.0 |
| Sirene — StockEtablissementHistorique | 500, sur 95 865 102 | Systématique, colonnes complètes | Licence Ouverte v2.0 |
| Sirene — StockUniteLegale | 500, sur 29 922 486 | Systématique, colonnes d'identité directe exclues | Licence Ouverte v2.0 |
| Sirene — StockUniteLegaleHistorique | 500, sur 71 355 318 | Systématique, colonnes d'identité directe exclues | Licence Ouverte v2.0 |
| IDÉO (4 jeux) | 300 par jeu | Systématique | ODbL (odc-odbl) |
| RNCP | 300, sur 30 484 | Systématique | Licence Ouverte v2.0 |
| RNCP — correspondance fiche/ROME | 300, sur 67 768 | Systématique | Licence Ouverte v2.0 |
| France Travail — correspondance ROME/NAF | intégral, 112 Ko | Copie complète (arborescence non ré-échantillonnable ligne à ligne) | Licence Ouverte v2.0 |

Le détail (chemin source, colonnes retenues et exclues, empreinte SHA-256)
est dans `manifeste.json`, régénéré à chaque exécution.

Les huit millésimes Parcoursup sont tous présents, pas seulement le
dernier : c'est ce qui permet de tester la réconciliation de schéma
(85 colonnes en 2018, 92 en 2019, 115 en 2020, 118 de 2021 à 2025) sans
télécharger les 8 CSV complets.

## Pseudonymisation, pas anonymisation

Les colonnes d'identité directe (nom, prénoms, pseudonyme, sexe) sont
exclues de `StockUniteLegale` et `StockUniteLegaleHistorique` :

```
sexeUniteLegale, prenom1UniteLegale, prenom2UniteLegale, prenom3UniteLegale,
prenom4UniteLegale, prenomUsuelUniteLegale, pseudonymeUniteLegale,
nomUniteLegale, nomUsageUniteLegale
```

Retirer ces colonnes ne rend pas l'échantillon anonyme. Plus de la moitié
des lignes de `StockUniteLegale` sont des entrepreneurs individuels
(56,4 % exactement, vérifié sur le fichier source complet : 16 890 687
lignes de catégorie juridique 1000 sur 29 922 486). Une entreprise
individuelle n'a pas de personnalité juridique distincte de la personne
qui la crée : sa dénomination commerciale, conservée sans restriction dans
`StockEtablissementHistorique`, porte donc souvent son patronyme. Le SIREN
étant présent dans tous les fichiers, une simple jointure entre le nom
retiré ici et la dénomination conservée là restitue l'identité. Vérifié
sur le fichier complet : en joignant `nomUniteLegale`/`prenom1UniteLegale`
à `denominationUsuelleEtablissement`/`enseigne1Etablissement` sur le
SIREN, le nom réapparaît en clair par dizaines de milliers de
correspondances — par exemple SIREN 006341887, « RENE BLANC » côté unité
légale, dénomination d'établissement « BLANC RENE ».

| | Anonymisation | Pseudonymisation (le cas ici) |
|---|---|---|
| Définition | Ré-identification impossible, y compris par recoupement | Ré-identification possible via une information supplémentaire |
| Effet RGPD | La donnée sort du champ du RGPD | La donnée reste une donnée personnelle (RGPD art. 4.5, considérant 26) |
| Ici | — | L'information supplémentaire est le fichier source public lui-même, déjà téléchargé pour produire cet échantillon |

L'exclusion des neuf colonnes d'identité directe reste une mesure de
minimisation utile, mais elle ne change pas le régime juridique de
l'ensemble : cet échantillon reste une donnée personnelle au sens du
RGPD, d'où la base légale ci-dessous.

Les colonnes techniques hors des 9 retenues (adresse complète,
coordonnées Lambert, codes cedex) sont absentes du projet — voir la liste
dans `src/edumatch/ingestion/echantillons.py`. Ça limite la surface de
données à maintenir, sans rapport avec la question des personnes
physiques traitée ci-dessus.

## Base légale (RGPD art. 6)

La minimisation (art. 5.1.c) dit comment traiter une donnée une fois qu'on
a le droit de la traiter ; l'article 6 dit si on a ce droit.

**Base retenue : intérêt légitime (art. 6.1.f).**

1. **Intérêt poursuivi** — faire tourner une suite de tests représentative
   de la structure réelle des données, sans dépendre de 4,6 Go de fichiers
   non versionnés.
2. **Nécessité** — pas d'alternative : une donnée simulée est interdite
   dans ce projet et ne détecterait de toute façon pas une dérive de
   schéma réelle (déjà arrivé : colonne
   `activitePrincipaleNAF25Etablissement`, ajoutée par l'INSEE le
   16/12/2025 sans préavis).
3. **Proportionnalité** — 500 lignes sur 29 à 96 millions par fichier
   (0,001 à 0,002 %), 9 colonnes personnelles retirées, poids total de
   `data/samples/` maintenu sous 10 Mo.
4. **Impact non additionnel** — la source Sirene complète est déjà une
   base publique librement téléchargeable (Licence Ouverte v2.0) ; cet
   extrait ne rend accessible à un tiers aucune information que la source
   ne rendait pas déjà accessible.
5. **Droit d'opposition** — un entrepreneur individuel inscrit à Sirene
   sait sa dénomination commerciale publique. Le droit d'opposition
   (art. 21) s'exerce auprès de l'INSEE, qui gère la diffusion de la base
   source (statut « non diffusible », déjà visible sous la forme `[ND]`) ;
   voir « Durée de validité » plus bas.

La Licence Ouverte v2.0 ne vaut jamais base légale : elle règle le droit
de réutiliser une information publique (propriété intellectuelle, droit
*sui generis* des bases de données), un régime distinct du droit des
données personnelles. Les deux se cumulent : être autorisé à réutiliser
Sirene par la licence n'autorise pas, à lui seul, à y traiter des données
personnelles.

## Licence ODbL des jeux IDÉO

Les quatre jeux ONISEP (IDÉO) sont sous **ODbL v1.0**, pas Licence
Ouverte (texte : https://opendatacommons.org/licenses/odbl/1-0/). Elle
impose trois conditions, réunies ici :

1. **Attribution** — producteur ONISEP, base IDÉO
   (https://api.opendata.onisep.fr) ; URL et date de collecte consignées
   dans `manifeste.json`.
2. **Partage à l'identique** — les quatre CSV de
   `data/samples/referentiels/ideo/` restent sous ODbL quelle que soit la
   licence du reste du dépôt (le code est sous licence MIT, voir
   `LICENSE`). Le texte de la licence les accompagne dans
   `data/samples/referentiels/ideo/LICENSE`.
3. **Pas de mesure technique restrictive** — aucun verrou sur ces
   fichiers.

Le RNCP, Parcoursup et Sirene restent en Licence Ouverte v2.0.

## Coexistence des licences du dépôt

Le code (`src/`, `tests/`, `pipelines/`, `configs/`, etc.) est sous
licence MIT. Les données de `data/samples/` restent sous leur licence
d'origine — Licence Ouverte v2.0 ou ODbL selon la source, jamais MIT. Un
lecteur qui réutilise le dépôt doit appliquer la licence propre à chaque
partie qu'il reprend.

## Durée de validité et procédure de retrait

Cet extrait est figé au moment de sa génération ; la base Sirene source
évolue en continu (créations, cessations, changements de statut de
diffusion). Il est régénéré à chaque nouveau stock Sirene utilisé pour le
projet, et au plus tard avant la remise du dépôt au jury.

Un entrepreneur individuel peut demander à l'INSEE le passage de son
établissement en statut « non diffusible » ; l'INSEE le répercute au
stock suivant. Un fichier déjà commité dans Git ne suit pas cette mise à
jour automatiquement : une demande de retrait avérée sur une ligne
présente dans `data/samples/` exigerait de retirer la ligne et de
réécrire l'historique Git (`git filter-repo` ou équivalent, puis
synchronisation forcée du dépôt distant), pas seulement un nouveau
commit.

## Reproductibilité

```
python -m edumatch.ingestion.echantillons
```

Régénère l'intégralité de ce dossier depuis `data/raw/` et
`data/external/`, en configuration `prod` (jamais `dev`, qui réduit
Parcoursup à deux millésimes pour itérer plus vite). Nécessite les
sources complètes déjà téléchargées
(`python -m edumatch.ingestion.parcoursup`, `sirene`, `referentiels`).

`tests/data/test_echantillons_conformite.py` fait échouer la suite de
tests si une colonne hors liste blanche apparaît dans un fichier Sirene
régénéré.
