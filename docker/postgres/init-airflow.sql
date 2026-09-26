-- Création de la base de métadonnées d'Airflow et de son rôle applicatif
-- (ADR 0019, point 9 — instance dédiée à l'orchestrateur).
--
-- Exécuté automatiquement, UNE SEULE FOIS, par l'image officielle
-- `postgres:16` au tout premier démarrage sur un volume vierge
-- (`docker-entrypoint-initdb.d/`, voir `docker-compose.prod.yml`). Sur un
-- volume déjà initialisé, ce fichier n'est jamais rejoué : les gardes
-- `IF NOT EXISTS` ci-dessous protègent malgré tout contre un montage
-- accidentel sur un volume qui contiendrait déjà un rôle ou une base du même
-- nom (restauration, migration d'instance).
--
-- Le compte `postgres` (POSTGRES_PASSWORD, docker-compose.prod.yml) reste un
-- compte d'administration générique, jamais celui qu'Airflow utilise pour se
-- connecter : ce script crée un rôle applicatif dédié (`AIRFLOW_DB_USER`,
-- valeur par défaut `airflow`) et sa base (`AIRFLOW_DB_NAME`, valeur par
-- défaut `airflow`), avec le mot de passe applicatif
-- (`AIRFLOW_DB_PASSWORD`) — une base dédiée, distincte de celle qui sert de
-- backend MLflow sur une autre machine (cluster Kapsule).
--
-- Aucun secret en dur : les trois variables sont lues depuis l'environnement
-- du conteneur avec `\getenv`, une commande du client `psql` (pas du serveur
-- PostgreSQL) — ce fichier reste un simple script SQL portable, sans
-- dépendre d'un prétraitement (envsubst, template) qui n'existe pas dans le
-- mécanisme officiel d'initialisation de l'image.
\getenv nom_role AIRFLOW_DB_USER
\getenv mot_de_passe_role AIRFLOW_DB_PASSWORD
\getenv nom_base AIRFLOW_DB_NAME

\if :{?nom_role}
\else
  \warn 'AIRFLOW_DB_USER absent de l''environnement du conteneur postgres : ce script ne peut rien créer.'
  \quit 1
\endif
\if :{?mot_de_passe_role}
\else
  \warn 'AIRFLOW_DB_PASSWORD absent de l''environnement du conteneur postgres : ce script ne peut rien créer.'
  \quit 1
\endif
\if :{?nom_base}
\else
  \warn 'AIRFLOW_DB_NAME absent de l''environnement du conteneur postgres : ce script ne peut rien créer.'
  \quit 1
\endif

-- Création du rôle applicatif, par `\gexec` et non dans un bloc `DO` : `psql` ne
-- substitue jamais ses variables (`:'nom_role'`) à l'intérieur d'une chaîne entre
-- dollars, si bien qu'un bloc `DO $do$ ... :'nom_role' ... $do$` partait tel quel
-- vers PostgreSQL, qui répondait « syntax error at or near ":" ». Constaté le
-- 26 septembre 2026, à la première mise en service réelle de la pile : le rôle
-- n'était pas créé, et `airflow-init` échouait ensuite sur « password
-- authentication failed for user "airflow" ». Même technique que la création de la
-- base ci-dessous, qui fonctionnait déjà.
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'nom_role', :'mot_de_passe_role')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = :'nom_role')
\gexec

-- `CREATE DATABASE` ne supporte pas `IF NOT EXISTS` avant PostgreSQL 18 :
-- le contournement classique est cette requête sur le catalogue, exécutée
-- dans le bloc `psql` (`\gexec`) plutôt que dans un bloc `DO` — `CREATE
-- DATABASE` ne peut pas s'exécuter à l'intérieur d'un bloc transactionnel
-- implicite comme `DO $$ ... $$`.
SELECT format(
    'CREATE DATABASE %I OWNER %I ENCODING ''UTF8'' TEMPLATE template0 LC_COLLATE ''C'' LC_CTYPE ''C''',
    :'nom_base', :'nom_role'
)
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_database WHERE datname = :'nom_base')
\gexec

GRANT ALL PRIVILEGES ON DATABASE :"nom_base" TO :"nom_role";
