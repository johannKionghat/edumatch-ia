# ADR 0006 — Vocabulaire commun d'erreur : transitoire contre définitif

Statut : accepté (2026-08-28)

## Contexte

Le futur DAG Airflow (E33) devra décider, à chaque échec d'un connecteur,
s'il retente la tâche ou alerte un humain. Jusqu'ici chaque connecteur ne
levait qu'une seule classe d'erreur, qui ne distinguait pas une coupure
réseau (retentable) d'un millésime absent ou d'un catalogue qui a changé de
contrat (non retentable, intervention humaine nécessaire). Un orchestrateur
qui capturerait cette classe unique retenterait aveuglément des échecs
qu'aucune tentative ne résoudrait.

## Décision

Deux mixins communs, `ErreurTransitoire` et `ErreurDefinitive`, posés dans
`_flux.py` et combinés par héritage multiple à la classe de base de chaque
connecteur. `ErreurReseauParcoursup` et `ErreurReseauSirene` héritent
d'`ErreurTransitoire` ; `ErreurConfigurationParcoursup` et
`ErreurCatalogueSirene` héritent d'`ErreurDefinitive`. La classe de base de
chaque connecteur reste levée en pratique via l'une des deux sous-classes,
donc un appelant qui ne distingue pas encore les deux continue de fonctionner
sans changement.

## Alternatives écartées

- Laisser chaque connecteur définir sa propre distinction, sans vocabulaire
  partagé : le DAG devrait connaître les classes internes de chaque
  connecteur, recréant le couplage que `_flux.py` a justement été créé pour
  éviter.
- Un code d'erreur numérique ou une chaîne de statut : perd le typage,
  oblige à comparer des chaînes plutôt qu'à utiliser `except`.

## Conséquences

Le futur DAG peut écrire `except ErreurTransitoire: retenter()` /
`except ErreurDefinitive: alerter()` une seule fois, valable pour les deux
connecteurs actuels et tout connecteur à venir. Un connecteur qui oublierait
de distinguer retomberait sur la classe de base : à surveiller en E07 et en
revue de code, pas garanti par le typage seul. Testé pour les deux
connecteurs existants : coupure réseau et échec HTTP lèvent
`ErreurTransitoire`, configuration absente ou catalogue non conforme lèvent
`ErreurDefinitive`, jamais les deux à la fois.

Je reviendrais sur ce classement si une nature d'échec s'avérait mal classée
à l'usage réel du DAG (un 5xx qui ne se résorbe jamais, une absence de
configuration qu'un simple redéploiement corrigerait) — ce serait alors le
classement d'une erreur précise à revoir, pas la distinction elle-même.
