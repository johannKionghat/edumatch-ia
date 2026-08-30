# Vérification des sources — E03

**Date de vérification : 2026-08-26.** Chaque chiffre ci-dessous est reproduit
par une commande, exécutée le jour même contre le catalogue de la source — pas
contre un téléchargement complet. Le script qui rejoue l'ensemble est
`scripts/verifier_sources.sh`.

**Mise à jour du 2026-08-29 (E08)** : un échantillon versionné de chacune de
ces sources est désormais disponible dans `data/samples/`, avec son régime
juridique propre (pseudonymisation des lignes Sirene de personnes physiques,
base légale, licences ODbL et Licence Ouverte) — détail dans
`01-donnees/echantillons.md`.

**Mise à jour du 2026-08-28 (E06)** : les 4 fichiers Sirene retenus ont été
réellement téléchargés (`data/raw/sirene/`). Le nombre de lignes, invérifiable
par l'API de métadonnées le 26/08, est mesuré ici pour la première fois par
métadonnée Parquet — voir la section B, sous-section « Nombre d'établissements
et d'unités légales — corrigé en E06 ».

**Mise à jour du 2026-08-29 (E07)** : le connecteur des référentiels
(`ingestion/referentiels.py`, `_referentiels_rncp.py`) a réellement téléchargé
les 4 jeux ONISEP et l'export RNCP du jour dans `data/external/referentiels/`
(22 Mo au total, `du -sh data/external/referentiels/`). Deux corrections
importantes en découlent, détaillées dans la section C.2 : le nombre de fiches
RNCP annoncé le 26/08 (« 36 000 fiches, dont 6 995 actives ») était **faussé
par l'outil de vérification lui-même**, pas par une évolution de la source —
et l'encodage annoncé pour le RNCP (Latin-1) était faux, le fichier réel est en
UTF-8.

**Mise à jour du 2026-08-29 (E12)** : la phase exploratoire sur Parcoursup
(`notebooks/02` à `04-jgk-eda-*.ipynb`) a établi que le numérateur du label
ventilé par type de baccalauréat (`prop_tot_{bg|bt|bp}[_brs]`) n'existe qu'à
partir de la session 2020, et que la part de vœux boursiers connaît deux
ruptures de série (2019-2020, puis 2025). Ces deux constats ne changent rien
au schéma ni à la volumétrie brute du fichier Parcoursup mesurés ici, mais
bornent ce qui est réellement exploitable pour l'entraînement du modèle —
détail dans `01-donnees/label.md` et `04-modele/evaluation.md`.

## Méthode

Les gros fichiers (8 CSV Parcoursup, 11 fichiers Sirene) ne sont **jamais**
téléchargés ici : on interroge les API de métadonnées (`api/explore/v2.1` côté
opendatasoft pour Parcoursup, `api/1/datasets/...` côté data.gouv pour Sirene et
RNCP), qui renvoient nombre d'enregistrements, colonnes, taille de fichier et
date de publication sans rapatrier la donnée. Les référentiels ONISEP (quelques
Mo chacun) sont téléchargés en entier : à cette taille, c'est le seul moyen
d'obtenir un nombre de lignes exact, et ça ne contredit pas le principe — on ne
réduit que ce qui est trop gros pour être manipulé directement.

Outils : `curl` (présent), `python -c` pour parser le JSON (`jq` absent de cet
environnement). Chaque commande listée a été exécutée aujourd'hui ; les sorties
collées sont réelles.

---

## A. Parcoursup (MESR)

**Identifiant et accès** — un jeu de données par millésime, sur le portail
opendatasoft du MESR. Export CSV à la demande, pas de fichier stocké :

```
https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets/{id}/exports/csv?delimiter=%3B
```

**Commande de vérification** (exécutée pour les 8 identifiants) :

```bash
curl -sS "https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets/fr-esr-parcoursup" \
  | python -c "import json,sys; d=json.load(sys.stdin); m=d['metas']['default']; \
    print(m['records_count'], len(d['fields']), m['license'], m['modified'])"
```

**Sortie réelle, les 8 millésimes** :

| Identifiant | Formations | Colonnes | Licence | Dernière modification |
|---|---:|---:|---|---|
| `fr-esr-parcoursup` (2025) | 14 252 | 118 | Licence Ouverte v2.0 (Etalab) | 2026-03-09 |
| `fr-esr-parcoursup_2024` | 14 079 | 118 | Licence Ouverte v2.0 (Etalab) | 2025-01-16 |
| `fr-esr-parcoursup_2023` | 13 869 | 118 | Licence Ouverte v2.0 (Etalab) | 2024-07-01 |
| `fr-esr-parcoursup_2022` | 13 644 | 118 | Licence Ouverte v2.0 (Etalab) | 2023-01-30 |
| `fr-esr-parcoursup_2021` | 13 396 | 118 | Licence Ouverte v2.0 (Etalab) | 2022-01-20 |
| `fr-esr-parcoursup_2020` | 12 760 | 115 | Licence Ouverte v2.0 (Etalab) | 2022-01-20 |
| `fr-esr-parcoursup-2019` | 11 577 | 92 | Licence Ouverte v2.0 (Etalab) | 2020-04-27 |
| `fr-esr-parcoursup-2018` | 10 697 | 85 | Licence Ouverte v2.0 (Etalab) | 2019-10-07 |

**Total : 104 274 formation-années** (14 252+14 079+13 869+13 644+13 396+12 760+11 577+10 697),
recalculé aujourd'hui — identique au chiffre retenu jusqu'ici.

**Licence** — Licence Ouverte v2.0 (Etalab). Texte :
`https://www.etalab.gouv.fr/wp-content/uploads/2017/04/ETALAB-Licence-Ouverte-v2.0.pdf`.
Elle oblige à mentionner la source (MESR, Parcoursup) et la date de dernière
mise à jour de la donnée réutilisée ; elle n'impose ni partage à l'identique ni
restriction d'usage commercial.

**Schéma — nombre de colonnes croissant** : 85 en 2018, 92 en 2019, 115 en 2020,
118 à partir de 2021. Ce n'est pas une instabilité aléatoire : le MESR a ajouté
des champs au fil des sessions (mentions, néo-bacheliers, académie d'origine).

**Stabilité inter-millésimes — mesurée par intersection des noms de champs**,
commande réellement exécutée (bloc « Champs communs » de
`scripts/verifier_sources.sh`, lignes 34-45) :

```bash
python - "$TMP" <<'PY'
import json, glob, os, sys
tmp = sys.argv[1]
sets = {}
for f in glob.glob(os.path.join(tmp, "fr-esr-parcoursup*.json")):
    d = json.load(open(f, encoding="utf-8"))
    sets[d["dataset_id"]] = {fld["name"] for fld in d.get("fields", [])}
common_2020_2025 = sets["fr-esr-parcoursup_2020"] & sets["fr-esr-parcoursup"]
common_all = set.intersection(*sets.values())
print(f"  Champs communs 2020<->2025 : {len(common_2020_2025)}")
print(f"  Champs communs sur les 8 sessions : {len(common_all)}")
PY
```

($TMP contient les 8 réponses JSON téléchargées à l'étape précédente du
script, une par millésime.)

Sortie réelle : **106 champs communs entre 2020 et 2025**, et **83 champs
communs sur les 8 sessions** (2018 → 2025), la liste étant dominée par les
compteurs de vœux et d'admis (`nb_voe_pp_*`, `acc_*`, `pct_*`) et les
identifiants de formation (`cod_uai`, `fili`, `dep`). C'est le socle de variables
disponible sur toute la période. Il ne suffit toutefois pas à rendre un modèle
entraîné sur huit sessions possible : le numérateur du label n'existe qu'à
partir de 2020, comme je l'ai constaté ensuite. Les colonnes qui apparaissent
seulement après 2020 (détail des mentions, `acc_neobac`, `g_olocalisation...`)
sont enrichissantes mais pas indispensables au label.

**Fréquence de mise à jour** — annuelle (déduction faite à partir d'un jeu
par session Parcoursup constaté sur 8 ans ; l'API opendatasoft ne porte pas de
champ `frequency` pour ces jeux, contrairement à Sirene et RNCP où ce champ
existe et vaut respectivement `monthly` et `daily`). Un jeu par session
Parcoursup (candidatures de janvier à l'été), publié en fin de campagne
(juillet à octobre selon les années, voir colonne « dernière modification »
ci-dessus).

**Volumétrie en octets** — non vérifiable par l'API de métadonnées : l'export
CSV est généré à la volée (`Content-Length` absent de la réponse, transfert
« chunked »). Mesurée directement le **2026-08-28**, une fois les 8 millésimes
réellement téléchargés par `ingestion/parcoursup.py` (E05) : **82 Mo** au total
sur `data/raw/parcoursup/` (`du -sh data/raw/parcoursup/`). Ce chiffre remplace
l'ordre de grandeur « ~100 Mo », qui n'avait jamais été mesuré faute de fichier
posé sur disque.

---

## B. Sirene (INSEE)

**Identifiant et accès** — le jeu `base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret`
sur data.gouv. Les URL de téléchargement changent chaque mois (nouveau stock
publié) : on interroge systématiquement le point d'entrée stable du catalogue,
jamais une URL codée en dur.

```
https://www.data.gouv.fr/api/1/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/
```

**Commande exécutée aujourd'hui** :

```bash
curl -sS "https://www.data.gouv.fr/api/1/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/"
```

**Sortie réelle** — 24 ressources, dernier stock publié le **01/08/2026**,
fréquence déclarée **mensuelle**, licence `lov2` (Licence Ouverte v2.0, même
texte que Parcoursup).

**Volumétrie des 4 fichiers retenus (Parquet), taille exacte du stock du
01/08/2026** :

| Fichier | Taille (octets) | Go décimal |
|---|---:|---:|
| `StockEtablissement` | 2 202 341 459 | 2,20 |
| `StockEtablissementHistorique` | 870 319 380 | 0,87 |
| `StockUniteLegaleHistorique` | 855 957 649 | 0,86 |
| `StockUniteLegale` | 705 090 270 | 0,71 |
| **Total 4 fichiers Parquet retenus** | **4 633 708 758** | **4,63** |

Concorde avec le chiffre retenu jusqu'ici (« 4,64 Go en Parquet pour les 4
fichiers retenus »), à l'arrondi près et au mois de publication près.

**Schéma** — le fichier `StockEtablissement` porte désormais un champ
`activitePrincipaleNAF25Etablissement`, ajouté depuis le **16 décembre 2025**
en anticipation du basculement du répertoire vers la nomenclature NAF 2025
(bascule effective prévue début janvier 2027, information lue dans la
description du jeu de données, elle-même datée d'aujourd'hui). C'est la colonne
« à réconcilier » identifiée parmi les 9 colonnes utiles — sa présence
est confirmée par l'API, pas supposée.

**Fréquence de mise à jour et fraîcheur** — mensuelle, dernier stock : **1er
août 2026**, soit vieux de 25 jours à la date de vérification. Cohérent avec
une exigence de fraîcheur mensuelle dans le contrat de données à venir (E14).

**Licence** — Licence Ouverte v2.0 (Etalab), même texte que Parcoursup.
Attribution obligatoire (source : INSEE, base Sirene, date du stock utilisé).

### Écart détecté — volumétrie compressée totale

Le chiffre retenu jusqu'ici était « 11,2 Go compressés au total ». La mesure d'aujourd'hui,
somme des 6 fichiers `.zip` de type stock (StockUniteLegale,
StockEtablissement, StockEtablissementHistorique, StockUniteLegaleHistorique,
StockEtablissementLiensSuccession, StockDoublons) donne :

```
970 595 120 + 2 857 221 335 + 1 233 959 618 + 1 254 072 080 + 118 993 640 + 1 070 052
= 6 435 911 845 octets ≈ 6,44 Go décimal
```

Et la somme des 6 fichiers Parquet correspondants donne **4,75 Go**, cohérent
avec le sous-total des 4 fichiers retenus (4,63 Go) plus les deux petits
fichiers non retenus (liens de succession, doublons).

**Aucune combinaison de ressources du catalogue ne totalise 11,2 Go
aujourd'hui.** Deux explications possibles, non tranchées ici faute de pouvoir
consulter l'état du catalogue au moment où le chiffre a été établi : (1) un
stock antérieur, plus volumineux, a pu être mesuré à cette date — les stocks
Sirene croissent d'un mois sur l'autre ; (2) le chiffre visait la taille des
CSV **décompressés**, pas des `.zip` — plausible, un CSV texte se compresse
généralement à 30-40 % de sa taille d'origine, ce qui rapprocherait 6,44 Go
compressés d'environ 16 à 21,5 Go décompressés (6,44 / 0,40 ≈ 16,1 ; 6,44 /
0,30 ≈ 21,5), pas 11,2 Go non plus. Le chiffre
n'est donc pas reproductible tel quel aujourd'hui. Je le corrige plus loin,
dans la section « Révision des chiffres retenus jusqu'ici », avec la mesure du
jour.

### Nombre d'établissements et d'unités légales — corrigé en E06

Le chiffre « 36 millions d'établissements, 25 millions d'unités légales »,
retenu jusqu'ici, ne figurait dans aucune métadonnée de catalogue : l'analyseur
data.gouv renvoie explicitement `"analysis:error": "File too large to
download"` pour ces ressources — data.gouv lui-même n'a pas pu compter les
lignes. Il fallait lire le fichier Parquet pour trancher. C'est fait à l'étape
E06 (connecteur Sirene), une fois les 4 fichiers réellement téléchargés le
2026-08-28 (`data/raw/sirene/`, manifeste à l'appui) : la métadonnée Parquet
porte le nombre de lignes en clair, sans lire une seule valeur.

```bash
python -c "
import pyarrow.parquet as pq
for f in ['StockEtablissement','StockEtablissementHistorique','StockUniteLegale','StockUniteLegaleHistorique']:
    pf = pq.ParquetFile(f'data/raw/sirene/{f}.parquet')
    print(f, pf.metadata.num_rows, pf.metadata.num_columns)
"
```

Sortie réelle, sur le stock du 01/08/2026 :

| Fichier | Lignes | Colonnes |
|---|---:|---:|
| `StockEtablissement` | **43 896 818** | 54 |
| `StockEtablissementHistorique` | 95 865 102 | 18 |
| `StockUniteLegale` | **29 922 486** | 35 |
| `StockUniteLegaleHistorique` | 71 355 318 | 28 |

**Le chiffre retenu jusqu'ici était sous-estimé** : 43 896 818 établissements
contre 36 millions annoncés, 29 922 486 unités légales contre 25 millions.
Je corrige partout où l'ancien ordre de grandeur figurait — même famille
d'erreur que le « 11,2 Go » et le « ~100 Mo » : un chiffre entré une fois,
jamais revérifié contre le fichier réel une fois qu'il a existé sur disque.

**Cette correction renforce l'argument qui justifie Spark plutôt que
Databricks ou un traitement mono-nœud** (ADR 0002) : le volume à parcourir est
plus élevé que ce qui était annoncé, pas moins.

**La nuance qui compte plus que le chiffre brut** : sur les 43 896 818 lignes
de `StockEtablissement`, les filtres du projet (`etat_administratif: A`,
`caractere_employeur: true`) n'en retiennent que 2 436 624 — 5,6 %. Ce n'est
pas le résultat filtré qui dimensionne le traitement, c'est la **lecture** :
il faut parcourir les 43,9 M de lignes pour savoir lesquelles passent le
filtre. C'est très exactement l'argument de la projection colonnaire déjà
tenu pour ce fichier (9 colonnes sur 54, jamais 54) : réduire tôt, mais on ne
réduit qu'après avoir lu.

**Mesure du jour, chiffres nouveaux, sur les 2 colonnes utiles au filtre**
(`etatAdministratifEtablissement`, `caractereEmployeurEtablissement`) :

```bash
python -c "
import time, pyarrow.parquet as pq, pyarrow.compute as pc
t0 = time.perf_counter()
table = pq.read_table('data/raw/sirene/StockEtablissement.parquet',
    columns=['etatAdministratifEtablissement','caractereEmployeurEtablissement'])
n = table.num_rows
actifs_mask = pc.equal(table.column('etatAdministratifEtablissement'), 'A')
actifs = pc.sum(pc.cast(actifs_mask, 'int64')).as_py()
employeur_mask = pc.equal(table.column('caractereEmployeurEtablissement'), 'O')
both = pc.and_(actifs_mask, employeur_mask)
actifs_employeurs = pc.sum(pc.cast(both, 'int64')).as_py()
print('total', n, 'actifs', actifs, 'actifs_employeurs', actifs_employeurs, 'duree_s', round(time.perf_counter()-t0,1))
"
```

Sortie réelle : **16 715 258 établissements actifs (38,1 % du total)**, dont
**2 436 624 actifs ET employeurs (5,6 % du total)** — c'est ce sous-ensemble
qui constitue un débouché réel au sens du projet (un établissement inactif ou
sans salarié n'en est pas un). Lecture de 2 colonnes sur 54, **35,4 secondes**
sur ce poste : c'est ce chiffre, pas le nombre de lignes filtrées, qui montre
pourquoi un parcours mono-nœud de ce fichier reste praticable en local — et
qui borne le temps qu'un job Spark équivalent devra battre, pas seulement
égaler, pour se justifier (E17).

---

## C. Référentiels — ONISEP (IDÉO) et RNCP (France Compétences)

Établis pour la première fois aujourd'hui.

### C.1 — IDÉO-Formations, IDÉO-Métiers, IDÉO-Structures (ONISEP)

**Identifiants et accès** — 4 jeux, portail data.gouv, données servies par
l'API opendata de l'ONISEP (`api.opendata.onisep.fr`) :

| Jeu | Slug data.gouv | URL CSV |
|---|---|---|
| Idéo-Formations initiales en France | `ideo-formations-initiales-en-france` | `api.opendata.onisep.fr/downloads/5fa591127f501/5fa591127f501.csv` |
| Idéo-Métiers Onisep | `ideo-metiers-onisep` | `api.opendata.onisep.fr/downloads/5fa5949243f97/5fa5949243f97.csv` |
| Idéo-Structures d'enseignement secondaire | `ideo-structures-denseignement-secondaire` | `api.opendata.onisep.fr/downloads/5fa5816ac6a6e/5fa5816ac6a6e.csv` |
| Idéo-Structures d'enseignement supérieur | `ideo-structures-denseignement-superieur` | `api.opendata.onisep.fr/downloads/5fa586da5c4b6/5fa586da5c4b6.csv` |

**Commande exécutée** (taille sans téléchargement, puis nombre de lignes par
téléchargement complet — fichiers de moins de 8 Mo) :

```bash
curl -sSI "https://api.opendata.onisep.fr/downloads/5fa591127f501/5fa591127f501.csv" | grep -i content-length
curl -sS  "https://api.opendata.onisep.fr/downloads/5fa591127f501/5fa591127f501.csv" -o ideo_formations.csv
wc -l ideo_formations.csv
```

**Sortie réelle** :

| Jeu | Taille CSV | Lignes de données | Colonnes | Dernière modification |
|---|---:|---:|---:|---|
| Idéo-Formations | 2 496 480 o (2,5 Mo) | 5 869 | 16 | 2026-07-06 |
| Idéo-Métiers | 644 642 o (0,6 Mo) | 1 534 | 13 | 2026-07-06 |
| Idéo-Structures secondaire | 7 721 120 o (7,7 Mo) | 15 293 | 30 | 2026-07-06 |
| Idéo-Structures supérieur | 5 069 258 o (5,1 Mo) | 8 985 | 29 | 2026-07-06 |

(Lignes de données = lignes du fichier moins l'en-tête ; délimiteur `;`,
encodage avec BOM UTF-8, vérifié sur l'en-tête de chaque fichier.)

Confirme l'ordre de grandeur « référentiels, quelques Mo » retenu jusqu'ici —
4 fichiers pour un total de 15,9 Mo.

**Licence** — `odc-odbl` (Open Database License 1.0), portée par l'organisation
« Office national d'information sur les enseignements et les professions »
(ONISEP) sur data.gouv. Texte :
`https://opendatacommons.org/licenses/odbl/1-0/`. Elle diffère de la Licence
Ouverte Etalab : l'ODbL impose l'attribution **et** le partage à l'identique de
toute base de données dérivée qui serait elle-même redistribuée — une
contrainte à documenter si `naf_rome_formation.csv` (E18) intègre des données
IDÉO et est publié tel quel.

**Fréquence de mise à jour** — `punctual` (ponctuelle) au sens data.gouv :
pas de calendrier de publication garanti. Dernière modification du contenu :
2026-07-06 pour les 4 jeux, à la date de vérification (2026-08-26) une donnée
vieille de 51 jours — à surveiller en E14 comme test de fraîcheur, avec un
seuil à documenter puisqu'aucun engagement de fréquence n'existe côté source.

**Schéma** — nombre de colonnes stable dans le temps à l'échelle où on
l'observe aujourd'hui (un seul instantané disponible, pas d'historique de
schéma exposé par l'API data.gouv pour ces jeux ponctuels) : 16, 13, 30 et 29
colonnes respectivement. La stabilité inter-versions n'est donc **pas
vérifiable** avec les moyens de ce jour — seule la comparaison d'un
téléchargement futur avec celui d'aujourd'hui le permettra.

### C.2 — RNCP et Répertoire spécifique (France Compétences)

**Identifiant et accès** — jeu
`repertoire-national-des-certifications-professionnelles-et-repertoire-specifique`
sur data.gouv, organisation France Compétences.

```
https://www.data.gouv.fr/api/1/datasets/repertoire-national-des-certifications-professionnelles-et-repertoire-specifique/
```

**Commande exécutée** :

```bash
curl -sS "https://www.data.gouv.fr/api/1/datasets/repertoire-national-des-certifications-professionnelles-et-repertoire-specifique/"
```

**Sortie réelle** — **8 362 ressources** : un export complet (RNCP + RS, aux
formats CSV et XML v3/v4) publié **chaque jour**, chaque export daté et
horodaté séparément et jamais supprimé (l'historique complet reste
téléchargeable). Licence `lov2` (Licence Ouverte v2.0, Etalab).

**Export du jour exact de la vérification (2026-08-26)** :

| Export | Taille |
|---|---:|
| `export-fiches-rncp-v4-1-2026-08-26.zip` | 74 198 555 o (70,8 Mio) |
| `export-fiches-rs-v4-1-2026-08-26.zip` | 11 862 025 o (11,3 Mio) |
| `export-fiches-csv-2026-08-26.zip` | 9 607 237 o (9,2 Mio) |

**Nombre d'enregistrements — obtenu en dépouillant l'export CSV du jour**
(téléchargé et compté, taille 9,2 Mo, en dessous du seuil qui justifierait un
prétraitement distribué) :

```bash
curl -sS "https://static.data.gouv.fr/resources/repertoire-national-des-certifications-professionnelles-et-repertoire-specifique/20260826-020002/export-fiches-csv-2026-08-26.zip" \
  -o export-fiches-csv-2026-08-26.zip
unzip export-fiches-csv-2026-08-26.zip
wc -l export_fiches_CSV_Standard_2026_08_25.csv
grep -c '"ACTIVE"' export_fiches_CSV_Standard_2026_08_25.csv
```

Sortie obtenue le 26/08, **annoncée à tort ici** : **36 000 fiches** au total
dans le fichier « Standard », dont **6 995 fiches actives**. Cette valeur est
**corrigée ci-dessous (⚠️ correction du 2026-08-29)** : elle est fausse, mais
pas pour la raison qu'on croirait — voir le détail.

⚠️ **Correction du 2026-08-29 — un chiffre faussé par l'outil de mesure, pas
par la source.** En construisant le connecteur E07, le nombre de fiches
réellement écrit dans `data/external/referentiels/rncp/manifeste.json` ne
correspondait pas au chiffre ci-dessus. Cause : `wc -l` compte des retours à la
ligne **physiques**. Le CSV RNCP contient des champs de texte entre guillemets
qui s'étendent sur plusieurs lignes (des intitulés de certification avec des
sauts de ligne internes) : chaque saut de ligne interne à un champ est compté
par `wc -l` comme si c'était une fiche supplémentaire. Un parseur CSV qui
respecte les guillemets (module `csv` de Python, ou tout outil équivalent) ne
s'y trompe pas :

```bash
python -c "
import csv
with open('data/external/referentiels/rncp/rncp_2026-08-29.csv', encoding='utf-8') as f:
    r = csv.reader(f, delimiter=';')
    header = next(r)
    idx = header.index('Actif')
    rows = list(r)
    print('total', len(rows), 'actives', sum(1 for row in rows if row[idx] == 'ACTIVE'))
"
```

Sortie réelle, export du **2026-08-29** : **total 30 484, actives 7 000**.
La somme confirme le compte : 7 000 + 23 484 (inactives) = 30 484. Le chiffre
« 36 000 » ne se reproduit avec aucun parseur CSV correct — l'écart (5 522
lignes en trop) est entièrement absorbé par les retours à la ligne internes
aux champs multi-lignes, pas par des fiches en plus ou en moins.

Le compte des actives, lui, **survivait par coïncidence** : la chaîne
`"ACTIVE"` n'apparaît jamais à l'intérieur d'un champ multi-ligne dans cet
export, donc `grep -c '"ACTIVE"'` retombait juste sur le nombre de fiches
actives sans que ce soit garanti par construction — un futur export où cette
chaîne apparaîtrait dans un intitulé de certification romprait ce hasard
favorable sans qu'aucun signal ne le révèle.

**`scripts/verifier_sources.sh` comptait avec `wc -l` et `grep -c`, donc
l'outil de vérification produisait lui-même un chiffre faux** — c'est
distinct d'un chiffre mal recopié depuis une source correcte : ici l'outil
censé garantir l'exactitude était la cause de l'erreur. Le script est corrigé
pour compter avec un vrai parseur CSV (voir le commentaire qui l'explique dans
le fichier). Le comptage des colonnes IDÉO par `head -1 | tr ';' '\n' | wc -l`
a été revu par la même occasion et remplacé par le même parseur, par cohérence
— vérifié : il ne produisait pas de chiffre faux sur les 4 fichiers IDÉO
d'aujourd'hui (aucun champ multi-ligne dans ces fichiers), mais rien ne
garantissait que ce resterait vrai.

**16 colonnes** (`Id_Fiche`, `Numero_Fiche`, `Intitule`,
`Nomenclature_Europe_Niveau`, `Date_Fin_Enregistrement`, `Actif`, etc.),
délimiteur `;`.

⚠️ **Correction du 2026-08-29 — encodage annoncé à tort.** La documentation du
26/08 annonçait l'export RNCP en **Latin-1**. Vérification sur le fichier
réellement téléchargé pour E07 : les octets `\xc3\xa9` codent la lettre « é »,
ce qui est la séquence UTF-8, pas Latin-1 — et le fichier entier décode sans
erreur en UTF-8. L'export est donc en **UTF-8**, pas en Latin-1.

La nuance qui compte plus que la correction : **Latin-1 ne lève jamais
d'erreur de décodage**, quel que soit le fichier — il associe un caractère à
chacun des 256 octets possibles. Constater que « le fichier se décode en
Latin-1 sans exception » ne prouve donc rien : un fichier réellement en UTF-8
lu en Latin-1 se décode aussi sans erreur, silencieusement, et donne un texte
corrompu (`comptabilitÃ©` au lieu de `comptabilité`), pas une exception qui
alerterait. C'est pour cette raison que le contrôle d'encodage du connecteur
(`verifier_encodage`, dans `_referentiels_communs.py`) est **asymétrique** : il
détecte un fichier réellement en Latin-1 déclaré UTF-8 (UTF-8 rejette
certaines suites d'octets, l'erreur remonte), mais ne peut pas détecter
l'inverse — un fichier réellement en UTF-8 déclaré Latin-1 ne fait jamais
échouer le décodage. Cette limite est assumée dans le code, pas corrigée :
aucune des deux sources configurées aujourd'hui ne déclare `latin-1`, le
risque n'est donc pas actif, mais il existerait dès qu'une configuration le
ferait.

**Nom de fichier du connecteur** : `rncp_{date_publication_jour}.csv`
(`rncp_2026-08-29.csv` pour l'export d'aujourd'hui), pas un nom fixe écrasé à
chaque exécution — voir `03-pipeline/ingestion.md` et l'ADR 0007 pour la
raison.

Commande figée telle qu'exécutée le 26/08 — l'URL contient la date de l'export
et change chaque jour ; la version rejouable qui résout cette URL depuis
l'API sans date en dur est dans `scripts/verifier_sources.sh`, section
« C. RNCP/RS ».

⚠️ Décalage de date à noter : l'archive zip est datée du jour de la vérification (26/08), mais le fichier CSV qu'elle contient porte la date de la veille (25/08) — l'export est généré peu après minuit et référence le travail de la journée précédente. Ce n'est pas une incohérence, c'est le fonctionnement normal de la publication quotidienne de France Compétences ; un connecteur (E07) doit résoudre le nom du fichier par motif (`export_fiches_CSV_Standard_*.csv`) plutôt que par date fixe, exactement comme le fait le script.

⚠️ Chiffre daté, commande stable : l'export RNCP/RS est republié chaque jour, donc le nombre exact de fiches (36 000 / 6 995 actives) bougera à la prochaine exécution. La **commande** est reproductible à l'identique ; la **sortie** ne l'est pas — c'est attendu, pas une erreur de vérification.

**Licence** — Licence Ouverte v2.0 (Etalab), texte identique à Parcoursup et
Sirene. Attribution : France Compétences, RNCP/RS, date de l'export utilisé.

**Fréquence de mise à jour** — quotidienne, publication automatisée
(`08362` ressources cumulées démontrent un historique quotidien conservé
depuis plusieurs années). C'est la source la plus fraîche du projet : aucune
donnée du modèle ne dépendra directement de cette fraîcheur (le RNCP sert de
table de réconciliation NAF↔ROME↔formation à E18, recalculée à chaque
exécution du pipeline, pas de latence critique).

### C.3 — RNCP, membre ROME de l'archive quotidienne (E18)

**Identifiant et accès** — même archive quotidienne que C.2, un membre
distinct du CSV standard : `rncp_rome_2026-08-30.csv`, extrait de la même
archive ZIP par un motif de nom, comme le CSV standard. Ce membre existait
dans l'archive depuis le début, mais le connecteur de E07 n'en extrayait
qu'un seul CSV sur les dix qu'elle contient — l'extension a été faite en E18,
au moment où la réconciliation NAF↔ROME↔formation en a eu besoin.

**Contenu** — 3 colonnes : `Numero_Fiche`, `Codes_Rome_Code`,
`Codes_Rome_Libelle`. Une ligne par couple (fiche RNCP, code ROME) : une
fiche peut couvrir plusieurs métiers.

**Sortie mesurée, export du 2026-08-30** : **4 353 036 octets**, **24 424**
fiches distinctes couvrant au moins un code ROME (100 % des fiches de cet
export, par construction).

**Licence** — Licence Ouverte v2.0 (Etalab), identique au CSV standard de la
même archive (section C.2).

### C.4 — France Travail, table de correspondance ROME/NAF (E18)

**Identifiant et accès** — jeu de données data.gouv publié par France
Travail, ressource résolue par sous-chaîne de titre (« Les tables de
correspondance ROME / autres référentiels - ROME/NAF »), le nom de fichier
changeant à chaque révision du ROME.

**Fichier obtenu le 2026-08-30** :
`rome-arborescence-des-secteurs-naf-juin-2026.xlsx`, **112 896 octets**.

**Contenu** — un classeur Excel dont une feuille (« Secteur NAF ») porte une
arborescence implicite : une ligne « division NAF » (2 chiffres) précède les
lignes « code ROME » qui lui sont rattachées. La correspondance s'arrête à la
**division NAF (2 chiffres)** — jamais à la sous-classe complète (5
caractères) que porte le champ NAF de l'agrégat Sirene (E17).

**Licence** — Licence Ouverte v2.0 (Etalab), même texte que Parcoursup,
Sirene et RNCP.

**Fréquence de mise à jour** — pas de cadence de republication connue
(contrairement à Sirene, mensuel, et RNCP, quotidien) : l'idempotence du
connecteur repose sur une empreinte SHA-256, pas sur une date de publication.

### Note de gouvernance — la table dérivée E18 mêle deux régimes de licence

`naf_rome_formation.csv` (E18) assemble IDÉO (ODbL, section C.1), le membre
ROME et le CSV standard de l'archive RNCP (Licence Ouverte v2.0, sections
C.2 et C.3) et la table France Travail ROME/NAF (Licence Ouverte v2.0,
section C.4). Elle intègre des données IDÉO (le libellé de formation) : la
clause de partage à l'identique de l'ODbL s'applique donc potentiellement à
cette base dérivée si elle est redistribuée telle quelle. Cette question
n'est pas tranchée ici — elle relève de la gouvernance (registre des
sources, E40) et sera reprise à ce titre.

---

## Révision des chiffres retenus jusqu'ici

### Chiffres confirmés à l'identique

- Les 8 volumétries Parcoursup (10 697 → 14 252 formations par millésime) et le
  total **104 274 formation-années**.
- 118 colonnes en 2025.
- **106 champs communs entre 2020 et 2025** (chiffre retenu jusqu'ici,
  reproduit exactement).
- Licence Ouverte v2.0 (Etalab) pour Parcoursup et Sirene.
- Sirene : taille des 4 fichiers Parquet retenus, **4,63 Go** aujourd'hui contre
  **4,64 Go** retenu jusqu'ici — écart de 0,01 Go, imputable à l'arrondi et au
  fait que le stock a été republié entre-temps (mois différent). Le détail par
  fichier (2,20 / 0,87 / 0,86 / 0,71 Go) est identique au chiffre près.
- URL Sirene mensuelles, confirmées volatiles (dernier stock : 01/08/2026).

### Chiffre corrigé

- **« 11,2 Go compressés au total »** (Sirene) : ce chiffre, retenu jusqu'ici,
  ne se reproduit plus aujourd'hui — non reproductible avec aucune combinaison
  de ressources du catalogue actuel. Mesuré ce jour : **6,44 Go** pour les 6
  fichiers `.zip` de type stock, **4,75 Go** pour les 6 fichiers Parquet
  correspondants. J'ai corrigé la valeur retenue vers **6,44 Go** (zip, taille
  compressée), en précisant explicitement que « compressé » désigne le zip et
  non un CSV décompressé, datée au stock du 01/08/2026, et propagé la
  correction partout où l'ancien chiffre figurait.
- **« 36 millions d'établissements, 25 millions d'unités légales »** : chiffre
  sous-estimé, jamais recalculé depuis sa première mesure. Compté aujourd'hui
  par métadonnée Parquet une fois les fichiers réellement posés sur disque
  (E06) : **43 896 818 établissements, 29 922 486 unités légales**, stock du
  01/08/2026. Voir la section B ci-dessus pour la commande et le détail des 4
  fichiers. Corrigé partout où l'ancien ordre de grandeur figurait.
- **« 36 000 fiches RNCP, dont 6 995 actives »** (2026-08-29) : chiffre faussé
  non par la source, mais par l'outil de mesure — `wc -l` sur un CSV à champs
  multi-lignes. Le vrai total, obtenu par un parseur CSV respectant les
  guillemets, est **30 484 fiches (7 000 actives, 23 484 inactives)**, export
  du 2026-08-29. `scripts/verifier_sources.sh` est corrigé pour compter avec
  ce parseur. Voir la section C.2 pour le détail complet et la commande.
- **« Encodage Latin-1 » pour le RNCP** (2026-08-29) : faux — le fichier
  réellement téléchargé décode intégralement en **UTF-8** (`\xc3\xa9` = « é »
  en UTF-8). Voir la section C.2 pour la nuance méthodologique : un fichier se
  décodant sans erreur en Latin-1 ne prouve rien, Latin-1 acceptant n'importe
  quelle suite d'octets.

### Chiffres non vérifiables aujourd'hui par cette méthode

- **Taille en octets des 8 CSV Parcoursup** : invérifiable par l'API de
  métadonnées (pas de `Content-Length`), hors périmètre de cette vérification
  du 26/08. **Mesurée depuis, en E05** (2026-08-28) une fois les fichiers
  posés sur disque : **82 Mo**, contre « ~100 Mo » retenu jusque-là — voir la
  section A ci-dessus et `avancement.md`.

### Chiffres nouveaux, établis aujourd'hui

- IDÉO-Formations : 5 869 formations, 16 colonnes, 2,5 Mo.
- IDÉO-Métiers : 1 534 métiers, 13 colonnes, 0,6 Mo.
- IDÉO-Structures secondaire : 15 293 structures, 30 colonnes, 7,7 Mo.
- IDÉO-Structures supérieur : 8 985 structures, 29 colonnes, 5,1 Mo.
- RNCP/RS : **30 484 fiches (7 000 actives, 23 484 inactives)**, export
  quotidien du **2026-08-29**, 16 colonnes, 9,2 Mo (export CSV du jour) —
  chiffre corrigé le 2026-08-29, voir « Chiffre corrigé » ci-dessus et la
  section C.2.
- Licence des jeux ONISEP : ODbL (`odc-odbl`), distincte de la Licence Ouverte
  utilisée par Parcoursup, Sirene et RNCP — implication de partage à
  l'identique à documenter avant toute redistribution d'un dérivé.
- Transition NAF 2025 sur Sirene : champ `activitePrincipaleNAF25Etablissement`
  ajouté le 16/12/2025, bascule complète prévue début janvier 2027 — fait
  nouveau qui touche directement à la réconciliation NAF↔ROME (E18) et devra
  être suivi dans le temps.
- Sur `StockEtablissement` (43 896 818 lignes) : **16 715 258 établissements
  actifs (38,1 %)**, dont **2 436 624 actifs ET employeurs (5,6 %)** — c'est ce
  dernier sous-ensemble qui constitue un débouché réel au sens du projet.
  Lecture de 2 colonnes sur 54 en **35,4 secondes** sur ce poste.
