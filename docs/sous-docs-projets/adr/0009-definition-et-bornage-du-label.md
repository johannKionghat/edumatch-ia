# ADR 0009 — Définition du label, bornage, pondération et absence de seuil d'effectif

**Date** : 2026-08-29 · **Statut** : accepté

## Contexte

La cible du modèle est un taux d'admission observé par cellule
`(formation × session × type de bac × boursier)`. L'analyse du carnet
`notebooks/01-jgk-eda-label.ipynb` (E09) établit trois faits sur la session
2025 qui obligent à arbitrer :

- le taux `prop_tot / nb_voe_pp` dépasse 1 dans 8,9 % des cellules bac général
  (1 219 sur 13 685), et le dépassement persiste sur les grosses cellules
  (483 sur 7 154 au-delà de 100 vœux) — ce n'est pas un artefact de petit
  effectif, c'est structurel : `nb_voe_pp` compte des vœux (candidats),
  `prop_tot` compte des propositions émises, réémises après chaque
  désistement ;
- la distribution est étalée sur tout l'intervalle avec des masses non
  négligeables aux deux bornes (jusqu'à 21,6 % de taux nul pour le bac
  professionnel) ;
- le nombre de vœux par cellule varie fortement, et un seuil d'effectif
  minimal écarterait une part substantielle des observations (26 % à
  30 vœux).

## Options envisagées

1. **Définition alternative `acc / nb_voe_pp`** (candidats inscrits plutôt que
   propositions émises) — ne dépasse jamais 1 (3 cellules sur 13 685) et
   réglerait le bornage d'un trait. Écartée : `acc` mesure l'acceptation, pas
   l'admission. Un candidat qui décline une proposition pour une meilleure
   option a bel et bien été admis ; le retenir mesurerait un mélange entre
   sélectivité et désirabilité, pas l'accessibilité que le système promet.
2. **Ne pas borner, garder le taux brut** — écartée : un taux supérieur à 1
   n'a pas de sens comme probabilité d'admission, et casserait toute métrique
   de calibration en aval.
3. **Borner à 1, en documentant la raison** — retenue.
4. **Poids égal pour toutes les cellules à l'entraînement** — écartée : une
   cellule à 3 vœux et une cellule à 500 vœux ne portent pas la même
   fiabilité statistique ; les traiter à égalité biaiserait l'optimisation
   vers les petites cellules, nombreuses.
5. **Pondérer par l'effectif de la cellule (`nb_voe_pp`)** — retenue.
6. **Exclure les cellules sous un seuil d'effectif (ex. 30 vœux)** — écartée :
   écarterait 26 % des observations, et la pondération (option 5) traite déjà
   leur moindre fiabilité sans les supprimer purement.
7. **Ne pas exclure les petites cellules** — retenue, en corollaire de
   l'option 5.

## Décision

Quatre décisions arrêtées ensemble :

1. **Conserver `prop_tot / nb_voe_pp`** comme définition du taux : c'est la
   seule des définitions comparées qui mesure l'accessibilité de la formation
   et non la préférence du candidat.
2. **Borner le taux à 1**, en énonçant que le dépassement provient de
   propositions réémises après désistement — une borne sémantique, pas une
   correction de valeur aberrante.
3. **Pondérer par l'effectif de la cellule** à l'entraînement du modèle
   (E22).
4. **Ne pas exclure les petites cellules** par un seuil d'effectif minimal.

## Conséquences

- La moyenne de 0,522 déjà citée dans la documentation et le dossier
  correspond à cette moyenne bornée (la moyenne brute vaut 0,545) : le calcul
  ne change pas, sa justification est désormais écrite.
- Le protocole d'évaluation (E23) doit vérifier la calibration explicitement
  aux deux bornes, où la formation d'accessibilité nulle et la formation en
  tension nulle sont des cas réels à bien restituer, pas des extrêmes à
  lisser.
- Une erreur absolue moyenne pondérée est retenue plutôt qu'une erreur
  quadratique, plus sensible aux valeurs bornées et moins lisible pour une
  cible interprétée comme une probabilité.
- **Ce qui ferait reconsidérer** : si l'audit d'équité (E26) montrait que la
  pondération par effectif défavorise systématiquement les formations à
  faible volume de vœux d'un profil donné (bac professionnel, notamment,
  où 21,6 % des formations n'émettent aucune proposition) — auquel cas il
  faudrait revoir la pondération, pas la définition du taux elle-même.

**Reproduit par** : `notebooks/01-jgk-eda-label.ipynb`, cellules de la
section « Phase 2 — la cible », sur `data/raw/parcoursup/` (session 2025).
