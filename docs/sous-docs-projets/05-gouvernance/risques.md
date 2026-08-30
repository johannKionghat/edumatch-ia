# Matrice des risques

**Critère servi** : Bloc 1, 1.5 · **Dernière revue** : 2026-08-30 ·
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
| R1 | Violation de données personnelles | Personnes | 3 | 1 | Modéré | Faible | Partiellement traité |
| R2 | Ré-identification par l'agrégat territorial | Personnes | 2 | **4** | **Élevé** | Faible | **Décision prise ici, non implémentée** |
| R3 | Discrimination indirecte par variable substitut | Personnes | **4** | 3 | **Élevé** | Modéré | Mesuré, dispositif à trois niveaux |
| R4 | Boucle de rétroaction sur l'orientation | Personnes | **4** | 2 | Élevé | Modéré | Identifié, surveillance à construire |
| R5 | Estimation mal calibrée conduisant au renoncement | Personnes | **4** | 3 | **Élevé** | Modéré | Métrique définie, non mesurée |
| R6 | Contrôle humain de façade (biais d'automatisation) | Personnes | 3 | 3 | Élevé | Modéré | Spécifié, non construit |
| R7 | Information erronée sur les débouchés | Personnes | 3 | **4** | **Élevé** | Faible | Chaîne rompue, décision à prendre |
| R8 | Obsolescence du modèle et des référentiels | Personnes | 3 | **4** | **Élevé** | Modéré | Dérive mesurée, surveillance à construire |
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

**Mesures** : minimisation vérifiée par
`tests/data/test_echantillons_conformite.py` ; chiffrement au repos et
cloisonnement par rôles à porter par le code d'infrastructure ; procédure de
notification de violation à écrire (72 heures, art. 33) — **non écrite à ce
jour**.

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

**Statut : décidé, non implémenté.** Ce point bloque l'exposition du terme
« débouchés ». Je le dis comme tel : en l'état, il n'est pas conforme de
publier cet agrégat.

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

**Risque résiduel** : réel. Le modèle reconstituera partiellement le genre par
la filière, quoi qu'il arrive. Seul le niveau 3 dira de combien.

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

**Statut** : identifié et documenté, aucune surveillance construite. C'est le
risque le plus difficile à mesurer du registre, et je ne prétends pas
l'avoir traité.

---

## R5 — Estimation mal calibrée conduisant au renoncement

**D'où il vient.** Le système annonce une probabilité à un adolescent. Une
estimation à 20 % qui vaut en réalité 45 % peut coûter une candidature — donc
un parcours. La gravité pour la personne est maximale ; c'est le risque le
plus directement lié à la qualité du modèle.

**Ce qui est établi.** La première exécution enregistrée du modèle appris
affiche une erreur absolue moyenne pondérée de 0,0820, **quand la règle
naïve de référence atteint 0,0713** : à cet instant, le modèle appris est
moins bon que la baseline qu'il doit battre. La conduite est écrite d'avance :
la comparaison est rapportée telle quelle. Retoucher le protocole jusqu'à ce
que le chiffre passe est la seule conduite exclue.

**Mesures** : erreur absolue moyenne pondérée par l'effectif de cellule, plus
**courbe de calibration et erreur de calibration attendue** — la métrique qui
compte le plus quand on annonce une probabilité, et celle qui manque encore ;
affichage d'un intervalle plutôt que d'un point ; mention explicite que
l'estimation porte sur une cellule et non sur une personne.

**Exigence bloquante** : aucune mise en service sans mesure de calibration
publiée dans la Model Card, ventilée par type de baccalauréat.

---

## R6 — Contrôle humain de façade

**D'où il vient.** L'article 14 exige un dispositif permettant de comprendre,
superviser et **écarter**. Un écran qui affiche un score sans permettre de le
contredire, ou dont le bouton d'écartement n'est jamais utilisé, satisfait la
lettre et manque l'objet. C'est le biais d'automatisation : un professionnel
suit une recommandation chiffrée parce qu'elle est chiffrée.

**Mesures exigées, et vérifiables** : l'écartement doit être **motivé**
(champ obligatoire), **horodaté** et **journalisé** ; le taux d'écartement
doit être **mesuré et affiché au déployeur** — un taux nul sur une année n'est
pas un signe de qualité du modèle, c'est un signal d'alerte sur la supervision ;
les facteurs explicatifs doivent être présentés **avant** le score, pour que le
raisonnement précède le chiffre.

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
indisponible ailleurs. Ce qui est exclu : laisser le manque dans un fichier
de couverture sans qu'il apparaisse dans ce qui est montré à l'utilisateur.

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

**Mesures** : réentraînement annuel calé sur la publication du millésime ;
seuil de dérive documenté ; contrôle de fraîcheur par source, avec un seuil à
écrire pour IDÉO qui ne s'engage sur aucune cadence.

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
- **Trois risques sont décidés et non implémentés** : R2 (seuil de
  k-anonymat), R5 (calibration), R6 (écran de supervision). Ils conditionnent
  la mise en service, et sont repris à ce titre dans l'analyse d'impact.

---
*Étape E44 · rédigé le 2026-08-30.*
