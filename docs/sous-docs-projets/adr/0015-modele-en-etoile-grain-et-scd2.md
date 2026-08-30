# ADR 0015 — Modèle en étoile de la couche gold : grain, SCD 2 et moteur

**Date** : 2026-08-30 · **Statut** : accepté · complète l'ADR 0001 (ELT), s'appuie
sur l'ADR 0009 (définition du label) et l'ADR 0012 (six sessions exploitables)

## Contexte

La couche silver (`stg_parcoursup`) est une table unique de **104 274 lignes et
128 colonnes**, une ligne par formation-session, schémas harmonisés sur les huit
millésimes. Elle est réconciliée, typée, mais elle n'est modélisée pour rien : ni
pour l'entraînement, ni pour l'analyse, ni pour la supervision.

L'étape E16 doit produire la couche gold. Trois contraintes commandent le choix :

1. **La cible ne vit pas au grain de silver.** Le label (ADR 0009) est un taux
   par cellule `(formation × session × type de bac × boursier)` : une ligne
   silver se déplie en jusqu'à six cellules.
2. **Les attributs d'une formation changent d'une session à l'autre.** Capacité,
   filière, sélectivité, établissement gérant : une formation n'est pas un objet
   figé sur six millésimes.
3. **La volumétrie est petite.** 440 030 cellules de faits, 43 858 versions de
   formations. Ce n'est pas une échelle qui impose un entrepôt distribué, et
   j'ai décidé de ne pas en faire semblant.

J'ai donc arbitré six questions, chacune ci-dessous avec l'alternative que j'ai
écartée et le seuil qui me ferait revenir dessus.

---

## Décision 1 — Le grain de la table de faits est la cellule

**Retenu** : une ligne de `fait_admission` = une cellule
`(session, cod_aff_form, type_bac, boursier)`, portée après résolution des
dimensions par `(session, sk_formation, sk_profil)`. Grain vérifié unique sur
les 440 030 lignes produites.

**Écarté — le grain formation-session** (celui de silver, une ligne par
`(session, cod_aff_form)`). Il obligerait à porter six couples de mesures par
ligne (`nb_voe_pp_bg`, `prop_tot_bg`, `nb_voe_pp_bg_brs`, …) : les six profils
deviendraient des colonnes et non des lignes. Toute agrégation par type de
baccalauréat s'écrirait alors en énumérant six colonnes à la main, et l'ajout
d'un septième profil serait une migration de schéma. C'est exactement le défaut
que le modèle dimensionnel corrige : ce qui varie en nombre doit être une
dimension, pas une colonne.

**Écarté — la ligne dépliée par genre.** Le fichier source porte aussi des
compteurs ventilés par genre. Les déplier en lignes de faits ferait entrer le
genre dans la table que lit l'entraînement, ce que l'ADR 0011 interdit : le
genre sert exclusivement à l'audit d'équité a posteriori. Le maintenir hors du
grain de `fait_admission` rend l'interdit **structurel** plutôt que
procédural — il n'y a rien à oublier d'exclure, la colonne n'existe pas.

**Le seuil qui ferait reconsidérer** : la publication par le ministère d'une
ventilation supplémentaire du numérateur (par exemple par mention au
baccalauréat) qui deviendrait une dimension d'analyse. Le grain descendrait
alors d'un cran, et `dim_profil_candidat` gagnerait un axe — sans changer la
nature du modèle.

## Décision 2 — Une étoile, ni table plate ni flocon

**Retenu** : une table de faits, quatre dimensions, clés de substitution
entières.

**Écarté — la grande table plate dénormalisée** (les 128 colonnes silver
recopiées sur chaque cellule). C'est tentant : une seule table, aucune jointure,
et l'entraînement lit un seul fichier. Je l'écarte pour trois raisons. D'abord
la redondance : les attributs de formation seraient recopiés jusqu'à six fois
par session. Ensuite l'impossibilité d'historiser proprement — sans dimension
séparée, il n'y a plus d'endroit où dire « cette formation a changé de capacité
en 2023 ». Enfin la lisibilité pour le jury : le critère 2.1 demande une
modélisation logique justifiée, pas un fichier de travail. La table plate reste
disponible, mais comme **produit de la construction des variables** (E19-E20),
en aval de l'étoile et non à sa place.

**Écarté — le flocon** (normaliser `dim_territoire` sous `dim_formation`, et
`dep_lib` / `acad_mies` / `region_etab_aff` en sous-dimensions du département).
Le flocon économise quelques kilo-octets et coûte deux jointures de plus à
chaque requête d'analyse. `dim_territoire` pèse 1 448 lignes : la redondance
d'académie et de région sur ces 1 448 lignes est un non-sujet. J'assume la
redondance, c'est le principe même de l'étoile.

**Le seuil qui ferait reconsidérer** : une dimension descriptive qui deviendrait
elle-même volumineuse et sujette à mises à jour fréquentes — typiquement un
référentiel géographique complet mis à jour indépendamment du catalogue. À ce
moment-là, la maintenir à part et la référencer aurait un sens ; ce n'est pas le
cas de 1 448 couples département-ville figés par session.

## Décision 3 — SCD 2 sur `dim_formation`

**Retenu** : `dim_formation` est une dimension à évolution lente de **type 2**.
Une nouvelle ligne (une nouvelle `sk_formation`) naît dès qu'un des huit
attributs suivis change pour une même `cod_aff_form` : `fili`,
`form_lib_voe_acc`, `fil_lib_voe_acc`, `select_form`, `contrat_etab`, `tri`,
`capa_fin`, `cod_uai`. Les sessions consécutives sans changement sont regroupées
dans une même version, bornée par `session_debut` et `session_fin`.

Résultat mesuré : **43 858 versions pour 16 618 formations distinctes**, soit
2,6 versions par formation en moyenne, 6 au maximum (une par session).

**Écarté — SCD 1** (écraser l'attribut à chaque changement, une ligne par
formation). C'est plus simple et c'est faux ici. Écraser, c'est **réécrire
l'histoire** : la capacité 2025 d'une formation serait attribuée à sa cellule
2020. Comme la capacité est une variable candidate du modèle (ADR 0013), le
modèle apprendrait sur une session passée une valeur qui n'était pas connue à ce
moment-là — une **fuite de données rétrospective**, et l'invariant qui l'interdit
n'est pas négociable dans ce projet.

**Écarté — la dimension figée sur la dernière session** (ne garder que l'état
2025). Même défaut que SCD 1, en pire : toute formation
disparue du catalogue avant 2025 n'aurait plus de ligne de dimension du tout, et
ses cellules de faits deviendraient orphelines.

**Ce que SCD 2 coûte, et que j'assume** : la table de dimension est 2,6 fois
plus grosse que le nombre de formations ; la jointure faits → formation n'est
pas une simple égalité de clé naturelle, elle passe par la résolution
`(session, cod_aff_form) → sk_formation` ; et une requête écrite naïvement sur
`cod_aff_form` sans filtrer la plage de validité multiplierait les lignes. Ce
dernier risque n'est pas laissé au hasard : la construction du fait lève une
erreur si une jointure de dimension fait varier le nombre de lignes, ce qui est
la signature exacte d'une plage de validité qui se recouvre.

**Ce que SCD 2 évite**, et c'est la raison d'être de la décision : la
reconstitution exacte de l'état d'une formation **tel qu'il était à la session
observée**. C'est la condition pour que le split temporel (ADR 0012) ait un sens.

**Le seuil qui ferait reconsidérer** : si aucun des huit attributs suivis
n'entrait dans le modèle ni dans l'écran de supervision, l'historisation
deviendrait un coût sans contrepartie et SCD 1 suffirait. Ce n'est pas le cas :
`capa_fin` et `select_form` sont des variables candidates retenues.

`dim_territoire` reste en **SCD 1** : l'affectation d'un département à une
académie et à une région ne varie pas dans les données observées, historiser une
grandeur qui ne bouge pas n'apporterait rien.

## Décision 4 — Pas de dimension « établissement »

**Écarté** : une `dim_etablissement` séparée, portant `cod_uai`, référencée par
`dim_formation`.

C'était l'idée naturelle — un établissement propose plusieurs formations, la
relation est bien un-à-plusieurs. Je l'ai abandonnée pour une raison précise :
**aucune formation ne change d'établissement gérant d'une session à l'autre dans
les données observées**. Une dimension sans grain propre qui la justifie n'est
donc rien d'autre qu'une colonne de plus dans `dim_formation`, avec une jointure
en supplément. Or la surarchitecture est explicitement sanctionnée : ajouter un
composant qu'aucune contrainte n'exige est une faute, pas une ambition.

`cod_uai` reste donc un attribut de `dim_formation`, suivi en SCD 2 comme les
autres, **et jamais une variable du modèle** (ADR 0011, ADR 0013) : il sert à
l'analyse et à la supervision humaine.

**Le seuil qui ferait reconsidérer** : l'arrivée d'attributs d'établissement
issus d'une autre source — effectifs, statut, coordonnées, agrégats Sirene
rattachés à l'UAI. À ce moment-là l'établissement aurait un grain propre,
alimenté indépendamment du catalogue Parcoursup, et la dimension se justifierait
d'elle-même.

## Décision 5 — DuckDB comme moteur, Parquet comme format d'échange

**Retenu** : les tables gold sont matérialisées en **Parquet** dans
`data/processed/parcoursup/` par le chemin de production, et rejouées dans une
base **DuckDB** locale par dbt pour produire le lignage et exécuter les tests.

**Écarté — PostgreSQL comme entrepôt gold.** L'instance PostgreSQL existe déjà
dans l'environnement local (elle sert les métadonnées d'orchestration et de suivi
d'expériences). Y charger gold aurait été possible. Je l'écarte parce qu'elle
n'apporterait rien ici : la table de faits pèse **3,85 Mo** en Parquet, elle est
reconstruite en totalité à chaque exécution, jamais mise à jour ligne à ligne, et
personne n'y accède en concurrence. Payer un serveur, un schéma à migrer et une
connexion à ouvrir pour un fichier de 3,85 Mo lu en analytique pure, c'est le
contraire d'une décision d'architecture.

**Écarté — un entrepôt distant managé** (BigQuery, Snowflake ou équivalent).
Hors sujet à cette volumétrie, et contraire à la contrainte de souveraineté déjà
arbitrée : les données servent un système qui profile des mineurs.

**Pourquoi Parquet et pas CSV** : typage conservé (les entiers restent entiers,
`2A` et `2B` restent du texte), lecture par colonne, compression. Dès qu'un
fichier est relu par un programme, Parquet est le format par défaut.

**Pourquoi DuckDB en plus de Parquet** : dbt a besoin d'un moteur pour
matérialiser les modèles et exécuter les tests. DuckDB lit et écrit le Parquet
nativement, ne demande aucun serveur, et le fichier de base est régénérable — il
n'est pas versionné. C'est le seul composant qui coûte quelque chose, et il ne
coûte qu'une dépendance Python.

**Le seuil de bascule vers un entrepôt distant** : la couche gold dépassant
quelques dizaines de gigaoctets de travail, **ou** l'apparition d'un accès
concurrent depuis plusieurs services devant lire la même table en même temps,
**ou** un besoin de mise à jour transactionnelle ligne à ligne. Aucun des trois
n'est atteint aujourd'hui, et deux d'entre eux ne sont même pas en vue.

## Décision 6 — 2018 et 2019 : un filtre sur la donnée, une trace dans la dimension

L'ADR 0012 a établi que le numérateur du label n'existe pas avant 2020. Vérifié à
nouveau sur silver : pour 2018 et 2019, `nb_voe_pp_bg` est renseigné (10 697 et
11 577 lignes), mais `prop_tot_bg` ne l'est sur **aucune ligne**. Le numérateur
n'existe pas : aucune cellule n'est calculable.

**Retenu** : la condition d'exploitabilité est écrite sur la donnée
elle-même — dénominateur renseigné et strictement positif, numérateur
renseigné — et **nulle part sur un millésime en dur**. 2018 et 2019 sortent
d'elles-mêmes de `fait_admission`, sans qu'il ait fallu les nommer.

**Écarté — un filtre `session >= 2020` explicite.** Il produirait le même
résultat aujourd'hui et deviendrait faux le jour où le ministère republierait
rétrospectivement ces deux millésimes ventilés, ou le jour où une session future
présenterait la même lacune. Un filtre sur une date est un chiffre magique ; un
filtre sur la disponibilité de la donnée est une règle.

**Retenu également** : les huit sessions restent présentes dans `dim_session`,
avec `label_disponible` à `False` pour 2018 et 2019. Un lecteur du schéma qui
constate que la table de faits ne cite que six sessions trouve la réponse dans la
dimension, au lieu d'avoir à la déduire ou à me la demander.

**Le seuil qui ferait reconsidérer** : aucun changement de code ne serait
nécessaire si la donnée devenait disponible — c'est précisément l'intérêt du
filtre sur la donnée. Les deux sessions entreraient d'elles-mêmes dans les faits,
et `label_disponible` passerait à `True` sans intervention.

---

## Conséquences

- La couche gold compte **cinq tables** : `fait_admission` (440 030 lignes,
  9 colonnes), `dim_formation` (43 858 / 12), `dim_territoire` (1 448 / 6),
  `dim_profil_candidat` (6 / 4), `dim_session` (8 / 2).
- Le grain `(session, sk_formation, sk_profil)` est **unique**, et aucune cellule
  ne porte un taux hors de `[0, 1]` — deux propriétés vérifiées à la construction
  et rejouées comme test dbt.
- L'intégrité référentielle est garantie dans les deux sens : aucune cellule sans
  dimension résolue, et aucune ligne de dimension jamais référencée par un fait,
  parce que faits et dimensions sont construits sur le même sous-ensemble
  exploitable.
- Le label est calculé **une seule fois**, dans la table de faits, avec le
  bornage de l'ADR 0009 et une colonne `taux_depasse_1` qui conserve
  l'information du dépassement brut. Le répliquer dans chaque étape aval aurait
  garanti qu'un jour deux versions de la formule divergent.
- La chaîne complète est verte : `dbt run` puis `dbt test` exécutent
  **26 nœuds, 26 succès**, dont le test de grain singulier ;
  `dbt docs generate` produit le catalogue des 6 nœuds
  (`stg_parcoursup` et les 5 tables gold) ; la suite de tests du dépôt compte
  **260 tests, 260 succès**.
- Coût assumé : le calcul de `dim_formation` parcourt les versions formation par
  formation en Python plutôt qu'en SQL ensembliste. À 16 618 formations c'est
  négligeable ; à un ordre de grandeur de plus, il faudrait le réécrire en
  fonction de fenêtre.

**Reproduit par** : `make gold` (chemin de production) et `make transform-lignage`
(rejeu dbt, tests et lignage), sur `data/interim/parcoursup/silver.parquet`.
Détail de la modélisation logique et physique dans
`docs/sous-docs-projets/02-architecture/modele-etoile.md`.
