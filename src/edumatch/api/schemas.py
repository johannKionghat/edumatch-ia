"""Schémas Pydantic de l'API (E29) : contrat d'entrée et de sortie, validation stricte.

Aucune logique métier ici : ce module traduit les dataclasses de `matching/`
et de `models/explain.py` vers un contrat HTTP stable et documenté (OpenAPI).

## L'article 22 du RGPD, rendu visible dans le contrat

Cette API assiste un conseiller ; elle ne décide jamais à sa place. `avis_assistance`
porte ce rappel sur chaque réponse qui contient une recommandation ou une
explication — pas seulement dans la documentation, dans la réponse elle-même,
pour qu'un système consommateur ne puisse pas l'ignorer par inattention.

## Le genre n'a sa place dans aucun schéma d'entrée

`ProfilRequete` ne porte, par construction, aucun champ de genre (ADR 0011,
invariant du projet) — cohérent avec `matching.affinite.ProfilCandidat`, qui
l'interdit déjà par introspection au chargement du module.
`extra="forbid"` refuse en plus tout champ non déclaré : un client qui
enverrait `"genre": "F"` reçoit une erreur 422, jamais un champ ignoré en
silence.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TypeBac = Literal["bg", "bt", "bp"]

DecisionConseiller = Literal["retenue", "ecartee"]

# Code INSEE de département : deux chiffres, trois chiffres (DOM/TOM), ou 2A/2B (Corse) —
# même règle que `matching/agregat_sirene_debouches.departement_depuis_commune`.
MOTIF_PATTERN_DEPARTEMENT = r"^(2[AB]|[0-9]{2,3})$"

AVIS_ASSISTANCE = (
    "Cette estimation assiste un conseiller humain ; elle ne constitue jamais une décision "
    "automatisée au sens de l'article 22 du RGPD. Le conseiller reste seul décisionnaire et "
    "peut l'écarter, avec motif obligatoire (voir POST /feedback)."
)


# ─── /health ─────────────────────────────────────────────────────────────────


class ReponseSante(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statut: Literal["ok"] = "ok"
    version: str


# ─── /matching ───────────────────────────────────────────────────────────────


class ProfilRequete(BaseModel):
    """Ce qu'un candidat déclare pour une recherche — jamais son genre (voir le docstring
    du module). `type_bac` et `boursier` sont les deux dimensions de la cellule prédite
    (ADR 0009) : sans elles, aucune prédiction ne peut être sélectionnée dans le catalogue."""

    model_config = ConfigDict(extra="forbid")

    type_bac: TypeBac = Field(description="Dimension de la cellule prédite : bg, bt ou bp.")
    boursier: bool = Field(description="Dimension de la cellule prédite.")
    type_formation: str | None = Field(
        default=None, max_length=64, description="Filtre dur (ex. 'BTS', 'Licence', 'CPGE')."
    )
    domaine: str | None = Field(default=None, max_length=128, description="Mot-clé cherché dans le libellé.")
    departement: str | None = Field(
        default=None, pattern=MOTIF_PATTERN_DEPARTEMENT, description="Département visé, code INSEE."
    )
    top_n: int = Field(default=10, ge=1, description="Nombre de recommandations souhaitées (plafonné côté serveur).")


class TermeAffiniteReponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valeur: float
    filtre_type_formation_respecte: bool
    filtre_domaine_respecte: bool
    territoire_correspond: bool | None


class TermeAccessibiliteReponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valeur: float = Field(description="Bornée dans [0, 1] — voir `avertissement_accessibilite`.")
    valeur_brute: float = Field(description="Prédiction du modèle avant écrêtage.")


class TermeDebouchesReponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valeur: float
    disponible: bool
    statut: str
    motif: str = Field(description="Explication lisible du statut — jamais un zéro non expliqué.")
    naf_divisions: tuple[str, ...] = ()
    n_etablissements: int | None = None


class RecommandationFormation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifiant_formation: str
    libelle_formation: str
    score: float
    affinite: TermeAffiniteReponse
    accessibilite: TermeAccessibiliteReponse
    debouches: TermeDebouchesReponse


class ReponseMatching(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: int
    recommandations: list[RecommandationFormation]
    n_formations_disponibles: int = Field(
        description="Formations du catalogue correspondant au type de baccalauréat, au statut de "
        "boursier et, si renseigné, au département — avant le calcul du score."
    )
    n_formations_evaluees: int
    avertissement_accessibilite: str
    debouches_disponible: bool = Field(
        description="Faux si les artefacts de débouchés n'ont pas pu être construits au démarrage "
        "du service (voir `motif_indisponibilite_debouches`) — toutes les valeurs de débouchés "
        "sont alors neutres, jamais estimées."
    )
    motif_indisponibilite_debouches: str | None = None
    avertissement_debouches: str
    avis_assistance: str = AVIS_ASSISTANCE


# ─── /explain ────────────────────────────────────────────────────────────────


class ContributionReponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variable: str
    contribution: float = Field(description="Valeur de Shapley signée — positive pousse la prédiction "
        "au-dessus de la valeur de base, négative en dessous.")


class ReponseExplication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: int
    identifiant_formation: str
    type_bac: TypeBac
    boursier: bool
    prediction: float
    valeur_base: float = Field(description="Moyenne de la cible sur l'échantillon d'arrière-plan (TreeSHAP).")
    contributions: list[ContributionReponse] = Field(
        description="Triées par contribution absolue décroissante, précalculées (E25) — jamais recalculées ici."
    )
    avertissement_accessibilite: str
    avis_assistance: str = AVIS_ASSISTANCE


# ─── /feedback ───────────────────────────────────────────────────────────────


class RequeteFeedback(BaseModel):
    """La décision d'un conseiller sur une recommandation. Voir `feedback_store.py` : aucune
    donnée du candidat n'est portée par ce schéma, uniquement la cellule et la décision."""

    model_config = ConfigDict(extra="forbid")

    session: int = Field(gt=2000)
    identifiant_formation: str = Field(min_length=1, max_length=64)
    type_bac: TypeBac
    boursier: bool
    decision: DecisionConseiller
    motif: str | None = Field(default=None, max_length=1000)
    identifiant_conseiller: str = Field(
        min_length=1, max_length=128, description="Identifiant pseudonyme du conseiller, jamais un nom."
    )

    @model_validator(mode="after")
    def _motif_obligatoire_si_ecartee(self) -> "RequeteFeedback":
        """R6 (`risques.md`) : un écartement doit être motivé, sans quoi le contrôle humain
        n'est qu'une façade — voir le docstring de `feedback_store.py`."""
        if self.decision == "ecartee" and not (self.motif and self.motif.strip()):
            raise ValueError(
                "Un écartement doit être motivé (R6, risques.md) : le champ 'motif' est obligatoire "
                "quand decision='ecartee'."
            )
        return self


class ReponseFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifiant_feedback: str
    horodatage: str
    enregistre: bool = True
