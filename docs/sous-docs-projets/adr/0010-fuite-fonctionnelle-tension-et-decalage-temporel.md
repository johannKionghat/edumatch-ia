# ADR 0010 — Fuite fonctionnelle de la tension de vœux, décalage temporel pour reconstruire la clé de formation

Statut : accepté (2026-08-29)

## Contexte

L'analyse des écarts entre types de baccalauréat
(`02-jgk-eda-ecarts-selectivite.ipynb`, E10) établit que le taux d'admission
est fortement expliqué par la tension, `voe_tot / capa_fin` : de 1,000 à
0,182 du quintile le moins tendu au plus tendu (médiane 11,4 vœux par
place). Mais `voe_tot` est le total des vœux reçus sur la session, connu
seulement à la clôture de la campagne — après le moment où le système doit
répondre à un candidat qui formule encore son vœu. Ce n'est pas une fuite
temporelle au sens strict (la variable précède chronologiquement la décision
d'admission), c'est une inadéquation au cas d'usage : elle existe avant
l'admission mais après le moment où le système doit produire sa réponse. Par
ailleurs, la clé de formation `cod_aff_form`, grain de l'analyse (E09), est
absente des millésimes 2018 et 2019.

## Décision

`voe_tot` de la session courante n'entre pas dans les variables du modèle :
seule une version décalée d'au moins une session est éligible. La clé de
formation est reconstruite pour 2018 et 2019 à partir de `g_ta_cod`, qui
coïncide exactement avec `cod_aff_form` sur les millésimes où les deux
coexistent — couverture de 92,4 % en 2018 et 94,6 % en 2019, taux de
jointure d'une session à la suivante de 82 % à 95 %, vérifiés par un test à
chaque exécution.

## Alternatives écartées

- Conserver `voe_tot` tel quel : excellente performance en évaluation
  rétrospective, inutilisable en production.
- Retirer purement la tension du modèle : jette une information utile, la
  tension décalée d'une session reste disponible et porte une part du
  signal.
- Abandonner le suivi inter-sessions faute de clé stable en 2018-2019 :
  écartée sans l'avoir vérifié, `g_ta_cod` comble le manque.

## Conséquences

Le test anti-fuite prévu en E20 doit couvrir cette classe d'inadéquation, en
plus de la fuite temporelle au sens strict. La couverture de 82 % à 95 %
pour la jointure inter-sessions signifie qu'une part des formations n'aura
pas de tension décalée fiable, à traiter par une valeur manquante explicite
plutôt qu'une imputation.

Je reviendrais sur ce choix si le taux de jointure sur les sessions les plus
récentes (2024-2025) tombait sous 80 % : la variable décalée perdrait trop de
couverture et devrait être retirée.

Reproduit par `notebooks/02-jgk-eda-ecarts-selectivite.ipynb`, sur
`data/raw/parcoursup/` (tous millésimes).
