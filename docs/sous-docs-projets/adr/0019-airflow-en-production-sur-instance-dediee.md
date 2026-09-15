# ADR 0019 — Airflow en production sur une instance Scaleway dédiée, pas sur le cluster Kapsule

**Date** : 2026-09-15 · **Statut** : proposé

## Contexte

Le critère 3.12 du bloc 3 exige une vidéo du pipeline **en production**, avec une panne
et sa reprise. Sans cette vidéo, le bloc n'est pas validé. Or, à la date de cette décision :

- Le graphe existe et il est testé : `pipelines/edumatch_pipeline.py` définit quatre DAG
  (Parcoursup `@yearly`, Sirene `@monthly`, référentiels `@daily`, purge d'audit
  `@daily`, voir `configs/base.yaml`). La reprise n'est pas confiée à Airflow
  (`retries: 0`). Elle est décidée dans le code, par
  `orchestration/reprise.py` : jusqu'à `tentatives_max: 3` exécutions, avec une
  temporisation de 60 s puis 120 s (`delai_reprise_secondes: 60`,
  `facteur_backoff: 2.0`), et seulement pour une `ErreurTransitoire`. Le blocage qualité
  (`ErreurQualiteBloquante`, définitive) et l'idempotence de l'enchaînement sont prouvés
  par `tests/integration/test_pipeline_enchainement.py`.
- **Airflow n'a jamais tourné dans un vrai Airflow.** Les tests exécutent les fonctions
  de `orchestration/taches.py` sans l'ordonnanceur. Le service `airflow` de
  `docker-compose.yml` démarre en mode `standalone` sur une base SQLite embarquée. Ce mode
  n'exécute qu'une tâche à la fois, et le fichier le déclare lui-même impropre à la
  production.
- Le socle Terraform (dépôt `edumatch-cicd`, dossier `terraform/`) provisionne un cluster
  Kapsule : un pool de 1 à 2 nœuds DEV1-M (3 vCPU, 4 Go), un registre privé et un bucket
  d'artefacts. Les manifestes `k8s/base/` ne déploient **que l'API**. Aucun fichier ne
  déploie Airflow sur le cluster, et `terraform apply` n'a encore jamais été exécuté.
- `ARCHITECTURE_EduMatch.md` promet que « ce qu'on filme à J8 est la même chaîne,
  provisionnée par Terraform ». Filmer Airflow sur le poste de développement
  contredirait cette phrase du dossier. Or une incohérence entre le dossier et le dépôt
  invalide un bloc à elle seule.

J'ai trouvé un défaut en instruisant cette décision, et il vaut quelle que soit l'option
retenue. `configs/prod.yaml` fixe `execution.moteur_volume: cluster`, et le service
`airflow` de `docker-compose.yml` démarre avec `EDUMATCH_ENV=prod`. La tâche
`agreger_sirene` emprunte donc le chemin PySpark (`spark/run_sirene_agregats.py`, mode
`local[*]`). Mais `docker/Dockerfile.airflow` installe le paquet sans l'extra `[spark]`
(`pyproject.toml`), et l'image de base `apache/airflow` n'embarque pas de machine
virtuelle Java. **En l'état, le DAG `edumatch_sirene` échouerait en production** au
moment d'importer `pyspark`. Je ne l'ai pas encore observé : je l'ai déduit en lisant le
code, et c'est la première chose à confirmer au premier lancement.

## Les chiffres qui servent à trancher

Tarifs hors taxes, relevés le 2026-09-15 sur les pages tarifaires publiques de Scaleway :

| Ressource | Prix horaire | Un mois complet |
|---|---:|---:|
| Instance DEV1-M (3 vCPU, 4 Go) | 0,0202 € | ≈ 14,74 € |
| Instance DEV1-L (4 vCPU, 8 Go) | 0,04284 € | ≈ 31,27 € |
| Instance DEV1-XL (4 vCPU, 12 Go) | 0,06508 € | ≈ 47,50 € |
| IPv4 flexible | 0,005 € | ≈ 3,6 € |
| Stockage bloc 5K | 0,000130 € / Go | ≈ 0,095 € / Go |

Empreinte d'Airflow, d'après les sources officielles :

- La documentation Airflow 2.9.3 demande **au moins 4 Go de mémoire** pour faire tourner
  la pile Docker Compose de référence : base de métadonnées, ordonnanceur, serveur web,
  travailleur, déclencheur. Elle recommande 8 Go sur macOS.
- Les valeurs par défaut du chart Helm officiel (version 1.15.0) prévoient
  `executor: CeleryExecutor`, et activent PostgreSQL, Redis, StatsD et le déclencheur.
  **Aucun composant ne porte de `requests` ni de `limits`** : `resources: {}` partout.
  L'ordonnanceur Kubernetes placerait donc ces pods sans connaître leur besoin.
- Le guide de production du même chart écarte sa propre base embarquée : « Embedded
  Postgres lacks stability, monitoring and persistence features that you need for a
  production database. »

Mémoire déjà réservée sur le cluster, d'après les manifestes :

| Charge | `requests` mémoire |
|---|---:|
| API au pic, 6 réplicas × 320 Mi (`hpa.yaml`, `deployment.yaml`) | 1 920 Mi |
| Prometheus, Alertmanager, Grafana (`monitoring/README.md`) | 448 Mi |
| **Total déjà réservé** | **2 368 Mi** |
| Capacité brute du pool au maximum (2 × 4 096 Mi) | 8 192 Mi |

Volume à stocker, mesuré sur le poste de développement : `data/raw/sirene` 4,4 Go,
`data/raw/parcoursup` 82 Mo, `interim` 37 Mo, `processed` 123 Mo, `external` 32 Mo. Soit
environ 4,7 Go de données, auxquels s'ajoutent les images Docker et les fichiers
temporaires de Spark (**à mesurer**).

Deux chiffres restent inconnus et je ne les invente pas :

- **le pic mémoire de la tâche `agreger_sirene` en mode Spark** sur les 43 896 818 lignes
  de `StockEtablissement` ;
- **la mémoire que Kapsule réserve au système sur chaque nœud DEV1-M.**

Les deux sont à mesurer au premier lancement réel.

## Options envisagées

### 1. Airflow sur le cluster Kapsule (chart Helm officiel ou manifestes)

- **Tenue en mémoire** : si j'ajoute les 4 Go minimum de la documentation aux 2 368 Mi
  déjà réservés, j'arrive à 6 464 Mi, soit **79 % de la capacité brute du pool à son
  maximum**. Ce calcul est fait avant la réservation système de chaque nœud et avant le
  pic de la tâche Spark, qui s'exécute *dans* le travailleur. Deux nœuds DEV1-M ne
  suffisent pas. Il faudrait un troisième nœud ou un pool dédié : +0,02 à +0,04 €/h
  selon le type.
- **Mise en œuvre** :
  - Écrire des `requests`/`limits` pour chaque composant, puisque le chart n'en fournit
    aucun.
  - Choisir la base de métadonnées. La base embarquée est écartée par la documentation
    du chart elle-même. Une base PostgreSQL managée Scaleway ajouterait un coût que je
    n'ai pas vérifié.
  - Construire l'image, qui doit porter les DAG.
  - Surtout, résoudre le partage des données entre tâches. Avec l'exécuteur
    `KubernetesExecutor`, chaque tâche tourne dans son propre pod : le pod
    `controler_qualite` devrait relire ce que le pod `ingerer_sirene` vient d'écrire.
    Or le stockage bloc Scaleway ne se monte que sur un seul nœud à la fois (accès
    `ReadWriteOnce`, limite déjà relevée dans `terraform/main.tf`). Pour que plusieurs
    pods voient les mêmes fichiers, il faudrait réécrire toutes les entrées-sorties du
    pipeline vers le stockage objet, ce qui représente plusieurs jours. Avec
    `LocalExecutor`, toutes les tâches restent dans un seul pod accroché à un volume
    `ReadWriteOnce` : cela revient à une machine unique enfermée dans un pod, avec la
    complexité de Kubernetes et sans rien de son intérêt.
- **Charge d'ici le 24 septembre** : plusieurs jours, sur un socle jamais appliqué, pour
  un premier lancement d'Airflow qui aurait lieu *dans* ce socle. C'est le risque le plus
  élevé des trois options.
- **Ce que l'option prouve** : c'est la lecture la plus forte de « en production ».
- **Ce qu'un jury pourrait objecter** : « Pourquoi un cluster élastique pour un traitement
  mensuel ? » La saisonnalité de 1 à 6, qui justifie Kubernetes et le HPA, porte sur les
  requêtes de l'API pendant la campagne de vœux, pas sur le pipeline. Le pipeline tourne
  selon sa cadence (une fois par an, par mois, par jour) et n'a aucun pic concurrent à
  absorber.

### 2. Airflow sur une instance Scaleway dédiée, provisionnée par le même Terraform

- **Coût** :
  - si l'instance tourne en permanence : DEV1-L + IPv4 + 60 Go de stockage bloc ≈ 31,27
    + 3,6 + 5,7 ≈ **40 € HT par mois** ;
  - pour une séance de tournage de 6 heures : ≈ 0,26 + 0,03 + 0,05 ≈ **0,35 €** ;
  - si l'instance reste allumée pendant toute la préparation, du 18 au 29 septembre
    (≈ 288 h) : ≈ **16 €**.
- **Choix du DEV1-L plutôt que du DEV1-M** : 4 Go correspondent exactement au plancher
  documenté pour Airflow seul, sans laisser de place à MLflow ni à la tâche Spark.
  DEV1-XL (12 Go) reste le repli si la mesure du pic Spark l'exige.
- **Mise en œuvre** :
  - un fichier Terraform de plus : instance, IPv4, groupe de sécurité, rattachement au
    réseau privé existant ;
  - un fichier d'initialisation qui installe Docker ;
  - une surcouche Compose qui remplace le mode `standalone` (SQLite, une tâche à la
    fois) par `LocalExecutor` sur le PostgreSQL déjà présent dans la pile ;
  - la correction de l'image Airflow (Java et `[spark]`).

  Ces pièces sont toutes connues, sans mécanisme nouveau à inventer. J'estime le travail
  à un ou deux jours ; c'est une estimation, pas une mesure.
- **Ce que l'option prouve** : une infrastructure provisionnée par du code, chez le
  fournisseur de production, qui télécharge les données réelles depuis leurs sources
  publiques et les traite selon leur cadence réelle. Et c'est la même chaîne que la pile
  locale, ce qui tient la promesse du dossier.
- **Ce qu'un jury pourrait objecter** : « La documentation d'Airflow dit que Docker
  Compose n'est pas conçu pour la production. » Ma réponse est dans la section
  Conséquences.

### 3. Airflow local, filmé, en définissant « production » par les données et la cadence

- **Coût** : nul. **Mise en œuvre** : finir la pile locale déjà en cours.
- **Ce que l'option prouve** : le mécanisme de reprise, le blocage et l'idempotence, sur
  données réelles.
- **Ce qu'un jury pourrait objecter** : « C'est votre ordinateur, pas la production. »
  L'argument sémantique se défend, mais il se retourne contre moi pour deux raisons.
  D'abord, le dossier promet la même chaîne provisionnée par Terraform, donc la vidéo le
  contredirait. Ensuite, les critères 2.3 et 2.10 exigent déjà une infrastructure
  déployée : si la vidéo du pipeline est la seule à se tourner hors du cloud, le jury
  remarquera l'asymétrie et me demandera pourquoi.

## Décision

**Option 2.** En production, Airflow tourne sur une instance Scaleway dédiée de type
**DEV1-L**, provisionnée par le Terraform d'`edumatch-cicd` sur le réseau privé du
cluster. Elle y exécute la pile Compose du dépôt dans une configuration de production :

- l'exécuteur `LocalExecutor` ;
- une base de métadonnées PostgreSQL ;
- une image tirée du registre privé et étiquetée par l'empreinte du commit ;
- aucune interface exposée publiquement.

Les alternatives sont écartées pour les raisons suivantes :

- **Kapsule (option 1)** : 6 464 Mi réservés sur 8 192 Mi bruts avant même le pic de la
  tâche Spark. Le partage de données entre pods de tâches est impossible sur un stockage
  bloc `ReadWriteOnce` sans réécrire les entrées-sorties. Et le risque n'est pas
  compatible avec l'échéance du 24 septembre. Kubernetes reste le bon choix pour l'API,
  dont la charge est élastique, et un mauvais choix pour un traitement périodique
  mono-machine.
- **Local (option 3)** : l'option coûte 0 € mais contredit le dossier et laisse le
  critère 3.12 à la merci d'une lecture stricte de « en production ». L'écart de coût
  avec l'option 2 est de l'ordre de 0,35 € par séance de tournage. Il ne justifie pas ce
  risque.

## Conséquences

- **Deux plans d'exécution, chacun à sa place.** Kapsule sert l'API, dont la charge suit
  la campagne de vœux avec un rapport de 1 à 6. L'instance dédiée exécute le pipeline,
  dont la charge suit la cadence de publication des sources. Le diagramme C4 de niveau 2
  doit montrer les deux, sinon le dossier ne décrirait pas l'infrastructure réelle.
- **Ce que j'assume de « Docker Compose en production ».** La mise en garde de la
  documentation vise le fichier de démarrage rapide : SQLite, mots de passe par défaut,
  interface ouverte. Je n'utilise aucun de ces trois éléments en production :
  - la base de métadonnées est PostgreSQL ;
  - les secrets passent par l'environnement ;
  - l'interface n'est joignable que par un tunnel SSH, et le groupe de sécurité
    n'autorise en entrée que le port 22, depuis ma seule adresse.

  Ce que je ne revendique pas : la haute disponibilité de l'ordonnanceur. Une instance
  arrêtée, c'est une exécution mensuelle retardée, pas un service interrompu pour un
  utilisateur. Aucun conseiller n'attend ce traitement en direct.
- **L'infrastructure reste éphémère**, avec la même règle de coût que le cluster :
  `airflow_active = false` et `terraform apply` après le tournage suppriment l'instance.
  Les données se retéléchargent depuis leurs sources publiques, et c'est justement ce
  que la vidéo montre.
- **Le monitoring du pipeline (critère 3.7) n'est pas traité par cette décision.**
  L'instance n'est pas collectée par le Prometheus du cluster. C'est un point ouvert, à
  arbitrer séparément.
- **La reprise n'est pas visible dans le graphe d'Airflow.** La décision de reprendre est
  prise dans le code, pas par le mécanisme natif d'Airflow. La tâche ne passe donc pas
  par l'état `up_for_retry`. **La vidéo doit ouvrir le journal de la tâche** pour montrer
  « tentative 1/3 … nouvelle tentative dans 60 s ». Sinon, la reprise ne se voit pas à
  l'écran.

## Comment la panne sera montrée dans cet environnement

**1. Panne transitoire : coupure réseau pendant une ingestion.** Je déclenche le DAG
`edumatch_sirene` sur un dossier `raw/sirene` vide. Pendant le téléchargement, que le
journal de progression rend visible, je coupe le trafic sortant des conteneurs depuis
l'hôte :

```bash
sudo iptables -I DOCKER-USER -p tcp --dport 443 -j REJECT --reject-with tcp-reset
```

- **Pourquoi `REJECT` et pas `DROP`.** Avec `DROP`, les paquets disparaissent sans
  réponse : la connexion resterait suspendue jusqu'au délai de lecture du connecteur, soit
  20 minutes (`DELAI_ATTENTE_SECONDES_SIRENE`). Avec `REJECT`, la connexion est
  réinitialisée immédiatement.
- **Pourquoi la chaîne `DOCKER-USER`.** Elle ne filtre que le trafic des conteneurs, donc
  la connexion SSH de tournage n'est pas coupée.
- **Ce qui s'affiche.** Le journal de la tâche montre l'échec transitoire et la
  temporisation de 60 s.
- **Le rétablissement.** Je rétablis le réseau avant la fin de ces 60 s :

  ```bash
  sudo iptables -D DOCKER-USER -p tcp --dport 443 -j REJECT --reject-with tcp-reset
  ```

  La deuxième tentative saute les fichiers déjà intacts, vérifiés contre le manifeste
  SHA-256. Elle retélécharge **depuis le début** le fichier interrompu : le connecteur ne
  reprend pas par plage d'octets, et le fichier `.part` est supprimé. La tâche finit en
  succès.
- **Variante.** Si je laisse la coupure au-delà des trois tentatives, soit 180 s
  cumulées, l'erreur `ErreurRepriseEpuisee` s'affiche, la tâche échoue et les tâches en
  aval passent en `upstream_failed`. Après avoir rétabli le réseau, j'utilise « Clear » :
  la chaîne repart sans retélécharger ce qui est déjà intact.
- **À vérifier en répétition, avant de filmer.** Une réinitialisation en plein flux doit
  lever une sous-classe de `requests.RequestException`, pour être traduite en
  `ErreurReseauSirene` (transitoire). Si ce n'est pas le cas, c'est un défaut du
  connecteur, à corriger, pas à contourner.

**2. Arrêt définitif : contrôle qualité bloquant.** Je rejoue en production le scénario
du test d'intégration `test_panne_qualite_arrete_la_chaine_avant_la_transformation` :

- **Injection.** Un script d'injection contrôlée sauvegarde le millésime Parcoursup le
  plus récent, puis en retire une colonne de la liste blanche.
- **Ce qui s'affiche.** Dans le DAG `edumatch_parcoursup`, `controler_qualite` échoue au
  premier essai, sans aucune reprise. `transformer_silver`, `construire_gold`,
  `construire_variables` et `detecter_derive` passent en `upstream_failed`, et la date de
  modification de `interim/parcoursup/silver.parquet` ne bouge pas.
- **Restauration.** Le script remet le fichier d'origine en place, puis vérifie que son
  SHA-256 est identique au manifeste. La chaîne se relance ensuite jusqu'au bout.
- **Ce que j'annonce à l'écran.** Il s'agit d'une injection volontaire. La modification
  de `raw/` ne dure que la démonstration et elle est vérifiée réversible octet pour
  octet.

**3. Idempotence.** Après une exécution réussie, je relance le même DAG sans rien
changer :

- l'ingestion journalise que chaque fichier est déjà présent et intact, et le manifeste
  est inchangé ;
- un script compare le **contenu** des sorties (`silver.parquet`,
  `fait_admission.parquet`, `variables.parquet`, agrégat Sirene) avant et après
  l'exécution, avec la même égalité de tables que le test d'intégration. Je ne compare
  pas les empreintes binaires : je n'ai pas vérifié qu'un fichier Parquet réécrit reste
  identique octet pour octet.

## Ce qui reste à construire

Dans **`edumatch-cicd`**, une fois terminée la correction en cours sur ce dépôt :

1. `terraform/airflow.tf` :
   - `scaleway_instance_ip.airflow` ;
   - `scaleway_instance_security_group.airflow` : entrée refusée par défaut, TCP 22
     accepté depuis `var.cidr_operateur` seulement, sortie ouverte, `stateful = true` ;
   - `scaleway_instance_server.airflow` : `type = var.type_instance_airflow`, image
     Ubuntu LTS dont le libellé est à confirmer par `scw instance image list`, volume
     racine de `var.taille_volume_airflow_go`, groupe de sécurité, IP, rattachement à
     `scaleway_vpc_private_network.edumatch`, `user_data` d'initialisation.

   Toutes ces ressources portent `count = var.airflow_active ? 1 : 0`.
2. `terraform/cloud-init/airflow.yaml` : installation de Docker Engine et du plugin
   Compose, création du répertoire `/srv/edumatch/data`. **Aucun secret dans ce
   fichier** : les données d'initialisation d'une instance sont lisibles dans ses
   métadonnées. La connexion au registre se fait par SSH, avec la clé lue depuis
   l'environnement.
3. `terraform/variables.tf` :
   - `type_instance_airflow`, par défaut `DEV1-L`, avec le prix relevé en description ;
   - `cidr_operateur`, sans valeur par défaut, donc obligatoire ;
   - `airflow_active`, par défaut `false` ;
   - `taille_volume_airflow_go`, par défaut `60`.
4. `terraform/outputs.tf` : `airflow_ip_publique` et `airflow_commande_tunnel`
   (`ssh -L 8080:127.0.0.1:8080 …`).
5. `.github/workflows/build-images.yml` : construction et publication de l'image
   `edumatch-airflow`, étiquetée par l'empreinte courte du commit, comme `serve` et
   `train`.
6. `README.md` et `terraform/README.md` : la séquence provisionner, déployer, tourner,
   détruire propre à l'instance, et son coût.

Dans **`edumatch-ia`** :

7. `docker/Dockerfile.airflow` :
   - installer une machine virtuelle Java headless compatible avec Spark 3.5 ;
   - installer `.[spark]` avec le fichier de contraintes qu'Airflow publie pour 2.9.3 ;
   - copier `pipelines/` dans le dossier des DAG, pour que l'image embarque ses DAG au
     lieu de les monter depuis l'hôte : le graphe qui tourne en production est alors
     celui du commit étiqueté.
8. `docker-compose.prod.yml`, une surcouche du fichier existant :
   - les services `airflow-init` (`airflow db migrate`, puis création du compte
     administrateur depuis l'environnement), `airflow-scheduler` et `airflow-webserver`,
     avec `AIRFLOW__CORE__EXECUTOR=LocalExecutor` ;
   - une connexion SQLAlchemy vers une base `airflow`, distincte de celle de MLflow ;
   - l'image `${EDUMATCH_AIRFLOW_IMAGE}` plutôt qu'une construction sur place ;
   - `restart: unless-stopped` ;
   - des ports liés à `127.0.0.1` uniquement, sans aucun port PostgreSQL publié ;
   - des données sur `/srv/edumatch/data`.
9. `docker/postgres/init-airflow.sql` : création de la base et de l'utilisateur
   `airflow`.
10. `.env.example` : `AIRFLOW__CORE__FERNET_KEY`, `AIRFLOW__WEBSERVER__SECRET_KEY`, les
    identifiants d'administration d'Airflow et `EDUMATCH_AIRFLOW_IMAGE`, avec des valeurs
    factices.
11. `scripts/demo_panne_qualite.sh` (injection et restauration, avec contrôle SHA-256
    contre le manifeste) et `scripts/verifier_idempotence.py` (comparaison du contenu des
    sorties avant et après).
12. `Makefile` : cibles `demo-panne-qualite`, `demo-restaurer-qualite` et
    `verifier-idempotence`.
13. `README.md` : l'arborescence mise à jour avec ces fichiers.
14. `docs/sous-docs-projets/03-pipeline/orchestration.md` et le guide de tournage : la
    vidéo se tourne sur l'instance, plus en local.

**Mesures à faire au premier lancement, avant de filmer** :

- le pic mémoire de `agreger_sirene` en mode Spark (`docker stats`) : au-delà d'environ
  6 Go, je passe à DEV1-XL ;
- la durée réelle du téléchargement Sirene sur l'instance ;
- la vérification que l'import de `pyspark` échouait bien sans la correction 7, pour
  confirmer le défaut décrit dans le contexte.

## Ce qui ferait reconsidérer

- **Une tâche dont le pic mémoire dépasse 12 Go** (la plus grande instance DEV1), ou la
  fusion des fichiers Sirene déjà identifiée comme seuil par l'ADR 0016 : le calcul
  n'est alors plus mono-machine, et l'agrégat part vers un Spark réellement distribué.
  C'est ce chemin, et non la machine d'orchestration, qui passerait sur un cluster.
- **Une exigence de fraîcheur des données contractuelle et inférieure à la journée**, ou
  plusieurs personnes qui exploitent le pipeline : la haute disponibilité de
  l'ordonnanceur devient alors un besoin, et le chart Helm sur Kubernetes, avec une base
  managée, en est la réponse standard.
- **Un cluster Kapsule qui cesse d'être éphémère** et tourne en permanence avec de la
  marge mesurée : y loger Airflow coûterait alors moins qu'une instance à part, à
  condition que les entrées-sorties aient d'abord migré vers le stockage objet.
