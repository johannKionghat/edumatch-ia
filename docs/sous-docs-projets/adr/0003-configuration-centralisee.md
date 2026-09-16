# ADR 0003 — Configuration centralisée : Pydantic Settings, précédence à trois couches

Statut : accepté (2026-08-28)

## Contexte

Aucun chemin ni seuil ne doit être en dur dans le code : la configuration
métier vient de `configs/*.yaml`, les secrets de l'environnement. Trois
environnements partagent une base commune, et le code tourne à des endroits
différents selon le moment (poste de développement, Scaleway, conteneur,
CI) : la racine des données ne peut pas être un chemin unique écrit en dur.

## Décision

Pydantic Settings, avec trois arbitrages : précédence à trois couches
(`base.yaml` < `{env}.yaml` via `herite_de: base.yaml` < variable
d'environnement, réservée aux secrets et aux réglages sans redéploiement) ;
héritage limité à un niveau, pour rester auditable d'un coup d'œil ;
`EDUMATCH_DATA_ROOT` pilotable, avec `<dépôt>/data` par défaut mais une
valeur vide, blanche ou relative refusée explicitement (sinon `Path("")` se
résout en `.`, un emplacement non maîtrisé selon le point de lancement).

## Alternatives écartées

- YAML brut, sans validation : une clé mal orthographiée n'est détectée qu'à
  l'usage, parfois en cours d'entraînement.
- Hydra : composition multi-fichiers et interpolation, un outil de plus pour
  un besoin couvert ici par une fusion à un seul niveau.

## Conséquences

Une configuration invalide échoue au démarrage, champ fautif nommé.
`load_settings()` traduit toute erreur de validation en erreur de
configuration explicite, quelle que soit la source. Ajouter un environnement
ou un paramètre demande une modification du schéma Pydantic : c'est le
contrat entre la configuration et le code qui la consomme, pas une simple
recopie du YAML.

Je reviendrais sur ce choix si un besoin réel de composition multi-fichiers
ou d'interpolation entre clés apparaissait, ou si la configuration devait se
recharger sans redémarrage.
