"""Configuration centralisée du projet, typée avec Pydantic.

Aucun chemin ni seuil ne doit apparaître en dur ailleurs dans le code : tout
paramètre métier vient de `configs/*.yaml`, tout secret vient de
l'environnement.

Précédence de résolution (du plus faible au plus fort) :

    configs/base.yaml  <  configs/{env}.yaml  <  fichier .env  <  variable
    d'environnement exportée par le shell ou l'orchestrateur

`data/` fait partie du dépôt : par défaut, `EDUMATCH_DATA_ROOT` pointe donc
vers `<dépôt>/data`, sauf `data/samples/` qui y reste toujours, quelle que
soit cette variable. Les arbitrages détaillés — pourquoi Pydantic Settings,
pourquoi cette précédence à trois couches, pourquoi `EDUMATCH_DATA_ROOT` est
pilotable malgré ce défaut — sont dans
`docs/sous-docs-projets/adr/0003-configuration-centralisee.md`.

Seule exception assumée à « aucun chemin en dur » : le défaut de
`_defaut_racine_donnees()`. Ce n'est pas un paramètre métier venant de
`configs/*.yaml`, c'est le comportement du programme en l'absence de toute
configuration — voir l'ADR.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, get_args

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

# Racine du dépôt : src/edumatch/config.py -> src/edumatch -> src -> edumatch-ia
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = PROJECT_ROOT / "configs"

# Source de vérité unique pour les environnements valides : le type Literal
# utilisé par Settings.env. ENVIRONNEMENTS_VALIDES en est dérivé, plutôt que
# recopié, pour qu'ajouter un environnement ne demande qu'une modification.
EnvironnementValide = Literal["dev", "staging", "prod"]
ENVIRONNEMENTS_VALIDES: tuple[str, ...] = get_args(EnvironnementValide)


class ConfigurationError(RuntimeError):
    """Erreur de configuration explicite : un fichier, un champ, une raison.

    Levée plutôt que de laisser une valeur par défaut masquer un problème.
    """


# ─── Modèles reflétant configs/base.yaml ────────────────────────────────────


class _Strict(BaseModel):
    """Base commune : rejette tout champ inconnu, interdit la mutation.

    Un champ inconnu dans un YAML est presque toujours une faute de frappe ou
    une clé oubliée après renommage. Le signaler au démarrage coûte moins cher
    que de le découvrir en production.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjetConfig(_Strict):
    nom: str
    version: str


class ParcoursupConfig(_Strict):
    millesimes: list[int] = Field(min_length=1)
    effectif_minimal_cellule: int = Field(ge=1)
    # Un identifiant de jeu de données par millésime : sa forme (tiret,
    # souligné, ou aucun suffixe pour le millésime courant) change d'une
    # année à l'autre, aucune règle ne permet de la déduire.
    identifiants: dict[int, str]
    url_export_gabarit: str  # gabarit de l'URL d'export CSV, {identifiant} à substituer
    delimiteur: str

    @model_validator(mode="after")
    def _identifiants_couvrent_les_millesimes(self) -> "ParcoursupConfig":
        """Chaque millésime déclaré doit avoir son identifiant (l'inverse est toléré, cas de dev.yaml)."""
        manquants = set(self.millesimes) - set(self.identifiants)
        if manquants:
            raise ValueError(
                "donnees.parcoursup.identifiants ne couvre pas le(s) "
                f"millésime(s) {sorted(manquants)} déclaré(s) dans "
                "donnees.parcoursup.millesimes."
            )
        return self

    @field_validator("url_export_gabarit")
    @classmethod
    def _gabarit_contient_le_parametre_identifiant(cls, valeur: str) -> str:
        if "{identifiant}" not in valeur:
            raise ValueError(
                "donnees.parcoursup.url_export_gabarit doit contenir le "
                "paramètre '{identifiant}' à substituer."
            )
        return valeur


class SireneFiltresConfig(_Strict):
    etat_administratif: str
    caractere_employeur: bool
    diffusible: bool


class SireneConfig(_Strict):
    fichiers: list[str] = Field(min_length=1)
    filtres: SireneFiltresConfig
    # Sirene n'a pas de gabarit d'URL fixe comme Parcoursup : les liens de
    # téléchargement changent chaque mois (nouveau stock republié). Seul le
    # jeu de données et le gabarit de l'API du catalogue sont stables ; l'URL
    # de chaque fichier est résolue à l'exécution en interrogeant ce catalogue.
    jeu_de_donnees: str
    url_catalogue_gabarit: str  # gabarit vers l'API data.gouv, {jeu_de_donnees} à substituer

    @field_validator("url_catalogue_gabarit")
    @classmethod
    def _gabarit_contient_le_parametre_jeu_de_donnees(cls, valeur: str) -> str:
        if "{jeu_de_donnees}" not in valeur:
            raise ValueError(
                "donnees.sirene.url_catalogue_gabarit doit contenir le "
                "paramètre '{jeu_de_donnees}' à substituer."
            )
        return valeur


class IdeoJeuConfig(_Strict):
    """Un jeu ONISEP (IDÉO) : une URL de téléchargement fixe, ses conventions et sa licence.

    Chaque jeu porte sa propre licence par prudence, même si les quatre valent
    aujourd'hui ODbL : c'est le manifeste, alimenté depuis ce champ, qui
    permettra en E18 de savoir si une table dérivée est contaminée par le
    partage à l'identique obligatoire de l'ODbL, sans relire la documentation.
    """

    url: str
    encodage: str
    delimiteur: str
    licence: str


class IdeoConfig(_Strict):
    # Clé = nom du jeu (formations, metiers, structures_secondaire,
    # structures_superieur) : la même clé sert de nom de fichier en sortie.
    jeux: dict[str, IdeoJeuConfig] = Field(min_length=1)


class RncpConfig(_Strict):
    """Résolution de l'export RNCP/RS du jour, republié chaque jour par France Compétences.

    Comme Sirene, aucune URL de fichier n'est codée en dur : seuls
    l'identifiant du jeu de données et le gabarit de l'API du catalogue le
    sont, l'URL de l'archive du jour est résolue à l'exécution.
    """

    jeu_de_donnees: str
    url_catalogue_gabarit: str  # gabarit vers l'API data.gouv, {jeu_de_donnees} à substituer
    prefixe_ressource: str  # préfixe du titre des ressources d'export quotidien
    format_ressource: str  # "zip" : l'export est distribué sous forme d'archive
    nom_fichier_gabarit: str  # motif (glob) du CSV standard à l'intérieur de l'archive
    # E18 : deuxième membre de la même archive, la correspondance fiche RNCP
    # -> codes ROME (voir ingestion/_referentiels_rncp.telecharger_rome).
    nom_fichier_rome_gabarit: str
    encodage: str
    delimiteur: str
    licence: str

    @field_validator("url_catalogue_gabarit")
    @classmethod
    def _gabarit_contient_le_parametre_jeu_de_donnees(cls, valeur: str) -> str:
        if "{jeu_de_donnees}" not in valeur:
            raise ValueError(
                "donnees.referentiels.rncp.url_catalogue_gabarit doit contenir "
                "le paramètre '{jeu_de_donnees}' à substituer."
            )
        return valeur


class FranceTravailConfig(_Strict):
    """Résolution de la table de correspondance ROME/NAF de France Travail (E18).

    Contrairement à Sirene et RNCP, ce n'est pas un export périodique : la
    ressource existe en permanence dans le catalogue data.gouv, mais son nom
    de fichier change à chaque révision du ROME (ex. suffixe "juin-2026"),
    d'où la résolution par sous-chaîne de titre plutôt qu'un nom fixe —
    aucune URL de fichier n'est codée en dur, seul l'identifiant du jeu de
    données et le gabarit du catalogue le sont.
    """

    jeu_de_donnees: str
    url_catalogue_gabarit: str  # gabarit vers l'API data.gouv, {jeu_de_donnees} à substituer
    sous_chaine_titre_ressource: str  # sous-chaîne du titre identifiant la ressource ROME/NAF
    format_ressource: str  # "xlsx" : seul format publié pour cette table
    licence: str

    @field_validator("url_catalogue_gabarit")
    @classmethod
    def _gabarit_contient_le_parametre_jeu_de_donnees(cls, valeur: str) -> str:
        if "{jeu_de_donnees}" not in valeur:
            raise ValueError(
                "donnees.referentiels.france_travail.url_catalogue_gabarit doit "
                "contenir le paramètre '{jeu_de_donnees}' à substituer."
            )
        return valeur


class ReferentielsConfig(_Strict):
    ideo: IdeoConfig
    rncp: RncpConfig
    france_travail: FranceTravailConfig


class EchantillonsTestConfig(_Strict):
    """Tailles cibles des échantillons versionnés de `data/samples/` (E08).

    Distinct de `DonneesConfig.echantillonnage` : celui-ci réduit le volume
    réellement traité en dev (une fraction du flux de production), alors que
    `data/samples/` est un jeu figé, versionné dans le dépôt, qui ne sert
    qu'à faire tourner les tests sans les 4,6 Go de sources complètes. Les
    deux mécanismes ne partagent ni le code ni le cycle de vie.
    """

    lignes_par_millesime_parcoursup: int = Field(ge=1)
    lignes_par_fichier_sirene: int = Field(ge=1)
    lignes_par_jeu_ideo: int = Field(ge=1)
    lignes_rncp: int = Field(ge=1)
    # Taille des lots lus par pyarrow.iter_batches sur les fichiers Sirene :
    # borne la mémoire du script de génération, indépendamment de la taille
    # du fichier source (2,2 Go pour le plus gros).
    taille_lot_sirene: int = Field(ge=1)


class DonneesConfig(_Strict):
    parcoursup: ParcoursupConfig
    sirene: SireneConfig
    referentiels: ReferentielsConfig
    echantillons_test: EchantillonsTestConfig
    # Uniquement présent en dev, pour itérer sur un échantillon.
    echantillonnage: float | None = Field(default=None, gt=0, le=1)


class SplitConfig(_Strict):
    entrainement: list[int] = Field(min_length=1)
    validation: list[int] = Field(min_length=1)
    test: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def _millesimes_disjoints(self) -> "SplitConfig":
        """Empêche la fuite de données : aucun millésime dans deux jeux à la fois.

        Le split est temporel (invariant du projet) : entraînement, validation
        et test doivent être des ensembles de millésimes disjoints, faute de
        quoi une session serait apprise puis réutilisée pour l'évaluer.
        """
        ensembles = {
            "entrainement": set(self.entrainement),
            "validation": set(self.validation),
            "test": set(self.test),
        }
        noms = list(ensembles)
        for i, nom_a in enumerate(noms):
            for nom_b in noms[i + 1 :]:
                intersection = ensembles[nom_a] & ensembles[nom_b]
                if intersection:
                    raise ValueError(
                        f"modele.split.{nom_a} et modele.split.{nom_b} partagent "
                        f"le(s) millésime(s) {sorted(intersection)} : le split "
                        "doit être temporel et strictement disjoint."
                    )
        if max(self.entrainement) >= min(self.validation):
            raise ValueError(
                "modele.split : le dernier millésime d'entraînement doit précéder "
                "le premier millésime de validation."
            )
        if max(self.validation) >= min(self.test):
            raise ValueError(
                "modele.split : le dernier millésime de validation doit précéder "
                "le premier millésime de test."
            )
        return self


class HyperparametresConfig(_Strict):
    num_leaves: int = Field(ge=2)
    max_depth: int = Field(ge=1)
    learning_rate: float = Field(gt=0, le=1)
    min_child_samples: int = Field(ge=1)
    reg_alpha: float = Field(ge=0)
    reg_lambda: float = Field(ge=0)
    n_estimators: int = Field(ge=1)
    early_stopping_rounds: int = Field(ge=1)


MotifExclusion = Literal[
    "interdite",
    "substitut",
    "instabilite",
    "cardinalite",
    "completude",
    "hors_perimetre",
    "redondance",
]


class VariablesConfig(_Strict):
    """Classement de chaque colonne source Parcoursup, décidé une fois et pour toutes.

    La protection contre la fuite repose sur une **liste blanche** :
    `session_courante` énumère les seules colonnes lues sur la session que le
    modèle prédit. Toute autre colonne n'est lisible que décalée d'une
    session. Une colonne nouvelle, non classée, est donc exclue par défaut —
    l'inverse d'une liste noire, qui l'admettrait en silence.

    Les arbitrages, colonne par colonne, sont dans
    `docs/sous-docs-projets/adr/0013-decision-des-variables.md`.
    """

    cles: list[str] = Field(min_length=1)
    dimensions_cellule: list[str] = Field(min_length=1)
    session_courante: list[str] = Field(min_length=1)
    decalees: list[str] = Field(min_length=1)
    decalees_sous_reserve: list[str]
    exclues: dict[str, MotifExclusion] = Field(min_length=1)

    @property
    def colonnes_sources(self) -> set[str]:
        """Toutes les colonnes du fichier Parcoursup citées, quel que soit leur sort.

        `dimensions_cellule` en est exclu : ces deux entrées décrivent la
        structure du label, pas des colonnes du fichier.
        """
        return (
            set(self.cles)
            | set(self.session_courante)
            | set(self.decalees)
            | set(self.decalees_sous_reserve)
            | set(self.exclues)
        )

    @model_validator(mode="after")
    def _aucune_colonne_dans_deux_categories(self) -> "VariablesConfig":
        """Une colonne a un sort et un seul : retenue, décalée, sous réserve, ou exclue.

        Sans cette vérification, une colonne pourrait figurer à la fois dans
        `session_courante` et dans `exclues` — la construction des variables
        lirait alors sur la session prédite une colonne annoncée comme
        écartée, exactement la fuite que ce classement doit empêcher.
        """
        categories = {
            "cles": list(self.cles),
            "dimensions_cellule": list(self.dimensions_cellule),
            "session_courante": list(self.session_courante),
            "decalees": list(self.decalees),
            "decalees_sous_reserve": list(self.decalees_sous_reserve),
            "exclues": list(self.exclues),
        }
        for nom, valeurs in categories.items():
            doublons = {v for v in valeurs if valeurs.count(v) > 1}
            if doublons:
                raise ValueError(
                    f"modele.variables.{nom} contient des doublons : {sorted(doublons)}."
                )
        noms = list(categories)
        for i, nom_a in enumerate(noms):
            for nom_b in noms[i + 1 :]:
                commun = set(categories[nom_a]) & set(categories[nom_b])
                if commun:
                    raise ValueError(
                        f"modele.variables.{nom_a} et modele.variables.{nom_b} "
                        f"partagent la ou les colonnes {sorted(commun)} : une "
                        "colonne doit relever d'une seule catégorie."
                    )
        return self


class ModeleConfig(_Strict):
    type: str
    objectif: str
    ponderation: str
    variables: VariablesConfig
    split: SplitConfig
    hyperparametres: HyperparametresConfig
    # Le taux de la même cellule à la session précédente (la baseline, E21)
    # comme variable explicite plutôt que comme seul concurrent (E22, comparaison
    # à couverture égale). Décidé sur la seule validation 2024 : voir le
    # compte rendu de l'étape pour le chiffre qui a tranché.
    inclure_taux_precedent: bool


class EvaluationConfig(_Strict):
    metrique_principale: str
    calibration: bool
    # Nombre de tranches également espacées sur [0, 1] pour le diagramme de
    # fiabilité (E23) : la cible est un taux borné (ADR 0009), pas une classe,
    # donc la calibration se lit par tranches de valeur prédite plutôt que par
    # les déciles habituels d'une probabilité de classification.
    n_tranches_calibration: int = Field(ge=2)
    courbe_apprentissage: list[float] = Field(min_length=1)
    baseline: str


class EquiteConfig(_Strict):
    dimensions: list[str] = Field(min_length=1)
    variables_interdites: list[str]
    substituts_a_tester: list[str]
    seuil_impact_disparate: float = Field(gt=0, le=1)


class AblationConfig(_Strict):
    """Seuils de reconsidération de l'ablation (E27, adr/0013 § « Ce qui ferait reconsidérer »).

    `seuil_gain_mentions` : gain d'erreur absolue moyenne pondérée, mesuré sur
    la validation, au-delà duquel les variables de mention (écartées par
    défaut, ADR 0013 §3) seraient réintroduites. Fixé par l'ADR à 0,01, pas
    au jugé : en dessous, la contamination du baccalauréat en contrôle
    continu (2020-2021) sur deux des quatre sessions d'entraînement ne vaut
    pas le risque qu'elle documente.
    """

    seuil_gain_mentions: float = Field(gt=0, le=1)


class ExplicabiliteConfig(_Strict):
    """Paramètres de l'explicabilité TreeSHAP (E25), tous des choix de présentation,
    jamais des seuils qui changent un résultat.

    `top_n_figure` : nombre de variables affichées sur le diagramme d'importance
    globale — au-delà, les barres restantes sont trop fines pour rien ajouter à
    la lecture.

    `effectif_minimal_exemple` : effectif plancher pour qu'une cellule serve
    d'exemple local commenté (haut, bas) — sous ce seuil, une seule
    proposition supplémentaire ou en moins fait basculer le taux observé, et
    l'exemple illustrerait le bruit plutôt que le modèle. Même valeur que le
    plancher retenu par l'analyse d'équité (E11, "formations recevant au moins
    trente vœux") : pas une coïncidence, la même raison — en dessous, une
    cellule ne dit rien de stable.
    """

    top_n_figure: int = Field(ge=1)
    effectif_minimal_exemple: int = Field(ge=1)


class QualiteParcoursupConfig(_Strict):
    """Seuils du contrôle qualité Parcoursup (E14), tous mesurés sur le fichier source.

    `seuil_completude` : le taux en dessous duquel une colonne de la liste
    blanche (`modele.variables.session_courante`) est jugée incomplète.
    Mesuré sur la session 2025 : 8 des 9 colonnes sont remplies à 100 %,
    `region_etab_aff` à 99,32 % (97 lignes vides sur 14 252) — 0,99 couvre ce
    cas réel sans le signaler à tort.

    `tolerance_reconstruction_pourcentage` : écart maximal, en points,
    toléré entre une colonne `pct_*` et sa reconstruction depuis `acc_neobac`
    ou `acc_tot` (ADR 0013). Mesuré à 0,500 point exactement sur les 19
    colonnes et 13 954 lignes comparables de la session 2025 — c'est
    l'arrondi au point entier, rien de plus.

    `age_max_jours_avertissement` : Parcoursup publie un fichier par an, par
    campagne. Le contrôle ne porte donc que sur le millésime le plus récent
    déclaré (les archives plus anciennes restent volontairement anciennes) ;
    au-delà de ce nombre de jours sans nouveau téléchargement du dernier
    millésime configuré, un avertissement est levé — jamais un blocage, une
    campagne n'ayant pas de date de publication garantie à l'avance.
    """

    seuil_completude: float = Field(gt=0, le=1)
    tolerance_reconstruction_pourcentage: float = Field(ge=0)
    age_max_jours_avertissement: int = Field(ge=1)


class QualiteSireneConfig(_Strict):
    """Seuils du contrôle qualité Sirene (E14).

    `seuil_completude` : appliqué aux seules colonnes structurellement
    complètes par construction (`siret`, `etatAdministratifEtablissement`) —
    pas à `trancheEffectifsEtablissement` (code `NN` fréquent, pas une
    valeur manquante) ni à `activitePrincipaleNAF25Etablissement` (bascule de
    nomenclature en cours, ajoutée le 16/12/2025, 296 valeurs vides sur 500
    dans l'échantillon par construction du calendrier, pas par défaut de
    collecte).

    `age_max_jours_avertissement` : le stock Sirene est republié chaque
    mois. 60 jours laisse une marge de deux cycles de publication avant
    d'alerter, sans bloquer un job qui téléchargerait 4,6 Go pour rien à
    chaque exécution.
    """

    seuil_completude: float = Field(gt=0, le=1)
    age_max_jours_avertissement: int = Field(ge=1)


class QualiteReferentielsConfig(_Strict):
    """Seuils du contrôle qualité des référentiels ONISEP (IDÉO) et RNCP (E14).

    `age_max_jours_avertissement_ideo` : IDÉO n'expose aucune date de
    publication par l'API — seule `date_telechargement` (dernière
    vérification locale) est disponible. Le seuil, généreux, est une
    politique d'hygiène (« revérifier de temps en temps »), pas une mesure
    de péremption du contenu : à revoir si ONISEP publie un jour une date de
    mise à jour exploitable.

    `age_max_jours_avertissement_rncp` : l'export RNCP est republié chaque
    jour (ADR 0007). Le contrôle ne porte que sur l'export le plus récent
    présent dans le manifeste.
    """

    seuil_completude: float = Field(gt=0, le=1)
    age_max_jours_avertissement_ideo: int = Field(ge=1)
    age_max_jours_avertissement_rncp: int = Field(ge=1)


class QualiteConfig(_Strict):
    parcoursup: QualiteParcoursupConfig
    sirene: QualiteSireneConfig
    referentiels: QualiteReferentielsConfig


class MatchingConfig(_Strict):
    """Paramètres du score à trois termes (E28) : affinité x accessibilité x débouchés.

    `k_anonymat_debouches` : seuil de k-anonymat appliqué à l'agrégat Sirene
    (département x division NAF) qui porte le terme « débouchés ». Arrêté à
    5 par la gouvernance (`docs/sous-docs-projets/05-gouvernance/risques.md`,
    R2) : au grain commune, ce seuil supprimerait 90,6 % des cellules et
    46,9 % des établissements réels ; au grain département, seulement 35,0 %
    des cellules pour 1,6 % des établissements — c'est ce renversement qui a
    tranché le grain de restitution.

    `seuil_saturation_etablissements` : nombre d'établissements
    actifs-employeurs diffusibles, dans le département et les divisions NAF
    d'une formation, au-delà duquel le terme de débouchés est jugé pleinement
    disponible (valeur 1,0). En dessous, le terme croît linéairement de 0 à
    1. La façon dont ce nombre se traduit en un facteur dans [0, 1] est une
    règle de présentation, pas un modèle ; le seuil lui-même est un repère
    choisi à partir de la distribution réellement observée sur l'agrégat
    k-anonymisé (médiane à 71 établissements, 25e centile à 23 — voir
    `configs/base.yaml`), pas une valeur mesurée au sens d'un résultat
    statistique à défendre comme tel — à revoir si le produit exige une
    échelle différente (voir `matching/debouches.py`).

    `facteur_territoire_hors_zone` : facteur d'atténuation (pas d'exclusion)
    appliqué au terme d'affinité quand le département demandé par le
    candidat diffère de celui de la formation. Une préférence géographique
    reste une préférence, jamais une contrainte absolue au même titre qu'un
    type de formation demandé — décision arbitrée, déclarée comme telle.
    """

    k_anonymat_debouches: int = Field(ge=1)
    seuil_saturation_etablissements: int = Field(ge=1)
    facteur_territoire_hors_zone: float = Field(gt=0, le=1)


class RagConfig(_Strict):
    """Paramètres de l'assistant documentaire (E32), brique secondaire de restitution.

    Choix délibérément sobre : l'assistant retrouve les passages pertinents
    par similarité lexicale (TF-IDF, `scikit-learn`, déjà une dépendance du
    projet depuis E22) plutôt que par un index vectoriel dédié (embeddings +
    base vectorielle). Le corpus indexé — quelques milliers de lignes IDÉO —
    est très en dessous du volume où un index approximatif apporterait un
    gain de latence mesurable ; voir `src/edumatch/rag/index.py`.

    `jeux_indexes` : sous-ensemble de `donnees.referentiels.ideo.jeux` à
    indexer — une liste explicite plutôt que « tous les jeux disponibles »,
    pour qu'ajouter un jeu IDÉO à la configuration n'agrandisse pas le
    corpus de l'assistant sans décision explicite.

    `seuil_similarite_minimale` : score de similarité cosinus en dessous
    duquel un passage n'est pas restitué. C'est le verrou anti-invention :
    sous ce seuil, l'assistant déclare ne pas savoir plutôt que de citer un
    passage sans rapport avec la question (voir `rag/assistant.py`).

    `modele_generation` : nom du modèle appelé quand `MISTRAL_API_KEY` est
    renseignée. Sans cette variable d'environnement, l'assistant reste en
    mode extractif (voir `rag/generation.py`) — jamais un plantage, jamais
    un silence.
    """

    jeux_indexes: list[str] = Field(min_length=1)
    top_k: int = Field(ge=1)
    seuil_similarite_minimale: float = Field(gt=0, le=1)
    modele_generation: str


class DeriveConfig(_Strict):
    reference: str
    tests: list[str] = Field(min_length=1)
    seuil_reentrainement: float = Field(gt=0, lt=1)


class AutoscalingConfig(_Strict):
    min: int = Field(ge=1)
    max: int = Field(ge=1)
    cible_cpu_pourcent: int = Field(ge=1, le=100)

    @model_validator(mode="after")
    def _bornes_coherentes(self) -> "AutoscalingConfig":
        if self.min > self.max:
            raise ValueError("api.autoscaling.min doit être inférieur ou égal à api.autoscaling.max")
        return self


class AuditConfig(_Strict):
    """Durées de conservation du journal d'inférence, article 12 du règlement sur l'IA (E30).

    Conciliation entre le plancher de l'article 12 (conserver, au moins six
    mois pour un système à haut risque) et le plafond de l'article 5.1.e du
    RGPD (ne pas conserver au-delà du nécessaire) — arrêtée par la
    gouvernance et reprise ici telle quelle (voir
    `docs/sous-docs-projets/05-gouvernance/registre-traitements.md`, T5) :
    trois paliers datés, jamais une conservation indéfinie.

    `delai_pseudonymisation_jours` : durée du palier 1 (journal en clair).
    Au-delà, `api.audit_purge` remplace l'identifiant d'exécution par un
    jeton non réversible — le lien avec une personne est rompu, les
    variables d'entrée et la sortie restent lisibles pour l'audit d'équité
    et la détection de dérive. Valeur retenue : une campagne Parcoursup
    entière (janvier à la phase complémentaire) plus une marge de
    réclamation, soit 365 jours.

    `delai_agregation_jours` : durée cumulée des paliers 1 et 2 (journal en
    clair puis pseudonymisé). Au-delà, la ligne d'inférence disparaît :
    seul un agrégat par session, type de baccalauréat et statut de boursier
    est conservé. Valeur retenue : trois millésimes, la fenêtre minimale
    pour observer une dérive du concept sur une cible qui bouge d'une
    session à l'autre, soit 1095 jours (365 x 3).
    """

    delai_pseudonymisation_jours: int = Field(ge=1)
    delai_agregation_jours: int = Field(ge=1)

    @model_validator(mode="after")
    def _paliers_croissants(self) -> "AuditConfig":
        if self.delai_agregation_jours <= self.delai_pseudonymisation_jours:
            raise ValueError(
                "api.audit.delai_agregation_jours doit être strictement supérieur à "
                "api.audit.delai_pseudonymisation_jours : le palier d'agrégation suit celui de "
                "pseudonymisation, il ne peut pas le précéder."
            )
        return self


class ApiConfig(_Strict):
    """Paramètres de l'API de matching (E29).

    `max_formations_evaluees` : plafond de lignes du catalogue soumises à
    `matching.score.recommander` pour une seule requête `/matching`.
    `recommander` boucle ligne à ligne, délibérément non vectorisé (voir son
    docstring, E28) : au-delà de ce plafond, le temps de calcul menacerait
    `slo_latence_p95_ms`. Au-delà, l'API répond 422 et demande de préciser un
    département ou un domaine plutôt que de tronquer silencieusement le
    catalogue — aucune formation écartée sans que l'appelant en soit informé.
    Valeur retenue par ordre de grandeur avec `matching/exemple.py`, qui
    documente un catalogue « de la taille d'une recherche candidate (quelques
    centaines de lignes) » ; à mesurer précisément si ce plafond doit changer.

    `top_n_max` : borne du nombre de recommandations qu'un appelant peut
    demander (`ProfilRequete.top_n`) — protège des mêmes risques de latence
    qu'un catalogue trop large, pour la raison inverse (page de résultats
    demandée trop grande plutôt que catalogue trop large).
    """

    slo_latence_p95_ms: int = Field(gt=0)
    max_formations_evaluees: int = Field(ge=1)
    top_n_max: int = Field(ge=1)
    audit: AuditConfig
    # replicas et autoscaling n'existent qu'à partir de staging/prod.
    replicas: int | None = Field(default=None, ge=1)
    autoscaling: AutoscalingConfig | None = None


class ExecutionConfig(_Strict):
    moteur_volume: Literal["local", "cluster"]
    niveau_journal: Literal["DEBUG", "INFO", "WARNING", "ERROR"]


# ─── Fusion des fichiers YAML ────────────────────────────────────────────────


def _deep_merge(base: dict, surcharge: dict) -> dict:
    """Fusionne deux dictionnaires, `surcharge` l'emportant sur `base`.

    Les sous-dictionnaires sont fusionnés récursivement clé par clé. Les
    listes ne sont pas fusionnées : une liste dans `surcharge` remplace
    entièrement celle de `base` (c'est le comportement attendu de
    dev.yaml, qui réduit délibérément la liste des millésimes).
    """
    fusion = dict(base)
    for cle, valeur in surcharge.items():
        existante = fusion.get(cle)
        if isinstance(existante, dict) and isinstance(valeur, dict):
            fusion[cle] = _deep_merge(existante, valeur)
        else:
            fusion[cle] = valeur
    return fusion


def _charger_yaml(chemin: Path) -> dict:
    if not chemin.exists():
        raise ConfigurationError(
            f"Fichier de configuration introuvable : {chemin}. "
            "Vérifier configs/ ou la variable EDUMATCH_ENV."
        )
    try:
        contenu = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    except yaml.YAMLError as erreur:
        raise ConfigurationError(f"{chemin} : YAML malformé — {erreur}") from erreur
    if contenu is None:
        return {}
    if not isinstance(contenu, dict):
        raise ConfigurationError(
            f"{chemin} : le document YAML racine doit être une table (clé: valeur), "
            f"obtenu {type(contenu).__name__}."
        )
    return contenu


def _fusionner_configuration(environnement: str, configs_dir: Path) -> dict:
    """Charge base.yaml puis {environnement}.yaml et les fusionne.

    Un seul niveau d'héritage est supporté : `{environnement}.yaml` doit
    déclarer `herite_de: base.yaml`. C'est une vérification volontairement
    stricte — une chaîne d'héritage plus longue rendrait la configuration
    résolue difficile à auditer à l'œil.
    """
    if environnement not in ENVIRONNEMENTS_VALIDES:
        raise ConfigurationError(
            f"EDUMATCH_ENV={environnement!r} invalide. "
            f"Valeurs acceptées : {', '.join(ENVIRONNEMENTS_VALIDES)}."
        )

    base = _charger_yaml(configs_dir / "base.yaml")
    surcharge = _charger_yaml(configs_dir / f"{environnement}.yaml")

    herite_de = surcharge.pop("herite_de", None)
    if herite_de != "base.yaml":
        raise ConfigurationError(
            f"configs/{environnement}.yaml : le champ 'herite_de' vaut "
            f"{herite_de!r}, attendu 'base.yaml'. Un seul niveau d'héritage "
            "est pris en charge."
        )

    return _deep_merge(base, surcharge)


# ─── Racine des données ──────────────────────────────────────────────────────


def _defaut_racine_donnees() -> Path:
    """Valeur par défaut de EDUMATCH_DATA_ROOT : le dossier data/ du dépôt.

    Résolu depuis l'emplacement du paquet (`PROJECT_ROOT`), donc déjà
    absolu et indépendant du répertoire courant au lancement — identique
    sous Windows et sous Linux. C'est le comportement du poste de
    développement ; le déploiement (Scaleway, conteneur, CI) surcharge cette
    valeur via la variable d'environnement.
    """
    return PROJECT_ROOT / "data"


# ─── Point d'entrée : Settings ───────────────────────────────────────────────


class Settings(BaseSettings):
    """Configuration résolue du projet : YAML fusionné, puis surchargé par l'environnement.

    Ne pas instancier directement en dehors des tests : utiliser
    `get_settings()`, qui met le résultat en cache pour tout le processus.
    """

    model_config = SettingsConfigDict(
        env_prefix="EDUMATCH_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        validate_default=True,
    )

    # Sélection d'environnement et racine des données : pas de contrepartie
    # YAML, uniquement pilotables par variable d'environnement.
    env: EnvironnementValide = "dev"
    data_root: Path = Field(default_factory=_defaut_racine_donnees)

    @field_validator("data_root", mode="before")
    @classmethod
    def _rejeter_data_root_vide_ou_relatif(cls, valeur: object) -> object:
        """Refuse une racine de données vide, blanche ou relative.

        Seule et unique validation de `data_root`, quelle que soit sa
        provenance (YAML fusionné, `.env`, variable d'environnement) : sans
        elle, `Path("")` vaudrait '.', le répertoire courant, un emplacement
        non maîtrisé selon le point de lancement. `load_settings()` traduit
        la `ValidationError` levée ici en `ConfigurationError`, pour que
        l'appelant reçoive le même type d'erreur qu'aux autres points de ce
        module, indépendamment du canal par lequel la valeur est arrivée.
        """
        if valeur is None:
            return valeur  # absent : le default_factory (data/ du dépôt) s'applique
        texte = str(valeur).strip()
        if not texte:
            raise ValueError(
                "data_root est vide ou ne contient que des espaces : "
                "Path('') se résoudrait en le répertoire courant."
            )
        chemin = Path(texte)
        if not chemin.is_absolute():
            raise ValueError(f"data_root={texte!r} doit être un chemin absolu.")
        return chemin

    # Reflet typé de configs/*.yaml, fusionné en amont.
    projet: ProjetConfig
    donnees: DonneesConfig
    modele: ModeleConfig
    evaluation: EvaluationConfig
    equite: EquiteConfig
    ablation: AblationConfig
    explicabilite: ExplicabiliteConfig
    matching: MatchingConfig
    qualite: QualiteConfig
    rag: RagConfig
    derive: DeriveConfig
    api: ApiConfig
    execution: ExecutionConfig

    # Secrets — uniquement lisibles depuis l'environnement, jamais du YAML.
    # `validation_alias` court-circuite le préfixe EDUMATCH_ pour coller aux
    # noms déjà en usage dans .env.example et docker-compose.yml.
    postgres_host: str | None = Field(default=None, validation_alias="POSTGRES_HOST")
    postgres_port: int | None = Field(default=None, validation_alias="POSTGRES_PORT")
    postgres_db: str | None = Field(default=None, validation_alias="POSTGRES_DB")
    postgres_user: str | None = Field(default=None, validation_alias="POSTGRES_USER")
    postgres_password: SecretStr | None = Field(default=None, validation_alias="POSTGRES_PASSWORD")
    mlflow_tracking_uri: str | None = Field(default=None, validation_alias="MLFLOW_TRACKING_URI")
    mistral_api_key: SecretStr | None = Field(default=None, validation_alias="MISTRAL_API_KEY")
    scw_access_key: str | None = Field(default=None, validation_alias="SCW_ACCESS_KEY")
    scw_secret_key: SecretStr | None = Field(default=None, validation_alias="SCW_SECRET_KEY")
    scw_default_project_id: str | None = Field(default=None, validation_alias="SCW_DEFAULT_PROJECT_ID")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Ordonne les sources pour appliquer la précédence documentée en tête de module.

        L'ordre du tuple va de la priorité la plus haute à la plus basse.
        `init_settings` porte ici le YAML déjà fusionné (base < environnement),
        transmis explicitement par `load_settings`. Le placer après
        `env_settings` et `dotenv_settings` garantit qu'une variable
        d'environnement, réelle ou issue d'un fichier .env, l'emporte
        toujours sur le YAML.
        """
        return env_settings, dotenv_settings, init_settings, file_secret_settings

    # ─── Chemins dérivés de data_root ────────────────────────────────────

    @property
    def raw_dir(self) -> Path:
        """Données brutes, immuables — équivalent bronze."""
        return self.data_root / "raw"

    @property
    def interim_dir(self) -> Path:
        """Données nettoyées, réconciliées — équivalent silver."""
        return self.data_root / "interim"

    @property
    def processed_dir(self) -> Path:
        """Données prêtes pour la modélisation — équivalent gold."""
        return self.data_root / "processed"

    @property
    def external_dir(self) -> Path:
        """Référentiels tiers (ONISEP, RNCP, IDEO...)."""
        return self.data_root / "external"

    @property
    def samples_dir(self) -> Path:
        """Échantillons versionnés pour les tests — reste dans le dépôt, pas sous data_root."""
        return PROJECT_ROOT / "data" / "samples"


def load_settings(environnement: str | None = None, configs_dir: Path | None = None) -> Settings:
    """Construit une instance de Settings pour l'environnement demandé.

    Args:
        environnement: `dev`, `staging` ou `prod`. À défaut, lu depuis la
            variable d'environnement `EDUMATCH_ENV`, avec `dev` en repli
            explicite (poste de développement sans configuration).
        configs_dir: dossier contenant les YAML. Paramétrable pour les tests,
            sinon `<racine du dépôt>/configs`.

    Raises:
        ConfigurationError: fichier manquant, héritage incorrect, YAML
            malformé, nom d'environnement inconnu, EDUMATCH_DATA_ROOT vide,
            blanche ou relative, ou argument explicite en contradiction avec
            EDUMATCH_ENV.
        pydantic.ValidationError: une valeur du YAML fusionné ou de
            l'environnement ne respecte pas le schéma — le message pointe le
            champ fautif et la raison.
    """
    env_variable = os.environ.get("EDUMATCH_ENV")
    if environnement is not None and env_variable is not None and env_variable != environnement:
        raise ConfigurationError(
            f"load_settings({environnement!r}) contredit EDUMATCH_ENV={env_variable!r}. "
            "Deux mécanismes choisiraient un environnement différent : le YAML chargé "
            f"serait {environnement!r} mais Settings.env vaudrait {env_variable!r}, "
            "puisqu'une variable d'environnement prime toujours sur le YAML. "
            "Aligner les deux (ne garder que l'un des deux), plutôt que de laisser "
            "l'objet résultant annoncer un environnement différent de son contenu."
        )
    env_resolu = environnement or env_variable or "dev"
    dossier = configs_dir or CONFIGS_DIR
    config_fusionnee = _fusionner_configuration(env_resolu, dossier)
    config_fusionnee.setdefault("env", env_resolu)
    try:
        return Settings(**config_fusionnee)
    except ValidationError as erreur:
        erreurs_data_root = [e for e in erreur.errors() if e["loc"] and e["loc"][0] == "data_root"]
        if not erreurs_data_root:
            raise
        detail = "; ".join(e["msg"] for e in erreurs_data_root)
        raise ConfigurationError(
            f"EDUMATCH_DATA_ROOT invalide (qu'elle vienne d'une variable "
            f"d'environnement, d'un fichier .env ou du YAML) : {detail}"
        ) from erreur


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Point d'entrée unique de la configuration, mis en cache pour le processus.

    Le cache évite de relire et revalider les YAML à chaque appel — la
    configuration ne change pas en cours d'exécution. `get_settings.cache_clear()`
    permet de forcer un rechargement (utile en test, quand l'environnement
    change entre deux cas).
    """
    return load_settings()
