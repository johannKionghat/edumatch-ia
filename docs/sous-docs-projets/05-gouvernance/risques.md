# Matrice des risques

**Critère servi** : Bloc 1, 1.5 · **Dernière revue** : 2026-09-15 ·
**Cadence de revue** : à chaque campagne Parcoursup, et à tout changement de
source, de variable ou de modèle.

Structure reprise du cadre NIST AI RMF — gouverner, cartographier, mesurer,
gérer. Chaque risque est **cartographié** (d'où il vient), **mesuré** quand
c'est possible (un chiffre, pas une appréciation), puis **géré** par une
mesure qui pointe vers un fichier ou une procédure existante. Un risque dont
la mesure de réduction ne se traduit ni en code, ni en champ, ni en procédure
datée n'est pas traité : il est seulement décrit.

**Échelles.** Gravité et vraisemblance de 1 (négligeable) à 4 (maximale). La
gravité s'apprécie **pour les personnes concernées**, sauf pour les trois
risques marqués « organisation », qui sont explicitement d'une autre nature et
ne doivent pas être mélangés aux premiers.

---

## Tableau de synthèse

| # | Risque | Nature | G | V | Niveau | Réduit à | Statut |
|---|---|---|:-:|:-:|---|---|---|
| R1 | Violation de données personnelles | Personnes | 3 | **3** | **Élevé** | Faible | **Aggravé le 2026-09-15** : l'écran expose des données sans authentification |
| R2 | Ré-identification par l'agrégat territorial | Personnes | 2 | **4** | **Élevé** | **Faible** | **Traité** — k = 5 et filtre de diffusion appliqués au point de restitution |
| R3 | Discrimination indirecte par variable substitut | Personnes | **4** | 3 | **Élevé** | **Élevé** | **Mesuré sur les prédictions : impact disparate 0,76, sous le seuil légal. Non résolu** |
| R4 | Boucle de rétroaction sur l'orientation | Personnes | **4** | 2 | Élevé | Modéré | Partiellement instrumenté (dérive des prédictions), **non mesuré** |
| R5 | Estimation mal calibrée conduisant au renoncement | Personnes | **4** | **4** | **Élevé** | **Élevé** | **Mesuré, et défavorable** : sur-confiance de six points en test |
| R6 | Contrôle humain de façade (biais d'automatisation) | Personnes | 3 | 3 | Élevé | Modéré | **Dispositif construit ; effectivité non démontrable** |
| R7 | Information erronée sur les débouchés | Personnes | 3 | **4** | **Élevé** | **Faible** | **Tranché** : couverture 1,4 %, terme déclaré indisponible ailleurs |
| R8 | Obsolescence du modèle et des référentiels | Personnes | 3 | **4** | **Élevé** | Modéré | **Surveillance construite** (ADR 0018) ; aveu : le seuil n'aurait pas vu la dégradation mesurée |
| R9 | Non-conformité de réutilisation (licences) | Organisation | 2 | 2 | Modéré | Faible | Tranché dans le registre des sources |
| R10 | Fuite de données dans le protocole d'évaluation | Organisation | **4** | 1 | Modéré | Faible | **Traité et testé** |
| R11 | Secret versionné dans le dépôt | Organisation | **4** | 1 | Modéré | Faible | **Traité et vérifié** |

---

## R1 — Violation de données personnelles

**D'où il vient.** Trois surfaces, et trois seulement : les échantillons
versionnés dans un dépôt public (T2), les journaux d'inférence une fois
construits (T5), et l'infrastructure d'hébergement.

**Ce que la conception a déjà retiré du risque.** L'entraînement ne touche
aucune donnée personnelle, et l'inférence ne conserve rien de la saisie. Il
n'existe **aucune base de dossiers de candidats** : la violation qui ferait le
plus de dégâts dans un système d'orientation classique — l'exfiltration d'une
base de profils — n'a pas d'objet ici. Ce n'est pas une mesure de sécurité,
c'est une propriété d'architecture, et elle vaut mieux qu'une mesure.

**Ce qui reste.** Les 239 lignes d'entrepreneur individuel diffusibles de
`data/samples/` sont publiques par construction — la source l'est déjà. Le
risque résiduel n'est pas la divulgation, c'est l'**impossibilité pratique de
répondre à une opposition** sans réécrire l'historique du dépôt (T2, T8).

**Ce qui s'est aggravé le 2026-09-15.** Une quatrième surface est apparue avec
l'écran conseiller : **il expose les caractéristiques d'un candidat et n'est
protégé par aucune authentification**, l'identifiant du conseiller étant
déclaratif. La vraisemblance passe de 1 à 3 et le risque de modéré à élevé —
non parce que les données ont changé, mais parce qu'une surface d'accès
existe désormais et qu'aucun contrôle ne la garde. C'est le motif de blocage A
de l'analyse d'impact.

**Mesures** : minimisation vérifiée par
`tests/data/test_echantillons_conformite.py` ; **authentification du
conseiller : à construire, bloquante** ; chiffrement au repos et cloisonnement
par rôles à porter par le code d'infrastructure ; procédure de notification de
violation à écrire (72 heures, art. 33) — **non écrite à ce jour**.

---

## R2 — Ré-identification par l'agrégat territorial, et le seuil que je tranche

**D'où il vient.** L'agrégat `commune × NAF` compte les établissements
employeurs par couple (commune, secteur). Une cellule à effectif 1 désigne un
établissement précis ; s'il s'agit d'un entrepreneur individuel, elle désigne
une personne. Sirene est **pseudonymisée, pas anonymisée** (T2, T3).

**La mesure, faite sur l'agrégat réel** (1 929 179 lignes,
`data/processed/sirene/agregats_commune_naf.parquet`) :

| Grain | Cellules non vides | Cellules sous k=3 | Cellules sous k=5 | Établissements perdus si k=5 |
|---|---:|---:|---:|---:|
| **commune × NAF (5 car.)** — grain actuel | 886 688 | 719 651 (81,2 %) | 803 693 (**90,6 %**) | **46,9 %** |
| commune × division NAF (2 car.) | 430 719 | 295 967 (68,7 %) | 351 256 (81,6 %) | 22,9 % |
| **département × NAF (5 car.)** | 52 493 | 12 390 (23,6 %) | 18 361 (**35,0 %**) | **1,6 %** |
| département × division NAF (2 car.) | 7 725 | 426 (5,5 %) | 694 (9,0 %) | 0,1 % |

**Ce que ce tableau démontre, et qui n'était pas évident avant de le
calculer** : appliquer un seuil de k-anonymat **au grain actuel** ne protège
pas, il détruit. Supprimer les cellules sous 5 établissements y ferait perdre
90,6 % des cellules et **près de la moitié des établissements réels** — le
terme « débouchés » n'aurait plus de sens. La suppression n'est donc pas le
bon outil à ce grain : la **généralisation** l'est.

Au grain `département × NAF`, le même seuil de 5 ne coûte que **1,6 % des
établissements** pour 35 % des cellules — c'est-à-dire qu'il ne retire presque
que du vide. C'est le renversement qui décide.

**Décision.**

1. **k = 5**, au grain de restitution, jamais au grain de calcul.
2. **Le grain `commune × NAF` reste un calcul intermédiaire, jamais exposé.**
   Il continue d'exister tel quel : il n'est pas le problème, son exposition
   l'était.
3. **Le grain de restitution est `département × NAF (5 caractères)`**, avec
   suppression — et non lissage — des cellules à moins de 5 établissements
   actifs employeurs. Si une cellule est supprimée, le terme « débouchés » est
   calculé au niveau `département × division NAF`, où 91,0 % des cellules
   passent le seuil ; si celui-ci ne passe pas non plus, **le terme est déclaré
   indisponible plutôt qu'estimé**.
4. **Le filtre `diffusible: true` doit être appliqué** — il est déclaré dans
   `configs/base.yaml` et ne l'est pas, ce qui laisse 20 501 établissements
   (0,84 %) que l'INSEE a exclus de la diffusion entrer dans les comptages.
   Lire `statutDiffusionEtablissement` en dixième colonne est le prix à payer,
   et il est faible.

**Alternatives écartées.**

- *Bruit différentiel sur les comptages* — écartée. La confidentialité
  différentielle apporte une garantie formelle, mais sur des comptages dont la
  médiane est de 1 à 2 établissements par cellule, le bruit nécessaire serait
  du même ordre que le signal : on protégerait une information qu'on aurait
  détruite. Elle redeviendrait pertinente si la restitution portait sur des
  comptages beaucoup plus gros.
- *l-diversité ou t-proximité* — écartées : elles protègent un attribut
  sensible associé à une classe d'équivalence. Ici il n'y a pas d'attribut
  sensible à protéger, seulement un comptage. Le k-anonymat suffit et
  c'est le bon outil.
- *Ne rien faire au motif que Sirene est publique* — écartée. La source est
  publique ; l'agrégat, lui, **crée une information qui n'y était pas**, à
  savoir « ce secteur ne compte qu'un seul employeur dans cette commune ».
  L'inférence est nouvelle même si les données ne le sont pas.

**Ce qui me ferait changer d'avis** : si la restitution devait descendre au
niveau communal pour une raison produit — un lycéen cherchant un emploi dans
sa commune, ce qui est un besoin légitime — alors il faudrait passer au
regroupement par bassin d'emploi plutôt qu'au département, et remesurer le
même tableau à ce grain avant de trancher.

**Statut au 2026-09-15 : implémenté, et vérifié.**
`src/edumatch/matching/agregat_sirene_debouches.py` construit l'agrégat
consommé par le terme de débouchés au grain `département × division NAF`,
applique **k = 5**, et applique le **filtre `diffusible`** que le job
d'agrégation amont n'appliquait pas : **20 488 établissements actifs
employeurs** non diffusibles sont exclus du comptage, sur les 2 423 308
rattachés à une commune — cohérent avec les 20 501 mesurés sur l'ensemble du
stock. Le grain communal reste un calcul intermédiaire jamais exposé, et le
module ne renvoie jamais l'effectif sous le seuil, pas même pour distinguer un
zéro réel d'une cellule supprimée : les deux cas passent par un simple
indicateur d'existence.

Ce que ce traitement **ne change pas** : Sirene reste pseudonymisée, pas
anonymisée. k = 5 réduit le risque de ré-identification, il ne fait pas sortir
la donnée du champ du RGPD.

---

## R3 — Discrimination indirecte par variable substitut

**D'où il vient.** Le genre n'entre jamais dans le modèle — invariant du
projet, vérifié par test. Mais l'exclusion ne suffit pas : une variable
neutre en apparence peut reconstituer l'attribut protégé.

**Mesure faite, et hypothèse infirmée.** Information mutuelle entre variables
candidates et sexe des admis, corrigée du nombre de modalités par permutation
(5 tirages, graine 42) : `cod_uai` 28,9 % · **`fili` 19,5 %** · `ville_etab`
10,2 % · `select_form` 5,6 % · `dep` 2,3 % · `acad_mies` **1,4 %**.

L'hypothèse de départ désignait l'académie comme substitut principal. Elle
arrive **dernière**. Le deuxième substitut est la filière — variable
indispensable, qu'on ne peut pas retirer sans détruire l'objet du système.

**Le paradoxe assumé.** Mesurer l'équité exige de disposer de l'attribut
protégé, alors que la minimisation pousse à ne pas le collecter. La résolution
retenue est la seule qui tienne : le genre est **conservé dans les données
publiques d'audit, jamais collecté auprès du candidat, jamais en entrée du
modèle, et accessible uniquement pour la finalité d'audit**. Les quatre
colonnes concernées sont classées `interdite` dans `configs/base.yaml`.

**Mesures** : dispositif à trois niveaux de l'ADR 0011 — exclusion à l'entrée
(testée), mesure des substituts (à rejouer sur le jeu de variables final),
audit a posteriori sur les prédictions avec ratio d'impact disparate.
`cod_uai` et `ville_etab` sont exclus ; `fili` est conservée, et c'est une
position assumée dont le seuil de réouverture est écrit.

**Le niveau 3 a parlé, le 2026-08-30.** Sur le test 2025, les substituts
totalisent **14,2 % de l'explication SHAP** alors que le genre n'entre jamais
en entrée ; le **ratio d'impact disparate du groupe le plus féminisé est de
0,76, sous le seuil des quatre cinquièmes**, et l'erreur de calibration y est
**le double** de celle des autres groupes (0,0656 contre 0,0319 et 0,0341),
supérieure à celle de la règle de référence (0,0475).

**Et le levier envisagé ne fonctionne pas** : retirer les quatre substituts
coûte +0,0006 de MAE pondérée et **dégrade** le ratio (0,66 → 0,62 en
validation). L'information est diffuse dans les variables décalées, pas
concentrée dans quatre colonnes de catalogue.

**Risque résiduel : élevé, et non résolu.** Aucune mesure disponible dans ce
projet ne le ramène sous le seuil. Ce qui reste ouvert — repondération à
l'apprentissage, contrainte d'équité dans l'objectif, recalibration par groupe
— n'a pas été tenté, et je ne le présente pas comme une solution acquise.

---

## R4 — Boucle de rétroaction sur l'orientation

**D'où il vient.** Un système qui estime faibles les chances d'un profil
décourage ce profil de candidater. Moins de vœux de ce profil, c'est un taux
d'admission observé qui change l'année suivante — et le modèle réapprend sur
des données que ses propres recommandations ont façonnées.

**Pourquoi ce n'est pas théorique ici.** La cible du modèle est *le taux de
propositions rapporté aux vœux*. Le dénominateur, ce sont les vœux : très
exactement la variable que le système influence. Un profil découragé disparaît
du dénominateur, ce qui déplace mécaniquement le taux mesuré l'année suivante.
Les profils les plus exposés sont ceux dont les taux sont déjà les plus bas —
bac professionnel, où **21,6 % des formations n'émettent aucune proposition**.

**Mesures** : suivre, d'une session à l'autre, la distribution des profils
recommandés et non plus seulement la performance du modèle ; conserver la
capacité de comparer les taux observés avant et après mise en service, ce que
les paliers de conservation de T5 rendent possible ; **ne jamais présenter une
estimation basse comme une interdiction** — c'est une exigence d'interface,
pas de modèle.

**Statut au 2026-09-15** : partiellement instrumenté. `models/derive.py`
(ADR 0018) suit la distribution des **prédictions** d'une session à l'autre —
PSI 0,0174 en validation 2024, 0,0296 en test 2025, contre un seuil de 0,20.
C'est l'instrument qui verrait une boucle se refermer. Ce qu'il ne fait pas :
sa référence est la distribution d'entraînement 2020-2023, pas une population
post-déploiement, qui n'existe pas. **Aucun millésime postérieur à une mise en
service n'a été observé** : ce risque restera, à l'échelle de ce projet,
identifié, instrumenté et non mesuré. Je ne prétends pas l'avoir traité.

**Une réduction structurelle mérite d'être notée** : le système **n'apprend
pas en continu**. L'entraînement est une tâche de lot déclenchée sur un
millésime publié ; aucune inférence ne remonte dans le modèle. La boucle ne
peut donc pas se refermer en quelques heures — au pire en une campagne.

---

## R5 — Estimation mal calibrée conduisant au renoncement

**D'où il vient.** Le système annonce une probabilité à un adolescent. Une
estimation à 20 % qui vaut en réalité 45 % peut coûter une candidature — donc
un parcours. La gravité pour la personne est maximale ; c'est le risque le
plus directement lié à la qualité du modèle.

**Ce qui est établi au 2026-09-15**, mesuré à couverture égale sur les 77 159
cellules du test 2025, et rapporté tel quel :

| | Modèle | Règle de référence |
|---|---:|---:|
| MAE pondérée, validation 2024 | **0,0690** | 0,0727 |
| MAE pondérée, test 2025 | 0,0758 | **0,0701** |
| ECE, validation 2024 | **0,0030** | 0,0141 |
| ECE, test 2025 | 0,0371 | **0,0322** |

En validation, le modèle est remarquablement calibré. **En test, il devient
sur-confiant sur toute la plage médiane : il annonce 0,55 quand la réalité
observée est 0,49.** Il reste bien calibré aux extrêmes.

**Pourquoi la vraisemblance passe de 3 à 4.** Elle n'était qu'estimée tant que
la calibration n'était pas mesurée. Elle est désormais **constatée** : le
défaut existe, il est chiffré, et il porte sur la plage de probabilités où un
candidat hésite. Sur-confiance et renoncement sont les deux faces du même
défaut : le candidat à qui l'on annonce 0,55 pour 0,49 candidate sur une
formation moins accessible qu'annoncé et s'expose à un refus qu'il n'avait pas
anticipé.

**Mesures en place** : mention portée par **chaque réponse de l'API**
(`MISE_EN_GARDE_ACCESSIBILITE`) et affichée à l'écran ; facteurs explicatifs
présentés à côté du score ; formulation par catégorie et non par personne.
**Mesure absente** : l'affichage d'un intervalle plutôt que d'un point.

**Exigence bloquante, désormais chiffrée** : aucune restitution chiffrée à un
candidat réel tant que le modèle ne passe pas **sous 0,0701 de MAE pondérée et
sous 0,0322 d'ECE** sur une session de test non consultée pendant le réglage.
Le seuil est écrit avant la prochaine mesure, pas après.

---

## R6 — Contrôle humain de façade

**D'où il vient.** L'article 14 exige un dispositif permettant de comprendre,
superviser et **écarter**. Un écran qui affiche un score sans permettre de le
contredire, ou dont le bouton d'écartement n'est jamais utilisé, satisfait la
lettre et manque l'objet. C'est le biais d'automatisation : un professionnel
suit une recommandation chiffrée parce qu'elle est chiffrée.

**Mesures exigées, et leur état au 2026-09-15** :

| Exigence | État |
|---|---|
| Écartement **motivé**, champ obligatoire | **Fait** — bloqué côté client **et** côté serveur. La double validation empêche qu'un contournement rende le contrôle cosmétique |
| Horodaté et journalisé | **Fait** (`api/feedback_store.py`) |
| Facteurs explicatifs présentés à côté du score | **Fait** |
| Taux d'écartement **mesuré et affiché au déployeur** | **Non fait.** Un taux nul sur une campagne n'est pas un signe de qualité du modèle, c'est un signal d'alerte — encore faut-il pouvoir l'observer |
| Identité du superviseur **vérifiée** | **Non fait** — identifiant déclaratif, aucune authentification. Une trace de supervision non imputable ne démontre rien |

**Risque résiduel** : le dispositif existe et est bien conçu ; **son
effectivité n'est pas démontrable**. C'est exactement la différence entre
satisfaire la lettre de l'article 14 et en atteindre l'objet.

---

## R7 — Information erronée ou absente sur les débouchés

**D'où il vient.** La chaîne de nomenclatures atteint 61,42 % de couverture
d'IDÉO vers NAF (3 605 formations sur 5 869), mais **aucune formation
Parcoursup n'y est raccordée** : aucun millésime ne porte de code RNCP, NSF ou
ROME. Le terme « débouchés » ne peut donc être calculé pour aucune formation
effectivement recommandée. S'y ajoute que la correspondance ROME/NAF s'arrête
à la division (2 chiffres), quand l'agrégat Sirene porte la sous-classe (5
caractères).

**Pourquoi c'est un risque pour la personne et pas seulement un défaut
technique.** Un appariement textuel de libellés non mesuré produirait des
débouchés faux, présentés avec la même assurance que des débouchés justes. Un
lycéen ne peut pas distinguer les deux.

**Les deux seules issues acceptables** : un appariement mesuré, **avec son
taux d'erreur déclaré** ; ou un périmètre restreint, chiffré et assumé, où le
terme n'est calculé que pour les formations réellement raccordées, et déclaré
indisponible ailleurs. Ce qui est exclu : laisser le manque dans un fichier de
couverture sans qu'il apparaisse dans ce qui est montré à l'utilisateur.

**La seconde issue a été prise, et la mesure est sévère.** L'appariement
textuel exact des libellés couvre **7 libellés distincts sur 712 (1,0 %)**,
soit **6 017 lignes sur 440 030 (1,4 %)**, les sept correspondances relues à la
main. **Pour les 98,6 % restants, le terme est explicitement marqué
indisponible avec son motif**, jamais mis à zéro en silence, et le motif voyage
jusqu'à l'écran du conseiller.

**Risque résiduel : faible.** Non parce que la couverture est bonne — elle est
mauvaise — mais parce qu'aucune personne n'est exposée à un chiffre faux. Un
manque déclaré ne nuit à personne ; un chiffre inventé, si. Contrepartie à dire
au déployeur : le troisième terme du score est sans valeur pour la
quasi-totalité du catalogue, et c'est une limite du produit, pas un réglage en
cours.

---

## R8 — Obsolescence du modèle et des référentiels

**D'où il vient.** Quatre échéances datées, toutes vérifiées :

| Source d'obsolescence | Fait mesuré | Échéance |
|---|---|---|
| Cible non stationnaire | Taux agrégé de 40,5 % à 36,7 % entre 2020 et 2025, **pendant que** la moyenne des taux par formation monte de 0,491 à 0,522 | Chaque session |
| Rupture de série boursiers | Part de vœux boursiers de 16,3 % à 13,8 % en 2025 — les cellules `_brs` du test ne décrivent pas la même population que celles de l'entraînement | Déjà réalisée |
| Bascule NAF 2025 | Le répertoire Sirene bascule de nomenclature, la clé de l'agrégat en dépend ; couverture NAF 2025 déjà à 100,0 % dans le stock actuel | **Début 2027** |
| Schéma Parcoursup | 85 colonnes en 2018, 118 en 2025 ; une colonne nouvelle non classée fait échouer la chaîne | Chaque session |

**Le piège que ce risque contient**, et qui vaut d'être énoncé : un
dispositif de surveillance qui suivrait le seul taux agrégé conclurait que les
formations deviennent **plus** sélectives, alors que la moyenne par formation
— la grandeur réellement apprise — évolue en sens inverse. Surveiller la
mauvaise grandeur est pire que ne rien surveiller, parce qu'on croit savoir.

**Mesures, et leur état au 2026-09-15** : réentraînement annuel calé sur la
publication du millésime, porté par le DAG `edumatch_parcoursup` ; **seuil de
dérive arrêté et mesuré** (ADR 0018 : PSI 0,20 appliqué à la **médiane** des 46
variables, jamais au maximum — au maximum il se déclencherait en permanence à
cause de deux variables dont la dérive n'est qu'un changement de libellé à la
source, `region_etab_aff` 0,75 et `select_form` 0,35) ; contrôle de fraîcheur
par source, avec un seuil restant à écrire pour IDÉO, qui ne s'engage sur
aucune cadence.

**L'aveu que ce registre doit porter** : au seuil retenu, **le dispositif
n'aurait pas détecté la dégradation validation → test** mesurée par ailleurs.
Dérive de la cible 0,0115, des prédictions 0,0174 puis 0,0296 : un ordre de
grandeur sous 0,20. C'est cohérent avec la nature du phénomène — une dérive du
concept, où la relation entre variables et cible se déforme sans que les
distributions marginales bougent, est **par construction** invisible au PSI. Le
PSI est un signal précoce sur les entrées et les sorties, **pas un substitut à
la mesure de performance réelle**, qui n'arrive qu'avec la vérité terrain de la
campagne suivante.

---

## R9 — Non-conformité de réutilisation (organisation)

Tranché dans `registre-sources.md` : ODbL sur toute base dérivée
redistribuée ou publiquement exploitée, attribution avec date pour les cinq
jeux sous Licence Ouverte. **Aucune source non commerciale n'est utilisée** —
ce qui aurait été une non-conformité franche pour un projet porté par une
société, même présenté comme académique.

**Reste ouvert** : l'écran d'attribution n'existe pas ; la publication ODbL de
la table dérivée est décidée et non faite.

## R10 — Fuite de données dans le protocole (organisation)

**Traité et prouvé.** Critère de tri fondé sur ce qu'un lycéen connaît au
moment où il formule ses vœux — plus large que « postérieur à la décision » :
`voe_tot` précède l'admission et reste une fuite. Liste blanche de 9 colonnes
sur la session prédite, 35 variables décalées d'une session, 73 exclusions
motivées ; les quatre contrôles de `tests/data/test_variables_reference.py`
ont été vérifiés **par mutation**, pas par relecture.

**Risque résiduel déclaré** : le contrôle porte sur des noms de colonnes, pas
sur leur sémantique. Il empêche l'ajout distrait d'un compteur ; il ne prouve
pas que les 9 colonnes retenues sont réellement publiées avant l'ouverture de
la campagne.

## R11 — Secret versionné (organisation)

**Traité et vérifié.** `.gitignore` exclut `.env`, `*.env`,
`credentials*.json`, `*adminsdk*.json`, `*.pem`, `*.key`, `kubeconfig` ;
`.env.example` liste toutes les variables avec des valeurs factices ; aucune
chaîne ressemblant à un secret dans `src/` ni `configs/`. La politique de
rotation et de révocation est écrite dans `plan-gouvernance.md`.

---

## Ce que cette matrice ne couvre pas

- **Aucune procédure de notification de violation** (art. 33 et 34) n'est
  écrite. C'est une lacune, pas un oubli de rédaction : elle suppose de savoir
  qui héberge quoi, ce que l'infrastructure dira.
- **Aucun journal d'incident** n'existe, alors que l'article 9 du règlement sur
  l'IA suppose un processus de gestion des risques **continu**, donc alimenté
  par les incidents réels.
- **Aucun plan de surveillance après commercialisation** (art. 72). La mesure
  de dérive en serait l'instrument ; elle n'en est pas le plan.
- **Un risque nouveau, non listé ci-dessus parce qu'il relève de la sécurité
  technique et non de ce registre** : l'absence de contrôle d'accès à l'écran
  conseiller. Il est porté par R1, et par le motif de blocage A de l'analyse
  d'impact.

### Ce qui a changé au 2026-09-15

| Risque | Avant | Après |
|---|---|---|
| R2 k-anonymat | Décidé, non implémenté | **Implémenté et vérifié** au point de restitution |
| R5 calibration | Métrique définie, non mesurée | **Mesurée, et défavorable** — vraisemblance relevée de 3 à 4 |
| R6 contrôle humain | Spécifié, non construit | **Construit** ; effectivité non démontrable |
| R3 discrimination indirecte | Mesuré sur les entrées | **Mesuré sur les prédictions** — résiduel relevé de modéré à élevé |
| R7 débouchés | Décision à prendre | **Tranché** — couverture 1,4 %, indisponibilité déclarée |
| R8 obsolescence | Surveillance à construire | **Construite**, avec son aveu de portée |
| R1 violation | Vraisemblance 1 | **Vraisemblance 3** — une surface d'accès non authentifiée est apparue |

**Trois risques restent décidés et non traités** : R3 (aucun levier disponible
ne ramène l'impact disparate sous le seuil), R4 (non mesurable sans millésime
post-déploiement), et le contrôle d'accès porté par R1.

---
*Étape E44 · rédigé le 2026-08-30, révisé le 2026-09-15 après les mesures
d'équité, de calibration, de dérive et la construction du service.*
