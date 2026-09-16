# Journalisation article 12 et purge exécutable (E30)

**Critère servi** : Bloc 1, 1.3 et 1.6 · Bloc 3, 3.10 · Bloc 4, 4.7 ·
**Source** : `src/edumatch/api/audit.py`, `src/edumatch/api/audit_purge.py` ·
**Commit** : `44c49be` · **Dernière revue** : 2026-09-01.

Complète le registre des traitements de la gouvernance
(`05-gouvernance/registre-traitements.md`, T5) : ce document décrit ce que
j'ai construit pour exécuter la durée de conservation que le registre
décide.

## Le point qui comptait

Une durée de conservation n'existe que si une tâche l'exécute, sinon c'est
une intention. C'était la lacune inscrite par la gouvernance
(`registre-traitements.md`, lacune L2). Elle est levée côté code : la
purge existe, tourne, est testée et idempotente.

## Le journal (`audit.py`)

Un registre distinct des journaux applicatifs, écrit dans un fichier dédié
(`processed/audit/journal.jsonl`) plutôt que dans la sortie standard,
accessible à quiconque a accès au service. Chaque enregistrement porte :
horodatage, identifiant technique de requête, version du modèle et
empreinte du commit Git, variables d'entrée, score produit, facteurs
explicatifs restitués. `decision_conseiller` reste `None` à l'écriture :
la décision motivée d'un conseiller est journalisée séparément par
`feedback_store.py` (T6 de la gouvernance), qui ne partage aujourd'hui
aucun identifiant de requête avec ce journal — les deux traces ne se
corrèlent donc pas automatiquement. Le champ existe pour que la structure
n'ait pas à changer le jour où cette corrélation sera construite.

## Les trois paliers

L'article 12 du règlement sur l'IA impose un plancher de conservation pour
un système à haut risque (au moins six mois) ; l'article 5.1.e du RGPD
impose un plafond. Deux textes contradictoires, conciliés par trois
paliers datés :

| Palier | Durée | Contenu | Ce que cela permet |
|---|---|---|---|
| 1 — clair | 0 à 12 mois | Entrées, sortie, version, horodatage | Répondre à une réclamation individuelle, rejouer une inférence contestée. Couvre le plancher légal et une campagne Parcoursup entière |
| 2 — pseudonymisé | 12 à 36 mois | Identifiant de requête remplacé par un jeton non réversible, variables conservées | Audit d'équité et détection de dérive restent possibles ; le lien avec une personne est rompu |
| 3 — agrégats | au-delà de 36 mois | Distributions et métriques par sous-population, plus aucune ligne d'inférence | Conserver la capacité de démonstration historique sans conserver l'identification |

La pseudonymisation remplace l'identifiant d'exécution par un jeton neuf
et jette l'original. Écarté : un hachage avec secret, techniquement
réversible tant que le secret existe, pour une garantie plus faible que
l'original qui n'existe simplement plus.

## La purge, prudente par construction

Mode simulation par défaut, mode réel explicite (`--appliquer`). Chaque
passage, simulation comprise, ajoute sa ligne à
`processed/audit/purges.jsonl` : horodatage, mode, quatre compteurs. Une
suppression silencieuse serait invisible le jour où elle se tromperait.

**Ce qui a été vérifié** : un test écrit trois lignes à trois âges, lance
une purge réelle, et vérifie que la fraîche est intacte, que
l'intermédiaire a changé de jeton sans perdre ses variables, et que
l'ancienne a disparu du journal pour réapparaître comptée dans l'agrégat.
Un autre test rejoue la même purge à la même date et vérifie que rien ne
bouge : l'idempotence est démontrée, pas supposée.

## Deux lacunes déclarées

- **Le déclenchement planifié reste à poser.** La purge existe et
  s'exécute à la demande ; elle n'est pas encore appelée par une tâche
  planifiée de l'ordonnanceur (Airflow, E33).
- **La purge du journal des décisions de conseiller (T6, `/feedback`)
  n'est pas construite**, faute d'identifiant commun avec le journal
  d'inférence (T5) : les deux journaux ne se corrèlent pas aujourd'hui,
  donc purger l'un ne garantit rien sur l'autre.

---

*Dernière mise à jour : 2026-09-01, commit `44c49be`.*
