# Contrôles qualité

**Étape** : E14 · **Bloc servi** : 3, critère 3.5 (contrôle qualité : détection,
validation, blocage) · **Code** : `src/edumatch/quality/`

## Ce qui existe

Un module par source — `parcoursup.py`, `sirene.py`, `referentiels.py` —
orchestrés par `run.py` (`python -m edumatch.quality.run`, cible `make
quality`). Le vocabulaire commun (anomalie, gravité, rapport) vit dans
`_diagnostic.py` ; le contrôle de fraîcheur, générique aux trois sources,
dans `_fraicheur.py`.

Quatre familles de contrôle, présentes sur chaque source dans la mesure où
elle s'y prête :

| Famille | Ce qu'elle vérifie |
|---|---|
| Schéma | Les colonnes attendues sont présentes, avec le type attendu |
| Complétude | Le taux de valeurs renseignées dépasse le seuil configuré, colonne par colonne, hors colonnes dont l'absence a une raison documentée |
| Cohérence | Des relations internes entre colonnes tiennent (somme, ratio, encadrement) |
| Fraîcheur | La date portée par le manifeste du connecteur n'est ni absente, ni illisible, ni dans le futur, ni trop ancienne |

Les seuils (`seuil_completude`, `age_max_jours_avertissement`, tolérance de
reconstruction des pourcentages) sont dans `configs/base.yaml`, section
`qualite`, jamais en dur dans le code.

## La frontière entre bloquer et avertir

C'est le cœur de cette étape. Deux gravités seulement
(`Gravite.BLOQUANT`, `Gravite.AVERTISSEMENT`) : un troisième niveau serait
le début d'une échelle qu'on ne veut pas.

- **Bloquant** : la donnée ne doit pas atteindre la couche suivante en
  l'état. `RapportControle.lever_si_bloquant()` interrompt la chaîne en
  levant `ErreurQualiteBloquante`, rangée du côté définitif du vocabulaire
  commun d'erreurs partagé avec les connecteurs
  (`ingestion._flux.ErreurDefinitive`) : retenter ne change rien, c'est la
  donnée elle-même qui viole son contrat.
- **Avertissement** : la donnée reste exploitable, mais un humain devrait
  le savoir. Journalisé, jamais silencieux, mais ne bloque rien.

Un contrôle qui journalise sans jamais bloquer laisserait une donnée
corrompue atteindre dbt puis le modèle. Un contrôle qui bloque sur tout est
désactivé en une semaine. L'exemple qui a guidé chaque arbitrage de cette
étape est celui de la date de création dans Sirene :

- **10 613 établissements** portent une date de création dans les cinq ans
  à venir, des immatriculations anticipées, plausibles administrativement.
  Avertissement.
- **5 établissements** portent une date de création en 2054, 2116, 2202,
  2924 et 5015, des fautes de frappe dans le répertoire officiel, vérifiées
  une à une. Bloquant.

Un contrôle naïf « date supérieure à aujourd'hui » aurait bloqué sur 10 618
lignes, dont 10 613 saines, et aurait été désactivé à la première exécution
réelle. Le seuil retenu, cinq ans, sépare les deux régimes.

## Trois hypothèses de contrôle écrites, puis infirmées par la mesure

Avant d'être figé, chaque contrôle de cohérence a été confronté aux huit
millésimes réels. Trois hypothèses de départ se sont révélées fausses :

1. **Le ratio admission / vœux serait borné à 1.** Faux : il compte des
   propositions émises, réémises après désistement (ADR 0009), et monte
   jusqu'à 26 sur la session 2025. Le contrôle ne borne jamais ce ratio, il
   ne fait que signaler une valeur négative.
2. **Un admis aurait nécessairement formulé un vœu dans sa cellule.** Faux :
   482 cellules en 2025 présentent un numérateur d'admission positif pour
   un dénominateur de vœux nul. Ni l'un ni l'autre cas n'est bloqué.
3. **`acc_tot` égalerait la somme des quatre types de bac** (`acc_bg +
   acc_bt + acc_bp + acc_at`). Vérifié faux sur cinq des huit sessions : le
   contrôle a été rétrogradé en avertissement plutôt que retiré, la
   relation restant vraie la plupart du temps.

Écrire un contrôle sans le confronter aux données réelles produit un
contrôle faux, dans un sens ou dans l'autre : trop laxiste (le ratio borné
à 1 aurait laissé passer un vrai défaut sans jamais se déclencher sur ce
qui est en réalité normal), ou trop strict (bloquer sur les 482 cellules
aurait arrêté la chaîne sur un fait structurel du fichier source).

## La démonstration du blocage

Le critère de validation de l'étape n'est pas affirmé, il est démontré :

```bash
PYTHONPATH=src python -m edumatch.quality.run
echo $?
```

Sur les données réelles, la commande sort en **code 1** : les 5 dates
impossibles de Sirene constituent une anomalie bloquante, et
`ErreurQualiteBloquante` interrompt la chaîne avant qu'elle n'atteigne dbt
(E15). Une tâche d'orchestration Airflow (E33) échouerait de la même façon.

Sur Parcoursup et les référentiels, la même commande ne relève aucune
anomalie bloquante, seuls des avertissements (dont les 10 613
immatriculations anticipées).

## Limite assumée

Il n'existe pas de contrôle de schéma dédié pour
`StockEtablissementHistorique`, `StockUniteLegale` et
`StockUniteLegaleHistorique` : seul `StockEtablissement` porte les 9
colonnes utiles au projet, et aucun traitement du pipeline ne lit encore
les trois autres fichiers (voir E18). Ils sont soumis au seul contrôle de
fraîcheur, sur la même cadence de republication mensuelle. Reporté dans la
feuille de route.

---
*Dernière mise à jour : 2026-08-29 · commit `fb86e87`*
