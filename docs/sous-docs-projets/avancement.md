# Avancement : les 46 étapes

Le projet suit un plan d'exécution en 46 étapes ordonnées, une à la fois :
chaque étape n'est considérée validée que si son livrable existe, que son
critère de validation a été vérifié par une commande, et que je saurais
l'expliquer devant le jury sans notes. Le tableau ci-dessous reflète l'état
réel du dépôt à ce jour, pas une intention.

**État : 42 / 46 étapes validées.**

| Étape | Intitulé | État | Date |
|---|---|---|---|
| E01 | Architecture et dépôt local | ✅ validée | 2026-08-24 |
| E02 | Dépôts distants et protection de `main` | ✅ validée | 2026-08-26 |
| E03 | Vérification des sources sur data.gouv | ✅ validée | 2026-08-26 |
| E04 | Configuration centralisée `config.py` | ✅ validée | 2026-08-28 |
| E05 | Connecteur Parcoursup | ✅ validée | 2026-08-28 |
| E06 | Connecteur Sirene | ✅ validée | 2026-08-28 |
| E07 | Connecteur référentiels | ✅ validée | 2026-08-29 |
| E08 | Échantillons versionnés | ✅ validée | 2026-08-29 |
| E09 | EDA — label et distributions | ✅ validée | 2026-08-29 |
| E10 | EDA — écarts et sélectivité | ✅ validée | 2026-08-29 |
| E11 | EDA — équité et substituts | ✅ validée | 2026-08-29 |
| E12 | EDA — stabilité inter-millésimes | ✅ validée | 2026-08-29 |
| E13 | Décision de variables (ADR) | ✅ validée | 2026-08-29 |
| E14 | Contrôles qualité bloquants | ✅ validée | 2026-08-29 |
| E15 | dbt — bronze vers silver | ✅ validée | 2026-08-29 |
| E16 | dbt — modèle en étoile | ✅ validée | 2026-08-30 |
| E17 | Job Spark Sirene | ✅ validée | 2026-08-30 |
| E18 | Table NAF ↔ ROME ↔ formation | ✅ validée | 2026-08-30 |
| E19 | Calcul du label | ✅ validée | 2026-08-30 |
| E20 | Construction des variables | ✅ validée | 2026-08-30 |
| E21 | Baseline | ✅ validée | 2026-08-30 |
| E22 | Entraînement LightGBM | ✅ validée | 2026-08-30 |
| E23 | Évaluation et calibration | ✅ validée | 2026-08-30 |
| E24 | Courbe d'apprentissage | ✅ validée | 2026-08-30 |
| E25 | Explicabilité SHAP | ✅ validée | 2026-08-30 |
| E26 | Audit d'équité | ✅ validée | 2026-08-30 |
| E27 | Ablation | ✅ validée | 2026-08-31 |
| E28 | Score à trois termes | ✅ validée | 2026-09-01 |
| E29 | API | ✅ validée | 2026-09-01 |
| E30 | Journalisation article 12 | ✅ validée | 2026-09-01 |
| E31 | Écran conseiller RGAA | ✅ validée | 2026-09-01 |
| E32 | Assistant RAG réécrit | ✅ validée | 2026-09-01 |
| E33 | DAG Airflow | ✅ validée | 2026-09-01 |
| E34 | Détection de dérive | ✅ validée | 2026-09-01 |
| E35 | Conteneurisation | ✅ validée | 2026-09-16 |
| E36 | CI/CD | 🟡 en cours | 2026-09-15 |
| E37 | Infrastructure Terraform et Kubernetes | ✅ validée | 2026-09-15 |
| E38 | Monitoring et SLO | ✅ validée | 2026-09-15 |
| E39 | Panne provoquée et reprise, filmée | ⬜ à faire | — |
| E40 | Registres traitements et sources | ✅ validée | 2026-09-15 |
| E41 | AIPD | ✅ validée | 2026-09-15 |
| E42 | Model Card | ✅ validée | 2026-09-15 |
| E43 | Correspondance AI Act | ✅ validée | 2026-09-15 |
| E44 | Plan de gouvernance et risques | ✅ validée | 2026-09-15 |
| E45 | Diagrammes C4 et les 3 vidéos | 🟡 en cours | 2026-09-15 |
| E46 | Cohérence dossier ↔ dépôt, slides, répétition | ⬜ à faire | — |

**Précision de dépôt** : les étapes E36, E37 et E38 sont portées par le
second dépôt de CI/CD et d'infrastructure, distinct de celui-ci. C'est la
répartition attendue par le critère qui exige deux dépôts de code distincts.

## Ce qui reste à faire

- **CI/CD (E36)** : les workflows existent mais n'ont pas encore tourné sur
  la forge.
- **Déploiement cloud réel (E37, E38)** : l'infrastructure Terraform et
  Kubernetes et le monitoring sont écrits et testés localement, restent à
  démontrer en conditions de production.
- **Panne provoquée et reprise, filmée (E39)** : la coupure volontaire du
  pipeline et sa reprise automatique n'ont pas encore été jouées ni
  enregistrées.
- **Les trois captures vidéo (E45)** : les diagrammes d'architecture sont
  livrés, les vidéos de l'infrastructure, du pipeline avec panne et de la
  solution en production restent à tourner.
- **Lecteur d'écran (RGAA, E31)** : l'audit d'accessibilité outillé et le
  parcours clavier sont faits et corrigés, mais la section consacrée aux
  lecteurs d'écran (NVDA, VoiceOver) n'a pas encore été déroulée par une
  personne humaine.
- **Relecture finale et répétition (E46)** : la cohérence entre le dossier
  de certification et le dépôt reste à vérifier une dernière fois, avant les
  slides et la répétition orale minutée.

---
*Mise à jour : 2026-09-16.*
