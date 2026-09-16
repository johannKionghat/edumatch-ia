# Vérification des sources

Chaque chiffre de cette page est reproduit par une commande, exécutée
contre le catalogue de la source — pas contre un téléchargement complet
quand ce n'est pas nécessaire. Le script qui les rejoue toutes est
`scripts/verifier_sources.sh`. Un échantillon versionné de chaque source
est disponible dans `data/samples/`, détaillé dans
`01-donnees/echantillons.md`.

## Méthode

Les gros fichiers (8 CSV Parcoursup, 11 fichiers Sirene) ne sont jamais
téléchargés pour cette vérification : j'interroge les API de métadonnées
(`api/explore/v2.1` côté opendatasoft pour Parcoursup, `api/1/datasets/...`
côté data.gouv pour Sirene et RNCP), qui renvoient nombre
d'enregistrements, colonnes, taille et date de publication sans rapatrier
la donnée. Les référentiels ONISEP (quelques Mo chacun) sont téléchargés
en entier : à cette taille c'est le seul moyen d'obtenir un nombre de
lignes exact.

Outils : `curl`, `python -c` pour parser le JSON.

---

## A. Parcoursup (MESR)

Un jeu de données par millésime, sur le portail opendatasoft du MESR.
Export CSV à la demande, pas de fichier stocké :

```
https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets/{id}/exports/csv?delimiter=%3B
```

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

**Total : 104 274 formation-années.**

**Licence** — Licence Ouverte v2.0 (Etalab). Elle oblige à mentionner la
source (MESR, Parcoursup) et la date de dernière mise à jour de la donnée
réutilisée ; elle n'impose ni partage à l'identique ni restriction d'usage
commercial.

**Schéma** — nombre de colonnes croissant : 85 en 2018, 92 en 2019, 115 en
2020, 118 à partir de 2021. Le MESR a ajouté des champs au fil des
sessions (mentions, néo-bacheliers, académie d'origine).

**Stabilité inter-millésimes**, mesurée par intersection des noms de
champs : **106 champs communs entre 2020 et 2025**, **83 champs communs
sur les 8 sessions** (2018 → 2025). La liste commune est dominée par les
compteurs de vœux et d'admis (`nb_voe_pp_*`, `acc_*`, `pct_*`) et les
identifiants de formation (`cod_uai`, `fili`, `dep`) : c'est le socle
disponible sur toute la période. Ça ne suffit pas à entraîner un modèle
sur les huit sessions : le numérateur du label n'existe qu'à partir de
2020 (détail dans `01-donnees/label.md`).

**Fréquence** — annuelle : un jeu par session Parcoursup, publié en fin de
campagne (juillet à octobre selon les années).

**Volumétrie** — 82 Mo au total sur `data/raw/parcoursup/`, mesurée une
fois les 8 millésimes téléchargés par `ingestion/parcoursup.py`.

---

## B. Sirene (INSEE)

Jeu `base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret`
sur data.gouv. Les URL de téléchargement changent chaque mois (nouveau
stock publié) : le connecteur interroge le point d'entrée stable du
catalogue, jamais une URL codée en dur.

```
https://www.data.gouv.fr/api/1/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/
```

24 ressources, dernier stock publié le **01/08/2026**, fréquence
mensuelle, licence `lov2` (Licence Ouverte v2.0, même texte que
Parcoursup).

**Volumétrie des 4 fichiers Parquet retenus, stock du 01/08/2026** :

| Fichier | Taille (octets) | Go décimal |
|---|---:|---:|
| `StockEtablissement` | 2 202 341 459 | 2,20 |
| `StockEtablissementHistorique` | 870 319 380 | 0,87 |
| `StockUniteLegaleHistorique` | 855 957 649 | 0,86 |
| `StockUniteLegale` | 705 090 270 | 0,71 |
| **Total 4 fichiers Parquet retenus** | **4 633 708 758** | **4,63** |

Les 6 fichiers `.zip` de type stock (les 4 ci-dessus, plus liens de
succession et doublons) totalisent **6,44 Go** compressés ; les 6 fichiers
Parquet correspondants totalisent **4,75 Go**.

**Schéma** — `StockEtablissement` porte un champ
`activitePrincipaleNAF25Etablissement`, ajouté depuis le 16 décembre 2025
en anticipation du basculement vers la nomenclature NAF 2025 (bascule
prévue début janvier 2027). C'est la colonne à réconcilier parmi les 9
colonnes utiles du projet.

**Fréquence et fraîcheur** — mensuelle, dernier stock du 1er août 2026.

**Licence** — Licence Ouverte v2.0 (Etalab). Attribution obligatoire
(source INSEE, base Sirene, date du stock utilisé).

### Nombre de lignes

Les analyseurs de data.gouv renvoient `"analysis:error": "File too large
to download"` pour ces ressources : il faut lire le fichier Parquet pour
compter, ce qui donne le nombre de lignes via la métadonnée, sans lire une
seule valeur :

```bash
python -c "
import pyarrow.parquet as pq
for f in ['StockEtablissement','StockEtablissementHistorique','StockUniteLegale','StockUniteLegaleHistorique']:
    pf = pq.ParquetFile(f'data/raw/sirene/{f}.parquet')
    print(f, pf.metadata.num_rows, pf.metadata.num_columns)
"
```

| Fichier | Lignes | Colonnes |
|---|---:|---:|
| `StockEtablissement` | **43 896 818** | 54 |
| `StockEtablissementHistorique` | 95 865 102 | 18 |
| `StockUniteLegale` | **29 922 486** | 35 |
| `StockUniteLegaleHistorique` | 71 355 318 | 28 |

Ce volume renforce l'argument qui justifie Spark plutôt que Databricks ou
un traitement mono-nœud (ADR 0002).

**La nuance qui compte plus que le total** : sur les 43 896 818 lignes de
`StockEtablissement`, les filtres du projet (`etat_administratif: A`,
`caractere_employeur: true`) n'en retiennent que 2 436 624, soit 5,6 %. Ce
n'est pas le résultat filtré qui dimensionne le traitement, c'est la
lecture : il faut parcourir les 43,9 M de lignes pour savoir lesquelles
passent le filtre. C'est l'argument de la projection colonnaire (9
colonnes sur 54, jamais 54) : réduire tôt, mais après avoir lu.

Lecture des 2 colonnes utiles au filtre
(`etatAdministratifEtablissement`, `caractereEmployeurEtablissement`) :
**16 715 258 établissements actifs (38,1 % du total)**, dont
**2 436 624 actifs ET employeurs (5,6 % du total)** — c'est ce
sous-ensemble qui constitue un débouché réel au sens du projet. Lecture de
2 colonnes sur 54, **35,4 secondes**. Ce chiffre montre pourquoi un
parcours mono-nœud de ce fichier reste praticable en local, et borne le
temps qu'un job Spark équivalent doit battre pour se justifier (E17).

---

## C. Référentiels — ONISEP (IDÉO) et RNCP (France Compétences)

### C.1 — IDÉO-Formations, IDÉO-Métiers, IDÉO-Structures (ONISEP)

4 jeux, portail data.gouv, données servies par l'API opendata de l'ONISEP
(`api.opendata.onisep.fr`) :

| Jeu | Taille CSV | Lignes de données | Colonnes | Dernière modification |
|---|---:|---:|---:|---|
| Idéo-Formations | 2,5 Mo | 5 869 | 16 | 2026-07-06 |
| Idéo-Métiers | 0,6 Mo | 1 534 | 13 | 2026-07-06 |
| Idéo-Structures secondaire | 7,7 Mo | 15 293 | 30 | 2026-07-06 |
| Idéo-Structures supérieur | 5,1 Mo | 8 985 | 29 | 2026-07-06 |

(Lignes de données = lignes du fichier moins l'en-tête ; délimiteur `;`,
encodage avec BOM UTF-8.)

4 fichiers pour un total de 15,9 Mo.

**Licence** — `odc-odbl` (Open Database License 1.0), portée par
l'ONISEP sur data.gouv. Elle diffère de la Licence Ouverte Etalab :
l'ODbL impose l'attribution et le partage à l'identique de toute base
dérivée redistribuée — une contrainte pour `naf_rome_formation.csv` (E18)
si elle intègre des données IDÉO et est publiée telle quelle.

**Fréquence** — ponctuelle au sens data.gouv, pas de calendrier de
publication garanti. Dernière modification du contenu : 2026-07-06 pour
les 4 jeux — à surveiller en E14 comme test de fraîcheur.

### C.2 — RNCP et Répertoire spécifique (France Compétences)

Jeu `repertoire-national-des-certifications-professionnelles-et-repertoire-specifique`
sur data.gouv, organisation France Compétences. 8 362 ressources : un
export complet (RNCP + RS, CSV et XML v3/v4) publié chaque jour, jamais
supprimé. Licence `lov2` (Licence Ouverte v2.0, Etalab).

**Nombre d'enregistrements** — un comptage naïf par `wc -l` sur le CSV
donne un chiffre faux : le fichier contient des champs texte entre
guillemets qui s'étendent sur plusieurs lignes (intitulés de certification
avec sauts de ligne internes), que `wc -l` compte à tort comme des lignes
supplémentaires. Un parseur qui respecte les guillemets (module `csv` de
Python) donne le compte correct :

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

Export du **2026-08-29** : **30 484 fiches, dont 7 000 actives** (23 484
inactives). 16 colonnes (`Id_Fiche`, `Numero_Fiche`, `Intitule`,
`Nomenclature_Europe_Niveau`, `Date_Fin_Enregistrement`, `Actif`, etc.),
délimiteur `;`. `scripts/verifier_sources.sh` compte avec ce même
parseur, y compris pour les fichiers IDÉO, par cohérence.

**Encodage** — UTF-8, vérifié sur les octets bruts (`\xc3\xa9` code la
lettre « é » en UTF-8, pas en Latin-1). Un fichier réellement en UTF-8 lu
en Latin-1 se décode aussi sans erreur, mais produit un texte corrompu
(`comptabilitÃ©` au lieu de `comptabilité`) sans jamais lever d'exception
— c'est pour cette raison que le contrôle d'encodage du connecteur
(`verifier_encodage`) est asymétrique : il détecte un fichier réellement
en Latin-1 déclaré UTF-8, mais pas l'inverse.

**Nom de fichier du connecteur** : `rncp_{date_publication_jour}.csv`, pas
un nom fixe écrasé à chaque exécution (voir `03-pipeline/ingestion.md` et
l'ADR 0007).

L'archive zip est datée du jour de la vérification, mais le CSV qu'elle
contient porte la date de la veille — l'export est généré peu après
minuit et référence le travail de la veille. Le connecteur résout le nom
du fichier par motif (`export_fiches_CSV_Standard_*.csv`), pas par date
fixe.

L'export étant republié chaque jour, le nombre exact de fiches change
d'une exécution à l'autre : la commande est reproductible, la sortie ne
l'est pas.

**Licence** — Licence Ouverte v2.0 (Etalab), identique à Parcoursup et
Sirene.

**Fréquence** — quotidienne, publication automatisée. C'est la source la
plus fraîche du projet ; le RNCP sert de table de réconciliation
NAF↔ROME↔formation (E18), recalculée à chaque exécution du pipeline.

### C.3 — RNCP, membre ROME de l'archive quotidienne (E18)

Même archive quotidienne que C.2, un membre distinct :
`rncp_rome_2026-08-30.csv`. 3 colonnes : `Numero_Fiche`,
`Codes_Rome_Code`, `Codes_Rome_Libelle` — une ligne par couple (fiche
RNCP, code ROME), une fiche pouvant couvrir plusieurs métiers.

Export du 2026-08-30 : **4 353 036 octets**, **24 424** fiches distinctes
couvrant au moins un code ROME (100 % des fiches de cet export).

**Licence** — Licence Ouverte v2.0 (Etalab).

### C.4 — France Travail, table de correspondance ROME/NAF (E18)

Jeu data.gouv publié par France Travail, ressource résolue par
sous-chaîne de titre (« Les tables de correspondance ROME / autres
référentiels - ROME/NAF »), le nom de fichier changeant à chaque révision
du ROME. Fichier obtenu le 2026-08-30 :
`rome-arborescence-des-secteurs-naf-juin-2026.xlsx`, 112 896 octets.

Un classeur Excel dont une feuille (« Secteur NAF ») porte une
arborescence implicite : une ligne « division NAF » (2 chiffres) précède
les codes ROME rattachés. La correspondance s'arrête à la division NAF (2
chiffres), jamais à la sous-classe complète (5 caractères) que porte le
champ NAF de l'agrégat Sirene (E17).

**Licence** — Licence Ouverte v2.0 (Etalab).

**Fréquence** — pas de cadence de republication connue : l'idempotence du
connecteur repose sur une empreinte SHA-256, pas sur une date de
publication.

### Note de gouvernance

`naf_rome_formation.csv` (E18) assemble IDÉO (ODbL), le membre ROME et le
CSV standard de l'archive RNCP (Licence Ouverte v2.0) et la table France
Travail ROME/NAF (Licence Ouverte v2.0). Elle intègre le libellé de
formation IDÉO : la clause de partage à l'identique de l'ODbL s'applique
donc potentiellement à cette base dérivée si elle est redistribuée telle
quelle — question reprise au titre du registre des sources (E40).
