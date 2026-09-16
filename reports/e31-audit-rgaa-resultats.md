# Résultats de l'audit RGAA — écran conseiller (E31, critère 4.18)

**Date de l'audit** : 2026-09-16
**Commit audité** : `60ec389` (`60ec3894b80f8b15f93be9e554a5c35c0d27d2e9`)
**Environnement** : API lancée en local par `uvicorn edumatch.api.main:app`, port 8010
(le port 8000 par défaut de `make api` était déjà occupé par un conteneur `fastapi_app`
d'un autre projet sur ce poste — non modifié, non arrêté). Authentification HTTP Basic
de test : identifiant/mot de passe fixés uniquement en variables d'environnement du
processus (`CONSEILLER_IDENTIFIANT`, `CONSEILLER_MOT_DE_PASSE`), jamais écrits dans un
fichier.

**Outils et versions** :
- Google Chrome / Chrome headless : `HeadlessChrome/153.0.0.0` (build résident du poste)
- Lighthouse : `13.4.1` (catégorie accessibilité uniquement)
- `@axe-core/cli` / `axe-core` : `4.13.0`, piloté par un script Puppeteer (`puppeteer-core`,
  déjà présent en dépendance de Lighthouse) pour auditer les trois états réels de l'écran
- Scripts d'audit et JSON bruts : `reports/e31-audit-rgaa/`

## Score Lighthouse (accessibilité)

**Score : 100 / 100**, sur l'écran de recherche vide (`http://127.0.0.1:8010/`, après
authentification HTTP Basic passée dans l'URL pour Lighthouse). Aucun audit binaire en
échec (`color-contrast`, `heading-order`, `html-has-lang`, `label`, `link-name` : tous à
1). Rapport brut : `reports/e31-audit-rgaa/lighthouse-ecran-vide.report.json` et
`.report.html`.

**Limite assumée** : Lighthouse audite une page chargée, pas un parcours scripté — je ne
l'ai fait tourner que sur l'écran vide. Les états « résultats affichés » et « panneau
d'explication ouvert » sont couverts par axe-core (voir ci-dessous), pas par Lighthouse.

## Violations axe-core, par gravité

**0 violation, sur les trois états audités.** axe-core ne fait remonter que la
gravité des violations qu'il détecte ; il n'y en a aucune à classer.

| État de l'écran | Violations | Incomplete (à vérifier manuellement) | Règles passées |
|---|---|---|---|
| Écran vide, avant recherche | 0 | 0 | 21 |
| Résultats affichés (profil bac général, non boursier, département 05) | 0 | 0 | 26 |
| Panneau « Comprendre cette recommandation » ouvert | 0 | 0 | 26 |

Rapports bruts : `reports/e31-audit-rgaa/axe-ecran-vide.json`,
`axe-ecran-resultats.json`, `axe-ecran-explication.json`.

**Ce que ça ne prouve pas** : axe-core et Lighthouse détectent des défauts de balisage
et de structure automatiquement identifiables (~30-40 % des critères RGAA selon les
éditeurs eux-mêmes). Un score parfait aux deux outils ne dispense pas de la vérification
manuelle ci-dessous — c'est exactement ce que la procédure documente, et exactement
pourquoi deux non-conformités réelles ont été trouvées par le parcours manuel alors que
les outils automatisés ne les voient pas (un lien d'évitement qui ne pose pas le focus,
et un message d'erreur non informatif sont tous deux invisibles à un audit de structure
DOM statique).

## Non-conformités constatées — à corriger ou à assumer, décision au demandeur

### 1. Le lien d'évitement ne déplace pas le focus dans `<main>` — MAJEUR

**Constat** : `Tab` puis `Entrée` sur « Aller au contenu principal » fait défiler la page
jusqu'à `<main id="contenu-principal">`, mais ne pose pas le focus clavier dessus.
`document.activeElement` retombe sur `<body>` : un `Tab` suivant repart du tout début du
document (les liens de navigation), pas du contenu principal. Vérifié par script
Puppeteer (`reports/e31-audit-rgaa/clavier-zoom-check.mjs`, section « clavier »).

**Cause** : `<main id="contenu-principal">` (`src/edumatch/api/static/index.html`) n'a
pas d'attribut `tabindex`. Un élément qui n'est ni nativement focusable (lien, bouton,
champ) ni doté de `tabindex` ne peut jamais recevoir le focus par script ni par ancre
`href="#…"` — seul le défilement visuel se produit.

**Critère concerné** : RGAA 12.7 (le lien d'évitement doit remplir sa fonction), WCAG
2.4.1 (Bypass Blocks). C'est exactement le point 2 de la section 1 de la procédure
(« Entrée sur le lien d'évitement déplace le focus dans `<main>` »).

**Correction proposée** (non appliquée — décision au demandeur) : ajouter
`tabindex="-1"` à `<main id="contenu-principal">`, ce qui le rend focusable par
programme sans l'ajouter à l'ordre de tabulation normal.

### 2. Message d'erreur illisible sur une erreur de validation 422 — MINEUR

**Constat** : soumettre le formulaire avec un département mal formé (`7`, qui ne
respecte pas le motif `^(2[AB]|[0-9]{2,3})$`) affiche dans la zone de message :
« Erreur 422. » — sans aucune indication du champ en cause ni de la correction
attendue. Reproduit par requête directe :

```
curl -s -X POST http://127.0.0.1:8010/matching -H "Content-Type: application/json" \
  -d '{"type_bac":"bg","boursier":false,"departement":"7"}'
→ {"detail":[{"type":"string_pattern_mismatch","loc":["body","departement"],
    "msg":"String should match pattern '^(2[AB]|[0-9]{2,3})$'", ...}]}
```

**Cause** : `lireDetailErreur` (`src/edumatch/api/static/app.js`) ne traite que le cas
où `corps.detail` est une chaîne. FastAPI/Pydantic v2 renvoie, sur une erreur de
validation 422, un **tableau** d'objets d'erreur (`type`, `loc`, `msg`) — le
`typeof corps.detail === "string"` échoue, et le code retombe sur le message générique
`Erreur ${status}.`, qui ne transmet aucune information utile au conseiller.

**Ce qui est déjà correct, à ne pas confondre avec le point ci-dessus** : aucune trace
technique (chemin de fichier, nom de module Python) n'est exposée — la partie « pas de
fuite technique » du point 1 de la section 5 de la procédure est respectée. C'est la
lisibilité qui fait défaut, pas la sécurité.

**Correction proposée** (non appliquée) : dans `lireDetailErreur`, gérer le cas
`Array.isArray(corps.detail)` en construisant un message à partir de `loc` et `msg` de
chaque erreur (ex. « Département : le format ne correspond pas à celui attendu »).

### Ce qui est conforme, vérifié en direct dans le navigateur

- Premier `Tab` : active le lien d'évitement, contour visible (`outline: 3px solid
  rgb(209, 123, 0)`).
- Ordre de tabulation du formulaire de recherche : identifiant conseiller → type de bac
  → boursier → type de formation → domaine → département → nombre de recommandations →
  bouton Rechercher — exactement l'ordre visuel attendu par la procédure.
- Tous les éléments interactifs réels de cette séquence (11 sur 11, hors `<body>` atteint
  après le dernier élément, qui n'a pas vocation à porter un contour) affichent un
  contour visible au focus.
- `Shift+Tab` fonctionne : aucun piège au clavier constaté sur le parcours testé.
- Après soumission d'un formulaire en erreur, le focus reste sur le bouton « Rechercher »
  — pas de perte de focus.
- Écarter une recommandation sans motif : message d'erreur explicite (« Un écartement
  doit être motivé (article 14) : indiquez le motif. ») **et** focus déplacé
  automatiquement vers le champ de motif (`textarea`) — conforme au point 9 de la
  section 1 et au point 2 de la section 5.
- Zoom (approximé par réduction du viewport CSS à 640 px, moitié de 1280 px — voir
  limite ci-dessous) et fenêtre à 320 px de large : aucun débordement horizontal
  constaté (`scrollWidth === clientWidth` dans les deux cas).
- Statuts « Mesuré » / « Indisponible » : le texte du badge reste identique et présent
  sous émulation Chrome de quatre déficiences de vision (deutéranopie, protanopie,
  tritanopie, achromatopsie) — le statut n'est jamais porté par la couleur seule.
- CSP stricte (`default-src 'self'`) confirmée en conditions réelles : l'injection d'un
  script tiers (axe-core) dans la page est bloquée par défaut et n'a été rendue possible
  pour l'audit qu'en désactivant explicitement la CSP côté client Puppeteer
  (`setBypassCSP`) — l'écran lui-même ne l'affaiblit jamais.

## Déroulé de la procédure, point par point

### 1. Navigation clavier seule

| Point | Statut | Preuve / motif |
|---|---|---|
| `Tab` active d'abord le lien d'évitement, visible dès le premier `Tab` | **Conforme** | Script Puppeteer, `premier_tab` : `<a class="lien-evitement">`, contour visible |
| `Entrée` sur le lien d'évitement déplace le focus dans `<main>` | **Non conforme** | Voir non-conformité n° 1 — `document.activeElement` reste `<body>` |
| Ordre de tabulation suit l'ordre visuel du formulaire | **Conforme** | Séquence observée identique à l'ordre attendu |
| Contour visible sur chaque élément focusé (fond blanc et boutons bleus) | **Conforme sur fond blanc, vérifié** ; **non vérifié sur fond bleu** | Aucun bouton à fond bleu n'existe dans l'état actuel de l'écran (les boutons observés sont à fond neutre) — rien à vérifier sur ce point précis dans l'état actuel du DOM |
| Focus non perdu après soumission | **Conforme** | Focus reste sur le bouton « Rechercher » après une erreur 422 |
| Ordre sur une carte de recommandation (Comprendre, radios, motif, enregistrer) | **Conforme** | Vérifié par clic direct sur chaque contrôle (pas par tabulation exhaustive de la carte, voir limite ci-dessous) |
| « Comprendre » déplace le focus dans le panneau, sur son titre | **Partiellement vérifié** | Le script confirme que la section `#explication` reçoit `hidden=false` et que `section.focus()` est appelé (lu dans `app.js`) ; le focus effectif sur le titre précis n'a pas été revérifié élément par élément — voir limite |
| « Fermer » referme et renvoie le focus au bouton « Comprendre » | **Non vérifié** | Non testé dans ce passage — `app.js` l'implémente (`dernierBoutonExplicationActif.focus()`), lecture de code seulement, pas de vérification en direct |
| Écarter sans motif : focus vers le champ, message explicite | **Conforme** | Vérifié en direct : message et focus corrects |
| Aucun piège au clavier | **Conforme sur le parcours testé** | `Shift+Tab` fonctionne ; aucun blocage constaté sur le formulaire de recherche et le formulaire de décision |

### 2. Lecteur d'écran (NVDA ou VoiceOver)

**Non fait, en totalité.** Aucun point de cette section n'a été vérifié : je n'ai pas de
lecteur d'écran disponible dans cet environnement, et je ne simule pas son comportement
— le déclarer conforme sans l'avoir entendu serait une affirmation non vérifiée, exactement
ce qui est interdit. Les huit points de la section 2 restent à dérouler avec NVDA ou
VoiceOver, par une personne humaine, avant de clore ce critère.

### 3. Zoom et redimensionnement

| Point | Statut | Preuve / motif |
|---|---|---|
| Zoom 200 %, aucun texte tronqué ni chevauchement, pas de défilement horizontal | **Conforme, avec réserve méthodologique** | Approximé par un viewport CSS réduit à 640 px (moitié de 1280 px) plutôt qu'un vrai zoom du moteur de rendu (qui agrandit la police sans changer le viewport CSS) — un zoom réel `Ctrl +` dans un navigateur non piloté n'a pas été effectué |
| Fenêtre à 320 px : formulaire et cartes restent utilisables | **Conforme** | `scrollWidth === clientWidth === 320`, aucun débordement horizontal mesuré |

### 4. Perception des couleurs

| Point | Statut | Preuve / motif |
|---|---|---|
| Statuts « Mesuré »/« Indisponible » compréhensibles en simulation de daltonisme | **Conforme** | Texte du badge identique sous 4 émulations Chrome (deutéranopie, protanopie, tritanopie, achromatopsie) |
| Vérification au pixel des couleurs réellement rendues vs `style.css` | **Non fait** | Vérification visuelle au pixel près non réalisée — hors de portée d'un script, nécessite une inspection humaine de l'écran rendu |

### 5. Formulaires et erreurs

| Point | Statut | Preuve / motif |
|---|---|---|
| Erreur 422 (département mal formé) lisible, sans trace technique | **Non conforme sur la lisibilité, conforme sur l'absence de trace technique** | Voir non-conformité n° 2 : message « Erreur 422. », aucune trace de fichier ou de module |
| Écartement sans motif : message relié au champ concerné | **Conforme** | Message affiché dans `role="status"` du formulaire de décision (pas une bannière générique en haut de page), focus posé sur le champ |

## Ce qui reste à vérifier manuellement, avant de clore le critère 4.18

1. **Toute la section 2** (lecteur d'écran NVDA ou VoiceOver) — nécessite une personne
   humaine avec un lecteur d'écran, ce qui n'est pas disponible dans cet environnement.
2. Le focus précis sur le titre du panneau d'explication à l'ouverture, et le retour de
   focus au bon bouton à la fermeture — vérifiable par le même type de script, non fait
   ici par manque de temps, pas par impossibilité technique.
3. Le contour de focus sur un bouton à fond bleu — inapplicable dans l'état actuel de
   l'écran (aucun bouton à fond bleu n'existe), à revérifier si la charte visuelle change.
4. Un vrai zoom `Ctrl +` du moteur de rendu (agrandissement de police, pas seulement
   réduction du viewport), sur un navigateur non piloté par script.
5. Vérification au pixel des couleurs réellement affichées par rapport aux variables
   déclarées dans `style.css`, à l'œil, sur l'écran rendu.

## Re-vérification du 2026-09-16, après correction des deux non-conformités

**Ce qui a changé, et rien d'autre** : `tabindex="-1"` ajouté sur
`<main id="contenu-principal">` (`src/edumatch/api/static/index.html`) — même
technique déjà en place sur `#explication` dans ce même document, donc rien
de nouveau à valider sur ce point précis — et réécriture de
`lireDetailErreur` (`src/edumatch/api/static/app.js`) pour traiter le cas où
`corps.detail` est un **tableau** d'erreurs Pydantic v2 (`type`, `loc`,
`msg`), en construisant un message par champ fautif plutôt que le générique
`Erreur ${status}.`. Le constat initial ci-dessus n'est pas modifié : cette
section documente uniquement l'état après correction.

**Environnement de la re-vérification** : API relancée en local par
`uvicorn edumatch.api.main:app`, port **8010** (le 8000 restait occupé par le
conteneur `fastapi_app` d'un autre projet, non touché, ni `newsletter_worker`,
`reminder_worker`, `adminer_db`, `postgres_db`, tous vérifiés intacts après
coup). Identifiants HTTP Basic de test fixés uniquement en variables
d'environnement du processus (`CONSEILLER_IDENTIFIANT`,
`CONSEILLER_MOT_DE_PASSE`), jamais écrits dans un fichier. Serveur arrêté à
la fin de la vérification.

### Non-conformité n° 1 (majeure) — reproduite avant, puis revérifiée après

Reproduite avant correction, dans ce même passage, avec le script inchangé
`clavier-zoom-check.mjs` : `lien_evitement_deplace_focus_dans_main: false`
(comportement identique à celui déjà consigné plus haut dans ce rapport).

Après correction, rejouée avec le **même script, sans aucune modification** :

```
[clavier] lien_evitement_deplace_focus_dans_main = true
```

`document.activeElement.closest("main")` n'est plus `null` après `Entrée`
sur le lien d'évitement : le focus est désormais posé dans `<main>`, pas
seulement le défilement. **Corrigé, vérifié en conditions réelles.**

### Non-conformité n° 2 (mineure) — reproduite avant, puis revérifiée après

Avant correction (inchangé par rapport au constat initial) :

```
[formulaires] departement_mal_forme_message = "Erreur 422."
```

Après correction, même script, même scénario (département `"7"`, motif
`^(2[AB]|[0-9]{2,3})$`) :

```
[formulaires] departement_mal_forme_message = "Département visé : le format saisi ne correspond pas à celui attendu."
[formulaires] departement_mal_forme_sans_trace_technique = true
```

Le champ fautif est nommé, la correction attendue est indiquée en termes non
techniques, et — ce qui était déjà conforme avant correction et ne devait pas
régresser — aucune trace technique n'apparaît (pas de motif d'expression
régulière, pas de nom de module Python). **Corrigé, vérifié en conditions
réelles.**

### Confirmation qu'aucune violation n'est apparue

`axe-check.mjs` (inchangé) rejoué sur les trois états réels de l'écran après
correction :

| État de l'écran | Violations | Passes |
|---|---|---|
| Écran vide, avant recherche | 0 | 21 |
| Résultats affichés | 0 | 26 |
| Panneau « Comprendre cette recommandation » ouvert | 0 | 26 |

Nombres de règles passées identiques à ceux mesurés avant correction (voir la
section « Violations axe-core, par gravité » ci-dessus) : les deux
corrections n'ont ni cassé ni masqué de structure sémantique, et n'ont
introduit aucune nouvelle violation. Le reste du parcours clavier rejoué au
passage reste stable par rapport à l'audit initial (séquence de tabulation du
formulaire inchangée, `Shift+Tab` toujours sans piège, focus toujours retenu
sur « Rechercher » après une 422, écartement sans motif toujours annoncé et
toujours suivi d'un déplacement de focus vers le champ de motif, aucun
débordement horizontal à 640 px ni 320 px).

**Ce qui reste non résolu, sans changement** : la section 2 (lecteur d'écran
NVDA/VoiceOver) de la procédure d'audit demeure entièrement non déroulée,
pour la même raison qu'au constat initial — nécessite une personne humaine
avec un lecteur d'écran, absente de cet environnement.

## Traçabilité

| Date | Commit | Navigateur / outils | Écarts constatés | Statut |
|---|---|---|---|---|
| 2026-09-16 | `60ec389` | HeadlessChrome 153.0.0.0, Lighthouse 13.4.1, axe-core 4.13.0 (Puppeteer) | 2 non-conformités (lien d'évitement sans focus programmatique — majeur ; message d'erreur 422 non informatif — mineur) ; section « lecteur d'écran » entièrement non vérifiée | Audit outillé et parcours clavier/zoom/couleur réalisés ; lecteur d'écran humain restant à faire |
| 2026-09-16 (re-vérification, non commitée à ce stade) | — (correction en cours, non encore commitée) | même environnement, mêmes scripts `clavier-zoom-check.mjs` et `axe-check.mjs`, inchangés | 0 non-conformité restante sur les deux points corrigés ; 0 violation axe-core sur les trois états ; section « lecteur d'écran » toujours entièrement non vérifiée | Corrections vérifiées en conditions réelles ; lecteur d'écran humain restant à faire |
