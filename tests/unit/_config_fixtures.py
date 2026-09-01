"""Le YAML minimal partagé par les tests de `src/edumatch/config.py`.

Isolé du vrai `configs/base.yaml` : les tests de chargement et de validation
ne doivent pas dépendre de son contenu réel, qui évolue indépendamment de ce
qu'ils vérifient.

Module dédié plutôt que porté par `conftest.py` : `tests/unit/conftest.py` et
`tests/data/conftest.py` portent tous deux le nom de module `conftest`, et en
l'absence de `__init__.py` (mode d'import « prepend » de pytest), Python met
en cache le premier des deux importé sous ce nom pour toute la session — un
`from conftest import BASE_YAML` écrit dans un fichier de test résolvait donc
tantôt le bon module, tantôt l'autre, selon l'ordre de découverte des
répertoires, lui-même sensible à l'ajout de nouveaux fichiers de test
ailleurs dans le dépôt. Un nom de module unique élimine l'ambiguïté à la
racine plutôt que de dépendre d'un ordre de collecte non garanti.
"""

from __future__ import annotations

BASE_YAML = """
projet:
  nom: test-projet
  version: "0.0.1"

donnees:
  parcoursup:
    millesimes: [2020, 2021, 2022]
    effectif_minimal_cellule: 1
    identifiants:
      2020: fr-esr-parcoursup_2020
      2021: fr-esr-parcoursup_2021
      2022: fr-esr-parcoursup_2022
    url_export_gabarit: "https://exemple.test/datasets/{identifiant}/exports/csv?delimiter=%3B"
    delimiteur: ";"
  sirene:
    fichiers: [StockEtablissement]
    jeu_de_donnees: base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret
    url_catalogue_gabarit: "https://exemple.test/api/1/datasets/{jeu_de_donnees}/"
    filtres:
      etat_administratif: A
      caractere_employeur: true
      diffusible: true
  referentiels:
    ideo:
      jeux:
        formations:
          url: "https://exemple.test/ideo/formations.csv"
          encodage: utf-8
          delimiteur: ";"
          licence: "ODbL (odc-odbl)"
    rncp:
      jeu_de_donnees: repertoire-national-des-certifications-professionnelles-et-repertoire-specifique
      url_catalogue_gabarit: "https://exemple.test/api/1/datasets/{jeu_de_donnees}/"
      prefixe_ressource: "export-fiches-csv-"
      format_ressource: zip
      nom_fichier_gabarit: "export_fiches_CSV_Standard_*.csv"
      nom_fichier_rome_gabarit: "export_fiches_CSV_Rome_*.csv"
      encodage: utf-8
      delimiteur: ";"
      licence: "Licence Ouverte v2.0"
    france_travail:
      jeu_de_donnees: "58da857388ee384902e505f5"
      url_catalogue_gabarit: "https://exemple.test/api/1/datasets/{jeu_de_donnees}/"
      sous_chaine_titre_ressource: "ROME/NAF"
      format_ressource: xlsx
      licence: "Licence Ouverte v2.0"
  echantillons_test:
    lignes_par_millesime_parcoursup: 5
    lignes_par_fichier_sirene: 5
    lignes_par_jeu_ideo: 5
    lignes_rncp: 5
    taille_lot_sirene: 100

modele:
  type: lightgbm
  objectif: regression_proportion
  ponderation: effectif_cellule
  variables:
    cles: [session, cod_aff_form]
    dimensions_cellule: [type_bac, boursier]
    session_courante: [fili, dep]
    decalees: [voe_tot, capa_fin]
    decalees_sous_reserve: [acc_tb]
    exclues:
      pct_f: interdite
      cod_uai: substitut
  split:
    entrainement: [2020, 2021]
    validation: [2022]
    test: [2023]
  hyperparametres:
    num_leaves: 31
    max_depth: 8
    learning_rate: 0.05
    min_child_samples: 20
    reg_alpha: 0.1
    reg_lambda: 0.1
    n_estimators: 100
    early_stopping_rounds: 10
  inclure_taux_precedent: true

evaluation:
  metrique_principale: mae_ponderee
  calibration: true
  n_tranches_calibration: 10
  courbe_apprentissage: [0.5, 1.0]
  baseline: taux_session_precedente

equite:
  dimensions: [type_bac]
  variables_interdites: [genre]
  substituts_a_tester: []
  seuil_impact_disparate: 0.80

ablation:
  seuil_gain_mentions: 0.01

explicabilite:
  top_n_figure: 5
  effectif_minimal_exemple: 10

matching:
  k_anonymat_debouches: 5
  seuil_saturation_etablissements: 20
  facteur_territoire_hors_zone: 0.6

qualite:
  parcoursup:
    seuil_completude: 0.99
    tolerance_reconstruction_pourcentage: 0.5
    age_max_jours_avertissement: 400
  sirene:
    seuil_completude: 0.99
    age_max_jours_avertissement: 60
  referentiels:
    seuil_completude: 0.99
    age_max_jours_avertissement_ideo: 200
    age_max_jours_avertissement_rncp: 3

rag:
  jeux_indexes: [formations]
  top_k: 4
  seuil_similarite_minimale: 0.05
  modele_generation: mistral-small-latest

derive:
  reference: distribution_entrainement
  tests: [psi]
  seuil_reentrainement: 0.20

api:
  slo_latence_p95_ms: 300
  max_formations_evaluees: 500
  top_n_max: 50
  audit:
    delai_pseudonymisation_jours: 365
    delai_agregation_jours: 1095

orchestration:
  tentatives_max: 3
  delai_reprise_secondes: 1
  facteur_backoff: 2.0
  planification:
    parcoursup: "@yearly"
    sirene: "@monthly"
    referentiels: "@daily"
    purge_audit: "@daily"
"""

DEV_YAML = """
herite_de: base.yaml

modele:
  hyperparametres:
    n_estimators: 5

execution:
  moteur_volume: local
  niveau_journal: DEBUG
"""
