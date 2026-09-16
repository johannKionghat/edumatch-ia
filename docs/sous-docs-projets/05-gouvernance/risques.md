# Matrice des risques

**Critère servi** : Bloc 1, 1.5 · **Dernière revue** : 2026-09-15 ·
**Cadence de revue** : à chaque campagne Parcoursup, et à tout changement de
source, de variable ou de modèle.

Structure reprise du cadre NIST AI RMF : gouverner, cartographier, mesurer,
gérer. Chaque risque est cartographié (d'où il vient), mesuré quand c'est
possible (un chiffre, pas une appréciation), puis géré par une mesure qui
pointe vers un fichier ou une procédure existante. Un risque dont la mesure de
réduction ne se traduit ni en code, ni en champ, ni en procédure daté n'est
pas traité, seulement décrit.

**Échelles.** Gravité et vraisemblance de 1 (négligeable) à 4 (maximale). La
gravité s'apprécie pour les personnes concernées, sauf pour les trois risques
marqués « organisation ».

---

## Tableau de synthèse

| # | Risque | Nature | G | V | Niveau | Réduit à | Statut |
|---|---|---|:-:|:-:|---|---|---|
| R1 | Violation de données personnelles | Personnes | 3 | 3 | Élevé | Faible | Aggravé le 2026-09-15 : l'écran expose des données sans authentification |
| R2 | Ré-identification par l'agrégat territorial | Personnes | 2 | 4 | Élevé | Faible | Traité, k = 5 et filtre de diffusion appliqués au point de restitution |
| R3 | Discrimination indirecte par variable substitut | Personnes | 4 | 3 | Élevé | Élevé | Mesuré sur les prédictions : impact disparate 0,76, sous le seuil légal. Non résolu |
| R4 | Boucle de rétroaction sur l'orientation | Personnes | 4 | 2 | Élevé | Modéré | Partiellement instrumenté, non mesuré |
| R5 | Estimation mal calibrée conduisant au renoncement | Personnes | 4 | 4 | Élevé | Élevé | Mesuré, défavorable : sur-confiance de six points en test |
| R6 | Contrôle humain de façade (biais d'automatisation) | Personnes | 3 | 3 | Élevé | Modéré | Dispositif construit, effectivité non démontrable |
| R7 | Information erronée sur les débouchés | Personnes | 3 | 4 | Élevé | Faible | Tranché : couverture 1,4 %, terme déclaré indisponible ailleurs |
| R8 | Obsolescence du modèle et des référentiels | Personnes | 3 | 4 | Élevé | Modéré | Surveillance construite (ADR 0018), le seuil n'aurait pas vu la dégradation mesurée |
| R9 | Non-conformité de réutilisation (licences) | Organisation | 2 | 2 | Modéré | Faible | Tranché dans le registre des sources |
| R10 | Fuite de données dans le protocole d'évaluation | Organisation | 4 | 1 | Modéré | Faible | Traité et testé |
| R11 | Secret versionné dans le dépôt | Organisation | 4 | 1 | Modéré | Faible | Traité et vérifié |

---

## R1, violation de données personnelles

Trois surfaces : les échantillons versionnés dans un dépôt public (T2), les
journaux d'inférence (T5), l'infrastructure d'hébergement. L'entraînement ne
touche aucune donnée personnelle et l'inférence ne conserve rien de la saisie :
il n'existe aucune base de dossiers de candidats, ce qui retire déjà l'essentiel
du risque classique de ce type de système. C'est une propriété d'architecture,
pas une mesure de sécurité.

Les 239 lignes d'entrepreneur individuel diffusibles de `data/samples/` sont
publiques par construction. Le risque résiduel n'est pas la divulgation, c'est
l'impossibilité pratique de répondre à une opposition sans réécrire
l'historique du dépôt (T2, T8).

**Aggravation du 2026-09-15** : une quatrième surface est apparue avec l'écran
conseiller, qui expose les caractéristiques d'un candidat sans authentification
(identifiant déclaratif). La vraisemblance passe de 1 à 3 et le risque de
modéré à élevé, car une surface d'accès existe désormais sans contrôle. Motif
de blocage A de l'analyse d'impact.

**Mesures** : minimisation vérifiée par
`tests/data/test_echantillons_conformite.py`, authentification du conseiller à
construire (bloquante), chiffrement au repos et cloisonnement par rôles à
porter par le code d'infrastructure, procédure de notification de violation à
écrire (72 heures, art. 33), non écrite à ce jour.

---

## R2, ré-identification par l'agrégat territorial

L'agrégat `commune × NAF` compte les établissements employeurs par couple
(commune, secteur). Une cellule à effectif 1 désigne un établissement précis,
et si c'est un entrepreneur individuel, une personne. Sirene est pseudonymisée,
pas anonymisée (T2, T3).

**Mesure sur l'agrégat réel** (1 929 179 lignes) :

| Grain | Cellules non vides | Sous k=5 | Établissements perdus si k=5 |
|---|---:|---:|---:|
| commune × NAF (5 car.), grain actuel | 886 688 | 90,6 % | 46,9 % |
| commune × division NAF (2 car.) | 430 719 | 81,6 % | 22,9 % |
| département × NAF (5 car.) | 52 493 | 35,0 % | 1,6 % |
| département × division NAF (2 car.) | 7 725 | 9,0 % | 0,1 % |

Appliquer un seuil de k-anonymat au grain actuel ne protège pas, il détruit :
90,6 % des cellules et près de la moitié des établissements réels
disparaîtraient. Au grain `département × NAF`, le même seuil ne coûte que
1,6 % des établissements pour 35 % des cellules. C'est ce renversement qui
décide de généraliser plutôt que supprimer au grain fin.

**Décision.** k = 5 au grain de restitution, jamais au grain de calcul. Le
grain `commune × NAF` reste un calcul intermédiaire jamais exposé. Le grain de
restitution est `département × NAF (5 car.)`, avec suppression (non lissage)
des cellules à moins de 5 établissements actifs employeurs ; si la cellule est
supprimée, le terme est recalculé à `département × division NAF` (91,0 % des
cellules passent le seuil), sinon déclaré indisponible plutôt qu'estimé. Le
filtre `diffusible: true`, déclaré dans `configs/base.yaml` mais non appliqué
jusque-là, laissait entrer 20 501 établissements (0,84 %) exclus de la
diffusion par l'INSEE : lire `statutDiffusionEtablissement` en dixième colonne
corrige le point, à faible coût.

**Alternatives écartées** : le bruit différentiel, car sur des comptages dont
la médiane est de 1 à 2 établissements par cellule, le bruit nécessaire
détruirait le signal qu'il protège (pertinent sur des comptages plus gros) ;
la l-diversité et la t-proximité, car elles protègent un attribut sensible
associé à une classe d'équivalence, alors qu'ici il n'y a qu'un comptage ; ne
rien faire au motif que Sirene est publique, car l'agrégat crée une
information nouvelle (« ce secteur ne compte qu'un employeur dans cette
commune »).

**Ce qui me ferait changer d'avis** : un besoin produit légitime de
restitution communale imposerait de passer au bassin d'emploi plutôt qu'au
département, et de remesurer le même tableau avant de trancher.

**Statut au 2026-09-15 : implémenté et vérifié.**
`src/edumatch/matching/agregat_sirene_debouches.py` applique k = 5 et le
filtre `diffusible` (20 488 établissements exclus sur 2 423 308 rattachés à
une commune), le module ne renvoie jamais l'effectif sous le seuil. Sirene
reste pseudonymisée : k = 5 réduit le risque, il ne sort pas la donnée du
champ du RGPD.

---

## R3, discrimination indirecte par variable substitut

Le genre n'entre jamais dans le modèle, invariant vérifié par test, mais une
variable neutre en apparence peut reconstituer l'attribut protégé.

**Mesure** : information mutuelle entre variables candidates et sexe des
admis, corrigée par permutation (5 tirages, graine 42) : `cod_uai` 28,9 %,
`fili` 19,5 %, `ville_etab` 10,2 %, `select_form` 5,6 %, `dep` 2,3 %,
`acad_mies` 1,4 %. L'hypothèse de départ désignait l'académie comme substitut
principal, elle arrive dernière. Le deuxième substitut, `fili`, est une
variable indispensable qu'on ne peut pas retirer sans détruire l'objet du
système.

**Le paradoxe assumé** : mesurer l'équité exige l'attribut protégé, la
minimisation pousse à ne pas le collecter. Résolution : le genre reste dans
les données publiques d'audit, jamais collecté auprès du candidat, jamais en
entrée du modèle, accessible seulement pour l'audit (colonnes classées
`interdite` dans `configs/base.yaml`).

**Dispositif à trois niveaux (ADR 0011)** : exclusion à l'entrée (testée),
mesure des substituts, audit a posteriori sur les prédictions avec ratio
d'impact disparate. `cod_uai` et `ville_etab` sont exclus, `fili` est
conservée, position assumée dont le seuil de réouverture est écrit.

**Le niveau 3 a parlé le 2026-08-30** : sur le test 2025, les substituts
totalisent 14,2 % de l'explication SHAP alors que le genre n'entre jamais en
entrée ; le ratio d'impact disparate du groupe le plus féminisé est de 0,76,
sous le seuil des quatre cinquièmes, et son erreur de calibration est le
double des autres groupes (0,0656 contre 0,0319 et 0,0341), au-dessus de la
règle de référence (0,0475). Retirer les quatre substituts coûte +0,0006 de
MAE pondérée et dégrade le ratio (0,66 → 0,62) : l'information est diffuse
dans les variables décalées, pas concentrée dans quatre colonnes.

**Risque résiduel : élevé, non résolu.** Aucune mesure disponible dans ce
projet ne le ramène sous le seuil. Repondération à l'apprentissage, contrainte
d'équité dans l'objectif, recalibration par groupe restent à essayer, non
tentés.

---

## R4, boucle de rétroaction sur l'orientation

Un système qui estime faibles les chances d'un profil décourage ce profil de
candidater. Moins de vœux de ce profil, c'est un taux d'admission observé qui
change l'année suivante, et le modèle réapprend sur des données que ses
propres recommandations ont façonnées.

La cible est le taux de propositions rapporté aux vœux, et le vœu est
justement la variable que le système influence. Un profil découragé disparaît
du dénominateur, ce qui déplace le taux mesuré l'année suivante. Les profils
les plus exposés sont ceux dont les taux sont déjà les plus bas, le bac
professionnel où 21,6 % des formations n'émettent aucune proposition.

**Mesures** : suivre, d'une session à l'autre, la distribution des profils
recommandés et pas seulement la performance du modèle ; conserver la capacité
de comparer les taux avant et après mise en service (permise par les paliers
de T5) ; ne jamais présenter une estimation basse comme une interdiction.

**Statut au 2026-09-15** : partiellement instrumenté. `models/derive.py`
(ADR 0018) suit la distribution des prédictions d'une session à l'autre, PSI
0,0174 en validation 2024, 0,0296 en test 2025, contre un seuil de 0,20. Sa
référence reste la distribution d'entraînement 2020-2023, pas une population
post-déploiement, qui n'existe pas : ce risque reste identifié, instrumenté et
non mesuré. Réduction structurelle à noter : le système n'apprend pas en
continu, l'entraînement est une tâche de lot sur un millésime publié, la
boucle ne peut pas se refermer en quelques heures.

---

## R5, estimation mal calibrée conduisant au renoncement

Le système annonce une probabilité à un adolescent : une estimation à 20 % qui
vaut en réalité 45 % peut coûter une candidature, donc un parcours. Gravité
maximale pour la personne.

**Mesuré au 2026-09-15**, à couverture égale sur les 77 159 cellules du test
2025 :

| | Modèle | Règle de référence |
|---|---:|---:|
| MAE pondérée, validation 2024 | 0,0690 | 0,0727 |
| MAE pondérée, test 2025 | 0,0758 | 0,0701 |
| ECE, validation 2024 | 0,0030 | 0,0141 |
| ECE, test 2025 | 0,0371 | 0,0322 |

En validation, le modèle est bien calibré. En test, il devient sur-confiant
sur la plage médiane : il annonce 0,55 quand la réalité observée est 0,49. Il
reste bien calibré aux extrêmes.

**La vraisemblance passe de 3 à 4** parce que le défaut, jusque-là seulement
estimé, est désormais constaté sur la plage où un candidat hésite. Le candidat
à qui l'on annonce 0,55 pour 0,49 candidate sur une formation moins accessible
qu'annoncé et s'expose à un refus non anticipé.

**Mesures en place** : mise en garde portée par chaque réponse de l'API
(`MISE_EN_GARDE_ACCESSIBILITE`) et affichée à l'écran, facteurs explicatifs
présentés à côté du score, formulation par catégorie et non par personne.
Manque un intervalle plutôt qu'un point.

**Exigence bloquante, chiffrée** : aucune restitution chiffrée à un candidat
réel tant que le modèle ne passe pas sous 0,0701 de MAE pondérée et 0,0322
d'ECE sur une session de test non consultée pendant le réglage.

---

## R6, contrôle humain de façade

L'article 14 exige un dispositif permettant de comprendre, superviser et
écarter. Un écran qui affiche un score sans permettre de le contredire, ou
dont le bouton d'écartement n'est jamais utilisé, satisfait la lettre et
manque l'objet : c'est le biais d'automatisation.

| Exigence | État au 2026-09-15 |
|---|---|
| Écartement motivé, champ obligatoire | Fait, bloqué côté client et serveur |
| Horodaté et journalisé | Fait (`api/feedback_store.py`) |
| Facteurs explicatifs présentés à côté du score | Fait |
| Taux d'écartement mesuré et affiché au déployeur | Non fait ; un taux nul sur une campagne serait un signal d'alerte, pas un signe de qualité |
| Identité du superviseur vérifiée | Non fait, identifiant déclaratif |

**Risque résiduel** : le dispositif existe et est bien conçu, son effectivité
n'est pas démontrable.

---

## R7, information erronée ou absente sur les débouchés

La chaîne de nomenclatures atteint 61,42 % de couverture d'IDÉO vers NAF
(3 605 formations sur 5 869), mais aucune formation Parcoursup n'y est
raccordée : aucun millésime ne porte de code RNCP, NSF ou ROME. Le terme
« débouchés » ne peut donc être calculé pour aucune formation effectivement
recommandée. La correspondance ROME/NAF s'arrête à la division (2 chiffres),
quand l'agrégat Sirene porte la sous-classe (5 caractères).

Un appariement textuel de libellés non mesuré produirait des débouchés faux,
présentés avec la même assurance que des débouchés justes, qu'un lycéen ne
peut pas distinguer. Deux issues acceptables : un appariement mesuré avec son
taux d'erreur, ou un périmètre restreint et déclaré, où le terme n'est
calculé que pour les formations réellement raccordées.

**La seconde issue a été prise.** L'appariement textuel exact des libellés
couvre 7 libellés distincts sur 712 (1,0 %), soit 6 017 lignes sur 440 030
(1,4 %), les sept correspondances relues à la main. Pour les 98,6 % restants,
le terme est marqué indisponible avec son motif, jamais mis à zéro en
silence, motif qui remonte jusqu'à l'écran du conseiller.

**Risque résiduel : faible.** Pas parce que la couverture est bonne, elle est
mauvaise, mais parce qu'aucune personne n'est exposée à un chiffre faux. À
dire au déployeur : le troisième terme du score est sans valeur pour la
quasi-totalité du catalogue, c'est une limite du produit.

---

## R8, obsolescence du modèle et des référentiels

| Source d'obsolescence | Fait mesuré | Échéance |
|---|---|---|
| Cible non stationnaire | Taux agrégé de 40,5 % à 36,7 % entre 2020 et 2025, pendant que la moyenne des taux par formation monte de 0,491 à 0,522 | Chaque session |
| Rupture de série boursiers | Part de vœux boursiers de 16,3 % à 13,8 % en 2025, les cellules `_brs` du test ne décrivent pas la même population que celles de l'entraînement | Déjà réalisée |
| Bascule NAF 2025 | Le répertoire Sirene bascule de nomenclature, la clé de l'agrégat en dépend ; couverture NAF 2025 déjà à 100,0 % | Début 2027 |
| Schéma Parcoursup | 85 colonnes en 2018, 118 en 2025, une colonne nouvelle non classée fait échouer la chaîne | Chaque session |

Un dispositif de surveillance qui suivrait le seul taux agrégé conclurait que
les formations deviennent plus sélectives, alors que la moyenne par formation,
la grandeur réellement apprise, évolue en sens inverse : surveiller la
mauvaise grandeur est pire que ne rien surveiller.

**Mesures** : réentraînement annuel calé sur la publication du millésime
(DAG `edumatch_parcoursup`), seuil de dérive arrêté (ADR 0018, PSI 0,20
appliqué à la médiane des 46 variables, jamais au maximum, sans quoi il se
déclencherait en permanence à cause de deux variables dont la dérive n'est
qu'un changement de libellé, `region_etab_aff` 0,75 et `select_form` 0,35),
contrôle de fraîcheur par source, seuil restant à écrire pour IDÉO.

**Aveu à porter** : au seuil retenu, le dispositif n'aurait pas détecté la
dégradation validation → test mesurée par ailleurs (dérive de la cible
0,0115, des prédictions 0,0174 puis 0,0296, un ordre de grandeur sous 0,20).
Cohérent avec la nature du phénomène : une dérive du concept, où la relation
entre variables et cible se déforme sans que les distributions marginales
bougent, est invisible au PSI, qui est un signal précoce, pas un substitut à
la mesure de performance réelle.

---

## R9, non-conformité de réutilisation (organisation)

Tranché dans `registre-sources.md` : ODbL sur toute base dérivée redistribuée
ou publiquement exploitée, attribution avec date pour les cinq jeux sous
Licence Ouverte. Aucune source non commerciale n'est utilisée. Reste ouvert :
l'écran d'attribution n'existe pas, la publication ODbL de la table dérivée
est décidée et non faite.

## R10, fuite de données dans le protocole (organisation)

**Traité et prouvé.** Critère de tri fondé sur ce qu'un lycéen connaît au
moment où il formule ses vœux (plus large que « postérieur à la décision » :
`voe_tot` précède l'admission et reste une fuite). Liste blanche de 9 colonnes
sur la session prédite, 35 variables décalées d'une session, 73 exclusions
motivées, les quatre contrôles de `tests/data/test_variables_reference.py`
vérifiés par mutation. Risque résiduel : le contrôle porte sur des noms de
colonnes, pas sur leur sémantique.

## R11, secret versionné (organisation)

**Traité et vérifié.** `.gitignore` exclut `.env`, `credentials*.json`,
`*adminsdk*.json`, `*.pem`, `*.key`, `kubeconfig` ; `.env.example` liste
toutes les variables avec des valeurs factices ; aucune chaîne ressemblant à
un secret dans `src/` ni `configs/`. La politique de rotation et de
révocation est écrite dans `plan-gouvernance.md`.

---

## Ce que cette matrice ne couvre pas

- Aucune procédure de notification de violation (art. 33 et 34) n'est écrite,
  elle suppose de savoir qui héberge quoi.
- Aucun journal d'incident, alors que l'article 9 du règlement sur l'IA
  suppose un processus de gestion des risques continu.
- Aucun plan de surveillance après commercialisation (art. 72) : la mesure de
  dérive en est l'instrument, pas le plan.
- L'absence de contrôle d'accès à l'écran conseiller relève de la sécurité
  technique, portée ici par R1 et par le motif de blocage A de l'AIPD.

### Ce qui a changé au 2026-09-15

| Risque | Avant | Après |
|---|---|---|
| R2 k-anonymat | Décidé, non implémenté | Implémenté et vérifié au point de restitution |
| R5 calibration | Métrique définie, non mesurée | Mesurée, défavorable, vraisemblance relevée de 3 à 4 |
| R6 contrôle humain | Spécifié, non construit | Construit, effectivité non démontrable |
| R3 discrimination indirecte | Mesuré sur les entrées | Mesuré sur les prédictions, résiduel relevé de modéré à élevé |
| R7 débouchés | Décision à prendre | Tranché, couverture 1,4 %, indisponibilité déclarée |
| R8 obsolescence | Surveillance à construire | Construite, avec son aveu de portée |
| R1 violation | Vraisemblance 1 | Vraisemblance 3, surface d'accès non authentifiée apparue |

**Trois risques restent décidés et non traités** : R3 (aucun levier
disponible ne ramène l'impact disparate sous le seuil), R4 (non mesurable
sans millésime post-déploiement), et le contrôle d'accès porté par R1.

---
*Étape E44, rédigé le 2026-08-30, révisé le 2026-09-15 après les mesures
d'équité, de calibration, de dérive et la construction du service.*
