# ADR 0013 — Décision des variables : liste blanche sur la session prédite, décalage d'une session pour tout le reste

**Date** : 2026-08-29 · **Statut** : accepté

S'appuie sur l'ADR 0009 (définition du label), l'ADR 0010 (fuite fonctionnelle
et décalage temporel), l'ADR 0011 (substituts du genre) et l'ADR 0012
(protocole d'évaluation). Il ne les rouvre pas : il les applique, colonne par
colonne, à l'ensemble du fichier Parcoursup.

## Contexte

Les quatre carnets exploratoires ont établi ce que valent la cible, les écarts
entre baccalauréats, les substituts du genre et la stabilité des séries. Il
reste à décider, pour **chaque colonne**, si elle entre dans le modèle et sous
quelle forme. C'est la décision qui engage tout le reste : la construction des
variables, l'entraînement, l'audit d'équité et l'ablation en dépendent.

Le périmètre exact, mesuré sur les huit millésimes réellement téléchargés :
**128 colonnes vues au moins une fois**, de 85 (session 2018) à 118 (sessions
2021 à 2025), dont **83 communes aux huit sessions** et 59 remplies à plus de
99 % partout.

Trois contraintes encadrent la décision :

1. **Le moment de l'inférence.** Le système doit répondre à un lycéen qui
   formule encore ses vœux, entre janvier et mars de la session N. Le critère
   d'exclusion n'est donc pas « postérieur à la décision d'admission » mais
   **« inconnu au moment où le lycéen formule ses vœux »** (ADR 0010). Il est
   plus large : la tension `voe_tot` précède l'admission et reste inutilisable.
2. **Le split temporel** entraînement 2020-2023, validation 2024, test 2025
   (ADR 0012). Une colonne dont la disponibilité change à l'intérieur de cette
   fenêtre est un piège : le modèle apprend une régularité qui n'existe plus au
   moment du test.
3. **L'interdiction du genre**, et le constat que l'exclusion ne suffit pas :
   la filière, indispensable, reconstitue déjà 19,5 % de la féminisation
   (ADR 0011).

## Options envisagées

1. **Lister les colonnes à exclure et prendre le reste** — écartée. Une liste
   noire admet par défaut : une colonne ajoutée par un millésime futur entrerait
   dans le modèle sans avoir été examinée. C'est exactement le mode de
   défaillance rencontré ailleurs dans ce projet (une référence de contrôle
   dérivée de l'objet contrôlé, qui laisse passer ce qu'elle est censée
   arrêter).
2. **Lister les colonnes lisibles sur la session prédite, et n'autoriser que
   celles-là** — retenue. Neuf colonnes seulement. Tout le reste n'est lisible
   que décalé d'une session, ou pas du tout. Une colonne nouvelle est exclue
   par défaut, et la chaîne s'arrête tant qu'elle n'a pas été classée.
3. **Décaler toutes les variables, y compris les attributs de catalogue** —
   écartée : la filière, le département ou le caractère sélectif d'une
   formation sont publiés dans le catalogue avant l'ouverture de la campagne.
   Les décaler ferait perdre les formations nouvelles, soit 5 % à 18 % du
   catalogue selon la paire de sessions, sans aucun gain de sûreté.
4. **Décaler de deux sessions plutôt qu'une** — écartée par défaut, conservée
   comme repli (voir la réserve sur la date de publication ci-dessous).

## Décision

### 1. La liste blanche de la session prédite — neuf colonnes

Ce sont les attributs de catalogue, publiés et consultables au moment où le
lycéen formule son vœu.

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

Aucune ne compte de vœux, de propositions, d'admis ni de rangs. Les compteurs
sont, par construction, hors d'atteinte sur la session prédite.

À quoi s'ajoutent les deux **dimensions de la cellule** — type de baccalauréat
et statut de boursier — qui ne viennent d'aucune colonne : elles sont portées
par la structure du label (ADR 0009), qui déplie chaque formation en six
cellules. Le modèle doit savoir quelle cellule il prédit, sans quoi il
prédirait une moyenne de six situations très différentes (écart médian de
8,5 points entre bac général et bac professionnel, jusqu'à 42,3 points en CPGE).

### 2. Les variables décalées d'une session — trente-cinq colonnes

Tous les compteurs de la session N-1 : capacité, vœux exprimés, candidats
classés, propositions, admis, académie d'origine des admis, calendrier des
propositions, rang du dernier appelé du premier groupe.

**Ce qui rend le décalage licite, vérifié et non supposé** : le fichier du
millésime 2024 porte, dans le catalogue du ministère, une dernière modification
au **16 janvier 2025**, c'est-à-dire à l'ouverture de la campagne 2025.

```
https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets/fr-esr-parcoursup_2024
  metas.default.modified -> 2025-01-16T19:10:50+00:00
```

**Réserve, et je préfère l'écrire que la taire** : cette métadonnée donne la
*dernière* modification, pas la première publication. Le millésime 2023 porte
une modification au 1er juillet 2024, postérieure à la phase de vœux 2024 — ce
qui prouve qu'un fichier peut être révisé après coup. Un modèle entraîné sur la
version révisée d'un fichier ne verrait donc pas exactement ce qu'un candidat
avait sous les yeux en janvier. L'écart n'est pas mesurable avec les seules
données dont je dispose : je le déclare comme une limite du protocole plutôt
que de l'ignorer.

### 3. Les variables de mention — retenues sous réserve, écartées par défaut

Huit colonnes : `acc_sansmention`, `acc_ab`, `acc_b`, `acc_tb`,
`acc_mention_nonrenseignee`, `acc_bg_mention`, `acc_bt_mention`,
`acc_bp_mention`.

Le baccalauréat 2020 a été délivré en contrôle continu : les mentions « très
bien » passent de 7,4 % à 11,8 % et les admis sans mention chutent de 43,4 % à
29,8 %, sans retour au niveau antérieur en 2021 (ADR 0012).

**La conséquence exacte, une fois le décalage appliqué** : ces variables sont
lues sur N-1, donc l'anomalie de 2020 et 2021 contamine les sessions cibles
**2021 et 2022** — soit **deux des quatre sessions d'entraînement**. Un modèle
qui les utiliserait apprendrait, sur la moitié de son entraînement, le mode
d'attribution du diplôme plutôt que la sélectivité de la formation.

Elles sont donc **écartées du jeu de référence**, et réintroduites seulement si
l'ablation démontre un gain. Ce n'est pas un abandon : c'est une hypothèse à
tester, avec son coût connu à l'avance.

### 4. Les exclusions définitives — soixante-treize colonnes

| Motif | Nb | Colonnes | Raison |
|---|---:|---|---|
| `interdite` | 4 | `pct_f`, `voe_tot_f`, `acc_tot_f`, `acc_term_f` | Ventilations par sexe. Invariant du projet : le genre ne sert qu'à l'audit a posteriori. Elles seraient aussi des fuites, mais c'est l'interdiction qui prévaut et se défend seule |
| `substitut` | 3 | `cod_uai`, `ville_etab`, `g_olocalisation_des_formations` | Voir l'arbitrage détaillé ci-dessous |
| `instabilite` | 22 | `regr_forma`, `rang_der_max`, `etablissement_id_paysage`, `composante_id_paysage`, `pct_etab_orig`, `taux_adm_psup{,_gen,_techno,_pro}`, `lib_grp4`, `ran_grp4`, `lib_grp5`, `ran_grp5`, `taux_acces_ens`, `part_acces_{gen,tec,pro}`, `list_com`, `lib_for_voe_ins`, `acc_tbf`, `pct_tbf`, `detail_forma2` | Disponibilité qui change à l'intérieur de la fenêtre 2020-2025 |
| `completude` | 10 | `detail_forma`, `acc_term`, `nb_voe_pp_internat`, `nb_cla_pp_internat`, `nb_cla_pp_pasinternat`, `acc_internat`, `lib_grp2`, `ran_grp2`, `lib_grp3`, `ran_grp3` | Renseignées sur 7 % à 47 % des lignes, et non aléatoirement |
| `hors_perimetre` | 10 | `nb_voe_pp_at`, `nb_voe_pc{,_bg,_bt,_bp,_at}`, `nb_cla_pp_at`, `nb_cla_pc`, `prop_tot_at`, `acc_at` | Décrivent les autres terminales et la phase complémentaire, deux populations que le label ne couvre pas |
| `redondance` | 23 | `dep_lib`, `g_ea_lib_vx`, `acc_pp`, `acc_pc`, `lib_grp1`, et l'ensemble des `pct_*` non interdits | Recalculables depuis une colonne retenue |
| `cardinalite` | 1 | `lib_comp_voe_ins` | 11 891 modalités pour 14 252 lignes : un quasi-identifiant, pas une variable |

**Sur trois de ces motifs, le détail compte.**

*Instabilité.* Le cas des deux colonnes `*_id_paysage` est le plus net :
absentes jusqu'en 2020, renseignées à environ 47 % de 2021 à 2024, **vides en
2025**. C'est le scénario qui dégrade un modèle en silence — entraîné sur une
période où la variable existe, évalué sur une période où elle a disparu, sans
qu'aucune erreur ne soit levée. La formulation exacte du motif importe : non
pas « ces colonnes sont vides » (un constat), mais « leur disponibilité change
entre ma période d'entraînement et ma période de test » (un argument).
`pct_etab_orig` relève du même motif pour une raison inverse : elle passe de
46 % à 100 % en 2023, non parce que la saisie s'améliore mais parce que la
règle de publication s'élargit à toutes les filières. `taux_acces_ens` et les
trois `part_acces_*` n'apparaissent qu'en 2022 : décalées, elles manqueraient
aux sessions cibles 2021 et 2022, comme les mentions.

*Complétude non aléatoire.* `acc_term` n'est pas une valeur manquante mais une
valeur **non applicable** : 0 % de manque pour les BTS et les CPGE, 100 %
ailleurs. Trois conséquences. L'imputer par la moyenne fabriquerait, pour
toutes les licences, une valeur calculée uniquement sur des BTS et des CPGE.
Retenir l'indicateur d'absence redonnerait la filière sous une autre forme,
sans l'avoir voulu. Et le combler sans le dire serait le seul choix
indéfendable des trois. Les colonnes d'internat relèvent du même mécanisme,
avec 7 % de renseignement.

*Redondance.* La règle appliquée est simple et vaut partout : **je retiens les
effectifs, j'écarte les pourcentages qui s'en déduisent.** Je l'ai vérifiée
plutôt que supposée, et la vérification a corrigé une erreur que j'avais
d'abord écrite : `pct_bours` n'est pas `acc_brs / acc_tot` — ce rapport s'en
écarte de 3,4 points en médiane et de 97,5 points au maximum. Le dénominateur
réel est `acc_neobac`, les néo-bacheliers, et non l'ensemble des admis.

Reconstitution exacte de chacune des dix-neuf colonnes de pourcentage,
session 2025, écart maximal de **0,500 point** dans tous les cas — c'est-à-dire
le seul arrondi au point entier :

| Dénominateur | Colonnes |
|---|---|
| `acc_neobac` | `pct_bours`, `pct_bg`, `pct_bt`, `pct_bp`, `pct_bg_mention`, `pct_bt_mention`, `pct_bp_mention`, `pct_tb`, `pct_b`, `pct_ab`, `pct_sansmention`, `pct_mention_nonrenseignee`, `pct_tbf`, `pct_aca_orig`, `pct_aca_orig_idf` |
| `acc_tot` | `pct_neobac`, `pct_f`, `pct_acc_debutpp`, `pct_acc_datebac`, `pct_acc_finpp` |

Les deux dénominateurs sont retenus, donc chaque ratio reste reconstructible.
La construction des variables recalculera ceux qui servent — un modèle à base
d'arbres ne forme pas spontanément un quotient, mais la référence doit déclarer
les colonnes *sources*, pas les variables dérivées. Cela évite qu'une même
information entre deux fois sous deux noms, ce qui fausserait la lecture des
valeurs de Shapley au moment de l'explicabilité.

La leçon est plus large que le cas : un pourcentage ne se rattache jamais à son
dénominateur par le nom. `pct_bours` et `pct_neobac` se ressemblent et ne se
rapportent pas à la même population.

### 5. L'arbitrage difficile : `cod_uai` et `ville_etab`

`cod_uai` est le **premier substitut du genre mesuré** — 28,9 % de pouvoir
explicatif net, après correction du nombre de modalités par permutation. C'est
aussi une variable que beaucoup jugeraient évidente à retenir : l'établissement
a une réputation, et la réputation pèse sur la sélectivité.

Je l'exclus, pour **deux raisons qui tiennent chacune séparément** :

- **Cardinalité.** 4 058 établissements. Le modèle mémoriserait
  l'établissement au lieu d'apprendre une règle transférable, et tout
  établissement absent de l'entraînement serait imprédictible. Ce risque existe
  indépendamment de toute considération d'équité.
- **Substitut.** C'est la plus forte association mesurée avec la féminisation
  des admis. Retenir la variable la plus problématique alors que son apport
  métier est déjà porté par ailleurs serait un mauvais arbitrage.

**Ce qui rend la décision moins confortable qu'elle n'en a l'air, et que je
dois dire.** L'information d'établissement ne disparaît pas complètement : les
variables décalées sont attachées à la formation, donc à son établissement, et
en portent une partie. Exclure `cod_uai` réduit le canal le plus direct ; cela
ne rend pas le modèle aveugle à l'établissement. C'est précisément pourquoi le
dispositif d'équité de l'ADR 0011 ne repose pas sur l'exclusion seule, et
pourquoi son niveau 2 — la mesure des substituts — doit être rejoué sur ce jeu
de variables une fois construit, avec la même correction par permutation.

`ville_etab` (10,2 % net) est plus simple à trancher : son apport métier est
faible — le département et l'académie sont retenus, et la région aussi — et
elle est de surcroît absente de la session 2020, soit un quart de
l'entraînement. `g_olocalisation_des_formations` la suit par cohérence : ce
sont les coordonnées géographiques exactes, donc une version plus fine encore
de la même information. Exclure la ville et garder ses coordonnées aurait été
une exclusion de façade.

### 6. Une conséquence que je n'avais pas anticipée

`prop_tot_*` ventilé par type de baccalauréat n'existe pas avant 2020
(ADR 0012). Décalé d'une session, il **manque donc pour la session cible
2020**, dont le fichier N-1 est le millésime 2019.

Autrement dit, la variable la plus prédictive du jeu — le taux d'admission
observé de la même cellule l'année précédente — est **absente pour un quart des
sessions d'entraînement**. Deux conséquences :

- ces valeurs restent **manquantes de façon explicite**, sans imputation :
  LightGBM traite nativement l'absence, et une imputation reviendrait ici à
  fabriquer un antécédent qui n'existe pas ;
- la **baseline** de l'ADR 0012 (« le taux de la session précédente ») n'est
  mesurable que sur 2021-2025. Le plancher de comparaison devra être annoncé
  sur ce périmètre, et non sur l'ensemble de l'entraînement.

Je n'écarte pas 2020 pour autant : l'ADR 0012 l'a conservée sur une mesure de
la cible, et l'absence d'un antécédent n'est pas une anomalie de la cible.

### 7. Où vit la décision

La classification des 128 colonnes est écrite dans **`configs/base.yaml`,
section `modele.variables`**, et typée par `VariablesConfig` dans
`src/edumatch/config.py`.

Trois raisons de préférer ce support à un document ou à une constante en dur :

- la configuration est déjà le lieu déclaré des paramètres métier (ADR 0003) ;
  un second mécanisme de référence en concurrencerait un existant ;
- elle est **vérifiable par un test**, ce qu'un tableau en markdown n'est pas ;
- elle **échoue à la lecture** si une colonne relève de deux catégories à la
  fois — la faute qui rouvrirait la fuite.

Trois contrôles s'appuient dessus, dans `tests/data/test_variables_reference.py`
et `tests/unit/test_config_validation.py`. Ils lisent les échantillons
versionnés, donc tournent sans les fichiers bruts complets :

1. toute colonne citée existe réellement dans un millésime — une faute de
   frappe serait sinon lue comme une colonne vide, sans erreur ;
2. toute colonne d'un millésime est classée — un millésime futur qui ajoute une
   colonne **fait échouer la suite** tant que son sort n'est pas décidé ;
3. aucune colonne de résultat de campagne ne figure dans la liste blanche de la
   session prédite.

Les quatre contrôles ont été vérifiés par mutation, et non par relecture :
colonne mal orthographiée, colonne retirée du classement, `voe_tot` déplacé
vers la liste blanche, split rouvert à 2018. Les quatre mutations font échouer
le test qui les vise, et lui seul.

## Conséquences

- Le jeu de référence compte **9 colonnes lues sur la session prédite,
  35 décalées, 2 dimensions de cellule**, et 8 colonnes de mention en réserve.
  C'est peu au regard des 128 colonnes disponibles, et c'est voulu : chaque
  variable retenue doit pouvoir être justifiée une par une devant le jury.
- La construction des variables lira cette section ; elle n'a pas à réinterpréter
  le présent document.
- Le niveau 2 du dispositif d'équité (ADR 0011) doit être rejoué sur ce jeu
  final, sur les variables décalées cette fois, et non plus sur les seules
  variables catégorielles de la session courante.
- L'ablation devra mesurer trois retraits, et pas seulement l'apport de Sirene :
  les mentions, `cod_uai`, et les variables décalées dans leur ensemble.

**Ce qui ferait reconsidérer**, par ordre de probabilité :

| Décision | Seuil de reconsidération |
|---|---|
| Mentions écartées | Un gain d'erreur absolue moyenne pondérée supérieur à 0,01 en ablation, mesuré sur les seules sessions cibles non contaminées (2023 et au-delà) |
| `cod_uai` exclu | Une perte mesurée en ablation, traitée alors par encodage par la cible calculé sur les seuls plis d'entraînement — jamais par réintroduction de l'identifiant brut |
| Décalage d'une session | Si l'écart entre la version révisée et la version publiée en janvier d'un millésime devenait mesurable et important, passage à un décalage de deux sessions |
| Colonnes exclues pour instabilité | Deux millésimes consécutifs de disponibilité stable après 2025 |
| Liste blanche de neuf colonnes | La publication, par le ministère, d'un fichier de catalogue distinct du fichier de résultats — il lèverait l'ambiguïté sur ce qui est réellement affiché en janvier, `capa_fin` en particulier |

## Ce que je n'ai pas tranché

**`capa_fin`.** Parcoursup affiche un nombre de places sur chaque fiche pendant
la campagne, mais la colonne du fichier de résultats s'appelle « capacité
finale », et rien dans les fichiers dont je dispose ne prouve qu'elle vaut la
capacité affichée en janvier. Par prudence, je la classe en variable
**décalée** : la capacité de l'an dernier est certainement connue, celle de
l'année en cours ne l'est peut-être pas sous cette forme.

Trancher demande une vérification que les données ne contiennent pas — comparer
la fiche affichée pendant la campagne au fichier publié ensuite. Tant que je ne
l'ai pas faite, je préfère la version prudente à la version avantageuse. Si les
deux valeurs coïncident, `capa_fin` passe en liste blanche et le gain est réel :
c'est le dénominateur direct de la tension, mon meilleur prédicteur.

**Reproduit par** : les quatre carnets de `notebooks/` pour les mesures citées,
et la commande ci-dessous pour l'inventaire des 128 colonnes et de leur
disponibilité par session.

```bash
python - <<'EOF'
import csv, sys
sys.path.insert(0, "src")
from edumatch.config import load_settings

s = load_settings("prod")
raw = s.raw_dir / "parcoursup"
millesimes = s.donnees.parcoursup.millesimes

def entetes(annee):
    with open(raw / f"parcoursup_{annee}.csv", encoding="utf-8-sig") as f:
        return list(csv.reader(f, delimiter=";"))[0]

union = []
for annee in millesimes:
    for colonne in entetes(annee):
        if colonne not in union:
            union.append(colonne)

print("colonnes vues au moins une fois :", len(union))
print("communes aux huit sessions      :",
      len(set.intersection(*(set(entetes(a)) for a in millesimes))))
print("classées dans modele.variables  :", len(s.modele.variables.colonnes_sources))
EOF
```
