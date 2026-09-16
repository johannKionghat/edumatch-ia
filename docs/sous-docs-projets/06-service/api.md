# L'API — service de matching, explication, retour (E29)

**Critère servi** : Bloc 4, 4.7 (intégration API, erreurs, sécurité) ·
**Source** : `src/edumatch/api/main.py`, `routes/`, `schemas.py`,
`deps.py`, `state.py`, `errors.py`, `auth.py`, `rate_limit.py`,
`security_headers.py` · **Commit** : `bcf0a81`, durci par `b3e8bba` ·
**Dernière revue** : 2026-09-16.

FastAPI, 6 routeurs : `health`, `matching`, `explain`, `feedback`,
`assistant`, `ecran`. 31 tests ajoutés à cette étape, suite complète à 572
puis 668 après E30-E32, puis 732 (un ignoré) après le durcissement de
sécurité décrit ci-dessous (`python -m pytest -q`).

## Durcissement de sécurité (2026-09-16, commit `b3e8bba`)

Une revue de sécurité sur cette étape et sur l'écran conseiller (E31) a
montré qu'un identifiant de conseiller saisi librement dans le corps de
`POST /feedback` permettait d'imputer un écartement à un conseiller qui
ne l'avait jamais décidé. Une trace de contrôle humain non imputable ne
prouve rien au sens de l'article 14 du règlement sur l'IA. C'était le
motif A de l'analyse d'impact (`05-gouvernance/aipd.md`, §8.4).

**Authentification HTTP Basic sur `/feedback` seulement.** Le champ
`identifiant_conseiller` a disparu du schéma d'entrée
(`schemas.RequeteFeedback`) : l'identifiant journalisé est maintenant le
principal HTTP authentifié, vérifié par `api/auth.get_conseiller_courant`
avec `secrets.compare_digest` (comparaison en temps constant, pour ne pas
laisser deviner par le temps de réponse quels caractères sont déjà bons).
Les identifiants attendus (`CONSEILLER_IDENTIFIANT`,
`CONSEILLER_MOT_DE_PASSE`) viennent de l'environnement, jamais versionnés
(`.env.example`). Sans eux, la route répond **503** plutôt que d'accepter
un identifiant qu'elle ne peut pas vérifier.

`/matching`, `/explain` et l'assistant restent anonymes : seule la route
qui écrit une décision imputée à quelqu'un est concernée. Étendre
l'authentification partout aurait cassé l'usage anonyme de l'écran sans
bénéfice établi. Je reverrai ce choix le jour où l'écran affichera une
donnée nominative de candidat, ou s'il faut tracer qui a consulté quoi
(pas seulement qui a décidé quoi).

**Limitation de débit à fenêtre glissante** sur `/matching` (par adresse
IP) et `/feedback` (par identifiant authentifié), 120 requêtes par minute
par défaut (`configs/base.yaml`, `api.limite_requetes_par_minute`). Une
fenêtre glissante plutôt qu'un compteur remis à zéro périodiquement, qui
laisserait passer une rafale à cheval sur deux fenêtres. Limite connue :
le compteur vit en mémoire de chaque processus, donc plusieurs réplicas
multiplieraient la limite réelle — il faudra un magasin partagé avant un
déploiement à plusieurs pods (le HPA du second dépôt monte jusqu'à 6
réplicas).

**En-têtes de sécurité** sur chaque réponse, y compris les erreurs :
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Content-Security-Policy: default-src 'self'`, `Referrer-Policy:
no-referrer` (`security_headers.py`). Pas de `Strict-Transport-Security` :
aucun TLS ne termine devant ce service aujourd'hui, et ajouter cet en-tête
mentirait sur une protection absente. Je le poserai quand un relais TLS
existera.

**Métriques Prometheus** sur `/metrics`, sans authentification (le
collecteur n'en porte pas) et sans donnée personnelle : compteurs et
histogrammes par route et par code de statut, plus deux compteurs métier
(`edumatch_feedback_decisions_total` par type de décision,
`edumatch_matching_sans_resultat_total`).

**Un bug trouvé en lançant le conteneur** : la bibliothèque
d'instrumentation Prometheus en version 7 casse toutes les routes avec la
version de FastAPI installée dans l'image. Bornée en version 8, image
reconstruite, vérifiée par de vraies requêtes HTTP. Toutes les dépendances
signalées reçoivent maintenant une borne haute calée sur ce qui est
réellement installé.

**Ce qui reste ouvert** : la limitation de débit ne survit pas à plusieurs
réplicas, l'authentification ne couvre que `/feedback`, aucun verrouillage
après une série d'échecs d'authentification, et aucun TLS ne termine
devant le service.

## Les routes

| Route | Méthode | Rôle |
|---|---|---|
| `/health` | GET | sonde de vivacité |
| `/matching` | POST | recommande des formations pour un profil |
| `/explain` | GET | explication SHAP d'une cellule |
| `/feedback` | POST | retour et écartement motivé du conseiller |
| `/assistant` | POST | question documentaire (E32) |
| `/` | GET | écran conseiller (E31) |

## `/explain` ne recalcule jamais SHAP en direct

Le précalcul (E25) porte sur les **440 030 cellules**, pèse **99,8 Mo** et
prend **8,3 minutes**. Le nombre de cellules est fini, donc je précalcule
par lots après chaque réentraînement : l'API se contente de lire le
fichier. La latence de `/explain` est bornée par une lecture disque, pas
par un calcul TreeSHAP à la demande.

## Dégradation explicite, jamais de panne totale ni de zéro silencieux

Si le stock Sirene manque au démarrage, le service démarre quand même :
chaque formation porte le statut de chaîne rompue déjà défini par le
module de débouchés (E28), avec son motif dans la réponse. Un zéro n'est
jamais confondu avec une absence réelle de débouché.

## La réserve sur le modèle voyage avec la réponse

L'accessibilité prédite ne bat pas la baseline sur le jeu de test — 0,0758
contre 0,0701 — et sa calibration s'y dégrade (`04-modele/evaluation.md`).
Chaque réponse de `/matching` porte cette mise en garde, pas seulement la
documentation.

## Article 22 du RGPD

Chaque réponse de `/matching` rappelle que le score assiste un conseiller,
il ne décide jamais. `/feedback` est le point d'entrée où un écartement
motivé et horodaté est journalisé, comme l'exige la matrice de risques de
la gouvernance.

## Catalogue trop grand : erreur explicite, jamais de troncature

Si le sous-catalogue restreint au profil déclaré dépasse le plafond
configuré, le service répond **422** et demande de préciser le
département ou le domaine : le module de recommandation n'est pas
vectorisé et ne peut pas classer un volume arbitraire en temps borné. Un
plafond explicite vaut mieux qu'une troncature invisible.

## Deux dettes déclarées dans le code

- **Le modèle est entraîné au démarrage**, faute d'un chargeur depuis un
  registre de modèles (MLflow n'est pas encore branché sur le service) —
  acceptable pour la démonstration, à corriger avant une vraie mise en
  production.
- **La durée de conservation du journal de retour** (`/feedback`, T6 de la
  gouvernance) n'est pas encore purgeable à cette étape — voir
  `journalisation-purge.md` pour ce qui a été construit ensuite (E30) et
  ce qui reste ouvert.

---

*Dernière mise à jour : 2026-09-16, commit `b3e8bba`.*
