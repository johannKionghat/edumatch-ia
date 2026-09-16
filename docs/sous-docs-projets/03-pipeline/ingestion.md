# Ingestion — les connecteurs

**Dernière mise à jour** : 2026-08-30 (E18).

Cette page couvre les trois connecteurs opérationnels à ce jour — Parcoursup,
Sirene et référentiels — et les primitives qu'ils partagent. Elle sert de
preuve au critère 3.2 (ELT entre sources hétérogènes) du Bloc 3 : trois
sources, trois stratégies de résolution d'URL, chacune justifiée par la
façon dont la source publie ses fichiers. Elle sert aussi au critère 3.6
(idempotence des tâches) : trois grains d'idempotence différents, du fichier
qui ne change jamais une fois publié (Parcoursup) au fichier réexporté
chaque jour (RNCP).

**Mise à jour du 2026-08-30 (E18)** : le volet référentiels s'est étendu de
deux façons, décrites plus bas : l'extraction d'un second membre de
l'archive RNCP quotidienne, et une source nouvelle, la table France Travail
ROME/NAF. Un correctif d'encodage touchant la primitive d'écriture atomique,
commune à tout connecteur, est aussi décrit dans « Écriture atomique ».

## Ce qui existe

| Fichier | Rôle |
|---|---|
| `src/edumatch/ingestion/_flux.py` | Primitives communes à tout connecteur : session HTTP, téléchargement en flux, empreinte, écriture atomique, manifeste |
| `src/edumatch/ingestion/parcoursup.py` | Connecteur Parcoursup : résolution d'URL par gabarit, orchestration des 8 millésimes |
| `src/edumatch/ingestion/sirene.py` | Connecteur Sirene : résolution d'URL par interrogation du catalogue data.gouv, orchestration des 4 fichiers stock |
| `src/edumatch/ingestion/referentiels.py` | Connecteur référentiels : point d'entrée public, volet IDÉO (URL fixe) |
| `src/edumatch/ingestion/_referentiels_rncp.py` | Volet RNCP : résolution de l'export quotidien, extraction de **deux** membres depuis l'archive ZIP — le CSV standard et, depuis E18, le CSV de correspondance RNCP↔ROME |
| `src/edumatch/ingestion/_referentiels_france_travail.py` | Volet France Travail (E18) : résolution par titre de ressource dans le catalogue, table de correspondance ROME/NAF |
| `src/edumatch/ingestion/_referentiels_communs.py` | Vocabulaire d'erreur et primitives propres aux volets du connecteur référentiels |
| `src/edumatch/ingestion/echantillons.py` | Génération de `data/samples/`, l'échantillon versionné des trois sources |

## Le connecteur Parcoursup

`telecharger_millesime(millesime, settings, session, forcer)` télécharge
l'export CSV d'un millésime déclaré dans `configs/base.yaml`
(`donnees.parcoursup.millesimes` et `.identifiants`) vers
`data/raw/parcoursup/parcoursup_{millesime}.csv`. `telecharger_tous()`
répète l'opération pour tous les millésimes configurés, sur une session HTTP
unique.

L'URL est construite à partir d'un gabarit fixe et de l'identifiant du
millésime :

```
https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets/{identifiant}/exports/csv?delimiter=%3B
```

Aucune URL, aucun identifiant, aucun chemin n'est écrit en dur dans le code :
tout vient de `Settings` (E04).

### Volumétrie mesurée

| Millésime | Formations | Colonnes |
|---|---:|---:|
| 2018 | 10 697 | 85 |
| 2019 | 11 577 | 92 |
| 2020 | 12 760 | 115 |
| 2021 | 13 396 | 118 |
| 2022 | 13 644 | 118 |
| 2023 | 13 869 | 118 |
| 2024 | 14 079 | 118 |
| 2025 | 14 252 | 118 |
| **Total** | **104 274** | — |

Compté directement sur les fichiers posés sur `data/raw/parcoursup/` (une
ligne par en-tête + comptage des lignes de données), pas depuis l'API de
métadonnées. Reproductible :

```bash
python -c "
import csv
for y in range(2018, 2026):
    with open(f'data/raw/parcoursup/parcoursup_{y}.csv', encoding='utf-8') as f:
        r = csv.reader(f, delimiter=';')
        header = next(r)
        n = sum(1 for _ in r)
        print(y, n, len(header))
"
```

**Poids sur disque des 8 CSV : 82 Mo** (`du -sh data/raw/parcoursup/`,
mesuré le 2026-08-28). Ce chiffre corrige l'estimation « ~100 Mo » retenue
jusqu'ici, un ordre de grandeur jamais mesuré faute de fichier réellement
téléchargé, l'export de l'API n'annonçant pas sa taille (`Content-Length`
absent, transfert « chunked »). Détail de la correction dans
`01-donnees/sources.md` et `avancement.md`.

**Dérive de schéma entre millésimes** : 85 colonnes en 2018, 92 en 2019, 115
en 2020, stable à 118 à partir de 2021. Ce n'est pas une anomalie : le MESR a
ajouté des champs au fil des sessions (détail des mentions, néo-bacheliers,
académie d'origine). C'est la matière de la réconciliation de schéma prévue
en E15 (dbt bronze → silver).

## Le connecteur Sirene

`resoudre_ressources(settings, session)` interroge le catalogue data.gouv du
jeu `base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret`
(`donnees.sirene.url_catalogue_gabarit`, un seul appel JSON léger, aucun
fichier de données transféré) et en extrait l'URL Parquet courante des 4
fichiers configurés (`donnees.sirene.fichiers`). `telecharger_fichier`
prend ensuite le relais avec les mêmes garanties que Parcoursup :
idempotence par empreinte, écriture atomique, manifeste. `telecharger_tous()`
enchaîne les deux sur une session HTTP unique.

### Trois sources, trois stratégies de résolution d'URL — pourquoi

| | Parcoursup | Sirene | Référentiels — IDÉO | Référentiels — RNCP |
|---|---|---|---|---|
| Forme de l'URL | Gabarit fixe + identifiant du millésime | Résolue à l'exécution par requête au catalogue | URL fixe, un fichier par jeu | Résolue à l'exécution par requête au catalogue, **puis** extraction d'un membre depuis une archive ZIP |
| Ce qui varie | Un identifiant par millésime, stable une fois publié | L'URL entière, republiée chaque mois | Rien : les 4 URL ne changent jamais | L'URL de l'archive, republiée **chaque jour** |
| Stockage en configuration | Le gabarit et les 8 identifiants (`configs/base.yaml`) | Le nom du jeu de données et le gabarit de **l'API du catalogue**, jamais une URL de fichier | Les 4 URL, écrites telles quelles | Le nom du jeu de données, le gabarit du catalogue, le préfixe de ressource attendu (`export-fiches-csv-`) et le motif du fichier à extraire dans l'archive |
| Grain de l'idempotence | Un fichier par millésime, jamais réécrit une fois publié | Un fichier par stock mensuel, écrasé si republié dans le même mois | Un fichier par jeu, écrasé seulement si le contenu a changé (empreinte) | **Un fichier par date de publication** (`rncp_AAAA-MM-JJ.csv`), jamais écrasé — voir plus bas |
| Coût de la stratégie | Aucun appel réseau supplémentaire avant le téléchargement | Un appel de résolution avant chaque exécution ; échoue si le catalogue est indisponible ou a renommé une ressource | Aucun appel supplémentaire, mais aucune protection si l'ONISEP change une URL sans préavis | Un appel de résolution, plus un décodage de ZIP en mémoire (~9 Mo, sous le seuil qui justifierait un flux) |

Parcoursup republie un export par session sous un identifiant qui, une fois
connu, ne change plus : un gabarit d'URL en configuration reste vrai d'une
exécution à l'autre. Sirene republie un stock complet chaque mois, sous un
chemin qui contient l'horodatage de publication
(`.../20260801-074451/stock-stocketablissement-parquet.parquet` pour le
stock du jour) : coder ce chemin en dur casserait le connecteur dès le mois
suivant. IDÉO ne republie (à ce jour) sous aucun horodatage : 4 URL fixes
suffisent. Le RNCP cumule les deux difficultés : comme Sirene, l'URL change
à chaque republication (ici quotidienne) et se résout par requête au
catalogue ; en plus, le fichier utile n'est pas téléchargé directement mais
extrait d'une archive ZIP. La résolution dynamique n'est donc pas une
préférence uniforme, c'est la stratégie qui survit à la façon dont chaque
source publie ses fichiers. L'arbitrage Parcoursup/Sirene est documenté dans
l'ADR 0005 ; celui du grain d'idempotence du RNCP dans l'ADR 0007.

### RNCP — pourquoi un fichier daté, pas un fichier unique écrasé

Le RNCP est un export quotidien : une nouvelle archive est publiée chaque
jour par France Compétences, avec un contenu qui évolue (nouvelles fiches,
fiches retirées, statuts qui changent). Appliquer au RNCP la même mécanique
que Sirene — un seul fichier écrasé à chaque republication — poserait un
problème que Sirene ne pose pas : une table dérivée construite un jour donné
à partir de l'export RNCP (la table NAF↔ROME↔formation, E18) doit rester
rejouable sans reprocher la source. Si le fichier RNCP est écrasé à la
publication suivante, l'export qui a servi à construire cette table n'existe
plus le lendemain.

Le connecteur conserve donc un fichier par date de publication
(`rncp_AAAA-MM-JJ.csv`), avec une entrée de manifeste par date.
L'idempotence ne porte pas sur « le contenu a-t-il changé », mais sur « ai-je
déjà l'export de ce jour » : une réexécution le même jour ne retélécharge
rien, une réexécution un autre jour crée un nouveau fichier sans toucher aux
précédents. Non traité à cette étape : l'accumulation dans le temps (~9 Mo
par jour) suppose une politique de rétention si cette tâche est programmée à
cadence quotidienne dans un DAG sur une longue durée — hors du périmètre de
l'ingestion, qui garantit la disponibilité de l'instantané, pas sa purge.
Détail complet et seuil de bascule : ADR 0007.

### RNCP — un second membre extrait de la même archive (E18)

L'archive quotidienne RNCP contient dix fichiers ; le connecteur, jusqu'à
E18, n'en extrayait qu'un seul, le CSV standard. Ce n'est pas une source
nouvelle, c'est une source déjà présente dans l'archive qu'on n'avait pas
ouverte : le second membre, `rncp_rome_AAAA-MM-JJ.csv`, relie chaque fiche
RNCP à un ou plusieurs codes ROME (`Numero_Fiche`, `Codes_Rome_Code`,
`Codes_Rome_Libelle`, 3 colonnes), et sert de maillon central à la
réconciliation NAF↔ROME↔formation (E18,
`03-pipeline/reconciliation-naf-rome.md`). Sans lui, aucune fiche RNCP ne
peut être reliée à un métier ROME.

Le second membre suit le même mécanisme d'idempotence que le premier, un
fichier par date de publication, jamais écrasé, puisque les deux sont
extraits de la même archive quotidienne. Mesuré sur l'export du 2026-08-30 :
`rncp_rome_2026-08-30.csv`, **4 353 036 octets**, Licence Ouverte v2.0,
même licence que le CSV standard de la même archive.

Extraire le second membre déclenche un nouveau téléchargement complet de
l'archive plutôt que de réutiliser en mémoire celle du premier : chaque
appel au connecteur reste indépendant, ce doublement de volume (~9,6 Mo) ne
justifie pas de complexifier l'appelant avec un cache partagé.

### France Travail — une source nouvelle, résolue par titre (E18)

Aucune table officielle ne relie directement un code NAF à un code ROME.
France Travail publie, sur data.gouv, une table de correspondance ROME/NAF
au sein du jeu de données ROME, résolue à l'exécution par sous-chaîne de
titre dans le catalogue (« Les tables de correspondance ROME / autres
référentiels - ROME/NAF »), jamais par une URL en dur : le nom du fichier
change à chaque édition du ROME (constaté :
`rome-arborescence-des-secteurs-naf-juin-2026.xlsx`, **112 896 octets**,
Licence Ouverte v2.0). C'est un cinquième cas de résolution d'URL : une
requête au catalogue comme Sirene et RNCP, mais par titre plutôt que par
nom de jeu ou par préfixe de ressource.

Le fichier est un classeur Excel (xlsx), seul format publié pour cette
table. Le contrat vérifié après téléchargement n'est donc pas un encodage
de texte, comme pour IDÉO et RNCP, mais la validité du conteneur ZIP
sous-jacent : un xlsx est un ZIP contenant au minimum `[Content_Types].xml`.

**Un mécanisme d'idempotence différent de celui du RNCP.** Le RNCP est
republié chaque jour, l'idempotence porte donc sur la date de publication.
La table France Travail n'a aucune cadence de republication connue :
l'idempotence porte ici sur l'empreinte SHA-256 du contenu, comme pour
IDÉO, un nom de fichier fixe en configuration, retéléchargé seulement si son
contenu a changé.

`_correspond_au_fichier` sélectionne, parmi les ressources du catalogue,
celle dont le titre porte exactement `Fichier {nom} -` : une correspondance
par sous-chaîne aurait fait correspondre `StockUniteLegale` au titre de
`StockUniteLegaleHistorique`, dont il n'est qu'un préfixe. Toute ambiguïté
(zéro ressource, ou plus d'une) lève une erreur explicite plutôt que de
choisir par défaut.

### Vocabulaire commun d'erreur : transitoire contre définitif

Les deux connecteurs distinguent deux natures d'échec, par un vocabulaire
partagé posé dans `_flux.py` (`ErreurTransitoire`, `ErreurDefinitive`) que
chaque connecteur combine par héritage multiple à sa propre classe de base :

| | Transitoire (à retenter) | Définitif (à alerter) |
|---|---|---|
| Sirene | `ErreurReseauSirene` — catalogue ou fichier injoignable | `ErreurCatalogueSirene` — catalogue mal formé, fichier renommé ou retiré, résolution ambiguë |
| Parcoursup | `ErreurReseauParcoursup` — coupure réseau, HTTP en échec | `ErreurConfigurationParcoursup` — millésime non déclaré en configuration |

Sans cette distinction, un DAG qui capturerait une seule classe d'erreur par
connecteur retenterait aveuglément un échec qu'aucun nombre de tentatives ne
peut résoudre. Avec elle, le futur DAG Airflow (E33) écrit une seule fois
`except ErreurTransitoire: retenter()` / `except ErreurDefinitive:
alerter()`, valable pour les deux connecteurs — le critère 3.4 (reprise sur
erreur) directement servi par ce choix, documenté dans l'ADR 0006.

### Taille annoncée contre taille réellement écrite

Le catalogue annonce une taille (`filesize`) pour chaque ressource, mais un
statut HTTP 200 ne garantit pas que le flux a été reçu en entier. Après
téléchargement, `_avertir_si_ecart_de_taille` compare la taille réellement
écrite à celle annoncée : au-delà d'un écart relatif de 5 %, un
avertissement est journalisé (`ECART_TAILLE_SIRENE`), jamais une exception,
`filesize` n'étant pas garanti par contrat. Une taille annoncée nulle ou
absente ne déclenche aucune comparaison.

Le manifeste Sirene enregistre en plus `date_publication_stock`, lue dans le
champ `last_modified` du catalogue : un stock Sirene grossit chaque mois, un
volume sans la date du stock auquel il se rapporte n'est pas reproductible.

### Résolution rejouée contre le catalogue réel, aujourd'hui

```bash
python -c "
from edumatch.ingestion.sirene import resoudre_ressources
for r in resoudre_ressources():
    print(r.fichier, r.date_publication, r.url)
"
```

Sortie réelle, le 2026-08-28 :

```
StockEtablissement            2026-08-01T07:46:40.670000+00:00  .../20260801-074451/stock-stocketablissement-parquet.parquet
StockEtablissementHistorique  2026-08-01T07:48:41.558000+00:00  .../20260801-074757/stock-stocketablissementhistorique-parquet.parquet
StockUniteLegale              2026-08-01T07:40:13.463000+00:00  .../20260801-073937/stock-stockunitelegale-parquet.parquet
StockUniteLegaleHistorique    2026-08-01T07:42:16.180000+00:00  .../20260801-074131/stock-stockunitelegalehistorique-parquet.parquet
```

Les 4 URL correspondent exactement à celles enregistrées dans
`data/raw/sirene/manifeste.json` lors du téléchargement effectif : le stock
n'a pas changé depuis.

### Volumétrie réelle des 4 fichiers, stock du 01/08/2026

| Fichier | Octets | Lignes | Colonnes |
|---|---:|---:|---:|
| `StockEtablissement` | 2 202 341 459 | **43 896 818** | 54 |
| `StockEtablissementHistorique` | 870 319 380 | 95 865 102 | 18 |
| `StockUniteLegale` | 705 090 270 | **29 922 486** | 35 |
| `StockUniteLegaleHistorique` | 855 957 649 | 71 355 318 | 28 |
| **Total 4 fichiers** | **4 633 708 758 (4,63 Go décimaux, 4,4 Gio)** | — | — |

Ces deux chiffres, 43 896 818 établissements et 29 922 486 unités légales,
corrigent l'ordre de grandeur « 36 millions / 25 millions » retenu jusqu'ici,
un chiffre jamais recalculé depuis sa première mesure. Détail dans
`01-donnees/sources.md`.

**Un débouché n'est pas une ligne du fichier.** Sur les 43 896 818
établissements, seuls **16 715 258 sont actifs (38,1 %)** et **2 436 624
sont actifs ET employeurs (5,6 %)** — c'est ce dernier sous-ensemble que
retiennent les filtres du projet (`donnees.sirene.filtres`). Mesuré par
lecture de 2 colonnes sur 54 en **35,4 secondes** :

```bash
python -c "
import time, pyarrow.parquet as pq, pyarrow.compute as pc
t0 = time.perf_counter()
table = pq.read_table('data/raw/sirene/StockEtablissement.parquet',
    columns=['etatAdministratifEtablissement','caractereEmployeurEtablissement'])
actifs_mask = pc.equal(table.column('etatAdministratifEtablissement'), 'A')
employeur_mask = pc.equal(table.column('caractereEmployeurEtablissement'), 'O')
print('actifs', pc.sum(pc.cast(actifs_mask, 'int64')).as_py())
print('actifs_employeurs', pc.sum(pc.cast(pc.and_(actifs_mask, employeur_mask), 'int64')).as_py())
print('duree_s', round(time.perf_counter()-t0, 1))
"
```

C'est cette lecture, pas le résultat filtré, qui dimensionne le traitement :
il faut parcourir les 43,9 M de lignes pour savoir lesquelles passent le
filtre, même principe que la projection colonnaire (9 colonnes utiles sur
54). 43,9 M de lignes lues et filtrées en 35 secondes sur un poste ordinaire
est ce qui permet de retenir un traitement Spark local plutôt qu'un service
managé pour ce job mensuel (ADR 0002) : le volume justifie un outil
distribué, pas une plateforme.

### Délai d'attente et journalisation de la progression

Le plus gros fichier configuré dépasse 2 Go en Parquet : le délai d'attente
réseau par défaut de `_flux.py` (120 s, taillé pour les CSV Parcoursup de
quelques dizaines de Mo) serait atteint avant la fin d'un transfert normal.
Le connecteur Sirene retient un délai propre à son volume réel (20 minutes).
`_flux.telecharger_en_flux` accepte un rappel de progression optionnel
(`sur_progression`), appelé au plus une fois toutes les 10 secondes quel que
soit le rythme des blocs reçus du réseau : sans lui (le cas de Parcoursup,
inchangé), aucun décompte n'est effectué.

### Le contrat d'encodage, vérifié à l'écriture

`verifier_encodage` (`_referentiels_communs.py`) contrôle, une fois le
fichier écrit, qu'il décode intégralement selon l'encodage déclaré en
configuration (`donnees.referentiels.*.encodage`, `utf-8` pour les deux
volets aujourd'hui). Le cas réel qui a motivé ce contrôle : la
documentation du 26/08 annonçait le RNCP en Latin-1 ; l'export réellement
téléchargé décode sans erreur en UTF-8 (`\xc3\xa9` = « é » en UTF-8). La
configuration a été corrigée en conséquence (voir `01-donnees/sources.md`).

Cette garantie est asymétrique, et le code le documente explicitement : elle
détecte un fichier réellement en Latin-1 déclaré UTF-8, mais pas l'inverse,
un fichier réellement en UTF-8 déclaré Latin-1 ne fait jamais échouer un
décodage, puisque Latin-1 associe un caractère à chacun des 256 octets
possibles. Un fichier lu avec le mauvais encodage dans ce sens se relit tel
quel, silencieusement corrompu (mojibake). Aucune des deux sources
configurées aujourd'hui ne déclare `latin-1` : le risque n'est pas actif,
mais il existerait dès qu'une configuration le ferait, d'où un test dédié
(`test_verifier_encodage_ne_detecte_pas_un_fichier_utf8_declare_a_tort_en_latin1`).

### Licences par source — pourquoi ça compte pour E18

Le manifeste (`data/external/referentiels/manifeste.json`) enregistre la
licence de chaque jeu, comme la configuration (`configs/base.yaml`,
`donnees.referentiels.*.licence`) : ONISEP (IDÉO) est sous ODbL
(`odc-odbl`), le RNCP sous Licence Ouverte v2.0, la même que Parcoursup et
Sirene. Ce ne sont pas des variantes équivalentes : l'ODbL impose
l'attribution et le partage à l'identique de toute base de données dérivée
redistribuée, une obligation que la Licence Ouverte n'impose pas.
Conséquence pour E18 : si `naf_rome_formation.csv` intègre des données IDÉO
(intitulés de formation ou de métier) et qu'il est publié tel quel, il doit
l'être sous ODbL, pas sous la licence par défaut du reste du dépôt. Repris
dans le registre des sources (`05-gouvernance/registre-sources.md`, à
construire en E40).

## Les deux garanties du connecteur

### Idempotence, par empreinte

Avant tout téléchargement, le connecteur compare le fichier déjà présent au
manifeste : si le fichier existe, n'est pas vide, et que son empreinte
SHA-256 correspond à celle enregistrée, le téléchargement est évité
(`ResultatTelechargement.telecharge = False`). Sans entrée de manifeste, le
fichier n'est jamais considéré intact sur la seule foi de sa présence : on
retélécharge par prudence plutôt que de faire confiance à un fichier dont la
provenance ne peut pas être prouvée.

Rejoué sur l'API réelle, configuration `prod` (8 millésimes), une fois les
fichiers déjà en place :

```bash
EDUMATCH_ENV=prod python -c "
from edumatch.ingestion.parcoursup import telecharger_tous
for r in telecharger_tous(forcer=False):
    print(r.millesime, r.telecharge)
"
```

Résultat : les 8 millésimes renvoient `telecharge=False`, sans requête de
téléchargement.

### Écriture atomique

Chaque fichier, CSV comme manifeste, est écrit sous un nom temporaire
(`.part`) puis renommé vers son nom définitif seulement une fois l'écriture
terminée avec succès (`os.replace`, atomique y compris sous Windows, où
`Path.rename` échoue si la cible existe déjà). Une interruption réseau ou
disque en cours de transfert laisse un `.part` orphelin, jamais un fichier
tronqué sous le nom que le reste de la chaîne croirait complet.

**Correctif d'encodage (E18)** : en mode texte, cette primitive n'imposait
pas l'encodage UTF-8 et laissait Python retenir celui de la plateforme
(`cp1252` par défaut sous Windows). Ce défaut ne fait pas échouer l'écriture
sous Windows (cp1252 sait encoder un accent), il produit des octets que la
relecture en UTF-8 (déclarée explicitement par `lire_manifeste`) ne sait pas
relire : le défaut est silencieux à l'écriture et ne se révèle qu'à la
lecture. Constaté sur un titre de ressource France Travail contenant un
accent (« référentiels »). Corrigé en imposant `utf-8` explicitement dès
qu'un mode sans `b` est demandé ; test de non-régression en place
(`test_ecriture_atomique_en_mode_texte_ecrit_en_utf8_meme_sans_lencoder_de_la_plateforme`).

## Le manifeste de traçabilité

`data/raw/parcoursup/manifeste.json` porte, pour chaque millésime :
identifiant, URL résolue, date de téléchargement, taille en octets,
empreinte SHA-256. `data/raw/sirene/manifeste.json` porte la même chose par
fichier stock, avec un champ supplémentaire propre à Sirene :
`date_publication_stock`. `data/external/referentiels/manifeste.json` fait
de même pour les référentiels : une entrée par jeu IDÉO (`ideo:{jeu}`), plus
une entrée par date de publication pour le RNCP (`rncp:{date}`), la licence
et le délimiteur de chaque source y figurent aussi, en plus de l'encodage et
de l'empreinte. Ni l'un ni l'autre n'est la source de l'intégrité, c'est
l'empreinte recalculée à chaque passage qui la garantit, mais ils évitent de
recalculer une empreinte sur un fichier déjà connu intact, et donnent la
traçabilité exigée par le critère 3.8.

**Manifeste corrompu** : un JSON illisible n'est jamais silencieusement
écrasé par la prochaine écriture. Il est déplacé vers un nom horodaté
(`manifeste.json.corrompu-{horodatage}`) et l'incident est journalisé au
niveau erreur ; le connecteur repart d'un manifeste vide, donc retélécharge
tout, plutôt que de bloquer la chaîne. Ce choix est documenté dans l'ADR
0004.

## Primitives partagées (`_flux.py`)

Les mécaniques communes à tout connecteur d'ingestion du projet — session
HTTP, téléchargement en flux par blocs (sans jamais charger un fichier entier
en mémoire), empreinte SHA-256, écriture atomique générique, lecture et
écriture du manifeste — sont regroupées dans `_flux.py`. Ce module ne
connaît aucune source précise. La résolution d'URL reste propre à chaque
connecteur, parce qu'elle varie réellement d'une source à l'autre : gabarit
fixe pour Parcoursup, requête au catalogue data.gouv pour Sirene. Le choix
d'extraire ces primitives avant l'écriture du deuxième connecteur est
documenté dans l'ADR 0004.

## La génération des échantillons de test — son rôle pour la CI

`echantillons.py` lit `data/raw/` et `data/external/`, déjà peuplés par les
trois connecteurs ci-dessus, et écrit `data/samples/` : 17 fichiers, 1,2 Mo,
sans jamais modifier ni supprimer une ligne des dossiers qu'il lit.
Contrairement aux trois connecteurs, il ne fait aucun accès réseau, sa seule
tâche est de réduire des fichiers déjà présents localement à un extrait
représentatif et versionnable.

Ce que ce module rend possible, et qu'aucun connecteur ne peut rendre
possible seul : faire tourner la suite de tests sur un poste, ou une
exécution de CI, qui n'a jamais téléchargé les 4,6 Go de Sirene ni les 82 Mo
de Parcoursup. Vérifié en le provoquant, `data/raw/` et `data/external/`
rendus absents, la suite tourne quand même (voir « Suite complète » plus
bas).

L'échantillonnage est systématique à pas fixe, sans graine aléatoire : un
fichier source inchangé produit toujours le même extrait, empreinte SHA-256
identique sur deux générations. Les 9 colonnes d'identité directe de
personne physique sont exclues des deux fichiers `StockUniteLegale*`, mais
cela ne suffit pas à rendre l'extrait anonyme, le régime juridique complet
est documenté dans `01-donnees/echantillons.md` et l'ADR 0008, pas repris
ici : cette page couvre la mécanique d'ingestion, pas la conformité RGPD du
résultat.

## Tests

`tests/unit/test_ingestion_flux.py` et `tests/unit/test_ingestion_parcoursup.py`
couvrent : le téléchargement en flux, l'écriture atomique, l'empreinte, la
lecture d'un manifeste absent ou corrompu, l'idempotence, et l'erreur levée
pour un millésime non configuré.

`tests/unit/test_ingestion_sirene.py` couvre en plus, sans aucun accès
réseau : la résolution d'une ressource par titre exact, le rejet d'un
catalogue mal formé, le rejet d'une ressource sans `url` ou sans
`last_modified` exploitable, et la même idempotence et écriture atomique
que Parcoursup.

`tests/unit/test_ingestion_sirene_erreurs.py` couvre le vocabulaire
transitoire/définitif et la vérification de la taille annoncée contre la
taille écrite. `test_ingestion_flux.py` et `test_ingestion_parcoursup.py`
couvrent la même distinction côté Parcoursup et côté primitives communes.

`tests/unit/test_ingestion_referentiels.py` couvre le volet IDÉO :
idempotence par empreinte, écriture atomique, jeu non configuré
(`ErreurConfigurationReferentiels`), échec réseau
(`ErreurReseauReferentiels`), et le contrôle d'encodage, y compris le test
qui met en évidence son asymétrie. `tests/unit/test_ingestion_referentiels_rncp.py`
couvre le volet RNCP, sans accès réseau : résolution de la ressource la plus
récente, rejet d'un catalogue mal formé, extraction du CSV standard depuis
l'archive ZIP, et l'idempotence par date de publication.

`tests/data/test_echantillons_conformite.py` couvre `data/samples/` : liste
blanche de colonnes par fichier Sirene, présence et non-vacuité de chaque
échantillon, couverture des 8 millésimes Parcoursup et de leur dérive de
schéma, poids total sous 10 Mo, mentions obligatoires du README de
`data/samples/`. `tests/unit/test_ingestion_echantillons.py` couvre le
module de génération lui-même.

Suite complète du dépôt, paquet non installé, sans variable d'environnement
positionnée à la main :

```bash
python -m pytest -q
```

→ **145 passed**. Rejoué avec `data/raw/` et `data/external/` rendus absents
(dossiers renommés) : même résultat, **145 passed** — c'est précisément ce
que E08 devait prouver.

## Ce qui reste à faire

- Contrôles qualité bloquants sur les fichiers ingérés (E14), le connecteur
  garantit l'intégrité du transfert, pas la conformité du contenu
- Politique de rétention pour les exports RNCP quotidiens accumulés (~9
  Mo/jour), assumée comme non traitée à l'étape E07, à reprendre si la
  tâche est programmée à cadence quotidienne dans le DAG (E33)
