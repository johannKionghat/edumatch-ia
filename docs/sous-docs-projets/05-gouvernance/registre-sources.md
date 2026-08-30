# Registre des sources et de leurs licences

**Critère servi** : Bloc 1, 1.4 · **Dernière revue** : 2026-08-30 ·
**Prochaine revue obligatoire** : à chaque ajout de source, et au plus tard à
l'ouverture de la campagne Parcoursup suivante (janvier 2027).

Ce registre est le pendant, côté données entrantes, du registre des
traitements. Il répond à six questions pour chaque source : **qui la produit,
sous quelle licence exacte, ce qu'elle m'oblige à faire, ce que j'en ai
réellement téléchargé, quand, et où cette preuve se vérifie dans le dépôt.**

Je ne recopie pas les licences à la main : chaque connecteur écrit la licence,
l'URL, la date et l'empreinte SHA-256 de chaque fichier dans un manifeste
(`data/raw/*/manifeste.json`, `data/external/referentiels/manifeste.json`,
`data/samples/manifeste.json`). Ce registre commente ces manifestes, il ne s'y
substitue pas — si les deux divergent un jour, **c'est le manifeste qui fait
foi**, parce que c'est lui qu'un programme a écrit à partir du fichier réel.

---

## 1. Les six sources entrantes

| # | Source | Producteur (titulaire des droits) | Licence exacte | Volumétrie mesurée | Récupérée le | Preuve dans le dépôt |
|---|---|---|---|---|---|---|
| S1 | Parcoursup, 8 millésimes 2018-2025 | Ministère de l'Enseignement supérieur et de la Recherche (MESR) | **Licence Ouverte v2.0 (Etalab)** | 104 274 formation-années, 118 colonnes en 2025, **82 Mo** | **2026-08-28** | `data/raw/parcoursup/manifeste.json` |
| S2 | Base Sirene, 4 fichiers de stock | INSEE | **Licence Ouverte v2.0 (Etalab)** | 4 fichiers Parquet, **4,63 Go** ; `StockEtablissement` = 43 896 818 lignes, 54 colonnes | **2026-08-28**, stock publié le **2026-08-01** | `data/raw/sirene/manifeste.json` |
| S3 | IDÉO, 4 jeux (formations, métiers, structures du secondaire et du supérieur) | ONISEP | **ODbL v1.0** (`odc-odbl`) | 5 869 + 1 534 + 15 293 + 8 985 lignes, **15,9 Mo** | **2026-08-29** | `data/external/referentiels/manifeste.json`, entrées `ideo:*` |
| S4 | RNCP et Répertoire spécifique, export CSV standard | France Compétences | **Licence Ouverte v2.0 (Etalab)** | 30 484 fiches dont 7 000 actives, 16 colonnes | **2026-08-29** puis **2026-08-30** | manifeste, entrées `rncp:2026-08-29`, `rncp:2026-08-30` |
| S5 | RNCP, membre « codes ROME » de la même archive quotidienne | France Compétences | **Licence Ouverte v2.0 (Etalab)** | 24 424 fiches couvrant au moins un code ROME, 4 353 036 o | **2026-08-30** | manifeste, entrée `rncp_rome:2026-08-30` |
| S6 | Table de correspondance ROME / NAF | France Travail | **Licence Ouverte v2.0 (Etalab)** | 1 classeur, 112 896 o, correspondance arrêtée à la **division NAF (2 chiffres)** | **2026-08-30** | manifeste, entrée `france_travail_rome_naf:rome_naf` |

Toutes les volumétries ci-dessus sont **mesurées sur le fichier réellement
posé sur disque**, pas reprises d'une fiche de catalogue. Le détail des
commandes, et les trois chiffres que j'ai dû corriger en cours de route — la
volumétrie compressée de Sirene, le nombre d'établissements, le nombre de
fiches RNCP faussé par mon propre outil de comptage — sont dans
`01-donnees/sources.md`.

## 2. Ce que chaque licence m'oblige à faire, traduit en obligation vérifiable

### Licence Ouverte v2.0 — S1, S2, S4, S5, S6

Vérification faite sur le texte de la licence
(`https://www.etalab.gouv.fr/wp-content/uploads/2017/04/ETALAB-Licence-Ouverte-v2.0.pdf`),
et non sur son résumé :

| Point de contrôle | Réponse pour ces cinq sources |
|---|---|
| Réutilisation commerciale autorisée ? | **Oui**, sans restriction |
| Attribution obligatoire ? | **Oui** — paternité *et* **date de la dernière mise à jour** de la donnée réutilisée |
| Partage à l'identique ? | Non |
| Durée ? | Non limitée |
| Compatible avec un projet porté par une société ? | **Oui** — aucune clause non commerciale |

**Traduction technique de l'obligation d'attribution.** Une mention générique
« source : données publiques » ne satisfait pas la licence, parce qu'elle omet
la date. L'obligation devient donc, dans ce projet, **un écran « Sources et
licences » de l'interface conseiller, alimenté par les manifestes et non par
une liste écrite en dur** : producteur, intitulé du jeu, licence, et date de
publication ou de collecte du fichier effectivement utilisé. Alimenter cet
écran depuis les manifestes n'est pas un raffinement : une liste écrite en dur
deviendrait fausse au premier stock Sirene mensuel suivant, sans que rien ne
le signale.

**Statut au 2026-08-30 : non implémenté.** L'interface n'existe pas encore
(`src/edumatch/api/` ne contient que des marqueurs de dossier). C'est une
obligation ouverte, inscrite au registre des risques sous R7.

### ODbL v1.0 — S3 (IDÉO / ONISEP), et la question tranchée

L'ODbL diffère de la Licence Ouverte sur un point qui change tout : elle
impose le **partage à l'identique** de toute base dérivée. La question restée
ouverte dans `01-donnees/sources.md` est : est-ce que ce projet redistribue ?
**Je la tranche ici.**

Trois artefacts de ce dépôt contiennent de la donnée IDÉO :

| Artefact | Redistribué ? | Conséquence ODbL | Statut |
|---|---|---|---|
| `data/samples/referentiels/ideo/` — 4 extraits de 300 lignes | **Oui, versionné dans le dépôt remis** | Base dérivée publiquement diffusée : partage à l'identique déclenché | **Conforme** : `data/samples/referentiels/ideo/LICENSE` place explicitement ce dossier sous ODbL, indépendamment du MIT du code, avec producteur, source et date |
| `data/processed/referentiel/naf_rome_formation.csv` — 26 358 lignes, dont la colonne `libelle_formation_ideo` | **Non aujourd'hui** : `data/processed/` est exclu du dépôt par `.gitignore` | Le partage à l'identique **ne se déclenche pas** tant que le fichier reste sur le poste | Conforme aujourd'hui, **à requalifier dès l'exposition par l'interface** |
| Le modèle appris | Non concerné | Il n'apprend sur aucune donnée IDÉO — l'entraînement ne lit que Parcoursup | Sans objet |

**La décision, et son point de bascule exact.** L'obligation ODbL se déclenche
à la diffusion publique de la base dérivée. Mais l'ODbL vise aussi l'**usage
public** d'une base dérivée qu'on ne diffuse pas : servir un libellé de
formation issu d'IDÉO par une interface accessible au public est un usage de
ce type, et la licence impose alors d'offrir par ailleurs une copie de la base
dérivée sous ODbL.

Je choisis donc, plutôt que de retirer les libellés IDÉO du produit :

1. **publier `naf_rome_formation.csv` sous ODbL** au moment où l'interface
   exposera le terme « débouchés », avec un fichier de licence dédié, à
   l'identique de ce qui est déjà fait pour `data/samples/referentiels/ideo/` ;
2. **attribuer les quatre producteurs de la chaîne** (ONISEP, France
   Compétences, France Travail, INSEE), puisque la table dérivée en mêle
   quatre ;
3. **ne poser aucune mesure technique restrictive** sur cette table —
   l'ODbL l'interdit.

Alternative écartée : retirer `libelle_formation_ideo` de la table dérivée
pour se replacer entièrement sous Licence Ouverte. Écartée parce que ce
libellé est précisément le maillon qui raccorde la chaîne à un lecteur humain
— sans lui, la table relie des codes à des codes. Le coût de la conformité
ODbL se limite ici à un fichier de licence et à une ligne d'attribution : il
est très inférieur au coût fonctionnel du retrait.

**Ce qui me ferait changer d'avis** : si une contrainte contractuelle
interdisait un jour de publier la table dérivée sous ODbL — par exemple si
elle intégrait une donnée propriétaire d'un client — alors le retrait des
champs IDÉO redeviendrait la seule issue, et le libellé de formation devrait
être repris d'une source sous Licence Ouverte.

## 3. La licence n'est jamais une base légale

Confusion à ne pas commettre, et qui vaut pour S2 en particulier : la Licence
Ouverte règle le droit de **réutiliser une information publique** (propriété
intellectuelle, droit *sui generis* du producteur de base de données). Elle ne
dit rien du droit des données personnelles. Les deux régimes **se cumulent** :
une donnée peut être librement réutilisable au titre de la licence et rester
une donnée personnelle soumise au RGPD.

C'est exactement le cas des lignes d'entrepreneur individuel de Sirene, dont
la base légale — intérêt légitime, article 6.1.f — est établie séparément
(registre des traitements, T2 et T3).

## 4. Les artefacts dérivés, et le régime qui leur est attaché

| Artefact | Sources combinées | Régime résultant | Publiable en l'état ? |
|---|---|---|---|
| `data/samples/` (17 fichiers, 1,2 Mo) | S1, S2, S3, S4 | Mixte : ODbL sur le sous-dossier IDÉO, Licence Ouverte ailleurs, MIT pour le code | **Oui, et déjà publié** — c'est le seul dossier de `data/` versionné |
| `data/processed/referentiel/naf_rome_formation.csv` | S3, S4, S5, S6 | **ODbL par contamination** du champ IDÉO | Oui, **sous réserve** d'y joindre la licence ODbL et l'attribution des quatre producteurs |
| `data/processed/sirene/agregats_commune_naf.parquet` | S2 seule | Licence Ouverte v2.0 | Oui côté licence — **non côté RGPD en l'état**, voir le seuil de k-anonymat arrêté dans `risques.md` (R2) |
| `data/processed/parcoursup/*.parquet` (modèle en étoile) | S1 seule | Licence Ouverte v2.0 | Oui |
| Le modèle appris et sa Model Card | S1 seule | Licence Ouverte v2.0 pour la donnée d'entraînement ; le modèle est une création du projet | Oui, avec attribution du MESR |

## 5. Ce que je surveille dans le temps

| Source | Cadence de publication | Risque de rupture identifié | Où le contrôle est fait |
|---|---|---|---|
| S1 Parcoursup | Annuelle, en fin de campagne | Schéma croissant : 85 colonnes en 2018, 118 en 2025. Une colonne nouvelle non classée **fait échouer la chaîne** | `tests/data/test_variables_reference.py` |
| S2 Sirene | Mensuelle ; dernier stock 2026-08-01 | URL différente chaque mois — jamais codée en dur, résolue par le catalogue ; **bascule NAF 2025 prévue début 2027**, la clé d'agrégat en dépend | `src/edumatch/ingestion/sirene.py`, ADR 0005 ; `nb_naf25_renseigne` mesure déjà la couverture, à 100,0 % |
| S3 IDÉO | Ponctuelle, aucun engagement de fréquence — dernier contenu daté du 2026-07-06 | Donnée qui vieillit sans signal ; seuil de fraîcheur à documenter faute d'engagement de la source | contrôles de fraîcheur, `src/edumatch/quality/` |
| S4, S5 RNCP | Quotidienne | Le nombre de fiches change chaque jour : la **commande** est reproductible, sa **sortie** ne l'est pas | ADR 0007 (datation quotidienne de l'export) |
| S6 France Travail ROME/NAF | Aucune cadence connue | Nom de fichier variable à chaque révision du ROME ; idempotence assurée par empreinte SHA-256, pas par date | `src/edumatch/ingestion/_referentiels_france_travail.py` |

## 6. Ce que ce registre ne couvre pas encore

- **L'écran « Sources et licences » n'existe pas** : l'obligation
  d'attribution des cinq jeux sous Licence Ouverte n'est donc pas encore
  satisfaite vis-à-vis d'un utilisateur final. Elle l'est vis-à-vis d'un
  lecteur du dépôt, par les manifestes et par ce registre.
- **La publication ODbL de la table dérivée est décidée, pas faite** : elle
  n'a de sens qu'au moment où l'interface l'expose.
- **Aucune source sous licence non commerciale, ni sous clause de réciprocité
  autre que l'ODbL, n'est utilisée** — vérifié source par source. C'est ce qui
  rend le projet réutilisable par une société sans reprise du travail.

---
*Étape E40 · rédigé le 2026-08-30.*
