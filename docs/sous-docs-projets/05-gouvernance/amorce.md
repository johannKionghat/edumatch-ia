# Gouvernance : index du dossier

**Mise à jour : 2026-09-15.** Cette page indexe les sept documents de gouvernance et signale ce qui reste ouvert.

## Les documents de ce dossier

| Document | Critères servis | État |
|---|---|---|
| [`registre-sources.md`](registre-sources.md) | 1.4 | Complet. Six sources, licences vérifiées, ODbL tranchée |
| [`registre-traitements.md`](registre-traitements.md) | 1.3, 1.6 | Complet. Huit traitements dont sept construits, cinq lacunes déclarées |
| [`risques.md`](risques.md) | 1.5 | Complet et révisé après les mesures d'équité, de calibration et de dérive. Onze risques |
| [`plan-gouvernance.md`](plan-gouvernance.md) | 1.1, 1.2, 1.10, 1.11 | Complet. Classification, rôles, secrets, procédure d'audit en douze points |
| [`aipd.md`](aipd.md) | 1.7 | Version 1.0, complète, avis rendu et motivé |
| [`model-card.md`](model-card.md) | 1.9 | Complet. Format Mitchell, performance ventilée sur 27 sous-populations |
| [`ai-act.md`](ai-act.md) | 1.8 | Complet. Articles 9 à 15, chaque ligne pointe vers un composant existant ou déclare l'absence |

## Sur quoi ces documents s'appuient, ailleurs dans le dépôt

- `01-donnees/sources.md` : volumétries, licences et schémas mesurés source par source.
- `01-donnees/echantillons.md` et ADR 0008 : pseudonymisation, intérêt légitime.
- `04-modele/evaluation.md` : protocole temporel, baseline, calibration.
- `04-modele/equite.md` et ADR 0011 : substituts du genre, audit sur les prédictions.
- `04-modele/explicabilite.md` : TreeSHAP, classement global, limites.
- `04-modele/ablation.md` : apport de chaque bloc de variables.
- `06-service/` (`journalisation-purge.md`, `ecran-conseiller.md`, `score.md`) : la conformité telle qu'implémentée.
- ADR 0013 : décision des variables, 128 colonnes classées. ADR 0018 : seuil de dérive.
- Les manifestes d'ingestion (`data/raw/*/manifeste.json`, `data/external/referentiels/manifeste.json`, `data/samples/manifeste.json`) : licence, URL, date et empreinte de chaque fichier. En cas de divergence, le manifeste fait foi.

## Les décisions prises dans ce dossier, et pas ailleurs

1. **ODbL** : le partage à l'identique se déclenche à la redistribution ou à l'usage public d'une base dérivée. La table de correspondance sera publiée sous ODbL quand l'interface l'exposera.
2. **k-anonymat** : k = 5 au grain de restitution `département × NAF`, jamais au grain de calcul `commune × NAF`. Implémenté.
3. **Paliers de conservation des journaux** : 12 mois en clair, 36 mois pseudonymisés, puis agrégats, pour concilier traçabilité (règlement IA) et limitation (RGPD).
4. **Qualification de haut risque** : annexe III, point 3. La dérogation de l'article 6 §3 est fermée d'avance : un système de profilage de personnes physiques n'y a jamais droit.
5. **Définition d'équité privilégiée** : la calibration par groupe, déclarée avant la mesure, avec ce qu'elle sacrifie écrit noir sur blanc.
6. **Avis rendu le 2026-09-15** : favorable sur le principe, défavorable à la restitution auprès de candidats réels de l'estimation produite par le modèle (échec au test de nécessité), favorable sous cinq motifs de blocage et six réserves pour le reste. Détail dans `aipd.md` §8.
