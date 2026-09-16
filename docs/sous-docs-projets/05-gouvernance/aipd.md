# Analyse d'impact relative à la protection des données (AIPD)

**Critère servi** : Bloc 1, 1.7, livrable obligatoire · **Version** : 1.0,
complète · **Date** : 2026-09-15 · **Fondement** : RGPD art. 35 ·
**Version précédente** : 0.9 du 2026-08-30, qui laissait quatre points en
attente.

Depuis la version 0.9, quatre mesures qui manquaient ont été produites :
l'audit d'équité sur les prédictions, la calibration, l'écran de supervision,
la journalisation. Cette version les intègre et rend un avis tranché en §8.

Cette analyse porte sur les risques pour les droits et libertés des
candidats. Les risques pour le projet lui-même (licence non conforme, fuite
de données dans le protocole, secret versionné) sont dans `risques.md`,
marqués « Organisation ».

---

## 1. Pourquoi cette analyse est obligatoire

| Critère | Réalisé ? | Fait |
|---|---|---|
| Évaluation ou notation, y compris profilage | Oui | Estimation chiffrée des chances d'admission, formation par formation |
| Données de personnes vulnérables | Oui | Lycéens de terminale, mineurs pour une part |
| Usage innovant ou nouvelles technologies | Oui | Modèle appris, explication par valeurs de Shapley |
| Traitement faisant obstacle à un droit ou service | Partiellement | N'interdit rien, mais une estimation basse peut conduire à renoncer de soi-même à une candidature |

Deux critères auraient suffi à déclencher l'obligation, quatre sont réunis.

## 2. Description du traitement

**Finalité.** Aider un lycéen de terminale à construire une liste de vœux
informée : à quel point une formation correspond à ses intérêts (affinité,
par règles), ses chances d'y être admis (accessibilité, seul terme appris),
les débouchés d'emploi sur son territoire (débouchés, par agrégats). Le score
est multiplicatif : si un terme s'annule, la recommandation disparaît
(`src/edumatch/matching/score.py`, testé).

**Ce que le système fait, et ne fait pas**

| Il fait | Il ne fait pas |
|---|---|
| Estimer un taux d'admission par cellule (formation, session, type de bac, boursier) | Estimer une probabilité individuelle : le modèle n'a jamais vu de dossier de candidat |
| Restituer les facteurs de l'estimation (TreeSHAP) | Prendre une décision d'admission, qui appartient aux établissements |
| Ordonner des formations selon un score composite | Empêcher une candidature ou la transmettre à quiconque |

Le modèle apprend sur des agrégats publics de campagnes passées, pas sur des
personnes : il prédit la propriété d'une cellule, affectée ensuite à la
personne qui en relève. Le candidat reçoit « le taux estimé de sa
catégorie », pas « sa probabilité », et l'interface doit le dire ainsi.

**Flux de données**

```
ENTRAÎNEMENT (T1)
  Parcoursup 2020-2025, comptages agrégés par formation
  440 030 cellules, 46 variables -> LightGBM pondéré
  aucune donnée personnelle

INFÉRENCE (T4)
  Saisie du candidat : type de bac, boursier ou non, territoire,
  intérêts déclarés
  -> score par formation + facteurs explicatifs
  données personnelles, mineurs possibles, saisie non conservée

TRAÇABILITÉ (T5)             SUPERVISION (T6)
  Journal d'inférence          Conseiller : voir, comprendre, écarter
  12 / 36 mois, purge          avec motif obligatoire, bloqué client
  exécutable et planifiée      et serveur
```

Aucune donnée de navigation, d'historique de consultation, ni de profil
alimenté par l'usage, ni à l'entraînement ni à l'inférence.

**Données traitées à l'inférence**

| Collectée | Non collectée, par décision |
|---|---|
| Type de baccalauréat | Nom, prénom, adresse, date de naissance exacte |
| Statut de boursier | Établissement d'origine (`cod_uai`, exclu, ADR 0013) |
| Département ou académie | Genre |
| Intérêts déclarés | Origine, convictions, santé, handicap, résultats scolaires nominatifs |

Le statut de boursier n'est pas une donnée sensible au sens de l'article 9
(qui couvre origine ethnique, opinions politiques, convictions, appartenance
syndicale, données génétiques et biométriques, santé, vie et orientation
sexuelles). C'est une donnée à forte portée sociale, qui appelle une
vigilance sur la discrimination indirecte : le taux d'admission d'un
boursier et d'un non-boursier dans la même formation diffère, masquer cette
différence donnerait à un boursier une estimation calculée sur une
population qui n'est pas la sienne.

**Périmètre, destinataires, durées.** Détail dans `registre-traitements.md`.
Personnes concernées : lycéens de terminale du territoire du déployeur.
Destinataires : le candidat et le conseiller. Hébergement souverain, aucun
transfert hors Union. Durées : 12 mois en clair, 36 mois pseudonymisés, puis
agrégats, purge exécutable (`api/audit_purge.py`) et planifiée (DAG
`edumatch_audit_purge`).

## 3. Nécessité et proportionnalité

| Exigence | Appréciation | Preuve |
|---|---|---|
| Finalité déterminée, explicite, légitime | Satisfaite | Aide à l'orientation, aucune finalité secondaire, aucun profilage publicitaire, aucune revente |
| Base légale | Satisfaite | Consentement (art. 6.1.a) en usage direct, mission d'intérêt public (art. 6.1.e) pour un déployeur public, intérêt légitime (art. 6.1.f) pour les échantillons Sirene (ADR 0008) |
| Minimisation | Satisfaite et testée | 4 caractéristiques collectées, 9 colonnes sur 128 lues sur la session prédite, 9 sur 54 pour Sirene, genre exclu et contrôlé par mutation |
| Exactitude | Mesurée, résultat défavorable au modèle appris | §3.1, point qui commande l'avis |
| Limitation de conservation | Décidée, exécutée, planifiée | `audit_purge.py`, testée, idempotente. Exception : T6 sans purge |
| Information | Non satisfaite | Aucune notice destinée au candidat, l'écran construit s'adresse au conseiller |
| Droits des personnes | Non satisfaits | Aucun dispositif d'exercice (T8), délai d'un mois décrit, non outillé |
| Sous-traitance | Contrat art. 28 obligatoire avant la mise en service de l'assistant (T7) | Non conclu |

### 3.1 Le test de nécessité, refait avec les mesures

Le terme d'accessibilité existe en deux versions comparables, même protocole
temporel (entraînement 2020-2023, validation 2024, test 2025, ADR 0012), à
couverture égale (100 % des 77 159 cellules de test) :

| | Modèle appris | Règle de référence |
|---|---:|---:|
| MAE pondérée, validation 2024 | **0,0690** | 0,0727 |
| MAE pondérée, test 2025 | 0,0758 | **0,0701** |
| ECE, validation 2024 | **0,0030** | 0,0141 |
| ECE, test 2025 | 0,0371 | **0,0322** |

Ventilé par sous-population sur le test 2025, le modèle appris est battu par
la règle de référence dans les trois types de bac, dans les deux statuts de
boursier, dans deux des trois groupes de mixité, et dans 16 des 19
territoires mesurés (tableau complet dans `model-card.md`, §6).

La nécessité, au sens de l'article 35 §7.b, ne porte pas sur l'utilité
générale du service mais sur l'existence d'un moyen moins intrusif atteignant
aussi bien la finalité. Ici, un moyen moins intrusif existe, il est déjà
construit (`models/baseline.py`), n'apprend rien, est intégralement
explicable, et fait mieux que le modèle appris sur la session la plus
récente, en précision comme en calibration. Un modèle appris qui n'apporte
rien de mesurable ajoute de l'opacité, une surface de dérive, une charge de
journalisation et un risque de discrimination indirecte pour un résultat
inférieur : le test de proportionnalité ne tranche pas en sa faveur. Il ne
tranche pas contre le service : affinité, restitution des facteurs, écran de
supervision, journalisation et ordonnancement restent proportionnés. C'est le
seul terme appris qui échoue.

## 4. Ce que l'architecture retire du risque avant toute mesure

Trois propriétés structurelles, qui ne peuvent pas être désactivées par
erreur : aucune donnée personnelle à l'entraînement (pas de base de dossiers
à exfiltrer ou réidentifier) ; aucune conservation de la saisie (ce qui sert
à produire la réponse disparaît, seul le journal est conservé, à part et
avec ses propres durées) ; le genre n'est jamais collecté ni utilisé en
entrée, il existe seulement dans les données publiques agrégées pour l'audit
(`models/fairness.py`).

## 5. Risques pour les droits et libertés des personnes

| Risque | Impact potentiel | Vraisemblance | Mesures | Résiduel |
|---|---|---|---|---|
| Accès illégitime aux données | Divulgation du statut de boursier et du projet d'orientation d'un mineur | Relevée depuis la v0.9 : l'écran conseiller n'est protégé par aucune authentification | Chiffrement et cloisonnement à porter par l'infrastructure, non écrits ; purge du journal exécutée et planifiée | Élevé tant qu'aucun contrôle d'accès n'est en place, §8.4 motif A |
| Modification non désirée | Caractéristique altérée, estimation fausse, conseil faux | Faible | Écriture atomique, empreintes SHA-256, contrôles qualité bloquants, idempotence testée | Faible |
| Disparition de données | Impossibilité de retracer une recommandation contestée | Faible désormais | Journal d'inférence horodaté, version de modèle et empreinte de commit | Faible pour T5 ; T6 ne se corrèle pas au journal d'inférence, faute d'identifiant commun |

## 6. Risques spécifiques au système apprenant

C'était le point le plus délicat, siège des quatre lacunes de la v0.9,
comblées par des mesures.

### 6.1 Discrimination indirecte par variable substitut, mesurée

Le risque : recevoir une estimation systématiquement différente en raison
d'un attribut protégé jamais collecté, sans moyen de s'en apercevoir.

Sur les entrées, information mutuelle corrigée par permutation : la filière
reconstitue 19,5 % du genre, l'établissement d'origine 28,9 % (exclu),
l'académie 1,4 %. La filière est indispensable au modèle : exclure le genre
est nécessaire mais insuffisant.

Sur les sorties (`models/fairness.py`, test 2025, définition privilégiée =
calibration par groupe, seuil 0,50, taux de sélection pondéré par
l'effectif) :

| Dimension | Groupe le plus défavorisé | Ratio, modèle | Ratio, référence | Seuil |
|---|---|---:|---:|---:|
| Genre | plus de 80 % de candidates femmes | **0,76** | 0,63 | 0,80 |
| Type de bac | professionnel | **0,58** | 0,62 | 0,80 |
| Territoire | Mayotte, Île-de-France | **0,25** | 0,25 | 0,80 |
| Boursier | boursier | 0,88 | 0,92 | 0,80 |

Et sur la calibration par groupe :

| Groupe de mixité | ECE modèle | ECE référence |
|---|---:|---:|
| plus de 80 % de candidates femmes | **0,0656** | 0,0475 |
| mixte (20-80 %) | 0,0319 | 0,0288 |
| moins de 20 % de candidates femmes | 0,0341 | 0,0416 |

Trois lectures, à rapporter ensemble. Sur le genre, le modèle sur-annonce les
chances d'admission dans les formations très féminisées : son erreur de
calibration y est le double des autres groupes, supérieure à la règle de
référence. Sur ma propre définition d'équité, la règle de référence est plus
équitable que le modèle appris. Le ratio de 0,76 est sous le seuil des quatre
cinquièmes, mais le modèle y fait mieux que la référence (0,63) : je n'ai pas
choisi la définition d'équité selon le résultat, la calibration par groupe a
été retenue avant de connaître les chiffres (`04-modele/equite.md`), sachant
que le théorème d'impossibilité interdit de satisfaire calibration et parité
en même temps si les taux de base diffèrent entre groupes. Sous une parité
démographique, le verdict s'inverserait, je le note plutôt que de le taire.
Les écarts par type de bac et territoire sont réels mais ne sont pas des
artefacts du modèle : la règle de référence, qui n'apprend rien, échoue aux
mêmes seuils (professionnel 0,62, Mayotte 0,25). Ils décrivent la structure
du système d'orientation français. Exception : sur le bac professionnel, le
modèle dégrade légèrement le ratio (0,58 contre 0,62).

Retirer les quatre substituts encore présents (`fili`, `select_form`, `dep`,
`acad_mies`, 14,2 % de l'explication SHAP) coûte presque rien en performance
(+0,0006 de MAE pondérée) et n'améliore pas l'équité (ratio du groupe le plus
féminisé de 0,66 à 0,62). L'information est diffuse dans les variables
décalées, pas concentrée dans quatre colonnes : l'exclusion de variables ne
peut pas être le seul levier d'équité.

### 6.2 Renoncement induit par une estimation basse, la calibration se dégrade

Le risque le plus grave : un adolescent à qui l'on annonce 20 % de chances
renonce à candidater. Si l'estimation est fausse, le système a fermé une
porte qu'aucune décision humaine n'avait fermée, effet invisible car personne
ne mesure les candidatures qui n'ont pas eu lieu.

La mesure existe (`models/evaluate.py`, 10 tranches) : en validation 2024, le
modèle est bien calibré, ECE 0,0030 ; en test 2025, l'ECE monte à 0,0371,
au-dessus de la règle de référence (0,0322), et le modèle devient sur-confiant
sur toute la plage médiane, il annonce 0,55 quand la réalité observée est
0,49, restant bien calibré aux extrêmes.

Six points de sur-annonce au milieu de l'échelle sont l'erreur qui compte
pour ce risque : le candidat qui hésite lit un chiffre médian. Lui annoncer
0,55 pour 0,49 le fait candidater sur une formation moins accessible
qu'annoncé et l'expose à un refus non anticipé. Sur-confiance et renoncement
sont les deux faces du même défaut, la première mesurée, la seconde non
observable. La réserve de la v0.9 est confirmée par la mesure et change de
motif : on ne s'oppose plus à une restitution dont on ignore la qualité, mais
à une restitution dont on connaît le défaut.

Mesures en place : l'interface énonce que l'estimation porte sur une
catégorie et non sur la personne, les facteurs explicatifs sont présentés à
côté du score, la mise en garde voyage avec chaque réponse de l'API
(`MISE_EN_GARDE_ACCESSIBILITE`). Manque un intervalle plutôt qu'un point.

### 6.3 Boucle de rétroaction, partiellement instrumentée

Le risque : appartenir à un profil découragé, le voir se raréfier dans les
campagnes suivantes, et le modèle confirme son propre biais. Profils
exposés : le bac professionnel, où 21,6 % des formations n'émettent aucune
proposition. Pas théorique : la cible est un taux dont le dénominateur est le
nombre de vœux, la grandeur que le système influence.

`models/derive.py` (ADR 0018) mesure la dérive des variables, de la cible et
des prédictions, PSI 0,0174 en validation 2024, 0,0296 en test 2025, contre
un seuil de 0,20. C'est l'instrument qui verrait une boucle s'installer, mais
sa référence est la distribution d'entraînement 2020-2023, pas une
population post-déploiement, qui n'existe pas : ce risque reste identifié,
partiellement instrumenté et non mesuré. Le seuil (PSI médian 0,20) est vingt
fois au-dessus du pire cas observé, calibré contre le bruit d'une session,
pas contre une dérive lente de composition : l'ADR reconnaît qu'il n'aurait
pas détecté la dégradation validation → test déjà mesurée.

### 6.4 Contrôle humain de façade, dispositif construit, effectivité non mesurable

Le risque : qu'un conseiller suive l'outil parce que l'outil est chiffré.

| Exigence posée en v0.9 | État |
|---|---|
| Écartement possible | Oui |
| Écartement motivé, motif obligatoire | Oui, bloqué côté client et serveur |
| Horodaté et journalisé | Oui |
| Facteurs explicatifs présentés à côté du score | Oui |
| L'interface dit ce qu'elle ne sait pas | Oui, affiché |
| Taux d'écartement mesuré et restitué | Non, aucun tableau de bord |
| Identité du superviseur vérifiée | Non, identifiant déclaratif |

Deux manques différents : l'absence de tableau de bord empêche de mesurer
l'effectivité du contrôle (réserve) ; l'absence d'authentification est plus
grave, une trace de supervision n'est imputable à personne (motif de blocage
A).

### 6.5 Information erronée sur les débouchés, tranché

Le risque : orienter un choix de vie sur un chiffre de débouchés faux. La
mesure est sévère : l'appariement textuel exact des libellés couvre 7
libellés distincts sur 712 (1,0 %), soit 6 017 lignes sur 440 030 (1,4 %),
relues à la main. Pour les 98,6 % restants, le terme est marqué indisponible
avec son motif, jamais mis à zéro en silence, motif qui remonte à l'écran.

Je considère ce risque comme traité, non parce que la couverture est bonne,
elle est mauvaise, mais parce que la personne n'est jamais exposée à un
chiffre faux. La valeur du troisième terme du score est aujourd'hui nulle
pour la quasi-totalité du catalogue, à dire au déployeur comme une limite du
produit.

### 6.6 Ré-identification d'un tiers par l'agrégat territorial, traité

Risque sur une autre catégorie de personnes que les candidats : les
entrepreneurs individuels. 65,9 % des cellules non vides de l'agrégat
`commune × NAF` ne comptent qu'un établissement. La décision de `risques.md`
(R2) est implémentée : restitution au grain `département × NAF` avec k = 5,
grain communal jamais exposé, filtre `diffusible` appliqué (20 488
établissements exclus). Le module ne renvoie jamais l'effectif sous le
seuil. Sirene reste pseudonymisée, pas anonymisée : k = 5 réduit le risque,
ce n'est pas une anonymisation.

## 7. Les mineurs, ce que l'article 8 impose et ce qui manque

Le public visé : lycéens de terminale, majoritairement 17-18 ans, minorité
de 16 ans. L'âge du consentement numérique est fixé à quinze ans en France,
le public est au-dessus, le consentement parental n'est pas requis pour ce
périmètre. Trois conséquences, deux non satisfaites : l'information doit
être rédigée pour un adolescent, affichée avant la saisie (non satisfaite,
le seul écran s'adresse au conseiller) ; aucun public de moins de quinze ans
sans rouvrir cette analyse et recueillir le consentement parental (écrit,
non outillé, la date de naissance n'étant pas collectée) ; vigilance sur le
champ libre du motif d'écartement, où un conseiller peut consigner une
information sur un mineur (avertissement affiché, purge inexistante).

## 8. Avis

### 8.1 État des quatre motifs de la version 0.9

| Motif v0.9 | État au 2026-09-15 | Preuve |
|---|---|---|
| 1. Calibration non mesurée | Levé comme motif d'ignorance, mesure défavorable, fonde le motif D | `models/evaluate.py` |
| 2. Audit d'équité non réalisé | Levé, réalisé sur quatre dimensions | `models/fairness.py`, `04-modele/equite.md` |
| 3. Aucun dispositif de contrôle humain | Levé sur l'existence, effectivité non mesurable, accès non authentifié | `api/static/`, `routes/feedback.py` |
| 4. Durées sans purge exécutable | Levé pour T5, pas pour T6 | `api/audit_purge.py`, DAG |

### 8.2 Sur le principe du traitement : favorable

L'architecture retire du risque là où il est le plus lourd, aucune donnée
personnelle à l'entraînement, aucune conservation de la saisie, aucune donnée
comportementale. La minimisation est vérifiée par des tests qui échouent si
on la contredit, validés par mutation. Le dispositif d'équité repose sur des
mesures qui ont infirmé plusieurs hypothèses initiales du projet.

### 8.3 Sur la mise en service : défavorable sur le terme appris, favorable sous réserves sur le reste

**(a) Défavorable à la restitution, à des candidats réels, de l'estimation
d'accessibilité produite par le modèle appris.** Motif suffisant : il échoue
au test de nécessité (§3.1). Une règle de dénombrement déjà construite fait
mieux que lui en précision et en calibration sur la session la plus récente,
dans la quasi-totalité des sous-populations, et elle est mieux calibrée par
groupe sur la dimension la plus sensible du projet. Le modèle appris ajoute
de l'opacité et un risque de discrimination indirecte pour un résultat
inférieur, cela ne se rattrape pas par un avertissement.

Ce qui lèverait ce point, écrit avant la prochaine mesure : un modèle
réentraîné qui passe sous 0,0701 de MAE pondérée et 0,0322 d'ECE sur une
session de test non consultée pendant le réglage, avec un ECE du groupe le
plus féminisé ramené à l'ordre de grandeur des autres groupes (0,032).

**(b) Favorable, sous réserves, au reste du dispositif** : affinité,
ordonnancement, restitution des facteurs, écran de supervision,
journalisation et purge, composants proportionnés, utiles et documentés.

**(c) Favorable, sans réserve de fond, à l'exploitation en environnement de
démonstration et d'évaluation**, avec des conseillers et sans restitution
directe à des candidats mineurs. C'est le périmètre du projet de
certification.

### 8.4 Les motifs de blocage encore actifs

Chacun renvoie à la liste opposable de `plan-gouvernance.md` §3 et suffit
seul à bloquer une mise en service auprès de candidats réels.

| # | Motif | Rattachement | Ce qui le lève |
|---|---|---|---|
| A | Aucun contrôle d'accès sur l'écran exposant des données de candidats, identifiant du conseiller déclaratif, aucune trace imputable | art. 32 RGPD, art. 14 AI Act | Authentification du conseiller, identifiant journalisé |
| B | Journal de supervision T6 sans purge, durée écrite (12 mois), faute d'identifiant commun avec T5 | art. 5.1.e | Identifiant de corrélation T5/T6, extension de `audit_purge.py` |
| C | Aucune notice d'information destinée au candidat | art. 12, 13, 14 RGPD, art. 8 | Notice affichée avant la saisie, pour un lecteur de 17 ans |
| D | Restitution chiffrée d'une probabilité dont le défaut de calibration est connu, sur-annonce de six points en test | art. 5.1.d, §6.2 | Le double seuil de (a) ci-dessus |
| E | Attribution des sources non effective, la Licence Ouverte impose paternité et date | art. 2 Licence Ouverte v2.0 | Écran Sources et licences alimenté par les manifestes |

### 8.5 Réserves fermes, non bloquantes

1. Aucun dispositif d'exercice des droits (T8), délai d'un mois dès la
   première demande.
2. Aucune procédure de notification de violation (art. 33 et 34), elle
   suppose de savoir qui héberge quoi.
3. Aucun tableau de bord du taux d'écartement, un taux nul est un signal
   d'alerte, pas un succès.
4. Aucun contrat de sous-traitance (art. 28) pour le fournisseur de modèle de
   langage, pas de mise en service de T7 sans lui.
5. Pas d'affichage d'intervalle, le score est restitué comme un point.
6. L'ablation de la source Sirene est impossible, aucune formation Parcoursup
   n'étant reliée par la chaîne de nomenclatures : mesure sans objet, à
   écrire ainsi partout, y compris dans la Model Card.

### 8.6 Révision

Obligatoire avant toute mise en service, et à chaque changement substantiel
(nouvelle finalité, variable, catégorie de personnes, modèle, public de
moins de quinze ans, ou incident). Prochaine révision programmée à la
publication du millésime Parcoursup suivant, qui apportera la première
session de test non encore consultée et permettra de statuer sur le motif
(a).

---
*Étape E41, version 1.0 du 2026-09-15, remplaçant la version 0.9 du
2026-08-30 : plus aucun point en attente, cinq motifs de blocage et six
réserves opposables.*
