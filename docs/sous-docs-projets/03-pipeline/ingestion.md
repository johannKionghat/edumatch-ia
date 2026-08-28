# Ingestion — les connecteurs

**Dernière mise à jour** : 2026-08-28 (E06).

Cette page couvre les deux connecteurs opérationnels à ce jour — Parcoursup et
Sirene — et les primitives qu'ils partagent avec le connecteur à venir
(référentiels). Elle sert de preuve aux critères 3.2 (ELT entre sources
hétérogènes) et 3.6 (idempotence des tâches) du Bloc 3 : deux sources, deux
stratégies de résolution d'URL, chacune justifiée par la façon dont la source
publie ses fichiers.

## Ce qui existe

| Fichier | Rôle |
|---|---|
| `src/edumatch/ingestion/_flux.py` | Primitives communes à tout connecteur : session HTTP, téléchargement en flux, empreinte, écriture atomique, manifeste |
| `src/edumatch/ingestion/parcoursup.py` | Connecteur Parcoursup : résolution d'URL par gabarit, orchestration des 8 millésimes |
| `src/edumatch/ingestion/sirene.py` | Connecteur Sirene : résolution d'URL par interrogation du catalogue data.gouv, orchestration des 4 fichiers stock |

## Le connecteur Parcoursup

`telecharger_millesime(millesime, settings, session, forcer)` télécharge
l'export CSV d'un millésime déclaré dans `configs/base.yaml`
(`donnees.parcoursup.millesimes` et `.identifiants`) vers
`data/raw/parcoursup/parcoursup_{millesime}.csv`. `telecharger_tous()` répète
l'opération pour tous les millésimes configurés, sur une session HTTP unique.

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

**Poids sur disque des 8 CSV : 82 Mo** (`du -sh data/raw/parcoursup/`, mesuré
le 2026-08-28). Ce chiffre corrige l'estimation « ~100 Mo » retenue jusqu'ici
dans le dossier et mes notes de cadrage — un ordre de grandeur jamais mesuré
faute de fichier réellement téléchargé, l'export de l'API n'annonçant pas sa
taille (`Content-Length` absent, transfert « chunked »). Le détail de la
correction est dans `01-donnees/sources.md` et `avancement.md`.

**Dérive de schéma entre millésimes** : 85 colonnes en 2018, 92 en 2019, 115 en
2020, stable à 118 à partir de 2021. Ce n'est pas une anomalie : le MESR a
ajouté des champs au fil des sessions (détail des mentions, néo-bacheliers,
académie d'origine). C'est la matière de la réconciliation de schéma prévue en
E15 (dbt bronze → silver).

## Le connecteur Sirene

`resoudre_ressources(settings, session)` interroge le catalogue data.gouv du
jeu `base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret`
(`donnees.sirene.url_catalogue_gabarit`, un seul appel JSON léger, aucun
fichier de données transféré) et en extrait l'URL Parquet courante des 4
fichiers configurés (`donnees.sirene.fichiers`). `telecharger_fichier` prend
ensuite le relais avec les mêmes garanties que Parcoursup — idempotence par
empreinte, écriture atomique, manifeste. `telecharger_tous()` enchaîne les deux
sur une session HTTP unique.

### Deux sources, deux stratégies de résolution d'URL — pourquoi

| | Parcoursup | Sirene |
|---|---|---|
| Forme de l'URL | Gabarit fixe + identifiant du millésime | Résolue à l'exécution par requête au catalogue |
| Ce qui varie | Un identifiant par millésime, stable une fois publié | L'URL entière, republiée chaque mois |
| Stockage en configuration | Le gabarit et les 8 identifiants (`configs/base.yaml`) | Le nom du jeu de données et le gabarit de **l'API du catalogue**, jamais une URL de fichier |
| Coût de la stratégie | Aucun appel réseau supplémentaire avant le téléchargement | Un appel de résolution avant chaque exécution ; échoue si le catalogue est indisponible ou a renommé une ressource |

Parcoursup republie un export par session sous un identifiant qui, une fois
connu, ne change plus — un gabarit d'URL en configuration reste vrai d'une
exécution à l'autre. Sirene republie un stock complet chaque mois, sous un
chemin qui contient l'horodatage de publication
(`.../20260801-074451/stock-stocketablissement-parquet.parquet` pour le stock
du jour) : coder ce chemin en dur casserait le connecteur dès le mois suivant.
La résolution dynamique n'est donc pas une préférence de conception, elle est
la seule stratégie qui survit à la façon dont l'INSEE publie ses données.
L'arbitrage entre les deux approches, avec son coût et son seuil de bascule,
est documenté dans l'ADR 0005.

`_correspond_au_fichier` sélectionne, parmi les ressources du catalogue,
celle dont le titre porte exactement `Fichier {nom} -` : une correspondance
par sous-chaîne aurait fait correspondre `StockUniteLegale` au titre de
`StockUniteLegaleHistorique`, dont il n'est qu'un préfixe. Toute ambiguïté
(zéro ressource, ou plus d'une) lève une erreur explicite plutôt que de
choisir par défaut : un catalogue qui a renommé ou retiré un fichier doit
arrêter la chaîne, pas continuer sur une hypothèse.

### Vocabulaire commun d'erreur : transitoire contre définitif

Les deux connecteurs distinguent désormais deux natures d'échec, par un
vocabulaire partagé posé dans `_flux.py` (`ErreurTransitoire`,
`ErreurDefinitive`) que chaque connecteur combine par héritage multiple à sa
propre classe de base :

| | Transitoire (à retenter) | Définitif (à alerter) |
|---|---|---|
| Sirene | `ErreurReseauSirene` — catalogue ou fichier injoignable | `ErreurCatalogueSirene` — catalogue mal formé, fichier renommé ou retiré, résolution ambiguë |
| Parcoursup | `ErreurReseauParcoursup` — coupure réseau, HTTP en échec | `ErreurConfigurationParcoursup` — millésime non déclaré en configuration |

Sans cette distinction, un DAG qui capturerait une seule classe d'erreur par
connecteur retenterait aveuglément un échec qu'aucun nombre de tentatives ne
peut résoudre (catalogue qui a changé de contrat, millésime jamais configuré).
Avec elle, le futur DAG Airflow (E33) écrit une seule fois `except
ErreurTransitoire: retenter()` / `except ErreurDefinitive: alerter()`, valable
pour les deux connecteurs sans connaître leurs classes internes — c'est le
critère 3.4 (reprise sur erreur) directement servi par ce choix, documenté
dans l'ADR 0006.

### Taille annoncée contre taille réellement écrite

Le catalogue annonce une taille (`filesize`) pour chaque ressource, mais un
statut HTTP 200 ne garantit pas que le flux a été reçu en entier. Après
téléchargement, `_avertir_si_ecart_de_taille` compare la taille réellement
écrite à celle annoncée : au-delà d'un écart relatif de 5 %, un avertissement
est journalisé (`ECART_TAILLE_SIRENE`), jamais une exception — `filesize`
n'est pas garanti par contrat, en faire une condition bloquante romprait la
chaîne pour une cause qui n'est pas nécessairement la nôtre. Une taille
annoncée nulle ou absente (ressource tout juste publiée) ne déclenche aucune
comparaison.

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
n'a pas changé depuis, la résolution est stable dans la même fenêtre
mensuelle.

### Volumétrie réelle des 4 fichiers, stock du 01/08/2026

| Fichier | Octets | Lignes | Colonnes |
|---|---:|---:|---:|
| `StockEtablissement` | 2 202 341 459 | **43 896 818** | 54 |
| `StockEtablissementHistorique` | 870 319 380 | 95 865 102 | 18 |
| `StockUniteLegale` | 705 090 270 | **29 922 486** | 35 |
| `StockUniteLegaleHistorique` | 855 957 649 | 71 355 318 | 28 |
| **Total 4 fichiers** | **4 633 708 758 (4,63 Go décimaux, 4,4 Gio)** | — | — |

Ces deux chiffres — 43 896 818 établissements, 29 922 486 unités légales —
corrigent l'ordre de grandeur « 36 millions / 25 millions » retenu jusqu'ici
dans le dossier et mes notes de cadrage : un chiffre jamais recalculé depuis
sa première mesure. Détail complet et commande dans `01-donnees/sources.md`.

**Un débouché n'est pas une ligne du fichier.** Sur les 43 896 818
établissements, seuls **16 715 258 sont actifs (38,1 %)** et **2 436 624 sont
actifs ET employeurs (5,6 %)** — c'est ce dernier sous-ensemble que retiennent
les filtres du projet (`donnees.sirene.filtres`). Mesuré par lecture de 2
colonnes sur 54 en **35,4 secondes** :

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
filtre. C'est le même principe que la projection colonnaire (9 colonnes
utiles sur 54, jamais 54) — on réduit tôt, mais seulement après avoir lu.
43,9 M de lignes lues et filtrées en 35 secondes sur un poste ordinaire est
précisément ce qui permet de retenir un traitement Spark **local** plutôt
qu'un service managé pour ce job mensuel (ADR 0002) : le volume justifie un
outil distribué, pas une plateforme.

### Délai d'attente et journalisation de la progression

Le plus gros fichier configuré dépasse 2 Go en Parquet : le délai d'attente
réseau par défaut de `_flux.py` (120 s, taillé pour les CSV Parcoursup de
quelques dizaines de Mo) serait atteint avant la fin d'un transfert normal.
Le connecteur Sirene retient un délai propre à son volume réel (20 minutes).
`_flux.telecharger_en_flux` accepte désormais un rappel de progression optionnel
(`sur_progression`), appelé au plus une fois toutes les 10 secondes quel que
soit le rythme des blocs reçus du réseau : sans lui — le cas de Parcoursup,
inchangé — aucun décompte n'est effectué. Sans ce rappel, un téléchargement de
plusieurs minutes ne laisse aucune trace dans les journaux avant la fin, ce
qu'un opérateur ne peut pas distinguer d'un blocage.

## Les deux garanties du connecteur

### Idempotence, par empreinte

Avant tout téléchargement, le connecteur compare le fichier déjà présent au
manifeste : si le fichier existe, n'est pas vide, et que son empreinte SHA-256
correspond à celle enregistrée, le téléchargement est évité
(`ResultatTelechargement.telecharge = False`). Sans entrée de manifeste — cache
absent ou premier passage — le fichier n'est jamais considéré intact sur la
seule foi de sa présence : on retélécharge par prudence plutôt que de faire
confiance à un fichier dont la provenance ne peut pas être prouvée.

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

Chaque fichier — CSV comme manifeste — est écrit sous un nom temporaire
(`.part`) puis renommé vers son nom définitif seulement une fois l'écriture
terminée avec succès (`os.replace`, atomique y compris sous Windows, où
`Path.rename` échoue si la cible existe déjà). Une interruption réseau ou
disque en cours de transfert laisse un `.part` orphelin, jamais un fichier
tronqué sous le nom que le reste de la chaîne croirait complet — c'est ce qui
protège l'immuabilité de `data/raw/`.

## Le manifeste de traçabilité

`data/raw/parcoursup/manifeste.json` porte, pour chaque millésime :
identifiant, URL résolue, date de téléchargement, taille en octets, empreinte
SHA-256. `data/raw/sirene/manifeste.json` porte la même chose par fichier
stock, avec un champ supplémentaire propre à Sirene :
`date_publication_stock`, la date de publication du stock rendue par le
catalogue (`last_modified`) — nécessaire parce qu'un stock Sirene grossit
chaque mois, contrairement à un millésime Parcoursup qui, une fois publié, ne
change plus. Ni l'un ni l'autre n'est la source de l'intégrité — c'est
l'empreinte recalculée à chaque passage qui la garantit — mais ils évitent de
recalculer une empreinte sur un fichier déjà connu intact, et donnent la
traçabilité exigée par le critère 3.8.

**Manifeste corrompu** : un JSON illisible n'est jamais silencieusement écrasé
par la prochaine écriture. Il est déplacé vers un nom horodaté
(`manifeste.json.corrompu-{horodatage}`) et l'incident est journalisé au niveau
erreur ; le connecteur repart d'un manifeste vide, donc retélécharge tout,
plutôt que de bloquer la chaîne. Le choix d'une quarantaine plutôt que d'un
écrasement silencieux est documenté dans l'ADR 0004.

## Primitives partagées (`_flux.py`)

Les mécaniques communes à tout connecteur d'ingestion du projet — session
HTTP, téléchargement en flux par blocs (sans jamais charger un fichier entier
en mémoire), empreinte SHA-256, écriture atomique générique, lecture et
écriture du manifeste — sont regroupées dans `_flux.py`. Ce module ne connaît
aucune source précise : ni URL, ni identifiant de jeu de données. La
résolution d'URL reste propre à chaque connecteur, parce qu'elle varie
réellement d'une source à l'autre : gabarit fixe pour Parcoursup, requête au
catalogue data.gouv pour Sirene (les liens changent chaque mois). Le choix
d'extraire ces primitives avant l'écriture du deuxième connecteur, plutôt
qu'après une première duplication, est documenté dans l'ADR 0004.

## Tests

`tests/unit/test_ingestion_flux.py` et `tests/unit/test_ingestion_parcoursup.py`
couvrent : le téléchargement en flux, l'écriture atomique (fichier `.part`
absent après succès, absent après échec), l'empreinte, la lecture d'un
manifeste absent ou corrompu, l'idempotence, et l'erreur levée pour un
millésime non configuré.

`tests/unit/test_ingestion_sirene.py` couvre en plus, sans aucun accès réseau
(session HTTP remplacée par une session factice) : la résolution d'une
ressource par titre exact (pas par sous-chaîne, pour éviter qu'un nom de
fichier serve de préfixe à un autre), le rejet d'un catalogue mal formé
(racine non-objet, `resources` absent ou non-liste, ressource non-objet), le
rejet d'une ressource sans `url` ou sans `last_modified` exploitable, et la
même idempotence et écriture atomique que Parcoursup.

`tests/unit/test_ingestion_sirene_erreurs.py`, séparé du précédent pour isoler
le sujet, couvre le vocabulaire transitoire/définitif (catalogue injoignable,
coupure réseau en cours de transfert, catalogue mal formé, fichier absent du
catalogue) et la vérification de la taille annoncée contre la taille écrite
(écart journalisé, taille conforme silencieuse, taille annoncée nulle
silencieuse). `test_ingestion_flux.py` et `test_ingestion_parcoursup.py`
couvrent la même distinction transitoire/définitif côté Parcoursup et côté
primitives communes.

Suite complète du dépôt, paquet non installé, sans variable d'environnement
positionnée à la main :

```bash
python -m pytest -q
```

→ **80 passed**.

## Ce qui reste à faire

- Connecteur référentiels (E07) : ONISEP, RNCP, IDÉO
- Contrôles qualité bloquants sur les fichiers ingérés (E14) — le connecteur
  garantit l'intégrité du transfert, pas la conformité du contenu
