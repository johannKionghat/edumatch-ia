# Registre des traitements

**Critère servi** : Bloc 1, 1.3 (et 1.6 pour la conformité) ·
**Dernière revue** : 2026-09-15 · **Article de référence** : RGPD art. 30.

Ce registre distingue ce qui existe aujourd'hui dans le dépôt (T1 à T3,
vérifiables par un fichier) de ce qui est spécifié et pas encore construit
(T4 à T8). La colonne « statut » évite de décrire une intention au présent.

---

## 0. La qualification qui structure tout le reste

```
ENTRAÎNEMENT   comptages agrégés Parcoursup, par formation et par session
               -> aucune donnée à caractère personnel

INFÉRENCE      caractéristiques scolaires et intérêts déclarés du candidat
               -> données personnelles, candidats mineurs possibles
```

Aucune donnée de navigation, aucun historique, aucun comportement, ni à
l'entraînement ni à l'inférence. Le modèle apprend sur des taux d'admission
observés par cellule `(formation × session × type de baccalauréat × boursier)`,
440 030 cellules (`01-donnees/label.md`), pas sur des dossiers de candidats.
Cela place le projet dans une situation plus favorable qu'un système entraîné
sur des dossiers scolaires individuels, mais ne règle rien pour l'inférence,
qui elle traite des données personnelles, et de mineurs.

## 1. Rôles

| Rôle RGPD / AI Act | Qui | Portée |
|---|---|---|
| Responsable de traitement, développement (T1 à T3) | Le porteur du projet | Ingestion, entrepôt, échantillons, entraînement |
| Responsable de traitement, exploitation (T4 à T7) | L'établissement ou l'organisme d'orientation déployeur | Recommandation, journalisation, supervision |
| Sous-traitant (art. 28) | L'éditeur de la solution | Hébergement du modèle et de l'API |
| Fournisseur au sens de l'AI Act | L'éditeur de la solution | Articles 9 à 15 |
| Déployeur au sens de l'AI Act | L'établissement client | Article 26, supervision humaine effective |

Le détail des responsabilités opérationnelles est dans `plan-gouvernance.md`.

---

## 2. Les traitements

### T1, catalogue de formations et entraînement du modèle

| | |
|---|---|
| **Statut** | Existant, `data/raw/parcoursup/`, `data/processed/parcoursup/`, `src/edumatch/models/` |
| **Finalité** | Apprendre un taux d'admission par cellule, pour estimer l'accessibilité d'une formation |
| **Données personnelles ?** | Non |
| **Base légale** | Sans objet, hors champ du RGPD |
| **Catégories de données** | Comptages agrégés par formation et session : vœux, propositions, admis, capacité, ventilés par type de baccalauréat et statut de boursier |
| **Durée de conservation** | Sans limite RGPD, conservation liée aux millésimes utiles (2020-2025 aujourd'hui) |
| **Destinataires** | Personne, données restant sur le poste et l'infrastructure du projet |
| **Transferts hors UE** | Aucun |

Le fichier du MESR est un fichier d'agrégats par formation : une ligne est une
formation pour une session, jamais un candidat. Aucun identifiant direct ou
indirect n'y figure.

**Réserve.** L'effectif minimal observé par cellule est de 1
(`01-donnees/label.md` : minimum 1, médiane 30, maximum 16 483). Une cellule à
un vœu, dans une formation à faible effectif, décrit statistiquement une
personne. Ce risque est porté par la publication du MESR, pas créé par ce
projet, mais je m'interdis d'exposer les comptages de cellule à l'utilisateur
final : l'API restitue un taux estimé et ses facteurs, jamais l'effectif brut
(exigence portée dans T4). Je n'en tire pas que le traitement devient un
traitement de données personnelles : aucun moyen raisonnable ne permet
d'individualiser depuis ces comptages seuls.

**Genre.** Les quatre colonnes de ventilation par sexe (`pct_f`, `voe_tot_f`,
`acc_tot_f`, `acc_term_f`) sont classées `interdite` dans `configs/base.yaml`,
réservées à l'audit d'équité a posteriori. Contrôle :
`tests/data/test_features_build_antifuite.py`.

---

### T2, échantillons versionnés pour la suite de tests

| | |
|---|---|
| **Statut** | Existant, `data/samples/`, 17 fichiers, 1,2 Mo, versionnés |
| **Finalité** | Faire tourner la suite de tests et l'intégration continue sans dépendre de 4,6 Go de sources non versionnées |
| **Données personnelles ?** | Oui, lignes d'entrepreneur individuel de Sirene |
| **Base légale** | Intérêt légitime, art. 6.1.f, mise en balance dans `data/samples/README.md` et ADR 0008 |
| **Personnes concernées** | Entrepreneurs individuels inscrits au répertoire Sirene : 282 des 500 lignes de `StockUniteLegale` portent la catégorie juridique 1000, dont 239 diffusibles |
| **Catégories de données** | SIREN, catégorie juridique, activité principale, commune, dates. Les 9 colonnes d'identité directe sont exclues (`nomUniteLegale`, `prenomNUniteLegale` ×4, `prenomUsuelUniteLegale`, `pseudonymeUniteLegale`, `nomUsageUniteLegale`, `sexeUniteLegale`) |
| **Mesure de sécurité** | Pseudonymisation, pas anonymisation |
| **Durée de conservation** | Durée de vie du dépôt, régénérés à chaque évolution des sources |
| **Destinataires** | Tout lecteur du dépôt, il est public |
| **Transferts hors UE** | Le dépôt peut être hébergé sur une forge dont les serveurs sont hors UE, à qualifier, voir lacune L1 |

**Pseudonymisation et non anonymisation.** Retirer les 9 colonnes d'identité
ne rend pas l'échantillon anonyme : une jointure sur le SIREN entre l'unité
légale et `denominationUsuelleEtablissement` / `enseigne1Etablissement`
(conservées sans restriction dans `StockEtablissementHistorique`) restitue
l'identité des 239 lignes diffusibles sur 239, avec pour seule information
complémentaire le fichier source public. L'individualisation reste possible,
la corrélation aussi : la donnée reste personnelle (art. 4.5). L'exclusion des
colonnes reste une mesure de minimisation réelle (art. 5.1.c), qui ne change
pas le régime juridique. Les 43 lignes en statut « P » restent masquées `[ND]`
par l'INSEE à la source, aucune n'a été reconstruite.

**Contrôle** : `tests/data/test_echantillons_conformite.py` applique une liste
blanche de colonnes écrite dans le test lui-même, pour qu'une régénération
future ne puisse pas réintroduire une colonne d'identité directe.

---

### T3, agrégat territorial Sirene, commune × NAF

| | |
|---|---|
| **Statut** | Existant, `data/processed/sirene/agregats_commune_naf.parquet`, 1 929 179 lignes, 12,6 Mo |
| **Finalité** | Calculer le terme « débouchés » du score : densité d'établissements employeurs par commune et secteur |
| **Données personnelles ?** | Oui, indirectement, une cellule à un seul établissement désigne cet établissement, et si c'est un entrepreneur individuel, une personne |
| **Base légale** | Intérêt légitime, art. 6.1.f, même mise en balance que T2 |
| **Catégories de données** | Comptages par couple (commune, code NAF) : actifs employeurs, fermés employeurs, ventilation par tranche d'effectifs, ancienneté moyenne |
| **Durée de conservation** | Recalculé à chaque stock mensuel, l'agrégat précédent est écrasé |
| **Destinataires** | Interne au calcul du score, non exposé en l'état |
| **Transferts hors UE** | Aucun |

Sur les 886 688 cellules comptant au moins un établissement actif employeur,
584 489 n'en comptent qu'un seul, soit 65,9 % : un couple (commune, secteur) à
effectif 1 identifie une entreprise de façon quasi directe. 20 501
établissements actifs employeurs non diffusibles (0,84 %) n'étaient pas
filtrés jusqu'au 2026-08-30, faute d'une dixième colonne lue.

**Deux exigences posées le 2026-08-30, levées au 2026-09-15** (seuil chiffré
dans `risques.md`, R2) : le filtre `diffusible` est appliqué
(`src/edumatch/matching/agregat_sirene_debouches.py` exclut 20 488
établissements non diffusibles sur 2 423 308 rattachés à une commune), et
l'exposition se fait au grain `département × division NAF` avec suppression
des cellules sous 5 établissements, sans jamais renvoyer l'effectif sous le
seuil. T3 peut alimenter le terme de débouchés exposé. La donnée reste
pseudonymisée, pas anonymisée, et k = 5 réduit le risque sans sortir du champ
du RGPD.

---

### T4, recommandation d'orientation (inférence), construit (E28-E29)

| | |
|---|---|
| **Statut** | Existant, `src/edumatch/matching/`, `src/edumatch/api/routes/matching.py`. Détail dans `06-service/score.md` et `06-service/api.md` |
| **Finalité** | Estimer les chances d'admission d'un candidat dans une formation et restituer les facteurs de l'estimation |
| **Données personnelles ?** | Oui, et de mineurs |
| **Personnes concernées** | Lycéens de terminale, en majorité 17-18 ans, une minorité de 16 ans. Pas destiné aux moins de 15 ans |
| **Catégories de données** | Type de baccalauréat, statut de boursier, académie ou département, intérêts déclarés. Aucune donnée de navigation, aucun historique, aucun identifiant de compte tiers |
| **Données non collectées, par décision** | Nom, adresse, date de naissance exacte, établissement d'origine, genre, origine, handicap, résultats scolaires nominatifs |
| **Base légale** | Consentement (art. 6.1.a) en usage direct, ou mission d'intérêt public (art. 6.1.e) si le déployeur est un établissement public. Le choix appartient au responsable de traitement |
| **Durée de conservation** | Aucune conservation de la saisie au-delà de la session, ce qui est conservé relève de T5 |
| **Destinataires** | Le candidat, et le conseiller (T6) |
| **Transferts hors UE** | Aucun, hébergement souverain Scaleway, motivé par la présence de données de mineurs |

Le statut de boursier n'est pas une donnée sensible au sens de l'article 9
(qui vise origine ethnique, opinions politiques, convictions, appartenance
syndicale, données génétiques et biométriques, santé, vie et orientation
sexuelles) : c'est une donnée à forte portée sociale, qui appelle une
vigilance sur la discrimination indirecte.

**Article 8, mineurs.** L'âge du consentement numérique est de quinze ans en
France. Le public visé est au-dessus, mais l'information doit être rédigée
dans des termes qu'un adolescent comprend, affichée avant la saisie et non
dans un lien de bas de page. Un déploiement visant des élèves de moins de
quinze ans exigerait le consentement du titulaire de l'autorité parentale et
rouvrirait cette analyse d'impact.

**Article 22.** Le système ne prend aucune décision : il n'admet ni ne refuse
personne, la décision appartient aux établissements par Parcoursup. Je
n'estime donc pas relever du §1, faute d'effet juridique ou significatif
produit automatiquement. Mais j'applique les garanties comme si c'était le
cas, parce que la frontière est discutable et que la qualification de haut
risque au titre de l'AI Act s'impose de toute façon : intervention humaine
(T6), explication par valeurs de Shapley, possibilité de contester par le
formulaire de retour.

---

### T5, journalisation des inférences, construit (E30)

| | |
|---|---|
| **Statut** | Existant, `src/edumatch/api/audit.py`, purge dans `audit_purge.py`. Détail dans `06-service/journalisation-purge.md` |
| **Finalité** | Traçabilité exigée par l'AI Act pour un système à haut risque |
| **Données personnelles ?** | Oui pendant la phase en clair |
| **Base légale** | Obligation légale, art. 6.1.c |
| **Catégories de données** | Horodatage, identifiant de requête, version du modèle et empreinte du commit, variables d'entrée, score produit, facteurs explicatifs |
| **Durée de conservation** | 12 mois en clair, puis pseudonymisation, puis agrégation à 36 mois, puis suppression |
| **Destinataires** | Le déployeur, le fournisseur, une autorité de contrôle sur demande |
| **Transferts hors UE** | Aucun |

L'AI Act impose une durée minimale de conservation (au moins six mois pour un
fournisseur à haut risque, article 19), le RGPD impose de la limiter
(art. 5.1.e). Je concilie les deux en trois paliers datés :

| Palier | Durée | Contenu | Ce que cela permet |
|---|---|---|---|
| 1, journal en clair | 0-12 mois | Entrées, sortie, version, horodatage | Répondre à une réclamation et rejouer une inférence contestée, au-delà du plancher légal de six mois |
| 2, journal pseudonymisé | 12-36 mois | Identifiant remplacé par un jeton non réversible | Audit d'équité et détection de dérive, sans lien avec une personne |
| 3, agrégats | au-delà de 36 mois | Distributions par sous-population, plus de ligne d'inférence | Démonstration historique sans identification |

12 mois couvre une campagne Parcoursup complète plus une marge de
réclamation ; 36 mois correspond à trois millésimes, la fenêtre minimale pour
observer une dérive du concept. La purge est exécutable, testée et
idempotente (E30, commit `44c49be`) : `audit_purge.py` exécute les trois
paliers, en simulation par défaut, en mode réel sur option, et journalise ses
compteurs dans `processed/audit/purges.jsonl`. La lacune L2 est levée pour T5.
Le DAG Airflow `edumatch_audit_purge` (2026-09-01) appelle `purger_audit` avec
`simulation=False` explicite, sans quoi une tâche planifiée en mode par
défaut ne purgerait jamais rien.

---

### T6, supervision humaine et écartement motivé, construit (E31)

| | |
|---|---|
| **Statut** | Existant, `src/edumatch/api/static/`, `routes/ecran.py`, `feedback_store.py`. Détail dans `06-service/ecran-conseiller.md`. Purge non construite |
| **Finalité** | Permettre à un conseiller de comprendre une recommandation et de l'écarter avec motif, article 14 de l'AI Act |
| **Données personnelles ?** | Oui, celles du candidat et l'identifiant du conseiller |
| **Base légale** | Mission d'intérêt public ou intérêt légitime du déployeur, obligation légale pour la part imposée par l'article 14 |
| **Catégories de données** | Recommandation affichée, facteurs explicatifs, décision du conseiller, motif en texte libre, horodatage, identifiant du conseiller |
| **Durée de conservation** | Alignée sur T5, 12 mois en clair. Le motif en texte libre est le point de vigilance |
| **Destinataires** | Le déployeur |

Un avertissement explicite est affiché au conseiller (ne pas consigner
d'information de santé, de situation familiale ou d'origine) et une purge au
même terme que T5 est prévue.

**Deux manques**, portés en motifs opposables (`aipd.md` §8.4) : la purge de
ce journal n'existe pas, faute d'identifiant commun avec T5 (motif B) ;
l'identifiant du conseiller est déclaratif, sans authentification, la trace
n'est imputable à personne (motif A).

---

### T7, assistant conversationnel (brique secondaire), construit (E32)

| | |
|---|---|
| **Statut** | Existant, `src/edumatch/rag/`. La question posée n'est jamais journalisée, seulement sa longueur et le nombre de résultats. Détail dans `06-service/assistant-rag.md` |
| **Finalité** | Répondre à des questions sur les formations en citant ses sources documentaires |
| **Données personnelles ?** | Oui, potentiellement, une question en texte libre peut contenir n'importe quoi |
| **Base légale** | Consentement, ou intérêt légitime du déployeur |
| **Destinataires** | Un fournisseur de modèle de langage tiers, seul point du projet où une donnée saisie sort de l'infrastructure |
| **Transferts hors UE** | À qualifier selon le fournisseur. `MISTRAL_API_KEY` dans `.env.example` désigne un fournisseur européen, ce qui écarte la question du transfert mais ne dispense pas du contrat de sous-traitance (art. 28) |
| **Durée de conservation** | Aucune conservation des questions côté projet |

Exigence posée : pas de contrat de sous-traitance écrit, pas de mise en
service de cette brique secondaire, qui ne justifie aucune exception.

---

### T8, exercice des droits des personnes, procédure non construite

| | |
|---|---|
| **Statut** | À construire |
| **Finalité** | Recevoir, tracer et traiter les demandes d'accès, rectification, effacement, limitation, opposition et portabilité |
| **Délai** | Un mois à réception (art. 12.3), prorogeable de deux mois pour les demandes complexes |
| **Traçabilité** | Chaque demande enregistrée : date, nature, identité vérifiée, date et sens de la réponse |

L'effacement doit atteindre la base de production, les journaux d'inférence
(T5), les sauvegardes, et pour T2, l'historique Git. Une demande d'opposition
d'un entrepreneur individuel figurant dans `data/samples/` exigerait de
retirer la ligne et de réécrire l'historique du dépôt, ce qu'un simple commit
ne fait pas. Coût connu et accepté.

---

## 3. Synthèse, ce qui se conserve et combien de temps

| Traitement | Donnée personnelle | Base légale | Durée définie ? | Purge implémentée ? |
|---|---|---|---|---|
| T1 catalogue et modèle | Non | Sans objet | Sans objet | Sans objet |
| T2 échantillons | Oui (pseudonymisée) | art. 6.1.f | Vie du dépôt | Sans objet |
| T3 agrégat territorial | Oui (indirecte) | art. 6.1.f | Écrasé chaque mois | Oui, par écrasement, k = 5 et filtre de diffusion appliqués |
| T4 inférence | Oui, mineurs | art. 6.1.a ou 6.1.e | Aucune conservation | À implémenter |
| T5 journalisation | Oui | art. 6.1.c | 12 / 36 mois | Oui, testée, idempotente, planifiée. Lacune L2 levée |
| T6 supervision | Oui | art. 6.1.c et 6.1.e | 12 mois | Non, écran construit, purge non construite. Motif de blocage actif |
| T7 assistant | Oui, possible | art. 6.1.a | Aucune | Non |
| T8 droits | Oui | art. 6.1.c | 3 ans après clôture | Non |

## 4. Les lacunes, déclarées plutôt que masquées

- **L1**, localisation de la forge. Le dépôt public héberge `data/samples/`,
  qui contient des données pseudonymisées (T2), sans que la localisation des
  serveurs soit qualifiée. À trancher : qualifier le transfert, ou retirer les
  lignes d'entrepreneur individuel des échantillons, au prix de 56,4 % de
  représentativité perdue sur les catégories juridiques (ADR 0008).
- **L2**, levée pour T5, maintenue pour T6 (revue du 2026-09-15). T6 n'a
  toujours pas de purge, faute d'identifiant commun avec T5 : motif de
  blocage opposable (motif B).
- **L3**, aucune notice d'information n'est rédigée pour les candidats.
  L'interface existe mais s'adresse au conseiller : la notice reste à
  produire, en français simple, affichée avant la saisie. Motif C.
- **L4**, aucune authentification ne protège l'écran qui expose les
  caractéristiques d'un candidat, l'identifiant du conseiller est déclaratif :
  lacune de sécurité et de traçabilité. Motif A.
- **L5**, aucun dispositif d'exercice des droits (T8), aucune procédure de
  notification de violation, aucun contrat de sous-traitance pour T7. Trois
  réserves non bloquantes prises isolément, mais qui le deviennent au premier
  usage réel.

---
*Étape E40, rédigé le 2026-08-30, mis à jour le 2026-09-01 après la
construction du service, revu le 2026-09-15 au moment de l'analyse d'impact
complète, de la Model Card et de la correspondance au règlement sur l'IA : T3
et T5 corrigés dans le sens du progrès, T6 dans le sens du manque, cinq
lacunes désormais déclarées au lieu de trois.*
