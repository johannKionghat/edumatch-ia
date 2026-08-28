# ADR 0006 — Vocabulaire commun d'erreur : transitoire contre définitif

**Date** : 2026-08-28 · **Statut** : accepté

## Contexte

Le DAG Airflow (E33) devra décider, à chaque échec d'un connecteur, s'il
retente la tâche ou s'il alerte un humain. Jusqu'ici, chaque connecteur ne
levait qu'une seule classe d'erreur (`ErreurTelechargementParcoursup`,
`ErreurTelechargementSirene`), qui ne distinguait pas une coupure réseau
(retentable) d'un millésime absent de la configuration ou d'un catalogue qui a
changé de contrat (non retentable, une intervention humaine est nécessaire).
Un orchestrateur qui capturerait cette classe unique retenterait aveuglément
des échecs qu'aucun nombre de tentatives ne résoudrait.

## Options envisagées

1. **Laisser chaque connecteur définir sa propre distinction**, sans
   vocabulaire partagé — écartée : le DAG devrait alors connaître les classes
   internes de chaque connecteur pour décider quoi faire, ce qui recrée un
   couplage que `_flux.py` a justement été créé pour éviter (ADR 0004).
2. **Deux mixins communs, `ErreurTransitoire` et `ErreurDefinitive`, posés
   dans `_flux.py` et combinés par héritage multiple à la classe de base de
   chaque connecteur** — retenue.
3. **Un code d'erreur numérique ou une chaîne de statut**, à la place de
   classes — écartée : perd le typage, oblige à comparer des chaînes plutôt
   qu'à utiliser `except`, et n'apporte rien que Python n'offre déjà par
   l'héritage.

## Décision

Option 2. `ErreurReseauParcoursup(ErreurTelechargementParcoursup,
ErreurTransitoire)` et `ErreurReseauSirene(ErreurTelechargementSirene,
ErreurTransitoire)` sur les échecs réseau ; `ErreurConfigurationParcoursup` et
`ErreurCatalogueSirene`, tous deux `ErreurDefinitive`, sur les échecs qui
tiennent au contrat de la source (millésime non configuré, catalogue mal
formé, ressource introuvable ou ambiguë). La classe de base de chaque
connecteur (`ErreurTelechargementX`) reste levée en pratique via l'une des
deux sous-classes : un appelant qui ne distingue pas encore les deux natures
continue de fonctionner sans changement (`except ErreurTelechargementX`
capture toujours tout).

## Conséquences

- **Le futur DAG peut écrire `except ErreurTransitoire: retenter()` /
  `except ErreurDefinitive: alerter()` une seule fois**, valable pour les deux
  connecteurs actuels et tout connecteur à venir (référentiels, E07), sans
  connaître leurs classes internes.
- **Un connecteur qui oublierait de distinguer** retomberait sur la classe de
  base, ni transitoire ni définitive : à surveiller en E07 et en revue de
  code, pas garanti par le typage seul.
- Testé pour les deux connecteurs existants : coupure réseau et échec HTTP
  lèvent `ErreurTransitoire`, configuration absente ou catalogue non conforme
  lèvent `ErreurDefinitive`, jamais les deux à la fois
  (`test_erreur_transitoire_et_definitive_sont_des_exceptions_disjointes`).

**Ce qui ferait reconsidérer** : si une nature d'échec s'avérait mal classée
à l'usage réel du DAG (un 5xx qui ne se résorbe jamais, une absence de
configuration qu'un simple redéploiement corrigerait) — auquel cas c'est le
classement d'une erreur précise qu'il faudrait revoir, pas la distinction
elle-même.
