"""Assistant documentaire (E32) : répond à des questions sur les formations en citant ses
sources, à partir des référentiels publics déjà présents dans le dépôt.

## Ce que cette brique fait, et ce qu'elle ne fait jamais

Elle retrouve, dans le référentiel ONISEP (IDÉO), les passages les plus
proches d'une question posée, et les restitue — cités, jamais reformulés en
une affirmation qu'aucune source ne porte. Voir `assistant.py` pour le
comportement exact : mode extractif toujours disponible, mode génératif
seulement si une clé de modèle de langage externe est configurée, et jamais
une réponse sans citation vérifiable.

## Portée délibérément secondaire

Cette brique n'a droit à aucun composant que le reste du projet
n'exigerait pas ailleurs : pas de base vectorielle dédiée, pas de reranker,
pas d'évaluation automatisée de la qualité des réponses (RAGAS ou
équivalent). La recherche de passages utilise `scikit-learn`
(`TfidfVectorizer`), déjà une dépendance du projet — voir `index.py`.

## Hors périmètre de la détection de dérive

Cette brique n'entre dans le périmètre d'aucune surveillance de dérive
(`edumatch.models`, PSI et KS, E34) : elle ne sert aucune prédiction du
modèle appris, elle indexe un référentiel public et restitue des extraits
cités. Rien ici n'est comparé à une distribution de référence.

## Aucune donnée personnelle

Le corpus indexé (IDÉO) est un référentiel public sans donnée personnelle.
Les questions posées par un utilisateur ne sont jamais journalisées telles
quelles (voir `assistant.AssistantRAG.repondre`) : le projet traite des
données de mineurs, et une question mal formulée pourrait en contenir sans
que l'utilisateur y pense.
"""

from __future__ import annotations
