# Avancement — les 46 étapes

Journal d'exécution. Je le tiens à jour à la fin de chaque étape.

Référence des étapes : le plan d'exécution du projet.

> **Le dépôt fait foi.** Si ce journal déclare une étape faite mais que le code
> ne le confirme pas, c'est ce journal qui est faux.

**État : 21 / 46 étapes validées.**

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
| E07 | Connecteur référentiels | ✅ validée | 2026-08-29 | `22bf61d` |
| E08 | Échantillons versionnés | ✅ validée | 2026-08-29 | `f6ecd6c` |

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

**E08 — ce qui a été vérifié**
- `data/samples/` : 1,2 Mo, 17 échantillons versionnés (8 CSV Parcoursup, 4
  Parquet Sirene, 4 CSV IDÉO, 1 CSV RNCP), générés par
  `src/edumatch/ingestion/echantillons.py` (`python -m
  edumatch.ingestion.echantillons`, cible `make samples`)
- **Critère central de l'étape, vérifié en le provoquant** : `data/raw/` et
  `data/external/` rendus absents (dossiers renommés) → la suite complète
  tourne quand même, `python -m pytest -q` → **145 passed**. C'est ce qui rend
  la CI possible sans les 4,6 Go de sources
- Échantillonnage systématique à pas fixe, sans graine aléatoire : deux
  générations successives produisent une empreinte SHA-256 strictement
  identique sur chaque fichier — vérifié, pas supposé
- Les 8 millésimes Parcoursup sont représentés, dérive de schéma 85 → 118
  colonnes visible sur l'échantillon (`test_parcoursup_couvre_les_huit_millesimes_et_la_derive_de_schema`)
- Manifeste (`data/samples/manifeste.json`) : 17 entrées, chacune porte `url`,
  `date_source`, `empreinte_sha256_source`, `licence` en plus des champs déjà
  existants

**E08 — le point de gouvernance, pas seulement technique**
Les 9 colonnes d'identité directe de personnes physiques (`nomUniteLegale`,
`prenom1UniteLegale`, etc.) sont exclues de l'échantillon `StockUniteLegale`.
Retirer ces colonnes **ne rend pas l'échantillon anonyme**. Vérifié sur
l'échantillon lui-même : 282 des 500 lignes de `StockUniteLegale`
(catégorie juridique 1000, entrepreneur individuel — sans personnalité
juridique distincte de la personne physique qui le crée) sont retrouvables
par jointure sur le SIREN avec `denominationUsuelleEtablissement` /
`enseigne1Etablissement`, conservées sans restriction dans
`StockEtablissementHistorique` :

```
python -c "
import pyarrow.parquet as pq, collections
t = pq.read_table('data/samples/sirene/StockUniteLegale.parquet')
cat = t.column('categorieJuridiqueUniteLegale').to_pylist()
statut = t.column('statutDiffusionUniteLegale').to_pylist()
print(collections.Counter(s for c, s in zip(cat, statut) if c == 1000))
"
# → Counter({'O': 239, 'P': 43})
```

239 des 282 sont en statut diffusible (« O ») : sur le fichier source complet,
la jointure nom retiré ↔ dénomination conservée restitue l'identité des 239
sur 239 diffusibles (les 43 « P » restent masqués `[ND]` par l'INSEE à la
source — art. A123-96 du code de commerce, respecté sans reconstruction).
C'est une **pseudonymisation** (RGPD art. 4.5), pas une anonymisation : la
donnée reste dans le champ du RGPD. Base légale retenue : **intérêt légitime**
(art. 6.1.f), mise en balance écrite dans `data/samples/README.md`. Rappel
explicite : la Licence Ouverte v2.0 ne vaut jamais base légale RGPD, les deux
régimes se cumulent. Alternatives écartées : exclure les lignes d'entrepreneur
individuel (détruit la représentativité — 56,4 % des lignes du fichier source
complet), hacher le SIREN (9 chiffres, espace forçable en secondes), fabriquer
une valeur de substitution (donnée simulée, interdite par ailleurs dans ce
projet). Détail complet et seuil de bascule : ADR 0008.

**E08 — un test corrigé sur le même défaut qu'un test déjà revu sur ce
projet** : `tests/data/test_echantillons_conformite.py` importait sa liste de
colonnes interdites depuis le module qu'il contrôlait
(`edumatch.ingestion.echantillons`) — vider cette liste dans le module aurait
laissé le test vert. Devenu une liste blanche écrite en dur dans le test,
propre à chaque fichier Sirene, qui refuse par défaut toute colonne non
examinée — y compris une colonne ajoutée sans préavis par l'INSEE (précédent
réel : `activitePrincipaleNAF25Etablissement`, apparue le 16/12/2025).

**E08 — décision prise** : ADR 0008 — conserver les lignes d'entrepreneur
individuel sous régime d'intérêt légitime plutôt que de les exclure de
l'échantillon.

## Phase 2 — Analyse exploratoire

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E09 | EDA — label et distributions | ✅ validée | 2026-08-29 | `7bcd5ef` |
| E10 | EDA — écarts et sélectivité | ✅ validée | 2026-08-29 | `4f4bdc9` |
| E11 | EDA — équité et substituts | ✅ validée | 2026-08-29 | `cbf9be2` |
| E12 | EDA — stabilité inter-millésimes | ✅ validée | 2026-08-29 | `be2787c` |
| E13 | Décision de variables (ADR) | ✅ validée | 2026-08-29 | `f7c1449` |

**E09 — ce qui a été vérifié**
- `notebooks/01-jgk-eda-label.ipynb` (34 cellules, dont 20 de commentaire,
  sorties nettoyées) établit le grain de l'analyse : une ligne est une
  formation identifiée par `cod_aff_form`, pour une session. Clé vérifiée sans
  doublon ni manque : 14 252 valeurs distinctes pour 14 252 lignes en 2025.
  `cod_uai` seul ne suffit pas : 4 058 établissements pour 14 252 formations
- Schéma mesuré sur les huit millésimes empilés : 85 colonnes en 2018,
  92 en 2019, 115 en 2020, 118 de 2021 à 2025. **83 colonnes communes aux 8
  sessions** sur 128 vues au moins une fois, dont 59 remplies à plus de 99 %
  partout — c'est le socle sur lequel un modèle entraîné sur toute la période
  peut s'appuyer
- Trois faits de dérive relevés dans les données elles-mêmes :
  `etablissement_id_paysage` et `composante_id_paysage` absentes jusqu'en
  2020, renseignées à environ 47 % de 2021 à 2024, vides à 100 % en 2025 ;
  `pct_etab_orig` passe de 46 % à 100 % de remplissage en 2023, rupture nette
  qui correspond à un élargissement de la publication à toutes les filières
  (elle ne concernait que BTS et CPGE) ; `acc_term` reste à 45-56 % de
  remplissage sur toute la période
- `acc_term` n'est pas une valeur manquante mais une valeur **non
  applicable** : son absence vaut 0 % pour les BTS et CPGE, 100 % pour toutes
  les autres filières, jamais entre les deux. L'imputer fabriquerait de la
  donnée et redonnerait la filière au modèle sous une autre forme
- **Le label dépasse 1 dans 8,9 % des cellules bac général** (1 219 sur
  13 685), et le dépassement persiste sur les grosses cellules (483 sur
  7 154 au-delà de 100 vœux) : ce n'est pas un artefact de petit effectif,
  c'est structurel — `prop_tot` compte des propositions émises, réémises
  après désistement, quand `nb_voe_pp` compte des vœux
- Moyennes et médianes reproduites à l'identique : bac général 0,522 / 0,498 ;
  technologique 0,433 / 0,381 ; professionnel 0,405 / 0,333. Masses aux
  bornes mesurées : taux nul pour 1,2 %, 12,9 % et **21,6 % (2 779
  formations)** des cellules selon le bac ; taux à 1 pour 13,1 %, 11,8 % et
  13,1 %

**E09 — décision explicitée, pas nouvelle dans le résultat**
La moyenne de 0,522 déjà citée dans la documentation et le dossier est la
moyenne calculée sur le taux **borné à 1** (la moyenne brute vaut 0,545). La
borne était donc déjà appliquée dans le calcul, sans être écrite nulle part.
Corrigé : `01-donnees/label.md` et l'ADR 0009 rendent la borne explicite, sans
changer le chiffre.

**E09 — décision prise** : ADR 0009 — quatre décisions sur le label : conserver
`prop_tot / nb_voe_pp` (mesure l'accessibilité, pas la préférence du candidat :
l'alternative `acc / nb_voe_pp` ne dépasse jamais 1 mais mesurerait
l'acceptation), borner à 1 en énonçant pourquoi, pondérer par l'effectif de la
cellule à l'entraînement, ne pas exclure les petites cellules (un seuil à
30 vœux écarterait 26 % des observations).

**E10 — ce qui a été vérifié**
- `notebooks/02-jgk-eda-ecarts-selectivite.ipynb` (18 cellules dont 10 de
  commentaire), 3 figures exportées dans `reports/figures/`
- Comparaison **appariée** : la même formation observée avec elle-même, sur
  les 12 552 formations recevant des vœux des deux profils de bac. Comparer
  deux moyennes globales aurait mélangé la sélectivité propre des formations
  et le choix d'orientation des candidats — un biais de composition, pas une
  mesure d'écart
- Écart médian **+8,5 points** en faveur du bac général, mais 63,9 % des
  formations avantagent le bac général et **26,8 % avantagent le bac
  professionnel** ; un tiers présentent un écart supérieur à 20 points. Il
  n'existe donc pas un désavantage uniforme, mais une forte hétérogénéité
- Écart médian par filière : BTS +1,1 point (quasi neutre, 5 231 formations)
  · Licence +7,4 · École de Commerce +9,2 · EFTS +12,0 · PASS +14,9 ·
  Licence-LAS +18,8 · BUT +25,7 · IFSI +33,2 · CPGE +42,3. **CPGE, BUT et
  PASS affichent une médiane de taux NULLE pour le bac professionnel** :
  dans plus de la moitié de ces formations, un candidat de cette voie ne
  reçoit aucune proposition
- La tension (`voe_tot / capa_fin`) explique fortement le taux observé : de
  1,000 à 0,182 du quintile le moins tendu au plus tendu, médiane à 11,4
  vœux par place

**E10 — fuite fonctionnelle identifiée, à traiter avant E20**
`voe_tot` n'existe pas au moment où un lycéen formule ses vœux : ce n'est pas
une fuite temporelle au sens strict — la variable précède chronologiquement
la décision d'admission — mais une inadéquation au cas d'usage, la variable
n'étant disponible qu'après le moment où le système doit répondre. Un modèle
qui l'utiliserait serait excellent en évaluation et inutilisable en
production. Décalage temporel praticable identifié : `cod_aff_form` est
absente avant 2020, mais l'identifiant est encodé dans le paramètre
`g_ta_cod` du lien vers la fiche de formation — vérifié par coïncidence
exacte sur les millésimes où les deux coexistent. Reconstruite, la clé
couvre 92,4 % des lignes en 2018 et 94,6 % en 2019, avec un taux de jointure
d'une session à la suivante de 82 % à 95 %.

**E10 — décision prise** : aucun ADR séparé — la fuite fonctionnelle et le
décalage temporel sont actés dans l'ADR 0010, avec E11 et E12 (voir plus bas).

**E11 — ce qui a été vérifié**
- `notebooks/03-jgk-eda-equite-substituts.ipynb` (17 cellules dont 9 de
  commentaire), 3 figures exportées
- **Correction de chiffre** : 179 formations n'admettent aucun candidat, et
  leur `pct_f` vaut mécaniquement 0 %. Les compter portait le constat de
  2 775 à 2 954 formations à moins de 20 % de femmes. Le chiffre juste,
  dénominateur non nul, est **2 775 (19,7 %)**
- Féminisation polarisée : 19,7 % sous 20 % de femmes, 17,9 % au-dessus de
  80 %, 21,5 % seulement entre 40 et 60 %. Part globale de femmes admises :
  56,3 %
- **À formation égale**, sur 11 099 formations avec au moins 30 vœux de
  chaque sexe : écart médian **−0,04 point**, inférieur à 5 points dans
  **83,8 %** des cas, femmes avantagées dans 48,8 % des cas contre 50,8 %
  pour les hommes. L'inégalité se joue en amont du choix, pas à l'admission
  — réserve de méthode : le fichier ne ventile les propositions par sexe que
  pour les admis, pas pour l'ensemble des vœux, la comparaison porte donc
  sur une quantité différente de celle du label
- Substituts du genre mesurés par information mutuelle, **corrigée du
  nombre de modalités par permutation** (5 tirages, graine 42) : `cod_uai`
  observé 57,5 % / hasard 28,5 % / net **28,9 %** · `fili` 19,6 % / 0,1 % /
  **19,5 %** · `ville_etab` 19,1 % / 8,9 % / **10,2 %** · `select_form`
  5,6 % / 0,0 % / **5,6 %** · `dep` 3,1 % / 0,8 % / **2,3 %** · `acad_mies`
  1,6 % / 0,2 % / **1,4 %**

**E11 — deux conséquences majeures**
Sans la correction de cardinalité, `cod_uai` aurait été crédité d'un pouvoir
explicatif deux fois trop grand. Et surtout : **l'hypothèse de départ est
infirmée** — l'académie, désignée jusqu'ici comme substitut à surveiller,
n'explique que 1,4 % ; le deuxième substitut le plus puissant est la
**filière**, variable indispensable au système qu'on ne peut pas retirer. Le
modèle reconstituera donc partiellement le genre quoi qu'il arrive :
l'exclusion de la variable de genre est nécessaire mais insuffisante.
Dispositif retenu à trois niveaux : exclusion du genre à l'entrée, mesure
des substituts (ce carnet), audit d'équité a posteriori sur les prédictions
(E26). Détaillé dans `04-modele/equite.md`.

**E11 — décision prise** : actée dans l'ADR 0011, avec le dispositif à trois
niveaux.

**E12 — ce qui a été vérifié**
- `notebooks/04-jgk-eda-stabilite-millesimes.ipynb` (18 cellules dont 11 de
  commentaire), 2 figures exportées. Clôture la phase exploratoire
- **Le numérateur `prop_tot_*` ventilé par type de baccalauréat n'existe
  qu'à partir de 2020.** Le label n'est calculable que sur **six sessions**
  (2020-2025), pas huit. La répartition déclarée jusqu'ici (entraînement
  2018-2023) plaçait deux sessions sans cible dans le jeu d'entraînement
- **Volumétrie corrigée : 440 030 cellules exploitables** sur 2020-2025
  (67 768 · 71 080 · 72 784 · 74 831 · 76 408 · 77 159), contre 560 000 à
  625 000 annoncées en supposant huit sessions utilisables. Le chiffre de
  77 159 cellules pour 2025 seul reste confirmé
- Alternative écartée : construire un label dès 2018 à partir de `acc_bg`,
  présent sur toute la période. `acc` compte les inscrits, pas les
  propositions — ce serait une autre cible, et un label composite selon la
  session serait incohérent avec lui-même
- **La cible n'est pas stationnaire, et les deux définitions divergent** :
  taux agrégé 40,5 % → 36,7 % de 2020 à 2025, pendant que la moyenne par
  formation monte de 0,491 à 0,522 (pic à 0,534 en 2024). Explication : le
  catalogue passe de 12 760 à 14 252 formations, les nouvelles étant plus
  petites et moins tendues. Un dispositif de surveillance suivant une seule
  définition conclurait à l'inverse de la réalité
- **Rupture 2020, contrôle continu** : mentions très bien 7,4 % → 11,8 %,
  sans-mention 43,4 % → 29,8 %. Retour lent (2021 encore à 29,8 %), niveau
  d'avant jamais retrouvé. Les variables de mention sont contaminées pour
  2020 et 2021
- **Rupture boursiers, en 2019 puis en 2025** : part de vœux boursiers
  12,5 % → 13,8 % → 16,3 % en 2020, stable quatre ans, puis rechute à
  13,8 % en 2025. Le statut de boursier étant une dimension des cellules de
  label, les cellules `_brs` du jeu de test ne décrivent pas la même
  population que celles de l'entraînement
- La session 2020 est **conservée** : l'anomalie porte sur les mentions, pas
  sur la cible — tension médiane 11,8 alignée sur les autres sessions,
  masses aux bornes dans la norme. L'écarter aurait coûté un quart de
  l'entraînement sans fondement mesuré

**E12 — protocole d'évaluation révisé**
Entraînement 2020-2023, validation 2024, test 2025 — trois réserves écrites
avant tout résultat : mentions écartées ou signalées pour 2020-2021,
métriques ventilées par statut de boursier, dégradation attendue entre
validation et test à ne pas imputer d'emblée au modèle. Détail :
`04-modele/evaluation.md`.

**E12 — décision prise** : ADR 0012 — révision du protocole d'évaluation et
conservation de la session 2020.

**E13 — ce qui a été vérifié**
- ADR 0013 (décision des variables), synthèse colonne par colonne des quatre
  carnets d'exploration, sur les **128 colonnes** vues au moins une fois sur
  les huit millésimes : **9 lues sur la session prédite, 35 décalées d'une
  session, 8 décalées sous réserve (mentions), 73 exclues** — total 128, sans
  reste
- Motifs d'exclusion comptés : redondance 23 · instabilité 22 · complétude
  10 · hors périmètre 10 · interdite 4 · substitut 3 · cardinalité 1
- Classement écrit dans `configs/base.yaml` (section `modele.variables`),
  typé par `VariablesConfig` dans `src/edumatch/config.py`, avec validation
  de disjonction entre catégories
- Split corrigé : entraînement [2020, 2021, 2022, 2023], validation [2024],
  test [2025] — vérifié par `load_settings("prod")`
- **153 tests passent**. Quatre contrôles de contrat dans
  `tests/data/test_variables_reference.py`, vérifiés par mutation : colonne
  mal orthographiée, colonne retirée du classement, `voe_tot` déplacé vers
  la liste blanche, split rouvert à 2018 — les quatre mutations font échouer
  le test qui les vise, et lui seul

**E13 — le critère de tri, plus large qu'il n'y paraît**
Le critère n'est pas « la variable est-elle postérieure à la décision
d'admission » mais « est-elle connue au moment où le lycéen formule ses
vœux ». C'est pourquoi les compteurs (`voe_tot`, `prop_tot`, `capa_fin`,
`acc_tot`) ne sont pas exclus mais **décalés d'une session** : la même
colonne est une fuite lue sur la session courante et une information
légitime lue sur la précédente. Liste blanche plutôt que liste noire : une
colonne ajoutée par un millésime futur est exclue par défaut, la chaîne
s'arrête tant qu'elle n'a pas été classée.

**E13 — une hypothèse vérifiée puis corrigée**
Le motif de redondance des 19 colonnes de pourcentage repose sur une mesure,
pas une supposition. Ma première hypothèse — `pct_bours = acc_brs / acc_tot`
— s'est révélée fausse : écart médian de 3,4 points, jusqu'à 97,5 points au
maximum. Le dénominateur réel est `acc_neobac`. Reconstitution vérifiée des
19 colonnes, écart maximal de 0,500 point (l'arrondi) dans tous les cas.

**E13 — deux arbitrages sur l'équité, indépendants l'un de l'autre**
`cod_uai` est exclu pour deux raisons qui tiennent chacune séparément :
cardinalité (4 058 établissements, risque de mémorisation) et statut de
premier substitut du genre mesuré (28,9 % net, ADR 0011). `fili`, deuxième
substitut le plus fort (19,5 % net), est retenue malgré tout : la retirer
détruirait l'objet du système sans rendre le modèle aveugle au genre, la
ségrégation étant portée par la formation elle-même. Position assumée,
compensée par l'audit d'équité a posteriori (E26). Détail :
`04-modele/equite.md` et `04-modele/specification.md`.

**E13 — trois points laissés ouverts, non masqués**
- `capa_fin` n'est pas tranchée : classée décalée par prudence, faute de
  preuve que la capacité affichée pendant la campagne coïncide avec la
  colonne publiée ensuite sous ce nom.
- Le taux décalé manque pour toute la session cible 2020, `prop_tot_*` par
  type de bac n'existant pas en 2019. Valeurs manquantes laissées
  explicites, sans imputation.
- Le contrôle anti-fuite automatique travaille sur des noms de colonnes, pas
  sur leur sémantique : il empêche l'ajout distrait d'un compteur à la liste
  blanche, il ne prouve pas que les 9 colonnes retenues sont réellement
  publiées avant l'ouverture de la campagne. Cette preuve relève de l'ADR
  0013, pas d'un test automatisé.

**E13 — décision prise** : ADR 0013 — liste blanche sur la session prédite,
décalage d'une session pour le reste. Clôture la phase exploratoire.

## Phase 3 — Qualité et transformation

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E14 | Contrôles qualité bloquants | ✅ validée | 2026-08-29 | `b166378` |
| E15 | dbt — bronze vers silver | ✅ validée | 2026-08-29 | `95248e6` |
| E16 | dbt — modèle en étoile | ✅ validée | 2026-08-30 | `cae2485` |
| E17 | Job Spark Sirene | ✅ validée | 2026-08-30 | `8ebe613` |
| E18 | Table NAF ↔ ROME ↔ formation | ✅ validée | 2026-08-30 | `2439d26` |
| E19 | Calcul du label | ✅ validée | 2026-08-30 | `8376639` |
| E20 | Construction des variables | ✅ validée | 2026-08-30 | `a5ae188` |

**E14 — ce qui a été vérifié**
- `src/edumatch/quality/` : vocabulaire commun (`_diagnostic.py` —
  `Anomalie`, `Gravite`, `RapportControle`, `ErreurQualiteBloquante`),
  contrôle générique de fraîcheur (`_fraicheur.py`), un module par source
  (`parcoursup.py`, `sirene.py`, `referentiels.py`), orchestrés par
  `run.py`. Quatre familles de contrôle : schéma, complétude, cohérence,
  fraîcheur. Tous les seuils dans `configs/base.yaml` (section `qualite`),
  aucun en dur dans le code
- **Critère central de l'étape, démontré et non affirmé** :
  `PYTHONPATH=src python -m edumatch.quality.run` sur les données réelles →
  **code de sortie 1**. Une tâche d'orchestration échouerait, la chaîne
  s'arrête avant `dbt` (E15)
- Parcoursup et référentiels : 0 anomalie bloquante sur les données réelles
- Sirene : **5 établissements** portent une date de création en 2054, 2116,
  2202, 2924 et 5015 — des fautes de frappe dans le répertoire officiel,
  vérifiées une à une. Elles bloquent. **10 613 immatriculations
  anticipées** à moins de cinq ans dans le futur sont légitimes et ne
  produisent qu'un avertissement
- 217 tests au total (153 + 64 nouveaux), tournant sur `data/samples/` sans
  les 4,6 Go de sources réelles

**E14 — la frontière entre bloquer et avertir, justifiée par la mesure**
Un contrôle naïf « date supérieure à aujourd'hui » aurait bloqué sur 10 618
lignes dont 10 613 saines, et aurait été désactivé en une semaine. Le seuil
de cinq ans sépare l'immatriculation anticipée plausible de la faute de
frappe. Détail : `03-pipeline/qualite.md`.

**E14 — trois hypothèses de contrôle fausses, corrigées avant d'être
figées** : un ratio admission/vœux supposé borné à 1 (structurel, jusqu'à 26
en 2025) ; un admis supposé avoir nécessairement un vœu dans sa cellule
(482 cas réels en 2025) ; `acc_tot` supposé égal à la somme des quatre types
de bac (faux sur cinq sessions sur huit, rétrogradé en avertissement).
Écrire un contrôle sans le confronter aux données réelles produit un
contrôle faux.

**E14 — limite assumée** : pas de contrôle de schéma dédié pour
`StockEtablissementHistorique`, `StockUniteLegale` et
`StockUniteLegaleHistorique` — seule leur fraîcheur est contrôlée, aucun
traitement du pipeline ne les lit encore. Reporté dans `reste-a-faire.md`.

**E14 — décision prise** : ADR 0014 — Pandera plutôt que Great Expectations,
chiffré (447 Ko contre 5,7 Mo, une dépendance nouvelle contre neuf), avec le
seuil de bascule écrit.

**E15 — ce qui a été vérifié**
- `src/edumatch/transform/reconciliation.py` réconcilie les huit millésimes
  bronze en une table silver unique : reconstruction de la clé `cod_aff_form`
  pour 2018 et 2019 (couverture mesurée **92,4 % et 94,6 %**, ADR 0010),
  harmonisation des 128 colonnes classées par l'ADR 0013 (une colonne absente
  d'un millésime devient une colonne de valeurs manquantes, jamais une colonne
  absente du schéma final), typage générique sans table de correspondance à
  maintenir à la main
- Grain `(session, cod_aff_form)` vérifié unique à la construction — une
  clé dupliquée au sein d'une même session lève une erreur définitive
- Idempotence et écriture atomique par la même primitive que les connecteurs
  d'ingestion (`ecriture_atomique`) : un fichier temporaire renommé une fois
  l'écriture terminée, jamais de `silver.parquet` tronqué
- Volumétrie obtenue : **104 274 lignes, 128 colonnes** ; `silver.parquet`
  16 247 456 o, `silver.duckdb` (base de travail dbt) 22 294 528 o
- Projet dbt (`src/edumatch/transform/dbt/`) : les huit sources bronze
  déclarées dans `models/bronze/_sources.yml`, le modèle silver
  `stg_parcoursup.py`, un test dbt singulier (`assert_grain_unique.sql`) qui
  rejoue le même contrôle de grain que côté Python — redondant par
  construction, gardé parce que E15 exige des tests dbt verts, pas seulement
  une garantie invisible depuis `dbt test`

**E15 — décision prise** : documentée dans l'ADR 0015 (avec E16, les deux
étapes forment un seul arbitrage de modélisation de la couche gold, silver en
étant le socle direct).

**E16 — ce qui a été vérifié**
- `src/edumatch/transform/etoile.py` construit les cinq tables gold à partir
  de silver : le grain de `fait_admission` est la cellule `(session,
  cod_aff_form, type_bac, boursier)`, portée après résolution des dimensions
  par `(session, sk_formation, sk_profil)` — **vérifié unique** sur les
  440 030 lignes produites, et **0 ligne** à taux hors `[0, 1]`
- Volumétrie obtenue : `fait_admission` 440 030 lignes / 9 colonnes
  (67 768 / 71 080 / 72 784 / 74 831 / 76 408 / 77 159 sur 2020-2025) ;
  `dim_formation` 43 858 / 12 ; `dim_territoire` 1 448 / 6 ; `dim_profil_candidat`
  6 / 4 ; `dim_session` 8 / 2 ; total sur disque 4 766 953 o (4,55 Mio)
- 2018 et 2019 ne produisent aucune ligne de faits : `prop_tot_*` (numérateur
  du label) n'y est renseigné sur aucune ligne, le filtre porte sur la
  disponibilité de la donnée, jamais sur un millésime écrit en dur. Les deux
  sessions restent présentes dans `dim_session`, avec `label_disponible =
  false`
- Écart de périmètre mesuré et documenté : le catalogue silver compte
  16 960 formations distinctes sur 2020-2025 (dont 10 826 aux six sessions),
  `dim_formation` n'en porte que 16 618 — 342 formations du catalogue
  n'ont aucune cellule exploitable et n'entrent dans aucun fait
- Trois garanties de construction vérifiées avant écriture : grain unique,
  aucune dimension ni aucun fait orphelin, aucune jointure de dimension qui
  fait varier le nombre de lignes (signature d'une plage SCD 2 qui se
  recouvre) — un simple contrôle « pas de doublon sur le grain final »
  n'aurait pas détecté ce dernier cas
- Chaîne dbt complète verte : `dbt run` + `dbt test` → **26 nœuds, 26
  succès** ; `dbt docs generate` → catalogue sur **6 nœuds** (`stg_parcoursup`
  et les cinq tables gold) ; suite de tests du dépôt → **260 tests, 260
  succès**

**E16 — décision prise** : ADR 0015 — six arbitrages sur le modèle
dimensionnel de la couche gold : grain à la maille cellule (pas
formation-session, pas de ligne dépliée par genre), une étoile plutôt qu'une
table plate ou un flocon, SCD 2 sur `dim_formation` (contre SCD 1, qui
réécrirait l'histoire et introduirait une fuite rétrospective), pas de
dimension « établissement » séparée (surarchitecture sans second grain qui la
justifie), DuckDB/Parquet plutôt que PostgreSQL ou un entrepôt distant (la
couche gold pèse 4,55 Mio), et un filtre d'exploitabilité écrit sur la donnée
plutôt que sur un millésime en dur pour 2018-2019. Détail complet, options
écartées et seuils de bascule : ADR 0015 ;
`02-architecture/modele-etoile.md` pour le modèle lui-même ;
`03-pipeline/transformation.md` pour l'enchaînement, les tests dbt qui
bloquent et le lignage.

**E16 — limites déclarées**
- `session_fin` documente la dernière session **observée** d'une version de
  formation, pas une garantie de continuité sur les sessions absentes.
- `dim_formation` est construite formation par formation en Python, pas en
  SQL ensembliste — négligeable à 16 618 formations, à réécrire en fonction
  de fenêtre à un ordre de grandeur de plus.
- La couche gold ne couvre que Parcoursup : les agrégats territoriaux Sirene
  (E17) n'y sont pas encore rattachés.
- Aucun partitionnement ni indexation à cette volumétrie — assumé, pas oublié.

**E17 — ce qui a été vérifié**
- `src/edumatch/spark/` produit l'agrégat commune × NAF depuis
  `StockEtablissement.parquet` (43 896 818 lignes, 54 colonnes, 355 row
  groups, 2,20 Go) : 9 colonnes lues sur 54, filtrage à la lecture prouvé par
  `df.explain(True)` (`ReadSchema` limité aux 9 colonnes, `PushedFilters`
  renseignés) et par un test dédié
- Grain `(codeCommuneEtablissement, activitePrincipaleEtablissement)`,
  unicité vérifiée. Sortie : `data/processed/sirene/agregats_commune_naf.parquet`,
  **1 929 179 lignes, 14 colonnes, 12 618 239 o (12,6 Mo)** — réduction de
  2,20 Go à 12,6 Mo. 35 664 communes distinctes, 1 743 codes NAF distincts
- **2 423 308** actifs-employeurs agrégés, **4 897 540** fermés-employeurs
  conservés à côté (cessations non exclues, pour ne pas biaiser la mesure de
  débouchés vers les seuls territoires en croissance). Écart avec les
  2 436 624 actifs-employeurs du fichier : **13 316 lignes sans commune**,
  vérifiées porter toutes un `codePaysEtrangerEtablissement` — des
  établissements domiciliés à l'étranger, hors du grain territorial
- Couverture NAF 2025 mesurée : **100,0 %** des actifs-employeurs agrégés (14
  lignes seulement sans code NAF 2025), en vue de la bascule de nomenclature
  prévue début 2027
- `filtres.diffusible` déclaré en configuration mais **non appliqué** : écart
  chiffré à 20 501 établissements non diffusibles sur 2 436 624 (0,84 %),
  assumé et documenté, pas une omission silencieuse
- Deux moteurs implémentés, un seul jeu de règles métier partagé
  (`definitions.py`) : Polars (chemin `local`, dev/staging) et Spark (chemin
  `cluster`, prod), même résultat vérifié ligne à ligne sur le même
  échantillon. Mesure comparative sur le fichier complet, même filtre, mêmes
  9 colonnes, même regroupement : **Polars 18,2 s** contre **PySpark 87,0 s**
  (18,0 s de démarrage JVM + 69,0 s de calcul) — Spark 4,8× plus lent sur ce
  volume
- Suite de tests complète du dépôt : **278 tests, 278 succès** (260 avant
  cette étape)

**E17 — décision prise** : ADR 0016 — Polars en exécution courante, Spark
implémenté et testé, branché sur `execution.moteur_volume: cluster`. La
mesure (Spark plus lent) est rapportée telle quelle plutôt que masquée ; le
choix retenu est assumé malgré elle, avec le seuil de bascule écrit (fusion
de plusieurs fichiers Sirene — l'historique seul dépasse déjà 95,9 M lignes —
ou calcul intermédiaire qui ne tient plus en mémoire sur un poste de
développement).

**E17 — limites déclarées**
- Sur ce poste de développement (Windows), l'écrivain Parquet natif de Spark
  échoue faute de `winutils.exe` : le résultat, déjà réduit à 12,6 Mo, est
  ramené au pilote puis écrit par la primitive atomique du projet — valide
  aussi sur le cluster de production Linux, pas un contournement propre à
  Windows.
- L'agrégat n'est pas encore raccordé à la couche gold Parcoursup : il vit
  dans `data/processed/sirene/`, hors du modèle en étoile.
- **Question ouverte, non tranchée** : mesuré sur l'agrégat produit,
  584 489 des 886 688 cellules qui portent au moins un établissement actif
  (65,9 %) n'en portent qu'un seul. Une cellule à effectif 1 n'est ni un
  agrégat statistiquement exploitable pour le terme « débouchés » du score,
  ni conforme à une logique de pseudonymisation quand l'établissement
  identifié figure parmi les 20 501 non diffusibles non filtrés à cette
  étape. Reportée dans `reste-a-faire.md`, à trancher au croisement de la
  protection des données et de la construction du score (E28).

**E18 — ce qui a été vérifié**
- `src/edumatch/referentiel/naf_rome_formation.py` assemble trois sources
  publiques réelles pour relier une formation IDÉO (ONISEP) à une division
  NAF : formation IDÉO → fiche RNCP → code(s) ROME (via le membre ROME de
  l'archive RNCP quotidienne) → division NAF (via la table France Travail
  ROME/NAF)
- Couverture mesurée maillon par maillon, jamais un taux global unique :
  formations IDÉO avec code RNCP renseigné 3 857 / 5 869 (65,72 %) · fiches
  de l'export ROME couvrant au moins un code ROME 24 424 / 24 424 (100 %) ·
  formations avec RNCP rattachées à un ROME 3 605 / 3 857 (93,47 %) · codes
  ROME de l'export RNCP couverts par la table France Travail 528 / 572
  (92,31 %) · **chaîne complète formation IDÉO jusqu'à une division NAF
  3 605 / 5 869 (61,42 %)** · lignes rattachées à une certification active
  25 213 / 26 358 (95,66 %) · formations distinctes rattachées à une
  certification active 3 412 / 3 605 (94,65 %)
- Table produite : `data/processed/referentiel/naf_rome_formation.csv`,
  **26 358 lignes, 8 colonnes**, 4 887 629 octets. État des certifications
  exposé par une colonne (`rncp_actif`), jamais filtré : 25 213 lignes
  actives, 1 145 radiées (4,3 %), 0 valeur nulle — le choix d'exclure les
  radiées relève du calcul des débouchés (E28)
- Suite de tests complète du dépôt : **309 tests, 309 succès** (278 avant
  cette étape)

**E18 — deux manques déclarés, pas comblés**
1. Aucune formation Parcoursup n'est reliée à cette chaîne : vérifié sur les
   huit millésimes et sur `dim_formation.parquet`, aucun ne porte de code
   RNCP, NSF ou ROME. Seul un appariement textuel des libellés serait
   possible, non arbitré ici — c'est exactement le type de correspondance
   ambiguë que ce projet s'interdit de trancher sans mesure.
2. La correspondance ROME/NAF n'existe qu'au niveau division (2 chiffres),
   quand l'agrégat Sirene (E17) est à la sous-classe (5 caractères) : le
   rattachement à un établissement réel perd la granularité fine de
   l'activité. Aucune source publique ne relie ROME à la sous-classe.

**E18 — un fait de qualité de source, rapporté tel quel**
Contrôlé jusqu'à sa source : « BT métiers de la musique » (RNCP 919) ressort
rattaché au code ROME D1211 « Vente en articles de sport et loisirs ». C'est
l'export officiel du RNCP lui-même qui attribue ce code (et L1201 « Danse »)
à cette fiche. La jointure est fidèle ; c'est la source qui est bruitée —
une limite de la donnée publique, pas un défaut du code produit ici.

**E18 — deux effets de bord, à mentionner honnêtement**
- Le connecteur d'ingestion des référentiels (E07) a été étendu : un nouveau
  membre de l'archive RNCP (le CSV RNCP↔ROME) et une nouvelle source
  (France Travail, table ROME/NAF) s'ajoutent à ce qu'il téléchargeait déjà.
  Le module qui génère les échantillons de test (`echantillons.py`) a dû
  être scindé pour rester sous la limite de taille de fichier du projet,
  cet ajout l'ayant fait dépasser le seuil.
- Un bug d'encodage a été corrigé dans l'écriture atomique partagée par tout
  le projet (`_flux.ecriture_atomique`) : en mode texte, l'encodage n'était
  pas imposé et Python retombait sur celui de la plateforme (`cp1252` par
  défaut sous Windows) — un défaut silencieux à l'écriture, révélé
  seulement à la relecture (la lecture, elle, déclare explicitement
  `utf-8`). Constaté sur un titre de ressource France Travail contenant un
  accent. Corrigé en imposant `utf-8` en mode texte, avec un test de
  non-régression qui reproduit le cas exact.

**E18 — décision prise** : ADR 0017 — construire la chaîne sur trois sources
réelles et déclarer le maillon Parcoursup manquant, plutôt que de l'apparier
par libellés en texte libre. Seuil de bascule : la publication d'une table
ROME↔NAF à la sous-classe, ou l'apparition d'un identifiant de certification
dans un futur millésime Parcoursup.

**E18 — question de gouvernance signalée, non tranchée**
La table dérivée intègre des données IDÉO (ODbL) aux côtés de données RNCP et
France Travail (Licence Ouverte v2.0). La clause de partage à l'identique de
l'ODbL s'applique potentiellement si cette table est redistribuée telle
quelle — signalé dans `01-donnees/sources.md`, à reprendre par le registre
des sources (E40).

**E19 — ce qui a été vérifié**
- `src/edumatch/features/label.py` regroupe en un seul lieu ce qui était
  jusqu'ici codé directement dans la couche gold (`transform/etoile.py`) : la
  formule du taux (`calculer_taux`), inchangée, et sa pondération à
  l'entraînement (`poids_effectif`), décidée en principe par l'ADR 0009 mais
  jamais codée jusqu'ici. `etoile.py` appelle désormais cette fonction au lieu
  de la recalculer
- **Preuve d'empreinte identique avant/après**, sur
  `data/processed/parcoursup/fait_admission.parquet` réel : 440 030 lignes,
  somme des taux 201 404,572 630 955 43, 31 900 cellules à `taux_depasse_1`,
  empreinte SHA-256 `932e2ca72461f1e896c4bdac5b500cff4425b098589c8114ef0a0c04aa6106fd`
  identique de part et d'autre — recalculée moi-même de façon indépendante,
  pas seulement supposée. 0 valeur hors de `[0, 1]` avant comme après
- **Mesure de concentration du poids**, sur les 440 030 cellules, avant de
  confirmer la forme retenue : le 1 % de cellules les plus grosses (4 400)
  capte 25,9 % du poids total avec l'effectif brut, contre 15,4 % plafonné au
  p99, 7,2 % en racine carrée, 2,3 % en log(1+n). L'effectif brut est retenu
  tel quel (ADR 0009, décision 3 ; `configs/base.yaml`,
  `modele.ponderation: effectif_cellule`) : c'est la seule forme qui traduit
  l'écart de fiabilité statistique entre une petite et une grosse cellule
- Test de non-régression du label (`tests/data/test_features_label_non_regression.py`)
  à deux niveaux : un vecteur de cinq cellules figé sur la fonction isolée, et
  le pipeline complet rejoué sur les échantillons versionnés (1 280 cellules,
  somme des taux 558,742 252 776 133 5, 180 192 d'effectif total)
- Suite de tests complète du dépôt : **327 tests, 327 succès** (309 avant
  cette étape)

**E19 — limite à signaler avant la remise**
`make` n'est pas présent dans le PATH de ce poste : les commandes Python
sous-jacentes ont été employées directement à sa place pour produire les
chiffres ci-dessus. La documentation invite pourtant le lecteur à reproduire
par `make`. À vérifier sur un poste où `make` est disponible avant la remise
du dépôt.

**E19 — décision prise** : aucun ADR nouveau — l'ADR 0009 couvre déjà la
définition du taux et le principe de la pondération. Cette étape est une mise
en conformité du code avec une décision déjà arrêtée (regroupement de la
formule, codage de la forme du poids), pas un nouvel arbitrage.

**E20 — ce qui a été vérifié**
- `src/edumatch/features/build.py` applique, colonne par colonne, le
  classement arrêté par l'ADR 0013 (`modele.variables`) : les deux dimensions
  de cellule sont résolues depuis `dim_profil_candidat`, les 9 colonnes de la
  liste blanche sont lues par jointure directe sur la session prédite, les
  35 colonnes décalées sont lues sur la table silver translatée de `+1`
  session avant jointure — 46 variables au total
- Jeu produit sur les huit millésimes réels : **440 030 lignes, 46
  variables**, une ligne de sortie par cellule d'entrée (aucune jointure
  n'est autorisée à changer ce nombre, `_joindre_sans_fan_out`)
- **28 425 cellules sans antécédent décalé (6,46 %)** : session cible 2020
  (pas de `prop_tot` ventilé en N-1, ADR 0012/0013 §6) et formations
  nouvelles sans ligne silver en N-1. Valeur laissée `<NA>`, jamais imputée —
  combler fabriquerait un antécédent qui n'a pas existé, LightGBM (ADR 0009,
  ADR 0013) traite nativement l'absence. Colonne la plus souvent manquante :
  `ran_grp1`, 20,7 %
- **Contrat anti-fuite vérifié par mutation du code, refaite moi-même en plus
  de celles rapportées lors du développement, code restauré après chaque
  mutation** :
  - décalage ramené de `+1` à `+0` → 4 tests échouent, tous ceux qui
    reposent sur le décalage (dont
    `test_les_variables_decalees_proviennent_reellement_de_la_session_precedente`),
    342 restent verts
  - `pct_f` (genre) et `cod_uai` (substitut) réintroduits de force dans les
    colonnes produites → `test_aucune_colonne_de_genre_n_est_presente` et
    `test_cod_uai_est_absent_du_jeu_construit` échouent chacun
  - le test discriminant s'appuie sur une colonne dont la valeur diffère
    franchement entre les deux sessions (`capa_fin` à 40 contre 999999) : un
    test qui aurait seulement vérifié la présence des colonnes serait passé
    même avec la jointure inversée, sans rien prouver
- **Liste blanche, jamais liste noire** : une colonne non classée par l'ADR
  0013 ne peut jamais entrer par défaut ; `_verifier_colonnes_licites`
  refuse toute colonne hors des catégories déclarées
- **Piège de nommage bloqué explicitement** : `fait_admission` porte déjà
  `nb_voe_pp` et `prop_tot` sur la session prédite, homonymes de deux
  colonnes décalées (même colonne source, lue à N-1). Sans contrôle, la
  jointure aurait renommé les deux en silence (`_x`/`_y`) au lieu d'échouer,
  laissant passer une variable de résultat de campagne sans signal. Le code
  échoue désormais explicitement sur cette homonymie
  (`_colonnes_a_construire`)
- Suite de tests complète du dépôt : **346 tests, 346 succès** (327 avant
  cette étape, 19 nouveaux)

**E20 — décision prise** : aucun ADR nouveau — l'ADR 0013 couvre déjà le
classement des variables. Cette étape en est l'application, pas un nouvel
arbitrage.

## Phase 4 — Modèle

| # | Étape | État | Date | Commit |
|---|---|---|---|---|
| E21 | Baseline | ✅ validée | 2026-08-30 | `2b4c409` |

**E21 — ce qui a été vérifié**
- `src/edumatch/models/baseline.py` mesure quatre variantes, sans aucun
  paramètre appris : le taux de la même cellule à la session précédente
  (`session_precedente`, la règle retenue par `configs/base.yaml`), sa
  version à couverture complète par repli sur une moyenne de groupe
  (`session_precedente_avec_repli`), une moyenne pondérée par groupe
  `(type de bac, boursier)` en fenêtre expansive
  (`moyenne_groupe_expansive`), et une moyenne globale, sans distinction de
  groupe (`moyenne_globale_expansive`)
- Mesuré sur les 440 030 cellules réelles (E20), MAE pondérée par l'effectif
  (ADR 0009) : **0,0664** sur validation + test à couverture comparable
  (92,6 %), **0,0713** à couverture complète (100 %, repli inclus) — le
  plancher que le modèle appris (E22-E23) doit désormais battre nettement.
  J'ai recalculé ces chiffres indépendamment du code livré et je retrouve
  les mêmes valeurs
- Les deux moyennes de repli, mesurées comme second plancher plus naïf :
  0,2098 (par groupe) et 0,2124 (globale) — environ trois fois pire que le
  taux de la session précédente, ce qui justifie chiffrée le choix de la
  règle retenue plutôt qu'une des deux autres
- **Deux limites structurelles mesurées, pas masquées** : la session 2020
  n'a de couverture nulle pour toute variante, aucune session antérieure ne
  portant le numérateur du label ventilé par type de bac (ADR 0012),
  vérifié par un test dédié ; les cellules sans antécédent reçoivent un
  repli par moyenne de groupe en fenêtre expansive — jamais une moyenne
  calculée sur tout l'entraînement, qui aurait utilisé des labels
  postérieurs à la session prédite — et le score est rapporté avec et sans
  ce repli plutôt que de le laisser implicite
- Suite de tests complète du dépôt : **363 tests, 363 succès** (346 avant
  cette étape, 17 nouveaux)

**E21 — limite constatée et corrigée** : le paquet MLflow était déclaré dans
les dépendances mais n'était pas installé dans l'environnement au moment de
l'exécution d'E21. La baseline n'a donc pas été journalisée dans le registre
d'expériences au moment de sa mesure, alors que la discipline retenue pour ce
dépôt veut que le suivi d'expériences commence à la première expérience, pas
après. Le paquet a été installé depuis le constat ; l'enregistrement
rétroactif de cette baseline dans le registre est traité à l'étape suivante,
avant l'entraînement du modèle.

**E21 — décision prise** : aucun ADR nouveau — les règles comparées
n'introduisent aucun arbitrage de modélisation, seulement une mesure. Le
détail complet (tableau par session, comparatif des trois règles, le seuil
posé pour l'étape suivante) est dans `04-modele/evaluation.md`.
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
