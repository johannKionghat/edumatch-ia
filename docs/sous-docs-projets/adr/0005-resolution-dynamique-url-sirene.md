# ADR 0005 — Résolution dynamique de l'URL Sirene, jamais une URL en configuration

**Date** : 2026-08-28 · **Statut** : accepté

## Contexte

Le connecteur Sirene (E06) doit télécharger 4 fichiers stock republiés
**chaque mois** par l'INSEE. Le stock du 01/08/2026, vérifié aujourd'hui,
porte cette URL pour `StockEtablissement` :

```
https://static.data.gouv.fr/resources/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/20260801-074451/stock-stocketablissement-parquet.parquet
```

L'horodatage `20260801-074451` fait partie du chemin, pas d'un paramètre de
requête : une URL codée en dur pour le stock d'un mois donné cesse de
fonctionner dès la publication du mois suivant. Le connecteur Parcoursup
(E05), à l'inverse, s'appuie sur un gabarit stable — un identifiant par
millésime, qui ne change plus une fois publié — écrit tel quel en
configuration (`configs/base.yaml`).

## Options envisagées

1. **URL en configuration, mise à jour manuelle chaque mois** — écartée :
   viole le critère 3.3 (automatisation complète, sans intervention
   manuelle) dès le deuxième mois d'exécution du pipeline. Une tâche
   mensuelle qui exige une modification de fichier de configuration n'est
   pas automatisée.
2. **Résolution dynamique par interrogation du catalogue data.gouv à chaque
   exécution** — retenue. Seuls le nom du jeu de données et le gabarit de
   l'API du catalogue (`https://www.data.gouv.fr/api/1/datasets/{jeu}/`),
   stables dans le temps, sont en configuration.
3. **Scraper la page HTML du jeu de données** — écartée : l'API JSON du
   catalogue existe et est documentée ; scraper du HTML serait plus fragile
   pour un gain nul.

## Décision

Option 2. `resoudre_ressources()` fait un appel JSON léger (le descriptif du
jeu de données, pas un fichier de données) et sélectionne, pour chaque fichier
configuré, la ressource au format Parquet dont le titre correspond
exactement (`Fichier {nom} -`, pas une correspondance par sous-chaîne — deux
des quatre noms configurés sont des préfixes d'un autre). Toute ambiguïté ou
absence de correspondance lève une erreur explicite plutôt que de choisir par
défaut.

## Conséquences

- **Une dépendance de plus au moment de l'exécution** : le catalogue data.gouv
  doit être joignable pour que la résolution aboutisse. Un fichier de
  configuration n'a pas cette dépendance — il fonctionne hors ligne. Le DAG
  Airflow (E33) doit donc traiter l'indisponibilité du catalogue comme une
  panne transitoire (retry), pas comme une erreur de configuration.
- **Robustesse au renommage plutôt qu'à la disparition silencieuse** : si
  l'INSEE renomme un fichier ou change le format de titre des ressources, le
  connecteur s'arrête avec un message explicite au lieu de télécharger la
  mauvaise ressource ou aucune.
- **Traçabilité renforcée, pas dégradée** : la date de publication du stock
  (`last_modified`) est lue depuis le catalogue et enregistrée au manifeste
  sous `date_publication_stock` — une garantie qu'une URL statique en
  configuration n'aurait pas fournie sans un champ supplémentaire à tenir à
  jour manuellement, au même risque d'oubli que l'URL elle-même.
- **Vérifié aujourd'hui** : `resoudre_ressources()` rejoué contre le catalogue
  réel reproduit exactement les 4 URL enregistrées dans
  `data/raw/sirene/manifeste.json` lors du téléchargement effectif.

**Ce qui ferait reconsidérer** : si l'API du catalogue data.gouv devenait
elle-même instable ou dépréciée, ou si le format de titre des ressources
changeait de façon récurrente au point de multiplier les échecs de
résolution — auquel cas la correspondance par titre serait à remplacer par un
identifiant de ressource plus stable, si l'API en expose un, plutôt que
d'abandonner la résolution dynamique elle-même.
