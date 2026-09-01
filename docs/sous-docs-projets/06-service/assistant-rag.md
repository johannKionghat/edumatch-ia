# Assistant documentaire — brique secondaire (E32)

**Critère servi** : Bloc 4, 4.1 (algorithme adapté au cahier des charges) ·
**Source** : `src/edumatch/rag/` (`corpus.py`, `index.py`, `assistant.py`,
`generation.py`) · **Commit** : `b56ec9f` · **Dernière revue** :
2026-09-01.

Réécrit pour ce projet, jamais repris de l'ancien prototype d'orientation
qui existait par ailleurs.

## Le corpus

**7 403 documents**, issus des référentiels ONISEP déjà ingérés en E07 :
5 869 formations et 1 534 métiers. Chaque document porte sa citation — jeu,
URL, licence, date de collecte — lue depuis le manifeste d'ingestion, pas
recalculée ni ressaisie.

## La citation est garantie par construction

Les sources retournées viennent toujours de la recherche
(`index.rechercher`), jamais de ce que le modèle de langage affirme avoir
consulté : la liste des citations est bâtie à partir des documents
retrouvés **avant** l'appel au modèle. Un modèle qui inventerait une
réponse ne peut pas inventer sa source, puisque la source ne dérive jamais
de son texte.

Si aucun passage ne dépasse le seuil de similarité configuré
(`rag.seuil_similarite_minimale`), l'assistant répond qu'il ne sait pas
plutôt que de produire une réponse sans appui documentaire.

## Le choix technique : recherche lexicale, pas d'embeddings

TF-IDF, sur une dépendance déjà présente dans le projet. **Écartés** :
embeddings, base vectorielle, modèle à télécharger — pour un corpus deux
ordres de grandeur en dessous du volume où un index approximatif apporte
un gain mesurable. **Écartés aussi**, faute de critère qui les exige :
reranker et évaluation automatisée (RAGAS). Cette brique est secondaire au
projet ; la sobriété est ici la réponse d'architecte, pas un renoncement.

## Dégradation explicite à chaque étage

Sans clé d'API, le client n'est même pas construit et le SDK n'est pas
importé — pas d'appel réseau tenté puis échoué en silence. Avec une clé
mais un appel en échec, le service répond quand même en **mode extractif**
(les passages retrouvés, sans reformulation par un modèle de langage), avec
un avertissement qui nomme la panne. L'ensemble est testé sans aucun appel
réseau.

## Ce qui n'est jamais journalisé

La question posée n'est jamais journalisée — seulement sa longueur et le
nombre de résultats retournés. Un mineur peut saisir une donnée personnelle
dans une question sans y penser ; ne pas conserver la question elle-même
retire ce risque à la source plutôt que de le gérer après coup.

Les fichiers d'adresses d'établissements sont exclus de l'index, sans
pertinence pour une question documentaire sur les formations et les
métiers.

## Hors du périmètre de la surveillance de dérive

Cette brique reste hors du périmètre de la détection de dérive prévue pour
le modèle d'accessibilité (E34) — elle ne fait aucune prédiction chiffrée,
il n'y a rien à dériver au sens statistique. Le code le déclare
explicitement, pour qu'un lecteur ne l'y cherche pas.

---

*Dernière mise à jour : 2026-09-01, commit `b56ec9f`.*
