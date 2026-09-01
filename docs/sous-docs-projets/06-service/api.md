# L'API — service de matching, explication, retour (E29)

**Critère servi** : Bloc 4, 4.7 (intégration API, erreurs, sécurité) ·
**Source** : `src/edumatch/api/main.py`, `routes/`, `schemas.py`,
`deps.py`, `state.py`, `errors.py` · **Commit** : `0b61e25` ·
**Dernière revue** : 2026-09-01.

FastAPI, 6 routeurs montés : `health`, `matching`, `explain`, `feedback`,
`assistant`, `ecran`. 31 tests neufs à cette étape, suite complète à 572
puis 668 après E30-E32 (`python -m pytest -q`).

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

*Dernière mise à jour : 2026-09-01, commit `0b61e25`.*
