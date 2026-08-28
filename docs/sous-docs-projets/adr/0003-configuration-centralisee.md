# ADR 0003 — Configuration centralisée : Pydantic Settings, précédence à trois couches

**Date** : 2026-08-28 · **Statut** : accepté

## Contexte

Aucun chemin ni seuil ne doit être en dur dans le code (principe 3 de la structure du
dépôt) : la configuration métier vient de `configs/*.yaml`, les secrets viennent de
l'environnement. Trois environnements partagent une base commune. Le code tourne à des
endroits différents selon le moment (poste de développement, Scaleway, conteneur, CI) :
la racine des données ne peut pas être un chemin unique écrit en dur.

## Options envisagées

1. **YAML brut, sans validation** — une clé mal orthographiée n'est détectée qu'à
   l'usage, potentiellement en cours d'entraînement.
2. **Hydra** — composition multi-fichiers et interpolation, un outil de plus pour un
   besoin couvert ici par une fusion à un seul niveau.
3. **Pydantic Settings** — modèles typés, validation au démarrage, sources multiples
   (YAML, `.env`, variables d'environnement), déjà une dépendance du projet.

## Décision

Option 3, avec trois arbitrages : **précédence à trois couches** (`base.yaml` <
`{env}.yaml`, via `herite_de: base.yaml` < variable d'environnement, réservée aux
secrets et aux réglages sans nouveau déploiement) ; **héritage limité à un niveau**
(pas de chaîne `{env} → région → site`, une seule surcharge auditable d'un coup
d'œil) ; **`EDUMATCH_DATA_ROOT` justifiée par le déploiement**. `data/` fait partie
du dépôt, donc le défaut est `<dépôt>/data` ; la variable reste pilotable parce que
sur Scaleway les données ne vivront pas sous le dépôt, en conteneur ce sera un
volume monté, en CI un répertoire temporaire. Une valeur vide, blanche ou relative
est refusée explicitement : sans ce contrôle, `Path("")` se résout en `.`, un
emplacement non maîtrisé selon le point de lancement.

## Conséquences

- Une configuration invalide échoue au démarrage, champ fautif nommé.
- `load_settings()` traduit toute erreur de validation en erreur de configuration
  explicite, quelle que soit la source (YAML, `.env`, variable d'environnement).
- Ajouter un environnement ou un paramètre demande une modification du schéma
  Pydantic : le schéma est le contrat entre la configuration et le code qui la
  consomme, pas une simple recopie du YAML.

**Ce qui ferait reconsidérer** : un besoin réel de composition multi-fichiers ou
d'interpolation entre clés, qui justifierait Hydra ; ou une configuration devant se
recharger sans redémarrage, absent ici par choix.
