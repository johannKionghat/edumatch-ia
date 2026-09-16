# ADR 0013 — Décision des variables : liste blanche sur la session prédite, décalage d'une session pour tout le reste

Statut : accepté (2026-08-29)

S'appuie sur l'ADR 0009 (label), l'ADR 0010 (fuite fonctionnelle et
décalage), l'ADR 0011 (substituts du genre) et l'ADR 0012 (protocole
d'évaluation), sans les rouvrir : je les applique colonne par colonne à
l'ensemble du fichier Parcoursup.

## Contexte

Il reste à décider, pour chaque colonne du fichier Parcoursup, si elle entre
dans le modèle et sous quelle forme. Périmètre mesuré sur les huit
millésimes : 128 colonnes vues au moins une fois (de 85 en 2018 à 118 de
2021 à 2025), dont 83 communes aux huit sessions et 59 remplies à plus de
99 % partout.

Trois contraintes encadrent la décision : le système doit répondre à un
lycéen qui formule encore ses vœux entre janvier et mars, donc le critère
d'exclusion est « inconnu au moment où le lycéen formule ses vœux », plus
large que « postérieur à l'admission » (ADR 0010) ; le split temporel
2020-2023 / 2024 / 2025 (ADR 0012) rend piégeuse toute colonne dont la
disponibilité change dans cette fenêtre ; et l'exclusion du genre ne suffit
pas, la filière reconstituant déjà 19,5 % de la féminisation (ADR 0011).

## Décision

Une liste blanche plutôt qu'une liste noire : je n'autorise sur la session
prédite que les colonnes lisibles à ce moment-là, tout le reste est décalé
d'une session ou exclu par défaut tant qu'il n'a pas été classé.

### Liste blanche de la session prédite — neuf colonnes, attributs de catalogue publiés avant la campagne

| Colonne | Ce qu'elle porte | Modalités (2025) |
|---|---|---|
| `fili` | filière | 11 |
| `fil_lib_voe_acc` | filière détaillée | 438 |
| `form_lib_voe_acc` | type de formation | 53 |
| `select_form` | sélective ou non | 2 |
| `contrat_etab` | public, privé sous contrat, hors contrat | 4 |
| `tri` | université, lycée, autre | 3 |
| `dep` | département | 106 |
| `acad_mies` | académie | 33 |
| `region_etab_aff` | région | 19 |

Aucune ne compte de vœux, de propositions ou d'admis. S'y ajoutent les deux
dimensions de la cellule (type de bac, statut boursier), portées par la
structure du label et non par une colonne.

### Variables décalées d'une session — trente-cinq colonnes

Tous les compteurs de la session N-1 : capacité, vœux, candidats classés,
propositions, admis, académie d'origine, calendrier, rang du dernier appelé.
Le décalage est licite parce que le fichier du millésime 2024 porte, sur le
catalogue du ministère, une dernière modification au 16 janvier 2025 — date
d'ouverture de la campagne 2025. Réserve à écrire : cette métadonnée donne
la dernière modification, pas la première publication (le millésime 2023 a
été révisé après la phase de vœux 2024) ; l'écart n'est pas mesurable avec
les données dont je dispose, je le déclare comme limite plutôt que de
l'ignorer.

### Variables de mention — retenues sous réserve, écartées par défaut

Huit colonnes (`acc_sansmention`, `acc_ab`, `acc_b`, `acc_tb`,
`acc_mention_nonrenseignee`, `acc_bg_mention`, `acc_bt_mention`,
`acc_bp_mention`). Le bac 2020, délivré en contrôle continu, fait passer les
mentions « très bien » de 7,4 % à 11,8 % sans retour au niveau antérieur en
2021. Décalées d'une session, ces variables contamineraient les sessions
cibles 2021 et 2022, soit deux des quatre sessions d'entraînement. Écartées
du jeu de référence, réintroduites seulement si l'ablation démontre un gain.

### Exclusions définitives — soixante-treize colonnes

| Motif | Nb | Raison |
|---|---:|---|
| Interdites | 4 | Ventilations par sexe (`pct_f`, `voe_tot_f`...) : le genre ne sert qu'à l'audit a posteriori |
| Substituts | 3 | `cod_uai`, `ville_etab`, `g_olocalisation_des_formations` — voir ci-dessous |
| Instabilité | 22 | Disponibilité qui change dans la fenêtre 2020-2025 (ex. `*_id_paysage` : ~47 % de 2021 à 2024, vide en 2025) |
| Complétude non aléatoire | 10 | Renseignées sur 7 % à 47 % des lignes, non au hasard (ex. `acc_term` : non applicable hors BTS/CPGE) |
| Hors périmètre | 10 | Décrivent les autres terminales et la phase complémentaire, hors du label |
| Redondance | 23 | Recalculables depuis une colonne retenue (règle : effectifs gardés, pourcentages écartés) |
| Cardinalité | 1 | `lib_comp_voe_ins` : 11 891 modalités pour 14 252 lignes, un quasi-identifiant |

Sur la redondance, la vérification a corrigé une erreur que j'avais d'abord
écrite : `pct_bours` n'est pas `acc_brs / acc_tot`, l'écart atteint 97,5
points au maximum. Le dénominateur réel est `acc_neobac` (les
néo-bacheliers). Reconstitution exacte des dix-neuf colonnes de pourcentage
vérifiée à 0,500 point près (l'arrondi) sur la session 2025, sur deux
dénominateurs (`acc_neobac` ou `acc_tot`). La leçon : un pourcentage ne se
rattache jamais à son dénominateur par le nom.

### L'arbitrage sur `cod_uai` et `ville_etab`

`cod_uai` est le premier substitut du genre mesuré (28,9 % net) et pourrait
sembler indispensable — l'établissement a une réputation qui pèse sur la
sélectivité. Je l'exclus pour deux raisons indépendantes : sa cardinalité
(4 058 établissements, le modèle mémoriserait l'établissement plutôt que
d'apprendre une règle transférable) et son rôle de substitut (la plus forte
association mesurée avec la féminisation). L'information ne disparaît pas
complètement : les variables décalées, attachées à la formation, en portent
une partie — c'est pourquoi le dispositif d'équité de l'ADR 0011 ne repose
pas sur l'exclusion seule.

`ville_etab` (10,2 % net) est plus simple à trancher : apport métier faible
(département, académie et région sont déjà retenus) et absente de la
session 2020. `g_olocalisation_des_formations`, ses coordonnées exactes, la
suit par cohérence.

### Une conséquence non anticipée

`prop_tot_*` ventilé par type de bac n'existe pas avant 2020 (ADR 0012).
Décalé d'une session, il manque donc pour la session cible 2020 : la
variable la plus prédictive du jeu est absente pour un quart des sessions
d'entraînement. Ces valeurs restent manquantes de façon explicite, sans
imputation — LightGBM traite nativement l'absence. La baseline (session
précédente) n'est mesurable que sur 2021-2025.

### Où vit la décision

La classification des 128 colonnes est écrite dans `configs/base.yaml`
(section `modele.variables`), typée par `VariablesConfig`. Trois tests
s'appuient dessus : toute colonne citée doit exister réellement, toute
colonne d'un millésime doit être classée (un millésime futur qui en ajoute
une fait échouer la suite tant qu'elle n'est pas décidée), et aucune colonne
de résultat ne doit figurer dans la liste blanche. Vérifiés par mutation :
colonne mal orthographiée, colonne retirée du classement, `voe_tot` déplacé
vers la liste blanche, split rouvert à 2018 — chaque mutation fait échouer
le test qui la vise, et lui seul.

## Alternatives écartées

- Lister les colonnes à exclure et prendre le reste (liste noire) : une
  colonne ajoutée par un millésime futur entrerait dans le modèle sans
  avoir été examinée.
- Décaler aussi les attributs de catalogue : la filière ou le caractère
  sélectif sont publiés avant la campagne, les décaler ferait perdre les
  formations nouvelles (5 % à 18 % du catalogue selon la paire de sessions)
  sans gain de sûreté.
- Décaler de deux sessions plutôt qu'une : écartée par défaut, conservée
  comme repli si l'écart entre version révisée et version publiée en
  janvier s'avérait important.

## Conséquences

Le jeu de référence compte 9 colonnes lues sur la session prédite, 35
décalées, 2 dimensions de cellule, et 8 colonnes de mention en réserve — peu
au regard des 128 colonnes disponibles, et c'est voulu : chaque variable
retenue doit pouvoir être justifiée une par une devant le jury. Le niveau 2
du dispositif d'équité (ADR 0011) doit être rejoué sur ce jeu final.
L'ablation devra mesurer trois retraits : les mentions, `cod_uai`, et les
variables décalées dans leur ensemble.

Je reviendrais sur l'écart des mentions si l'ablation montrait un gain
d'erreur absolue moyenne pondérée supérieur à 0,01 sur les sessions non
contaminées. Je reviendrais sur l'exclusion de `cod_uai` si l'ablation
montrait une perte, traitée alors par un encodage par la cible calculé sur
les seuls plis d'entraînement, jamais par réintroduction de l'identifiant
brut. Je reviendrais sur le décalage d'une session si l'écart entre version
révisée et version publiée en janvier devenait mesurable et important.

## Ce que je n'ai pas tranché

`capa_fin`. Parcoursup affiche un nombre de places sur chaque fiche pendant
la campagne, mais rien dans les fichiers dont je dispose ne prouve que la
colonne « capacité finale » du fichier de résultats vaut la capacité
affichée en janvier. Par prudence je la classe en variable décalée.
Trancher demanderait de comparer la fiche affichée pendant la campagne au
fichier publié ensuite — une vérification que je n'ai pas faite. Si les deux
valeurs coïncident, `capa_fin` passe en liste blanche : c'est le
dénominateur direct de la tension, mon meilleur prédicteur.

Reproduit par les quatre carnets de `notebooks/` pour les mesures citées, et
par une commande d'inventaire des 128 colonnes sur `data/raw/parcoursup/`.
