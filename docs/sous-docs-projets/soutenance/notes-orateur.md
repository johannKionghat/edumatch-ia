# Notes orateur — soutenance EduMatch-IA

15 minutes de présentation. Minutage indicatif par slide, total 15:00. À
ajuster à l'usage sans dépasser l'enveloppe — mieux vaut couper une phrase
que déborder.

---

## Slide 1 — Titre (0:20)

Je présente EduMatch-IA, un moteur de matching explicable entre candidats
et formations, construit pour la certification Architecte en Intelligence
Artificielle.

---

## Slide 2 — Le problème et le cas d'usage (0:50)

Un lycéen construit sa liste de vœux Parcoursup sans indicateur chiffré de
ses chances réelles d'admission. Le système que j'ai construit assiste un
conseiller d'orientation dans cet accompagnement — il ne remplace jamais
son jugement. Le public visé est majoritairement mineur, ce qui a
structuré toutes les décisions de conception dès le départ : c'est pour
cette raison que j'ai conduit une analyse d'impact obligatoire avant
toute mise en service.

---

## Slide 3 — Le score à trois termes (1:00)

Le score est un produit de trois termes : affinité, accessibilité,
débouchés. Étant multiplicatif, si un terme est nul, la recommandation
disparaît — une formation inaccessible n'est jamais recommandée au seul
motif qu'elle correspond aux goûts du candidat. Un seul de ces trois
termes demande un modèle appris : l'accessibilité, calculée sur les
données Parcoursup. Les deux autres sont des règles et des dénombrements.
C'est une décision d'architecture : je n'ajoute de l'apprentissage que là
où rien de plus simple n'atteint l'objectif.

---

## Slide 4 — Les données (1:00)

Cinq sources publiques, toutes mesurées et non estimées. Parcoursup pour
les campagnes d'admission, Sirene pour les débouchés territoriaux, ONISEP
et RNCP pour les référentiels de formation, et une table France Travail
pour relier les métiers aux codes d'activité. Un point de vigilance :
ONISEP est sous licence ODbL, qui impose un partage à l'identique en cas
de redistribution — différente des trois autres sources en Licence
Ouverte. Chaque chiffre de ce tableau se reproduit par un script que
j'exécute et que le jury peut rejouer.

---

## Slide 5 — L'architecture (1:00)

J'ai retenu une architecture ELT plutôt qu'ETL : je conserve toujours la
donnée brute et je peux retransformer sans retélécharger. Les données
traversent trois couches — bronze, silver, gold — jusqu'à un entrepôt en
étoile construit avec dbt. Le grain retenu est la cellule formation ×
session × type de bac × statut de boursier, ce qui donne 440 030 lignes
de faits, avec vingt-six modèles dbt tous vérifiés.

---

## Slide 6 — Le volume : Polars contre Spark (1:00)

Sur le fichier Sirene complet, 44 millions de lignes, j'ai mesuré deux
moteurs sur les mêmes règles métier : Polars traite le fichier en 18
secondes, Spark local en 87 secondes, soit 4,8 fois plus lent. Je garde
Polars en exécution courante. Mais j'ai quand même implémenté et testé
Spark, parce que j'ai écrit à l'avance le seuil qui ferait basculer ce
choix : la fusion de plusieurs fichiers Sirene, ou un calcul qui ne
tiendrait plus en mémoire sur un poste de développement.

---

## Slide 7 — La qualité et le pipeline (0:50)

Les contrôles qualité sont bloquants, pas seulement informatifs. Je l'ai
démontré, pas seulement affirmé : en relançant les contrôles sur les
données réelles, la chaîne s'arrête avec un code d'erreur, parce que cinq
établissements Sirene portent une date de création manifestement fausse
— l'année 5015, par exemple. À l'inverse, dix mille immatriculations
anticipées mais plausibles ne produisent qu'un avertissement. Cette
distinction entre bloquant et avertissement a été calibrée sur la donnée
réelle, pas décidée à l'aveugle.

---

## Slide 8 — Le modèle : le résultat tel qu'il est (1:30)

C'est le résultat le plus important de cette soutenance, et je le
présente sans l'atténuer. J'ai construit une baseline sans aucun
apprentissage : le taux d'admission de la même cellule l'année
précédente. Le modèle LightGBM bat cette baseline en validation 2024,
sur les deux métriques. Mais sur le test 2025 — la session la plus
récente, jamais vue pendant le réglage — c'est la baseline qui gagne, en
précision comme en calibration. Un modèle appris qui perd contre une
règle de dénombrement sur la donnée la plus actuelle, c'est un résultat
défavorable, et je le rapporte intégralement plutôt que de le reléguer
en annexe.

---

## Slide 9 — Pourquoi : dérive temporelle (1:00)

J'ai voulu savoir si ce résultat venait d'un manque de données ou d'autre
chose. Deux mesures indépendantes convergent vers la même réponse : ce
n'est pas un manque de volume. La courbe d'apprentissage montre que le
gain marginal se réduit déjà fortement avec plus de données. Et la cible
elle-même n'est pas stable dans le temps — le taux moyen d'admission par
formation monte jusqu'en 2024 puis redescend en 2025. Le modèle a
correctement appris la période 2020-2023 ; ce qui change en 2025, il ne
pouvait pas le voir.

---

## Slide 10 — Explicabilité (1:00)

J'utilise TreeSHAP pour produire des valeurs de Shapley exactes, pas
approximées, ce que permet un modèle à arbres. J'ai vérifié
l'axiome d'efficacité — la somme des contributions doit reconstituer
exactement la prédiction — à une précision de dix puissance moins quinze
sur le modèle réel. La variable la plus importante est, sans surprise,
le taux observé l'année précédente. Ces explications sont précalculées
pour les 440 000 cellules en huit minutes : l'API ne recalcule jamais
SHAP à la demande, elle lit un résultat déjà produit.

---

## Slide 11 — Équité (1:15)

Le genre n'entre jamais dans le modèle — c'est vérifié par un test qui
survivrait uniquement si on le réintroduisait par erreur. Mais des
variables comme la filière reconstituent une partie du genre : 14 % de
l'explication du modèle est portée par ces substituts. Et sur les
formations très féminisées, le ratio d'impact disparate du modèle est de
0,76, sous le seuil légal des quatre cinquièmes — même s'il améliore la
baseline. J'ai retenu la calibration par groupe comme définition
d'équité, avant de connaître ce résultat : sur cette définition, le
modèle sur-annonce les chances d'admission dans ce groupe, plus que la
baseline. Et j'ai testé l'hypothèse la plus naturelle — retirer les
substituts du genre — elle ne répare rien, elle dégrade même légèrement
l'équité. L'exclusion de variables ne peut pas être le seul levier.

---

## Slide 12 — La gouvernance : un avis scindé (1:15)

J'ai rédigé une analyse d'impact complète, une Model Card, et la
correspondance avec le règlement sur l'intelligence artificielle. L'avis
que j'y rends sur mon propre système se scinde en deux, parce que les
mesures ne vont pas toutes dans le même sens. Il est défavorable à la
restitution de l'estimation du modèle appris à de vrais candidats,
puisqu'une règle plus simple, déjà construite, fait mieux sur la donnée
la plus récente. Il reste favorable au reste du dispositif — l'écran de
supervision, la traçabilité, la purge des journaux. Et il est
pleinement favorable à l'usage que je fais du système aujourd'hui, en
démonstration, sans restitution à de vrais mineurs. J'ai aussi documenté
cinq motifs de blocage qui devront être levés avant toute mise en
service réelle.

---

## Slide 13 — Le service (1:00)

Le système est servi par une API avec six routes, et un écran destiné au
conseiller. Ce qui compte le plus sur cet écran : écarter une
recommandation exige un motif, et ce contrôle est vérifié à la fois côté
navigateur et côté serveur — un conseiller ne peut pas contourner
l'obligation de justifier son choix. Chaque inférence est journalisée
conformément à l'article 12, avec une purge programmée que j'ai testée
et démontrée idempotente.

---

## Slide 14 — L'industrialisation (1:00)

Les conteneurs d'entraînement, de service et d'orchestration sont
construits. Deux dépôts de code distincts existent, comme l'exige la
certification. La chaîne d'intégration continue, le déploiement
Kubernetes, l'infrastructure Terraform et le monitoring en production
sont en cours de construction à la date de cette présentation — je ne
prétends pas qu'ils tournent déjà en production tant que je ne peux pas
le démontrer devant vous.

---

## Slide 15 — Limites assumées et prochaine étape (1:00)

Je conclus par ce que je ne cache pas. Le modèle appris ne bat pas
encore sa propre baseline sur la donnée la plus récente : je ne le
déploierais pas aujourd'hui devant de vrais candidats. Le terme
débouchés ne couvre qu'une fraction infime du catalogue, faute
d'identifiant commun entre Parcoursup et les référentiels métiers.
J'ai écrit, avant toute nouvelle mesure, le seuil précis qui me ferait
changer d'avis sur le modèle : passer sous les deux erreurs de la
baseline sur une session encore jamais vue, avec un écart de
calibration refermé sur le groupe le plus touché.

---

## Total : 15:00

