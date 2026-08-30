# Réconciliation NAF ↔ ROME ↔ formation

**Étape** : E18 · **Blocs servis** : 3, critère 3.9 (réconciliation des
nomenclatures, couverture mesurée) · **Code** :
`src/edumatch/referentiel/naf_rome_formation.py`,
`src/edumatch/ingestion/_referentiels_france_travail.py`,
`src/edumatch/ingestion/_referentiels_rncp.py` · **Décision** : ADR 0017

Cette page couvre l'étape qui relie une formation du référentiel ONISEP
(IDÉO) à une activité économique (code NAF), pour préparer le terme
« débouchés » du score de matching (E28). Elle s'appuie sur l'agrégat commune
× NAF déjà produit (`agregats-sirene.md`) et sur le connecteur des
référentiels déjà décrit (`ingestion.md`).

## Pourquoi trois sources, pas une

Aucune table officielle ne relie directement un code NAF à une formation. La
chaîne assemble trois sources publiques réelles, chacune vérifiée
séparément :

```
formation IDÉO --(code RNCP)--> fiche RNCP --(export ROME de l'archive
RNCP)--> code(s) ROME --(table France Travail ROME/NAF)--> division NAF
```

| Source | Fichier | Licence | Rôle dans la chaîne |
|---|---|---|---|
| ONISEP — IDÉO Formations | `data/external/referentiels/ideo/formations.csv` | ODbL | point de départ : une formation portant un code RNCP |
| RNCP — membre ROME de l'archive quotidienne | `rncp_rome_2026-08-30.csv` | Licence Ouverte v2.0 | relie une fiche RNCP à un ou plusieurs codes ROME |
| RNCP — CSV standard de la même archive | `rncp_2026-08-30.csv` | Licence Ouverte v2.0 | expose l'état actif/radié de chaque fiche |
| France Travail — table ROME/NAF | `rome-arborescence-des-secteurs-naf-juin-2026.xlsx` | Licence Ouverte v2.0 | relie un code ROME à une division NAF |

Le membre RNCP↔ROME existait dans l'archive RNCP depuis le début, mais le
connecteur de l'étape des référentiels n'en extrayait qu'un seul CSV sur les
dix que contient l'archive quotidienne. Il a fallu étendre ce connecteur pour
extraire ce second membre (voir « Effets de bord » plus bas).

## La chaîne, maillon par maillon

Mesuré sur les exports du 2026-08-30 (`data/processed/referentiel/naf_rome_formation_couverture.json`) :

| Maillon | Retenus / total | Taux |
|---|---|---:|
| formations IDÉO portant un code RNCP renseigné | 3 857 / 5 869 | 65,72 % |
| fiches de l'export ROME couvrant au moins un code ROME | 24 424 / 24 424 | 100 % |
| formations avec RNCP dont la fiche existe dans l'export ROME du jour | 3 605 / 3 857 | 93,47 % |
| codes ROME de l'export RNCP retrouvés dans la table France Travail | 528 / 572 | 92,31 % |
| **chaîne complète, formation IDÉO jusqu'à une division NAF** | 3 605 / 5 869 | **61,42 %** |
| lignes de la table finale rattachées à une certification active | 25 213 / 26 358 | 95,66 % |
| formations distinctes rattachées à une certification active | 3 412 / 3 605 | 94,65 % |

Chaque jointure vers la NAF est une jointure interne (`inner`) : une ligne
sans correspondance disparaît plutôt que d'apparaître avec des colonnes
nulles. C'est ce tableau, produit par `mesurer_couverture`, qui rend compte
de ce qui a été perdu à chaque étape — jamais un taux global unique.

## La table produite

`data/processed/referentiel/naf_rome_formation.csv` : **26 358 lignes, 8
colonnes** (`code_rncp_ideo`, `libelle_formation_ideo`, `code_nsf`,
`code_rome`, `libelle_rome`, `naf_division`, `naf_division_libelle`,
`rncp_actif`), 4 887 629 octets. Une ligne = un triplet (formation IDÉO, code
ROME, division NAF) : une formation n'a pas « un » débouché NAF mais un
ensemble, la relation étant N:N (une fiche RNCP peut couvrir plusieurs codes
ROME, un code ROME peut apparaître sous plusieurs divisions NAF).

## La colonne d'état, exposée et jamais filtrée

Le répertoire RNCP mêle des fiches actives et des fiches radiées. La colonne
`rncp_actif` (booléenne) porte cet état, joint par une jointure `left` : elle
ne retire aucune ligne, contrairement aux jointures qui construisent la
chaîne elle-même. Mesuré : **25 213 lignes actives, 1 145 radiées (4,3 % des
26 358 lignes), 0 valeur nulle** — aucune fiche présente dans l'export ROME
du jour n'est absente du CSV standard du même jour.

Une certification radiée n'est pas un débouché actuel. Ce n'est pourtant pas
à cette table d'en décider : elle expose l'état par une colonne, et le calcul
des débouchés (E28) choisira d'en tenir compte ou non — exactement comme il
devra décider comment traiter la relation N:N ci-dessus.

## Un fait de qualité de source, rapporté tel quel

Un cas suspect, contrôlé jusqu'à sa source : « BT métiers de la musique »
(code RNCP 919) ressort rattaché au code ROME D1211 « Vente en articles de
sport et loisirs ». Remonté jusqu'à l'export RNCP lui-même : RNCP919 est bien
« Métiers de la musique, Brevet de technicien », et c'est **l'export
officiel du RNCP** qui lui attribue D1211 et L1201 « Danse ». La jointure est
fidèle ; c'est la source qui est bruitée. Ce n'est pas un défaut du code
produit ici, c'est une limite de la donnée publique — je le déclare plutôt
que de le laisser découvrir en soutenance.

## Deux manques déclarés, pas comblés

1. **Aucune formation Parcoursup n'est reliée à cette chaîne.** Vérifié sur
   les fichiers sources : aucun des huit millésimes, ni `dim_formation.parquet`,
   ne porte de code RNCP, NSF ou ROME. La chaîne relie IDÉO à la NAF, pas
   Parcoursup. Le seul rapprochement possible serait un appariement de
   libellés en texte libre (`form_lib_voe_acc`, `fil_lib_voe_acc` côté
   Parcoursup contre le libellé de formation côté IDÉO) : une correspondance
   textuelle floue, pas une jointure sur clé — ce type de correspondance
   ambiguë n'est pas arbitré sans mesure dans ce projet, il n'est donc pas
   implémenté. Voir ADR 0017 pour le seuil qui ferait reconsidérer ce choix.
2. **La correspondance ROME/NAF n'existe qu'au niveau division (2 chiffres).**
   L'agrégat Sirene d'E17 est à la sous-classe (5 caractères) : le
   rattachement à un établissement réel perd la granularité fine de
   l'activité. Aucune source publique ne relie ROME à la sous-classe
   aujourd'hui.

## Reproduire

```bash
make naf-rome
```

Exécute `python -m edumatch.referentiel.naf_rome_formation`. Résout les
quatre sources déjà téléchargées (IDÉO, les deux membres RNCP du jour, la
table France Travail — voir `ingestion.md`), construit la table et le
rapport de couverture, puis écrit :

- `data/processed/referentiel/naf_rome_formation.csv`
- `data/processed/referentiel/naf_rome_formation_couverture.json`

Une source absente lève une erreur explicite qui nomme la commande
d'ingestion à exécuter d'abord, plutôt que d'échouer obscurément plus loin.

Suite de tests complète du dépôt : `python -m pytest -q` → **309 tests, 309
succès** (278 avant cette étape).

## Effets de bord de cette étape

- Le connecteur d'ingestion des référentiels a été étendu : un nouveau membre
  de l'archive RNCP (`telecharger_rome`, le CSV RNCP↔ROME) et une nouvelle
  source (`_referentiels_france_travail.py`, la table ROME/NAF) s'ajoutent à
  ce que téléchargeait déjà `telecharger_tous`.
- Le module qui génère les échantillons de test (`echantillons.py`) a été
  scindé pour rester sous la limite de taille de fichier du projet, l'ajout
  des deux nouvelles sources l'ayant fait dépasser le seuil.
- Un bug d'encodage a été corrigé dans l'écriture atomique partagée par tout
  le projet (`_flux.ecriture_atomique`) : en mode texte, l'encodage n'était
  pas imposé, et Python retombait sur celui de la plateforme (`cp1252` par
  défaut sous Windows). L'écriture n'échouait pas — cp1252 sait encoder un
  accent — mais produisait des octets que la lecture correspondante (déclarée
  en UTF-8) ne savait pas relire : un défaut silencieux à l'écriture, révélé
  seulement à la relecture. Constaté sur un titre de ressource France Travail
  contenant un accent (« référentiels »). Corrigé en imposant `utf-8`
  explicitement en mode texte ; test de non-régression :
  `test_ecriture_atomique_en_mode_texte_ecrit_en_utf8_meme_sans_lencoder_de_la_plateforme`.

## Ce que cette étape ne fait pas encore

- Pas de raccordement au modèle en étoile Parcoursup (`02-architecture/modele-etoile.md`) :
  cette table vit dans `data/processed/referentiel/`, en dehors des cinq
  tables gold.
- Pas d'arbitrage sur la relation N:N (formation → plusieurs divisions NAF)
  ni sur le filtrage des certifications radiées : ces deux choix relèvent du
  calcul des débouchés (E28).
- La question ODbL (partage à l'identique si cette table dérivée, qui
  intègre des données IDÉO, est redistribuée telle quelle) est signalée dans
  `01-donnees/sources.md`, pas tranchée ici : elle relève de la gouvernance
  (E40-E44).

---
*Étape E18 · dernière mise à jour : 2026-08-30.*
