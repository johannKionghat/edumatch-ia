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
