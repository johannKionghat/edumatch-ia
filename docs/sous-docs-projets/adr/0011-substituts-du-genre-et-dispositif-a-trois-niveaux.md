# ADR 0011 — Substituts du genre mesurés et dispositif d'équité à trois niveaux

Statut : accepté (2026-08-29)

## Contexte

Le projet exclut le genre des variables du modèle et prévoit de tester les
substituts potentiels pour corrélation résiduelle. L'hypothèse de départ
désignait l'académie et l'établissement d'origine comme principaux
substituts. L'analyse d'équité (`03-jgk-eda-equite-substituts.ipynb`, E11)
mesure l'information mutuelle entre six variables candidates et le sexe des
admis, corrigée du nombre de modalités par permutation (5 tirages, graine
42) : `cod_uai` 28,9 % · `fili` (filière) 19,5 % · `ville_etab` 10,2 % ·
`select_form` 5,6 % · `dep` 2,3 % · `acad_mies` (académie) 1,4 %. Ce résultat
infirme l'hypothèse de départ : l'académie n'explique que 1,4 % du genre. Le
deuxième substitut le plus puissant est la filière, à 19,5 % — une variable
indispensable, qu'on ne peut pas retirer sans détruire la capacité du modèle
à distinguer les formations.

## Décision

Un dispositif d'équité à trois niveaux, aucun ne suffisant seul : exclusion
du genre à l'entrée, vérifiée par test ; mesure des substituts, à rejouer à
chaque évolution notable du jeu de variables ; audit a posteriori sur les
prédictions (E26), seule vérification qui porte sur ce qui compte — l'écart
de traitement produit, pas les corrélations d'entrée.

## Alternatives écartées

- Retirer aussi la filière par précaution : elle est structurante de
  l'accessibilité (écart médian de +1,1 à +42,3 points selon la filière,
  E10) ; la retirer détruirait la capacité prédictive pour un gain d'équité
  qui reste à démontrer.
- Se fier au seul retrait du genre et de ses substituts directs, sans audit
  a posteriori : la mesure montre que l'exclusion ne suffit pas, la filière
  reconstitue déjà 19,5 % du genre.
- Ne surveiller que l'académie, comme prévu initialement : la mesure la
  place au dernier rang des six variables testées.

## Conséquences

L'audit d'équité (E26) doit être conçu pour détecter un écart de prédiction
par sexe même en l'absence de toute variable de genre — c'est précisément le
scénario que ce résultat rend probable, via la filière. La mesure de
substituts doit être rejouée sur le jeu de variables finalement retenu en
E20, avec la même correction de cardinalité (l'absence de correction avait
ici doublé artificiellement le score de `cod_uai`).

Je reviendrais sur le maintien de la filière si l'audit d'équité montrait un
ratio d'impact disparate significatif porté par elle — la décision serait
alors réexaminée en mettant en balance la perte de performance contre le
gain d'équité mesuré.

Reproduit par `notebooks/03-jgk-eda-equite-substituts.ipynb`, sur
`data/raw/parcoursup/` (session 2025).
