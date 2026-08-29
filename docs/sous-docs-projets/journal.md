# Journal de développement

Une entrée par journée de travail. Je le tiens moi-même.

Format :

```
## AAAA-MM-JJ

**Fait** : ce qui a réellement été produit
**Décisions** : ADR écrits ce jour
**Bloqué sur** : ce qui reste ouvert
**Jury** : verdict du jour si évaluation
```

---

## 2026-08-29 — E13, décision de variables : liste blanche et clôture de la phase exploratoire

**Fait** : E13 validée — ADR 0013, synthèse colonne par colonne des quatre
carnets d'exploration sur les **128 colonnes** vues au moins une fois sur les
huit millésimes Parcoursup. Classement sans reste : **9 colonnes lues sur la
session prédite** (attributs de catalogue publiés avant la campagne : filière,
type de formation, sélectivité, contrat, territoire), **35 décalées d'une
session** (tous les compteurs), **8 de mention retenues sous réserve mais
écartées par défaut** (contamination du contrôle continu 2020), **73
exclusions définitives** classées par motif — redondance 23, instabilité 22,
complétude 10, hors périmètre 10, interdite 4 (ventilations par sexe),
substitut 3, cardinalité 1.

Le critère de tri n'est pas « la variable est-elle postérieure à l'admission »
mais « est-elle connue au moment où le lycéen formule ses vœux » : c'est ce
qui distingue une variable décalée d'une variable exclue, la même colonne
étant une fuite sur la session courante et une information légitime sur la
précédente. J'ai retenu une liste blanche plutôt qu'une liste d'exclusion :
une colonne ajoutée par un millésime futur est refusée par défaut, jusqu'à
être classée.

Le classement vit dans `configs/base.yaml` (`modele.variables`), typé par
`VariablesConfig` dans `src/edumatch/config.py`, avec validation de
disjonction entre catégories. Quatre contrôles de contrat dans
`tests/data/test_variables_reference.py`, vérifiés par mutation et non par
relecture. Le split est corrigé en cohérence avec l'ADR 0012 : entraînement
[2020-2023], validation [2024], test [2025]. **153 tests passent.**

Une hypothèse posée puis corrigée à la mesure : le motif de redondance des 19
colonnes de pourcentage supposait d'abord `pct_bours = acc_brs / acc_tot` —
faux, écart jusqu'à 97,5 points. Le dénominateur réel est `acc_neobac`.
Reconstitution vérifiée à 0,500 point près (l'arrondi) une fois le bon
dénominateur identifié.

Deux arbitrages d'équité, indépendants l'un de l'autre : `cod_uai` exclu pour
cardinalité (4 058 établissements) **et** pour son statut de premier
substitut du genre (28,9 % net) — les deux raisons tiennent séparément.
`fili`, deuxième substitut le plus fort (19,5 % net), est retenue malgré
tout : sans elle, le système ne peut plus comparer des formations entre
elles, et la ségrégation qu'elle porte n'est pas propre au modèle. Position
assumée, compensée par l'audit d'équité a posteriori (E26).

Trois points laissés ouverts, non masqués : `capa_fin` non tranchée
(classée décalée par prudence), le taux décalé manquant pour toute la
session cible 2020, et le contrôle anti-fuite automatique qui ne vérifie que
des noms de colonnes, pas leur sémantique de publication réelle.

**Décidé** : ADR 0013 — liste blanche sur la session prédite, décalage d'une
session pour le reste. Cette étape clôt la phase exploratoire (E09 à E13) :
la phase suivante (qualité et transformation) peut s'appuyer sur un jeu de
variables arrêté.

**Bloqué sur** : rien. Prochaine étape : E14, contrôles qualité bloquants.

**Jury** : aucune évaluation ce jour.

## 2026-08-29 — E12, stabilité inter-millésimes et révision du protocole d'évaluation

**Fait** : E12 validée — `notebooks/04-jgk-eda-stabilite-millesimes.ipynb`
(18 cellules dont 11 de commentaire, 2 figures exportées). Clôture la phase
exploratoire. Constat central : le numérateur du label ventilé par type de
baccalauréat n'existe qu'à partir de la session 2020 — le label n'est
calculable que sur six sessions, pas huit. Volumétrie corrigée : **440 030
cellules exploitables** sur 2020-2025 (67 768 · 71 080 · 72 784 · 74 831 ·
76 408 · 77 159), contre 560 000 à 625 000 annoncées en supposant huit
sessions utilisables.

La cible n'est pas stationnaire, et deux définitions divergent : le taux
agrégé baisse de 40,5 % à 36,7 % entre 2020 et 2025, pendant que la moyenne
des taux par formation — la cible réellement apprise — monte de 0,491 à
0,522, le catalogue s'élargissant de formations plus petites et moins
tendues. Deux ruptures de série identifiées, sur les mentions (2020) et sur
la part de vœux boursiers (2019-2020 puis 2025), toutes deux documentées
sans écarter la session 2020 : l'anomalie porte sur des variables
candidates, pas sur le label lui-même.

**Corrigé** : la volumétrie du label (440 030 cellules sur six sessions,
et non 560 000 à 625 000 sur huit) dans `01-donnees/label.md`,
`01-donnees/sources.md` et `04-modele/evaluation.md`.

**Décisions** : ADR 0012 — protocole d'évaluation révisé : entraînement
2020-2023 (286 463 cellules), validation 2024, test 2025, avec trois
réserves écrites avant tout résultat (mentions contaminées 2020-2021,
métriques ventilées par statut boursier, dégradation possible entre
validation et test imputable à la non-stationnarité de la cible avant
d'être imputable au modèle). Alternative écartée : construire un label dès
2018 à partir de `acc_bg` — mesurerait l'acceptation, pas l'admission, et
produirait un label composite incohérent avec lui-même selon la session.

**Bloqué sur** : rien. Prochaine étape : E13, décision de variables (ADR),
qui synthétise E10, E11 et E12.

**Jury** : aucune évaluation ce jour.

---

## 2026-08-29 — E11, équité et substituts du genre

**Fait** : E11 validée — `notebooks/03-jgk-eda-equite-substituts.ipynb`
(17 cellules dont 9 de commentaire, 3 figures exportées). À formation égale,
l'écart d'admission entre femmes et hommes est proche de nul : médiane à
−0,04 point sur 11 099 formations comparables, inférieur à 5 points dans
83,8 % des cas. L'inégalité observée dans le système d'orientation se joue
donc en amont, dans le choix des formations, pas à l'admission.

Substituts du genre mesurés par information mutuelle, corrigée du nombre de
modalités par permutation (5 tirages, graine 42) : `cod_uai` 28,9 % net ·
`fili` (filière) 19,5 % · `ville_etab` 10,2 % · `select_form` 5,6 % · `dep`
2,3 % · `acad_mies` (académie) 1,4 %. **L'hypothèse de départ est
infirmée** : l'académie, désignée comme substitut à surveiller, arrive
dernière ; le deuxième substitut le plus puissant est la filière, variable
indispensable qu'on ne peut pas retirer du modèle. L'exclusion du genre à
l'entrée est donc nécessaire mais insuffisante — dispositif retenu à trois
niveaux : exclusion, mesure des substituts, audit a posteriori sur les
prédictions (E26).

**Corrigé** : 179 formations n'admettant aucun candidat faussaient à 0 % un
ratio de féminisation sans rapport avec la réalité d'un processus
d'admission qui n'a pas eu lieu — un pourcentage se lit avec son
dénominateur. Le constat de formations à moins de 20 % de femmes passe de
2 954 à **2 775 (19,7 %)**, dénominateur non nul. Deuxième correction :
sans la correction de cardinalité par permutation, `cod_uai` aurait été
crédité d'un pouvoir explicatif deux fois trop grand — une variable à haute
cardinalité capte mécaniquement de l'information mutuelle avec n'importe
quelle cible.

**Décisions** : ADR 0011 — dispositif d'équité à trois niveaux (exclusion,
mesure des substituts, audit a posteriori), la filière étant conservée
comme variable malgré sa corrélation résiduelle au genre, faute
d'alternative qui ne détruirait pas la capacité prédictive du modèle.

**Bloqué sur** : rien. Prochaine étape : E12, stabilité inter-millésimes.

**Jury** : aucune évaluation ce jour.

---

## 2026-08-29 — E10, écarts entre baccalauréats et sélectivité

**Fait** : E10 validée — `notebooks/02-jgk-eda-ecarts-selectivite.ipynb`
(18 cellules dont 10 de commentaire, 3 figures exportées). Comparaison
appariée (la même formation avec elle-même) sur les 12 552 formations
recevant des vœux des deux profils de bac : écart médian de +8,5 points en
faveur du bac général, mais 26,8 % des formations avantagent le bac
professionnel — il n'existe pas un désavantage uniforme, mais une forte
hétérogénéité selon la filière. CPGE, BUT et PASS affichent une médiane de
taux nulle pour le bac professionnel : dans plus de la moitié de ces
formations, un candidat de cette voie ne reçoit aucune proposition. La
tension (`voe_tot / capa_fin`) explique fortement le taux observé, de 1,000
à 0,182 du quintile le moins tendu au plus tendu.

**Corrigé (constat, pas un chiffre déjà publié)** : `voe_tot` n'est pas
utilisable comme variable du modèle malgré son fort pouvoir explicatif —
elle n'existe qu'à la clôture de la campagne, après le moment où le système
doit répondre à un candidat qui formule encore son vœu. Ce n'est pas une
fuite temporelle au sens strict, mais une inadéquation entre la
disponibilité de la variable et le moment de l'inférence. Décalage temporel
identifié en compensation : `cod_aff_form`, absente avant 2020, se
reconstruit à 92,4 % (2018) et 94,6 % (2019) à partir du paramètre `g_ta_cod`
du lien vers la fiche de formation, avec un taux de jointure d'une session à
la suivante de 82 % à 95 %.

**Décisions** : ADR 0010 — exclusion de `voe_tot` de la session courante des
variables du modèle, seule une version décalée d'au moins une session étant
éligible ; reconstruction de la clé de formation pour 2018-2019, avec test
de couverture à chaque exécution du pipeline.

**Bloqué sur** : rien. Prochaine étape : E11, équité et substituts du genre.

**Jury** : aucune évaluation ce jour.

---

## 2026-08-29 — E09, analyse exploratoire du label

**Fait** : E09 validée — `notebooks/01-jgk-eda-label.ipynb` (34 cellules, dont
20 de commentaire, sorties nettoyées), figure exportée dans
`reports/figures/e09-distribution-taux-admission.png`. Grain établi : une
ligne est une formation identifiée par `cod_aff_form`, pour une session — clé
vérifiée sans doublon ni manque (14 252 valeurs distinctes en 2025).
`cod_uai` seul ne suffit pas : 4 058 établissements pour 14 252 formations.
Schéma réconcilié sur les huit millésimes : 83 colonnes communes sur 128 vues
au moins une fois, dont 59 remplies à plus de 99 % partout.

Trois faits de dérive relevés dans les données elles-mêmes :
`etablissement_id_paysage` et `composante_id_paysage`, mortes en 2025 après
avoir été renseignées à 47 % de 2021 à 2024 ; `pct_etab_orig`, dont la
publication s'élargit à toutes les filières en 2023 ; `acc_term`, dont
l'absence vaut 0 % ou 100 % selon la filière — non applicable, pas manquante,
donc jamais à imputer.

Le label dépasse 1 dans 8,9 % des cellules bac général, et ce dépassement
persiste sur les grosses cellules (483 sur 7 154 au-delà de 100 vœux) : c'est
structurel, `prop_tot` compte des propositions réémises après désistement,
`nb_voe_pp` compte des vœux. J'ai comparé quatre définitions du taux avant de
trancher : `acc / nb_voe_pp` ne dépasse jamais 1 mais mesurerait l'acceptation
d'une proposition, pas l'admission — écartée.

**Corrigé** : la moyenne de 0,522, déjà citée dans la documentation et le
dossier, s'est avérée être la moyenne calculée sur le taux borné à 1 (la
moyenne brute vaut 0,545). La borne était déjà appliquée dans le calcul, sans
être écrite nulle part. Rendue explicite dans `01-donnees/label.md` et
l'ADR 0009, sans changer le chiffre.

**Décisions** : ADR 0009 — quatre décisions sur le label : conserver
`prop_tot / nb_voe_pp`, borner à 1 en énonçant pourquoi, pondérer par
l'effectif de la cellule à l'entraînement, ne pas exclure les petites
cellules (un seuil à 30 vœux écarterait 26 % des observations).

**Bloqué sur** : rien. Prochaine étape : E10, écarts entre types de bac et
sélectivité par filière.

**Jury** : aucune évaluation ce jour.

---

## 2026-08-29 — E08, échantillons de test versionnés

**Fait** : E08 validée — `data/samples/` (1,2 Mo, 17 échantillons couvrant
Parcoursup, Sirene et les référentiels), généré par
`src/edumatch/ingestion/echantillons.py` (`make samples`). Critère de
validation vérifié en le provoquant : `data/raw/` et `data/external/` rendus
absents, la suite complète tourne quand même — 145 passed. Échantillonnage
systématique déterministe (empreinte identique sur deux générations). Les 8
millésimes Parcoursup couvrent la dérive de schéma 85 → 118 colonnes.

Sujet central de l'étape, plus juridique que technique : les 9 colonnes
d'identité directe sont exclues de `StockUniteLegale`, mais 282 des 500
lignes de l'échantillon sont des entrepreneurs individuels (catégorie
juridique 1000), dont 239 diffusibles ; une jointure sur le SIREN avec la
dénomination d'établissement, conservée ailleurs dans l'échantillon,
restitue leur identité à 239 sur 239. Ces échantillons sont donc
**pseudonymisés, pas anonymisés** : ils restent dans le champ du RGPD. Base
légale retenue : intérêt légitime (art. 6.1.f), mise en balance écrite. La
Licence Ouverte ne vaut jamais base légale — les deux régimes se cumulent.
Détail complet : `01-donnees/echantillons.md`, ADR 0008.

**Corrigé** : `test_echantillons_conformite.py` importait sa liste de
colonnes interdites depuis le module de génération qu'il était censé
contrôler — vider la liste dans le module aurait laissé le test vert. Devenu
une liste blanche écrite en dur dans le test, propre à chaque fichier
Sirene, qui refuse par défaut toute colonne non examinée.

**Décisions** : ADR 0008 — conserver les lignes d'entrepreneur individuel
sous intérêt légitime plutôt que de les exclure de l'échantillon.
Alternatives écartées : exclusion (détruirait la représentativité, 56,4 %
des lignes du fichier source complet), hachage du SIREN (espace forçable en
secondes), valeur de substitution fabriquée (donnée simulée, interdite).

**Bloqué sur** : rien. Prochaine étape : E09, EDA — label et distributions.

**Jury** : aucune évaluation ce jour.

## 2026-08-29 — E07, connecteur référentiels et deux corrections

**Fait** : E07 validée — `ingestion/referentiels.py`, `_referentiels_rncp.py`
et `_referentiels_communs.py` téléchargent les 4 jeux ONISEP (IDÉO, URL fixe)
et l'export RNCP du jour (résolu par interrogation du catalogue data.gouv,
puis extraction du CSV standard depuis l'archive ZIP), avec les mêmes
garanties que Parcoursup et Sirene. Suite complète du dépôt à 120 tests
passants. Téléchargement réel effectué aujourd'hui vers
`data/external/referentiels/` : 22 Mo au total. Volumétrie IDÉO conforme aux
chiffres du 26/08, à la ligne près. Export RNCP du jour : **30 484 fiches**
(7 000 actives, 23 484 inactives), 16 colonnes.

Deux corrections importantes, propagées dans `01-donnees/sources.md` et
`03-pipeline/ingestion.md` :

1. **Un chiffre faussé par l'outil de vérification lui-même.** « 36 000
   fiches RNCP, dont 6 995 actives » ne venait pas d'une évolution de la
   source, mais d'un comptage par `wc -l` — qui compte des retours à la ligne
   physiques — sur un CSV contenant des champs de texte multi-lignes entre
   guillemets. Un parseur CSV correct donne 30 484, confirmé par la somme
   7 000 + 23 484. Le compte des actives survivait par coïncidence, la
   chaîne « ACTIVE » n'apparaissant jamais dans un champ multi-ligne de cet
   export. Corrigé : `scripts/verifier_sources.sh` compte désormais avec un
   vrai parseur CSV, pour le RNCP et pour les 4 fichiers IDÉO par cohérence.
2. **Un encodage annoncé à tort.** Le RNCP était donné pour Latin-1 ; le
   fichier réel décode intégralement en UTF-8. Nuance retenue : un décodage
   Latin-1 sans erreur ne prouve rien, Latin-1 acceptant n'importe quelle
   suite d'octets — c'est pourquoi le contrôle d'encodage du connecteur est
   volontairement asymétrique, et documenté comme tel.

**Décisions** : ADR 0007 — un fichier par date de publication pour l'export
RNCP (`rncp_AAAA-MM-JJ.csv`), jamais un fichier unique écrasé : une table
dérivée du RNCP (E18) doit rester vérifiable sur l'export qui l'a produite.
Alternatives écartées : fichier unique écrasé, retéléchargement systématique
sans persistance. Seuil de bascule : une politique de rétention à écrire si
la tâche est un jour programmée à cadence quotidienne sur une longue durée.

**Bloqué sur** : rien. Prochaine étape : E08, échantillons versionnés.

**Jury** : aucune évaluation ce jour.

## 2026-08-28 — E06, connecteur Sirene et correction du chiffre d'établissements

**Fait** : E06 validée — `ingestion/sirene.py` résout les 4 fichiers stock
configurés en interrogeant le catalogue data.gouv à l'exécution (aucune URL de
fichier codée en dur : les liens changent chaque mois, l'horodatage de
publication fait partie du chemin), puis les télécharge avec les mêmes
garanties que Parcoursup — idempotence par empreinte, écriture atomique,
manifeste — sur les primitives partagées de `_flux.py`, enrichies d'un rappel
de progression pour les transferts de plusieurs Go. Les deux connecteurs
partagent désormais un vocabulaire d'erreur transitoire/définitif
(`ErreurTransitoire`, `ErreurDefinitive` dans `_flux.py`), pour que le futur
DAG retente ou alerte sans connaître la classe interne du connecteur en cause
— Parcoursup a été rétrofité dans le même commit. Une vérification de la
taille annoncée par le catalogue contre la taille réellement écrite journalise
un avertissement au-delà d'un écart de 5 %, sans jamais bloquer la chaîne.
Suite complète du dépôt à 80 tests passants. Résolution rejouée aujourd'hui
contre le catalogue réel :
les 4 URL obtenues correspondent exactement à celles du manifeste enregistré
lors du téléchargement effectif, stock du 01/08/2026.

Correction de chiffre : « 36 millions d'établissements, 25 millions d'unités
légales », retenu depuis le début du projet, n'avait jamais été recalculé
depuis sa première mesure. Une fois les 4 fichiers réellement téléchargés, la
métadonnée Parquet donne **43 896 818 établissements, 29 922 486 unités
légales** — le chiffre retenu était sous-estimé. Corrigé dans
`01-donnees/sources.md`, `03-pipeline/ingestion.md`, l'ADR 0002,
`ARCHITECTURE_EduMatch.md` et le dossier de certification (`_build_dossier.py`,
régénéré). La correction renforce l'argument qui écarte Databricks au profit
de PySpark local : le volume est plus élevé que ce qui était annoncé, pas
moins. Nuance ajoutée : les filtres du projet ne retiennent que 2 436 624
lignes sur 43 896 818 (5,6 %), mais c'est la lecture du fichier entier, pas le
résultat filtré, qui dimensionne le traitement — et cette lecture (2 colonnes
sur 54) prend 35,4 secondes sur un poste ordinaire, ce qui justifie un Spark
local plutôt qu'un service managé pour le job réel (E17).

**Décisions** : ADR 0005 — résolution dynamique de l'URL Sirene contre une URL
en configuration. Coût assumé : une dépendance au catalogue au moment de
l'exécution, à traiter comme une panne transitoire dans le futur DAG, pas
comme une erreur de configuration. ADR 0006 — vocabulaire commun d'erreur
transitoire/définitif entre les deux connecteurs.

**Bloqué sur** : rien. Prochaine étape : E07, connecteur référentiels.

**Jury** : aucune évaluation ce jour.

## 2026-08-28 — E05, connecteur Parcoursup

**Fait** : E05 validée — `ingestion/parcoursup.py` télécharge les 8 millésimes
déclarés en configuration, avec idempotence par empreinte SHA-256 et écriture
atomique. Les primitives communes (flux HTTP, empreinte, écriture atomique,
manifeste) sont extraites dans `_flux.py`, avant que Sirene et les
référentiels ne les dupliquent. Suite complète du dépôt à 44 tests passants.
Volumétrie et schéma mesurés directement sur les 8 CSV posés sur disque :
104 274 formation-années au total, dérive de schéma confirmée (85 colonnes en
2018, jusqu'à 118 à partir de 2021), idempotence rejouée sur l'API réelle (les
8 millésimes renvoient `telecharge=False` au second passage).

Correction de chiffre : le poids des 8 CSV Parcoursup, jamais mesuré (l'export
de l'API ne porte pas de `Content-Length`), était estimé « ~100 Mo » dans la
documentation et mes notes de cadrage. Mesure directe une fois les fichiers
téléchargés : **82 Mo** (`du -sh data/raw/parcoursup/`). Corrigé dans
`01-donnees/sources.md`, `03-pipeline/ingestion.md`, l'ADR 0002 et le dossier
de certification (`_build_dossier.py`, régénéré). Le raisonnement qui appuie
le choix de ne pas distribuer la chaîne de décision (Polars/dbt plutôt que
Spark) s'en trouve renforcé, pas affaibli.

**Décisions** : ADR 0004 — extraction des primitives partagées avant la
deuxième occurrence plutôt qu'après trois duplications ; mise en quarantaine
d'un manifeste corrompu plutôt qu'écrasement silencieux.

**Corrigé** : un signalement de revue de code annonçait une perte d'entrées du
manifeste en fonctionnement normal. Reproduit avant correction : le risque
n'existait qu'en cas de manifeste déjà corrompu, pas en marche normale — déjà
couvert par la décision de quarantaine. Aucun correctif supplémentaire
nécessaire.

**Bloqué sur** : rien. Prochaine étape : E06, connecteur Sirene.

**Jury** : aucune évaluation ce jour.

## 2026-08-28 — E04, configuration centralisée

Écrit `src/edumatch/config.py` : modèles typés, validation au démarrage,
précédence `base.yaml` < `{env}.yaml` < variables d'environnement. 25 tests,
répartis en trois fichiers thématiques.

Trois défauts trouvés en validation et corrigés : une racine de données vide
qui se résolvait silencieusement en répertoire courant ; un objet de
configuration qui pouvait annoncer un environnement différent de son contenu ;
un canal `.env` jamais lu. Le test qui garantit l'absence de valeur en dur a été
réécrit en analyse syntaxique après qu'une mutation a montré qu'un seuil écrit
`4 / 5` lui échappait.

Écrit l'ADR 0003 (configuration centralisée) et l'ADR 0002 (refus de Databricks).
Corrigé la volumétrie Sirene et la licence des référentiels dans le dossier de
certification : l'ONISEP est sous ODbL, pas sous Licence Ouverte.

## 2026-08-26

**Fait** : E03 validée — vérification des 4 sources (Parcoursup, Sirene,
ONISEP, RNCP) par API de métadonnées, sans téléchargement des gros fichiers.
Note `01-donnees/sources.md` et script `scripts/verifier_sources.sh` produits.
Référentiels ONISEP et RNCP documentés pour la première fois. Écart détecté
sur le chiffre Sirene « 11,2 Go » (non reproductible) — corrigé vers 6,44 Go
(ZIP, stock du 01/08/2026), daté, propagé partout où le chiffre figurait.
Licence ONISEP corrigée en ODbL (elle était donnée pour Licence Ouverte).

**Décisions** : aucun ADR. Correction de chiffre arbitrée par mes soins,
actée dans mes notes de cadrage.

**Bloqué sur** : rien. Prochaine étape : E04, configuration centralisée
(`config.py`, Pydantic Settings).

**Jury** : aucune évaluation ce jour.
