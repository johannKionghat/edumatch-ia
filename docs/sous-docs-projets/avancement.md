# Avancement — les 46 étapes

Journal d'exécution. Je le tiens à jour à la fin de chaque étape.

Référence des étapes : le plan d'exécution du projet.

> **Le dépôt fait foi.** Si ce journal déclare une étape faite mais que le code
> ne le confirme pas, c'est ce journal qui est faux.

**État : 7 / 46 étapes validées.**

---

## Phase 0 — Fondations

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E01 | Architecture et dépôt local | ✅ validée | 2026-08-24 | `e0713ed` |
| E02 | Dépôts distants et protection de `main` | ✅ validée | 2026-08-26 | `86cc89b` |

**E01 — ce qui a été vérifié**
`git check-ignore` sur des chemins réels : `data/raw/*.csv`, `*adminsdk*.json` et
`models/*.pkl` sont exclus, `data/samples/*` ne l'est pas. `make` affiche l'aide.
Arborescence complète avec 35 `.gitkeep`.

**E01 — décision prise** : ADR 0001, ELT plutôt qu'ETL.

**E02 — ce qui a été vérifié**
- `edumatch-ia` et `edumatch-cicd` créés, privés
- Un premier dépôt avait été publié avec des documents de tiers. Il a été
  **supprimé** puis recréé : l'ancien commit `7d0785e` n'est plus résolvable
  (`404`), l'effacement est réel — un force-push n'aurait fait que masquer
- Historique publié vérifié motif par motif : **0 occurrence** de `retours`,
  `reference/`, notes de travail, `_legacy` ou secret, dans **tout**
  l'historique
- Aucune trace d'outillage dans les messages de commit

**E02 — limite déclarée**
La protection de branche est indisponible sur un dépôt privé en offre gratuite
(`Upgrade to GitHub Pro or make this repository public`). Compensée par le gate
de vérification, qui bloque tout push dont le commit n'a pas passé les contrôles
de tests **et** de contenu.

---

## Phase 1 — Accès aux données

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E03 | Vérification des sources sur data.gouv | ✅ validée | 2026-08-26 | `17a3228` |
| E04 | Configuration centralisée `config.py` | ✅ validée | 2026-08-28 | `c0726b0` |
| E05 | Connecteur Parcoursup | ✅ validée | 2026-08-28 | `144ee20` |
| E06 | Connecteur Sirene | ✅ validée | 2026-08-28 | `04efa8e` |
| E07 | Connecteur référentiels | ✅ validée | 2026-08-29 | *à committer* |
| E08 | Échantillons versionnés | ⬜ | | |

**E03 — ce qui a été vérifié**
- 4 sources interrogées par API de métadonnées (pas de téléchargement des gros
  fichiers) : Parcoursup (8 identifiants opendatasoft), Sirene (catalogue
  data.gouv), ONISEP/IDÉO (4 jeux, téléchargés en entier car sous 8 Mo), RNCP
  (export quotidien France Compétences)
- Chiffres Parcoursup confirmés à l'identique : 104 274 formation-années,
  118 colonnes en 2025, 106 champs communs 2020-2025. Fait nouveau : **83
  champs communs sur les 8 sessions**
- Référentiels ONISEP et RNCP établis pour la première fois — absents jusqu'ici
  de mes notes de cadrage. Licence ONISEP identifiée comme **ODbL**, distincte
  de la Licence Ouverte des trois autres sources
- **Écart Sirene détecté et résolu** : le chiffre « 11,2 Go compressés »,
  retenu jusqu'ici, ne se reproduit avec aucune combinaison de
  ressources du catalogue actuel. Mesure du jour, sur le stock du 01/08/2026 :
  6,44 Go pour les 6 fichiers ZIP de type stock, 4,75 Go en Parquet pour ces 6
  fichiers, 4,63 Go pour les 4 fichiers Parquet retenus par le projet. J'ai
  arbitré la correction vers **6,44 Go**, propagée partout où le chiffre
  figurait, datée au stock du jour
- Audit de la documentation : un bloquant trouvé — `sources.md` affirmait que
  `scripts/verifier_sources.sh` reproduisait l'intégralité des chiffres, alors
  que la section C (référentiels) n'y était pas rejouée. Corrigé : le script
  couvre désormais les 3 sections A, B, C

**E03 — décision prise** : aucune (pas d'ADR — E03 est une vérification, pas un
arbitrage d'architecture). Correction de chiffre actée dans mes notes de
cadrage.

**E04 — ce qui a été vérifié**
- `src/edumatch/config.py` (470 lignes) charge `configs/base.yaml`, le surcharge
  par `configs/{env}.yaml`, puis par les variables d'environnement. Précédence
  prouvée dans les deux sens : `dev` restreint à [2024, 2025], `prod` hérite des
  huit millésimes
- **25 tests** répartis en trois fichiers thématiques, tous sous 500 lignes :
  `PYTHONPATH=src python -m pytest tests/unit/ -q` → 25 passed
- Le critère « aucun chemin ni seuil en dur » est vérifié par un test qui
  analyse l'arbre syntaxique de `config.py`. Une première version, par
  expression régulière, laissait passer un seuil écrit `4 / 5` ou un chemin
  concaténé : la mutation l'a prouvé, le test a été réécrit. Il documente
  lui-même ce qu'il n'attrape pas
- La configuration résout ses chemins relativement au dépôt : exécutée depuis
  un autre support, elle pointe vers le `data/` de ce support, sans modification

**E04 — trois défauts trouvés en validation, tous corrigés**
1. `EDUMATCH_DATA_ROOT=""` (vide) n'est pas une variable absente : la valeur par
   défaut ne s'appliquait pas et `Path("")` se résolvait en répertoire courant,
   silencieusement. Désormais rejeté par une erreur explicite
2. `load_settings("prod")` pouvait retourner un objet annonçant `env = dev` tout
   en portant les valeurs de prod, quand `EDUMATCH_ENV` était posée dans le
   shell. Deux mécanismes de résolution ne se parlaient pas. La contradiction
   lève maintenant une erreur qui nomme les deux valeurs
3. Le canal `.env` n'était jamais lu (`env_file` non configuré). Corrigé, testé

**E04 — décisions prises** : ADR 0003 (configuration centralisée). `data/` reste
dans le dépôt, ignoré par Git ; `EDUMATCH_DATA_ROOT` existe pour le déploiement
— hébergement distant, conteneur, intégration continue — pas pour contourner le
poste de développement.

**E05 — ce qui a été vérifié**
- `src/edumatch/ingestion/parcoursup.py` (221 lignes) télécharge les 8
  millésimes déclarés dans `configs/base.yaml` vers `data/raw/parcoursup/`. Les
  primitives communes à tout connecteur (flux HTTP, empreinte SHA-256,
  écriture atomique, manifeste) sont extraites dans `_flux.py` (220 lignes),
  avant l'écriture du connecteur Sirene — pas après une première duplication
- Suite de tests, paquet non installé, sans `PYTHONPATH` positionné dans
  l'environnement : `python -m pytest -q` → **44 passed**
- Volumétrie réelle des 8 CSV posés sur `data/raw/parcoursup/` : `du -sh
  data/raw/parcoursup/` → **82 Mo**. Comptage ligne à ligne par millésime,
  conforme à `01-donnees/sources.md` : 104 274 formation-années au total
  (2018 : 10 697 · 2019 : 11 577 · 2020 : 12 760 · 2021 : 13 396 · 2022 :
  13 644 · 2023 : 13 869 · 2024 : 14 079 · 2025 : 14 252)
- Colonnes mesurées sur les fichiers réellement posés sur disque (pas sur la
  seule métadonnée du catalogue) : 85 en 2018, 92 en 2019, 115 en 2020, 118 de
  2021 à 2025 — dérive de schéma confirmée, cohérente avec E03
- Idempotence rejouée sur l'API réelle, config `prod` (8 millésimes) : les 8
  fichiers déjà présents renvoient `telecharge=False` au second passage, sans
  requête HTTP de téléchargement
- Écriture atomique : le fichier apparaît sous son nom définitif seulement une
  fois complet (`.part` renommé par `os.replace`, atomique y compris sous
  Windows où `Path.rename` échoue si la cible existe déjà)

**E05 — correction de chiffre propagée**
La documentation et mes notes de cadrage donnaient « ~100 Mo » pour le poids
des 8 CSV Parcoursup — un ordre de grandeur jamais mesuré, faute de fichier
posé sur disque (l'export de l'API est généré à la volée, sans en-tête
`Content-Length`, voir `01-donnees/sources.md`). Une fois les 8 fichiers
réellement téléchargés, la mesure directe donne **82 Mo**
(`du -sh data/raw/parcoursup/`, 2026-08-28). Je corrige la valeur partout où
elle figurait dans le dépôt. Le raisonnement qui s'appuyait dessus n'est pas
affaibli : le seuil de bascule vers Spark oppose un catalogue Parcoursup petit
(82 Mo, un seul nœud, Polars/dbt) à Sirene (36 M de lignes retenues à l'époque,
PySpark) — un écart encore plus net avec 82 Mo qu'avec 100 Mo.
*Le « 36 M » ci-dessus était lui-même une estimation jamais recalculée : voir
la correction en E06, ci-dessous — 43,9 M lignes mesurées.*

**E05 — décision prise** : aucun ADR nouveau sur le fond du connecteur — l'ADR
0002 (pas de Databricks) est mis à jour avec le chiffre corrigé. Deux choix
structurants de ce commit ont justifié un ADR séparé : voir ADR 0004.

**E06 — ce qui a été vérifié**
- `src/edumatch/ingestion/sirene.py` (490 lignes) : résolution des 4 fichiers
  configurés par interrogation du catalogue data.gouv (`resoudre_ressources`),
  puis téléchargement (`telecharger_fichier`, `telecharger_tous`) avec les
  mêmes garanties que Parcoursup — idempotence par empreinte, écriture
  atomique, manifeste — sur les primitives déjà extraites dans `_flux.py`
  (enrichi d'un rappel de progression facultatif, sans effet sur Parcoursup)
- Suite de tests, paquet non installé : `python -m pytest -q` → **80 passed**
  (`tests/unit/test_ingestion_sirene.py`, 22 cas, sans aucun accès réseau —
  session HTTP factice ; `tests/unit/test_ingestion_sirene_erreurs.py`,
  7 cas séparés, sur le vocabulaire d'erreur et la vérification de taille
  ci-dessous ; `test_ingestion_flux.py` et `test_ingestion_parcoursup.py`
  complétés en cohérence)
- Vocabulaire d'erreur transitoire/définitif partagé entre les deux
  connecteurs (`ErreurTransitoire`, `ErreurDefinitive` dans `_flux.py`) :
  `ErreurReseauSirene`/`ErreurReseauParcoursup` sur les échecs réseau,
  `ErreurCatalogueSirene`/`ErreurConfigurationParcoursup` sur les échecs qui
  tiennent au contrat de la source. Objectif : le futur DAG (E33) décide de
  retenter ou d'alerter sans connaître la classe interne du connecteur
- Vérification de la taille annoncée par le catalogue contre la taille
  réellement écrite après téléchargement : un écart de plus de 5 %
  est journalisé en avertissement (`ECART_TAILLE_SIRENE`), jamais levé —
  `filesize` n'est pas garanti par contrat côté catalogue
- Résolution rejouée contre le catalogue réel aujourd'hui
  (`resoudre_ressources()`) : les 4 URL obtenues correspondent exactement à
  celles enregistrées dans `data/raw/sirene/manifeste.json` lors du
  téléchargement effectif, stock du **01/08/2026**
- Les 4 fichiers réellement téléchargés (`data/raw/sirene/`, tailles
  identiques aux tailles annoncées par le catalogue) : `StockEtablissement`
  2 202 341 459 o · `StockEtablissementHistorique` 870 319 380 o ·
  `StockUniteLegale` 705 090 270 o · `StockUniteLegaleHistorique`
  855 957 649 o — **total 4 633 708 758 o = 4,63 Go décimaux (4,4 Gio)**
- Contenu mesuré par métadonnée Parquet (`pyarrow.parquet.ParquetFile(...).metadata`,
  sans lire une valeur) : `StockEtablissement` **43 896 818 lignes × 54
  colonnes** · `StockEtablissementHistorique` 95 865 102 × 18 ·
  `StockUniteLegale` **29 922 486 × 35** · `StockUniteLegaleHistorique`
  71 355 318 × 28. Les 9 colonnes utiles au projet sont toutes présentes,
  y compris `activitePrincipaleNAF25Etablissement`
- Chiffre nouveau, mesuré ce jour : sur les 43 896 818 établissements,
  **16 715 258 sont actifs (38,1 %)** et **2 436 624 sont actifs ET
  employeurs (5,6 %)** — lecture de 2 colonnes sur 54, **35,4 secondes**

**E06 — correction de chiffre propagée**
« 36 millions d'établissements, 25 millions d'unités légales », retenu
jusqu'ici dans la documentation et mes notes de cadrage, n'avait jamais été
recalculé depuis sa première mesure — même famille d'erreur que le « 11,2 Go »
(E03) et le « ~100 Mo » (E05) : un chiffre entré une fois, jamais revérifié
contre le fichier réel une fois qu'il a existé sur disque. Mesuré aujourd'hui
par métadonnée Parquet : **43 896 818 établissements, 29 922 486 unités
légales** — le chiffre retenu était **sous-estimé**, pas surestimé. Corrigé
dans `01-donnees/sources.md`, `03-pipeline/ingestion.md`, l'ADR 0002 et
`ARCHITECTURE_EduMatch.md`.

Cette correction **renforce** l'argument qui écarte Databricks au profit de
PySpark local (ADR 0002) : le volume à parcourir est plus élevé que ce qui
était annoncé. La nuance qui compte plus que le chiffre brut : les filtres du
projet (actif, employeur, diffusible) ne retiennent que 2 436 624 lignes sur
43 896 818 (5,6 %) — mais c'est la **lecture** des 43,9 M de lignes, pas le
résultat filtré, qui dimensionne le traitement, puisqu'il faut les parcourir
pour savoir lesquelles passent le filtre. Et le fait que cette lecture de
2 colonnes sur 54 prenne 35,4 secondes sur un poste ordinaire est précisément
ce qui justifie un Spark **local**, sans cluster managé, pour le job réel
(E17, jointure et agrégation) — voir ADR 0002 mis à jour.

**E06 — décisions prises**
- ADR 0005 — résolution dynamique de l'URL Sirene par interrogation du
  catalogue data.gouv, contre une URL en configuration (intenable dès le
  mois suivant : le chemin de l'URL porte l'horodatage de publication du
  stock). Coût assumé : une dépendance réseau supplémentaire au moment de
  l'exécution, à traiter comme une panne transitoire dans le DAG (E33), pas
  comme une erreur de configuration.
- ADR 0006 — vocabulaire commun d'erreur transitoire/définitif, partagé entre
  Parcoursup et Sirene via `_flux.py`. Rétrofité sur Parcoursup dans le même
  commit, pour que le futur DAG traite les deux connecteurs de façon uniforme
  plutôt que de découvrir la distinction séparément pour chacun.

**E07 — ce qui a été vérifié**
- `src/edumatch/ingestion/referentiels.py` (point d'entrée public),
  `_referentiels_rncp.py` (résolution et téléchargement de l'export RNCP du
  jour) et `_referentiels_communs.py` (vocabulaire d'erreur et primitives
  partagées entre les deux volets) téléchargent les 4 jeux ONISEP (IDÉO) à URL
  fixe et l'export RNCP du jour, avec les mêmes garanties que Parcoursup et
  Sirene — idempotence par empreinte (IDÉO) ou par date de publication (RNCP),
  écriture atomique, manifeste
- Suite de tests, paquet non installé : `python -m pytest -q` → **120 passed**
- Téléchargement réel effectué le 2026-08-29 vers
  `data/external/referentiels/` : **22 Mo** au total
  (`du -sh data/external/referentiels/`)
- Volumétrie IDÉO conforme aux chiffres du 2026-08-26, à la ligne près :
  formations 5 869 × 16, métiers 1 534 × 13, structures secondaire
  15 293 × 30, structures supérieur 8 985 × 29 — vérifié par comptage CSV
  correct (module `csv`, pas `wc -l`)
- Export RNCP du **2026-08-29** : **30 484 fiches, dont 7 000 actives et
  23 484 inactives**, 16 colonnes — vérifié par parseur CSV

**E07 — deux corrections importantes, propagées dans `01-donnees/sources.md`
et `03-pipeline/ingestion.md`**

1. **Un chiffre faussé par l'outil de vérification, pas par la source.** La
   documentation du 26/08 annonçait « 36 000 fiches RNCP, dont 6 995
   actives ». En construisant le connecteur, ce chiffre ne se reproduisait
   pas. Cause : `scripts/verifier_sources.sh` comptait avec `wc -l`, qui
   compte des retours à la ligne **physiques** — or le CSV RNCP contient des
   champs de texte multi-lignes entre guillemets (intitulés de certification
   avec sauts de ligne internes), que `wc -l` prend à tort pour des fiches
   supplémentaires. Un parseur CSV qui respecte les guillemets (module `csv`)
   donne **30 484**, confirmé par la somme 7 000 actives + 23 484 inactives =
   30 484. Le compte des actives, lui, survivait par coïncidence — la chaîne
   `"ACTIVE"` n'apparaît jamais dans un champ multi-ligne de cet export, ce
   qui n'a rien d'une garantie pour un futur export. **Corrigé** :
   `scripts/verifier_sources.sh` compte désormais avec un vrai parseur CSV,
   pour le RNCP (section C.2) comme pour les 4 fichiers IDÉO (section C.1),
   même si ces derniers ne présentaient pas l'écart aujourd'hui.
2. **Un encodage annoncé à tort.** La documentation du 26/08 annonçait le
   RNCP en Latin-1. Le fichier réellement téléchargé décode intégralement en
   **UTF-8** (`\xc3\xa9` = « é » en UTF-8, pas en Latin-1). Nuance
   méthodologique retenue : Latin-1 ne lève jamais d'erreur de décodage —
   « ça se décode sans erreur en Latin-1 » ne prouve rien, puisqu'un fichier
   UTF-8 relu en Latin-1 se décode aussi sans erreur, silencieusement corrompu.
   Le contrôle d'encodage du connecteur (`verifier_encodage`) est pour cette
   raison **asymétrique**, assumé et testé comme tel : il détecte un vrai
   Latin-1 déclaré UTF-8, jamais l'inverse.

**E07 — décision prise** : ADR 0007 — un fichier par date de publication pour
l'export RNCP (`rncp_AAAA-MM-JJ.csv`), jamais un fichier unique écrasé comme
pour Sirene : une table dérivée du RNCP (E18) doit rester vérifiable après
coup sur l'export qui l'a produite. Alternatives écartées : fichier unique
écrasé (perd la traçabilité d'un export passé), retéléchargement systématique
sans persistance (non idempotent). Seuil de bascule : l'accumulation
(~9 Mo/jour) exigerait une politique de rétention si la tâche est un jour
programmée à cadence quotidienne dans le DAG (E33) — non traitée à cette
étape.

**E07 — implication licence pour E18**, actée dans `03-pipeline/ingestion.md`
et à reprendre dans le registre des sources (E40) : ONISEP est sous **ODbL**
(partage à l'identique obligatoire sur toute base dérivée redistribuée), le
RNCP sous **Licence Ouverte v2.0**. Si `naf_rome_formation.csv` (E18) intègre
des données IDÉO et est publié tel quel, il devra l'être sous ODbL.

## Phase 2 — Analyse exploratoire

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E09 | EDA — label et distributions | ⬜ | | |
| E10 | EDA — écarts et sélectivité | ⬜ | | |
| E11 | EDA — équité et substituts | ⬜ | | |
| E12 | EDA — stabilité inter-millésimes | ⬜ | | |
| E13 | Décision de variables (ADR) | ⬜ | | |

## Phase 3 — Qualité et transformation

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E14 | Contrôles qualité bloquants | ⬜ | | |
| E15 | dbt — bronze vers silver | ⬜ | | |
| E16 | dbt — modèle en étoile | ⬜ | | |
| E17 | Job Spark Sirene | ⬜ | | |
| E18 | Table NAF ↔ ROME ↔ formation | ⬜ | | |
| E19 | Calcul du label | ⬜ | | |
| E20 | Construction des variables | ⬜ | | |

## Phase 4 — Modèle

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E21 | Baseline | ⬜ | | |
| E22 | Entraînement LightGBM | ⬜ | | |
| E23 | Évaluation et calibration | ⬜ | | |
| E24 | Courbe d'apprentissage | ⬜ | | |
| E25 | Explicabilité SHAP | ⬜ | | |
| E26 | Audit d'équité | ⬜ | | |
| E27 | Ablation | ⬜ | | |

## Phase 5 — Service

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E28 | Score à trois termes | ⬜ | | |
| E29 | API | ⬜ | | |
| E30 | Journalisation article 12 | ⬜ | | |
| E31 | Écran conseiller RGAA | ⬜ | | |
| E32 | Assistant RAG réécrit | ⬜ | | |

## Phase 6 — Industrialisation

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E33 | DAG Airflow | ⬜ | | |
| E34 | Détection de dérive | ⬜ | | |
| E35 | Conteneurisation | ⬜ | | |
| E36 | CI/CD | ⬜ | | |
| E37 | Infrastructure Terraform et Kubernetes | ⬜ | | |
| E38 | Monitoring et SLO | ⬜ | | |
| E39 | Panne provoquée et reprise, filmée | ⬜ | | |

## Phase 7 — Gouvernance

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E40 | Registres traitements et sources | ⬜ | | |
| E41 | AIPD | ⬜ | | |
| E42 | Model Card | ⬜ | | |
| E43 | Correspondance AI Act | ⬜ | | |
| E44 | Plan de gouvernance et risques | ⬜ | | |

## Phase 8 — Restitution

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E45 | Diagrammes C4 et les 3 vidéos | ⬜ | | |
| E46 | Cohérence dossier ↔ dépôt, slides, répétition | ⬜ | | |

---

## Évaluations du jury

| Date | Verdict | Blocs | Rapport |
|---|---|---|---|
| — | *aucune évaluation à ce jour* | | |

---

## Légende

| Symbole | Sens |
|---|---|
| ✅ | Validée : livrable existant, critère vérifié, argumentaire rendu |
| 🟡 | En cours |
| ⬜ | Non commencée |
| ⛔ | Bloquée — dépendance non validée, ou réserve de conformité ou de sécurité |
