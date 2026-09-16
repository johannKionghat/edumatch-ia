# Explicabilité — TreeSHAP, précalcul, limites

Bloc 4.14. Source : `src/edumatch/models/explain.py`. Le modèle expliqué est
celui entraîné et décrit dans `evaluation.md`, sur le même split temporel.

## Pourquoi TreeSHAP, et pourquoi précalculé

J'ai retenu LightGBM plutôt qu'un réseau de neurones pour trois raisons
(`specification.md`) : des données tabulaires et hétérogènes, des valeurs
manquantes structurelles, et l'explicabilité exacte que permet TreeSHAP sur
un modèle à arbres.

SHAP (SHapley Additive exPlanations) attribue à chaque variable une part de
la prédiction, en s'appuyant sur les valeurs de Shapley issues de la théorie
des jeux : la contribution moyenne d'une variable, calculée sur toutes les
façons de la combiner avec les autres. Sur un réseau de neurones, ce calcul
exact serait hors de portée (le coût croît de façon exponentielle avec le
nombre de variables) et il faudrait se contenter d'une approximation
(KernelSHAP, LIME). Sur un modèle à arbres, TreeSHAP calcule les valeurs de
Shapley exactement, en temps polynomial, en exploitant la structure des
arbres. C'est cet avantage qui a pesé dans le choix de LightGBM.

J'ai vérifié l'axiome d'efficacité : la somme des contributions plus la
valeur de base doit reconstituer exactement la prédiction. Vérifié à
2,1 × 10⁻¹⁵ près sur le modèle réel (écart résiduel dû à l'arrondi flottant,
pas à une erreur de méthode), et confirmé par un test unitaire sur un modèle
jouet dont la prédiction est connue par construction.

Le nombre de cellules (session, formation, type de bac, boursier) est fini
et connu à l'avance — 440 030 sur les six sessions labellisées — ce qui rend
un précalcul complet raisonnable, plutôt qu'un calcul à la demande pour un
flux de requêtes illimité. Mesuré sur l'exécution réelle : 440 030 cellules,
8,3 minutes, 99,8 Mo d'artefact. C'est une tâche de lot à relancer après
chaque réentraînement, pas un calcul par requête de l'API : recalculer SHAP
à chaque appel referait ce que le précalcul a déjà produit, pour un coût de
latence inutile.

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
`prop_tot` et `nb_voe_pp`, déjà présents séparément dans les variables : les
trois sont corrélées par construction. Réunies elles portent 48,3 % de
l'explication totale. TreeSHAP répartit le crédit selon l'usage réel qu'en
font les arbres, pas selon une cause première qui n'existe pas dans un
ensemble d'arbres — cette part cumulée est une seule information partagée en
trois, pas trois signaux indépendants.

## Un écart entre deux mesures d'importance

L'importance de gain de LightGBM (sous-produit de l'entraînement) donnait au
taux de la session précédente une importance sept fois supérieure à la
deuxième variable. TreeSHAP la ramène à 33,5 % de l'explication. Les deux
métriques répondent à des questions différentes :

| Métrique | Question posée |
|---|---|
| Importance de gain (LightGBM) | Réduction de perte cumulée sur tous les nœuds de tous les arbres |
| Valeur de Shapley (TreeSHAP) | Contribution moyenne à une prédiction individuelle |

Une variable très utilisée en profondeur dans l'arbre — c'est le cas du taux
précédent, qui sert à raffiner des coupures déjà bien orientées par
d'autres variables — voit son gain surestimé par rapport à sa contribution
réelle aux prédictions. Aucune des deux mesures n'est fausse, elles ne
mesurent simplement pas la même chose.

## Limites de SHAP

- Une valeur de Shapley explique ce que LightGBM a appris à partir des
  données d'entraînement, pas pourquoi un candidat est effectivement admis.
  Ce n'est pas une preuve causale.
- Avec des variables corrélées par construction (le quotient et ses deux
  composantes), le partage du crédit est défini par les axiomes de Shapley
  mais peut rester contre-intuitif : il dépend de la structure des arbres,
  pas d'une hiérarchie de causes.
- Une explication locale, pour une cellule donnée, ne se généralise pas à
  une autre — d'où la vue globale ci-dessus, qui répond à une question
  différente (l'effet moyen, pas l'effet pour un cas précis).
- La moyenne des valeurs absolues de Shapley n'est pas une importance
  causale : c'est une moyenne de contributions à des prédictions, pondérée
  par l'effectif de la cellule comme le reste de l'évaluation.

## Ce que cette étape transmet à l'audit d'équité

Le poids des substituts du genre dans l'explication globale (la filière et
le département, corrélés au genre) est un signal transmis à l'audit
d'équité, pas une conclusion à sa place : SHAP mesure la contribution d'une
variable au modèle, l'audit d'équité mesure l'écart de traitement entre
groupes sur les prédictions réelles. Détail chiffré : `equite.md`.

---
*Mise à jour : 2026-08-30, commit `e8417bb`.*
