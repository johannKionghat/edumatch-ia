"""Définitions partagées de l'agrégat Sirene commune x NAF (E17) — sans dépendance lourde.

Ce module ne dépend ni de PySpark ni de Polars : deux moteurs implémentent la
même agrégation (`sirene_agregats.py` pour Spark, `sirene_agregats_polars.py`
pour Polars — l'arbitrage entre les deux est documenté dans ce dernier), et
partagent depuis ici tout ce qui doit rester identique d'un moteur à l'autre :
le grain, la liste des colonnes lues, la table de correspondance des tranches
d'effectifs et la lecture des filtres de configuration. Sans ce partage, un
changement de règle métier appliqué à un seul des deux moteurs ferait diverger
silencieusement leurs résultats — exactement ce que la comparaison Spark
contre Polars (§ moteur, dans `sirene_agregats_polars.py`) doit exclure.

## Le grain

    (codeCommuneEtablissement, activitePrincipaleEtablissement)

une ligne = un couple (commune, code NAF). Le code NAF retenu est celui de la
nomenclature NAF2008 (`NAFRev2`) : mesuré sur le fichier complet
(43 896 818 lignes), 2 436 623 des 2 436 624 établissements actifs et
employeurs y sont déjà rattachés (un seul est encore en `NAF1993`) — la
double nomenclature n'est donc pas un problème pratique pour ce grain
aujourd'hui, à la différence de la couverture de la NAF 2025 (voir plus bas).
Le futur code NAF 2025 (`activitePrincipaleNAF25Etablissement`) n'est pas
utilisé comme clé de regroupement : au 01/08/2026 il n'est renseigné que sur
18 638 750 des 43 896 818 lignes du fichier complet (42,5 %), mais sur
2 436 610 des 2 436 624 actifs-employeurs (99,9994 %) — sa couverture est
mesurée et exposée en sortie (`nb_naf25_renseigne`) pour que la réconciliation
NAF -> ROME -> formation de l'étape suivante (E18) sache, sans le
redécouvrir, sur quelle proportion de chaque cellule elle peut s'appuyer.

## Ce qui est compté, et pourquoi les fermetures ne sont pas exclues

Le filtre de `configs/base.yaml` (`donnees.sirene.filtres`) restreint la
notion de débouché à l'établissement actif et employeur — c'est le compte
principal, `nb_actifs_employeurs`, qui doit reproduire exactement le chiffre
déjà mesuré (2 436 624, avant exclusion des lignes sans commune ; 2 423 308
après : 13 316 actifs employeurs, soit un sur 183, n'ont pas de commune
connue. Vérifié plutôt que supposé : les 13 316 portent tous un
`codePaysEtrangerEtablissement` renseigné — ce sont des établissements
domiciliés à l'étranger, hors du grain territorial de ce projet).
Mais un secteur qui perd des employeurs a une dynamique différente d'un
secteur qui en gagne, même à effectif actif identique : exclure les
cessations biaiserait la mesure de « débouchés » vers les seuls territoires
en croissance. `nb_fermes_employeurs` compte donc, à côté, les établissements
**fermés qui étaient employeurs** (état `F`, `caractereEmployeurEtablissement
= 'O'`) — 4 900 762 sur le fichier complet, près du double des actifs : ce
n'est pas anecdotique. Ce deuxième compte n'est pas piloté par
`filtres.etat_administratif` (qui ne retient que la valeur `A`) : il est
délibérément ajouté à côté, pas à la place.

`filtres.diffusible` est déclaré dans la configuration mais **n'est pas
appliqué ici** : l'appliquer demanderait de lire une dixième colonne
(`statutDiffusionEtablissement`), absente des neuf colonnes déjà arrêtées à
l'E06 et reprises telles quelles par le contrôle qualité (E14,
`edumatch.quality.sirene.COLONNES_UTILES`). Mesuré sur le fichier complet :
20 501 établissements actifs-employeurs sur 2 436 624 (0,84 %) portent un
statut non diffusible (`P`), et seulement 13 d'entre eux ont par ailleurs une
commune manquante — le filtre n'est donc pas redondant avec l'exclusion des
communes nulles, il retirerait bien 0,84 % de lignes supplémentaires. C'est
un écart assumé et chiffré, pas une omission silencieuse : une décision à
revoir explicitement si la précision au niveau commune devient sensible à ce
seuil, ou si une dixième colonne est de toute façon ajoutée pour une autre
raison.
"""

from __future__ import annotations

from dataclasses import dataclass

from edumatch.config import Settings
from edumatch.quality.sirene import COLONNES_UTILES

# Les 9 colonnes utiles, réexportées depuis le contrôle qualité (E14) : même
# projection pour valider le fichier et pour l'agréger, une seule liste à
# tenir à jour.
COLONNES_PROJECTION: tuple[str, ...] = COLONNES_UTILES

COLONNE_COMMUNE = "codeCommuneEtablissement"
COLONNE_NAF = "activitePrincipaleEtablissement"
COLONNE_NAF25 = "activitePrincipaleNAF25Etablissement"
COLONNE_ETAT = "etatAdministratifEtablissement"
COLONNE_EMPLOYEUR = "caractereEmployeurEtablissement"
COLONNE_TRANCHE = "trancheEffectifsEtablissement"
COLONNE_DATE_CREATION = "dateCreationEtablissement"

GRAIN: tuple[str, ...] = (COLONNE_COMMUNE, COLONNE_NAF)

VALEUR_EMPLOYEUR = "O"
ETAT_ACTIF = "A"
ETAT_FERME = "F"

# Nombre d'années en deçà duquel un établissement actif-employeur est compté
# comme « récemment créé » (`nb_crees_moins_3ans`) : signal de dynamique,
# distinct de l'âge moyen. Pas de source externe à ce seuil — c'est un ordre
# de grandeur usuel (un cycle de scolarité post-bac court) plutôt qu'une
# valeur mesurée ; à revoir si l'usage aval (E18, matching) en réclame un
# autre.
SEUIL_ANNEES_CREATION_RECENTE = 3

# Codes INSEE de tranche d'effectifs salariés (documentation Sirene),
# regroupés en six paliers pour la ventilation exposée en sortie. `NN` est un
# code documenté (« non renseignée »), jamais une valeur manquante au sens
# d'une anomalie — déjà noté ainsi par le contrôle qualité (E14).
TRANCHES_VERS_PALIER: dict[str, str] = {
    "00": "0",
    "01": "1_9",
    "02": "1_9",
    "03": "1_9",
    "11": "10_49",
    "12": "10_49",
    "21": "50_249",
    "22": "50_249",
    "31": "50_249",
    "32": "250_plus",
    "41": "250_plus",
    "42": "250_plus",
    "51": "250_plus",
    "52": "250_plus",
    "53": "250_plus",
    "NN": "non_renseignee",
}

PALIERS_EFFECTIFS: tuple[str, ...] = ("0", "1_9", "10_49", "50_249", "250_plus", "non_renseignee")

# Colonnes de la table agrégée écrite en sortie, dans l'ordre. `date_reference`
# est répétée sur chaque ligne (plutôt que tenue à part dans un fichier de
# métadonnées) : la table reste auto-descriptive sur la date par rapport à
# laquelle `age_moyen_annees` et `nb_crees_moins_3ans` ont été calculés, sans
# quoi la relire un an plus tard sans son contexte de calcul la rendrait
# ininterprétable.
COLONNES_SORTIE: tuple[str, ...] = (
    COLONNE_COMMUNE,
    COLONNE_NAF,
    "nb_actifs_employeurs",
    "nb_fermes_employeurs",
    *[f"nb_tranche_{palier}" for palier in PALIERS_EFFECTIFS],
    "nb_naf25_renseigne",
    "age_moyen_annees",
    "nb_crees_moins_3ans",
    "date_reference",
)


@dataclass(frozen=True)
class FiltresSirene:
    """Filtres résolus depuis `donnees.sirene.filtres`, sous la forme attendue par les deux moteurs."""

    etat_actif: str
    valeur_employeur: str
    filtrer_employeur: bool


def resoudre_filtres(settings: Settings) -> FiltresSirene:
    """Traduit `SireneFiltresConfig` en valeurs directement comparables aux colonnes du fichier.

    `caractere_employeur` est un booléen de configuration : `True` restreint
    aux établissements employeurs (`'O'`), `False` désactive ce filtre (les
    trois valeurs observées — `'O'`, `'N'`, absente — sont alors conservées).
    Il ne signifie jamais « ne garder que les non-employeurs » : un booléen
    n'a pas de troisième état pour l'exprimer, et rien dans le projet n'a
    besoin de cette lecture inverse.
    """
    filtres = settings.donnees.sirene.filtres
    return FiltresSirene(
        etat_actif=filtres.etat_administratif,
        valeur_employeur=VALEUR_EMPLOYEUR,
        filtrer_employeur=filtres.caractere_employeur,
    )
