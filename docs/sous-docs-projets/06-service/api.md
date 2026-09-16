# L'API — service de matching, explication, retour (E29)

**Critère servi** : Bloc 4, 4.7 (intégration API, erreurs, sécurité) ·
**Source** : `src/edumatch/api/main.py`, `routes/`, `schemas.py`,
`deps.py`, `state.py`, `errors.py`, `auth.py`, `rate_limit.py`,
`security_headers.py` · **Commit** : `0b61e25`, durci par `f7687ae` ·
**Dernière revue** : 2026-09-16.

FastAPI, 6 routeurs montés : `health`, `matching`, `explain`, `feedback`,
`assistant`, `ecran`. 31 tests neufs à cette étape, suite complète à 572
puis 668 après E30-E32, puis 732 (un ignoré) après le durcissement de
sécurité décrit ci-dessous (`python -m pytest -q`).

## Durcissement de sécurité (2026-09-16, commit `f7687ae`)

Une revue de sécurité a porté sur cette étape et sur l'écran conseiller
(E31). Elle a trouvé qu'un identifiant de conseiller déclaré librement dans
le corps de `POST /feedback` permettait à n'importe quel appelant
d'imputer un écartement à un conseiller qui ne l'avait jamais décidé — une
trace de contrôle humain qui n'est pas imputable ne prouve rien au sens de
l'article 14 du règlement sur l'IA. C'était le premier motif de blocage
(motif A) de l'analyse d'impact (`05-gouvernance/aipd.md`, §8.4) ; il est
levé par ce qui suit.

**Authentification HTTP Basic, sur `/feedback` seulement.** Le champ
`identifiant_conseiller` a disparu du schéma d'entrée
(`schemas.RequeteFeedback`) : l'identifiant journalisé est désormais le
principal HTTP authentifié, vérifié par `api/auth.get_conseiller_courant`
avec `secrets.compare_digest` (comparaison en temps constant, les deux
comparaisons — identifiant et mot de passe — toujours effectuées, pour ne
pas laisser fuir par le temps de réponse combien de caractères sont déjà
corrects). Les identifiants attendus (`CONSEILLER_IDENTIFIANT`,
`CONSEILLER_MOT_DE_PASSE`) sont lus dans l'environnement, jamais versionnés
(`.env.example`) ; sans eux la route répond **503**, explicitement, plutôt
que d'accepter un identifiant qu'elle ne peut vérifier.

`/matching`, `/explain` et l'assistant restent anonymes : le motif
démontré ne concernait que la route qui écrit une décision imputée à
quelqu'un, pas celles qui se contentent d'estimer. Étendre
l'authentification à l'ensemble de l'API aurait cassé l'usage anonyme de
l'écran de supervision sans bénéfice établi. Le seuil qui ferait
reconsidérer ce choix : le jour où l'écran expose une donnée nominative de
candidat, ou qu'il faut tracer qui a consulté quoi (pas seulement qui a
décidé quoi).

**Limitation de débit à fenêtre glissante** sur `/matching` (par adresse
IP, la route restant anonyme) et sur `/feedback` (par identifiant de
conseiller authentifié), 120 requêtes par minute par défaut
(`configs/base.yaml`, `api.limite_requetes_par_minute`). Une fenêtre
glissante plutôt qu'un compteur remis à zéro périodiquement, qui
autoriserait une rafale à cheval sur deux fenêtres. **Limite assumée** : le
compteur vit dans la mémoire de chaque processus, donc plusieurs réplicas
multiplieraient la limite réelle appliquée — à remplacer par un magasin
partagé avant un déploiement à plusieurs pods (le HPA du second dépôt monte
jusqu'à 6 réplicas).

**En-têtes de sécurité** ajoutés à chaque réponse, y compris les erreurs :
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Content-Security-Policy: default-src 'self'`, `Referrer-Policy:
no-referrer` (`security_headers.py`). **Pas de
`Strict-Transport-Security`** : aucun TLS ne termine devant ce service
aujourd'hui, ajouter cet en-tête mentirait sur une protection absente — à
poser le jour où un relais TLS est mis en place, pas avant.

**Métriques Prometheus** exposées sur `/metrics`, sans authentification
(le collecteur n'en porte pas) et sans donnée personnelle : compteurs et
histogrammes agrégés par route et par code de statut, plus deux compteurs
métier (`edumatch_feedback_decisions_total` par type de décision,
`edumatch_matching_sans_resultat_total`). Le tableau de bord de
supervision du second dépôt avait été écrit pour cette route avant qu'elle
n'existe côté service ; elle existe désormais.

**Un bug trouvé en lançant le conteneur, pas en lisant les tests** : la
bibliothèque d'instrumentation Prometheus en version 7 casse toutes les
routes avec la version de FastAPI réellement installée dans l'image.
Borne relevée en version 8, image reconstruite, vérifié par de vraies
requêtes HTTP (santé, métriques, matching, retour répondent, en-têtes
présents). Toutes les dépendances signalées reçoivent désormais une borne
haute calée sur les versions réellement installées, plutôt qu'au jugement.

**Ce qui reste ouvert** : la limitation de débit ne survit pas à plusieurs
réplicas, l'authentification ne couvre que `/feedback`, aucun verrouillage
après une série d'échecs d'authentification n'existe, et aucun TLS ne
termine devant le service — voir `reste-a-faire.md`.

## Les routes

| Route | Méthode | Rôle |
|---|---|---|
| `/health` | GET | sonde de vivacité |
| `/matching` | POST | recommande des formations pour un profil |
| `/explain` | GET | explication SHAP d'une cellule |
| `/feedback` | POST | retour et écartement motivé du conseiller |
| `/assistant` | POST | question documentaire (E32) |
| `/` | GET | écran conseiller (E31) |

## L'explication ne recalcule jamais SHAP en direct

Le précalcul complet (E25) porte sur les **440 030 cellules**, pèse
**99,8 Mo** et prend **8,3 minutes**. Le nombre de cellules étant fini, le
précalcul par lots après chaque réentraînement est la bonne réponse : l'API
se contente de le lire. La latence de `/explain` est bornée par
construction — une lecture de fichier — jamais par l'espérance d'un calcul
TreeSHAP à la demande.

## Dégradation explicite, jamais de panne totale ni de zéro silencieux

Si le stock Sirene manque au démarrage, le service démarre quand même :
chaque formation porte le statut de chaîne rompue déjà défini par le
module de débouches (E28), avec son motif dans la réponse. Un conseiller
ne lit jamais un zéro qu'il prendrait pour une absence réelle de débouché.

## La réserve sur le modèle voyage avec la réponse

L'accessibilité prédite ne bat pas la baseline sur le jeu de test — 0,0758
contre 0,0701 — et sa calibration s'y dégrade (`04-modele/evaluation.md`).
Cette mise en garde est portée par chaque réponse de `/matching`, pas
seulement écrite dans la documentation : un consommateur de l'API ne peut
pas l'ignorer en lisant uniquement le score.

## Article 22 du RGPD

Chaque réponse de `/matching` porte un avis d'assistance : le score assiste
un conseiller, il ne décide jamais. La route `/feedback` est le point
d'entrée par lequel un écartement motivé et horodaté est journalisé, comme
l'exige la matrice de risques de la gouvernance.

## Catalogue trop grand : erreur explicite, jamais de troncature

Si le sous-catalogue restreint au profil déclaré dépasse le plafond
configuré, le service répond **422** et demande de préciser le département
ou le domaine — le module de recommandation n'étant pas vectorisé à ce
stade et ne pouvant pas classer un volume arbitraire en temps borné. Un
plafond explicite vaut mieux qu'une troncature invisible qui masquerait des
formations à un conseiller sans le lui dire.

## Deux dettes déclarées dans le code, pas dans un commentaire tu

- **Le modèle est entraîné au démarrage**, faute d'un chargeur depuis un
  registre de modèles (MLflow n'est pas encore branché sur le service) —
  acceptable pour la démonstration, à corriger avant une mise en
  production réelle.
- **La durée de conservation du journal de retour** (`/feedback`, T6 de la
  gouvernance) n'est, à cette étape, pas encore purgeable — voir
  `journalisation-purge.md` pour ce qui a été construit ensuite (E30) et
  ce qui reste ouvert.

---

*Dernière mise à jour : 2026-09-16, commit `f7687ae`.*
