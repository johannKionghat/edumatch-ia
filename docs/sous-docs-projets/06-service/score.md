# Le score de matching — trois termes (E28)

**Critère servi** : Bloc 4, 4.1 (algorithme adapté), 4.16 (ablation, apport
Sirene) · **Source** : `src/edumatch/matching/score.py`,
`affinite.py`, `debouches.py`, `agregat_sirene_debouches.py` ·
**Commit** : `8b88b2a` · **Dernière revue** : 2026-09-01.

```
score = affinité  ×  accessibilité  ×  débouchés
        règles       MODÈLE APPRIS    agrégats Sirene
        (requête)    (E22, LightGBM)  (aucun apprentissage)
```

Un seul terme est appris — l'accessibilité, produite par le modèle entraîné
en E22. Les deux autres sont des règles déclaratives (affinité) et un
dénombrement (débouchés). C'est le principe d'architecture du projet tout
entier, retrouvé au niveau du score final.

## Le caractère multiplicatif

Un terme nul supprime la recommandation, testé séparément pour les trois
termes (`tests/unit/test_matching_score.py::test_un_terme_nul_supprime_le_score`).
Une formation inaccessible, sans débouché mesuré, ou hors des préférences
exprimées ne doit jamais apparaître, même si les deux autres termes sont
excellents.

Effet à connaître, pas à masquer : trois termes à 0,5 chacun donnent un
score de 0,125, pas 0,5. Un score multiplicatif punit sévèrement une
formation moyenne sur les trois critères à la fois. `ScoreFormation` expose
donc toujours les trois termes séparément à côté du score global, pour
qu'un lecteur ne prenne jamais 0,125 pour un score bas sur un seul facteur.

## Le terme accessibilité et sa mise en garde

Le modèle LightGBM (E22) n'est pas contraint à [0, 1] par construction ;
`borner_accessibilite` écrête toute prédiction dans cet intervalle — la
correction naturelle du label qu'il approxime (ADR 0009), pas une mise à
l'échelle arbitraire.

**Ce terme n'a pas encore battu son plancher.** Mesuré sur le test 2025
(`04-modele/evaluation.md`) : MAE pondérée 0,0758 pour le modèle contre
0,0701 pour la baseline, à couverture égale — le modèle reste au-dessus du
plancher qu'il doit battre, et sa calibration s'y dégrade également.
`MISE_EN_GARDE_ACCESSIBILITE` est portée par chaque `ScoreFormation`
produit — écrite là où le terme est consommé, pas seulement documentée.

## Le terme débouchés : l'obstacle et la mesure qui a tranché

`referentiel/naf_rome_formation.py` (E18) relie une formation IDÉO à une
division NAF via son code RNCP. Aucun des huit millésimes Parcoursup ne
porte de code RNCP, NSF ou ROME — vérifié par inspection des colonnes : la
chaîne ne rattache aucune formation Parcoursup à une activité NAF par la
clé. Le seul rapprochement possible est un appariement textuel des
libellés, et il est mesuré, pas supposé.

**La mesure**, sur `data/processed/parcoursup/variables.parquet` (440 030
lignes) et le référentiel IDÉO complet, après exclusion des formations
IDÉO sans code RNCP renseigné et des libellés ambigus : l'appariement exact
couvre **7 libellés distincts sur 712** (1,0 %), soit **6 017 lignes sur
440 030** (1,4 %). Les sept correspondances ont été relues à la main :
diplôme de comptabilité et de gestion, deux certificats de capacité
(orthoptiste, orthophoniste), prothésiste dentaire, DTS imagerie médicale,
deux intitulés de cadre technique de la mer — des diplômes d'État très
normés, dont la forme ne varie quasiment pas d'une source à l'autre.
C'est précisément ce qui explique aussi bien la réussite de ces sept
appariements que l'échec des autres, aux libellés rédigés librement par
chaque établissement.

**Pour les 98,6 % de lignes restantes, le terme est marqué explicitement
indisponible** — jamais mis à zéro en silence, jamais deviné. Le score se
réduit alors à affinité × accessibilité, et le motif exact voyage avec le
résultat : un conseiller voit pourquoi, au lieu d'un nombre creux.

**Alternatives écartées** :
- un rapprochement par la seule filière (`fili`, 12 valeurs) : trop
  grossier, il aurait attaché le même débouché à une licence de
  mathématiques et à une licence d'arts plastiques ;
- un appariement approché par distance d'édition : non tenté faute d'être
  mesuré, déclaré comme piste ouverte plutôt que présenté comme résolu.

## Le grain territorial : k-anonymat et filtre de diffusion

`matching/agregat_sirene_debouches.py` construit l'agrégat consommé par le
terme de débouchés au grain **département × division NAF** — jamais au
grain commune, qui n'est qu'un calcul intermédiaire jamais exposé. Deux
protections, appliquées ici et vérifiées, qui ne l'étaient pas au stade de
l'agrégat brut (E17) :

1. **k-anonymat, k = 5**, seuil arrêté par la gouvernance
   (`05-gouvernance/risques.md`, risque R2) au grain département × NAF —
   contre 90,6 % des cellules et 46,9 % des établissements perdus pour la
   même protection au grain commune ;
2. **le filtre `diffusible`**, déclaré dans `configs/base.yaml` mais non
   appliqué par le job d'agrégation Spark de l'E17 (voir
   `03-pipeline/agregats-sirene.md`), l'est ici : **20 488 établissements
   actifs-employeurs** portant un statut non diffusible sont exclus du
   comptage, sur les 2 423 308 rattachés à une commune — un ordre de
   grandeur cohérent avec les 20 501 établissements non diffusibles
   mesurés par ailleurs sur l'ensemble du stock (E17).

Le module ne renvoie jamais un effectif d'établissements sous le seuil de
k-anonymat, même pour distinguer un zéro réel d'une cellule supprimée : les
deux cas sont représentés par un simple indicateur d'existence, jamais par
l'effectif intermédiaire lui-même.

## Le genre, absent par construction

Le genre n'entre ni dans le profil candidat requis par l'API, ni dans
aucun des trois termes du score — vérifié par introspection au chargement
du module et par test. Il ne sert qu'à l'audit d'équité a posteriori
(`04-modele/equite.md`).

---

## Ce qui reste ouvert

- La couverture du terme débouchés (1,4 %) est le principal facteur
  limitant de la valeur du score pour la majorité des formations —
  reporté dans `reste-a-faire.md`.
- Un appariement approché (distance d'édition, ou croisement du
  `code_nsf` IDÉO avec `fili`) resterait à mesurer avant de conclure
  qu'aucune amélioration de couverture n'est possible.

*Dernière mise à jour : 2026-09-01, commit `8b88b2a`.*
