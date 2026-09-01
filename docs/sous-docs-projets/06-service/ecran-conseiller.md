# Écran conseiller — contrôle humain et accessibilité (E31)

**Critères servis** : Bloc 4, **4.17** (contrôle humain, article 14 du
règlement sur l'IA) et **4.18** (accessibilité RGAA) · **Source** :
`src/edumatch/api/static/` (`index.html`, `app.js`, `style.css`),
`src/edumatch/api/routes/ecran.py` · **Commit** : `bbebefd` ·
**Dernière revue** : 2026-09-01.

Voir, comprendre, écarter avec motif — les trois actions que l'écran rend
possibles, dans cet ordre.

## Critère 4.17 — contrôle humain effectif

L'écartement d'une recommandation est **bloqué côté client et côté
serveur** tant qu'aucun motif n'est saisi. C'est la distinction qui compte :
un écran qui affiche un score sans permettre de le contredire, motivé et
tracé, n'est qu'une façade. L'article 14 du règlement sur l'IA demande un
contrôle humain **effectif**, pas un bouton — la double validation (JavaScript
et route `/feedback`) empêche qu'un contournement côté client rende le
contrôle cosmétique.

L'écran dit ce que beaucoup d'interfaces cachent :
- le terme de débouchés est indisponible pour 98,6 % des formations
  (`06-service/score.md`) — quand c'est le cas, l'écran l'affiche avec son
  motif, jamais un score qui laisserait croire que les trois termes ont
  été calculés ;
- la réserve sur le modèle, qui ne bat pas la baseline sur le jeu de test,
  est affichée et non enfouie dans la documentation — un conseiller doit
  savoir quelle confiance accorder à ce qu'il lit ;
- le rappel que le score assiste sans décider (article 22 du RGPD) est
  lisible à l'écran, pas relégué à une mention légale.

Le flux d'écartement journalise, via `/feedback`, une décision motivée et
horodatée — voir `journalisation-purge.md` pour ce que devient cette trace
(T6 de la gouvernance) et ce qui n'est pas encore construit sur sa purge.

**Ce que ce critère ne couvre pas encore** : un tableau de bord du taux
d'écartement, destiné au déployeur, n'existe pas — reporté dans
`reste-a-faire.md`. Sans lui, un contrôle humain qui n'écarte jamais rien
resterait invisible au niveau de l'organisation, même si chaque écartement
individuel est, lui, tracé.

## Critère 4.18 — accessibilité RGAA

Pas de framework front : le contrôle fin du balisage qu'exige
l'accessibilité — ordre des repères, attributs précis, absence de
conteneurs imposés par une bibliothèque — est plus simple à garantir en
HTML, CSS et JavaScript servis directement par l'API.

**Prévention du XSS par construction.** Le rendu passe par `textContent` et
`createElement`, jamais par `innerHTML` : la classe d'attaque entière est
éliminée à la source plutôt que comptée sur un échappement qu'on
oublierait une fois.

**Ce que la suite automatisée prouve**
(`tests/unit/test_ecran_accessibilite.py`) : structure sémantique du
document (un seul `h1`, hiérarchie de titres sans saut, repères uniques),
chaque champ de saisie associé à un `<label>`, zones dynamiques annoncées
(`role="alert"`, `aria-live`), contraste **recalculé à chaque exécution**
des tests par la formule WCAG sur les couleurs réellement déclarées dans
`style.css` — jamais documenté une fois puis laissé dériver — focus jamais
supprimé sans remplacement visible, absence d'`innerHTML`.

**Ce que seul un navigateur peut vérifier** — rendu réel des polices et du
zoom, comportement d'un lecteur d'écran, parcours clavier de bout en bout,
perception effective par une personne daltonienne, temps de réponse
perçu — fait l'objet d'une procédure d'audit manuel écrite point par
point : **`reports/e31-audit-rgaa-procedure.md`**. Cette procédure n'a pas
encore été déroulée dans un navigateur réel — reporté dans
`reste-a-faire.md`.

## Trois limites déclarées

1. **L'audit manuel RGAA reste à dérouler** dans un vrai navigateur, avec
   lecteur d'écran (voir la procédure référencée ci-dessus).
2. **L'identifiant du conseiller est déclaratif**, saisi sans vérification
   d'identité — aucun mécanisme d'authentification n'est branché à cette
   étape.
3. **Le tableau de bord du taux d'écartement** destiné au déployeur reste
   à construire.

---

*Dernière mise à jour : 2026-09-01, commit `bbebefd`.*
