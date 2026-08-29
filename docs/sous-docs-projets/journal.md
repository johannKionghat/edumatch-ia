# Journal de développement

Une entrée par journée de travail. Je le tiens moi-même.

Format :

```
## AAAA-MM-JJ

**Fait** : ce qui a réellement été produit
**Décisions** : ADR écrits ce jour
**Bloqué sur** : ce qui reste ouvert
**Jury** : verdict du jour si évaluation
```

---

## 2026-08-29 — E08, échantillons de test versionnés

**Fait** : E08 validée — `data/samples/` (1,2 Mo, 17 échantillons couvrant
Parcoursup, Sirene et les référentiels), généré par
`src/edumatch/ingestion/echantillons.py` (`make samples`). Critère de
validation vérifié en le provoquant : `data/raw/` et `data/external/` rendus
absents, la suite complète tourne quand même — 145 passed. Échantillonnage
systématique déterministe (empreinte identique sur deux générations). Les 8
millésimes Parcoursup couvrent la dérive de schéma 85 → 118 colonnes.

Sujet central de l'étape, plus juridique que technique : les 9 colonnes
d'identité directe sont exclues de `StockUniteLegale`, mais 282 des 500
lignes de l'échantillon sont des entrepreneurs individuels (catégorie
juridique 1000), dont 239 diffusibles ; une jointure sur le SIREN avec la
dénomination d'établissement, conservée ailleurs dans l'échantillon,
restitue leur identité à 239 sur 239. Ces échantillons sont donc
**pseudonymisés, pas anonymisés** : ils restent dans le champ du RGPD. Base
légale retenue : intérêt légitime (art. 6.1.f), mise en balance écrite. La
Licence Ouverte ne vaut jamais base légale — les deux régimes se cumulent.
Détail complet : `01-donnees/echantillons.md`, ADR 0008.

**Corrigé** : `test_echantillons_conformite.py` importait sa liste de
colonnes interdites depuis le module de génération qu'il était censé
contrôler — vider la liste dans le module aurait laissé le test vert. Devenu
une liste blanche écrite en dur dans le test, propre à chaque fichier
Sirene, qui refuse par défaut toute colonne non examinée.

**Décisions** : ADR 0008 — conserver les lignes d'entrepreneur individuel
sous intérêt légitime plutôt que de les exclure de l'échantillon.
Alternatives écartées : exclusion (détruirait la représentativité, 56,4 %
des lignes du fichier source complet), hachage du SIREN (espace forçable en
secondes), valeur de substitution fabriquée (donnée simulée, interdite).

**Bloqué sur** : rien. Prochaine étape : E09, EDA — label et distributions.

**Jury** : aucune évaluation ce jour.

## 2026-08-29 — E07, connecteur référentiels et deux corrections

**Fait** : E07 validée — `ingestion/referentiels.py`, `_referentiels_rncp.py`
et `_referentiels_communs.py` téléchargent les 4 jeux ONISEP (IDÉO, URL fixe)
et l'export RNCP du jour (résolu par interrogation du catalogue data.gouv,
puis extraction du CSV standard depuis l'archive ZIP), avec les mêmes
garanties que Parcoursup et Sirene. Suite complète du dépôt à 120 tests
passants. Téléchargement réel effectué aujourd'hui vers
`data/external/referentiels/` : 22 Mo au total. Volumétrie IDÉO conforme aux
chiffres du 26/08, à la ligne près. Export RNCP du jour : **30 484 fiches**
(7 000 actives, 23 484 inactives), 16 colonnes.

Deux corrections importantes, propagées dans `01-donnees/sources.md` et
`03-pipeline/ingestion.md` :

1. **Un chiffre faussé par l'outil de vérification lui-même.** « 36 000
   fiches RNCP, dont 6 995 actives » ne venait pas d'une évolution de la
   source, mais d'un comptage par `wc -l` — qui compte des retours à la ligne
   physiques — sur un CSV contenant des champs de texte multi-lignes entre
   guillemets. Un parseur CSV correct donne 30 484, confirmé par la somme
   7 000 + 23 484. Le compte des actives survivait par coïncidence, la
   chaîne « ACTIVE » n'apparaissant jamais dans un champ multi-ligne de cet
   export. Corrigé : `scripts/verifier_sources.sh` compte désormais avec un
   vrai parseur CSV, pour le RNCP et pour les 4 fichiers IDÉO par cohérence.
2. **Un encodage annoncé à tort.** Le RNCP était donné pour Latin-1 ; le
   fichier réel décode intégralement en UTF-8. Nuance retenue : un décodage
   Latin-1 sans erreur ne prouve rien, Latin-1 acceptant n'importe quelle
   suite d'octets — c'est pourquoi le contrôle d'encodage du connecteur est
   volontairement asymétrique, et documenté comme tel.

**Décisions** : ADR 0007 — un fichier par date de publication pour l'export
RNCP (`rncp_AAAA-MM-JJ.csv`), jamais un fichier unique écrasé : une table
dérivée du RNCP (E18) doit rester vérifiable sur l'export qui l'a produite.
Alternatives écartées : fichier unique écrasé, retéléchargement systématique
sans persistance. Seuil de bascule : une politique de rétention à écrire si
la tâche est un jour programmée à cadence quotidienne sur une longue durée.

**Bloqué sur** : rien. Prochaine étape : E08, échantillons versionnés.

**Jury** : aucune évaluation ce jour.

## 2026-08-28 — E06, connecteur Sirene et correction du chiffre d'établissements

**Fait** : E06 validée — `ingestion/sirene.py` résout les 4 fichiers stock
configurés en interrogeant le catalogue data.gouv à l'exécution (aucune URL de
fichier codée en dur : les liens changent chaque mois, l'horodatage de
publication fait partie du chemin), puis les télécharge avec les mêmes
garanties que Parcoursup — idempotence par empreinte, écriture atomique,
manifeste — sur les primitives partagées de `_flux.py`, enrichies d'un rappel
de progression pour les transferts de plusieurs Go. Les deux connecteurs
partagent désormais un vocabulaire d'erreur transitoire/définitif
(`ErreurTransitoire`, `ErreurDefinitive` dans `_flux.py`), pour que le futur
DAG retente ou alerte sans connaître la classe interne du connecteur en cause
— Parcoursup a été rétrofité dans le même commit. Une vérification de la
taille annoncée par le catalogue contre la taille réellement écrite journalise
un avertissement au-delà d'un écart de 5 %, sans jamais bloquer la chaîne.
Suite complète du dépôt à 80 tests passants. Résolution rejouée aujourd'hui
contre le catalogue réel :
les 4 URL obtenues correspondent exactement à celles du manifeste enregistré
lors du téléchargement effectif, stock du 01/08/2026.

Correction de chiffre : « 36 millions d'établissements, 25 millions d'unités
légales », retenu depuis le début du projet, n'avait jamais été recalculé
depuis sa première mesure. Une fois les 4 fichiers réellement téléchargés, la
métadonnée Parquet donne **43 896 818 établissements, 29 922 486 unités
légales** — le chiffre retenu était sous-estimé. Corrigé dans
`01-donnees/sources.md`, `03-pipeline/ingestion.md`, l'ADR 0002,
`ARCHITECTURE_EduMatch.md` et le dossier de certification (`_build_dossier.py`,
régénéré). La correction renforce l'argument qui écarte Databricks au profit
de PySpark local : le volume est plus élevé que ce qui était annoncé, pas
moins. Nuance ajoutée : les filtres du projet ne retiennent que 2 436 624
lignes sur 43 896 818 (5,6 %), mais c'est la lecture du fichier entier, pas le
résultat filtré, qui dimensionne le traitement — et cette lecture (2 colonnes
sur 54) prend 35,4 secondes sur un poste ordinaire, ce qui justifie un Spark
local plutôt qu'un service managé pour le job réel (E17).

**Décisions** : ADR 0005 — résolution dynamique de l'URL Sirene contre une URL
en configuration. Coût assumé : une dépendance au catalogue au moment de
l'exécution, à traiter comme une panne transitoire dans le futur DAG, pas
comme une erreur de configuration. ADR 0006 — vocabulaire commun d'erreur
transitoire/définitif entre les deux connecteurs.

**Bloqué sur** : rien. Prochaine étape : E07, connecteur référentiels.

**Jury** : aucune évaluation ce jour.

## 2026-08-28 — E05, connecteur Parcoursup

**Fait** : E05 validée — `ingestion/parcoursup.py` télécharge les 8 millésimes
déclarés en configuration, avec idempotence par empreinte SHA-256 et écriture
atomique. Les primitives communes (flux HTTP, empreinte, écriture atomique,
manifeste) sont extraites dans `_flux.py`, avant que Sirene et les
référentiels ne les dupliquent. Suite complète du dépôt à 44 tests passants.
Volumétrie et schéma mesurés directement sur les 8 CSV posés sur disque :
104 274 formation-années au total, dérive de schéma confirmée (85 colonnes en
2018, jusqu'à 118 à partir de 2021), idempotence rejouée sur l'API réelle (les
8 millésimes renvoient `telecharge=False` au second passage).

Correction de chiffre : le poids des 8 CSV Parcoursup, jamais mesuré (l'export
de l'API ne porte pas de `Content-Length`), était estimé « ~100 Mo » dans la
documentation et mes notes de cadrage. Mesure directe une fois les fichiers
téléchargés : **82 Mo** (`du -sh data/raw/parcoursup/`). Corrigé dans
`01-donnees/sources.md`, `03-pipeline/ingestion.md`, l'ADR 0002 et le dossier
de certification (`_build_dossier.py`, régénéré). Le raisonnement qui appuie
le choix de ne pas distribuer la chaîne de décision (Polars/dbt plutôt que
Spark) s'en trouve renforcé, pas affaibli.

**Décisions** : ADR 0004 — extraction des primitives partagées avant la
deuxième occurrence plutôt qu'après trois duplications ; mise en quarantaine
d'un manifeste corrompu plutôt qu'écrasement silencieux.

**Corrigé** : un signalement de revue de code annonçait une perte d'entrées du
manifeste en fonctionnement normal. Reproduit avant correction : le risque
n'existait qu'en cas de manifeste déjà corrompu, pas en marche normale — déjà
couvert par la décision de quarantaine. Aucun correctif supplémentaire
nécessaire.

**Bloqué sur** : rien. Prochaine étape : E06, connecteur Sirene.

**Jury** : aucune évaluation ce jour.

## 2026-08-28 — E04, configuration centralisée

Écrit `src/edumatch/config.py` : modèles typés, validation au démarrage,
précédence `base.yaml` < `{env}.yaml` < variables d'environnement. 25 tests,
répartis en trois fichiers thématiques.

Trois défauts trouvés en validation et corrigés : une racine de données vide
qui se résolvait silencieusement en répertoire courant ; un objet de
configuration qui pouvait annoncer un environnement différent de son contenu ;
un canal `.env` jamais lu. Le test qui garantit l'absence de valeur en dur a été
réécrit en analyse syntaxique après qu'une mutation a montré qu'un seuil écrit
`4 / 5` lui échappait.

Écrit l'ADR 0003 (configuration centralisée) et l'ADR 0002 (refus de Databricks).
Corrigé la volumétrie Sirene et la licence des référentiels dans le dossier de
certification : l'ONISEP est sous ODbL, pas sous Licence Ouverte.

## 2026-08-26

**Fait** : E03 validée — vérification des 4 sources (Parcoursup, Sirene,
ONISEP, RNCP) par API de métadonnées, sans téléchargement des gros fichiers.
Note `01-donnees/sources.md` et script `scripts/verifier_sources.sh` produits.
Référentiels ONISEP et RNCP documentés pour la première fois. Écart détecté
sur le chiffre Sirene « 11,2 Go » (non reproductible) — corrigé vers 6,44 Go
(ZIP, stock du 01/08/2026), daté, propagé partout où le chiffre figurait.
Licence ONISEP corrigée en ODbL (elle était donnée pour Licence Ouverte).

**Décisions** : aucun ADR. Correction de chiffre arbitrée par mes soins,
actée dans mes notes de cadrage.

**Bloqué sur** : rien. Prochaine étape : E04, configuration centralisée
(`config.py`, Pydantic Settings).

**Jury** : aucune évaluation ce jour.
