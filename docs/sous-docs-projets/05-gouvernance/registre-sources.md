# Registre des sources et de leurs licences

**Critère servi** : Bloc 1, 1.4 · **Dernière revue** : 2026-08-30 ·
**Prochaine revue obligatoire** : à chaque ajout de source, et au plus tard à
l'ouverture de la campagne Parcoursup suivante (janvier 2027).

Pour chaque source j'indique qui la produit, sous quelle licence, ce que cette
licence m'oblige à faire, ce que j'ai réellement téléchargé, quand, et où la
preuve se trouve dans le dépôt.

Je ne recopie pas les licences à la main : chaque connecteur écrit la licence,
l'URL, la date et l'empreinte SHA-256 de chaque fichier dans un manifeste
(`data/raw/*/manifeste.json`, `data/external/referentiels/manifeste.json`,
`data/samples/manifeste.json`). Ce registre commente ces manifestes, il ne s'y
substitue pas : en cas de divergence, le manifeste fait foi, car c'est lui
qu'un programme a écrit à partir du fichier réel.

---

## 1. Les six sources entrantes

| # | Source | Producteur | Licence | Volumétrie mesurée | Récupérée le | Preuve |
|---|---|---|---|---|---|---|
| S1 | Parcoursup, 8 millésimes 2018-2025 | MESR | Licence Ouverte v2.0 (Etalab) | 104 274 formation-années, 118 colonnes en 2025, 82 Mo | 2026-08-28 | `data/raw/parcoursup/manifeste.json` |
| S2 | Base Sirene, 4 fichiers de stock | INSEE | Licence Ouverte v2.0 (Etalab) | 4 fichiers Parquet, 4,63 Go ; `StockEtablissement` = 43 896 818 lignes, 54 colonnes | 2026-08-28, stock publié le 2026-08-01 | `data/raw/sirene/manifeste.json` |
| S3 | IDÉO, 4 jeux (formations, métiers, structures secondaire/supérieur) | ONISEP | ODbL v1.0 (`odc-odbl`) | 5 869 + 1 534 + 15 293 + 8 985 lignes, 15,9 Mo | 2026-08-29 | `data/external/referentiels/manifeste.json`, entrées `ideo:*` |
| S4 | RNCP et Répertoire spécifique, export CSV | France Compétences | Licence Ouverte v2.0 (Etalab) | 30 484 fiches dont 7 000 actives, 16 colonnes | 2026-08-29 / 08-30 | entrées `rncp:2026-08-29`, `rncp:2026-08-30` |
| S5 | RNCP, membre « codes ROME » de la même archive | France Compétences | Licence Ouverte v2.0 (Etalab) | 24 424 fiches couvrant au moins un code ROME, 4 353 036 o | 2026-08-30 | entrée `rncp_rome:2026-08-30` |
| S6 | Table de correspondance ROME / NAF | France Travail | Licence Ouverte v2.0 (Etalab) | 112 896 o, correspondance à la division NAF (2 chiffres) | 2026-08-30 | entrée `france_travail_rome_naf:rome_naf` |

Toutes les volumétries sont mesurées sur le fichier réellement posé sur
disque, pas reprises d'un catalogue. Le détail des commandes, et les trois
chiffres que j'ai dû corriger en cours de route (volumétrie compressée de
Sirene, nombre d'établissements, nombre de fiches RNCP faussé par mon propre
outil de comptage), sont dans `01-donnees/sources.md`.

## 2. Ce que chaque licence m'oblige à faire

### Licence Ouverte v2.0 (S1, S2, S4, S5, S6)

Vérifiée sur le texte de la licence (Etalab), pas sur son résumé :

| Point de contrôle | Réponse |
|---|---|
| Réutilisation commerciale autorisée ? | Oui, sans restriction |
| Attribution obligatoire ? | Oui : paternité et date de la dernière mise à jour |
| Partage à l'identique ? | Non |
| Durée ? | Non limitée |
| Compatible avec un projet porté par une société ? | Oui |

Une mention générique « source : données publiques » ne suffit pas, car elle
omet la date. J'en fais donc un écran « Sources et licences » côté conseiller,
alimenté par les manifestes (pas par une liste écrite en dur, qui deviendrait
fausse au stock Sirene suivant) : producteur, intitulé, licence, date du
fichier utilisé. **Statut au 2026-09-17 : non implémenté** : l'écran
conseiller existe, mais ne porte pas encore cette rubrique (motif E). Inscrit au registre des risques sous R7.

### ODbL v1.0, S3 (IDÉO / ONISEP)

L'ODbL impose le partage à l'identique de toute base dérivée. Trois artefacts
du dépôt contiennent de la donnée IDÉO :

| Artefact | Redistribué ? | Statut |
|---|---|---|
| `data/samples/referentiels/ideo/`, 4 extraits de 300 lignes | Oui, versionné | Conforme : `LICENSE` dédié place ce dossier sous ODbL, producteur et date indiqués |
| `data/processed/referentiel/naf_rome_formation.csv`, colonne `libelle_formation_ideo` | Non aujourd'hui, dossier exclu par `.gitignore` | Conforme aujourd'hui, à requalifier dès l'exposition par l'interface |
| Le modèle appris | Non concerné, entraîné sur Parcoursup seul | Sans objet |

L'ODbL vise aussi l'usage public d'une base dérivée non diffusée : servir un
libellé IDÉO par une interface accessible au public compte comme un usage de
ce type, ce qui impose d'offrir une copie ODbL de la base dérivée.

Je choisis donc, plutôt que de retirer les libellés IDÉO :
1. publier `naf_rome_formation.csv` sous ODbL quand l'interface exposera les débouchés, avec un fichier de licence dédié ;
2. attribuer les quatre producteurs (ONISEP, France Compétences, France Travail, INSEE) ;
3. ne poser aucune mesure technique restrictive sur cette table, l'ODbL l'interdit.

Alternative écartée : retirer `libelle_formation_ideo` pour repasser sous
Licence Ouverte. Écartée car ce libellé est le maillon qui relie la chaîne à
un lecteur humain, sans lui la table ne relie que des codes. Le coût de la
conformité ODbL (un fichier de licence, une ligne d'attribution) est très
inférieur au coût fonctionnel du retrait.

**Ce qui me ferait changer d'avis** : une contrainte contractuelle interdisant
de publier la table sous ODbL (par exemple si elle intégrait une donnée
propriétaire d'un client). Le retrait des champs IDÉO redeviendrait alors la
seule issue.

## 3. La licence n'est pas une base légale

La Licence Ouverte règle le droit de réutiliser une information publique. Elle
ne dit rien du droit des données personnelles : les deux régimes se cumulent,
une donnée peut être librement réutilisable et rester une donnée personnelle
soumise au RGPD. C'est le cas des lignes d'entrepreneur individuel de Sirene,
dont la base légale (intérêt légitime, article 6.1.f) est établie séparément
(registre des traitements, T2 et T3).

## 4. Les artefacts dérivés, et le régime qui leur est attaché

| Artefact | Sources | Régime | Publiable en l'état ? |
|---|---|---|---|
| `data/samples/` (17 fichiers, 1,2 Mo) | S1, S2, S3, S4 | Mixte : ODbL sur le sous-dossier IDÉO, Licence Ouverte ailleurs, MIT pour le code | Oui, déjà publié |
| `data/processed/referentiel/naf_rome_formation.csv` | S3, S4, S5, S6 | ODbL par contamination du champ IDÉO | Oui, sous réserve d'y joindre la licence et l'attribution |
| `data/processed/sirene/agregats_commune_naf.parquet` | S2 seule | Licence Ouverte v2.0 | Oui côté licence, pas encore côté RGPD, voir k-anonymat dans `risques.md` (R2) |
| `data/processed/parcoursup/*.parquet` | S1 seule | Licence Ouverte v2.0 | Oui |
| Le modèle appris et sa Model Card | S1 seule | Licence Ouverte v2.0 pour la donnée d'entraînement, le modèle est une création du projet | Oui, avec attribution du MESR |

## 5. Ce que je surveille dans le temps

| Source | Cadence | Risque de rupture | Contrôle |
|---|---|---|---|
| S1 Parcoursup | Annuelle | Schéma croissant, 85 colonnes en 2018, 118 en 2025 : une colonne nouvelle non classée fait échouer la chaîne | `tests/data/test_variables_reference.py` |
| S2 Sirene | Mensuelle, dernier stock 2026-08-01 | URL différente chaque mois, jamais codée en dur ; bascule NAF 2025 prévue début 2027 | `src/edumatch/ingestion/sirene.py`, ADR 0005 ; `nb_naf25_renseigne` à 100,0 % |
| S3 IDÉO | Ponctuelle, dernier contenu daté du 2026-07-06 | Donnée qui vieillit sans signal, seuil de fraîcheur à documenter | `src/edumatch/quality/` |
| S4, S5 RNCP | Quotidienne | Le nombre de fiches change chaque jour, commande reproductible, sortie non figée | ADR 0007 |
| S6 France Travail ROME/NAF | Aucune cadence connue | Nom de fichier variable à chaque révision, idempotence par empreinte SHA-256 | `src/edumatch/ingestion/_referentiels_france_travail.py` |

## 6. Ce que ce registre ne couvre pas encore

- L'écran « Sources et licences » n'existe pas : l'attribution des cinq jeux
  sous Licence Ouverte n'est donc pas satisfaite vis-à-vis d'un utilisateur
  final, seulement vis-à-vis d'un lecteur du dépôt.
- La publication ODbL de la table dérivée est décidée, pas faite.
- Aucune source sous licence non commerciale ou à réciprocité autre que
  l'ODbL n'est utilisée, vérifié source par source.

---
*Étape E40, rédigé le 2026-08-30.*
