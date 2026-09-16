# ADR 0018 — Détection de dérive : PSI médian sur 46 variables, seuil à 0,20, sans Evidently

Statut : accepté (2026-09-01)

## Contexte

Le critère 4.11 exige une détection de dérive avec un seuil documenté, le
critère 4.12 un réentraînement automatique qui s'appuie dessus.
`configs/base.yaml` portait déjà `seuil_reentrainement: 0.20` en indice de
stabilité de population (PSI), sans qu'aucune mesure sur les données
réelles n'ait jamais confronté ce chiffre à une dérive observée. Le modèle a
par ailleurs un défaut déjà mesuré (E22, E23) : il bat la baseline en
validation 2024 (MAE pondérée 0,0690 contre 0,0727) mais la perd en test
2025 (0,0758 contre 0,0701), et sa calibration s'effondre (ECE 0,0030 →
0,0371). Cette étape devait établir si le PSI, à ce seuil, aurait pu
signaler ce défaut à l'avance.

## Ce qui a été mesuré

Sur la fenêtre où le label existe (2020-2025, six sessions), référence
contre validation et test : la médiane du PSI des 46 variables vaut 0,0061
puis 0,0096 ; la cible (`taux`) vaut 0,0115 dans les deux cas ; les
prédictions du modèle valent 0,0174 puis 0,0296. Les comparaisons
consécutives (session N contre N-1) calibrent le bruit « normal » : entre
0,0007 et 0,0106 selon la famille, à une exception — 2020→2021 (0,063), qui
recoupe l'anomalie déjà documentée par l'ADR 0012. Seules trois variables
sur 46 dépassent seules le seuil de 0,20 dans au moins une comparaison, et
c'est de la dérive amont plutôt qu'un déplacement réel : `region_etab_aff`
(PSI canonisé 0,75, un renommage de nomenclature entre sessions, reléguée au
rang 45/48 en importance) ; `select_form` (0,35, un libellé tronqué propre
au seul millésime 2020, alors que la proportion réelle ne bouge presque pas —
22,7 % en 2020, 23,9 % en 2025 — et que la variable compte, rang 6/48) ;
`fil_lib_voe_acc` (0,23 à 0,31, un renouvellement réel des libellés de
filière, plafonné à 30 catégories pour ne pas dominer le rapport).

## Décision

Le seuil reste 0,20, mais s'applique à la médiane du PSI des 46 variables,
jamais à leur maximum : appliqué au maximum, il se déclencherait en
permanence à cause des deux artefacts ci-dessus. Les variables
individuellement au-delà du seuil restent rapportées comme diagnostic de
dérive amont, jamais comme déclencheur. Le PSI catégoriel est toujours
calculé sur la forme canonisée (accent, casse, séparateur neutralisés). La
dérive de la cible et des prédictions gouvernent aussi le déclenchement, à
égalité avec la médiane des variables (OU logique) : une dérive du concept
pure, où P(Y|X) change sans que P(X) bouge, ne serait sinon jamais vue.

## Alternatives écartées

- Evidently plutôt qu'une implémentation directe : sa dernière version
  compatible entraîne un conflit de dépendances qui casse FastAPI
  (`ImportError: cannot import name 'MultipartSegment'`), reproduit et non
  contourné. Les fonctions de `models/derive_stats.py` produisent le même
  résultat sans cette dépendance.

## Ce que cette mesure ne permet pas de conclure

Le PSI, à ce seuil, n'aurait pas signalé la dégradation validation → test
déjà connue : la dérive de la cible et des prédictions reste un ordre de
grandeur sous 0,20. Soit le seuil est correctement calibré et cette
dégradation est une dérive du concept trop fine pour que le PSI la capture,
soit une partie de l'écart est un défaut de généralisation sur un split
court plutôt qu'une dérive. Le PSI est un signal précoce sur les entrées et
les sorties, pas un substitut à la mesure de performance réelle, qui reste
tranchée par `models.evaluate` une fois la vérité terrain disponible.

## Conséquences

Corriger `select_form` et `region_etab_aff` à la source ferait retomber leur
PSI sous 0,10, et le seuil pourrait alors s'appliquer au maximum. Si une
session future faisait franchir 0,20 à la médiane ou à la dérive de la
cible ou des prédictions sans cause amont identifiable, ce serait le premier
cas réel d'usage du seuil, à comparer à la MAE effectivement mesurée sur la
session suivante.

Reproduit par `src/edumatch/models/derive.py` (`executer`), sur
`data/processed/parcoursup/variables.parquet` ; `make derive`.
