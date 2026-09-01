# ADR 0018 — Détection de dérive : PSI médian sur 46 variables, seuil à 0,20, sans Evidently

**Date** : 2026-09-01 · **Statut** : accepté

## Contexte

Le critère 4.11 exige une détection de dérive avec un seuil documenté ; le critère 4.12,
un réentraînement automatique et reproductible qui s'appuie dessus. `configs/base.yaml`
portait déjà, avant cette étape, une intention non vérifiée : `seuil_reentrainement: 0.20`
en indice de stabilité de population (PSI), sans qu'aucune mesure sur les données réelles
n'ait jamais confronté ce chiffre à une dérive observée.

Le modèle a par ailleurs un défaut déjà mesuré et documenté (E22, E23) : il bat la
baseline en validation 2024 (MAE pondérée 0,0690 contre 0,0727) mais la perd en test 2025
(0,0758 contre 0,0701), et sa calibration s'effondre entre les deux (ECE 0,0030 → 0,0371).
Cette étape devait établir si le PSI, au seuil retenu, aurait pu signaler ce défaut à
l'avance.

## Ce qui a été mesuré, sur les données réelles

Trois familles de dérive, sur la fenêtre où le label existe (2020-2025, six sessions,
ADR 0012 — pas huit : les deux premiers millésimes Parcoursup bruts n'ont pas de cible
observée et ne peuvent alimenter ni la dérive de la cible ni celle des prédictions).
Référence : les quatre sessions d'entraînement 2020-2023 regroupées
(`distribution_entrainement`, déjà la valeur de `derive.reference`).

| Famille | Référence -> validation 2024 | Référence -> test 2025 |
|---|---|---|
| Variables (médiane des 46) | PSI = 0,0061 | PSI = 0,0096 |
| Cible (`taux`) | PSI = 0,0115 (KS = 0,044) | PSI = 0,0115 (KS = 0,028) |
| Prédictions du modèle | PSI = 0,0174 (KS = 0,038) | PSI = 0,0296 (KS = 0,053) |

Comparaisons consécutives (session N contre N-1, cinq paires 2020→2021 … 2024→2025), qui
calibrent ce qu'est une dérive « normale » d'une session sur l'autre : médiane des
variables entre 0,0013 et 0,0081 ; cible entre 0,0007 et 0,0106 ; prédictions entre 0,0008
et 0,0075, à une exception près — 2020→2021 (PSI = 0,063), qui recoupe exactement
l'anomalie déjà documentée par l'ADR 0012 (contamination des variables de mention et
absence d'antécédent sur la première session de la fenêtre).

### Trois variables dépassent seules le seuil, et c'est de la dérive amont

Sur les 46 variables, seules trois dépassent 0,20 dans au moins une comparaison de
production, même après neutralisation des variations de forme
(`derive_stats.canoniser_categorie` : accent, casse, tiret contre espace) :

- **`region_etab_aff`** — PSI brut 4,99, PSI canonisé 0,75. La moitié de l'écart brut
  n'est qu'un changement de graphie (« Grand Est » / « Grand-Est »,
  « Nouvelle-Aquitaine » / « Nouvelle Aquitaine »). Ce qui reste après neutralisation est
  un changement de **nomenclature** du référentiel région d'une session à l'autre
  (« Centre-Val de Loire » devient « Centre », « La Réunion » devient « Réunion »,
  « Polynésie française » et « étranger » disparaissent de l'échantillon). Le monde n'a
  pas bougé : le fichier source change de libellé. Cette variable est reléguée au rang 45
  sur 48 de l'importance du modèle (E22) — la dérive la plus spectaculaire du rapport ne
  porte sur presque rien d'utile au modèle.
- **`select_form`** — PSI 0,35 après neutralisation. La cause : le millésime 2020, et lui
  seul, porte le libellé tronqué « formation non selec » au lieu de
  « formation non sélective » partout ailleurs — un défaut d'export propre à cette seule
  session, jamais corrigé en amont. La proportion réelle de formations non sélectives ne
  bouge presque pas sur la période (22,7 % en 2020, 23,9 % en 2025). `select_form` est en
  revanche une variable importante (rang 6 sur 48) : c'est le cas le plus net de ce que le
  plan de détection nomme la dérive amont — une source qui change de format produit
  exactement les mêmes symptômes qu'un changement du monde réel, sur une variable qui
  compte.
- **`fil_lib_voe_acc`** — PSI 0,23 à 0,31, la seule des trois qui n'est pas un artefact de
  forme : 712 modalités mesurées (libellés de filière), un renouvellement chaque année à
  mesure que des formations apparaissent ou changent de nom dans le catalogue Parcoursup.
  Plafonnée à `top_k_categories_psi: 30` (les modalités les moins fréquentes de la
  référence regroupées sous une modalité `__autre__`) pour ne pas laisser cette seule
  colonne, à très forte cardinalité, dominer la lecture du rapport.

## Décision

1. **Le seuil reste 0,20**, mais s'applique à la **médiane** du PSI des 46 variables pour
   une comparaison donnée, jamais à leur maximum — voir `models.derive.RapportDerive.reentrainement_recommande`.
   Appliqué au maximum, il aurait déclenché en permanence à cause de `region_etab_aff`
   (0,75, un renommage de référentiel, jamais corrigé) et de `select_form` (0,35, un défaut
   d'un seul millésime) : exactement l'écueil que la consigne de cette étape demandait
   d'éviter — « un seuil qui se déclenche en permanence... est désactivé au bout d'un
   mois ». À la médiane, le pire cas mesuré (0,0096, référence contre test 2025) reste
   vingt fois sous le seuil : marge confortable contre le bruit normal d'une session,
   déclenchement réservé à un déplacement massif et généralisé, pas à une poignée de
   colonnes de nomenclature instable.
2. Les variables individuellement au-delà du seuil restent **rapportées** (`resume()`,
   figure `e34-derive-variables.png`) comme diagnostic de dérive amont — une alerte
   distincte, jamais un déclencheur de réentraînement. Corriger `select_form` et
   `region_etab_aff` à la source (`ingestion/parcoursup.py` ou `transform/reconciliation.py`)
   reste un travail futur, hors du périmètre de détection de cette étape.
3. **Le PSI catégoriel est toujours calculé sur la forme canonisée** (accent, casse,
   séparateur neutralisés), jamais sur le texte brut — sans quoi la moitié du rapport ne
   décrirait que des artefacts d'encodage et de graphie, pas des changements réels.
4. **La dérive de la cible et des prédictions gouvernent aussi le déclenchement**, à
   égalité avec la médiane des variables (OU logique des trois familles) : une des deux
   qui dépasse 0,20 suffit, même si les 46 variables restent stables — c'est le scénario
   d'une dérive du concept pure (P(Y|X) qui change sans que P(X) bouge), que le PSI des
   seules entrées ne peut pas voir.

## Ce que cette mesure ne permet pas de conclure, et pourquoi c'est important de le dire

Le PSI mesuré ici, à ce seuil, **n'aurait pas signalé** la dégradation validation → test
déjà connue (MAE 0,0690 → 0,0758, ECE 0,0030 → 0,0371) : la dérive de la cible (0,0115) et
des prédictions (0,0174 → 0,0296) reste un ordre de grandeur sous 0,20. Deux lectures, pas
une seule :

- soit le seuil est correctement calibré contre le bruit normal (ce que les comparaisons
  consécutives confirment) et cette dégradation particulière est trop fine pour qu'un
  déplacement **marginal** de P(X) ou de P(Y) la capture — c'est une dérive du concept au
  sens strict, une relation P(Y|X) qui se déforme sans que les distributions marginales
  bougent significativement, exactement le type de dérive que le PSI, par construction, ne
  voit pas ;
- soit une partie de cet écart n'est pas de la dérive du tout, mais un défaut de
  généralisation du modèle sur un split relativement court (quatre sessions
  d'entraînement) — l'ADR 0012 documente déjà que la cible elle-même n'est pas
  stationnaire sur la période.

Conséquence assumée : **le PSI est un signal précoce sur les entrées et les sorties, pas
un substitut à la mesure de performance réelle**. Une fois la vérité terrain disponible
(la campagne suivante), c'est `models.evaluate` (E23) qui tranche — c'est exactement la
raison pour laquelle le plan de détection distingue les deux (« on surveille les entrées et
les sorties en attendant [le délai d'étiquetage], car la performance réelle n'est mesurable
qu'après coup »). Ce module ne remplace pas cette mesure, il comble l'attente avant qu'elle
soit disponible.

## Ce qui ferait reconsidérer

- Une correction de `select_form` et `region_etab_aff` à la source ferait retomber leur PSI
  au niveau des autres variables catégorielles (< 0,10) : plus rien à isoler par la
  médiane plutôt que par le maximum, et le seuil pourrait alors s'appliquer au maximum
  sans se déclencher pour de mauvaises raisons.
- Si une session future faisait franchir 0,20 à la médiane des 46 variables, ou à la
  dérive de la cible ou des prédictions, sans qu'aucune cause amont ne l'explique
  (`taches.detecter_derive` journalise un avertissement, jamais un blocage), ce serait le
  premier cas réel d'usage du seuil — à comparer alors à la MAE effectivement mesurée sur
  la session suivante pour juger s'il a bien anticipé une vraie perte de performance.
- Si `evidently` (`pyproject.toml`, `evidently>=0.4`) redevenait installable proprement dans
  cet environnement — au moment de la rédaction, sa dernière version compatible
  (`0.7.21`, seule à ne pas exiger un `numpy<2.1` en conflit avec le reste du projet)
  entraîne `litestar`, dont la dépendance transitive `multipart` (2.0.0) occupe le même nom
  d'import que `python-multipart`, dont FastAPI dépend déjà (E29) ; l'installation aboutit
  mais `import evidently` lève (`ImportError: cannot import name 'MultipartSegment'`),
  reproduit et non contourné plutôt que masqué par un `except ImportError` silencieux — ce
  module pourrait migrer vers ses métriques `DataDriftPreset`, qui calculent PSI et KS
  selon les mêmes conventions. En l'état, les fonctions de `models/derive_stats.py`
  (implémentation directe, sans dépendance supplémentaire) produisent le même résultat sur
  ce projet.

**Reproduit par** : `src/edumatch/models/derive.py` (`executer`), sur
`data/processed/parcoursup/variables.parquet` (huit millésimes bruts, six exploitables) ;
`make derive`.
