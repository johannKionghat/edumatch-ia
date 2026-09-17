# Correspondance avec le règlement européen sur l'intelligence artificielle

**Critère servi** : Bloc 1, 1.8, livrable obligatoire · **Version** : 1.0 ·
**Date** : 2026-09-15 · **Portée** : articles 9 à 15, avec les articles 6, 16,
17, 19, 26 et 72 en appui.

Règle de lecture : une correspondance qui renverrait à une intention ne
servirait à rien. Chaque ligne pointe vers un fichier, une commande ou un test
de ce dépôt, ou déclare que l'obligation n'est pas couverte.

| Statut | Ce qu'il signifie |
|---|---|
| Couvert | Un composant existe, identifié, qui fait ce que l'article demande |
| Partiel | Un composant existe mais ne couvre qu'une partie de l'obligation, ce qui manque est nommé |
| Non couvert | Rien n'existe, je l'écris plutôt que de renvoyer à un projet |

---

## 1. Qualification du système

### 1.1 Le système relève de l'annexe III

L'annexe III, point 3, vise les systèmes d'IA destinés à l'éducation et à la
formation professionnelle, dont ceux destinés à déterminer l'accès,
l'admission ou l'affectation de personnes physiques à des établissements
d'enseignement.

Je retiens la qualification de système à haut risque, pour trois raisons.
L'objet du traitement est l'accès à l'enseignement supérieur : le système
estime les chances d'admission d'une personne et ordonne les formations sur
cette base, c'est la matière que le point 3 vise, quelle que soit la
qualification de l'acte final d'admission. L'effet sur la personne est réel,
même sans décision : le système détermine l'ensemble des formations qu'un
lycéen envisagera, une formation qui ne remonte jamais dans une
recommandation a autant de chances d'être candidatée qu'une formation
refusée. La qualification ne se marchande pas au bénéfice du fournisseur : en
cas de doute sérieux sur une frontière, je retiens la qualification la plus
protectrice.

### 1.2 L'objection à laquelle il faut savoir répondre

L'objection : le système ne détermine pas l'admission, ce sont les
établissements qui admettent, par Parcoursup, hors de ce système, il
n'entrerait donc pas dans le point 3.

La réponse est dans l'article 6 §3 : cet article permet, à certaines
conditions, de considérer qu'un système listé à l'annexe III ne présente pas
de risque important, notamment pour une tâche procédurale étroite ou
purement préparatoire à une évaluation humaine. Mais la dérogation comporte
une exclusion sans exception : elle ne s'applique jamais lorsque le système
effectue un profilage de personnes physiques. Or ce système effectue un
profilage au sens de l'article 4.4 du RGPD, il traite des données
personnelles à l'inférence pour évaluer des chances d'admission, et l'AIPD le
reconnaît dès sa première section. La voie de la dérogation est fermée
d'avance.

### 1.3 Fournisseur et déployeur, le partage des responsabilités

| Qualité | Qui | Ce qu'elle emporte |
|---|---|---|
| Fournisseur | L'éditeur de la solution, le porteur de ce projet | Articles 9 à 15, 16, 17, 19, 72 : conception, documentation, essais, journalisation, mise sur le marché |
| Déployeur | L'établissement ou l'organisme d'orientation client | Article 26 : utiliser conformément à la notice, assurer la supervision humaine par des personnes compétentes, informer les personnes concernées, conserver les journaux qu'il contrôle |

Ce partage décide qui répond d'une supervision défaillante, qui informe le
candidat, et qui produit l'AIPD d'un déploiement réel. La même répartition
est portée par `registre-traitements.md` §1, côté RGPD. Conséquence pour ce
dépôt : les obligations du déployeur ne peuvent pas être « implémentées »
ici. Ce que le fournisseur doit lui fournir, la notice d'utilisation de
l'article 13, doit exister, son état est déclaré au §2.5.

### 1.4 Calendrier

L'entrée en application du règlement est échelonnée, le calendrier des
systèmes à haut risque de l'annexe III étant distinct de celui des pratiques
interdites et des modèles à usage général. Je n'inscris aucune date dans ce
document : toute affirmation de date en soutenance doit être vérifiée sur le
texte consolidé le jour de la présentation. Ce qui est certain ici : le
régime applicable est celui des systèmes à haut risque, et la conformité se
construit avant l'échéance.

---

## 2. Articles 9 à 15, obligation par obligation

### 2.1 Article 9, système de gestion des risques

Un processus itératif sur tout le cycle de vie : identification et analyse
des risques pour la santé, la sécurité et les droits fondamentaux, en usage
normal et en mésusage prévisible, mesures de gestion, essais, attention aux
mineurs.

| Exigence | Composant | Statut |
|---|---|---|
| Registre des risques identifiés et analysés | `risques.md`, 11 risques selon le cadre NIST AI RMF, gravité appréciée pour les personnes, risques d'organisation isolés | Couvert |
| Risques quantifiés | R2 chiffré sur 1 929 179 lignes d'agrégat, R3 mesuré par information mutuelle corrigée, R8 daté par quatre échéances vérifiées | Couvert |
| Mesures de gestion rattachées à un composant | Chaque risque renvoie à un fichier, un test ou une décision d'architecture | Couvert |
| Attention particulière aux mineurs | `aipd.md` §7, article 8 RGPD, lisibilité, interdiction d'un public de moins de quinze ans sans réouverture | Couvert sur l'analyse, non outillé, rien dans le code ne contrôle l'âge |
| Processus itératif, révisé | Cadence écrite dans `plan-gouvernance.md` §6 | Partiel, aucun cycle de révision exécuté, faute de système en service |
| Essais pour identifier les mesures appropriées | `models/ablation.py`, sept variantes comparées, dont « sans les substituts du genre », qui infirme l'hypothèse d'un retrait de variables efficace | Couvert |
| Mésusage raisonnablement prévisible | `model-card.md` §2, six usages hors périmètre nommés et motivés | Couvert |
| Journal des incidents | | Non couvert |

### 2.2 Article 10, gouvernance des données

Des jeux de données soumis à des pratiques de gouvernance appropriées :
choix de conception, collecte, préparation, hypothèses, disponibilité,
examen des biais, correction, identification des lacunes.

| Exigence | Composant | Statut |
|---|---|---|
| Origine et licence de chaque jeu | `registre-sources.md`, six sources, licence vérifiée, volumétrie mesurée sur le fichier posé sur disque, manifestes faisant foi | Couvert |
| Choix de conception et préparation | ADR 0009, 0010, 0013, 0012, 0015, `01-donnees/label.md`, `04-modele/variables.md` | Couvert |
| Contrôles qualité, avec blocage | `src/edumatch/quality/` (Pandera, ADR 0014), un échec lève `ErreurQualiteBloquante`, démontré par test | Couvert |
| Lignage | Projet dbt, `dbt docs`, `02-architecture/modele-etoile.md` | Couvert |
| Examen des biais | `04-modele/equite.md`, information mutuelle corrigée par permutation, sans quoi `cod_uai` afficherait un pouvoir explicatif proche du double de sa valeur réelle | Couvert |
| Correction des biais | Exclusion de `cod_uai` (28,9 %) et `ville_etab` (10,2 %), conservation assumée de `fili` (19,5 %) avec seuil de réouverture | Partiel, l'ablation établit que le retrait des substituts n'améliore pas l'équité, aucune correction plus profonde tentée |
| Traitement du genre | Quatre colonnes classées `interdite`, contrôlé par mutation | Couvert |
| Représentativité | Fenêtre bornée à six sessions, motif écrit, deux ruptures de série identifiées | Partiel, établie sur la source, pas sur la population du déployeur |
| Identification des lacunes | `registre-traitements.md` §4, `risques.md` | Couvert |
| Pertinence de la source Sirene | La chaîne NAF/ROME/formation ne relie aucune formation Parcoursup, Sirene n'entre pas dans le modèle | Lacune déclarée, pas un apport nul mesuré |

### 2.3 Article 11 et annexe IV, documentation technique

Une documentation technique établie avant la mise sur le marché, tenue à
jour, dont le contenu minimal est fixé par l'annexe IV. Le dossier existe,
éclaté en plusieurs documents ; cette table en est le sommaire.

| Rubrique de l'annexe IV | Où | Statut |
|---|---|---|
| Description générale, finalité, versions | `model-card.md` §1-2, `ARCHITECTURE_EduMatch.md` | Couvert |
| Développement, architecture, ressources de calcul | `02-architecture/`, ADR 0001 à 0018 | Partiel, description de l'infrastructure de déploiement dépendante de travaux non achevés |
| Spécifications de conception, arbitrages | Les dix-huit ADR, chacune avec alternative écartée et seuil de réouverture | Couvert |
| Jeux de données : provenance, portée, préparation | `registre-sources.md`, `01-donnees/sources.md`, `01-donnees/label.md` | Couvert |
| Évaluation de la supervision humaine | `06-service/ecran-conseiller.md`, `aipd.md` §6.4 | Couvert |
| Performance, exactitude, métriques par sous-population | `model-card.md` §6, 27 sous-populations | Couvert |
| Système de gestion des risques | `risques.md` | Couvert |
| Modifications au cours du cycle de vie | Historique Git et ADR datés | Couvert |
| Normes harmonisées appliquées | | Non couvert, aucune revendiquée, NIST AI RMF, ISO/IEC 42001, ISO/IEC 27001 sont des cadres de travail |
| Déclaration UE de conformité | | Non couvert, le système n'est pas mis sur le marché |

Ce qui manque n'est pas le contenu, mais sa forme consolidée : un dossier
technique unique reprenant l'ordre de l'annexe IV reste à assembler.

### 2.4 Article 12, journalisation

Que le système permette l'enregistrement automatique d'événements, avec un
niveau de traçabilité adapté.

| Exigence | Composant | Statut |
|---|---|---|
| Enregistrement automatique des inférences | `api/audit.py`, écriture dans `processed/audit/journal.jsonl`, distinct des journaux applicatifs | Couvert |
| Contenu permettant la traçabilité | Horodatage, identifiant de requête, version du modèle et empreinte de commit, variables d'entrée, score, facteurs explicatifs | Couvert |
| Traçabilité de la supervision | Champ `decision_conseiller` toujours nul à l'écriture, décision journalisée séparément par `feedback_store.py` sans identifiant commun | Partiel, les deux traces ne se corrèlent pas |
| Journalisation du pipeline de données | Tâches d'orchestration journalisées, contrôles qualité produisant un rapport | Couvert, hors du champ propre de l'article |

**La tension entre l'article 12 et la limitation de conservation.** L'article
19 impose au fournisseur de conserver les journaux au moins six mois, l'
article 5.1.e du RGPD impose de limiter la conservation : une obligation de
plancher face à une obligation de plafond. Je concilie en trois paliers
exécutés :

| Palier | Durée | Contenu | Ce que cela permet |
|---|---|---|---|
| 1, clair | 0-12 mois | Entrées, sortie, version, horodatage | Répondre à une réclamation, rejouer une inférence contestée, au-delà du plancher de six mois |
| 2, pseudonymisé | 12-36 mois | Identifiant remplacé par un jeton, variables conservées | Audit d'équité et dérive, sans lien avec une personne |
| 3, agrégats | au-delà de 36 mois | Distributions par sous-population | Démonstration historique sans identification |

Trois précisions. La pseudonymisation jette l'original (un hachage avec
secret aurait été techniquement réversible tant que le secret existe). La
purge est exécutable et testée (`api/audit_purge.py`, simulation par défaut,
mode réel sur option, idempotente, journalisée dans `purges.jsonl`). La
purge est planifiée par le DAG `edumatch_audit_purge`, qui passe
`simulation=False` explicitement. Ce qui n'est pas couvert : le journal de
supervision (T6) n'a pas de purge, faute d'identifiant commun, motif de
blocage actif (`aipd.md` §8.4, motif B).

### 2.5 Article 13, transparence et information des déployeurs

Un fonctionnement suffisamment transparent pour que le déployeur interprète
les sorties, et une notice indiquant caractéristiques, limites, exactitude
par groupe, circonstances à risque et mesures de supervision.

| Exigence | Composant | Statut |
|---|---|---|
| Limites de performance déclarées | `model-card.md` §6 et §9, le fait que le modèle ne bat pas la référence ouvre le document | Couvert |
| Niveau d'exactitude par groupe | `model-card.md` §6.2-6.5, 27 sous-populations | Couvert |
| Circonstances conduisant à un risque | `model-card.md` §9.1-9.4, `aipd.md` §6 | Couvert |
| Transparence à l'usage, dans le produit | Mise en garde portée par chaque réponse de `/matching`, indisponibilité des débouchés affichée avec son motif | Couvert |
| Restitution des facteurs | TreeSHAP précalculé, exposé par `/explain` | Couvert |
| Notice destinée au déployeur, document distinct | La Model Card en porte l'essentiel, mais aucune notice d'installation et de maintenance rédigée | Partiel |
| Information de la personne concernée | | Non couvert, aucune notice candidat, motif de blocage C |
| Attribution des sources, exigée par leur licence | | Non couvert, la Licence Ouverte impose paternité et date, aucun écran ne les porte |

### 2.6 Article 14, contrôle humain

Un système conçu pour être effectivement supervisé, où les superviseurs
comprennent les capacités et limites, restent conscients du biais
d'automatisation, interprètent les sorties, décident de ne pas l'utiliser, et
peuvent interrompre le fonctionnement.

| Exigence | Composant | Statut |
|---|---|---|
| Comprendre les capacités et limites | L'écran affiche la réserve et l'indisponibilité des débouchés | Couvert |
| Interpréter correctement les sorties | Facteurs à côté du score, estimation présentée comme portant sur une catégorie | Couvert |
| Décider de ne pas utiliser, écarter | `routes/feedback.py`, écartement motivé, bloqué client et serveur | Couvert |
| Trace de l'intervention | Décision, motif, horodatage, identifiant de conseiller | Couvert sur l'écriture, non corrélé au journal d'inférence |
| Conscience du biais d'automatisation | Avis d'assistance affiché, consigne sur le champ libre | Couvert |
| Effectivité démontrable de la supervision | Panneau Grafana des décisions `/feedback` sur 24 heures | Partiel, décisions comptées, aucun taux d'écartement calculé |
| Imputabilité de la supervision | `api/auth.py`, HTTP Basic sur `POST /feedback` | Partiel, compte conseiller partagé non nominatif, motif de blocage A |

Le dispositif de contrôle humain existe et est bien conçu, un vrai progrès.
L'article 14 demande un contrôle effectif, l'effectivité se démontre par
deux choses encore incomplètes : savoir quelle personne a supervisé (le
compte est partagé), et quelle part des recommandations la supervision a
contredite (les décisions sont comptées, le taux n'est pas calculé).

### 2.7 Article 15, exactitude, robustesse et cybersécurité

Un niveau approprié d'exactitude, robustesse et cybersécurité, constant sur
le cycle de vie, résilience aux erreurs, attention aux boucles de
rétroaction, résistance à l'altération.

**Exactitude**

| Exigence | Composant | Statut |
|---|---|---|
| Protocole d'évaluation sans fuite | Split temporel (ADR 0012), liste blanche de 9 colonnes, 35 décalées, test anti-fuite vérifié par mutation | Couvert |
| Plancher mesuré avant d'entraîner | `models/baseline.py`, meilleure de trois règles triviales, seuil écrit d'avance | Couvert |
| Métriques adaptées, dont calibration | `models/evaluate.py`, MAE pondérée et ECE sur 10 tranches | Couvert |
| Niveaux d'exactitude déclarés | `model-card.md` §6 | Couvert |
| Niveau d'exactitude approprié | MAE 0,0758 contre 0,0701 pour la référence, ECE 0,0371 contre 0,0322 | Non satisfait, fondement de l'avis défavorable rendu sur ce terme |

**Robustesse**

| Exigence | Composant | Statut |
|---|---|---|
| Résilience aux erreurs et incohérences | `ErreurTransitoire` / `ErreurDefinitive` (ADR 0006), reprise décidée par `orchestration/reprise.py` | Couvert |
| Dégradation explicite, jamais de panne totale ni de zéro silencieux | Stock Sirene manquant : chaque formation porte un statut de chaîne rompue avec motif. Assistant sans clé : aucun appel tenté. Catalogue trop grand : erreur 422 explicite | Couvert |
| Idempotence | Écriture atomique, purge idempotente, tâches d'orchestration testées | Couvert |
| Boucles de rétroaction | `aipd.md` §6.3, `risques.md` R4, `models/derive.py` suit la distribution des prédictions | Partiel, la référence de mesure est la distribution d'entraînement, pas post-déploiement |
| Le système n'apprend pas en continu | Entraînement en tâche de lot, aucune mise à jour en ligne | Couvert, réduction de risque structurelle |

**Cybersécurité**

| Exigence | Composant | Statut |
|---|---|---|
| Aucun secret dans le dépôt | `.gitignore`, `.env.example` à valeurs factices, configuration externalisée | Couvert |
| Prévention de l'injection dans l'interface | Rendu par `textContent` et `createElement`, jamais `innerHTML` | Couvert |
| Validation des entrées de l'API | Schémas Pydantic, plafonds explicites, erreurs typées | Couvert |
| Contrôle d'accès | `api/auth.py`, HTTP Basic sur l'enregistrement des décisions | Partiel, compte partagé ; écran et `/matching` ouverts, motif de blocage A |
| Chiffrement au repos et en transit, cloisonnement par rôles | Code d'infrastructure du second dépôt (`edumatch-cicd/terraform/`, `k8s/`) : réseau privé, registre et stockage privés, NetworkPolicy, conteneurs non root, système de fichiers en lecture seule, aucun jeton de compte de service monté | Partiel, écrit et non déployé ; chiffrement en transit non démontré, aucune terminaison TLS devant le service |
| Rotation et révocation des secrets | Politique écrite (`plan-gouvernance.md` §5) | Partiel, non outillée |
| Résistance à l'empoisonnement des données ou du modèle | Contrôles qualité bloquants et empreintes SHA-256 | Partiel, aucun test adverse conduit |

---

## 3. Les articles voisins, en appui

| Article | Objet | État |
|---|---|---|
| 6 §3 | Dérogation possible pour un système de l'annexe III sans risque important | Écartée par le texte : la dérogation ne s'applique jamais à un profilage de personnes physiques, §1.2 |
| 16 | Obligations générales du fournisseur | Portées par les articles 9 à 15, marquage et déclaration de conformité non couverts, système non mis sur le marché |
| 17 | Système de management de la qualité | Partiel, le plan de gouvernance et la discipline de commit en portent des éléments, aucun système formalisé au sens ISO/IEC 42001 |
| 19 | Conservation des journaux par le fournisseur | Couvert, palier 1 à 12 mois, au-delà du plancher de six mois, §2.4 |
| 26 | Obligations du déployeur | Hors de ce dépôt, la notice à remettre est partielle (§2.5) |
| 72 | Surveillance après commercialisation | Non couvert, `models/derive.py` en serait l'instrument, pas le plan |

---

## 4. Synthèse

| Article | Statut d'ensemble |
|---|---|
| 9, gestion des risques | Couvert, sauf journal d'incident et cycle de révision exécuté |
| 10, gouvernance des données | Couvert, avec deux limites : correction des biais au bout de ce que l'exclusion de variables permet, représentativité non établie sur la population du déployeur |
| 11, documentation technique | Couvert sur le fond, partiel sur la forme, dossier consolidé à assembler |
| 12, journalisation | Couvert pour l'inférence, purge exécutable, testée, planifiée. Non couvert pour la trace de supervision |
| 13, transparence | Couvert vers le déployeur, non couvert vers la personne concernée et sur l'attribution des sources |
| 14, contrôle humain | Dispositif couvert, effectivité non démontrable |
| 15, exactitude, robustesse, cybersécurité | Robustesse couverte, exactitude mesurée et insuffisante, cybersécurité largement non couverte |

Cinq obligations non couvertes, qu'un jury trouvera de toute façon : aucune
information de la personne concernée (ni notice candidat, ni attribution des
sources), un compte conseiller partagé et un écran ouvert donc aucune
imputabilité de la supervision à une personne,
aucune purge du journal de supervision, aucun plan de surveillance après
commercialisation ni journal d'incident, un niveau d'exactitude inférieur à
celui d'une règle de dénombrement sur la session la plus récente.

Les quatre premières sont des manques d'outillage, rattrapables. La
cinquième est un fait sur le modèle, et porte l'avis défavorable rendu sur
le terme appris (`aipd.md` §8.3).

---
*Étape E43, version 1.0 du 2026-09-15, chaque ligne pointe vers un composant
existant ou déclare l'absence, aucune date d'entrée en application n'est
affirmée ici.*
