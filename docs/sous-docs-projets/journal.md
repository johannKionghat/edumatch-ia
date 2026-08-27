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
