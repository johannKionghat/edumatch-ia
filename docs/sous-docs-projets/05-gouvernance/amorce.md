# Gouvernance — index du dossier

**Mise à jour : 2026-09-15.** Cette page servait d'amorce, en indexant la
matière de gouvernance produite au fil des étapes d'ingestion et de
modélisation avant que le dossier lui-même n'existe. Les sept documents sont
désormais écrits : elle devient leur index, et signale ce qui reste ouvert.

## Les documents de ce dossier

| Document | Critères servis | État |
|---|---|---|
| [`registre-sources.md`](registre-sources.md) | 1.4 | **Complet.** Six sources, licences vérifiées sur le texte, ODbL tranchée |
| [`registre-traitements.md`](registre-traitements.md) | 1.3, 1.6 | **Complet.** Huit traitements, dont sept construits ; cinq lacunes déclarées |
| [`risques.md`](risques.md) | 1.5 | **Complet et révisé.** Onze risques, réévalués après les mesures d'équité, de calibration et de dérive |
| [`plan-gouvernance.md`](plan-gouvernance.md) | 1.1, 1.2, 1.10, 1.11 | **Complet.** Classification, rôles, secrets, procédure d'audit en douze points, motifs de blocage actualisés |
| [`aipd.md`](aipd.md) | 1.7 | **Version 1.0, complète.** Plus aucun trou ; avis rendu, motivé et opposable |
| [`model-card.md`](model-card.md) | 1.9 | **Complet.** Format Mitchell, performance ventilée sur 27 sous-populations, limites déclarées |
| [`ai-act.md`](ai-act.md) | 1.8 | **Complet.** Articles 9 à 15, chaque ligne pointant vers un composant existant ou déclarant l'absence |

## Ce sur quoi ces documents s'appuient, ailleurs dans le dépôt

- `01-donnees/sources.md` — volumétries, licences et schémas, mesurés source
  par source, avec les chiffres corrigés en cours de route.
- `01-donnees/echantillons.md` et l'ADR 0008 — qualification de
  pseudonymisation et mise en balance de l'intérêt légitime.
- `04-modele/evaluation.md` — protocole temporel, baseline, calibration,
  courbe d'apprentissage.
- `04-modele/equite.md` et l'ADR 0011 — substituts du genre mesurés, dispositif
  à trois niveaux, audit sur les prédictions.
- `04-modele/explicabilite.md` — TreeSHAP, classement global, limites.
- `04-modele/ablation.md` — apport mesuré de chaque bloc de variables, et
  l'ablation de Sirene déclarée impossible.
- `06-service/journalisation-purge.md`, `ecran-conseiller.md`, `score.md` — ce
  que la conformité est devenue en code.
- ADR 0013 — décision des variables, 128 colonnes classées sans reste.
- ADR 0018 — seuil de dérive, et l'aveu de ce qu'il ne détecte pas.
- Les manifestes d'ingestion (`data/raw/*/manifeste.json`,
  `data/external/referentiels/manifeste.json`, `data/samples/manifeste.json`)
  — licence, URL, date et empreinte de chaque fichier. En cas de divergence
  avec un document, **c'est le manifeste qui fait foi**.

## Les décisions prises dans ce dossier, et pas ailleurs

1. **ODbL** — le partage à l'identique ne se déclenche qu'à la redistribution
   ou à l'usage public d'une base dérivée ; la table de correspondance sera
   publiée sous ODbL au moment où l'interface l'exposera.
2. **k-anonymat** — k = 5 au grain de restitution `département × NAF`, jamais
   au grain de calcul `commune × NAF`, mesures à l'appui. **Implémenté.**
3. **Paliers de conservation des journaux** — 12 mois en clair, 36 mois
   pseudonymisés, puis agrégats, pour concilier l'obligation de traçabilité du
   règlement sur l'IA et l'obligation de limitation du RGPD. **Implémentés et
   planifiés.**
4. **Qualification de haut risque** — annexe III, point 3 ; la dérogation de
   l'article 6 §3 est fermée d'avance, un système qui effectue un profilage de
   personnes physiques n'y ayant jamais droit.
5. **Définition d'équité privilégiée** — la calibration par groupe, déclarée
   avant la mesure, avec ce qu'elle sacrifie écrit noir sur blanc.
6. **Avis rendu le 2026-09-15** : favorable sur le principe ; **défavorable à
   la restitution, auprès de candidats réels, de l'estimation produite par le
   modèle appris**, qui échoue au test de nécessité ; favorable sous cinq
   motifs de blocage et six réserves pour le reste du dispositif. Détail et
   motivation dans `aipd.md` §8.
