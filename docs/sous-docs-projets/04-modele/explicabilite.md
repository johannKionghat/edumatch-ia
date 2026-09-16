# Explicabilité — TreeSHAP, précalcul, limites (E25, critère 4.14)

Source : `src/edumatch/models/explain.py`. Le modèle expliqué est celui entraîné
en E22 (`04-modele/evaluation.md`), sur le même split temporel strict.

## Pourquoi TreeSHAP, et pourquoi précalculé

LightGBM a été retenu plutôt qu'un réseau de neurones pour trois raisons
déjà posées à la conception (`specification.md`) : des données tabulaires et
hétérogènes, des valeurs manquantes structurelles (ADR 0013), et
l'explicabilité exacte que permet TreeSHAP sur un modèle à arbres. Cette
étape encaisse cette dernière promesse.

Sur un réseau de neurones, une valeur de Shapley exacte serait hors de
portée — le coût croît exponentiellement avec le nombre de variables — et il
faudrait se contenter d'une approximation (KernelSHAP, LIME). Sur un modèle
à arbres, TreeSHAP calcule les valeurs de Shapley **exactement**, en temps
polynomial, en exploitant la structure des arbres plutôt qu'en
ré-échantillonnant des coalitions de variables. C'est le seuil qui a fait
préférer LightGBM à un réseau, et qui n'aurait pas de contrepartie
équivalente avec un modèle boîte noire.

**L'axiome d'efficacité vérifié, deux fois.** Une valeur de Shapley n'a de
sens que si la somme des contributions plus la valeur de base reconstitue
exactement la prédiction. Vérifié à **2,1 × 10⁻¹⁵** près sur le modèle réel
(l'écart résiduel est une erreur d'arrondi flottant, pas une erreur de
méthode), et par un test unitaire indépendant sur un modèle jouet dont la
prédiction est connue par construction.

## Le précalcul complet, mesuré et jugé réaliste en lot

Le nombre de cellules `(session, formation, type de baccalauréat, boursier)`
est fini et connu à l'avance — 440 030 sur les six sessions labellisées
(2020-2025, ADR 0012) — ce qui rend un précalcul complet raisonnable,
contrairement à un flux de requêtes illimité qu'un calcul à la demande
devrait supporter.

Mesuré sur l'exécution réelle : **440 030 cellules, 8,3 minutes, 99,8 Mo**
d'artefact. Réaliste en tâche de lot après chaque réentraînement (E33-E34),
pas à la demande par requête de l'API (E29) : une explication SHAP par
requête recalculerait ce que le précalcul a déjà produit, pour un coût de
latence que l'API n'a aucune raison de payer.

## Classement global — moyenne des valeurs absolues, pondérée par l'effectif

| Variable | Part de l'explication |
|---|---:|
| Taux de la session précédente | **33,5 %** |
| `nb_voe_pp` (nombre de vœux, session précédente) | 9,1 % |
| Libellé de filière | 8,4 % |
| Département | 7,5 % |
| Capacité de la formation | 6,0 % |
| `prop_tot` (nombre d'admis, session précédente) | 5,7 % |

Le taux de la session précédente est un quotient calculé à partir de
`prop_tot` et `nb_voe_pp`, déjà présents séparément dans le jeu de variables :
les trois sont corrélées par construction. Réunies, elles portent
**48,3 %** de l'explication totale — TreeSHAP répartit le crédit selon
l'usage réel qu'en font les arbres, pas selon une « cause première » qui
n'existe pas dans un ensemble d'arbres, et cette part cumulée doit se lire
comme une seule information partagée en trois plutôt que comme trois signaux
indépendants.

## Un écart entre deux mesures d'importance, rapporté tel quel

L'importance de gain de LightGBM, produite en E22 comme sous-produit de
l'entraînement, faisait du taux de la session précédente une variable **sept
fois** plus importante que la deuxième. TreeSHAP la ramène à 33,5 % de
l'explication. Les deux métriques répondent à des questions différentes :

| Métrique | Question posée |
|---|---|
| Importance de gain (LightGBM) | Réduction de perte cumulée sur tous les nœuds de tous les arbres |
| Valeur de Shapley (TreeSHAP) | Contribution moyenne à une prédiction individuelle |

Une variable très utilisée en profondeur dans l'arbre — c'est le cas du taux
précédent, qui sert à raffiner des coupures déjà bien orientées par d'autres
variables — voit son gain surestimé par rapport à sa contribution réelle aux
prédictions. Aucune des deux mesures n'est fausse ; elles ne mesurent pas la
même chose, et ne doivent jamais être citées l'une pour l'autre sans le dire.

## Limites de SHAP, à ne jamais taire

- Une valeur de Shapley contribue **au modèle**, pas à la réalité qu'il
  décrit : elle explique ce que LightGBM a appris à partir des données
  d'entraînement, pas pourquoi un candidat est effectivement admis. Ce n'est
  pas une preuve causale.
- Avec des variables corrélées par construction (le quotient et ses deux
  composantes, ci-dessus), le partage du crédit est mathématiquement défini
  par les axiomes de Shapley, mais peut rester contre-intuitif : il dépend
  de la structure des arbres, pas d'une hiérarchie de causes.
- Une explication locale, pour une cellule donnée, ne se généralise pas à
  une autre — d'où la nécessité de la vue globale ci-dessus, qui répond à
  une question différente (l'effet moyen, pas l'effet pour un cas précis).
- La moyenne des valeurs absolues de Shapley (l'importance globale) n'est
  pas une importance causale : c'est une moyenne de contributions à des
  prédictions, pondérée par l'effectif de la cellule comme le reste de
  l'évaluation (ADR 0009).

## Ce que cette étape transmet à l'audit d'équité (E26)

Le poids des substituts du genre dans l'explication globale (la filière et
le département, mesurés en E11 comme corrélés au genre) est un **signal
transmis** à l'audit d'équité, pas une conclusion à sa place : SHAP mesure
la contribution d'une variable au modèle, l'audit d'équité mesure l'écart de
traitement entre groupes sur les prédictions réelles. Détail chiffré :
`04-modele/equite.md`.

---
*Mise à jour : 2026-08-30, commit `e8417bb`.*
