# Correspondance avec le règlement européen sur l'intelligence artificielle

**Critère servi** : Bloc 1, 1.8 — livrable obligatoire · **Version** : 1.0 ·
**Date** : 2026-09-15 · **Portée** : articles 9 à 15, avec les articles 6, 16,
17, 19, 26 et 72 en appui.

> **Règle de lecture de ce document.** Une correspondance qui renverrait à une
> intention serait une correspondance vide. **Chaque ligne pointe vers un
> fichier, une commande ou un test de ce dépôt** — ou déclare que l'obligation
> n'est pas couverte. Trois statuts, et trois seulement :
>
> | Statut | Ce qu'il signifie |
> |---|---|
> | **Couvert** | Un composant existe, il est identifié, et il fait ce que l'article demande |
> | **Partiel** | Un composant existe mais ne couvre qu'une partie de l'obligation ; ce qui manque est nommé |
> | **Non couvert** | Rien n'existe. Je l'écris plutôt que de renvoyer à un projet |

---

## 1. Qualification du système

### 1.1 Le système relève de l'annexe III

L'annexe III, point 3, vise les systèmes d'IA destinés à être utilisés dans le
domaine de **l'éducation et de la formation professionnelle**, dont ceux
destinés à déterminer l'accès, l'admission ou l'affectation de personnes
physiques à des établissements d'enseignement.

**Je retiens la qualification de système à haut risque.** Trois raisons, dans
l'ordre où elles emportent la décision :

1. **L'objet du traitement est l'accès à l'enseignement supérieur.** Le système
   estime les chances d'admission d'une personne dans une formation et ordonne
   les formations sur cette base. C'est exactement la matière que le point 3
   vise, quelle que soit la qualification retenue pour l'acte final d'admission.
2. **L'effet sur la personne est réel, même sans décision.** Le système
   détermine l'ensemble des formations qu'un lycéen envisagera. Une formation
   qui ne remonte jamais dans une recommandation a autant de chances d'être
   candidatée qu'une formation refusée. Faire dépendre la qualification du seul
   moment formel de la décision reviendrait à laisser hors du règlement les
   systèmes qui agissent en amont, là où le choix se construit.
3. **La qualification ne se marchande pas au bénéfice du fournisseur.** En cas
   de doute sérieux sur une frontière, la position d'un délégué à la protection
   des données est la qualification la plus protectrice, pas la plus commode.

### 1.2 L'objection à laquelle il faut savoir répondre, et pourquoi elle ne tient pas

**L'objection** : « le système ne *détermine* pas l'admission ; ce sont les
établissements qui admettent, par Parcoursup, hors de ce système. Il n'entre
donc pas littéralement dans le point 3 ».

**La réponse** est dans l'article 6 §3 lui-même. Cet article permet, à
certaines conditions, de considérer qu'un système listé à l'annexe III ne
présente pas de risque important — notamment lorsqu'il accomplit une tâche
procédurale étroite, ou qu'il est purement préparatoire à une évaluation
humaine. Mais la dérogation comporte une **exclusion sans exception** : elle ne
s'applique jamais lorsque le système **effectue un profilage de personnes
physiques**.

Or ce système effectue un profilage au sens de l'article 4.4 du RGPD : il
traite des données personnelles à l'inférence pour évaluer des aspects
personnels — les chances d'admission — et l'analyse d'impact le reconnaît dès
sa première section. **La voie de la dérogation est donc fermée d'avance**, et
la discussion sur le caractère « préparatoire » du système n'a pas à être
tranchée : elle ne changerait rien au résultat.

C'est la façon la plus courte de fermer l'objection, et c'est celle que je
retiens.

### 1.3 Fournisseur et déployeur — le partage des responsabilités

| Qualité | Qui | Ce qu'elle emporte |
|---|---|---|
| **Fournisseur** | L'éditeur de la solution — le porteur de ce projet | Articles 9 à 15, 16, 17, 19, 72. La conception, la documentation, les essais, la journalisation, la mise sur le marché |
| **Déployeur** | L'établissement ou l'organisme d'orientation client | Article 26. Utiliser le système conformément à la notice, **assurer la supervision humaine par des personnes compétentes et dotées de l'autorité nécessaire**, informer les personnes concernées, conserver les journaux qu'il contrôle |

**Ce partage n'est pas cosmétique** : il décide qui répond d'une supervision
défaillante, qui informe le candidat, et qui produit l'analyse d'impact d'un
déploiement réel. La même répartition est portée par `registre-traitements.md`
§1, côté RGPD (responsable de traitement en exploitation = le déployeur ;
sous-traitant = l'éditeur).

**Conséquence directe sur ce dépôt** : les obligations du déployeur ne peuvent
pas être « implémentées » ici. Ce que le fournisseur doit lui fournir, en
revanche, doit exister — et c'est précisément la notice d'utilisation de
l'article 13, dont l'état est déclaré au §2.5 ci-dessous.

### 1.4 Calendrier — ce que je ne dirai pas devant un jury sans l'avoir vérifié

L'entrée en application du règlement est **échelonnée** : les dispositions ne
prennent pas toutes effet à la même date, et le calendrier des systèmes à haut
risque de l'annexe III est distinct de celui des pratiques interdites et de
celui des modèles à usage général.

**Je n'inscris aucune date dans ce document.** Toute affirmation de date en
soutenance doit être vérifiée sur le **texte consolidé, le jour de la
présentation** — un calendrier recopié de mémoire ou d'un article de presse est
exactement le genre d'affirmation qu'un juriste reprend. Ce qui est certain et
suffisant ici : le régime applicable est celui des systèmes à haut risque, et
la conformité se construit avant l'échéance, pas à l'échéance.

---

## 2. Articles 9 à 15 — obligation par obligation

### 2.1 Article 9 — Système de gestion des risques

**Ce que l'article demande** : un processus **itératif et continu** sur tout le
cycle de vie — identification et analyse des risques connus et raisonnablement
prévisibles pour la santé, la sécurité et les **droits fondamentaux**,
estimation des risques en usage normal et en mésusage raisonnablement
prévisible, adoption de mesures de gestion, essais. Une attention particulière
est due lorsque le système est susceptible d'affecter des **mineurs**.

| Exigence | Composant | Statut |
|---|---|---|
| Registre des risques identifiés et analysés | `risques.md` — 11 risques, structurés selon les quatre fonctions du cadre NIST AI RMF (gouverner, cartographier, mesurer, gérer), gravité appréciée **pour les personnes**, les risques d'organisation isolés et marqués comme tels | **Couvert** |
| Risques quantifiés plutôt qu'appréciés | R2 chiffré sur 1 929 179 lignes d'agrégat ; R3 mesuré par information mutuelle corrigée de la cardinalité ; R8 daté par quatre échéances vérifiées | **Couvert** |
| Mesures de gestion rattachées à un composant | Chaque risque renvoie à un fichier, un test ou une décision d'architecture ; ceux qui ne le font pas sont marqués « décrit, non traité » | **Couvert** |
| Attention particulière aux mineurs | `aipd.md` §7 — article 8 du RGPD, lisibilité de l'information, interdiction d'un public de moins de quinze ans sans réouverture de l'analyse | **Couvert sur le plan de l'analyse**, non outillé : rien dans le code ne contrôle l'âge, la date de naissance n'étant pas collectée |
| Processus **itératif**, révisé | Cadence écrite dans `plan-gouvernance.md` §6 : publication du millésime, ouverture de campagne, changement substantiel | **Partiel** — la cadence est écrite, **aucun cycle de révision n'a encore été exécuté**, faute de système en service |
| Essais en vue d'identifier les mesures les plus appropriées | `models/ablation.py` — sept variantes comparées sur la seule validation, dont la variante « sans les substituts du genre », qui **infirme** l'hypothèse qu'un retrait de variables réduirait l'écart | **Couvert** |
| Mésusage raisonnablement prévisible | `model-card.md` §2, six usages hors périmètre nommés et motivés | **Couvert** |
| Journal des incidents | — | **Non couvert.** Aucun registre d'incident n'existe |

### 2.2 Article 10 — Gouvernance des données

**Ce que l'article demande** : des jeux de données d'entraînement, de
validation et d'essai soumis à des pratiques de gouvernance appropriées —
choix de conception, collecte et origine, préparation, hypothèses formulées,
évaluation de la disponibilité et du caractère approprié, **examen des biais
possibles** affectant la santé, la sécurité ou les droits fondamentaux,
détection et correction de ces biais, identification des lacunes.

| Exigence | Composant | Statut |
|---|---|---|
| Origine et licence de chaque jeu | `registre-sources.md` — six sources, licence vérifiée **sur le texte** et non sur son résumé, volumétrie mesurée sur le fichier posé sur disque ; manifestes `data/raw/*/manifeste.json` faisant foi en cas de divergence | **Couvert** |
| Choix de conception et préparation | ADR 0009 (label), 0010 et 0013 (variables), 0012 (fenêtre temporelle), 0015 (grain du modèle en étoile) ; `01-donnees/label.md`, `04-modele/variables.md` | **Couvert** |
| Contrôles qualité, avec **blocage** | `src/edumatch/quality/` (Pandera, ADR 0014) — schéma, complétude, cohérence, fraîcheur. Un échec lève `ErreurQualiteBloquante`, rangée du côté définitif : la tâche échoue **sans reprise**, et aucune tâche en aval ne s'exécute. Démontré par `tests/data/test_quality_run_blocage.py` | **Couvert** |
| Lignage | Projet dbt, `dbt docs` ; `02-architecture/modele-etoile.md` | **Couvert** |
| **Examen des biais** | `04-modele/equite.md` — information mutuelle entre chaque variable candidate et le sexe des admis, **corrigée du nombre de modalités par permutation**. Sans cette correction, `cod_uai` aurait affiché un pouvoir explicatif proche du double de sa valeur réelle | **Couvert** |
| **Correction des biais** | Exclusion de `cod_uai` (28,9 %) et `ville_etab` (10,2 %) ; conservation assumée de `fili` (19,5 %), avec seuil de réouverture écrit ; audit a posteriori sur les prédictions | **Partiel, et je préfère le dire ainsi** : la mesure de l'ablation établit que le retrait des substituts **n'améliore pas** l'équité. La correction par exclusion de variables a atteint sa limite ; aucune correction plus profonde (repondération, contrainte d'équité à l'apprentissage) n'a été mise en œuvre |
| Traitement du genre | Quatre colonnes classées `interdite` dans `configs/base.yaml` ; contrôle par `tests/data/test_features_build_antifuite.py`, **vérifié par mutation** | **Couvert** |
| Représentativité | Fenêtre exploitable bornée à six sessions (2020-2025), motif écrit : le numérateur ventilé par type de baccalauréat n'existe pas avant 2020. Deux ruptures de série identifiées et déclarées **avant** toute mesure de performance : mentions 2020-2021, part de vœux boursiers | **Partiel** — la représentativité est établie sur la source, **pas sur la population du déployeur** : rien ne garantit que les lycéens d'un établissement donné se répartissent comme la population nationale |
| Identification des lacunes | `registre-traitements.md` §4 (trois lacunes), `risques.md`, `reste-a-faire.md` | **Couvert** |
| Pertinence des données de la source Sirene | La chaîne NAF ↔ ROME ↔ formation ne relie **aucune** formation Parcoursup ; Sirene n'entre pas dans le modèle | **Lacune déclarée**, pas un apport nul mesuré |

### 2.3 Article 11 et annexe IV — Documentation technique

**Ce que l'article demande** : une documentation technique établie **avant** la
mise sur le marché, tenue à jour, démontrant la conformité et permettant aux
autorités d'évaluer le système. Le contenu minimal est fixé par l'annexe IV.

Correspondance rubrique par rubrique — le dossier technique de ce projet
**existe, mais éclaté en plusieurs documents** ; cette table en est
l'équivalent de sommaire.

| Rubrique de l'annexe IV | Où elle se trouve | Statut |
|---|---|---|
| Description générale, finalité, versions, forme de mise à disposition | `model-card.md` §1 et §2 ; `00-vue-ensemble.md` | **Couvert** |
| Éléments et processus de développement, architecture, ressources de calcul | `02-architecture/`, `ARCHITECTURE_EduMatch.md`, ADR 0001 à 0018 | **Partiel** — la description de l'infrastructure de déploiement dépend de travaux d'industrialisation non achevés |
| Spécifications de conception, choix d'optimisation, arbitrages | Les dix-huit décisions d'architecture, chacune portant son alternative écartée et son seuil de réouverture | **Couvert** |
| Jeux de données : provenance, portée, caractéristiques, préparation | `registre-sources.md`, `01-donnees/sources.md`, `01-donnees/label.md`, `04-modele/variables.md` | **Couvert** |
| Évaluation des mesures de supervision humaine | `06-service/ecran-conseiller.md` ; `aipd.md` §6.4 | **Couvert** |
| Mesures de performance, exactitude, robustesse, **métriques par sous-population** | `model-card.md` §6 — 27 sous-populations ventilées ; `04-modele/evaluation.md` | **Couvert** |
| Système de gestion des risques | `risques.md` | **Couvert** |
| Modifications apportées au cours du cycle de vie | `avancement.md` et l'historique Git, chaque étape portant son commit | **Couvert** |
| Liste des normes harmonisées appliquées | — | **Non couvert.** Aucune norme harmonisée n'est appliquée ni revendiquée. Les référentiels mobilisés (NIST AI RMF pour la structure des risques, ISO/IEC 42001 comme horizon de système de management, ISO/IEC 27001 pour la sécurité) sont **des cadres de travail, pas des normes harmonisées au sens du règlement** — les confondre serait une faute |
| Déclaration UE de conformité | — | **Non couvert.** Le système n'est pas mis sur le marché |

**Ce qui manque réellement** : non pas le contenu, mais sa **forme
consolidée**. Un évaluateur externe doit aujourd'hui parcourir une douzaine de
documents. Un dossier technique unique reprenant l'ordre de l'annexe IV reste à
assembler ; cette table en est le sommaire provisoire.

### 2.4 Article 12 — Enregistrement (journalisation)

**Ce que l'article demande** : que le système permette l'enregistrement
automatique d'événements (« journaux ») tout au long de son cycle de vie, avec
un niveau de traçabilité adapté à la destination du système.

| Exigence | Composant | Statut |
|---|---|---|
| Enregistrement automatique des inférences | `src/edumatch/api/audit.py` — écriture dans un registre dédié (`processed/audit/journal.jsonl`), **distinct des journaux applicatifs**, et non dans une sortie standard consultable par quiconque accède au service | **Couvert** |
| Contenu permettant la traçabilité | Horodatage, identifiant technique de requête, **version du modèle et empreinte du commit Git**, variables d'entrée, score produit, facteurs explicatifs restitués | **Couvert** |
| Traçabilité de la supervision | Champ `decision_conseiller` présent dans la structure, **toujours nul à l'écriture** : la décision du conseiller est journalisée séparément par `feedback_store.py`, sans identifiant commun | **Partiel — les deux traces ne se corrèlent pas.** Une décision de conseiller n'est pas rattachable à l'inférence qui l'a motivée |
| Journalisation du pipeline de données | Tâches d'orchestration journalisées ; contrôles qualité produisant un rapport | **Couvert pour l'exploitation**, hors du champ propre de l'article 12 qui vise les événements du système d'IA |

#### La tension entre l'article 12 et la limitation de conservation — et comment elle est tranchée

**L'article 12 impose de journaliser**, et l'article 19 impose au fournisseur de
**conserver** les journaux pendant une durée appropriée, d'au moins six mois,
sauf disposition contraire du droit de l'Union ou national. **L'article 5.1.e
du RGPD impose au contraire de limiter la durée de conservation.** Une
obligation de plancher face à une obligation de plafond : les deux textes se
contredisent frontalement, et aucun des deux ne cède au seul motif qu'il est
gênant.

**La conciliation retenue — trois paliers datés, et surtout exécutés** :

| Palier | Durée | Ce qui est conservé | Ce que cela permet |
|---|---|---|---|
| 1 — clair | 0 à 12 mois | Entrées, sortie, version, horodatage | Répondre à une réclamation, rejouer une inférence contestée. Couvre le plancher de six mois **et** une campagne Parcoursup entière |
| 2 — pseudonymisé | 12 à 36 mois | Identifiant de requête remplacé par un jeton neuf, variables conservées | Audit d'équité et détection de dérive restent possibles ; **le lien avec une personne est rompu** |
| 3 — agrégats | au-delà de 36 mois | Distributions et métriques par sous-population | Capacité de démonstration historique sans identification |

**Trois précisions qui font la différence entre une décision et une intention.**

1. **La pseudonymisation jette l'original.** Un hachage avec secret aurait été
   techniquement réversible tant que le secret existe quelque part : plus
   complexe, pour une garantie plus faible qu'un identifiant qui n'existe
   simplement plus.
2. **La purge est exécutable et testée** (`src/edumatch/api/audit_purge.py`) :
   mode simulation par défaut, mode réel sur option explicite, **idempotente**
   (rejouer la purge à la même date ne change rien — démontré par test, pas
   supposé), chaque passage journalisant ses compteurs dans
   `processed/audit/purges.jsonl`.
3. **La purge est planifiée** : DAG `edumatch_audit_purge`, appelant
   `orchestration/taches.py::purger_audit`, qui passe `simulation=False`
   **explicitement** — une tâche planifiée qui se contenterait du mode par
   défaut ne purgerait jamais rien, et c'est exactement ce piège que la tâche
   referme.

**Ce qui n'est pas couvert** : le journal de supervision (T6) **n'a pas de
purge**, faute d'identifiant commun avec le journal d'inférence. C'est un motif
de blocage actif de l'analyse d'impact (§8.4, motif B).

### 2.5 Article 13 — Transparence et information des déployeurs

**Ce que l'article demande** : un fonctionnement suffisamment transparent pour
que le déployeur interprète les sorties et les utilise de façon appropriée, et
une **notice d'utilisation** concise, complète, exacte et claire, indiquant
notamment les caractéristiques, capacités et **limites de performance** du
système, son niveau d'exactitude **y compris pour les groupes de personnes
concernés**, les circonstances pouvant conduire à des risques, et les mesures
de supervision humaine.

| Exigence | Composant | Statut |
|---|---|---|
| Limites de performance déclarées | `model-card.md` §6 et §9 — le fait que le modèle ne batte pas sa règle de référence en test est **la première phrase du document**, pas une note de bas de page | **Couvert** |
| Niveau d'exactitude **par groupe** | `model-card.md` §6.2 à §6.5 — 27 sous-populations, MAE et ECE, comparées à la règle de référence | **Couvert** |
| Circonstances conduisant à un risque | `model-card.md` §9.1 à §9.4 ; `aipd.md` §6 | **Couvert** |
| Transparence à l'usage, dans le produit | La mise en garde sur le modèle est portée par **chaque réponse de `/matching`** (`MISE_EN_GARDE_ACCESSIBILITE`), et affichée à l'écran — pas seulement écrite dans la documentation. L'indisponibilité du terme de débouchés est affichée **avec son motif** pour les 98,6 % de formations concernées | **Couvert** |
| Restitution des facteurs | TreeSHAP précalculé, exposé par `/explain`, affiché à côté du score | **Couvert** |
| **Notice d'utilisation destinée au déployeur**, en tant que document distinct | La Model Card en porte l'essentiel du contenu, mais aucune notice adressée au déployeur, couvrant l'installation, la maintenance, la durée de vie attendue et les ressources nécessaires, n'est rédigée | **Partiel** |
| **Information de la personne concernée** — le candidat | — | **Non couvert.** Aucune notice destinée au candidat n'existe, ni en français simple, ni du tout. C'est aussi un manquement aux articles 12 à 14 du RGPD, et un motif de blocage actif (`aipd.md` §8.4, motif C) |
| Attribution des sources, exigée par leur licence | — | **Non couvert.** La Licence Ouverte v2.0 impose paternité **et date de dernière mise à jour** ; aucun écran ne les porte, alors que les manifestes d'ingestion contiennent déjà toute l'information nécessaire |

### 2.6 Article 14 — Contrôle humain

**Ce que l'article demande** : un système conçu de manière à pouvoir être
**effectivement** supervisé par des personnes physiques, de façon à prévenir ou
réduire les risques. Les personnes chargées de la supervision doivent pouvoir
comprendre les capacités et les limites du système, rester conscientes du
**biais d'automatisation**, interpréter correctement les sorties, décider de ne
pas l'utiliser, et **intervenir ou interrompre** le fonctionnement.

| Exigence | Composant | Statut |
|---|---|---|
| Comprendre les capacités et les limites | L'écran affiche la réserve sur le modèle et l'indisponibilité des débouchés ; `model-card.md` détaille | **Couvert** |
| Interpréter correctement les sorties | Facteurs explicatifs présentés à côté du score ; l'estimation est présentée comme portant sur une catégorie, non sur la personne | **Couvert** |
| **Décider de ne pas utiliser, écarter** | `src/edumatch/api/static/` et `routes/feedback.py` — écartement **avec motif obligatoire, bloqué côté client et côté serveur**. La double validation est ce qui empêche un contournement de rendre le contrôle cosmétique | **Couvert** |
| Trace de l'intervention | Décision, motif en texte libre, horodatage, identifiant de conseiller (`feedback_store.py`) | **Couvert sur l'écriture**, non corrélé au journal d'inférence |
| Conscience du biais d'automatisation | Avis d'assistance affiché en tête d'écran, rappelant que le conseiller reste seul décisionnaire ; consigne explicite sur le champ libre (« ne consignez aucune information de santé, de situation familiale ou d'origine ») | **Couvert** |
| **Effectivité démontrable** de la supervision | — | **Non couvert.** Aucun tableau de bord du **taux d'écartement**. Un contrôle humain qui n'écarterait jamais rien resterait invisible à l'échelle de l'organisation. Un taux nul sur une campagne est un signal d'alerte, pas un succès — encore faut-il pouvoir l'observer |
| **Imputabilité** de la supervision | — | **Non couvert.** L'identifiant du conseiller est **déclaratif** : aucune authentification. Une trace de supervision non imputable ne démontre rien. Motif de blocage actif (`aipd.md` §8.4, motif A) |

**Le jugement d'ensemble, sans complaisance** : le dispositif de contrôle humain
**existe** et il est bien conçu — c'est un vrai progrès par rapport à l'état
antérieur du projet, où rien n'existait. Mais l'article 14 demande un contrôle
**effectif**, et l'effectivité se démontre par deux choses qui manquent :
savoir qui a supervisé, et savoir combien de fois la supervision a contredit le
système.

### 2.7 Article 15 — Exactitude, robustesse et cybersécurité

**Ce que l'article demande** : un niveau approprié d'exactitude, de robustesse
et de cybersécurité, constant sur tout le cycle de vie ; la **déclaration des
niveaux d'exactitude et des métriques** dans la notice d'utilisation ; la
résilience aux erreurs, défaillances et incohérences ; l'attention portée aux
**boucles de rétroaction** des systèmes qui continuent d'apprendre ; la
résistance aux tentatives d'altération des données ou du modèle.

#### Exactitude

| Exigence | Composant | Statut |
|---|---|---|
| Protocole d'évaluation sans fuite | Split **strictement temporel** (ADR 0012) ; liste blanche de 9 colonnes sur la session prédite, 35 décalées, 73 exclusions motivées ; test anti-fuite **vérifié par mutation** — ramener le décalage de +1 à 0 fait échouer 4 tests et en laisse 342 verts | **Couvert** |
| Plancher mesuré avant d'entraîner | `models/baseline.py` — meilleure de trois règles triviales, mesurée **avant** l'entraînement, seuil de réussite écrit d'avance | **Couvert** |
| Métriques adaptées, dont **calibration** | `models/evaluate.py` — MAE pondérée et ECE sur 10 tranches | **Couvert** |
| Niveaux d'exactitude **déclarés** | `model-card.md` §6 | **Couvert** |
| Niveau d'exactitude **approprié** | MAE 0,0758 contre 0,0701 pour la règle de référence, ECE 0,0371 contre 0,0322, sur le test 2025 | **Non satisfait.** Le système n'atteint pas, sur la session la plus récente, le niveau d'une règle de dénombrement. C'est le fondement de l'avis défavorable rendu sur ce terme (`aipd.md` §3.1 et §8.3) |

#### Robustesse

| Exigence | Composant | Statut |
|---|---|---|
| Résilience aux erreurs et aux incohérences | Vocabulaire commun `ErreurTransitoire` / `ErreurDefinitive` (ADR 0006) ; reprise décidée par `orchestration/reprise.py` et **non** par le mécanisme de reprise natif de l'ordonnanceur, qui retenterait aveuglément une erreur définitive comme un schéma cassé | **Couvert** |
| Dégradation explicite, jamais de panne totale ni de zéro silencieux | Stock Sirene manquant : le service démarre, chaque formation porte le statut de chaîne rompue **avec son motif**. Assistant documentaire sans clé : aucun appel réseau tenté ; avec clé mais appel en échec : réponse en mode extractif, avec un avertissement qui nomme la panne. Catalogue trop grand : **erreur 422 explicite**, jamais une troncature invisible | **Couvert** |
| Idempotence | Ingestion à écriture atomique (fichier `.part` renommé à la fin) ; purge idempotente ; tâches d'orchestration idempotentes, testées | **Couvert** |
| **Boucles de rétroaction** | `aipd.md` §6.3 et `risques.md` R4 : risque identifié, cause nommée (le dénominateur du label est la grandeur que le système influence) ; `models/derive.py` suit la distribution des prédictions d'une session à l'autre | **Partiel.** L'instrument existe, sa référence est la distribution d'entraînement, pas une population post-déploiement, qui n'existe pas. Le seuil retenu n'aurait **pas** détecté la dégradation validation → test — écrit dans l'ADR 0018, pas dissimulé |
| Le système n'apprend pas en continu | L'entraînement est une tâche de lot, déclenchée sur un millésime publié ; aucune mise à jour en ligne à partir des inférences | **Couvert**, et c'est une réduction de risque structurelle : la boucle de rétroaction ne peut pas se refermer en quelques heures |

#### Cybersécurité

| Exigence | Composant | Statut |
|---|---|---|
| Aucun secret dans le dépôt | `.gitignore` excluant `.env`, `*.env`, `credentials*.json`, `*adminsdk*.json`, `*.pem`, `*.key`, `kubeconfig`, exclusion **vérifiée sur des chemins réels** ; `.env.example` à valeurs factices ; configuration externalisée et typée | **Couvert** |
| Prévention de l'injection dans l'interface | Rendu par `textContent` et `createElement`, **jamais** `innerHTML` : la classe d'attaque est éliminée à la source plutôt que confiée à un échappement qu'on oublierait une fois. Vérifié par `tests/unit/test_ecran_accessibilite.py` | **Couvert** |
| Validation des entrées de l'API | Schémas Pydantic ; plafonds explicites ; erreurs typées (`api/errors.py`) | **Couvert** |
| **Contrôle d'accès** | — | **Non couvert.** Aucune authentification sur l'écran ni sur les routes. Motif de blocage actif |
| **Chiffrement au repos et en transit, cloisonnement par rôles** | — | **Non couvert.** Ces mesures relèvent du code d'infrastructure, qui n'est pas encore écrit |
| Rotation et révocation des secrets | Politique écrite (`plan-gouvernance.md` §5 : rotation à 90 jours, révocation **avant** remplacement, portée minimale par environnement) | **Partiel** — écrite, non outillée ; l'analyse de secrets en intégration continue n'existe pas |
| Résistance à l'empoisonnement des données ou du modèle | Contrôles qualité bloquants et empreintes SHA-256 à l'ingestion ; aucun test adverse conduit | **Partiel** |

---

## 3. Les articles voisins, en appui

| Article | Objet | État |
|---|---|---|
| **6 §3** | Dérogation possible pour un système de l'annexe III sans risque important | **Écartée par le texte lui-même** : la dérogation ne s'applique jamais à un système qui effectue un profilage de personnes physiques. Voir §1.2 |
| **16** | Obligations générales du fournisseur | Portées par les articles 9 à 15 ci-dessus ; marquage et déclaration de conformité **non couverts**, le système n'étant pas mis sur le marché |
| **17** | Système de management de la qualité | **Partiel.** Le plan de gouvernance, la politique de tests, la définition de terminé et la discipline de commit en portent des éléments ; aucun système de management formalisé, au sens d'ISO/IEC 42001, n'est en place — et je ne le présente pas comme tel |
| **19** | Conservation des journaux par le fournisseur | **Couvert** — palier 1 à 12 mois, au-delà du plancher de six mois. Voir §2.4 |
| **26** | Obligations du déployeur | **Hors de ce dépôt par nature.** Ce que le fournisseur doit lui remettre — la notice d'utilisation — est **partiel** (§2.5) |
| **72** | Surveillance après commercialisation | **Non couvert.** Aucun plan de surveillance après commercialisation n'est établi. `models/derive.py` en serait l'instrument technique, il n'en est pas le plan |

---

## 4. Synthèse — ce qui est prouvé, ce qui ne l'est pas

| Article | Statut d'ensemble |
|---|---|
| 9 — Gestion des risques | **Couvert**, sauf le journal d'incident et l'exécution effective d'un cycle de révision |
| 10 — Gouvernance des données | **Couvert**, avec deux limites déclarées : correction des biais parvenue au bout de ce que l'exclusion de variables permet, et représentativité non établie sur la population du déployeur |
| 11 — Documentation technique | **Couvert sur le fond, partiel sur la forme** : le contenu de l'annexe IV existe, éclaté ; le dossier consolidé reste à assembler |
| 12 — Journalisation | **Couvert pour l'inférence**, purge exécutable, testée, planifiée. **Non couvert pour la trace de supervision** |
| 13 — Transparence | **Couvert vers le déployeur** ; **non couvert vers la personne concernée** et sur l'attribution des sources |
| 14 — Contrôle humain | **Dispositif couvert, effectivité non démontrable** : ni imputabilité, ni mesure du taux d'écartement |
| 15 — Exactitude, robustesse, cybersécurité | **Robustesse couverte. Exactitude mesurée et insuffisante. Cybersécurité largement non couverte** |

**Les cinq obligations qu'il faut savoir citer comme non couvertes**, parce
qu'un jury les trouvera de toute façon :

1. aucune information de la personne concernée — ni notice candidat, ni
   attribution des sources ;
2. aucun contrôle d'accès, donc aucune imputabilité de la supervision ;
3. aucune purge du journal de supervision ;
4. aucun plan de surveillance après commercialisation, ni journal d'incident ;
5. un niveau d'exactitude inférieur à celui d'une règle de dénombrement sur la
   session la plus récente.

Les quatre premières sont des manques d'outillage, rattrapables. **La
cinquième est un fait sur le modèle**, et c'est elle qui porte l'avis
défavorable rendu sur le terme appris (`aipd.md` §8.3).

---
*Étape E43 · version 1.0 du 2026-09-15 · chaque ligne pointe vers un composant
existant ou déclare l'absence ; aucune date d'entrée en application n'est
affirmée ici.*
