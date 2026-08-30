# Gouvernance — index du dossier

**Mise à jour : 2026-08-30.** Cette page servait d'amorce, en indexant la
matière de gouvernance produite au fil des étapes d'ingestion et de
modélisation avant que le dossier lui-même n'existe. Les documents sont
désormais écrits : elle devient leur index, et signale ce qui reste ouvert.

## Les documents de ce dossier

| Document | Critères servis | État |
|---|---|---|
| [`registre-sources.md`](registre-sources.md) | 1.4 | **Complet.** Six sources, licences vérifiées sur le texte, ODbL tranchée |
| [`registre-traitements.md`](registre-traitements.md) | 1.3, 1.6 | **Complet.** Trois traitements existants, cinq spécifiés ; trois lacunes déclarées |
| [`risques.md`](risques.md) | 1.5 | **Complet.** Onze risques ; seuil de k-anonymat arrêté et chiffré |
| [`plan-gouvernance.md`](plan-gouvernance.md) | 1.1, 1.2, 1.10, 1.11 | **Complet.** Classification, rôles, secrets, procédure d'audit en douze points |
| [`aipd.md`](aipd.md) | 1.7 | **Version 0.9.** Quatre compléments identifiés, dépendant de mesures non encore produites |
| `model-card.md` | 1.9 | **À écrire** — dépend de l'audit d'équité et de la calibration |
| `ai-act.md` | 1.8 | **À écrire** — chaque article doit pointer vers un composant existant, pas vers un composant prévu |

## Ce sur quoi ces documents s'appuient, ailleurs dans le dépôt

- `01-donnees/sources.md` — volumétries, licences et schémas, mesurés source
  par source, avec les chiffres corrigés en cours de route.
- `01-donnees/echantillons.md` et l'ADR 0008 — qualification de
  pseudonymisation et mise en balance de l'intérêt légitime.
- `04-modele/equite.md` et l'ADR 0011 — substituts du genre mesurés,
  dispositif à trois niveaux.
- `ADR 0013` — décision des variables, 128 colonnes classées sans reste.
- `03-pipeline/agregats-sirene.md` — taille des cellules territoriales et
  filtre de diffusion non appliqué.
- Les manifestes d'ingestion (`data/raw/*/manifeste.json`,
  `data/external/referentiels/manifeste.json`, `data/samples/manifeste.json`)
  — licence, URL, date et empreinte de chaque fichier. En cas de divergence
  avec un document, **c'est le manifeste qui fait foi**.

## Les décisions prises dans ce dossier, et pas ailleurs

1. **ODbL** — le partage à l'identique ne se déclenche qu'à la redistribution
   ou à l'usage public d'une base dérivée ; la table de correspondance sera
   publiée sous ODbL au moment où l'interface l'exposera.
2. **k-anonymat** — k = 5 au grain de restitution `département × NAF`, jamais
   au grain de calcul `commune × NAF`, mesures à l'appui.
3. **Paliers de conservation des journaux** — 12 mois en clair, 36 mois
   pseudonymisés, puis agrégats, pour concilier traçabilité et limitation.
4. **Avis défavorable à la mise en service en l'état**, avec quatre motifs
   opposables énumérés dans l'analyse d'impact.
