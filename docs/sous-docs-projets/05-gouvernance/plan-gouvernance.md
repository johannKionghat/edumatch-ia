# Plan de gouvernance des données

**Critères servis** : Bloc 1, 1.1 (politiques, classification, règles
d'usage), 1.2 (rôles et responsabilités), 1.10 (gestion des secrets),
1.11 (procédure d'audit et de mise à jour) · **Version** : 1.1 ·
**Date** : 2026-08-30, révisée le 2026-09-15.

Ce plan décrit la gouvernance de ce dépôt, pas une gouvernance idéale. Chaque
politique pointe vers un fichier, une commande ou un contrôle automatisé.
Quand une politique n'a pas encore sa traduction technique, elle est marquée
« non implémentée ».

Documents rattachés : `registre-traitements.md`, `registre-sources.md`,
`risques.md`, `aipd.md`, `model-card.md`, `ai-act.md`.

---

## 1. Principes

1. La preuve prime sur la déclaration : un chiffre non reproductible est
   retiré, pas arrondi (quatre corrections déjà faites : volumétrie Sirene,
   nombre d'établissements, nombre de fiches RNCP, encodage).
2. La minimisation est une décision de conception : neuf colonnes lues sur
   cinquante-quatre pour Sirene, neuf sur cent vingt-huit pour Parcoursup.
3. Le genre n'entre jamais dans le modèle, il sert à l'audit d'équité a posteriori.
4. Ce qui n'est pas classé n'entre pas : listes blanches, chaîne arrêtée par défaut.
5. Une obligation qui ne se traduit pas en code ou en procédure datée n'est
   pas mise en œuvre.
6. Je déclare ce qui manque.

## 2. Classification des données

Quatre niveaux, qui déterminent où la donnée vit, qui y accède et sa durée de conservation.

| Niveau | Définition | Où | Règles d'usage |
|---|---|---|---|
| P, Publique | Donnée ouverte, sans caractère personnel | `data/raw/parcoursup/`, `data/processed/parcoursup/`, `data/external/referentiels/`, `models/` | Réutilisation libre sous attribution, versionnable, publiable |
| I, Interne | Donnée dérivée du projet, dont la diffusion prématurée nuirait à la lecture | rapports intermédiaires, exécutions enregistrées, `mlflow.db` | Non versionnée, non publiée hors dossier de certification |
| DP, Personnelle pseudonymisée | Ré-identification possible avec une information complémentaire | `data/samples/sirene/`, `agregats_commune_naf.parquet`, journaux d'inférence après 12 mois | Base légale obligatoire, durée définie, minimisation testée, jamais exposée au grain d'origine |
| DP+, Personnelle en clair | Donnée identifiante, y compris de mineurs | Saisie d'inférence, journaux des 12 premiers mois, motifs de supervision | Chiffrement au repos et en transit, accès nominatif journalisé, purge planifiée, hébergement dans l'Union |

Aucune donnée de catégorie particulière (article 9) n'est traitée, vérifié
attribut par attribut. Le statut de boursier n'en est pas une : c'est une
donnée à forte portée sociale, qui appelle une vigilance sur la discrimination
indirecte, pas la qualification de l'article 9.

**Règle de propagation** : le niveau d'un artefact dérivé est le plus élevé de
ses sources, sauf démonstration écrite d'anonymisation (une base « sans nom »
n'est pas anonyme). C'est cette règle qui classe `agregats_commune_naf` en DP
bien qu'il ne contienne que des comptages : 65,9 % de ses cellules non vides
n'ont qu'un établissement.

## 3. Rôles et responsabilités

| Rôle | Décide de | Ne décide pas de | Traduction |
|---|---|---|---|
| Data Owner (un par domaine) | Usage autorisé, classification, durée de conservation | La technique de mise en œuvre | Domaines : catalogue de formations, territoire/emploi, référentiels |
| Data Steward | Qualité, schéma, contrôles bloquants, réconciliation des nomenclatures | La finalité | `src/edumatch/quality/`, `tests/data/`, `03-pipeline/qualite.md` |
| Délégué à la protection des données | Qualification juridique, base légale, durées, AIPD, licences ; blocage de mise en production | Les choix de modélisation | Ce dossier |
| Responsable du modèle | Variables, protocole d'évaluation, seuils de dérive, Model Card | La qualification juridique | `configs/base.yaml`, ADR 0009 à 0013 |
| Responsable sécurité technique | Secrets, accès, chiffrement, cloisonnement | Le droit applicable | `.gitignore`, infrastructure |
| Superviseur humain (conseiller, art. 14) | Écartement d'une recommandation, avec motif | Le modèle et ses paramètres | Écran conseiller construit, motif obligatoire côté client et serveur |

Quatre décisions exigent l'accord du délégué à la protection des données :
ajouter une variable, exposer un nouvel agrégat, allonger une durée de
conservation, ajouter une source.

**Motifs de blocage de la mise en production**, opposables tels quels : une
variable de genre en entrée du modèle, une analyse d'impact absente ou
périmée, un secret versionné, aucun contrôle humain effectif, une donnée
conservée sans durée ni purge exécutable, une source utilisée hors licence,
une conformité affirmée sans preuve d'implémentation.

**État au 2026-09-15.** Les trois motifs actifs de la version 1.0 (agrégat
exposable sans seuil, journalisation sans purge, absence d'écran de
supervision) sont levés : k = 5 et filtre de diffusion appliqués, purge
exécutable testée et planifiée, écran de supervision construit.

**Cinq motifs les remplacent** (détail et motivation dans `aipd.md` §8.4) :

| Motif | Contenu |
|---|---|
| A | Aucun contrôle d'accès à l'écran, identifiant de conseiller déclaratif : un contrôle non imputable ne se démontre pas |
| B | Journal de supervision (T6) sans purge exécutable |
| C | Aucune notice d'information destinée au candidat |
| D | Restitution d'une probabilité dont le défaut de calibration est mesuré et non corrigé |
| E | Attribution des sources non effective |

Le motif D est ajouté par cette révision : mesurer la calibration et publier
quand même le chiffre serait pire que ne l'avoir jamais mesurée. Ces motifs
bloquent la mise en service auprès de candidats réels, pas le développement.

## 4. Règles d'usage des données

| Règle | Traduction | Contrôle |
|---|---|---|
| Les données brutes sont immuables | `data/raw/` jamais modifié | Tout supprimer sauf `raw/` et régénérer par `make data` |
| Ce qui n'est pas classé n'entre pas | Liste blanche de 9 colonnes, classement des 128 dans `configs/base.yaml` | `tests/data/test_variables_reference.py` |
| Aucune variable postérieure à la connaissance du candidat | Décalage d'une session pour 35 compteurs | `tests/data/test_features_build_antifuite.py`, 5 contrôles |
| Le genre ne sert qu'à l'audit | 4 colonnes classées `interdite` | même fichier de test |
| Un échec de qualité bloque | Contrôles à l'entrée de chaque étape | `tests/data/test_quality_run_blocage.py` |
| Aucune donnée simulée | Toute source publique, réelle, sous licence vérifiée | `registre-sources.md` et manifestes |
| Aucune donnée personnelle dans les journaux applicatifs | Journal d'inférence dans un registre dédié (`processed/audit/journal.jsonl`), distinct de la sortie standard ; l'assistant documentaire ne journalise jamais la question, seulement sa longueur | Implémenté sur ces deux points, aucun contrôle automatisé pour le reste du code |
| Toute restitution territoriale passe un seuil de k-anonymat | k = 5 au grain `département × division NAF`, filtre `diffusible` | `src/edumatch/matching/agregat_sirene_debouches.py` |

## 5. Politique de gestion des secrets

**En place et vérifié**

| Mesure | Preuve |
|---|---|
| Aucun secret versionné | `.gitignore` exclut `.env`, `credentials*.json`, `*adminsdk*.json`, `*.pem`, `*.key`, `kubeconfig`, vérifié par `git check-ignore -v` |
| Variables documentées sans valeur | `.env.example`, valeurs factices |
| Aucun secret en dur | Identifiants exclusivement par variables d'environnement, règle rappelée en tête de `configs/base.yaml` |
| Configuration externalisée | `src/edumatch/config.py`, typée, un fichier par environnement (ADR 0003) |

**Ce qui manque**

| Règle | Contenu |
|---|---|
| Rotation | Clé cloud et clé API du modèle de langage : tous les 90 jours, et au départ de toute personne y ayant eu accès |
| Révocation | Un secret exposé est révoqué avant d'être remplacé, jamais l'inverse ; retirer le fichier du dépôt ne révoque rien |
| Détection | Analyse de secrets en intégration continue, non implémentée car la CI n'existe pas encore |
| Portée minimale | Une clé par environnement, jamais partagée dev/production |

## 6. Procédure d'audit

| Déclencheur | Date | Portée |
|---|---|---|
| Publication du millésime Parcoursup | Chaque année, juillet à octobre | Audit complet, les 12 points |
| Ouverture de la campagne | Chaque année, janvier | Fraîcheur, dérive, revue des risques |
| Changement substantiel | À l'événement | Nouvelle source, variable, finalité, modèle, incident |

**Douze points de contrôle**, chacun prouvé par une commande ou un fichier :
secret versionné (`git check-ignore -v`), licence à jour (`registre-sources.md`),
attribution effective (écran Sources et licences), base légale écrite
(`registre-traitements.md`), purge exécutée (`processed/audit/purges.jsonl`),
absence de genre en entrée (test anti-fuite), absence de fuite temporelle
(même test, par mutation), toute colonne classée (même fichier), audit
d'équité rejoué sur le modèle en service, calibration mesurée sur le
millésime en service, taux d'écartement des superviseurs mesuré (un taux nul
est un signal d'alerte, pas un succès), seuils de k-anonymat appliqués aux
restitutions.

**Sortie** : une entrée datée, avec les points en échec, leur responsable et
leur échéance. Un audit sans point en échec est un audit à refaire.

## 7. Procédure de mise à jour de la documentation

| Événement | Ce qui doit être mis à jour, dans cet ordre |
|---|---|
| Ajout d'une source | `registre-sources.md`, puis `registre-traitements.md`, puis `risques.md` |
| Ajout ou retrait d'une variable | `configs/base.yaml`, l'ADR correspondant, la Model Card, l'analyse d'impact si l'équité est touchée |
| Nouveau modèle en service | Model Card, correspondance AI Act, `risques.md` |
| Changement de finalité | Analyse d'impact rouverte avant toute mise en œuvre |
| Incident ou violation | Journal d'incident, notification sous 72 heures si risque pour les personnes, revue de `risques.md` |

**Règle de cohérence** : le dépôt fait foi. Si un document déclare un
composant que le code ne confirme pas, c'est le document qui est corrigé.

## 8. État de mise en œuvre

| Élément | État |
|---|---|
| Classification des données | Écrite et appliquée |
| Rôles et périmètres de décision | Écrits, le superviseur humain n'a pas encore d'outil complet |
| Règles d'usage | 6 des 7 contrôlées automatiquement |
| Secrets, exclusion et externalisation | En place et vérifiées |
| Secrets, rotation/révocation/détection | Écrites, non outillées |
| Procédure d'audit | Écrite, jamais exécutée intégralement, 7 des 12 points déjà outillés |
| Procédure de mise à jour | Écrite et appliquée trois fois |
| Analyse d'impact | Complète (version 1.0), avis rendu |
| Model Card | Écrite, performance ventilée sur 27 sous-populations |
| Correspondance au règlement sur l'IA | Écrite, articles 9 à 15 |

---
### Ce que ce plan ne couvre toujours pas

- Aucun système de management de la qualité au sens de l'article 17 du
  règlement sur l'IA, ni de certification ISO/IEC 42001. Les cadres mobilisés
  (NIST AI RMF, ISO/IEC 27001) sont des cadres de travail, pas des normes harmonisées.
- Aucun journal d'incident, aucune procédure de notification de violation,
  aucun plan de surveillance après commercialisation.
- Aucune détection de secrets en intégration continue.

---
*Étape E44, rédigé le 2026-08-30, révisé le 2026-09-15 : motifs de blocage
actualisés, motif D ajouté, état de mise en œuvre repris point par point.*
