# Ingestion — les connecteurs

**Dernière mise à jour** : 2026-08-28 · commit `144ee20`.

Cette page couvre le connecteur Parcoursup, seul opérationnel à ce jour, et les
primitives qu'il partage avec les connecteurs à venir (Sirene, référentiels).
Elle sert de preuve aux critères 3.2 (ELT entre sources hétérogènes) et 3.6
(idempotence des tâches) du Bloc 3.

## Ce qui existe

| Fichier | Rôle |
|---|---|
| `src/edumatch/ingestion/_flux.py` | Primitives communes à tout connecteur : session HTTP, téléchargement en flux, empreinte, écriture atomique, manifeste |
| `src/edumatch/ingestion/parcoursup.py` | Connecteur Parcoursup : résolution d'URL par gabarit, orchestration des 8 millésimes |

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
SHA-256. Il n'est pas la source de l'intégrité — c'est l'empreinte recalculée à
chaque passage qui la garantit — mais il évite de recalculer une empreinte sur
un fichier déjà connu intact, et donne la traçabilité exigée par le critère
3.8.

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

Suite complète du dépôt, paquet non installé, sans variable d'environnement
positionnée à la main :

```bash
python -m pytest -q
```

→ **44 passed**.

## Ce qui reste à faire

- Connecteur Sirene (E06) : résolution d'URL par requête au catalogue
  data.gouv, réutilisation des mêmes primitives de `_flux.py`
- Connecteur référentiels (E07) : ONISEP, RNCP, IDÉO
- Contrôles qualité bloquants sur les fichiers ingérés (E14) — le connecteur
  garantit l'intégrité du transfert, pas la conformité du contenu
