"""Contrôles qualité des données (E14) : schéma, complétude, cohérence, fraîcheur.

Point d'entrée : `python -m edumatch.quality.run` (cible `make quality`).
Organisé par source, conformément au plan d'exécution du projet :
`parcoursup.py`, `sirene.py`, `referentiels.py`, orchestrés par `run.py`. Le
vocabulaire commun (anomalie, gravité, rapport, erreur de blocage) vit dans
`_diagnostic.py` ; le contrôle générique de fraîcheur, dans `_fraicheur.py`.

## L'arbitrage d'outillage : Pandera plutôt que Great Expectations

La structure du projet évoquait les deux au moment d'aborder cette étape.
Les deux sont de vrais outils de contrat de données ; la question n'est pas
laquelle « est la meilleure », mais laquelle correspond au volume et à la
forme réels des données de ce projet.

**Ce qui a été mesuré avant de trancher**, avec `pip install --dry-run` sur
le même environnement que ce dépôt :

| | Great Expectations | Pandera |
|---|---|---|
| Poids du paquet | 5,7 Mo (wheel) | 447 Ko (wheel) |
| Dépendances nouvelles | 9 directes (`altair`, `cryptography`, `jsonschema`, `marshmallow`, `ruamel.yaml`, `scipy`, `mistune`, `tqdm`, `tzlocal`), dont plusieurs à compilation native (`cffi`/`cryptography`) | 1 (`typeguard`) — le reste (`pandas`, `numpy`, `pydantic`) est déjà une dépendance du projet |
| Mécanique minimale pour un contrôle qui bloque | Un magasin de contexte (`DataContext`), une suite d'attentes persistée, un point de contrôle (*checkpoint*), une action qui échoue le job | Un objet `DataFrameSchema`, `.validate(df, lazy=True)`, une exception `SchemaErrors` |
| Adapté à | Un ou plusieurs entrepôts, suivis dans la durée, avec documentation HTML générée à chaque exécution | Un DataFrame en mémoire, contrôlé au moment où on le construit |

**Le volume réel de ce projet** ne correspond pas au terrain de Great
Expectations : Parcoursup tient dans **82 Mo pour huit fichiers** (14 252
lignes au plus par millésime), les référentiels dans quelques dizaines de
milliers de lignes. Même Sirene, à 43,9 millions de lignes, n'est jamais
chargé en mémoire par ce module : il est lu par lots projetés sur 9 colonnes
(`quality/sirene.py`), et validé avec des compteurs `pandas` accumulés lot
par lot — un DataFrame Pandera couvrirait un lot, pas le fichier entier, et
l'accumulation devrait de toute façon être écrite à la main. Aucun des trois
contrôles de ce module n'a donc besoin d'un magasin de contexte persistant,
de checkpoints ou d'une documentation HTML régénérée à chaque exécution :
c'est explicitement la remarque déjà faite sur ce projet à propos de Spark
sur 120 Mo (retour Jedha, dossier ShopBR) — un outillage dimensionné pour un
volume qu'on n'a pas est une régression, pas une qualité.

**Ce qui ferait changer d'avis** : l'apparition d'un entrepôt partagé entre
plusieurs équipes, suivi dans la durée, où la documentation générée
automatiquement (`great_expectations docs build`) et l'historique des
validations deviendraient eux-mêmes un livrable attendu — pas seulement un
contrôle exécuté une fois par lancement de pipeline. Ce n'est pas la
situation actuelle : un seul candidat, un entrepôt en étoile qui tient sur un
poste de travail, une exécution avant chaque transformation dbt.

**Le coût réel du choix inverse** aurait été : ~9 dépendances
supplémentaires pour valider un fichier de 82 Mo, une mécanique de contexte
et de checkpoint à apprendre et maintenir pour un projet qui n'a besoin que
de « ce schéma est-il respecté, oui ou non », et une alternative déjà
sanctionnée dans ce projet pour son manque de proportionnalité.

Pandera n'est retenu que pour `parcoursup.py` (un DataFrame par millésime,
14 252 lignes au plus) : `sirene.py` et `referentiels.py` s'appuient sur des
compteurs et des vérifications écrits à la main, sans dépendance
supplémentaire, pour les raisons détaillées dans leurs docstrings respectifs
— le hasard d'un choix d'outil n'a pas à s'appliquer uniformément là où la
forme du problème diffère (un flux projeté par lots contre un DataFrame
unique en mémoire).
"""
