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
