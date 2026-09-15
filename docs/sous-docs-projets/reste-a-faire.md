# Reste à faire

Feuille de route vivante. Je la tiens à jour au fil du projet et des
évaluations du jury.

**État au 2026-09-15** : 41 étapes sur 46 du plan d'exécution du projet sont
validées (`avancement.md`). L'ingestion, la qualité, l'entrepôt, le modèle,
le service et la gouvernance sont construits et testés. L'infrastructure
Terraform/Kubernetes (E37) et le monitoring (E38) sont écrits et vérifiés
dans les fichiers du second dépôt, `edumatch-cicd`, mais rien n'a encore
tourné sur un cluster réel — voir le point ouvert dédié plus bas. Le CI/CD
(E36) reste 🟡 en cours : les trois workflows existent, aucun n'a encore
tourné sur la forge. Ce qui suit liste ce qui reste précisément, sans
ambiguïté avec ce qui est déjà fait.

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

- [x] Plan de gouvernance : classification, rôles, règles d'usage
      (`05-gouvernance/plan-gouvernance.md`, E44, complété le 2026-09-15)
- [x] Registre des traitements (`05-gouvernance/registre-traitements.md`, E40,
      amorcé le 2026-08-30, complété le 2026-09-15 — huit traitements, statut
      « existant » ou « spécifié » explicite par ligne)
- [x] Registre des sources et de leurs licences
      (`05-gouvernance/registre-sources.md`, E40)
- [x] AIPD — obligatoire, profilage de mineurs (`05-gouvernance/aipd.md`, E41,
      version 0.9 le 2026-08-30, complète le 2026-09-15). **Avis scindé, pas
      favorable sans réserve** : défavorable à la restitution du terme appris
      à des candidats réels, le modèle étant battu par la règle de
      dénombrement dans 23 des 27 sous-populations auditées ; favorable sous
      réserves au reste du dispositif ; favorable sans réserve à une
      démonstration encadrée
- [x] Model Card (`05-gouvernance/model-card.md`, E42, format Mitchell,
      performance ventilée par sous-population)
- [x] Matrice de risques (`05-gouvernance/risques.md`, E44)
- [x] Correspondance AI Act, articles 9 à 15 (`05-gouvernance/ai-act.md`, E43)
- [ ] Politique de gestion des secrets, avec l'incident documenté
- [ ] Procédure d'audit annuelle
- [ ] Slides de présentation, 15 min

## Bloc 2 — Architecture de données

- [ ] `config.py` — Pydantic Settings, chargement des YAML par environnement
- [ ] Modèle en étoile — schéma dbt, grain écrit
- [x] Diagrammes C4, niveaux 1 et 2 (`02-architecture/c4-contexte.md`,
      `c4-conteneurs.md`, E45, 2026-09-15) — en Mermaid versionné dans le
      Markdown plutôt qu'en image exportée, pour que le diff montre le
      changement plutôt qu'une image qui se périme en silence
- [ ] `docker/Dockerfile.train`, `docker/Dockerfile.serve`
- [x] Terraform — cluster, base, stockage objet, réseau *(dépôt 2,
      `edumatch-cicd`, E37, 2026-09-15, commit `5ef5ff3`)*. Écrit et
      vérifié en lecture — **jamais appliqué sur un compte Scaleway réel**,
      voir le point ouvert dédié
- [x] Manifestes Kubernetes, dont le HPA *(dépôt 2, même commit)* —
      `requests`/`limits` présents sur les deux conteneurs du déploiement,
      HPA avec un plancher de 2 réplicas et un plafond de 6 sur un seuil CPU
      à 60 %. ⚠️ Une contradiction a été trouvée à la relecture : le
      déploiement fixait `replicas: 2` pendant que le HPA déclarait
      `minReplicas: 1`, qui aurait eu le dernier mot et serait redescendu à
      un seul pod en creux de charge. Corrigée : le HPA porte seul les deux
      bornes (2 pour la disponibilité, 6 pour le rapport de charge mesuré
      entre le pic de la période des vœux et le creux estival), `replicas`
      retiré du déploiement, `PodDisruptionBudget` (`minAvailable: 1`) et
      anti-affinité souple ajoutés. Correction commitée dans le second dépôt
      sous `4e23b85`. Même réserve
      qu'avant sur le reste : rien n'a tourné sur un cluster
- [x] Prometheus et Grafana *(dépôt 2, E38, 2026-09-15, commit `71b2d19`)* —
      cinq alertes, chacune avec une action. Même réserve, et l'API
      n'expose pas encore `/metrics` — voir le point ouvert dédié
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
- [x] `referentiel/naf_rome_formation.csv` — chaîne NAF↔ROME↔formation sur
      trois sources réelles, couverture mesurée maillon par maillon (61,42 %
      de bout en bout) (E18, 2026-08-30) — voir `03-pipeline/reconciliation-naf-rome.md`
      et l'ADR 0017
- [x] `features/label.py` — taux d'admission par cellule, pondération par
      effectif regroupée en un seul lieu (E19, 2026-08-30)
- [x] `features/build.py` — 46 variables, décalage d'une session pour les
      compteurs, contrat anti-fuite vérifié par mutation de code (E20,
      2026-08-30)
- [x] `pipelines/edumatch_pipeline.py` — quatre DAG par cadence de source,
      reprise décidée dans le code, blocage qualité (E33, 2026-09-01).
      Idempotence, blocage et reprise **testés** sur données réelles ; **la
      démonstration filmée reste à produire (E39)** — voir le point ouvert
      ci-dessous
- [x] Tests : idempotence, anti-fuite, contrats de données — couverts par les
      suites citées à chaque étape ci-dessus
- [ ] Vidéo du pipeline, **avec panne provoquée et reprise** (E39, non
      commencée)

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
- [x] `models/ablation.py` — sept variantes mesurées sur la validation 2024
      (E27, 2026-08-31). Le signal de l'an dernier porte l'essentiel de la
      performance (+0,0422 à le retirer, contre +0,0070 à passer de 3 à
      48 variables) ; retirer les substituts du genre ne répare pas
      l'équité (ratio d'impact disparate 0,66 → 0,62) ; les deux exclusions
      de l'ADR 0013 sont confirmées. **L'apport de Sirene reste hors de
      portée de la mesure**, voir le point ouvert ci-dessous — voir
      `04-modele/ablation.md`
- [x] `matching/affinite.py`, `debouches.py`, `score.py` (E28, 2026-09-01).
      Score multiplicatif, un terme nul supprime la recommandation.
      **Couverture du terme débouchés mesurée à 1,4 %** (6 017 lignes sur
      440 030) faute de code RNCP/NSF/ROME dans les millésimes Parcoursup —
      voir le point ouvert ci-dessous — `06-service/score.md`
- [x] `api/main.py`, `routes/`, schémas Pydantic (E29, 2026-09-01). 6
      routeurs, explication lue depuis le précalcul SHAP (jamais recalculée
      en direct), dégradation explicite si Sirene manque, réponse 422 sur
      catalogue trop grand — `06-service/api.md`
- [x] `api/audit.py` — journalisation article 12 et `api/audit_purge.py` —
      purge exécutable (E30, 2026-09-01). Trois paliers testés, idempotents.
      **Déclenchement planifié restant, purge du journal de retour (T6) non
      construite** — voir le point ouvert ci-dessous —
      `06-service/journalisation-purge.md`
- [x] `api/static/` — écran conseiller (E31, 2026-09-01). Écartement bloqué
      côté client et serveur sans motif. **Audit RGAA automatisé fait,
      audit manuel navigateur non déroulé** — voir le point ouvert ci-dessous
      — `06-service/ecran-conseiller.md`, procédure : `reports/e31-audit-rgaa-procedure.md`
- [x] `rag/` — assistant réécrit, non repris du MVP (E32, 2026-09-01). 7 403
      documents, TF-IDF, citation garantie par construction —
      `06-service/assistant-rag.md`
- [ ] CI/CD — trois workflows *(dépôt 2, `edumatch-cicd`, E36, 2026-09-15,
      commit `a8e61f2`)*. Écrits, YAML valide — **aucun n'a encore tourné
      sur la forge**, 🟡 en cours, pas validé — voir le point ouvert dédié
- [x] Détection de dérive — PSI et KS implémentés directement dans
      `models/derive.py` et `derive_stats.py`, seuil documenté en ADR (E34,
      2026-09-01, ADR 0018). **Evidently écarté** pour un conflit de
      dépendance transitive reproduit deux fois (`python-multipart` de
      FastAPI contre `multipart` de `litestar`, entraîné par la seule version
      d'Evidently compatible avec le reste du projet), pas par préférence —
      voir le point ouvert ci-dessous sur MLflow, cassé par un incident
      voisin pendant ce même retrait
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

- [ ] **L'ablation de Sirene, prévue par le plan d'exécution du projet,
      reste impossible à mesurer.** Confirmé par `models/ablation.py`
      (E27, 2026-08-31) : la chaîne de nomenclatures NAF ↔ ROME ↔ formation
      (E18) n'atteint aucune formation Parcoursup — huit millésimes
      vérifiés, aucun ne porte de code RNCP, NSF ou ROME exploitable. Sans
      cette jointure, aucune variable issue des agrégats Sirene n'entre dans
      le modèle entraîné en E22, et l'écart avec/sans Sirene que l'ablation
      doit mesurer ne peut pas être calculé — il n'existe simplement rien à
      retirer. Ce n'est pas un écart nul mesuré, c'est une mesure qui n'a
      pas d'objet : le critère 4.16 du bloc 4 n'est donc pas encore
      entièrement couvert. Condition de clôture : soit la couverture de la
      chaîne de nomenclatures se corrige et l'ablation est rejouée avec une
      variante Sirene, soit l'impossibilité est actée définitivement dans la
      Model Card (E42) comme limite du dispositif, sans être présentée comme
      un apport nul. Détail : `04-modele/ablation.md`.

- [x] **✅ RÉSOLU — l'incohérence de chiffre d'équité entre l'analyse
      exploratoire et l'audit du modèle est réconciliée** (constatée en E11,
      réconciliée le 2026-09-15 en écrivant l'AIPD, E41, commit `7dbb482`).
      Même métrique, même session 2025, seul le filtre différait : avec un
      plancher de trente vœux par sexe (celui de l'E11), 83,79 % des 11 099
      formations qui l'atteignent présentent un écart inférieur à 5 points ;
      sans ce plancher (celui audité par `fairness.py` en E26), 73,37 % des
      14 159 formations. Le chiffre retenu pour la Model Card et l'AIPD est
      le second, avec son effectif — c'est celui qui décrit la population
      réellement soumise à l'audit d'équité, sans filtre de confort qui
      écarterait les petites formations. Réconcilié par recalcul, pas par
      hypothèse.

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

## Points ouverts issus de l'industrialisation, second dépôt (E36 à E38)

Ces trois étapes vivent dans `edumatch-cicd`, le second dépôt du projet
(critère 4.9), commité le 2026-09-15. Vérifié dans les fichiers eux-mêmes :
les workflows sont syntaxiquement valides, les manifestes Kubernetes portent
`requests`/`limits` et un HPA, les cinq règles Prometheus portent chacune une
action. Aucun de ces trois éléments n'a encore tourné en conditions réelles —
c'est ce point précis qui reste ouvert, pas la conception.

- [ ] **La CI/CD (E36) n'a jamais tourné.** Les trois workflows
      (`ci.yml`, `build-images.yml`, `deploy.yml`) existent mais aucun
      passage n'a été exécuté sur la forge à ce jour : le critère de
      l'étape — « lint, tests, build, déploiement » — décrit une exécution,
      pas un fichier. Condition de clôture : un premier passage vert de
      l'intégration continue, pour le commit exact poussé. Risque déjà
      identifié à ce premier passage : les 716 tests du dépôt n'ont tourné
      qu'en Python 3.12 sur le poste de développement, la CI les lance en
      3.11, jamais essayé.
- [ ] **`terraform apply` n'a jamais été exécuté.** Le cluster Kapsule, le
      registre privé et le stockage objet décrits dans
      `edumatch-cicd/terraform/` (E37) n'existent sur aucun compte Scaleway
      réel. Le critère propre de l'étape (`requests`/`limits`, HPA) est
      rempli par simple lecture des manifestes, mais le critère 2.3 du bloc
      2 (« infrastructure déployée ») ne l'est pas tant qu'un `apply` réel
      et une capture ne le démontrent pas.
- [ ] **Aucun déploiement Kubernetes réel n'a eu lieu.** Les manifestes de
      `edumatch-cicd/k8s/base/` n'ont jamais été appliqués sur un cluster —
      ni les valeurs de `requests`/`limits`, posées par ordre de grandeur
      dans les commentaires du fichier, ni le comportement du HPA n'ont été
      mesurés sous charge réelle. À confirmer par `kubectl top pod` après un
      premier déploiement.
- [ ] **L'API n'expose pas de route `/metrics`.** Condition préalable au
      fonctionnement réel du monitoring (E38) : sans instrumentation côté
      service, Prometheus n'a aucune cible à interroger et le tableau de
      bord Grafana reste vide. Le fichier de règles d'alerte le dit
      lui-même, et la cinquième alerte (`EdumatchInstrumentationAbsente`)
      est conçue pour détecter précisément cette absence plutôt que la
      masquer. À construire côté `edumatch-ia` avant que le monitoring
      puisse être démontré en fonctionnement.
- [ ] **Les règles Prometheus n'ont pas été validées par l'outil officiel.**
      Le format et la syntaxe de `monitoring/prometheus/alerts.yaml` n'ont
      été vérifiés que par lecture, jamais rejoués par `promtool check
      rules` ou équivalent.
- [ ] **L'alerte de dérive du modèle (PSI, ADR 0018) n'est pas intégrée au
      monitoring.** Le calcul tourne aujourd'hui en lot côté `edumatch-ia`
      (`make derive`), pas comme un flux exposé en continu — condition
      explicitement posée dans `edumatch-cicd` avant de l'ajouter : le DAG
      de réentraînement (E33) devra pousser son résultat vers un
      Pushgateway ou exposer lui-même `/metrics`.

---

## Points ouverts issus du service (E28 à E32)

- [ ] **La couverture du terme débouchés reste à 1,4 %.** Mesuré sur les
      fichiers réels (E28, `06-service/score.md`) : 7 libellés distincts sur
      712 (1,0 %), 6 017 lignes sur 440 030 (1,4 %) atteignent un débouché
      Sirene par appariement textuel exact ; les 98,6 % restants portent le
      terme explicitement marqué indisponible, jamais deviné. C'est peu, et
      c'est écrit tel quel plutôt que masqué. Un appariement approché
      (distance d'édition, ou croisement du `code_nsf` IDÉO avec `fili`)
      resterait à mesurer avant de conclure qu'aucune amélioration n'est
      possible. Condition de clôture : soit la couverture se corrige et se
      remesure, soit la limite est actée définitivement dans la Model Card
      (E42) plutôt que présentée comme provisoire sans échéance.
- [ ] **L'audit RGAA manuel n'a pas été déroulé dans un navigateur.** La
      suite automatisée (`tests/unit/test_ecran_accessibilite.py`) couvre ce
      qui se vérifie sans rendu réel — structure sémantique, étiquettes,
      contraste recalculé. Le rendu réel, le comportement d'un lecteur
      d'écran, le parcours clavier de bout en bout et la perception par une
      personne daltonienne restent à vérifier suivant la procédure écrite
      point par point dans `reports/e31-audit-rgaa-procedure.md`.
- [ ] **La purge du journal d'inférence (T5) n'est pas planifiée.** Elle
      existe, tourne, est testée et idempotente (E30,
      `src/edumatch/api/audit_purge.py`), mais s'exécute à la demande. Le
      déclenchement planifié relève de l'ordonnanceur — à construire avec le
      DAG Airflow (E33).
- [ ] **La purge du journal des décisions de conseiller (T6, `/feedback`)
      n'est pas construite**, faute d'identifiant commun entre ce journal et
      le journal d'inférence (T5) — les deux traces ne se corrèlent pas
      aujourd'hui. La durée décidée (12 mois, alignée sur T5) reste une
      intention pour ce journal précis.
- [ ] **L'identifiant du conseiller, saisi sur l'écran de supervision, est
      déclaratif et non vérifié.** Aucun mécanisme d'authentification n'est
      branché à cette étape (E31).
- [ ] **Le tableau de bord du taux d'écartement**, destiné au déployeur pour
      vérifier que le contrôle humain (article 14) n'est pas une façade,
      reste à construire.

---

## Points ouverts issus de l'industrialisation (E33-E34) et de la restitution (E45)

- [ ] **Le registre d'expériences MLflow a été cassé puis réparé, sans test
      qui garantisse qu'il reste utilisable.** Le retrait d'Evidently (E34,
      pour le conflit de dépendance documenté dans l'ADR 0018) a désinstallé
      au passage `opentelemetry-proto`, une dépendance transitive dont MLflow
      dépend pour son propre fonctionnement. L'environnement a été réparé,
      mais **aucun test du dépôt ne vérifie que le registre d'expériences est
      utilisable** — un futur retrait ou une future mise à jour de dépendance
      pourrait casser MLflow une deuxième fois sans qu'aucune suite ne le
      révèle avant l'entraînement suivant. Trou de couverture à combler avant
      l'industrialisation (E35-E36) : un test d'intégration minimal qui
      démarre un run, enregistre un paramètre et une métrique, et le relit.
- [ ] **Les trois vidéos obligatoires restent à produire** (E45) :
      infrastructure en production, pipeline avec panne provoquée et sa
      reprise (dépend de E39), solution en production (dépend au moins de
      E35 à E38). Les diagrammes C4 et du pipeline, eux, sont livrés.
- [ ] **La panne provoquée et sa reprise (E39) ne sont pas filmées.** Le
      mécanisme de reprise lui-même est déjà testé sur données réelles (E33,
      panne qualité et panne réseau reproduites et rejouées), mais rien n'a
      encore été filmé.
- [ ] **Le déploiement Scaleway reste à faire.** Décidé en principe (voir la
      décision « Cloud » du cadrage du projet, à partir du J8), non encore
      construit : aucune ressource Scaleway n'existe dans le dépôt à ce jour.
- [ ] **Les slides de présentation (15 minutes) restent à écrire** (bloc 1,
      critère 1.12).

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
