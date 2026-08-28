# ADR 0004 — Primitives d'ingestion mutualisées avant duplication, manifeste corrompu mis en quarantaine

**Date** : 2026-08-28 · **Statut** : accepté

## Contexte

Le connecteur Parcoursup (E05) est le premier des trois connecteurs
d'ingestion prévus (Parcoursup, Sirene, référentiels — E05 à E07). Tous les
trois doivent garantir la même chose : téléchargement en flux, empreinte
SHA-256, écriture atomique, manifeste de traçabilité. Seule la résolution
d'URL varie réellement d'une source à l'autre (gabarit fixe pour Parcoursup,
requête au catalogue data.gouv pour Sirene, dont les liens changent chaque
mois).

Deux décisions structurantes ont dû être arbitrées en écrivant ce premier
connecteur.

## Décision 1 — Extraire les primitives avant la deuxième occurrence

**Options envisagées**

1. **Écrire tout dans `parcoursup.py`, mutualiser après trois occurrences**
   (règle courante contre l'abstraction prématurée) — écartée : la
   mutualisation demandée n'est pas une conjecture sur un futur usage, elle
   est **déjà connue et écrite dans le plan d'exécution** (E06 et E07
   répéteront explicitement flux HTTP, empreinte, écriture atomique,
   manifeste). Attendre la troisième occurrence pour extraire un code déjà
   identifié comme commun ne réduit aucun risque, elle ne fait que reporter un
   refactoring certain.
2. **Extraire les primitives dans `_flux.py` dès le premier connecteur, avant
   Sirene** — retenue.

**Décision** : option 2. `_flux.py` porte les mécaniques génériques ;
`parcoursup.py` ne porte que ce qui est propre à Parcoursup (gabarit d'URL,
orchestration des 8 millésimes).

**Conséquences** — le deuxième connecteur (Sirene, E06) s'appuie sur du code
déjà testé plutôt que de dupliquer puis de refactorer sous pression. Le risque
accepté : `_flux.py` est écrit avec un seul appelant réel, donc son
interface pourrait devoir bouger à l'usage par Sirene ou les référentiels.
**Ce qui ferait reconsidérer** : si l'écriture du connecteur Sirene révèle
qu'une primitive supposée commune (ex. la résolution d'URL) doit en réalité
être générique — auquel cas la limite entre `_flux.py` et les connecteurs
serait à redessiner, pas la mutualisation elle-même.

## Décision 2 — Manifeste corrompu : quarantaine plutôt qu'écrasement silencieux

**Options envisagées**

1. **Écraser silencieusement un manifeste illisible** à la prochaine écriture
   — écartée : cache reconstructible ou non, un JSON qui devient
   soudainement illisible est un incident (disque plein en cours d'écriture,
   processus tué au milieu, corruption du support). Le laisser disparaître
   sans trace empêche tout diagnostic a posteriori.
2. **Bloquer la chaîne sur un manifeste corrompu** — écartée : le manifeste
   n'est pas la source de vérité de l'intégrité des données (l'empreinte
   SHA-256 recalculée à chaque passage l'est) ; le faire bloquer romprait la
   règle « le manifeste ne doit jamais bloquer la chaîne » et retélécharger
   inutilement des fichiers déjà intacts serait disproportionné.
3. **Mettre le fichier en quarantaine (renommage horodaté) et repartir d'un
   manifeste vide, en journalisant l'incident au niveau erreur** — retenue.

**Décision** : option 3. `lire_manifeste()` traite un JSON illisible comme
vide (pas d'exception propagée, la chaîne continue), mais déplace le fichier
fautif vers `manifeste.json.corrompu-{horodatage}` et journalise la perte de
traçabilité au niveau erreur plutôt qu'en silence.

**Conséquences** — un manifeste corrompu entraîne un retéléchargement complet
des millésimes déjà présents (perte de l'idempotence pour ce passage
uniquement, pas de perte de données), mais laisse une trace exploitable :
l'opérateur retrouve le fichier incriminé sous son nom horodaté et le message
d'erreur dans les journaux. **Ce qui ferait reconsidérer** : si la fréquence
réelle de corruption s'avérait non négligeable (au-delà d'un incident isolé),
un mécanisme de sauvegarde du manifeste avant écriture serait à envisager,
plutôt qu'une simple détection après coup.

## Note de méthode — signalement non reproduit

Un rapport de revue de code, en préparant ce commit, a signalé un risque de
perte d'entrées du manifeste en fonctionnement normal. Reproduit avant
correction (invariant du projet) : le risque n'existait qu'en cas de
manifeste déjà corrompu — c'est-à-dire exactement le cas couvert par la
décision 2 ci-dessus — pas en marche normale. Aucun correctif supplémentaire
n'a donc été appliqué au-delà de la quarantaine déjà décidée.
