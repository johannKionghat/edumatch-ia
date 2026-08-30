# Plan de gouvernance des données

**Critères servis** : Bloc 1 — 1.1 (politiques, classification, règles
d'usage), 1.2 (rôles et responsabilités), 1.10 (gestion des secrets),
1.11 (procédure d'audit et de mise à jour) · **Version** : 1.0 ·
**Date** : 2026-08-30.

Ce plan ne décrit pas une gouvernance idéale : il décrit **celle de ce
dépôt**. Chaque politique énoncée ci-dessous pointe vers un fichier, une
commande ou un contrôle automatisé. Quand une politique n'a pas encore sa
traduction technique, elle est marquée **« non implémentée »** — parce qu'une
conformité déclarée sans preuve d'implémentation n'en est pas une.

Documents rattachés, qui font partie intégrante de ce plan :
`registre-traitements.md`, `registre-sources.md`, `risques.md`, `aipd.md`,
et, quand le modèle sera figé, la Model Card et la correspondance AI Act.

---

## 1. Principes

Six principes, dans l'ordre où ils tranchent quand ils s'opposent.

1. **La preuve prime sur la déclaration.** Un chiffre non reproductible depuis
   un fichier source est retiré, pas arrondi. Ce principe a déjà coûté quatre
   corrections publiques dans ce projet — volumétrie Sirene, nombre
   d'établissements, nombre de fiches RNCP, encodage — et c'est ce qui le
   rend crédible.
2. **La minimisation est une décision de conception, pas un nettoyage.** Neuf
   colonnes lues sur cinquante-quatre pour Sirene ; neuf colonnes autorisées
   sur cent vingt-huit pour Parcoursup ; aucune donnée de navigation.
3. **Le genre n'entre jamais dans le modèle.** Il sert exclusivement à l'audit
   d'équité a posteriori.
4. **Ce qui n'est pas classé n'entre pas.** Les listes sont des listes
   blanches : ce qui n'a pas été examiné est refusé par défaut, et la chaîne
   s'arrête.
5. **Une obligation qui ne se traduit pas en code, en champ ou en procédure
   datée n'est pas mise en œuvre.**
6. **On déclare ce qui manque.** Un registre honnête sur ses lacunes vaut
   mieux qu'un registre qui prétend.

## 2. Classification des données

Quatre niveaux. Le niveau détermine où la donnée peut vivre, qui y accède et
combien de temps elle est conservée.

| Niveau | Définition | Où, concrètement | Règles d'usage |
|---|---|---|---|
| **P — Publique** | Donnée ouverte, sans caractère personnel | `data/raw/parcoursup/`, `data/processed/parcoursup/`, `data/external/referentiels/`, `models/` | Réutilisation libre sous réserve d'attribution ; versionnable ; publiable |
| **I — Interne** | Donnée dérivée du projet, sans caractère personnel, dont la diffusion prématurée nuirait à la lecture | rapports intermédiaires, exécutions enregistrées, `mlflow.db` | Non versionnée, non publiée hors du dossier de certification |
| **DP — Personnelle pseudonymisée** | Donnée personnelle dont la ré-identification reste possible avec une information complémentaire | `data/samples/sirene/`, `data/processed/sirene/agregats_commune_naf.parquet`, journaux d'inférence après 12 mois | Base légale obligatoire ; durée définie ; minimisation vérifiée par test ; **jamais** exposée au grain d'origine |
| **DP+ — Personnelle en clair** | Donnée personnelle identifiante, y compris de mineurs | Saisie d'inférence, journaux des 12 premiers mois, motifs de supervision | Chiffrement au repos et en transit ; accès nominatif et journalisé ; purge planifiée ; hébergement dans l'Union |

**Aucune donnée de catégorie particulière au sens de l'article 9 n'est
traitée**, et ce n'est pas une formule : je l'ai vérifié attribut par
attribut. Le **statut de boursier n'en est pas une** — l'article 9 vise
l'origine raciale ou ethnique, les opinions politiques, les convictions,
l'appartenance syndicale, les données génétiques et biométriques, la santé, la
vie et l'orientation sexuelles. Le boursier est une donnée personnelle à forte
portée sociale, qui appelle une vigilance sur la discrimination indirecte,
pas la qualification de l'article 9.

**Règle de propagation** : le niveau d'un artefact dérivé est le plus élevé de
ses sources, sauf démonstration écrite d'anonymisation — et une base « sans
nom » n'est pas anonyme. Cette règle est ce qui classe `agregats_commune_naf`
en DP alors qu'il ne contient que des comptages : 65,9 % de ses cellules non
vides n'ont qu'un établissement.

## 3. Rôles et responsabilités

Un rôle qui ne décide de rien n'est pas un rôle. La colonne « décide de » est
donc la seule qui compte.

| Rôle | Décide de | Ne décide pas de | Traduction dans le dépôt |
|---|---|---|---|
| **Propriétaire des données** (Data Owner) — un par domaine | L'usage autorisé d'un domaine, sa classification, sa durée de conservation | La technique de mise en œuvre | Domaines : catalogue de formations (Parcoursup), territoire et emploi (Sirene), référentiels (IDÉO, RNCP, ROME) |
| **Intendant des données** (Data Steward) | La qualité, le schéma, les contrôles bloquants, la réconciliation des nomenclatures | La finalité | `src/edumatch/quality/`, `tests/data/`, `03-pipeline/qualite.md` |
| **Délégué à la protection des données** | La qualification juridique, la base légale, les durées, l'AIPD, les licences. **Droit de blocage de la mise en production** | Les choix de modélisation | Ce dossier |
| **Responsable du modèle** | Variables, protocole d'évaluation, seuils de dérive, contenu de la Model Card | La qualification juridique | `configs/base.yaml`, ADR 0009 à 0013 |
| **Responsable de la sécurité technique** | Secrets, accès, chiffrement, cloisonnement | Le droit applicable | `.gitignore`, infrastructure |
| **Superviseur humain** (AI Act art. 14) — le conseiller d'orientation | **L'écartement d'une recommandation**, avec motif | Le modèle et ses paramètres | Écran conseiller, à construire |

**Les quatre décisions qui exigent l'accord du délégué à la protection des
données**, et qu'aucun autre rôle ne peut prendre seul : ajouter une variable
au modèle, exposer un nouvel agrégat, allonger une durée de conservation,
ajouter une source.

**Motifs de blocage de la mise en production**, opposables tels quels :

- une variable de genre entre en entrée du modèle ;
- l'analyse d'impact est absente ou n'a pas été revue depuis un changement
  substantiel ;
- un secret est versionné ;
- aucun dispositif de contrôle humain effectif n'existe ;
- une donnée personnelle est conservée sans durée définie **ni purge
  exécutable** ;
- une source est utilisée hors des conditions de sa licence ;
- une conformité est affirmée sans preuve d'implémentation.

**Trois de ces motifs sont actuellement actifs** : R2 (agrégat exposable sans
seuil), la journalisation sans purge, et l'absence d'écran de supervision.
Ils bloquent la mise en service, pas le développement.

## 4. Règles d'usage des données

| Règle | Traduction technique | Contrôle |
|---|---|---|
| Les données brutes sont immuables | `data/raw/` n'est jamais modifié ; toute transformation écrit ailleurs | Tout supprimer sauf `raw/` et régénérer par `make data` |
| Ce qui n'est pas classé n'entre pas | Liste blanche de 9 colonnes sur la session prédite ; classement des 128 colonnes dans `configs/base.yaml` | `tests/data/test_variables_reference.py` — une colonne nouvelle fait échouer la chaîne |
| Aucune variable postérieure à la connaissance du candidat | Décalage d'une session pour 35 compteurs | `tests/data/test_features_build_antifuite.py`, 5 contrôles, vérifiés par mutation |
| Le genre ne sert qu'à l'audit | 4 colonnes classées `interdite` | même fichier de test |
| Un échec de qualité **bloque** | Contrôles à l'entrée de chaque étape | `tests/data/test_quality_run_blocage.py` |
| Aucune donnée simulée | Toute source publique, réelle, sous licence vérifiée | `registre-sources.md` et manifestes |
| Aucune donnée personnelle dans les journaux applicatifs | Distinct des journaux d'inférence, qui en contiennent par obligation | **Non implémenté** |

## 5. Politique de gestion des secrets

**Ce qui est en place et vérifié.**

| Mesure | Preuve |
|---|---|
| Aucun secret versionné | `.gitignore` exclut `.env`, `*.env`, `credentials*.json`, `*adminsdk*.json`, `*.pem`, `*.key`, `kubeconfig` ; exclusion vérifiée par `git check-ignore -v` sur des chemins réels |
| Toutes les variables documentées sans valeur | `.env.example`, valeurs factices uniquement |
| Aucun secret en dur dans le code | `src/` et `configs/` — les identifiants passent exclusivement par variables d'environnement, règle rappelée en tête de `configs/base.yaml` |
| Configuration externalisée | `src/edumatch/config.py`, typée, un fichier par environnement (ADR 0003) |

**Ce qui manque et que ce plan arrête.**

| Règle | Contenu |
|---|---|
| Rotation | Clé d'accès au fournisseur cloud et clé d'API du modèle de langage : **tous les 90 jours**, et immédiatement au départ de toute personne y ayant eu accès |
| Révocation | Un secret exposé, même brièvement, même dans un dépôt privé, est **révoqué avant d'être remplacé** — jamais l'inverse. Retirer le fichier du dépôt ne révoque rien : l'historique le conserve |
| Détection | Analyse de secrets en intégration continue, en échec bloquant. **Non implémentée** — l'intégration continue n'existe pas encore |
| Portée minimale | Une clé par environnement, jamais partagée entre développement et production |

## 6. Procédure d'audit

**Cadence.** Trois déclencheurs, dont deux calés sur le calendrier réel des
sources plutôt que sur un rythme administratif.

| Déclencheur | Date | Portée |
|---|---|---|
| Publication du millésime Parcoursup | Chaque année, à la publication (juillet à octobre selon les sessions) | Audit complet : les 12 points ci-dessous |
| Ouverture de la campagne | Chaque année, janvier | Fraîcheur des sources, dérive, revue de la matrice des risques |
| Changement substantiel | À l'événement | Nouvelle source, nouvelle variable, nouvelle finalité, changement de modèle, incident |

**Les douze points de contrôle, avec ce qui les prouve.** Un point sans
commande ni fichier est un point non auditable.

| # | Point contrôlé | Preuve attendue |
|---|---|---|
| 1 | Aucun secret versionné | `git check-ignore -v` sur les motifs réels ; analyse d'historique |
| 2 | Chaque source a une licence identifiée et à jour | `registre-sources.md` confronté aux manifestes |
| 3 | L'attribution est effective côté utilisateur | Écran « Sources et licences », avec dates |
| 4 | Chaque traitement a une base légale écrite | `registre-traitements.md` |
| 5 | Chaque durée de conservation a une **purge exécutée** | Journal d'exécution de la tâche de purge |
| 6 | Aucune variable de genre en entrée | `tests/data/test_features_build_antifuite.py` |
| 7 | Aucune fuite temporelle | `tests/data/test_variables_reference.py`, vérifié par mutation |
| 8 | Toute colonne de source est classée | même fichier |
| 9 | L'audit d'équité a été rejoué sur le modèle en service | Résultats chiffrés, ventilés, dans la Model Card |
| 10 | La calibration a été mesurée sur le millésime en service | Courbe et erreur de calibration attendue |
| 11 | Le taux d'écartement par les superviseurs est mesuré | Journal de supervision ; **un taux nul est un signal d'alerte**, pas un succès |
| 12 | Les seuils de k-anonymat sont appliqués aux restitutions | Contrôle automatisé sur l'agrégat exposé |

**Sortie de l'audit** : une entrée datée dans ce dossier, avec les points en
échec, leur responsable et leur date d'échéance. Un audit sans point en échec
sur douze est un audit qu'il faut refaire.

## 7. Procédure de mise à jour de la documentation

| Événement | Ce qui doit être mis à jour, dans cet ordre |
|---|---|
| Ajout d'une source | `registre-sources.md`, puis `registre-traitements.md`, puis `risques.md` |
| Ajout ou retrait d'une variable | `configs/base.yaml`, la décision d'architecture correspondante, la Model Card, l'analyse d'impact si l'équité est touchée |
| Nouveau modèle mis en service | Model Card, correspondance AI Act, `risques.md` |
| Changement de finalité | **Analyse d'impact rouverte avant toute mise en œuvre**, sans exception |
| Incident ou violation | Journal d'incident, notification sous 72 heures si la violation présente un risque pour les personnes, revue de `risques.md` |

**Règle de cohérence** : le dépôt fait foi. Si un document déclare un
composant que le code ne confirme pas, c'est le document qui est faux et qui
doit être corrigé — jamais l'inverse.

## 8. État de mise en œuvre, sans complaisance

| Élément du plan | État |
|---|---|
| Classification des données | **Écrite et appliquée** aux artefacts existants |
| Rôles et périmètres de décision | **Écrits** ; le superviseur humain n'a pas encore d'outil |
| Règles d'usage | **6 des 7 contrôlées automatiquement** |
| Secrets — exclusion et externalisation | **En place et vérifiées** |
| Secrets — rotation, révocation, détection | **Écrites, non outillées** |
| Procédure d'audit | **Écrite, jamais exécutée** — le premier audit complet suppose un modèle en service |
| Procédure de mise à jour | **Écrite, déjà appliquée** lors des corrections de chiffres |

---
*Étape E44 · rédigé le 2026-08-30.*
