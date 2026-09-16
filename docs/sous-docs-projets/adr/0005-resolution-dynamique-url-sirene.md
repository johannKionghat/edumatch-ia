# ADR 0005 — Résolution dynamique de l'URL Sirene, jamais une URL en configuration

Statut : accepté (2026-08-28)

## Contexte

Le connecteur Sirene (E06) doit télécharger 4 fichiers stock republiés chaque
mois par l'INSEE. Le stock du 01/08/2026 porte une URL dont l'horodatage
`20260801-074451` fait partie du chemin, pas d'un paramètre de requête : une
URL codée en dur pour un mois donné cesse de fonctionner dès la publication
du mois suivant. Le connecteur Parcoursup, à l'inverse, s'appuie sur un
gabarit stable écrit en configuration — un identifiant par millésime, qui ne
change plus une fois publié.

## Décision

`resoudre_ressources()` interroge le catalogue data.gouv à chaque exécution
(`https://www.data.gouv.fr/api/1/datasets/{jeu}/`) et sélectionne, pour
chaque fichier configuré, la ressource Parquet dont le titre correspond
exactement (`Fichier {nom} -`, pas une sous-chaîne : deux des quatre noms
configurés sont des préfixes d'un autre). Toute ambiguïté ou absence de
correspondance lève une erreur explicite plutôt que de choisir par défaut.

## Alternatives écartées

- URL en configuration, mise à jour manuelle chaque mois : viole le critère
  3.3 (automatisation complète) dès le deuxième mois d'exécution.
- Scraper la page HTML du jeu de données : l'API JSON du catalogue existe et
  est documentée, scraper du HTML serait plus fragile pour un gain nul.

## Conséquences

Une dépendance de plus au moment de l'exécution : le catalogue doit être
joignable, ce qu'un fichier de configuration statique n'exige pas. Le DAG
Airflow doit donc traiter son indisponibilité comme une panne transitoire
(retry), pas comme une erreur de configuration. En contrepartie, le
connecteur est robuste au renommage plutôt qu'à la disparition silencieuse :
si l'INSEE change le format de titre, il s'arrête avec un message explicite.
La date de publication du stock (`last_modified`) est enregistrée au
manifeste sous `date_publication_stock`, une traçabilité qu'une URL statique
n'aurait pas fournie sans champ supplémentaire à tenir à jour. Vérifié le
jour même : `resoudre_ressources()` rejoué contre le catalogue réel reproduit
exactement les 4 URL enregistrées lors du téléchargement effectif.

Je reviendrais sur ce choix si l'API du catalogue devenait elle-même instable
ou dépréciée, ou si le format de titre des ressources changeait trop
souvent — la correspondance par titre serait alors à remplacer par un
identifiant de ressource plus stable, si l'API en expose un.
