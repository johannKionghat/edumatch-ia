# ADR 0010 — Fuite fonctionnelle de la tension de vœux, décalage temporel pour reconstruire la clé de formation

**Date** : 2026-08-29 · **Statut** : accepté

## Contexte

L'analyse des écarts entre types de baccalauréat
(`notebooks/02-jgk-eda-ecarts-selectivite.ipynb`, E10) établit que le taux
d'admission d'une cellule est fortement expliqué par sa tension,
`voe_tot / capa_fin` : de 1,000 à 0,182 du quintile le moins tendu au plus
tendu (médiane 11,4 vœux par place). `voe_tot` est donc une variable
candidate naturelle pour le modèle. Elle pose cependant un problème que le
split temporel seul ne détecte pas : `voe_tot` est le total des vœux reçus
par la formation sur la session, connu seulement à la clôture de la
campagne — **après** le moment où le système doit répondre à un candidat qui
formule encore son vœu.

Ce n'est pas une fuite temporelle au sens strict de l'invariant du projet
(la variable ne décrit pas un événement postérieur à la décision
d'admission qu'elle prétend prédire — elle précède chronologiquement cette
décision). C'est une **inadéquation au cas d'usage** : la variable existe
avant la décision d'admission mais après le moment où le système doit
produire sa réponse. Un modèle qui l'utiliserait afficherait une excellente
performance en évaluation rétrospective (la tension finale est très
informative) et serait inutilisable en production (elle n'est pas
disponible au moment de l'inférence réelle).

Par ailleurs, la clé de formation `cod_aff_form`, établie comme grain de
l'analyse en E09, est absente des millésimes 2018 et 2019 — ce qui limite la
possibilité de suivre une formation d'une session à l'autre sur toute la
période.

## Options envisagées

1. **Conserver `voe_tot` comme variable du modèle** — écartée : reproduit
   exactement le problème ci-dessus, un modèle excellent hors ligne et
   inopérant en production.
2. **Retirer purement la tension du modèle** — écartée : jette une
   information utile ; la tension de la session précédente ou des sessions
   antérieures pour la même formation reste disponible au moment de
   l'inférence et porte une part de ce signal.
3. **Utiliser la tension de la session N-1 pour prédire la session N**
   (variable décalée) — retenue en principe pour E20, sous réserve de
   disposer d'une clé de formation stable d'une session à l'autre.
4. **Abandonner le suivi inter-sessions faute de clé stable en 2018-2019** —
   écartée sans l'avoir vérifié : `cod_aff_form` est absente, mais le lien
   vers la fiche de formation porte un paramètre `g_ta_cod` qui, vérifié sur
   les millésimes où les deux coexistent, coïncide exactement avec
   `cod_aff_form`.
5. **Reconstruire `cod_aff_form` à partir de `g_ta_cod` pour 2018-2019** —
   retenue : couvre 92,4 % des lignes en 2018 et 94,6 % en 2019, avec un
   taux de jointure d'une session à la suivante de 82 % à 95 %.

## Décision

- `voe_tot` de la session courante n'entre pas dans les variables du modèle
  (E20) : seule une version décalée d'au moins une session est éligible.
- La clé de formation est reconstruite pour 2018 et 2019 à partir de
  `g_ta_cod`, avec un test qui vérifie la couverture (92,4 % / 94,6 %) et le
  taux de jointure d'une session à l'autre à chaque exécution du pipeline —
  une baisse de ces taux doit être détectée, pas silencieusement absorbée.

## Conséquences

- Le test anti-fuite prévu en E20 doit couvrir explicitement cette classe
  d'inadéquation (variable disponible avant la décision mais après le
  moment de l'inférence), en plus de la fuite temporelle au sens strict.
- La couverture de 82 % à 95 % pour la jointure inter-sessions signifie
  qu'une part des formations ne pourra pas bénéficier d'une variable de
  tension décalée fiable — à traiter par une valeur manquante explicite,
  pas par une imputation qui masquerait l'absence de continuité de la
  formation.
- **Ce qui ferait reconsidérer** : si le taux de jointure mesuré sur les
  sessions les plus récentes (2024-2025) tombait sous 80 %, la variable
  décalée perdrait trop de couverture pour être utile et devrait être
  retirée du jeu de variables plutôt que conservée avec une part importante
  de valeurs manquantes.

**Reproduit par** : `notebooks/02-jgk-eda-ecarts-selectivite.ipynb`, sections
sur la tension par quintile et la reconstruction de `cod_aff_form`, sur
`data/raw/parcoursup/` (tous millésimes).
