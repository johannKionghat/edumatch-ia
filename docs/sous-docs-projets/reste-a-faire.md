# Reste à faire

Feuille de route vivante. Je la tiens à jour au fil du projet et des
évaluations du jury.

**État au démarrage** : l'architecture est en place, le dépôt est initialisé,
**aucun code métier n'est écrit**. Tout ce qui suit est à construire.

---

## Ce qui est fait

| Élément | État |
|---|---|
| Arborescence normée | ✅ |
| Dépôt Git, `.gitignore` vérifié, `.gitattributes` | ✅ |
| `Makefile` auto-documenté, cible `make data` | ✅ |
| `configs/` — base, dev, staging, prod | ✅ |
| `pyproject.toml`, `docker-compose.yml`, `.env.example` | ✅ |
| `README` — structure commentée, démarrage | ✅ |
| Architecture de référence, C4 niveaux 1 et 2 | ✅ |
| ADR 0001 — ELT plutôt qu'ETL | ✅ |
| Dépôts distants `edumatch-ia` et `edumatch-cicd`, contenu audité | ✅ |
| Note de vérification des sources (`01-donnees/sources.md`) et script associé | ✅ |
| `config.py` — configuration centralisée typée, validée au démarrage | ✅ |
| `ingestion/parcoursup.py` — connecteur des 8 millésimes, idempotent | ✅ |
| `ingestion/_flux.py` — primitives partagées (flux, empreinte, écriture atomique, manifeste) | ✅ |
| `ingestion/sirene.py` — connecteur des 4 fichiers stock, résolution dynamique du catalogue mensuel | ✅ |
| `ingestion/referentiels.py`, `_referentiels_rncp.py`, `_referentiels_communs.py` — connecteur ONISEP + RNCP, idempotence par date de publication pour le RNCP | ✅ |
| `data/samples/` — 17 échantillons versionnés, générés par `ingestion/echantillons.py`, régime juridique documenté (pseudonymisation, intérêt légitime) | ✅ |
| `notebooks/01-jgk-eda-label.ipynb` — grain, schéma inter-millésimes, définition et bornage du label (ADR 0009) | ✅ |
| `notebooks/02-jgk-eda-ecarts-selectivite.ipynb` — écarts entre bacs, sélectivité, fuite fonctionnelle (ADR 0010) | ✅ |
| `notebooks/03-jgk-eda-equite-substituts.ipynb` — équité à l'admission, substituts du genre (ADR 0011) | ✅ |
| `notebooks/04-jgk-eda-stabilite-millesimes.ipynb` — stabilité inter-millésimes, protocole d'évaluation révisé (ADR 0012) | ✅ |

**Reste sur l'infrastructure** : protection de branche `main` — indisponible
sur dépôt privé en offre gratuite, compensée par le gate de vérification.

---

## Priorités du jury

*Aucune évaluation à ce jour. Lancer `/jury` une fois les premières briques
posées.*

---

## Bloc 1 — Gouvernance des données

- [ ] Plan de gouvernance : classification, rôles, règles d'usage
- [ ] Registre des traitements
- [ ] Registre des sources et de leurs licences — les 4 licences sont déjà
      identifiées et enregistrées dans les manifestes de chaque connecteur
      (Parcoursup, Sirene, RNCP : Licence Ouverte v2.0 ; ONISEP/IDÉO : ODbL,
      partage à l'identique obligatoire sur toute base dérivée redistribuée).
      La base légale du traitement « échantillons de test » (intérêt
      légitime, art. 6.1.f) et l'attribution des 4 producteurs sont
      également établies (E08). Le registre lui-même reste à écrire en E40 :
      pas anticipé maintenant, pour respecter l'ordre du plan d'exécution du
      projet — la matière est prête dans `01-donnees/sources.md`,
      `01-donnees/echantillons.md`, `03-pipeline/ingestion.md` et l'ADR 0008,
      et amorcée dans `05-gouvernance/`
- [ ] AIPD — obligatoire, profilage de mineurs
- [ ] Model Card
- [ ] Matrice de risques
- [ ] Correspondance AI Act, articles 9 à 15
- [ ] Politique de gestion des secrets, avec l'incident documenté
- [ ] Procédure d'audit annuelle
- [ ] Slides de présentation, 15 min

## Bloc 2 — Architecture de données

- [ ] `config.py` — Pydantic Settings, chargement des YAML par environnement
- [ ] Modèle en étoile — schéma dbt, grain écrit
- [ ] Diagrammes C4 exportés en image pour le dossier
- [ ] `docker/Dockerfile.train`, `docker/Dockerfile.serve`
- [ ] Terraform — cluster, base, stockage objet, réseau *(dépôt 2)*
- [ ] Manifestes Kubernetes, dont le HPA *(dépôt 2)*
- [ ] Prometheus et Grafana *(dépôt 2)*
- [ ] Vidéo de l'infrastructure en production

## Bloc 3 — Pipelines

- [x] `ingestion/parcoursup.py` — 8 millésimes, idempotent, écriture atomique
      (docstring aligné sur les 82 Mo mesurés en E05, vérifié le 2026-08-29)
- [x] `ingestion/sirene.py` — catalogue mensuel, Parquet
- [x] `ingestion/referentiels.py` — ONISEP, RNCP, IDÉO — connecteur écrit,
      120 tests passants, 22 Mo réellement téléchargés le 2026-08-29
- [x] `data/samples/` — échantillons versionnés des 3 sources, 145 tests
      passants sans `data/raw/` ni `data/external/` (E08, 2026-08-29). Régime
      juridique des échantillons Sirene (pseudonymisation, entrepreneurs
      individuels) documenté et à reprendre dans le registre des sources
      (E40) — voir `01-donnees/echantillons.md`
- [x] `quality/` — schéma, complétude, cohérence, fraîcheur, **bloquantes** (E14)
- [x] `transform/` — projet dbt, bronze → silver → gold, tests et lignage (E15, E16)
- [x] `spark/` — 9 colonnes, filtres, agrégats commune × NAF, deux moteurs
      (Polars et Spark, même résultat vérifié), 1 929 179 cellules produites
      (E17, 2026-08-30) — voir `03-pipeline/agregats-sirene.md` et l'ADR 0016.
      **Point ouvert reporté ci-dessous** : la taille des cellules et son
      articulation avec la protection des données
- [ ] `referentiel/naf_rome_formation.csv` — actif versionné, **taux de couverture mesuré**
- [ ] `features/label.py` — taux d'admission par cellule, pondération
- [ ] `features/build.py` — variables N-1 à N-3 uniquement, **anti-fuite**
- [ ] `pipelines/edumatch_pipeline.py` — DAG complet, reprise, blocage qualité
- [ ] Tests : idempotence, anti-fuite, contrats de données
- [ ] Vidéo du pipeline, **avec panne provoquée et reprise**

## Bloc 4 — Déploiement

- [x] `models/baseline.py` — taux de la session précédente, plancher mesuré
      (E21, 2026-08-30)
- [x] `models/train.py` — LightGBM pondéré, MLflow, comparé au plancher à
      couverture égale (E22, 2026-08-30). Résultat mitigé : le modèle bat le
      plancher en validation, reste derrière en test — voir
      `04-modele/evaluation.md`
- [x] `models/evaluate.py` — MAE pondérée, calibration, ECE, courbe
      d'apprentissage (E23-E24, 2026-08-30). En test, le modèle perd sur les
      deux tableaux, précision et calibration, contre le plancher
- [x] `models/explain.py` — TreeSHAP, précalcul par cellule (E25,
      2026-08-30) — voir `04-modele/explicabilite.md`
- [x] `models/fairness.py` — 4 dimensions, ratio d'impact disparate (E26,
      2026-08-30). Écart réel détecté sur les formations très féminisées,
      ratio d'impact disparate sous le seuil légal des quatre cinquièmes
      (0,76) — voir `04-modele/equite.md`
- [ ] `models/ablation.py` — apport de Sirene mesuré, pas postulé. **En
      cours d'écriture** ; un obstacle est déjà identifié, voir le point
      ouvert ci-dessous
- [ ] `matching/affinite.py`, `debouches.py`, `score.py`
- [ ] `api/main.py`, `routes/`, schémas Pydantic
- [ ] `api/audit.py` — journalisation article 12
- [ ] `api/static/` — écran conseiller, **conforme RGAA**
- [ ] `rag/` — assistant, brique secondaire, **réécrit** et non repris du MVP
- [ ] CI/CD — trois workflows *(dépôt 2)*
- [ ] Evidently — dérive, seuil documenté en ADR
- [ ] Vidéo de la solution en production

---

## EDA — préalable au Bloc 4

- [x] `notebooks/01-jgk-eda-label.ipynb` — distribution du label par cellule
      (E09, 2026-08-29). Grain établi, schéma des 8 sessions réconcilié,
      définition du label et son bornage arrêtés en ADR 0009 — voir
      `01-donnees/label.md`
- [x] `notebooks/02-jgk-eda-ecarts-selectivite.ipynb` — écart entre types de
      baccalauréat (E10, 2026-08-29). Comparaison appariée, hétérogénéité par
      filière (BTS neutre à CPGE +42,3 points), fuite fonctionnelle de
      `voe_tot` identifiée et traitée en ADR 0010 — voir `01-donnees/label.md`
- [x] Sélectivité par filière — couverte dans le même carnet (E10) : la
      tension `voe_tot / capa_fin` explique le taux de 1,000 à 0,182 du
      quintile le moins tendu au plus tendu
- [x] `notebooks/03-jgk-eda-equite-substituts.ipynb` — taux de féminisation
      par filière, écart d'admission à formation égale, corrélations
      corrigées de cardinalité (E11, 2026-08-29) — voir `04-modele/equite.md`
      et l'ADR 0011
- [x] Corrélations — les substituts du genre — couverte dans le même carnet
      (E11) : l'académie, désignée à surveiller, n'explique que 1,4 % net ;
      la filière en explique 19,5 % et ne peut pas être retirée — dispositif
      d'équité à trois niveaux retenu
- [x] `notebooks/04-jgk-eda-stabilite-millesimes.ipynb` — stabilité
      inter-millésimes (E12, 2026-08-29). Label calculable sur six sessions
      seulement (2020-2025), volumétrie corrigée à 440 030 cellules,
      protocole d'évaluation révisé (ADR 0012) — voir `04-modele/evaluation.md`
- [x] Décision de variables — classement sans reste des 128 colonnes (9 en
      liste blanche, 35 décalées, 8 de mention en réserve, 73 exclues), écrit
      dans `configs/base.yaml` et vérifié par 4 contrôles de contrat (E13,
      2026-08-29, ADR 0013) — voir `04-modele/specification.md` et
      `04-modele/equite.md`

**Phase exploratoire close** (E09 à E13). La phase suivante (qualité et
transformation) s'ouvre sur E14, contrôles qualité bloquants, **validée le
2026-08-29** — voir `03-pipeline/qualite.md` et l'ADR 0014.

---

## Point ouvert issu des contrôles qualité (E14)

- [ ] **Pas de contrôle de schéma dédié pour `StockEtablissementHistorique`,
      `StockUniteLegale` et `StockUniteLegaleHistorique`.** Seul
      `StockEtablissement` porte les 9 colonnes utiles au projet et reçoit un
      contrôle de schéma, complétude et cohérence complet ; les trois autres
      fichiers Sirene ont des colonnes différentes (`siren`, pas de `siret`
      pour l'unité légale) et ne sont soumis qu'au contrôle de fraîcheur. À
      construire quand un traitement du pipeline commencera à les lire
      (E18 pour la table de nomenclatures, potentiellement).

## Point ouvert issu de l'agrégat Sirene (E17)

- [ ] **La taille des cellules `(commune, NAF)` n'est pas traitée.** Mesuré
      sur l'agrégat produit : 584 489 des 886 688 cellules qui portent au
      moins un établissement actif-employeur (65,9 %) n'en portent qu'un
      seul, 135 162 en portent 2, 54 808 en portent 3. Deux conséquences non
      résolues à ce stade, détaillées dans `03-pipeline/agregats-sirene.md` :
      une cellule à effectif 1 n'est pas un agrégat statistiquement
      exploitable pour le terme « débouchés » du score (E28) ; et une
      cellule à effectif 1 ou 2 identifie quasi directement un établissement,
      alors que les données Sirene sont pseudonymisées et non anonymisées
      (ADR 0008), et que les 20 501 établissements non diffusibles ne sont
      pas filtrés à cette étape. La décision (maille plus grossière,
      lissage, ou autre) relève à la fois de la protection des données et de
      la construction du score : à trancher au plus tard à l'E28, pas
      anticipée ici.

## Points ouverts issus de la décision de variables (E13)

Trois points non tranchés à l'issue de l'ADR 0013, à ne pas laisser
s'oublier avant la construction des variables (E20) et l'entraînement (E22).

- [ ] **`capa_fin` — arbitrage qui me revient.** Parcoursup affiche un
      nombre de places sur chaque fiche pendant la campagne, mais la colonne
      du fichier de résultats s'appelle « capacité finale », et rien dans
      les fichiers dont je dispose ne prouve que les deux coïncident.
      Classée décalée par prudence en attendant. Trancher demande de
      comparer une fiche affichée en cours de campagne au fichier publié
      ensuite — une vérification hors des données du dépôt. Le gain serait
      réel si les deux coïncident : `capa_fin` passerait en liste blanche et
      deviendrait le dénominateur direct de la tension, mon meilleur
      prédicteur pressenti.
- [ ] **Le taux décalé manque pour toute la session cible 2020.**
      `prop_tot_{bg|bt|bp}[_brs]` n'existe pas en 2019 (ADR 0012). La
      variable la plus prédictive du jeu — le taux observé de la même
      cellule l'année précédente — est donc absente pour un quart des
      sessions d'entraînement. Valeurs laissées manquantes de façon
      explicite, sans imputation. Conséquence à ne pas oublier lors de
      l'entraînement (E22) : la baseline de session précédente (E21) n'est
      mesurable que sur 2021-2025, pas sur l'ensemble de l'entraînement.
- [ ] **Le contrôle anti-fuite automatique ne vérifie que des noms de
      colonnes, pas leur sémantique.** Il attrape l'ajout distrait d'un
      compteur à la liste blanche des 9 colonnes de session prédite ; il ne
      prouve pas que ces 9 colonnes sont réellement publiées avant
      l'ouverture de la campagne. Cette preuve relève du raisonnement de
      l'ADR 0013, pas d'un test automatisé — à rappeler si la liste blanche
      est un jour étendue.

---

## Points ouverts issus du modèle (E22 à E26)

- [ ] **L'ablation de Sirene, prévue par le plan d'exécution du projet, est
      impossible à mesurer aujourd'hui.** La chaîne de nomenclatures
      NAF ↔ ROME ↔ formation (E18) n'atteint aucune formation Parcoursup :
      la table de correspondance ne couvre, en l'état, aucune des formations
      du jeu de variables construit en E20. Sans cette jointure, aucune
      variable issue des agrégats Sirene n'entre dans le modèle entraîné en
      E22, et l'écart avec/sans Sirene que l'ablation doit mesurer ne peut
      pas être calculé — il n'existe simplement rien à retirer. À traiter
      avant de poursuivre l'écriture de `models/ablation.py` : soit la
      couverture de la chaîne de nomenclatures se corrige, soit l'ablation
      rapporte un écart nul faute de jonction possible, ce qui est un
      résultat en soi, mais alors distinct d'un apport nul de la source.

- [ ] **⚠️ INCOHÉRENCE — un chiffre d'équité diverge entre l'analyse
      exploratoire et l'audit du modèle.** L'analyse exploratoire (E11,
      `04-modele/equite.md`) mesure que l'écart d'admission entre femmes et
      hommes, à formation égale, reste inférieur à 5 points dans **83,8 %**
      des cas. L'audit d'équité sur les prédictions (E26,
      `src/edumatch/models/fairness.py`) rapporte un chiffre différent sur
      une question voisine, **73,4 %**. Les deux mesures ne portent
      vraisemblablement pas sur le même filtre d'effectif minimal par
      formation (l'E11 impose au moins 30 vœux de chaque sexe ; l'E26 audite
      la totalité du test 2025 sans ce même plancher), mais ce n'est pas
      vérifié — seulement l'hypothèse la plus probable. Je ne corrige ni le
      code ni le chiffre : à réconcilier avant d'écrire la Model Card (E42),
      qui ne peut pas porter deux chiffres contradictoires sur le même
      objet.

- [ ] **La borne de version de `numpy` n'est pas fixée après l'installation
      de `shap`.** Installer `shap` pour l'explicabilité (E25) a fait passer
      `numpy` de 1.26 à 2.4.6 sur le poste de développement, sans que ce
      changement soit demandé pour lui-même. La suite complète de tests
      passe avant et après ce changement, vérifié deux fois, donc aucune
      régression n'est constatée à ce jour — mais `pyproject.toml` ne borne
      pas encore la version de `numpy`, ce qui laisse la reproductibilité de
      l'environnement dépendre de l'ordre d'installation des paquets plutôt
      que d'une contrainte explicite. À corriger avant l'étape
      d'industrialisation (E35-E36), où l'image de conteneur doit être
      reproductible par construction.

---

## ⚠️ Incohérences relevées

**✅ RÉSOLU — volumétrie du label dans le dossier de certification**
(constatée le 2026-08-29 en documentant E12, corrigée le 2026-08-30)

Le dossier annonçait « 77 159 cellules exploitables par millésime ; 560 000 à
625 000 observations sur les huit sessions ». `_build_dossier.py` a été
corrigé pour annoncer les chiffres réels (440 030 cellules exploitables sur
les six sessions 2020-2025, ADR 0012) et le `.docx` régénéré.
`ARCHITECTURE_EduMatch.md` a été relu à cette occasion : il affiche déjà
440 030 cellules à l'endroit visé, rien à y corriger.

---

**✅ RÉSOLU — trois incohérences dossier ↔ dépôt** (relevées et corrigées le
2026-08-30, à l'occasion d'une revue croisée dossier de certification /
ADR / documentation technique)

1. Le §6 (Bloc 3) annonçait des contrôles qualité « Great Expectations » —
   l'ADR 0014 écarte cet outil et retient Pandera pour `parcoursup.py`, des
   compteurs écrits à la main pour `sirene.py` et `referentiels.py`. Corrigé.
2. Le §6 annonçait « chaîne de volume traitée en distribué avec PySpark » —
   l'ADR 0016 mesure Spark 4,8 fois plus lent que Polars sur le fichier
   Sirene complet (87,0 s contre 18,2 s), retient Polars en exécution
   courante et Spark comme moteur implémenté, testé, branché sur le mode
   cluster pour la trajectoire de volume (historique Sirene à 95,9 M
   lignes, republication mensuelle). Le §6 racontait l'inverse de ce que le
   projet a mesuré et assumé ; réécrit pour porter cette mesure et son
   seuil de bascule.
3. Le §7 se contredisait dans la même page : « 440 030 observations sur les
   six sessions … 2020-2025 » puis, six lignes plus bas, « entraînement
   2018-2023 ». Le protocole réel (ADR 0012, `04-modele/evaluation.md`) est
   entraînement 2020-2023 (286 463 cellules), validation 2024 (76 408),
   test 2025 (77 159) — corrigé, et la raison de la borne à six sessions
   (numérateur du label absent en 2018-2019) explicitée dans le tableau.

En corrigeant le point 3, une ambiguïté connexe a été traitée : la table de
composition du score (§1.2 et §7) citait « Parcoursup, huit millésimes »
comme source du terme d'accessibilité, sans distinguer le fichier brut
(8 sessions) du volume exploitable pour l'entraînement (6 sessions) — l'ADR
0012 demande explicitement cette distinction partout où le chiffre est
cité. Les deux cellules de tableau précisent maintenant les deux volumes.

---

**✅ RÉSOLU — chiffres de féminisation obsolètes dans le dossier** (relevé et
corrigé le 2026-08-30)

Le §1.1 citait encore « 2 954 formations (20,7 %) à moins de 20 % de femmes »
et « 21,3 % » de formations en zone équilibrée. `04-modele/equite.md` documente
une correction de méthode déjà actée : ce chiffre incluait 179 formations à
dénominateur nul (aucun candidat admis), où le taux de féminisation vaut
mécaniquement 0 % sans rien dire de la féminisation d'un processus qui n'a
pas eu lieu. Le chiffre corrigé, dénominateur non nul, est 2 775 formations
(19,7 %), 17,9 % à plus de 80 % de femmes, 21,5 % en zone équilibrée. Le
dossier reprenait la version pré-correction ; corrigé pour aligner ce
paragraphe sur `04-modele/equite.md`.

---

**✅ RÉSOLU — code de certification dans l'en-tête du dossier** (relevée le
2026-08-30, tranchée par moi le jour même : AIA02 est le bon
code, corrigé dans `_build_dossier.py`)

L'en-tête indiquait « Architecte en Intelligence Artificielle - Mastère 2
(AIA01) ». Le code retenu est AIA02, conforme au nom du dossier de travail.
Corrigé, `.docx` régénéré.

---

**✅ RÉSOLU — présent utilisé pour des composants non construits** (relevée
le 2026-08-30 pour le seul paragraphe RAG, généralisée et corrigée le même
jour selon la règle que je me suis fixée : « ce qui n'est pas construit passe
au futur »)

Vérification component par component contre le code réel du dépôt (pas
seulement le RAG) :

| Composant cité dans le dossier | Présent dans le dépôt ? | Vérifié par |
|---|---|---|
| Ingestion Parcoursup/Sirene/référentiels, contrôles qualité Pandera | Oui | `src/edumatch/ingestion/`, `src/edumatch/quality/`, E05-E14 validées |
| Réconciliation des 8 millésimes, entrepôt en étoile | Oui | `src/edumatch/transform/`, dbt gold, E15-E16 validées |
| Agrégats Sirene (Polars + Spark) | Oui | `src/edumatch/spark/`, E17 validée |
| Chaîne NAF↔ROME↔formation | Oui | `src/edumatch/referentiel/`, E18 validée |
| Label et pondération, variables, anti-fuite | Oui | `src/edumatch/features/`, E19-E20 validées |
| Baseline, entraînement LightGBM tracé MLflow | Oui | `src/edumatch/models/baseline.py`, `train.py` |
| SHAP (explicabilité), calibration, courbe d'apprentissage | Non | `src/edumatch/models/` ne contient ni `explain.py` ni code de calibration ; E23-E25 ⬜ |
| Audit d'équité (parité, égalité des chances, ratio d'impact) | Non | pas de `fairness.py` ; E26 ⬜ (l'analyse exploratoire des substituts, elle, est faite — E11) |
| Ablation Sirene | Non | pas de `ablation.py` ; E27 ⬜ |
| Module de score (`matching/affinite.py`, `debouches.py`, `score.py`) | Non | `src/edumatch/matching/` ne contient qu'un `.gitkeep` ; E28 ⬜ |
| API FastAPI, écran conseiller, journalisation article 12 | Non | `src/edumatch/api/` ne contient que des `.gitkeep` ; E29-E31 ⬜ |
| Chatbot RAG | Non | `src/edumatch/rag/` ne contient qu'un `.gitkeep` ; E32 ⬜ |
| DAG Airflow | Non | `pipelines/` ne contient qu'un `.gitkeep` ; le conteneur Airflow existe dans `docker-compose.yml` mais sans DAG chargé ; E33 ⬜ |
| Détection de dérive Evidently, réentraînement automatique | Non | aucun usage d'`evidently` dans le code (dépendance déclarée, non utilisée) ; E34 ⬜ |
| Conteneurs `Dockerfile.train`/`.serve` | Non | `docker/` ne contient qu'un `.gitkeep` ; E35 ⬜ |
| CI/CD, workflows GitHub Actions, second dépôt | Non | `.github/workflows/` est vide ; E36 ⬜ ; un seul dépôt existe à ce jour |
| Terraform, Kubernetes, HPA | Non | aucun fichier `.tf` ni manifeste Kubernetes dans le dépôt ; E37 ⬜ |
| Monitoring Prometheus/Grafana, SLO | Non | aucune configuration Prometheus/Grafana dans le dépôt ; E38 ⬜ |

Tous les paragraphes du dossier décrivant les lignes « Non » ont été
réécrits au futur, avec la justification déjà arbitrée conservée (le choix
technique reste assumé, seul le temps du verbe change), et une mention
explicite de ce qui n'existe pas encore ainsi que de l'étape du plan qui le
produira. Une correction de contenu accompagne ce changement de temps : le
modèle en étoile (E16, déjà construit) porte les dimensions formation,
candidat, session et territoire — pas de dimension « métier », que le
dossier citait par erreur.

> Toute divergence entre le code, la documentation et le dossier de
> certification est inscrite ici sous cette mention, et remontée. Elle n'est
> jamais corrigée silencieusement.
