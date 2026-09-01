# Analyse d'impact relative à la protection des données (AIPD)

**Critère servi** : Bloc 1, 1.7 — livrable obligatoire · **Version** : 0.9,
**incomplète et déclarée telle** · **Date** : 2026-08-30 ·
**Fondement** : RGPD art. 35.

> **Lecture de cette version.** Les sections 1 à 5 sont complètes et
> renseignées à partir d'éléments vérifiables du dépôt. Les sections 6 et 7
> comportent **quatre trous explicitement identifiés**, qui dépendent de
> mesures non encore produites — audit d'équité sur les prédictions,
> calibration, écran de supervision, journalisation. Chacun est marqué
> `[À COMPLÉTER]`, avec ce qui le débloque. Une analyse d'impact à trous
> déclarés vaut mieux qu'une analyse absente ; une analyse qui comblerait ces
> trous par des affirmations ne vaudrait rien du tout.

**Toute cette analyse apprécie les risques pour les droits et libertés des
personnes concernées — les candidats — et non les risques pour
l'organisation.** Les risques encourus par le projet lui-même (non-conformité
de licence, fuite de données dans le protocole, secret versionné) sont traités
ailleurs, dans `risques.md`, et sont marqués comme tels pour qu'aucune
confusion ne soit possible.

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

**Deux critères auraient suffi. Quatre sont présents.** L'obligation n'est
donc pas discutable, et elle ne dépendrait même pas du caractère haut risque
au titre du règlement sur l'IA, qui s'y ajoute par ailleurs.

## 2. Description systématique du traitement

### 2.1 Finalité

Aider un lycéen de terminale à construire une liste de vœux d'orientation
informée, en lui indiquant pour chaque formation : à quel point elle
correspond à ses intérêts (**affinité**, par règles), quelles sont ses chances
d'y être admis (**accessibilité**, seul terme appris), et quels débouchés
d'emploi existent sur son territoire (**débouchés**, par agrégats).

Le score est **multiplicatif** : si un terme s'annule, la recommandation
disparaît. Ce choix a une conséquence directe sur les personnes : une
formation ne peut pas être recommandée au seul motif qu'elle est accessible.

### 2.2 Ce que le système fait, et ce qu'il ne fait pas

| Il fait | Il ne fait pas |
|---|---|
| Estimer un taux d'admission par **cellule** — formation, session, type de baccalauréat, statut de boursier | Estimer une probabilité individuelle : le modèle n'a jamais vu un dossier de candidat |
| Restituer les facteurs qui portent l'estimation | Prendre une décision d'admission — elle appartient aux établissements, hors de ce système |
| Ordonner des formations selon un score composite | Empêcher une candidature, ni la transmettre à qui que ce soit |

**Cette distinction est la plus importante de l'analyse.** Le modèle apprend
sur des agrégats publics de campagnes passées, non sur des personnes. Il
prédit la propriété d'une cellule, puis on affecte cette propriété à la
personne qui appartient à cette cellule. Le candidat ne reçoit donc pas « une
probabilité le concernant » mais « le taux estimé de la catégorie à laquelle
il appartient » — et l'interface doit le dire dans ces termes, faute de quoi
elle promet une précision individuelle qui n'existe pas.

### 2.3 Flux de données

```
ENTRAÎNEMENT (T1)
  Parcoursup 2020-2025, comptages agrégés par formation
  440 030 cellules -> LightGBM pondéré
  AUCUNE donnée personnelle

INFÉRENCE (T4)
  Saisie du candidat : type de bac, boursier ou non, territoire,
  intérêts déclarés
  -> score par formation + facteurs explicatifs
  DONNÉES PERSONNELLES, MINEURS POSSIBLES, non conservées

TRAÇABILITÉ (T5)          SUPERVISION (T6)
  Journal d'inférence       Conseiller : voir, comprendre, écarter
  12 mois en clair          avec motif obligatoire
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
| Département ou académie | Établissement d'origine |
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

Détail complet dans `registre-traitements.md`. En résumé : personnes
concernées = lycéens de terminale du territoire du déployeur ; destinataires =
le candidat et le conseiller qui l'accompagne ; hébergement souverain, aucun
transfert hors Union ; durées 12 mois en clair, 36 mois pseudonymisés, puis
agrégats.

## 3. Nécessité et proportionnalité

| Exigence | Appréciation | Preuve |
|---|---|---|
| **Finalité déterminée, explicite, légitime** | Satisfaite | Aide à l'orientation ; aucune finalité secondaire, aucun profilage publicitaire, aucune revente |
| **Base légale** | Satisfaite, choix documenté | Consentement (art. 6.1.a) en usage direct ; mission d'intérêt public (art. 6.1.e) pour un déployeur public. Pour les traitements existants : intérêt légitime (art. 6.1.f) avec mise en balance écrite (ADR 0008) |
| **Minimisation** | **Satisfaite et vérifiée par test** | 4 caractéristiques collectées ; 9 colonnes lues sur 128 sur la session prédite ; 9 sur 54 pour Sirene ; genre exclu, contrôlé par `tests/data/test_features_build_antifuite.py` |
| **Exactitude** | Satisfaite côté données, **non établie côté modèle** | Contrôles qualité bloquants (`tests/data/test_quality_run_blocage.py`) ; mais la calibration du modèle n'est pas encore mesurée — voir 6.4 |
| **Limitation de conservation** | **Décidée, non exécutée** | Durées écrites ; aucune purge automatisée n'existe |
| **Information** | **Non satisfaite** | Aucune notice n'est rédigée. Elle devra être en français simple, compréhensible par un adolescent, affichée avant la saisie |
| **Droits des personnes** | **Non satisfaits** | Aucun dispositif d'exercice ; procédure décrite (T8), délai d'un mois, non outillée |
| **Sous-traitance** | Non applicable aujourd'hui ; contrat obligatoire avant la mise en service de l'assistant conversationnel | |

**Le test de proportionnalité, énoncé franchement** : l'atteinte est faible —
quatre caractéristiques, aucune conservation de la saisie, aucun croisement
avec un dossier scolaire — et l'utilité est réelle : un lycéen qui formule ses
vœux en janvier n'a aujourd'hui aucun moyen simple de savoir ce que valent ses
chances. La proportionnalité est acquise **sur les données**. Elle ne l'est
pas encore **sur les effets** : c'est l'objet de la section 6.

## 4. Ce que l'architecture retire du risque avant toute mesure

Trois propriétés structurelles, qui valent mieux que des mesures ajoutées
après coup, parce qu'elles ne peuvent pas être désactivées par erreur :

1. **Aucune donnée personnelle à l'entraînement.** Il n'existe pas de base de
   dossiers de candidats à exfiltrer, à réidentifier, ou à réutiliser pour une
   autre finalité. Le scénario de violation le plus grave d'un système
   d'orientation n'a pas d'objet ici.
2. **Aucune conservation de la saisie.** Ce que le candidat entre sert à
   produire la réponse et disparaît. Ce qui est conservé — le journal — l'est
   au titre d'une obligation légale distincte, avec ses propres durées.
3. **Le genre n'est jamais collecté ni utilisé en entrée.** Il n'existe que
   dans les données publiques agrégées, à seule fin d'audit.

## 5. Risques pour les droits et libertés des personnes — les trois risques classiques

| Risque | Impact potentiel sur la personne | Vraisemblance | Mesures | Résiduel |
|---|---|---|---|---|
| **Accès illégitime aux données** | Divulgation du statut de boursier et du projet d'orientation d'un mineur — information à forte portée sociale, susceptible de stigmatisation | Faible : aucune base de profils n'existe ; la surface se limite aux journaux | Chiffrement au repos et en transit, accès nominatif et journalisé, hébergement souverain, purge à 12 mois | **Faible**, sous réserve que les journaux soient effectivement chiffrés et purgés |
| **Modification non désirée des données** | Une caractéristique altérée produit une estimation fausse, donc un conseil faux, sans que la personne puisse le détecter | Faible | Écriture atomique, empreintes SHA-256, contrôles qualité bloquants, idempotence testée | Faible |
| **Disparition de données** | Impossibilité de retracer une recommandation contestée, donc de la contester utilement | Moyenne, en l'absence de journalisation construite | Journalisation art. 12, sauvegardes | **Élevé aujourd'hui** : la journalisation n'existe pas |

## 6. Risques spécifiques au système apprenant

C'est ici que se joue l'essentiel, et c'est ici que sont les trous.

### 6.1 Discrimination indirecte par variable substitut

**Le risque pour la personne** : recevoir une estimation systématiquement plus
basse en raison d'un attribut protégé qui n'a jamais été collecté, et sans
aucun moyen de s'en apercevoir.

**Ce qui est mesuré** : l'information mutuelle entre variables candidates et
sexe des admis, corrigée du nombre de modalités par permutation, montre que la
**filière reconstitue 19,5 %** du genre. La filière est indispensable au
modèle. L'exclusion du genre est donc **nécessaire mais insuffisante**, et je
l'écris avant tout résultat plutôt qu'après.

**Ce qui est en place** : exclusion à l'entrée, vérifiée par test ; exclusion
de `cod_uai` (28,9 %) et `ville_etab` (10,2 %) ; conservation assumée de la
filière, avec le seuil de réouverture écrit.

`[À COMPLÉTER — 1]` **Le ratio d'impact disparate sur les prédictions du
modèle n'est pas calculé.** Il ne peut l'être qu'une fois le modèle stabilisé.
Débloqué par : l'audit d'équité sur les sorties du modèle entraîné, sur quatre
dimensions. Sans cette mesure, l'analyse ne peut pas conclure sur le risque
résiduel de discrimination — et je ne conclus donc pas.

### 6.2 Renoncement induit par une estimation basse

**Le risque pour la personne** : le plus grave de l'analyse. Un adolescent à
qui l'on annonce 20 % de chances renonce à candidater. Si l'estimation est
fausse, ou seulement mal comprise, le système a fermé une porte qu'aucune
décision humaine n'avait fermée. L'effet est **invisible** : personne ne
mesure les candidatures qui n'ont pas eu lieu.

**Mesures** : présenter un intervalle et non un point ; énoncer que
l'estimation porte sur une catégorie et non sur la personne ; ne jamais
formuler une estimation basse comme un déconseil ; restituer les facteurs
**avant** le score ; maintenir le conseiller dans la boucle.

`[À COMPLÉTER — 2]` **La calibration n'est pas mesurée.** Annoncer une
probabilité impose de savoir si elle vaut ce qu'elle dit : sur l'ensemble des
estimations à 20 %, la proportion réellement admise doit avoisiner 20 %. Sans
courbe de calibration ni erreur de calibration attendue, **je m'oppose à toute
restitution chiffrée à un candidat**. C'est une réserve bloquante, pas une
remarque.

### 6.3 Boucle de rétroaction

**Le risque pour la personne** : appartenir à un profil que le système
décourage, donc voir ce profil se raréfier dans les campagnes suivantes, donc
voir le modèle apprendre que ce profil ne candidate pas — et confirmer son
propre biais. Les profils exposés sont les moins favorisés : le bac
professionnel, où **21,6 % des formations n'émettent aucune proposition**.

Ce n'est pas une considération théorique : la cible du modèle est un taux dont
le dénominateur est le nombre de vœux, c'est-à-dire exactement la grandeur que
le système influence.

**Mesures** : surveiller la distribution des profils recommandés d'une session
à l'autre, et non seulement la performance ; conserver la comparaison avant /
après mise en service, que les paliers de conservation rendent possible.

`[À COMPLÉTER — 3]` Aucune surveillance de ce type n'existe. Débloqué par la
mise en service et par un premier millésime post-déploiement. **À l'échelle du
projet de certification, ce risque restera identifié et non mesuré** — je le
dis plutôt que de laisser croire l'inverse.

### 6.4 Contrôle humain de façade

**Le risque pour la personne** : que son dossier soit traité par un conseiller
qui suit l'outil parce que l'outil est chiffré. Un contrôle humain qui
n'écarte jamais rien n'est pas un contrôle.

**Mesures exigées** : écartement possible, **motivé**, horodaté, journalisé ;
taux d'écartement mesuré et restitué au déployeur ; facteurs explicatifs
présentés avant le score.

`[À COMPLÉTER — 4]` L'écran de supervision n'existe pas. Tant qu'il n'existe
pas, **il n'y a pas de contrôle humain**, et l'article 14 n'est pas satisfait.

### 6.5 Information erronée sur les débouchés

**Le risque pour la personne** : orienter un choix de vie sur un chiffre de
débouchés faux. Aujourd'hui, aucune formation Parcoursup n'est raccordée à la
chaîne de nomenclatures : le terme ne peut être calculé pour aucune formation
recommandée. Un appariement textuel non mesuré produirait des chiffres faux
indistinguables des justes.

**Décision** : soit un appariement mesuré avec son taux d'erreur déclaré, soit
un périmètre restreint assumé et le terme déclaré indisponible ailleurs.
**Aucune troisième voie.**

### 6.6 Ré-identification d'un tiers par l'agrégat territorial

Risque portant sur une **autre** catégorie de personnes que les candidats :
les entrepreneurs individuels. 65,9 % des cellules non vides de l'agrégat
`commune × NAF` ne comptent qu'un établissement. Seuil de k-anonymat arrêté,
mesuré et motivé dans `risques.md` (R2) : **k = 5 au grain de restitution
`département × NAF`**, qui ne coûte que 1,6 % des établissements, contre
46,9 % si le même seuil était appliqué au grain communal.

## 7. Avis du délégué à la protection des données

**Sur le principe du traitement** : favorable. L'architecture retire du risque
là où il est le plus lourd — aucune donnée personnelle à l'entraînement,
aucune conservation de la saisie, aucune donnée comportementale. La
minimisation n'est pas déclarative : elle est vérifiée par des tests qui
échouent si on la contredit. Le dispositif d'équité repose sur une mesure qui
a infirmé l'hypothèse initiale du projet, ce qui vaut mieux qu'une mesure qui
la confirmerait.

**Sur la mise en service : défavorable en l'état**, pour quatre motifs
opposables, chacun suffisant à lui seul :

1. la **calibration** du modèle n'est pas mesurée — on ne peut pas annoncer
   une probabilité dont on ignore si elle vaut ce qu'elle dit ;
2. l'**audit d'équité sur les prédictions** n'est pas réalisé, alors que la
   mesure des substituts établit déjà que l'exclusion du genre ne suffit
   pas ;
3. il n'existe **aucun dispositif de contrôle humain**, donc aucune
   possibilité d'écarter une recommandation ;
4. ~~les **durées de conservation n'ont pas de purge exécutable**, ce qui les
   ramène au rang d'intentions~~ — **motif levé le 2026-09-01 (E30)** :
   `src/edumatch/api/audit_purge.py` exécute les trois paliers du journal
   d'inférence (clair, pseudonymisé, agrégé), en mode simulation par
   défaut, testé et idempotent. Détail : `06-service/journalisation-purge.md`.
   Ce que ce motif ne couvre pas encore : le déclenchement de la purge
   n'est pas planifié dans un ordonnanceur, et le journal des décisions de
   conseiller (T6) n'a pas de purge propre — deux points désormais suivis
   dans `reste-a-faire.md`, pas dans cet avis.

S'y ajoutent deux conditions non bloquantes mais fermes : la notice
d'information aux candidats, en termes qu'un adolescent comprend, et le seuil
de k-anonymat appliqué à toute restitution territoriale.

**Révision de la présente analyse** : obligatoire avant toute mise en service,
et à chaque changement substantiel — nouvelle finalité, nouvelle variable,
nouvelle catégorie de personnes concernées, changement de public visant des
élèves de moins de quinze ans.

---
*Étape E41 · version 0.9 du 2026-08-30, mise à jour le 2026-09-01 (motif 4
levé, voir §7) · trois compléments restants avant révision complète.*
