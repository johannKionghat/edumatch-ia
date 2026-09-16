# ADR 0014 — Pandera plutôt que Great Expectations pour les contrôles qualité

Statut : accepté (2026-08-29)

## Contexte

E14 exige des contrôles qualité bloquants sur trois sources — Parcoursup,
Sirene, référentiels. La structure du projet évoquait Great Expectations
comme piste, mais j'ai mesuré le coût réel de chaque option contre le volume
réel des données : Parcoursup tient dans 82 Mo pour huit fichiers (14 252
lignes au plus par millésime), les référentiels dans quelques dizaines de
milliers de lignes, et même Sirene (43,9 millions de lignes, 2,2 Go) n'a
jamais besoin d'être chargé en mémoire — il est lu par lots projetés sur 9
colonnes. Mesuré avec `pip install --dry-run` sur l'environnement du
dépôt : Great Expectations pèse 5,7 Mo et ajoute 9 dépendances directes
(`altair`, `cryptography`, `jsonschema`...) ; Pandera pèse 447 Ko et
n'ajoute qu'une dépendance (`typeguard`), le reste (`pandas`, `numpy`,
`pydantic`) étant déjà présent.

## Décision

Pandera pour `parcoursup.py` (un DataFrame par millésime,
`.validate(df, lazy=True)`). Compteurs et vérifications `pandas` écrits à la
main pour `sirene.py` (flux par lots) et `referentiels.py`, sans dépendance
supplémentaire, pour un coût de développement équivalent à ce qu'un
DataFrame Pandera aurait de toute façon exigé d'accumulation manuelle.

## Alternatives écartées

- Great Expectations : pertinent pour un entrepôt partagé entre plusieurs
  équipes, suivi dans la durée. Ici, neuf dépendances nouvelles, dont
  plusieurs à compilation native, pour valider un fichier de 82 Mo et un
  flux Sirene qui n'est de toute façon jamais un DataFrame unique.
- Pandera pour Sirene aussi : un schéma Pandera couvrirait un lot et non le
  fichier entier, et les compteurs de complétude devraient de toute façon
  être accumulés à la main.

## Conséquences

Ce qu'on accepte de perdre : pas de documentation HTML générée
automatiquement, pas d'historique de validations persisté comme livrable en
soi, pas de magasin de contextes partageable entre plusieurs projets. Aucun
de ces éléments n'est exigé par le critère 3.5 du bloc 3, qui porte sur la
détection, la validation et le blocage — pas sur la traçabilité inter-équipes
de l'historique des contrôles.

Je reviendrais sur ce choix si un entrepôt partagé entre plusieurs équipes
apparaissait, suivi dans la durée, où la documentation générée et
l'historique des validations deviendraient eux-mêmes un livrable attendu.
