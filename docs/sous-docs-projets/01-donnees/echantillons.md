# Échantillons versionnés — `data/samples/`

`data/samples/` est la seule exception versionnée de `data/` (voir
`.gitignore`) : quelques centaines de lignes par source, suffisantes pour
que la suite de tests tourne sans télécharger les sources complètes
(82 Mo pour Parcoursup, 4,6 Go pour les quatre fichiers Sirene retenus,
quelques dizaines de mégaoctets pour les référentiels). Généré par
`src/edumatch/ingestion/echantillons.py`
(`python -m edumatch.ingestion.echantillons`, ou `make samples`).

## Ce qui est versionné

| Source | Fichiers | Lignes / total | Méthode | Licence |
|---|---|---:|---|---|
| Parcoursup, 8 millésimes | 8 CSV | 40 par millésime, sur 10 697 à 14 252 | Systématique | Licence Ouverte v2.0 |
| Sirene — StockEtablissement | 1 Parquet | 500, sur 43 896 818 | Systématique, 9 colonnes sur 54 | Licence Ouverte v2.0 |
| Sirene — StockEtablissementHistorique | 1 Parquet | 500, sur 95 865 102 | Systématique, colonnes complètes | Licence Ouverte v2.0 |
| Sirene — StockUniteLegale | 1 Parquet | 500, sur 29 922 486 | Systématique, colonnes d'identité directe exclues | Licence Ouverte v2.0 |
| Sirene — StockUniteLegaleHistorique | 1 Parquet | 500, sur 71 355 318 | Systématique, colonnes d'identité directe exclues | Licence Ouverte v2.0 |
| IDÉO (4 jeux) | 4 CSV | 300 par jeu | Systématique | ODbL (odc-odbl) |
| RNCP | 1 CSV | 300, sur 30 484 | Systématique | Licence Ouverte v2.0 |

**Total : 17 fichiers, 1,2 Mo** (`test_poids_total_reste_raisonnable`
bloque au-delà de 10 Mo). Le détail par fichier — chemin source, colonnes
retenues et exclues, empreinte SHA-256, URL et date du fichier source —
est dans `data/samples/manifeste.json`, régénéré à chaque exécution.

## Méthode d'échantillonnage

Systématique, à pas fixe, sans graine aléatoire : un index retenu tous les
`total // cible` lignes, à partir de la première. Ni les N premières
lignes (Sirene est trié par SIREN, ce serait un échantillon des plus
anciens numéros), ni un tirage aléatoire (qui pourrait manquer les
extrémités du fichier). Un fichier source inchangé produit toujours le
même échantillon, vérifié par empreinte SHA-256 identique sur deux
générations successives.

Les huit millésimes Parcoursup sont tous présents, pas seulement le
dernier : c'est ce qui permet de tester la réconciliation de schéma (E15,
85 → 118 colonnes) sans télécharger les 8 CSV complets.

## Critère de validation de l'étape

`data/raw/` et `data/external/` rendus absents (renommés), la suite de
tests tourne quand même :

```bash
python -m pytest -q
```

→ **145 passed**. C'est ce qui rend une exécution en CI possible sans les
4,6 Go de sources Sirene.

## Pseudonymisation, pas anonymisation

Les 9 colonnes d'identité directe (`sexeUniteLegale`, les quatre
`prenomNUniteLegale`, `prenomUsuelUniteLegale`, `pseudonymeUniteLegale`,
`nomUniteLegale`, `nomUsageUniteLegale`) sont exclues de
`StockUniteLegale` et `StockUniteLegaleHistorique`. Retirer ces colonnes
ne rend pas l'échantillon anonyme.

Sur l'échantillon lui-même, 282 des 500 lignes de `StockUniteLegale`
portent la catégorie juridique 1000, entrepreneur individuel — une
entreprise individuelle n'a pas de personnalité juridique distincte de la
personne qui la crée.

```bash
python -c "
import pyarrow.parquet as pq, collections
t = pq.read_table('data/samples/sirene/StockUniteLegale.parquet')
cat = t.column('categorieJuridiqueUniteLegale').to_pylist()
statut = t.column('statutDiffusionUniteLegale').to_pylist()
print(collections.Counter(s for c, s in zip(cat, statut) if c == 1000))
"
# → Counter({'O': 239, 'P': 43})
```

239 de ces 282 lignes sont en statut diffusible (« O »). Sur le fichier
source complet, une jointure sur le SIREN entre le nom retiré ici et
`denominationUsuelleEtablissement` / `enseigne1Etablissement` —
conservées sans restriction dans `StockEtablissementHistorique` —
restitue l'identité des 239 sur 239 diffusibles (exemple : SIREN
006341887, « RENE BLANC » côté unité légale, dénomination
d'établissement « BLANC RENE »). La jointure ne demande aucun moyen hors
de portée : elle se fait avec le fichier source public déjà téléchargé
pour produire cet échantillon. Les 43 lignes en statut « P » restent
masquées `[ND]` par l'INSEE à la source (art. A123-96 du code de
commerce) : aucune n'a été reconstruite.

| | Anonymisation | Pseudonymisation (le cas ici) |
|---|---|---|
| Définition | Ré-identification impossible, y compris par recoupement | Ré-identification possible via une information supplémentaire |
| Effet RGPD | La donnée sort du champ du RGPD | La donnée reste une donnée personnelle (RGPD art. 4.5, considérant 26) |
| Ici | — | L'information supplémentaire est le fichier source public lui-même |

L'exclusion des 9 colonnes est une mesure de minimisation utile (RGPD
art. 5.1.c), mais elle ne change pas le régime juridique de l'ensemble :
ces échantillons restent une donnée personnelle au sens du RGPD.

## Base légale (RGPD art. 6)

La Licence Ouverte ne s'y substitue pas.

**Base retenue : intérêt légitime (art. 6.1.f).**

1. **Intérêt poursuivi** — une suite de tests représentative de la
   structure réelle des données, sans dépendre de 4,6 Go non versionnés.
2. **Nécessité** — pas d'alternative : une donnée simulée est interdite
   dans ce projet et ne détecterait pas une dérive de schéma réelle (déjà
   arrivé : colonne `activitePrincipaleNAF25Etablissement`, ajoutée par
   l'INSEE le 16/12/2025 sans préavis).
3. **Proportionnalité** — 500 lignes sur 29 à 96 millions par fichier
   (0,001 à 0,002 %), 9 colonnes personnelles directes retirées, poids
   total sous 10 Mo.
4. **Impact non additionnel** — la source Sirene complète est déjà une
   base publique librement téléchargeable (Licence Ouverte v2.0) ; cet
   extrait ne rend accessible à un tiers aucune information que la
   source ne rendait pas déjà accessible.
5. **Attente raisonnable et droit d'opposition** — un entrepreneur
   individuel inscrit à Sirene sait sa dénomination commerciale publique.
   Le droit d'opposition (art. 21) s'exerce auprès de l'INSEE, qui le
   répercute au stock suivant (statut « non diffusible », déjà visible
   sous la forme `[ND]`). Un fichier déjà commité dans Git ne suit pas
   cette mise à jour automatiquement : une demande de retrait avérée
   exigerait de retirer la ligne et de réécrire l'historique Git, pas
   seulement un nouveau commit.

La Licence Ouverte v2.0 ne vaut jamais base légale RGPD : elle règle le
droit de réutiliser une information publique (propriété intellectuelle,
droit *sui generis* des bases de données), un régime distinct du droit
des données personnelles. Les deux régimes se cumulent.

Alternatives écartées (détail et seuil de bascule : ADR 0008) : exclure
les lignes d'entrepreneur individuel (détruirait la représentativité —
56,4 % des lignes du fichier source complet), hacher le SIREN (9
chiffres, espace forçable en secondes), fabriquer une valeur de
substitution (donnée simulée, interdite par ailleurs).

## Licence ODbL des jeux IDÉO

Les quatre jeux ONISEP (IDÉO) sont sous ODbL v1.0, pas Licence Ouverte.
L'ODbL impose le partage à l'identique sur toute base dérivée
redistribuée : un extrait redistribué dans ce dépôt en est une. Trois
conditions, réunies ici : attribution (producteur ONISEP, URL et date
dans le manifeste), partage à l'identique (les 4 CSV et leur licence
dédiée dans `data/samples/referentiels/ideo/LICENSE` restent sous ODbL
quelle que soit la licence du reste du dépôt, MIT), absence de mesure
technique restrictive.

## Reproductibilité

```bash
python -m edumatch.ingestion.echantillons
```

Régénère l'intégralité de `data/samples/` depuis `data/raw/` et
`data/external/`, en configuration `prod`. Nécessite les sources
complètes déjà téléchargées. Détail complet, méthode et régime
juridique : `data/samples/README.md`.
