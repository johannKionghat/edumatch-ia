# ADR 0009 — Définition du label, bornage, pondération et absence de seuil d'effectif

Statut : accepté (2026-08-29)

## Contexte

La cible du modèle est un taux d'admission observé par cellule (formation ×
session × type de bac × boursier). L'analyse du carnet
`01-jgk-eda-label.ipynb` (E09) établit trois faits sur la session 2025 : le
taux `prop_tot / nb_voe_pp` dépasse 1 dans 8,9 % des cellules bac général
(1 219 sur 13 685), et ce n'est pas un artefact de petit effectif (483 sur
7 154 au-delà de 100 vœux) — `nb_voe_pp` compte des vœux, `prop_tot` compte
des propositions réémises après chaque désistement ; la distribution est
étalée avec des masses non négligeables aux deux bornes (jusqu'à 21,6 % de
taux nul pour le bac professionnel) ; et le nombre de vœux par cellule varie
fortement, un seuil d'effectif minimal écarterait 26 % des observations à
30 vœux.

## Décision

Je conserve `prop_tot / nb_voe_pp` comme définition du taux, je le borne à 1
en énonçant que le dépassement vient des propositions réémises (une borne
sémantique, pas une correction de valeur aberrante), je pondère par
l'effectif de la cellule à l'entraînement, et je n'exclus pas les petites
cellules.

## Alternatives écartées

- `acc / nb_voe_pp` (candidats inscrits plutôt que propositions émises) : ne
  dépasse jamais 1, mais mesure l'acceptation, pas l'admission. Un candidat
  qui décline une proposition pour une meilleure option a bel et bien été
  admis.
- Garder le taux brut, sans borner : un taux supérieur à 1 n'a pas de sens
  comme probabilité d'admission et casserait toute métrique de calibration
  en aval.
- Poids égal pour toutes les cellules : une cellule à 3 vœux et une cellule
  à 500 vœux ne portent pas la même fiabilité statistique.
- Exclure les cellules sous un seuil d'effectif : écarterait 26 % des
  observations, alors que la pondération traite déjà leur moindre fiabilité
  sans les supprimer.

## Conséquences

La moyenne de 0,522 déjà citée dans la documentation correspond à cette
moyenne bornée (la moyenne brute vaut 0,545). Le protocole d'évaluation
(E23) doit vérifier la calibration explicitement aux deux bornes. Une erreur
absolue moyenne pondérée est retenue plutôt qu'une erreur quadratique, plus
sensible aux valeurs bornées.

Je reviendrais sur la pondération si l'audit d'équité (E26) montrait qu'elle
défavorise systématiquement les formations à faible volume de vœux d'un
profil donné (le bac professionnel, notamment, où 21,6 % des formations
n'émettent aucune proposition).

Reproduit par `notebooks/01-jgk-eda-label.ipynb`, sur
`data/raw/parcoursup/` (session 2025).
