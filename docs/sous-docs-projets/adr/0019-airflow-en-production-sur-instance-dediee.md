# ADR 0019 — Airflow en production sur une instance Scaleway dédiée, pas sur le cluster Kapsule

Statut : accepté (2026-09-15) · amendé le 2026-09-15 (moteur de l'agrégat
Sirene et contenu de l'image Airflow, sans remise en cause du choix de
l'instance dédiée)

## Contexte

Le critère 3.12 exige une vidéo du pipeline en production, avec une panne et
sa reprise. Le graphe existe et est testé : quatre DAG (Parcoursup annuel,
Sirene mensuel, référentiels et purge d'audit quotidiens), la reprise
décidée dans le code (jusqu'à 3 tentatives, 60 s puis 120 s, uniquement pour
une erreur transitoire) et prouvée par test d'intégration. Mais Airflow n'a
jamais tourné dans un vrai Airflow : le service `docker-compose.yml` démarre
en mode `standalone` sur SQLite, que la documentation Airflow elle-même
déclare impropre à la production. Le socle Terraform provisionne un cluster
Kapsule dont les manifestes ne déploient que l'API ; aucun fichier ne
déploie Airflow dessus. Le dossier promet que la vidéo montre « la même
chaîne, provisionnée par Terraform » : filmer sur le poste de développement
contredirait cette phrase, et une incohérence entre dossier et dépôt
invalide un bloc à elle seule.

En instruisant cette décision, j'ai aussi trouvé un défaut valable quelle
que soit l'option retenue : `configs/prod.yaml` fixait le moteur de
l'agrégat Sirene sur Spark, mais l'image Airflow n'embarque ni Java ni
PySpark. Le DAG Sirene aurait échoué en production — déduit en lisant le
code, à confirmer au premier lancement.

## Les chiffres qui servent à trancher

Tarifs Scaleway relevés le 2026-09-15 : instance DEV1-M (3 vCPU, 4 Go)
0,0202 €/h (≈14,74 €/mois), DEV1-L (4 vCPU, 8 Go) 0,04284 €/h
(≈31,27 €/mois), IPv4 flexible 0,005 €/h, stockage bloc 0,000130 €/Go. La
documentation Airflow 2.9.3 demande au moins 4 Go de mémoire pour sa pile
Compose de référence. Sur le cluster Kapsule, la mémoire déjà réservée (API
au pic + monitoring) atteint 2 368 Mi sur une capacité brute de 8 192 Mi ; y
ajouter les 4 Go d'Airflow porte le total à 6 464 Mi, 79 % de la capacité
brute, avant même le pic de la tâche Spark. Deux chiffres restent inconnus
et je ne les invente pas : le pic mémoire réel de l'agrégation Sirene, et la
mémoire que Kapsule réserve au système sur chaque nœud — à mesurer au
premier lancement.

## Décision

En production, Airflow tourne sur une instance Scaleway dédiée de type
DEV1-L, provisionnée par le même Terraform, sur le réseau privé du cluster :
exécuteur `LocalExecutor`, base de métadonnées PostgreSQL, image tirée du
registre privé et étiquetée par l'empreinte du commit, aucune interface
exposée publiquement (accès par tunnel SSH). Coût : environ 40 €/mois si
l'instance tourne en permanence, environ 0,35 € pour une séance de tournage
de 6 heures.

## Alternatives écartées

- Airflow sur le cluster Kapsule (chart Helm ou manifestes) : 79 % de la
  capacité brute du pool réservée avant même le pic Spark, et le partage de
  données entre pods de tâches est impossible sur un stockage bloc
  `ReadWriteOnce` sans réécrire toutes les entrées-sorties vers le stockage
  objet — plusieurs jours de travail sur un socle jamais appliqué,
  incompatible avec l'échéance du 24 septembre. Kubernetes reste le bon
  choix pour l'API, dont la charge est élastique (rapport de 1 à 6 pendant
  la campagne), pas pour un traitement périodique mono-machine.
- Airflow local, filmé, en redéfinissant « production » par les données et
  la cadence : coût nul mais contredit la promesse du dossier, et laisse le
  critère 3.12 à la merci d'une lecture stricte de « en production » —
  l'écart de coût avec l'instance dédiée (0,35 € par séance) ne justifie
  pas ce risque.

## Conséquences

Deux plans d'exécution, chacun à sa place : Kapsule sert l'API dont la
charge suit la campagne de vœux, l'instance dédiée exécute le pipeline dont
la charge suit la cadence de publication des sources — le C4 de niveau 2
doit montrer les deux. Ce que j'assume de « Docker Compose en production » :
la mise en garde de la documentation vise le démarrage rapide (SQLite, mots
de passe par défaut, interface ouverte), aucun des trois n'est présent ici.
Ce que je ne revendique pas : la haute disponibilité de l'ordonnanceur — une
instance arrêtée retarde une exécution mensuelle, ça n'interrompt aucun
service pour un utilisateur. L'infrastructure reste éphémère, détruite après
le tournage. Le monitoring du pipeline (critère 3.7) n'est pas couvert par
cette décision, c'est un point ouvert. La reprise n'étant pas gérée par le
mécanisme natif d'Airflow, la vidéo doit ouvrir le journal de la tâche pour
la montrer.

La panne se filme en trois temps : une coupure réseau pendant l'ingestion
Sirene (`iptables REJECT` sur le trafic sortant des conteneurs, rétabli
avant la fin des 60 s de temporisation, deuxième tentative qui retélécharge
depuis le début le fichier interrompu) ; un contrôle qualité bloquant
(retrait contrôlé d'une colonne de la liste blanche sur le dernier
millésime, les tâches en aval passent en `upstream_failed`, restauration
vérifiée par SHA-256) ; une vérification d'idempotence (relance du même DAG,
comparaison du contenu des sorties avant et après).

Je reviendrais sur ce choix si une tâche dépassait 12 Go de pic mémoire ou
si les fichiers Sirene devaient fusionner (seuil déjà posé par l'ADR 0016) —
l'agrégat partirait alors vers un Spark réellement distribué, pas la
machine d'orchestration. Je reviendrais aussi sur ce choix si une exigence
de fraîcheur inférieure à la journée apparaissait, ou si plusieurs personnes
devaient exploiter le pipeline en parallèle.

## Amendement du 2026-09-15 — l'agrégat Sirene tourne en Polars en production

En construisant l'image Airflow avec un environnement Java et l'extra
`[spark]`, comme prescrit initialement, j'ai confirmé le défaut déduit dans
le contexte : l'image de base ne contient ni Java ni PySpark. Mais la
correction elle-même casse Airflow : le paquet du projet exige
`sqlalchemy>=2.0`, alors qu'Airflow 2.9.3 est construit pour SQLAlchemy 1.4 —
avec le fichier de contraintes d'Airflow, l'installation est impossible ;
sans lui, `airflow dags list` échoue sur un modèle interne écrit pour
SQLAlchemy 1.4. Le paquet du projet et Airflow ne peuvent pas partager le
même environnement Python — je ne l'avais pas vérifié avant d'écrire la
recommandation initiale.

Je corrige donc `configs/prod.yaml` : le moteur de l'agrégat Sirene passe de
`cluster` à `local` (Polars) en production. L'image Airflow n'embarque ni
Java ni `[spark]`, mais ajoute `libgomp1` (sans quoi `import lightgbm`
échoue), et embarque directement ses DAG et sa configuration plutôt que de
les monter depuis l'hôte. Vérifié sur l'image, sans aucun montage : elle
tourne sous l'utilisateur `airflow`, `import lightgbm` réussit, les quatre
DAG s'affichent sans erreur d'import.

Ce n'est pas un recul : l'ADR 0016 concluait déjà que Polars reste le
chemin de production réel tant que le calcul tient sur un nœud (18,2 s
contre 87,0 s pour Spark, résultat identique) ; `configs/prod.yaml`
contredisait cette conclusion sans que personne ne l'ait relevé. Le critère
2.4 reste prouvé : le job Spark est écrit, testé, sélectionnable par
configuration — ce que je revendique, c'est la capacité de basculer, pas une
exécution permanente. La décision de fond (instance dédiée, pas Kapsule) ne
change pas : sans JVM ni exécuteurs Spark, la marge mémoire de l'instance
augmente plutôt qu'elle ne diminue.

J'ai écarté une autre voie, isoler PySpark dans un environnement Python
séparé via `ExternalPythonOperator` : elle impose de réécrire la tâche
d'agrégation et de maintenir deux jeux de dépendances pour un moteur que le
volume actuel ne demande pas. Elle redevient la bonne réponse le jour où le
seuil de l'ADR 0016 est franchi.
