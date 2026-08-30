# Agrégat Sirene commune × NAF

**Étape** : E17 · **Blocs servis** : 2, critère 2.4 (structures adaptées au
volume) ; 3, critère 3.2 (ELT entre sources hétérogènes) · **Code** :
`src/edumatch/spark/definitions.py`, `sirene_agregats_polars.py`,
`sirene_agregats.py`, `run_sirene_agregats.py` · **Décision** : ADR 0016

Cette page couvre l'étape qui réduit le stock Sirene, source déjà ingérée
(`ingestion.md`) et déjà contrôlée (`qualite.md`), à un agrégat territorial
exploitable. Elle ne fait pas encore partie de la couche gold : `dim_territoire`
et `fait_admission` (`02-architecture/modele-etoile.md`) ne portent aujourd'hui
que Parcoursup ; le raccordement de cet agrégat au terme « débouchés » du score
est une étape ultérieure du plan d'exécution du projet.

## D'où vient la donnée, et pourquoi ces 9 colonnes

La source est `StockEtablissement.parquet` (E06), le stock des établissements
du répertoire Sirene : **43 896 818 lignes, 54 colonnes, 355 row groups,
2,20 Go**. Neuf colonnes sur les 54 sont lues, exactement la même liste que
celle déjà arrêtée par le contrôle qualité (E14,
`edumatch.quality.sirene.COLONNES_UTILES`) : `siret`,
`activitePrincipaleEtablissement`, `nomenclatureActivitePrincipaleEtablissement`,
`activitePrincipaleNAF25Etablissement`, `codeCommuneEtablissement`,
`trancheEffectifsEtablissement`, `etatAdministratifEtablissement`,
`caractereEmployeurEtablissement`, `dateCreationEtablissement`. Réutiliser
cette même liste plutôt que d'en définir une seconde évite qu'un contrôle
qualité et l'agrégat qu'il valide finissent par regarder des colonnes
différentes sans que rien ne le signale.

## Le grain

**Une ligne = un couple `(codeCommuneEtablissement, activitePrincipaleEtablissement)`**
— une commune et un code NAF (nomenclature NAFRev2, celle qui couvre déjà
2 436 623 des 2 436 624 établissements actifs-employeurs du fichier complet ;
le futur code NAF 2025 n'est pas encore utilisé comme clé, voir plus bas).
L'unicité du grain est vérifiée à l'exécution, sur l'agrégat produit comme sur
tout échantillon de test.

Chaque ligne porte, pour ce couple commune × NAF :

| Colonne | Contenu |
|---|---|
| `nb_actifs_employeurs` | établissements actifs et employeurs |
| `nb_fermes_employeurs` | établissements fermés qui **étaient** employeurs |
| `nb_tranche_{palier}` | ventilation des actifs-employeurs sur 6 paliers d'effectifs |
| `nb_naf25_renseigne` | actifs-employeurs dont le code NAF 2025 est déjà renseigné |
| `age_moyen_annees` | ancienneté moyenne des actifs-employeurs, par rapport à `date_reference` |
| `nb_crees_moins_3ans` | actifs-employeurs créés à moins de 3 ans de `date_reference` |
| `date_reference` | date de publication du stock Sirene utilisée pour les deux colonnes d'ancienneté — jamais la date d'exécution, pour qu'un rejeu du même stock produise le même résultat |

## Les filtres appliqués, et l'écart assumé

Deux filtres sont pilotés par `configs/base.yaml`
(`donnees.sirene.filtres`) :

- `etat_administratif: A` restreint le compteur principal aux établissements
  actifs. **Les fermetures ne sont pas exclues du fichier pour autant** :
  `nb_fermes_employeurs` compte, à côté, les établissements fermés qui
  étaient employeurs — un secteur qui perd des employeurs a une dynamique
  différente d'un secteur qui en gagne, même à effectif actif identique.
  Exclure les cessations biaiserait la mesure de « débouchés » vers les seuls
  territoires en croissance.
- `caractere_employeur: true` restreint aux établissements employeurs — un
  établissement qui n'emploie personne n'est pas un débouché.

Un troisième filtre, `diffusible: true`, est déclaré dans la même section de
configuration mais **n'est pas appliqué** à ce stade. L'appliquer demanderait
de lire une dixième colonne (`statutDiffusionEtablissement`), absente des 9
déjà arrêtées à l'E06 et reprises par le contrôle qualité. Mesuré sur le
fichier complet : 20 501 établissements actifs-employeurs sur 2 436 624
(0,84 %) portent un statut non diffusible, et seulement 13 d'entre eux ont
par ailleurs une commune manquante — le filtre n'est donc pas redondant avec
l'exclusion des communes nulles, il retirerait bien 0,84 % de lignes
supplémentaires s'il était appliqué. C'est un écart chiffré et assumé, pas
une omission silencieuse : une décision à revoir explicitement si la
précision au niveau commune devient sensible à ce seuil, ou si une dixième
colonne est de toute façon ajoutée pour une autre raison.

## Les chiffres de sortie

| Mesure | Valeur |
|---|---:|
| Lignes (cellules commune × NAF) | 1 929 179 |
| Colonnes | 14 |
| Taille sur disque | 12 618 239 o (12,6 Mo) |
| Communes distinctes | 35 664 |
| Codes NAF distincts | 1 743 |
| Actifs-employeurs agrégés | 2 423 308 |
| Fermés-employeurs agrégés | 4 897 540 |

Réduction de 2,20 Go à 12,6 Mo — un facteur d'environ 175.

**Écart avec les 2 436 624 actifs-employeurs du fichier complet** : 13 316
lignes n'entrent pas dans l'agrégat, soit un sur 183. Vérifié plutôt que
supposé : les 13 316 portent toutes un `codePaysEtrangerEtablissement`
renseigné — ce sont des établissements domiciliés à l'étranger, hors du
grain territorial de ce projet, sans commune française à leur associer.

**Couverture NAF 2025** : `nb_naf25_renseigne` totalise 2 423 294 sur
2 423 308 actifs-employeurs agrégés, soit **100,0 %** (14 lignes seulement
sans NAF 2025). La bascule officielle du répertoire vers la NAF 2025 est
prévue début 2027 ; les deux nomenclatures coexistent aujourd'hui dans le
fichier, et cette colonne mesure sur quelle proportion de chaque cellule
l'étape suivante (E18, réconciliation NAF ↔ ROME ↔ formation) pourra
s'appuyer sans avoir à le redécouvrir.

## La preuve du filtrage à la lecture (predicate pushdown)

Le moteur Spark expose son plan physique par `df.explain(True)` : il porte un
`ReadSchema` limité aux 9 colonnes utiles — jamais les 54 du fichier — et des
`PushedFilters` qui listent les conditions déjà traduites en filtres Parquet
(`IsNotNull`, `EqualTo`, `In`). Spark ne décompresse jamais les groupes de
lignes qui ne peuvent statistiquement pas satisfaire ces filtres, avant même
de les charger en mémoire. Un test dédié
(`test_explain_montre_projection_et_pushdown`) vérifie que le plan contient
les 9 colonnes utiles et ne contient pas `statutDiffusionEtablissement`,
colonne jamais lue.

## Deux moteurs, un seul comportement

Deux implémentations existent, sélectionnées par `execution.moteur_volume`
(déjà présente dans `configs/*.yaml`) : Polars en mode `local` (dev,
staging), Spark en mode `cluster` (prod). Les deux importent leurs règles
métier — grain, colonnes, filtres, table de correspondance des tranches
d'effectifs — d'un seul module (`definitions.py`), pour qu'une correction
appliquée à un moteur ne puisse pas diverger silencieusement de l'autre. Un
test compare les deux sorties ligne à ligne sur le même échantillon.

L'arbitrage entre les deux moteurs — la mesure comparative (Polars 18,2 s
contre Spark 87,0 s sur le fichier complet), pourquoi Spark existe malgré
tout, et le seuil qui ferait changer d'avis — est écrit dans l'ADR 0016. Je
ne le répète pas ici.

## Section dédiée — la taille des cellules

Mesurée sur l'agrégat produit :

| Établissements actifs-employeurs par cellule | Nombre de cellules | Part |
|---|---:|---:|
| Au moins 1 | 886 688 | 100,0 % |
| Exactement 1 | 584 489 | 65,9 % |
| Exactement 2 | 135 162 | 15,2 % |
| Exactement 3 | 54 808 | 6,2 % |

**Deux conséquences, énoncées franchement, ni corrigées ni tranchées ici :**

- **Utilité.** Une cellule à un seul établissement n'est pas un agrégat, c'est
  une observation isolée. Le terme « débouchés » du score de matching
  (E28) ne peut pas s'appuyer directement sur une cellule de taille 1 sans
  fausser sa lecture statistique : il devra travailler à une maille plus
  grossière que `(commune, NAF)` — un territoire plus large, un niveau de
  NAF moins fin — ou lisser ces cellules avec leurs voisines. La question
  n'est pas résolue par cette étape.
- **Conformité.** Une cellule à un seul établissement identifie cet
  établissement de façon quasi directe — un couple (commune, secteur
  d'activité) à effectif 1 désigne concrètement une entreprise repérable.
  Or ces données sont **pseudonymisées, pas anonymisées** (voir l'ADR 0008,
  qui pose le même constat sur un autre échantillon Sirene) : le RGPD
  s'applique toujours. À cela s'ajoute que les 20 501 établissements non
  diffusibles ne sont pas filtrés à cette étape (voir plus haut) — une
  partie des cellules à effectif 1 ou 2 pourrait donc porter un établissement
  qui n'a pas vocation à être individuellement identifiable.

Cette décision relève à la fois de la protection des données et de l'étape
du score de matching : elle est **ouverte**, reportée dans
`reste-a-faire.md`, et n'est pas tranchée par ce document.

## Reproduire

```bash
make sirene-agregats
```

Exécute `python -m edumatch.spark.run_sirene_agregats`. Résout la source
(`data/raw/sirene/StockEtablissement.parquet`), la date de référence de
l'ancienneté depuis le manifeste écrit par l'ingestion (E06 — jamais la date
du jour), le moteur depuis `execution.moteur_volume`, puis écrit
`data/processed/sirene/agregats_commune_naf.parquet`. Une source absente
lève une erreur explicite qui nomme la commande à exécuter d'abord
(`python -m edumatch.ingestion.sirene`) plutôt que d'échouer obscurément plus
loin.

Suite de tests complète du dépôt : `python -m pytest -q` → **278 tests, 278
succès** (260 avant cette étape).

## Ce que le pipeline garantit, à ce stade

| Propriété | Comment |
|---|---|
| Idempotence | Écriture atomique par la même primitive que le reste du projet ; réécrire deux fois le même agrégat produit un fichier identique, jamais de `.part` orphelin |
| Reprise correcte après erreur amont | Une source Sirene absente ou un manifeste sans date de publication lève une erreur explicite avant tout calcul |
| Reproductibilité temporelle | L'ancienneté est toujours calculée par rapport à la date de publication du stock, jamais `date.today()` |
| Deux moteurs, un seul résultat | Vérifié par un test qui compare Spark et Polars sur le même échantillon |

## Limites assumées

- **Pas encore raccordé à la couche gold.** Cet agrégat vit dans
  `data/processed/sirene/`, hors du modèle en étoile Parcoursup
  (`02-architecture/modele-etoile.md`). Le rattacher au terme « débouchés »
  du score est une étape ultérieure.
- **`filtres.diffusible` non appliqué** — écart chiffré ci-dessus, pas une
  omission silencieuse.
- **La taille des cellules n'est pas traitée** — question ouverte ci-dessus,
  reportée dans `reste-a-faire.md`.
- **Sur ce poste de développement (Windows)**, l'écrivain Parquet natif de
  Spark échoue faute de `winutils.exe`. Le résultat, déjà réduit à 12,6 Mo,
  est ramené au pilote puis écrit par la primitive atomique du projet — un
  choix cohérent avec le reste du dépôt, pas un contournement propre à ce
  seul problème (voir l'ADR 0016).
- **Pas d'orchestration Airflow à ce stade** : `make sirene-agregats`
  s'exécute manuellement. Le DAG (E33) reprendra ce même point d'entrée sans
  changer sa logique.

---
*Étape E17 · dernière mise à jour : 2026-08-30.*
