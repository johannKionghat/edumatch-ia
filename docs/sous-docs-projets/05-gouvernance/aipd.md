# Analyse d'impact relative à la protection des données (AIPD)

**Critère servi** : Bloc 1, 1.7 — livrable obligatoire · **Version** : 1.0,
**complète** · **Date** : 2026-09-15 · **Fondement** : RGPD art. 35 ·
**Version précédente** : 0.9 du 2026-08-30, qui portait quatre trous déclarés.

> **Ce qui a changé depuis la version 0.9.** Les quatre sections marquées
> `[À COMPLÉTER]` attendaient des mesures qui n'existaient pas encore :
> l'audit d'équité sur les prédictions, la calibration, l'écran de
> supervision, la journalisation. Les quatre sont produites. Cette version les
> intègre et **tranche l'avis** — §8. Une analyse à trous déclarés valait
> mieux qu'une analyse absente ; elle ne valait pas une analyse mesurée.

**Toute cette analyse apprécie les risques pour les droits et libertés des
personnes concernées — les candidats — et non les risques pour
l'organisation.** Les risques encourus par le projet lui-même (non-conformité
de licence, fuite de données dans le protocole, secret versionné) sont traités
dans `risques.md`, et y sont marqués « Organisation » pour qu'aucune confusion
ne soit possible.

---

## 1. Pourquoi cette analyse est obligatoire

L'article 35 §3 rend l'analyse obligatoire dans trois cas, et les lignes
directrices y ajoutent une liste de critères dont **deux suffisent** à
déclencher l'obligation. Ici, quatre sont réunis :

| Critère | Réalisé ? | Fait |
|---|---|---|
| Évaluation ou notation, y compris le profilage | **Oui** | Le système attribue à un candidat une estimation chiffrée de ses chances d'admission, formation par formation |
| Données concernant des **personnes vulnérables** | **Oui** | Lycéens de terminale, **mineurs** pour une part d'entre eux |
| Usage innovant ou application de nouvelles technologies | **Oui** | Modèle appris, explication par valeurs de Shapley |
| Traitement faisant obstacle à un droit ou à un service | **Partiellement** | Le système n'interdit rien, mais une estimation basse peut conduire une personne à renoncer d'elle-même à une candidature |

**Deux critères auraient suffi. Quatre sont présents.** L'obligation n'est donc
pas discutable, et elle ne dépendrait même pas de la qualification de haut
risque au titre du règlement sur l'IA, qui s'y ajoute par ailleurs
(`ai-act.md`, §1).

## 2. Description systématique du traitement

### 2.1 Finalité

Aider un lycéen de terminale à construire une liste de vœux d'orientation
informée, en lui indiquant pour chaque formation : à quel point elle correspond
à ses intérêts (**affinité**, par règles), quelles sont ses chances d'y être
admis (**accessibilité**, seul terme appris), et quels débouchés d'emploi
existent sur son territoire (**débouchés**, par agrégats).

Le score est **multiplicatif** : si un terme s'annule, la recommandation
disparaît (`src/edumatch/matching/score.py`, vérifié terme par terme par
`tests/unit/test_matching_score.py::test_un_terme_nul_supprime_le_score`). Ce
choix a une conséquence directe sur les personnes : une formation ne peut pas
être recommandée au seul motif qu'elle est accessible.

### 2.2 Ce que le système fait, et ce qu'il ne fait pas

| Il fait | Il ne fait pas |
|---|---|
| Estimer un taux d'admission par **cellule** — formation, session, type de baccalauréat, statut de boursier | Estimer une probabilité individuelle : le modèle n'a jamais vu un dossier de candidat |
| Restituer les facteurs qui portent l'estimation (TreeSHAP, `models/explain.py`) | Prendre une décision d'admission — elle appartient aux établissements, hors de ce système |
| Ordonner des formations selon un score composite | Empêcher une candidature, ni la transmettre à qui que ce soit |

**Cette distinction est la plus importante de l'analyse.** Le modèle apprend sur
des agrégats publics de campagnes passées, non sur des personnes. Il prédit la
propriété d'une cellule, puis on affecte cette propriété à la personne qui
appartient à cette cellule. Le candidat ne reçoit donc pas « une probabilité le
concernant » mais « le taux estimé de la catégorie à laquelle il appartient » —
et l'interface doit le dire dans ces termes, faute de quoi elle promet une
précision individuelle qui n'existe pas.

### 2.3 Flux de données

```
ENTRAÎNEMENT (T1)
  Parcoursup 2020-2025, comptages agrégés par formation
  440 030 cellules, 46 variables -> LightGBM pondéré
  AUCUNE donnée personnelle

INFÉRENCE (T4)
  Saisie du candidat : type de bac, boursier ou non, territoire,
  intérêts déclarés
  -> score par formation + facteurs explicatifs
  DONNÉES PERSONNELLES, MINEURS POSSIBLES, saisie non conservée

TRAÇABILITÉ (T5)             SUPERVISION (T6)
  Journal d'inférence          Conseiller : voir, comprendre, écarter
  12 / 36 mois, purge          avec motif obligatoire, bloqué client
  exécutable et planifiée      ET serveur
```

**Aucune donnée de navigation, aucun historique de consultation, aucun profil
de compte alimenté par l'usage**, ni à l'entraînement ni à l'inférence. Ce
n'est pas une omission de description : c'est une décision de conception, et
c'est ce qui distingue ce système d'un moteur de recommandation ordinaire.

### 2.4 Données traitées à l'inférence

| Collectée | Non collectée, par décision |
|---|---|
| Type de baccalauréat | Nom, prénom, adresse |
| Statut de boursier | Date de naissance exacte |
| Département ou académie | Établissement d'origine (`cod_uai`, exclu — ADR 0013) |
| Intérêts déclarés | **Genre** |
| | Origine, convictions, santé, handicap |
| | Résultats scolaires nominatifs |

**Le statut de boursier n'est pas une donnée sensible** au sens de l'article 9
— cette catégorie couvre l'origine raciale ou ethnique, les opinions
politiques, les convictions, l'appartenance syndicale, les données génétiques
et biométriques, la santé, la vie et l'orientation sexuelles. C'est une donnée
personnelle à forte portée sociale, qui appelle une vigilance particulière sur
la discrimination indirecte, et qui est une **dimension du label lui-même** :
le taux d'admission d'un boursier et d'un non-boursier dans la même formation
n'est pas le même, et masquer cette différence reviendrait à donner à un
boursier une estimation calculée sur une population qui n'est pas la sienne.

### 2.5 Périmètre, destinataires, durées

Détail complet dans `registre-traitements.md`. En résumé : personnes concernées
= lycéens de terminale du territoire du déployeur ; destinataires = le candidat
et le conseiller qui l'accompagne ; hébergement souverain, aucun transfert hors
Union ; durées 12 mois en clair, 36 mois pseudonymisés, puis agrégats, **avec
purge exécutable** (`src/edumatch/api/audit_purge.py`) et **planifiée** (DAG
`edumatch_audit_purge` de `pipelines/edumatch_pipeline.py`, cadence déclarée
par `orchestration.planification.purge_audit` dans `configs/base.yaml`).

## 3. Nécessité et proportionnalité

| Exigence | Appréciation | Preuve |
|---|---|---|
| **Finalité déterminée, explicite, légitime** | Satisfaite | Aide à l'orientation ; aucune finalité secondaire, aucun profilage publicitaire, aucune revente |
| **Base légale** | Satisfaite, choix documenté | Consentement (art. 6.1.a) en usage direct ; mission d'intérêt public (art. 6.1.e) pour un déployeur public ; intérêt légitime (art. 6.1.f) avec mise en balance écrite (ADR 0008) pour les échantillons Sirene |
| **Minimisation** | **Satisfaite et vérifiée par test** | 4 caractéristiques collectées ; 9 colonnes de catalogue lues sur 128 sur la session prédite ; 9 sur 54 pour Sirene ; genre exclu, contrôlé par `tests/data/test_features_build_antifuite.py`, **vérifié par mutation** |
| **Exactitude** | **Mesurée, et le résultat est défavorable au modèle appris** | Voir §3.1. C'est le point qui commande l'avis |
| **Limitation de conservation** | **Décidée, exécutée, planifiée** | `audit_purge.py`, testée et idempotente, appelée par `orchestration/taches.py::purger_audit` avec `simulation=False` explicite. **Exception : T6 n'a pas de purge** |
| **Information** | **Non satisfaite** | Aucune notice destinée au candidat n'existe. L'écran construit (`api/static/index.html`) s'adresse au **conseiller**, pas au candidat |
| **Droits des personnes** | **Non satisfaits** | Aucun dispositif d'exercice ; procédure décrite (T8), délai d'un mois, non outillée |
| **Sous-traitance** | Contrat art. 28 obligatoire avant la mise en service de l'assistant documentaire (T7), seul point où une saisie peut sortir de l'infrastructure | Non conclu |

### 3.1 Le test de nécessité, refait avec les mesures — et il échoue sur le terme appris

La version 0.9 concluait : « la proportionnalité est acquise **sur les
données**, elle ne l'est pas encore **sur les effets** ». Les effets sont
désormais mesurés, et voici ce qu'ils disent.

Le terme d'accessibilité existe en deux versions comparables, sur exactement le
même protocole temporel (entraînement 2020-2023, validation 2024, test 2025 —
ADR 0012) et à couverture égale (100 % des 77 159 cellules de test) :

| | Modèle appris (LightGBM) | Règle de référence (taux de la session précédente) |
|---|---:|---:|
| MAE pondérée, validation 2024 | **0,0690** | 0,0727 |
| MAE pondérée, **test 2025** | 0,0758 | **0,0701** |
| ECE, validation 2024 | **0,0030** | 0,0141 |
| ECE, **test 2025** | 0,0371 | **0,0322** |

Ventilé par sous-population sur le test 2025, le constat ne s'améliore nulle
part de façon décisive : le modèle appris est **battu par la règle de référence
dans les trois types de baccalauréat, dans les deux statuts de boursier, dans
deux des trois groupes de mixité, et dans 16 des 19 territoires mesurés**
(tableau complet dans `model-card.md`, §6).

**Ce que j'en tire, juridiquement, et c'est le cœur de cet avis.** La nécessité,
au sens de l'article 35 §7.b, n'est pas un jugement sur l'utilité générale du
service : c'est la question de savoir si le traitement mis en œuvre est
**nécessaire** pour atteindre la finalité, c'est-à-dire s'il n'existe pas de
moyen moins intrusif qui l'atteigne aussi bien. Ici, un moyen moins intrusif
existe, il est déjà construit (`src/edumatch/models/baseline.py`), il n'apprend
rien, il est intégralement explicable par sa définition, et il fait **mieux**
que le modèle appris sur la session la plus récente, en précision comme en
calibration.

Un modèle appris qui n'apporte rien de mesurable par rapport à une règle de
dénombrement n'est pas un raffinement neutre : il ajoute de l'opacité, une
surface de dérive, une charge de journalisation et un risque de discrimination
indirecte, **pour un résultat inférieur**. Le test de proportionnalité ne
tranche donc pas en sa faveur.

Il ne tranche pas non plus contre le **service** : affinité, restitution des
facteurs, écran de supervision, journalisation et ordonnancement des formations
restent proportionnés et utiles. C'est le seul terme appris qui échoue au test,
et l'avis du §8 en tire la conséquence sans l'étendre au reste.

## 4. Ce que l'architecture retire du risque avant toute mesure

Trois propriétés structurelles, qui valent mieux que des mesures ajoutées après
coup, parce qu'elles ne peuvent pas être désactivées par erreur :

1. **Aucune donnée personnelle à l'entraînement.** Il n'existe pas de base de
   dossiers de candidats à exfiltrer, à réidentifier, ou à réutiliser pour une
   autre finalité. Le scénario de violation le plus grave d'un système
   d'orientation n'a pas d'objet ici.
2. **Aucune conservation de la saisie.** Ce que le candidat entre sert à
   produire la réponse et disparaît. Ce qui est conservé — le journal — l'est au
   titre d'une obligation légale distincte, avec ses propres durées.
3. **Le genre n'est jamais collecté ni utilisé en entrée.** Il n'existe que dans
   les données publiques agrégées, à seule fin d'audit (`models/fairness.py`,
   qui le lit depuis la table silver et jamais depuis les variables du modèle).

## 5. Risques pour les droits et libertés des personnes — les trois risques classiques

| Risque | Impact potentiel sur la personne | Vraisemblance | Mesures | Résiduel |
|---|---|---|---|---|
| **Accès illégitime aux données** | Divulgation du statut de boursier et du projet d'orientation d'un mineur — information à forte portée sociale, susceptible de stigmatisation | **Relevée depuis la v0.9** : l'écran conseiller existe et n'est protégé par **aucune authentification** ; l'identifiant du conseiller est déclaratif | Chiffrement au repos et en transit, cloisonnement par rôles : à porter par le code d'infrastructure, non écrit à ce jour. Purge du journal exécutée et planifiée | **Élevé** tant qu'aucun contrôle d'accès n'est en place — voir §8.4, motif A |
| **Modification non désirée des données** | Une caractéristique altérée produit une estimation fausse, donc un conseil faux, sans que la personne puisse le détecter | Faible | Écriture atomique, empreintes SHA-256, contrôles qualité bloquants (`tests/data/test_quality_run_blocage.py`), idempotence testée | Faible |
| **Disparition de données** | Impossibilité de retracer une recommandation contestée, donc de la contester utilement | **Faible désormais** | Journal d'inférence construit (`api/audit.py`), horodaté, portant version de modèle et empreinte de commit | Faible pour T5 ; **la trace de supervision (T6) ne se corrèle pas au journal d'inférence**, faute d'identifiant commun : une décision de conseiller n'est pas rattachable à l'inférence qui l'a motivée |

## 6. Risques spécifiques au système apprenant

C'est ici que se jouait l'essentiel, et c'est ici que se trouvaient les quatre
trous de la version 0.9. Ils sont comblés par des mesures, pas par des
affirmations.

### 6.1 Discrimination indirecte par variable substitut — **mesurée**

**Le risque pour la personne** : recevoir une estimation systématiquement
différente en raison d'un attribut protégé qui n'a jamais été collecté, et sans
aucun moyen de s'en apercevoir.

**Ce qui était déjà mesuré sur les entrées** : information mutuelle entre
variables candidates et sexe des admis, corrigée du nombre de modalités par
permutation — la **filière reconstitue 19,5 %** du genre, l'établissement
d'origine 28,9 % (exclu), l'académie seulement 1,4 %. La filière est
indispensable au modèle : l'exclusion du genre est **nécessaire mais
insuffisante**.

**Ce qui est mesuré depuis, sur les sorties** (`models/fairness.py`, test 2025,
définition privilégiée = **calibration par groupe**, seuil de décision 0,50,
taux de sélection pondéré par l'effectif de cellule) :

| Dimension | Groupe le plus défavorisé | Ratio d'impact disparate — modèle | — règle de référence | Seuil |
|---|---|---:|---:|---:|
| Genre (mixité des candidats) | plus de 80 % de candidates femmes | **0,76** | 0,63 | 0,80 |
| Type de baccalauréat | bac professionnel | **0,58** | 0,62 | 0,80 |
| Territoire | Mayotte, Île-de-France | **0,25** | 0,25 | 0,80 |
| Statut de boursier | boursier | 0,88 | 0,92 | 0,80 |

Et sur la définition que j'ai retenue — la calibration par groupe :

| Groupe de mixité | ECE modèle | ECE règle de référence |
|---|---:|---:|
| plus de 80 % de candidates femmes | **0,0656** | 0,0475 |
| mixte (20 à 80 %) | 0,0319 | 0,0288 |
| moins de 20 % de candidates femmes | 0,0341 | 0,0416 |

**Trois lectures, et je les rapporte ensemble parce qu'aucune ne rachète les
autres.**

1. **Sur le genre, le modèle sur-annonce les chances d'admission dans les
   formations très féminisées** : son erreur de calibration y est deux fois
   celle des autres groupes, et supérieure à celle de la règle de référence. Sur
   ma propre définition d'équité, **la règle de référence est plus équitable que
   le modèle appris**.
2. **Le ratio d'impact disparate de 0,76 est sous le seuil des quatre
   cinquièmes.** Il faut l'apprécier honnêtement : le modèle y fait **mieux**
   que la règle de référence (0,63). Un critique dira donc que le modèle
   améliore l'équité de sélection. Ma réponse est qu'on ne choisit pas sa
   définition d'équité au cas par cas selon le résultat qu'elle donne : j'ai
   retenu la calibration par groupe **avant** de connaître les chiffres
   (`04-modele/equite.md`), en sachant que le théorème d'impossibilité interdit
   de satisfaire simultanément calibration et parité dès que les taux de base
   diffèrent entre groupes. Sur cette définition déclarée d'avance, le verdict
   est défavorable au modèle appris. **Sous une définition de parité
   démographique, il s'inverserait** — je l'écris plutôt que de le taire.
3. **Les écarts par type de bac et par territoire sont réels mais ne sont pas
   des artefacts du modèle** : la règle de référence, qui n'apprend rien, échoue
   aux mêmes seuils et dans les mêmes proportions (bac professionnel 0,62,
   Mayotte 0,25). Ils décrivent la structure du système d'orientation français,
   pas une décision du modèle. **Une exception mérite d'être signalée** : sur le
   bac professionnel, le modèle dégrade légèrement le ratio (0,58 contre 0,62),
   c'est-à-dire qu'il amplifie faiblement un écart préexistant.

**Ce que l'ablation ajoute, et qui ferme un faux espoir** : retirer les quatre
substituts du genre encore présents (`fili`, `select_form`, `dep`, `acad_mies`,
ensemble 14,2 % de l'explication SHAP) ne coûte presque rien en performance
(+0,0006 de MAE pondérée en validation) **et n'améliore pas l'équité** — le
ratio du groupe le plus féminisé passe de 0,66 à 0,62 en validation. Il se
dégrade. L'information qui permet de reconstituer le genre est diffuse dans les
variables décalées attachées à la formation, pas concentrée dans quatre
colonnes de catalogue.

**Conclusion, à ne pas édulcorer : l'exclusion de variables ne peut pas être le
seul levier d'équité.** C'est une conclusion mesurée, pas une prudence de style.

### 6.2 Renoncement induit par une estimation basse — **la calibration est mesurée, et elle se dégrade**

**Le risque pour la personne** : le plus grave de l'analyse. Un adolescent à qui
l'on annonce 20 % de chances renonce à candidater. Si l'estimation est fausse,
ou seulement mal comprise, le système a fermé une porte qu'aucune décision
humaine n'avait fermée. L'effet est **invisible** : personne ne mesure les
candidatures qui n'ont pas eu lieu.

**Ce que la version 0.9 exigeait** : « sans courbe de calibration ni erreur de
calibration attendue, je m'oppose à toute restitution chiffrée à un candidat ».
La mesure existe (`models/evaluate.py`, 10 tranches,
`reports/figures/e23-calibration.png`) :

- en validation 2024, le modèle est remarquablement bien calibré, ECE 0,0030 ;
- **en test 2025, l'ECE monte à 0,0371, au-dessus de celle de la règle de
  référence (0,0322)**, et le modèle devient **sur-confiant sur toute la plage
  médiane** : il annonce 0,55 quand la réalité observée est 0,49. Il reste bien
  calibré aux extrêmes.

**Six points de sur-annonce au milieu de l'échelle sont exactement l'erreur qui
compte pour ce risque.** Le candidat qui hésite est celui qui lit un chiffre
médian. Lui annoncer 0,55 pour 0,49 ne le fait pas renoncer — cela le fait au
contraire candidater sur une formation moins accessible qu'annoncé, et l'expose
à un refus qu'il n'avait pas anticipé. Sur-confiance et renoncement sont les
deux faces du même défaut de calibration ; la première est mesurée ici, la
seconde reste non observable.

**La réserve de la version 0.9 n'est donc pas levée : elle est confirmée par la
mesure.** Elle change seulement de motif — on ne s'oppose plus à une restitution
dont on ignore la qualité, on s'oppose à une restitution dont on connaît le
défaut.

**Mesures en place** : l'interface énonce que l'estimation porte sur une
catégorie et non sur la personne ; les facteurs explicatifs sont présentés à
côté du score ; la mise en garde sur le modèle voyage avec **chaque réponse de
l'API** (`MISE_EN_GARDE_ACCESSIBILITE`, portée par chaque `ScoreFormation`) et
non seulement dans la documentation. **Mesure absente** : l'affichage d'un
intervalle plutôt que d'un point n'est pas implémenté.

### 6.3 Boucle de rétroaction — **partiellement instrumentée, et je dis jusqu'où**

**Le risque pour la personne** : appartenir à un profil que le système
décourage, donc voir ce profil se raréfier dans les campagnes suivantes, donc
voir le modèle apprendre que ce profil ne candidate pas — et confirmer son
propre biais. Les profils exposés sont les moins favorisés : le bac
professionnel, où **21,6 % des formations n'émettent aucune proposition**.

Ce n'est pas une considération théorique : la cible du modèle est un taux dont
le dénominateur est le nombre de vœux, c'est-à-dire exactement la grandeur que
le système influence.

**Ce qui existe désormais** : `models/derive.py` (ADR 0018) mesure, session par
session, la dérive des variables (médiane de 46), de la cible et **des
prédictions du modèle** — PSI 0,0174 pour la validation 2024, 0,0296 pour le
test 2025, contre un seuil de 0,20. C'est l'instrument qui verrait une boucle de
rétroaction s'installer, puisqu'il suit la distribution des sorties dans le
temps.

**Ce qui n'existe pas, et qu'il faut dire** : la référence de cette mesure est
la distribution d'entraînement 2020-2023, pas une population post-déploiement,
qui n'existe pas. Aucun millésime postérieur à une mise en service n'a été
observé. **À l'échelle de ce projet, ce risque restera identifié, partiellement
instrumenté, et non mesuré.** Le seuil retenu (PSI médian 0,20, ADR 0018) est
par ailleurs vingt fois au-dessus du pire cas observé : il est calibré contre le
bruit d'une session, pas contre une dérive lente de composition — et l'ADR le
reconnaît explicitement en écrivant qu'il n'aurait pas détecté la dégradation
validation → test déjà mesurée.

### 6.4 Contrôle humain de façade — **le dispositif existe, son effectivité n'est pas encore mesurable**

**Le risque pour la personne** : que son dossier soit traité par un conseiller
qui suit l'outil parce que l'outil est chiffré. Un contrôle humain qui n'écarte
jamais rien n'est pas un contrôle.

**Ce qui existe** (`src/edumatch/api/static/`, `routes/ecran.py`,
`routes/feedback.py`, `api/feedback_store.py`) :

| Exigence posée en v0.9 | État |
|---|---|
| Écartement possible | **Oui** |
| Écartement **motivé** — motif obligatoire | **Oui, bloqué côté client ET côté serveur.** La double validation est ce qui empêche un contournement de rendre le contrôle cosmétique |
| Horodaté et journalisé | **Oui** (`feedback_store.py`) |
| Facteurs explicatifs présentés à côté du score | **Oui** |
| L'interface dit ce qu'elle ne sait pas : débouchés indisponibles pour 98,6 % des formations, réserve sur le modèle qui ne bat pas son plancher | **Oui, affiché à l'écran**, pas enfoui dans la documentation |
| Taux d'écartement **mesuré et restitué au déployeur** | **Non — aucun tableau de bord.** Sans lui, un contrôle qui n'écarterait jamais rien resterait invisible à l'échelle de l'organisation |
| Identité du superviseur vérifiée | **Non — identifiant déclaratif, aucune authentification** |

**Deux manques, de nature différente.** L'absence de tableau de bord empêche de
*mesurer* l'effectivité du contrôle : le dispositif est construit, sa vertu
n'est pas démontrable. L'absence d'authentification est plus grave : elle
signifie qu'une trace de supervision n'est imputable à personne, et qu'un écran
exposant des données de candidats est accessible sans contrôle d'accès. Le
premier point est une réserve ; le second est un motif de blocage (§8.4,
motif A).

### 6.5 Information erronée sur les débouchés — **tranché, dans le sens le plus inconfortable**

**Le risque pour la personne** : orienter un choix de vie sur un chiffre de
débouchés faux. La version 0.9 posait : « soit un appariement mesuré avec son
taux d'erreur déclaré, soit un périmètre restreint assumé et le terme déclaré
indisponible ailleurs. **Aucune troisième voie.** »

**La seconde voie a été prise, et la mesure est sévère** : l'appariement textuel
exact des libellés couvre **7 libellés distincts sur 712 (1,0 %)**, soit **6 017
lignes sur 440 030 (1,4 %)**, les sept correspondances ayant été relues à la
main (diplômes d'État très normés, dont la forme ne varie pas d'une source à
l'autre). Pour les **98,6 % restants, le terme est explicitement marqué
indisponible avec son motif** — jamais mis à zéro en silence, jamais deviné, et
le motif voyage jusqu'à l'écran.

**Je considère ce risque comme traité**, non parce que la couverture est bonne —
elle est mauvaise — mais parce que la personne n'est jamais exposée à un chiffre
faux. Un manque déclaré ne nuit à personne ; un chiffre inventé, si. En
contrepartie, la valeur du troisième terme du score est aujourd'hui nulle pour
la quasi-totalité du catalogue, et cela doit être dit au déployeur comme une
limite du produit, pas comme un réglage en cours.

### 6.6 Ré-identification d'un tiers par l'agrégat territorial — **traité**

Risque portant sur une **autre** catégorie de personnes que les candidats : les
entrepreneurs individuels. 65,9 % des cellules non vides de l'agrégat
`commune × NAF` ne comptent qu'un établissement.

**La décision de `risques.md` (R2) est désormais implémentée** dans
`src/edumatch/matching/agregat_sirene_debouches.py` : restitution au grain
`département × NAF` avec **k = 5**, le grain communal restant un calcul
intermédiaire jamais exposé, et le filtre `diffusible` **appliqué** — 20 488
établissements actifs employeurs non diffusibles exclus du comptage. Le module
ne renvoie jamais l'effectif sous le seuil, pas même pour distinguer un zéro
réel d'une cellule supprimée : les deux cas passent par un simple indicateur
d'existence.

Rappel de qualification, qui ne change pas : Sirene est **pseudonymisée, pas
anonymisée**. Retirer les colonnes d'identité ne suffit pas — une jointure sur
le SIREN restitue l'identité, et l'information complémentaire nécessaire est le
fichier public lui-même. La donnée reste une donnée personnelle (art. 4.5) ;
k = 5 est une mesure de réduction du risque, **pas une anonymisation**.

## 7. Les mineurs — ce que l'article 8 impose et ce qui manque

Le public visé est constitué de lycéens de terminale, majoritairement âgés de 17
à 18 ans, avec une minorité de 16 ans. L'âge du consentement numérique est fixé
à **quinze ans** en France : le public est au-dessus du seuil, donc le
consentement parental n'est pas requis **pour ce périmètre**.

Trois conséquences, dont deux ne sont pas satisfaites :

1. **L'information doit être rédigée dans des termes qu'un adolescent
   comprend**, affichée avant la saisie, pas dans un lien de bas de page.
   **Non satisfaite** : le seul écran existant s'adresse au conseiller.
2. **Aucun public de moins de quinze ans** ne doit être servi sans rouvrir cette
   analyse et recueillir le consentement du titulaire de l'autorité parentale.
   Un déploiement en classe de troisième rouvrirait tout le dossier.
   **Contrainte écrite, non outillée** : rien dans le code ne contrôle l'âge,
   parce que la date de naissance n'est pas collectée — ce qui est cohérent avec
   la minimisation, et laisse la contrainte au plan contractuel avec le
   déployeur.
3. **La vigilance sur le champ libre** du motif d'écartement : un conseiller peut
   y consigner une information sur un mineur qui n'a rien à y faire. Un
   avertissement est affiché ; **la purge de ce journal n'existe pas**.

## 8. Avis du délégué à la protection des données

### 8.1 État des quatre motifs de la version 0.9

| Motif de la v0.9 | État au 2026-09-15 | Preuve |
|---|---|---|
| 1. Calibration non mesurée | **Levé en tant que motif d'ignorance** — la mesure existe. Mais elle est défavorable, et fonde un motif de fond différent (§8.4, motif D) | `models/evaluate.py`, `reports/figures/e23-calibration.png` |
| 2. Audit d'équité non réalisé | **Levé** — réalisé sur quatre dimensions, résultats non atténués | `models/fairness.py`, `04-modele/equite.md` |
| 3. Aucun dispositif de contrôle humain | **Levé sur l'existence du dispositif** ; son effectivité reste non mesurable et son accès non authentifié | `api/static/`, `routes/feedback.py` |
| 4. Durées sans purge exécutable | **Levé pour T5**, purge testée, idempotente, planifiée. **Pas pour T6** | `api/audit_purge.py`, DAG `edumatch_audit_purge` |

**Les quatre motifs initiaux sont levés ou transformés.** Je ne les maintiens pas
par principe de précaution : je les remplace par ce que les mesures ont fait
apparaître.

### 8.2 Sur le principe du traitement : **favorable**

L'architecture retire du risque là où il est le plus lourd — aucune donnée
personnelle à l'entraînement, aucune conservation de la saisie, aucune donnée
comportementale. La minimisation n'est pas déclarative : elle est vérifiée par
des tests qui échouent si on la contredit, et ces tests ont été validés par
mutation du code, pas par relecture. Le dispositif d'équité repose sur des
mesures qui ont infirmé plusieurs hypothèses initiales du projet, ce qui vaut
mieux que des mesures qui les auraient confirmées.

### 8.3 Sur la mise en service : **défavorable sur le terme appris, favorable sous réserves sur le reste**

Cet avis se scinde, parce que les mesures ne pointent pas toutes dans la même
direction et qu'un avis global les écraserait.

**(a) Défavorable à la restitution, à des candidats réels, de l'estimation
d'accessibilité produite par le modèle appris.** Motif unique et suffisant : il
échoue au test de nécessité (§3.1). Une règle de dénombrement déjà construite
fait mieux que lui en précision et en calibration sur la session la plus
récente, dans la quasi-totalité des sous-populations, et elle est mieux calibrée
par groupe sur la dimension la plus sensible du projet. Le modèle appris ajoute
de l'opacité et un risque de discrimination indirecte pour un résultat
inférieur. Cela ne se rattrape pas par une mention d'avertissement.

**Ce qui lèverait ce point, écrit avant la prochaine mesure et non après** : un
modèle réentraîné qui passe sous **0,0701** de MAE pondérée **et** sous
**0,0322** d'ECE sur une session de test non consultée pendant le réglage, avec
un ECE du groupe le plus féminisé ramené à l'ordre de grandeur des autres
groupes (0,032).

**(b) Favorable, sous les réserves ci-dessous, au reste du dispositif** :
affinité, ordonnancement, restitution des facteurs par valeurs de Shapley, écran
de supervision, journalisation et purge. Ces composants sont proportionnés,
utiles et documentés.

**(c) Favorable, sans réserve de fond, à l'exploitation en environnement de
démonstration et d'évaluation**, avec des conseillers et sans restitution
directe à des candidats mineurs. C'est le périmètre du projet de certification,
et rien dans cette analyse ne s'y oppose.

### 8.4 Les motifs de blocage encore actifs

Chacun renvoie à la liste opposable de `plan-gouvernance.md` §3 et suffit à lui
seul à bloquer une mise en service auprès de candidats réels.

| # | Motif | Rattachement | Ce qui le lève |
|---|---|---|---|
| **A** | **Aucun contrôle d'accès sur l'écran exposant des données de candidats** ; l'identifiant du conseiller est déclaratif, donc aucune trace de supervision n'est imputable | art. 32 RGPD ; art. 14 du règlement sur l'IA — un contrôle humain non imputable n'est pas démontrable | Authentification du conseiller, identifiant journalisé issu de cette authentification |
| **B** | **Une donnée personnelle conservée sans purge exécutable** : le journal de supervision T6 porte une durée écrite (12 mois) et aucune purge, faute d'identifiant commun avec T5 | art. 5.1.e ; liste opposable | Identifiant de corrélation entre T5 et T6, puis extension de `audit_purge.py` à T6 |
| **C** | **Aucune notice d'information destinée au candidat** — ni en français simple, ni du tout | art. 12, 13 et 14 RGPD ; art. 8 pour la lisibilité par un adolescent | Notice affichée avant la saisie, rédigée pour un lecteur de 17 ans |
| **D** | **Restitution chiffrée d'une probabilité dont le défaut de calibration est connu et mesuré** : sur-annonce de six points sur la plage médiane en test | art. 5.1.d (exactitude) ; §6.2 | Le double seuil de (a) ci-dessus |
| **E** | **Attribution des sources non effective** : la Licence Ouverte v2.0 impose paternité **et date de dernière mise à jour** ; aucun écran ne les porte | art. 2 de la Licence Ouverte v2.0 ; liste opposable « une source est utilisée hors des conditions de sa licence » | Écran « Sources et licences » alimenté par les manifestes d'ingestion, jamais par une liste écrite en dur |

### 8.5 Réserves fermes, non bloquantes

1. **Aucun dispositif d'exercice des droits** (T8) : un formulaire qui n'aboutit
   pas serait une non-conformité ; n'en proposer aucun en est une aussi. Le délai d'un mois
   court dès la première demande.
2. **Aucune procédure de notification de violation** (art. 33 et 34) — elle
   suppose de savoir qui héberge quoi, ce que le code d'infrastructure dira.
3. **Aucun tableau de bord du taux d'écartement** : l'effectivité du contrôle
   humain n'est pas mesurable. Un taux nul sur une campagne est un signal
   d'alerte, pas un succès — encore faut-il pouvoir l'observer.
4. **Aucun contrat de sous-traitance (art. 28)** avec le fournisseur de modèle
   de langage : pas de contrat, pas de mise en service de l'assistant
   documentaire (T7). La brique est secondaire, elle ne justifie aucune
   exception.
5. **Pas d'affichage d'intervalle** : le score est restitué comme un point.
6. **L'ablation de la source Sirene est impossible**, la chaîne de nomenclatures
   ne reliant aucune formation Parcoursup. Ce n'est pas un apport nul mesuré,
   c'est une mesure sans objet — et cela doit être écrit ainsi partout, y
   compris dans la Model Card.

### 8.6 Révision

Obligatoire avant toute mise en service, et à chaque changement substantiel :
nouvelle finalité, nouvelle variable, nouvelle catégorie de personnes
concernées, nouveau modèle mis en service, changement de public visant des
élèves de moins de quinze ans, ou incident.

**Prochaine révision programmée** : à la publication du millésime Parcoursup
suivant, qui apportera la première session de test non encore consultée et
permettra de statuer sur le motif (a).

---
*Étape E41 · version 1.0 du 2026-09-15, remplaçant la version 0.9 du
2026-08-30 · plus aucun trou déclaré ; cinq motifs de blocage et six réserves
opposables.*
