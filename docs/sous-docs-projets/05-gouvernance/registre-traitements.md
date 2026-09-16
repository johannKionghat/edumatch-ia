# Registre des traitements

**Critère servi** : Bloc 1, 1.3 (et 1.6 pour la partie conformité) ·
**Dernière revue** : 2026-09-15 · **Article de référence** : RGPD art. 30.

Ce registre distingue explicitement **ce qui existe aujourd'hui dans le dépôt**
(T1 à T3, vérifiables par un fichier) de **ce qui est spécifié et pas encore
construit** (T4 à T8). Un registre qui décrirait les seconds au présent serait
une déclaration d'intention ; la colonne « statut » évite cette confusion.

---

## 0. La qualification qui structure tout le reste

```
ENTRAÎNEMENT   comptages agrégés Parcoursup, par formation et par session
               -> AUCUNE donnée à caractère personnel

INFÉRENCE      caractéristiques scolaires et intérêts déclarés du candidat
               -> données personnelles, candidats mineurs possibles
```

Ce n'est **pas** un profil de compte alimenté par l'usage. Aucune donnée de
navigation, aucun historique, aucun comportement, ni à l'entraînement ni à
l'inférence. Le modèle apprend sur des taux d'admission observés par cellule
`(formation × session × type de baccalauréat × boursier)` — 440 030 cellules,
`01-donnees/label.md` — et non sur des dossiers de candidats.

Cette architecture n'est pas un hasard : c'est ce qui place le projet dans une
situation nettement plus favorable qu'un système d'orientation entraîné sur
des dossiers scolaires individuels. Il faut le dire, et il faut aussi dire ce
qu'elle ne règle pas — l'inférence, elle, traite bien des données
personnelles, et de mineurs.

## 1. Rôles

| Rôle RGPD / AI Act | Qui | Portée |
|---|---|---|
| Responsable de traitement, phase de développement (T1 à T3) | Le porteur du projet | Ingestion, entrepôt, échantillons, entraînement |
| Responsable de traitement, phase d'exploitation (T4 à T7) | **L'établissement ou l'organisme d'orientation déployeur** — il détermine la finalité et les moyens auprès de ses élèves | Recommandation, journalisation, supervision |
| Sous-traitant (art. 28) | L'éditeur de la solution | Hébergement du modèle et de l'API, pour le compte du déployeur |
| **Fournisseur** au sens de l'AI Act | L'éditeur de la solution | Articles 9 à 15 |
| **Déployeur** au sens de l'AI Act | L'établissement client | Article 26, dont la supervision humaine effective |

Cette répartition n'est pas cosmétique : elle décide qui répond d'une demande
d'accès, qui tient le registre des inférences, et qui doit produire l'analyse
d'impact pour un déploiement réel. Le détail des responsabilités opérationnelles
est dans `plan-gouvernance.md`.

---

## 2. Les traitements

### T1 — Constitution du catalogue de formations et entraînement du modèle

| | |
|---|---|
| **Statut** | **Existant** — `data/raw/parcoursup/`, `data/processed/parcoursup/`, `src/edumatch/models/` |
| **Finalité** | Apprendre un taux d'admission par cellule, pour estimer l'accessibilité d'une formation |
| **Données personnelles ?** | **Non** |
| **Base légale** | Sans objet — hors champ du RGPD |
| **Personnes concernées** | Aucune |
| **Catégories de données** | Comptages agrégés par formation et par session : vœux, propositions, admis, capacité, ventilés par type de baccalauréat et statut de boursier |
| **Durée de conservation** | Sans limite RGPD ; conservation fonctionnelle liée aux millésimes utiles (2020-2025 aujourd'hui) |
| **Destinataires** | Personne — données restant sur le poste et l'infrastructure du projet |
| **Transferts hors UE** | Aucun |

**La qualification, argumentée et non postulée.** Le fichier publié par le
MESR est un fichier d'**agrégats par formation** : une ligne est une formation
pour une session, jamais un candidat. Aucun identifiant direct ni indirect de
personne n'y figure — ni nom, ni identifiant de dossier, ni date de naissance.

**La réserve que je dois écrire plutôt que taire.** Le fichier source contient
des cellules à très faible effectif : l'effectif minimal observé par cellule
est de 1 (`01-donnees/label.md`, distribution des effectifs : minimum 1,
médiane 30, maximum 16 483). Une cellule à un vœu, dans une formation à
faible effectif, décrit *statistiquement* une personne. Deux conséquences que
je tire, et une que je ne tire pas :

- ce risque est porté par la publication du MESR, pas créé par ce projet : je
  ne dispose d'aucune information supplémentaire qui permettrait de nommer la
  personne, et je n'en ajoute aucune ;
- **je m'interdis pour autant d'exposer les comptages de cellule à
  l'utilisateur final** : l'API restitue un taux estimé et ses facteurs
  explicatifs, jamais l'effectif brut d'une cellule à faible dénominateur.
  C'est une exigence portée dans le contrat d'interface (T4) ;
- je n'en tire **pas** que le traitement devient un traitement de données
  personnelles : aucun moyen raisonnable ne permet d'individualiser depuis ces
  comptages seuls.

**Statut du genre.** Les quatre colonnes de ventilation par sexe (`pct_f`,
`voe_tot_f`, `acc_tot_f`, `acc_term_f`) sont classées `interdite` dans
`configs/base.yaml`. Elles ne sont ni des données personnelles (ce sont des
comptages), ni utilisables : l'invariant du projet les réserve à l'audit
d'équité a posteriori. Contrôle automatisé :
`tests/data/test_features_build_antifuite.py`.

---

### T2 — Échantillons versionnés pour la suite de tests

| | |
|---|---|
| **Statut** | **Existant** — `data/samples/`, 17 fichiers, 1,2 Mo, versionnés |
| **Finalité** | Faire tourner la suite de tests et l'intégration continue sans dépendre de 4,6 Go de sources non versionnées |
| **Données personnelles ?** | **Oui** — lignes d'entrepreneur individuel de Sirene |
| **Base légale** | **Intérêt légitime, art. 6.1.f**, mise en balance écrite dans `data/samples/README.md` et ADR 0008 |
| **Personnes concernées** | Entrepreneurs individuels inscrits au répertoire Sirene. Mesuré : **282 des 500 lignes** de `StockUniteLegale` portent la catégorie juridique 1000, dont **239 en statut diffusible** |
| **Catégories de données** | SIREN, catégorie juridique, activité principale, commune, dates. **Les 9 colonnes d'identité directe sont exclues** (`nomUniteLegale`, quatre `prenomNUniteLegale`, `prenomUsuelUniteLegale`, `pseudonymeUniteLegale`, `nomUsageUniteLegale`, `sexeUniteLegale`) |
| **Mesure de sécurité** | **Pseudonymisation, pas anonymisation** — voir ci-dessous |
| **Durée de conservation** | Durée de vie du dépôt. Régénérés à chaque évolution des sources ; un retrait exigerait de **réécrire l'historique Git**, pas seulement un nouveau commit |
| **Destinataires** | Tout lecteur du dépôt — il est public |
| **Transferts hors UE** | Le dépôt est hébergé sur une forge dont les serveurs peuvent se situer hors UE. **À qualifier** : voir la lacune L1 en fin de document |

**Pseudonymisation et non anonymisation — le fait, pas l'affirmation.**
Retirer les 9 colonnes d'identité ne rend pas l'échantillon anonyme. Une
jointure sur le SIREN entre l'unité légale et
`denominationUsuelleEtablissement` / `enseigne1Etablissement` — conservées
sans restriction dans `StockEtablissementHistorique` — restitue l'identité des
**239 lignes diffusibles sur 239**. L'information complémentaire nécessaire
est le fichier source public lui-même : ce n'est pas un moyen hors de portée.

Les trois critères d'une anonymisation réelle ne sont donc pas réunis :
l'individualisation reste possible, la corrélation aussi. La donnée **reste
une donnée personnelle** (art. 4.5). L'exclusion des colonnes est une mesure
de minimisation réelle (art. 5.1.c) qui ne change pas le régime juridique.

Les 43 lignes en statut « P » (non diffusible) restent masquées `[ND]` par
l'INSEE à la source : aucune n'a été reconstruite.

**Contrôle qui empêche la régression** :
`tests/data/test_echantillons_conformite.py` applique une liste blanche de
colonnes écrite dans le test lui-même — et non importée du module qu'il
contrôle — de sorte qu'une régénération future ne peut pas réintroduire une
colonne d'identité directe sans faire échouer la chaîne.

---

### T3 — Agrégat territorial Sirene, commune × NAF

| | |
|---|---|
| **Statut** | **Existant** — `data/processed/sirene/agregats_commune_naf.parquet`, 1 929 179 lignes, 12,6 Mo |
| **Finalité** | Calculer le terme « débouchés » du score : densité d'établissements employeurs par commune et secteur d'activité |
| **Données personnelles ?** | **Oui, indirectement** — une cellule à un seul établissement désigne cet établissement, et si c'est un entrepreneur individuel, une personne |
| **Base légale** | Intérêt légitime, art. 6.1.f — même mise en balance que T2 |
| **Personnes concernées** | Entrepreneurs individuels employeurs |
| **Catégories de données** | Comptages par couple (commune, code NAF) : actifs employeurs, fermés employeurs, ventilation par tranche d'effectifs, ancienneté moyenne |
| **Durée de conservation** | Recalculé à chaque stock mensuel ; l'agrégat précédent est écrasé |
| **Destinataires** | Interne au calcul du score. **Non exposé en l'état** — voir la décision de k-anonymat |
| **Transferts hors UE** | Aucun |

**Le fait mesuré, et pourquoi il compte.** Sur les 886 688 cellules comptant au
moins un établissement actif employeur, **584 489 n'en comptent qu'un seul,
soit 65,9 %**. Un couple (commune, secteur) à effectif 1 identifie une
entreprise de façon quasi directe. S'y ajoute que **20 501 établissements
actifs employeurs non diffusibles (0,84 %) ne sont pas filtrés** : le filtre
`diffusible: true` est déclaré dans `configs/base.yaml` mais n'est pas
appliqué, faute d'une dixième colonne lue.

**Deux exigences posées le 2026-08-30, et leur état au 2026-09-15** (seuil
arrêté et chiffré dans `risques.md`, R2) :

1. le filtre `diffusible` doit être **appliqué** — **fait** :
   `src/edumatch/matching/agregat_sirene_debouches.py` exclut **20 488
   établissements actifs employeurs** non diffusibles, sur les 2 423 308
   rattachés à une commune ;
2. l'agrégat au grain `commune × NAF` reste un **calcul intermédiaire jamais
   exposé**, l'exposition se faisant au grain `département × division NAF` avec
   suppression des cellules sous 5 établissements — **fait**. Le module ne
   renvoie jamais l'effectif sous le seuil, pas même pour distinguer un zéro
   réel d'une cellule supprimée.

**Les deux points sont implémentés : T3 peut alimenter le terme de débouchés
exposé.** Ce qui ne change pas : la donnée reste pseudonymisée, pas anonymisée,
et k = 5 est une mesure de réduction du risque, non une sortie du champ du
RGPD.

---

### T4 — Recommandation d'orientation (inférence) — **construit** (E28-E29)

| | |
|---|---|
| **Statut** | **Existant** — `src/edumatch/matching/`, `src/edumatch/api/routes/matching.py`. Voir `06-service/score.md` et `06-service/api.md` pour le détail technique |
| **Finalité** | Estimer, pour un candidat, ses chances d'admission dans une formation et lui restituer les facteurs de cette estimation |
| **Données personnelles ?** | **Oui**, et **de mineurs** |
| **Personnes concernées** | Lycéens de terminale, en majorité âgés de 17 à 18 ans, une minorité de 16 ans. **Le service n'est pas destiné aux moins de 15 ans** |
| **Catégories de données** | Type de baccalauréat, statut de boursier, académie ou département, intérêts déclarés. **Aucune donnée de navigation, aucun historique, aucun identifiant de compte tiers** |
| **Données non collectées, par décision** | Nom, adresse, date de naissance exacte, établissement d'origine, **genre**, origine, situation de handicap, résultats scolaires nominatifs |
| **Base légale** | **Consentement (art. 6.1.a)** en usage direct par le candidat ; **mission d'intérêt public (art. 6.1.e)** lorsque le déployeur est un établissement public qui l'intègre à son accompagnement à l'orientation. Le choix appartient au responsable de traitement, il est documenté par lui |
| **Durée de conservation** | **Aucune conservation de la saisie au-delà de la session** : les caractéristiques saisies servent à produire la réponse et ne sont pas stockées. Ce qui est conservé relève de T5, sous forme distincte |
| **Destinataires** | Le candidat, et le conseiller qui l'accompagne (T6) |
| **Transferts hors UE** | Aucun — hébergement souverain (Scaleway), choix motivé précisément par la présence de données de mineurs |

**Le statut de boursier n'est pas une donnée sensible.** L'article 9 vise
l'origine raciale ou ethnique, les opinions politiques, les convictions
religieuses ou philosophiques, l'appartenance syndicale, les données
génétiques et biométriques, la santé, la vie et l'orientation sexuelles. Le
statut de boursier n'y figure pas. C'est une donnée personnelle à forte portée
sociale, qui appelle une vigilance réelle sur la discrimination indirecte —
mais l'annoncer comme une « donnée sensible » serait une erreur de
qualification.

**Article 8 — les mineurs.** En France, l'âge du consentement numérique est de
quinze ans. Le public visé est au-dessus, mais deux exigences en découlent
quand même, et elles se traduisent techniquement :

- l'information doit être rédigée **dans des termes qu'un adolescent
  comprend** : une notice courte, en français simple, affichée avant la
  saisie et non dans un lien de bas de page ;
- si un déploiement devait viser des élèves de moins de quinze ans (classe de
  troisième, orientation post-collège), le recueil du consentement du
  titulaire de l'autorité parentale deviendrait obligatoire, et cette analyse
  d'impact devrait être rouverte.

**Article 22 — décision individuelle automatisée.** Le système **ne prend
aucune décision** : il n'admet ni ne refuse personne. La décision d'admission
appartient aux établissements, par Parcoursup, hors de ce système. Je ne me
place donc pas sous l'exception de l'article 22 §2 — j'estime que le
traitement ne relève pas du §1, faute d'effet juridique ou d'effet
significatif produit *automatiquement*.

**Mais je mets en œuvre les garanties comme si.** Parce que la frontière est
discutable — une recommandation d'orientation suivie sans recul peut affecter
significativement un parcours — et parce que la qualification de haut risque
au titre de l'AI Act s'impose de toute façon. Concrètement : intervention
humaine (T6), explication des facteurs par valeurs de Shapley, possibilité
d'exprimer un point de vue et de contester par le formulaire de retour.

---

### T5 — Journalisation des inférences — **construit** (E30)

| | |
|---|---|
| **Statut** | **Existant** — `src/edumatch/api/audit.py`, purge exécutable dans `src/edumatch/api/audit_purge.py`. Voir `06-service/journalisation-purge.md` |
| **Finalité** | Traçabilité exigée par l'AI Act pour un système à haut risque : savoir quelle version du modèle a produit quelle sortie, à quelle date |
| **Données personnelles ?** | **Oui** pendant la phase en clair |
| **Base légale** | **Obligation légale, art. 6.1.c** — la journalisation n'est pas un choix du responsable de traitement, elle est imposée par le règlement sur l'IA |
| **Catégories de données** | Horodatage, identifiant technique de requête, version du modèle et empreinte du commit, variables d'entrée, score produit, facteurs explicatifs restitués |
| **Durée de conservation** | **12 mois en clair, puis pseudonymisation, puis agrégation à 36 mois, puis suppression** — voir la conciliation ci-dessous |
| **Destinataires** | Le déployeur (supervision, réclamations), le fournisseur (incidents, dérive), une autorité de contrôle sur demande |
| **Transferts hors UE** | Aucun |

**La tension à trancher, parce que les deux textes se contredisent.** Le
règlement sur l'IA impose de journaliser les inférences et fixe une durée
**minimale** de conservation des journaux — au moins six mois pour un
fournisseur de système à haut risque (article 19), sauf disposition contraire
du droit de l'Union ou national. Le RGPD, lui, impose de **limiter** la durée
de conservation (art. 5.1.e). Une obligation de plancher face à une obligation
de plafond.

**La conciliation retenue, en trois paliers datés :**

| Palier | Durée | Contenu conservé | Ce que cela permet, et ce que cela empêche |
|---|---|---|---|
| 1 — journal en clair | 0 à 12 mois | Entrées, sortie, version, horodatage | Répondre à une réclamation individuelle et rejouer une inférence contestée. Couvre le plancher légal de six mois, et une campagne Parcoursup entière |
| 2 — journal pseudonymisé | 12 à 36 mois | Identifiant de requête remplacé par un jeton non réversible, variables conservées | Audit d'équité et détection de dérive restent possibles ; **le lien avec une personne est rompu** |
| 3 — agrégats | au-delà de 36 mois | Distributions et métriques par sous-population, plus aucune ligne d'inférence | Conserver la capacité de démonstration historique sans conserver l'identification |

Le choix de 12 mois n'est pas arbitraire : c'est la durée qui couvre une
campagne complète, de la formulation des vœux en janvier à la fin de la phase
complémentaire, plus une marge de réclamation. Le choix de 36 mois correspond
à trois millésimes, c'est-à-dire à la fenêtre minimale pour observer une
dérive du concept sur une cible qui bouge d'une session à l'autre.

**Ce qui rend la durée vérifiable et non déclarative** : la purge doit être
une tâche exécutable, avec journal d'exécution — pas une procédure écrite
dans un document. **C'est fait (E30, commit `44c49be`)** :
`src/edumatch/api/audit_purge.py` exécute les trois paliers, en mode
simulation par défaut, en mode réel sur option explicite, idempotent
(rejouer la purge à la même date ne change rien), et chaque passage
journalise ses quatre compteurs dans `processed/audit/purges.jsonl`. La
lacune L2 est levée sur ce point précis — voir `06-service/journalisation-purge.md`
pour le détail.

**Le déclenchement planifié existe désormais** (2026-09-01, DAG Airflow) : le
graphe `edumatch_audit_purge` de `pipelines/edumatch_pipeline.py` appelle
`orchestration/taches.py::purger_audit`, à la cadence déclarée par
`orchestration.planification.purge_audit` dans `configs/base.yaml`. Ce point
mérite d'être souligné : cette tâche passe `simulation=False` **explicitement**,
parce qu'une tâche planifiée qui se contenterait du mode par défaut du module
— la simulation — ne purgerait jamais rien, et la durée de conservation
redeviendrait une intention sans que personne ne s'en aperçoive.

---

### T6 — Supervision humaine et écartement motivé — **construit** (E31)

| | |
|---|---|
| **Statut** | **Existant** — `src/edumatch/api/static/`, `routes/ecran.py`, `feedback_store.py`. Voir `06-service/ecran-conseiller.md`. **Purge non construite** pour ce journal — voir ci-dessous et `06-service/journalisation-purge.md` |
| **Finalité** | Permettre à un conseiller de comprendre une recommandation, de la contextualiser et de **l'écarter avec un motif** ; article 14 de l'AI Act |
| **Données personnelles ?** | Oui — celles du candidat concerné, et l'identifiant professionnel du conseiller |
| **Base légale** | Mission d'intérêt public ou intérêt légitime du déployeur, selon son statut ; **obligation légale** pour la part imposée par l'article 14 |
| **Catégories de données** | Recommandation affichée, facteurs explicatifs, décision du conseiller, motif d'écartement en texte libre, horodatage, identifiant du conseiller |
| **Durée de conservation** | Alignée sur T5 : 12 mois en clair. **Le motif en texte libre est le point de vigilance** : un champ libre finit toujours par contenir des informations non prévues |
| **Destinataires** | Le déployeur |

**La mesure qui accompagne le champ libre** : un avertissement explicite au
conseiller (« ne consignez aucune information de santé, de situation familiale
ou d'origine »), et une purge au même terme que T5. Un champ libre sans consigne
est une collecte non maîtrisée.

**Deux manques, portés en motifs opposables par l'analyse d'impact** :

1. **La purge de ce journal n'existe pas.** La durée est écrite (12 mois),
   aucune tâche ne l'exécute, faute d'identifiant commun avec T5. Une donnée
   personnelle conservée sans purge exécutable est un motif de blocage de la
   mise en service (`aipd.md` §8.4, motif B).
2. **L'identifiant du conseiller est déclaratif**, saisi sans vérification :
   aucune authentification n'est branchée sur l'écran. La trace existe, elle
   n'est **imputable à personne**, et l'écran expose des caractéristiques de
   candidats sans contrôle d'accès (`aipd.md` §8.4, motif A).

---

### T7 — Assistant conversationnel (brique secondaire) — **construit** (E32)

| | |
|---|---|
| **Statut** | **Existant** — `src/edumatch/rag/`. La question posée n'est jamais journalisée (seulement sa longueur et le nombre de résultats). Voir `06-service/assistant-rag.md` |
| **Finalité** | Répondre à des questions sur les formations en citant ses sources documentaires |
| **Données personnelles ?** | **Oui, potentiellement** — une question en texte libre peut contenir tout et n'importe quoi |
| **Base légale** | Consentement, ou intérêt légitime du déployeur |
| **Destinataires** | **Un fournisseur de modèle de langage tiers** — c'est le seul point du projet où une donnée saisie sort de l'infrastructure |
| **Transferts hors UE** | À qualifier selon le fournisseur retenu. La clé d'API prévue dans `.env.example` (`MISTRAL_API_KEY`) désigne un fournisseur européen, ce qui écarte la question du transfert mais **ne dispense pas du contrat de sous-traitance (art. 28)** |
| **Durée de conservation** | Aucune conservation des questions côté projet |

**Exigence posée** : pas de contrat de sous-traitance écrit, pas de mise en
service de cette brique. Elle est secondaire au projet ; elle ne justifie
aucune exception.

---

### T8 — Exercice des droits des personnes — **procédure, non construite**

| | |
|---|---|
| **Statut** | **À construire** |
| **Finalité** | Recevoir, tracer et traiter les demandes d'accès, de rectification, d'effacement, de limitation, d'opposition et de portabilité |
| **Délai** | **Un mois** à compter de la réception (art. 12.3), prorogeable de deux mois pour les demandes complexes, avec information de la personne dans le premier mois |
| **Traçabilité** | Chaque demande enregistrée : date de réception, nature, identité vérifiée, date et sens de la réponse |

**Ce que l'effacement doit atteindre, et qui se prévoit à la conception, pas
après** : la base de production, **les journaux d'inférence (T5)**, **les
sauvegardes**, et — cas particulier de ce projet — **l'historique Git** pour
T2. Un effacement qui ne traite pas les sauvegardes et les journaux n'est pas
un effacement.

**Le cas T2 mérite d'être énoncé franchement** : une demande d'opposition d'un
entrepreneur individuel dont une ligne figure dans `data/samples/` exigerait
de retirer la ligne **et de réécrire l'historique du dépôt**, ce qu'un simple
commit ne fait pas. C'est un coût connu et accepté, pas une découverte.

---

## 3. Synthèse — ce qui se conserve, et combien de temps

| Traitement | Donnée personnelle | Base légale | Durée définie ? | Purge implémentée ? |
|---|---|---|---|---|
| T1 catalogue et modèle | Non | Sans objet | Sans objet | Sans objet |
| T2 échantillons | **Oui** (pseudonymisée) | art. 6.1.f | Vie du dépôt | Sans objet |
| T3 agrégat territorial | **Oui** (indirecte) | art. 6.1.f | Écrasé chaque mois | Oui, par écrasement. **k = 5 et filtre de diffusion appliqués à la restitution** |
| T4 inférence | **Oui**, mineurs | art. 6.1.a ou 6.1.e | Aucune conservation | À implémenter |
| T5 journalisation | **Oui** | art. 6.1.c | 12 / 36 mois | **Oui — `audit_purge.py`, testée, idempotente, et planifiée par le DAG `edumatch_audit_purge`. Lacune L2 levée pour T5** |
| T6 supervision | **Oui** | art. 6.1.c et 6.1.e | 12 mois | **Non — écran construit, purge du journal de retour non construite, faute d'identifiant commun avec T5. Motif de blocage actif** |
| T7 assistant | **Oui**, possible | art. 6.1.a | Aucune | **Non** |
| T8 droits | **Oui** | art. 6.1.c | 3 ans après clôture | **Non** |

## 4. Les lacunes, déclarées plutôt que masquées

- **L1 — Localisation de la forge.** Le dépôt public héberge `data/samples/`,
  qui contient des données personnelles pseudonymisées (T2). La localisation
  des serveurs de la forge n'est pas qualifiée dans ce registre. À trancher :
  soit la qualification du transfert est écrite, soit les lignes
  d'entrepreneur individuel sortent des échantillons versionnés — au prix,
  chiffré dans l'ADR 0008, de 56,4 % de représentativité perdue sur les
  catégories juridiques.
- **L2 — Levée pour T5, maintenue pour T6 (revue du 2026-09-15).** Pour T5, la
  purge est exécutable, testée, idempotente **et planifiée** : ce n'est plus
  une intention. **T6 n'a toujours pas de purge**, faute d'identifiant commun
  avec T5 — c'est désormais un motif de blocage opposable, pas une simple
  lacune (`aipd.md` §8.4, motif B).
- **L3 — Aucune notice d'information n'est rédigée** à destination des
  candidats. L'interface existe désormais, mais elle s'adresse au
  **conseiller** : la notice destinée au candidat reste entièrement à produire,
  en français simple, compréhensible par un lecteur de 17 ans, affichée avant
  la saisie et non dans un lien de bas de page. Motif de blocage actif
  (motif C).
- **L4 — Aucune authentification** ne protège l'écran qui expose les
  caractéristiques d'un candidat, et l'identifiant du conseiller est
  déclaratif. Lacune de sécurité et lacune de traçabilité à la fois : une
  décision de supervision n'est imputable à personne. Motif de blocage actif
  (motif A).
- **L5 — Aucun dispositif d'exercice des droits (T8)**, aucune procédure de
  notification de violation, aucun contrat de sous-traitance pour T7. Trois
  réserves fermes, non bloquantes prises isolément, mais qui le deviennent au
  premier usage réel.

---
*Étape E40 · rédigé le 2026-08-30 · mis à jour le 2026-09-01 après la
construction du service, puis **revu intégralement le 2026-09-15** au moment de
la production de l'analyse d'impact complète, de la Model Card et de la
correspondance au règlement sur l'IA : T3 et T5 corrigés dans le sens du
progrès, T6 dans le sens du manque, cinq lacunes désormais déclarées au lieu de
trois.*
