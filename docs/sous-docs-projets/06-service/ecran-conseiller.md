# Écran conseiller — contrôle humain et accessibilité (E31)

**Critères servis** : Bloc 4, **4.17** (contrôle humain, article 14 du
règlement sur l'IA) et **4.18** (accessibilité RGAA) · **Source** :
`src/edumatch/api/static/` (`index.html`, `app.js`, `style.css`),
`src/edumatch/api/routes/ecran.py`, `src/edumatch/api/auth.py` ·
**Commit** : `a732aed`, durci par `b3e8bba` ·
**Dernière revue** : 2026-09-16.

Voir, comprendre, écarter avec motif : les trois actions que l'écran rend
possibles, dans cet ordre.

## Critère 4.17 — contrôle humain effectif

L'écartement d'une recommandation est **bloqué côté client et côté
serveur** tant qu'aucun motif n'est saisi. Un écran qui affiche un score
sans permettre de le contredire, motivé et tracé, n'est qu'une façade.
L'article 14 demande un contrôle humain effectif, pas un bouton : la
double validation (JavaScript et route `/feedback`) empêche qu'un
contournement côté client rende le contrôle cosmétique.

L'écran dit ce que beaucoup d'interfaces cachent :
- le terme de débouchés est indisponible pour 98,6 % des formations
  (`06-service/score.md`) — quand c'est le cas, l'écran l'affiche avec son
  motif, jamais un score qui laisserait croire que les trois termes ont
  été calculés ;
- la réserve sur le modèle, qui ne bat pas la baseline sur le jeu de test,
  est affichée et non enfouie dans la documentation ;
- le rappel que le score assiste sans décider (article 22 du RGPD) est
  lisible à l'écran, pas relégué à une mention légale.

Le flux d'écartement journalise, via `/feedback`, une décision motivée et
horodatée — voir `journalisation-purge.md` pour ce que devient cette trace
(T6 de la gouvernance) et ce qui n'est pas encore construit sur sa purge.

**L'identifiant du conseiller n'est plus déclaratif** (revue de sécurité du
2026-09-16, commit `b3e8bba`). Jusqu'à cette date, `/feedback` acceptait un
identifiant saisi librement dans le corps de la requête, ce qui permettait
d'imputer un écartement à un conseiller qui ne l'avait jamais décidé.
`/feedback` exige désormais une authentification HTTP Basic (`api/auth.py`) :
l'identifiant journalisé est le principal authentifié, jamais une valeur
saisie par le formulaire. Côté écran, le champ « Identifiant de
conseiller » ne sert plus qu'à personnaliser l'affichage local, il n'est
plus transmis à l'API. Une réponse **401** de `/feedback` affiche un
message demandant de se reconnecter.

`/matching` et l'écran lui-même (`GET /`) restent accessibles sans
authentification : seule la route qui écrit une décision imputée à
quelqu'un l'exige. Je reverrai cette limite le jour où l'écran affichera
une donnée nominative de candidat, ou s'il faudra tracer qui a consulté
quoi et non plus seulement qui a décidé quoi.

Une limitation de débit (fenêtre glissante, 120 requêtes par minute par
identifiant de conseiller) protège désormais `/feedback` contre une
succession d'appels automatisés — voir `06-service/api.md` pour le détail
et la limite sur plusieurs réplicas.

**Ce que ce critère ne couvre pas encore** : un tableau de bord du taux
d'écartement, destiné au déployeur, n'existe pas. Sans lui, un contrôle
humain qui n'écarte jamais rien resterait invisible au niveau de
l'organisation, même si chaque écartement individuel est tracé.

## Critère 4.18 — accessibilité RGAA

Pas de framework front : le contrôle fin du balisage qu'exige
l'accessibilité (ordre des repères, attributs précis, pas de conteneurs
imposés par une bibliothèque) est plus simple à garantir en HTML, CSS et
JavaScript servis directement par l'API.

**Prévention du XSS par construction.** Le rendu passe par `textContent`
et `createElement`, jamais par `innerHTML` : la classe d'attaque entière
est éliminée à la source plutôt que comptée sur un échappement qu'on
oublierait une fois.

**Ce que la suite automatisée prouve**
(`tests/unit/test_ecran_accessibilite.py`) : structure sémantique du
document (un seul `h1`, hiérarchie de titres sans saut, repères uniques),
chaque champ de saisie associé à un `<label>`, zones dynamiques annoncées
(`role="alert"`, `aria-live`), contraste recalculé à chaque exécution des
tests par la formule WCAG sur les couleurs déclarées dans `style.css`,
focus jamais supprimé sans remplacement visible, absence d'`innerHTML`.

**Ce que seul un navigateur peut vérifier** — rendu réel des polices et du
zoom, comportement d'un lecteur d'écran, parcours clavier de bout en bout,
perception effective par une personne daltonienne, temps de réponse
perçu — fait l'objet d'une procédure d'audit manuel :
**`reports/audit-rgaa-procedure.md`**. Je l'ai déroulée le 2026-09-16,
sur le commit `1a9a0e6`, avec Chrome (Lighthouse 100/100 en accessibilité,
0 violation axe-core sur les trois états réels de l'écran : vide,
résultats, panneau d'explication) et un parcours clavier et de
redimensionnement scripté. Détail point par point dans
**`reports/audit-rgaa-resultats.md`**. Deux non-conformités réelles en
sont ressorties, et j'ai corrigé et revérifié les deux le jour même
(section de re-vérification datée dans le rapport) :

- le lien d'évitement posait le défilement mais pas le focus clavier dans
  `<main>` (majeur, `tabindex` manquant) — corrigé par `tabindex="-1"` sur
  `<main id="contenu-principal">`, la même technique que celle déjà en
  place sur `#explication` ;
- le message d'une erreur de validation 422 s'affichait comme
  « Erreur 422. » sans indication exploitable (mineur, le tableau
  d'erreurs Pydantic v2 n'était pas traité côté client, seul le cas
  `detail` en chaîne l'était) — `lireDetailErreur` (`app.js`) construit
  désormais un message par champ fautif (ex. « Département visé : le
  format saisi ne correspond pas à celui attendu. »), sans jamais
  reprendre le message brut de Pydantic ni exposer de trace technique.

**La section « lecteur d'écran » de la procédure reste entièrement non
déroulée** : elle demande une personne humaine avec NVDA ou VoiceOver,
absente de l'environnement où j'ai mené cet audit.

## Limites déclarées

1. **L'audit manuel RGAA a été déroulé dans un vrai navigateur pour tout ce
   qui ne demande pas de lecteur d'écran** (clavier, zoom,
   redimensionnement, simulation de daltonisme, outils automatisés) — voir
   `reports/audit-rgaa-resultats.md`. Les deux non-conformités
   trouvées (lien d'évitement sans focus programmatique, message d'erreur
   422 non informatif) ont été corrigées et revérifiées en conditions
   réelles (parcours clavier scripté et audit axe-core rejoués sur les
   trois états, 0 violation). La vérification au lecteur d'écran (NVDA ou
   VoiceOver) n'a pas été faite, faute d'un tel outil dans l'environnement
   audité — elle reste à dérouler par une personne humaine.
2. **Le tableau de bord du taux d'écartement** destiné au déployeur reste
   à construire : Grafana compte les décisions, sans en calculer le taux.
3. **L'authentification ne couvre que `/feedback`** — `/matching` et
   l'écran restent anonymes, par choix assumé plutôt que par oubli (voir
   ci-dessus).
4. **Aucun verrouillage après une série d'échecs d'authentification** : la
   limitation de débit borne le rythme des appels, mais n'introduit pas de
   délai croissant ni de blocage après plusieurs mots de passe erronés.
5. **Résolu au 2026-09-16** — l'identifiant du conseiller n'est plus
   déclaratif : voir la section dédiée ci-dessus.

---

*Dernière mise à jour : 2026-09-16, commit `b3e8bba`.*
