"""Terme « affinité » du score de matching : des règles déclaratives, jamais un modèle.

## Ce que ce terme représente

Le candidat exprime des préférences facultatives — un type de formation, un
mot-clé de domaine, un département visé. Ce module compare ces préférences
aux attributs publiés de la formation (`fili`, `fil_lib_voe_acc`,
`form_lib_voe_acc`, `dep` — les mêmes colonnes de catalogue que
`modele.variables.session_courante`, ADR 0013) et en tire un facteur dans
[0, 1]. Aucune donnée n'est apprise ici : c'est une comparaison de chaînes de
caractères et un facteur d'atténuation, pas un modèle statistique — cohérent
avec le principe d'architecture du projet, un seul composant appris
(l'accessibilité, `models/`).

## Le caractère multiplicatif à l'intérieur même de ce terme

Deux critères sont des **filtres durs** : s'ils sont exprimés et non
satisfaits, l'affinité tombe à 0,0 et la formation ne peut plus être
recommandée, quels que soient les deux autres termes du score global
(`matching/score.py`). C'est voulu : un candidat qui demande un « BTS » ne
doit jamais se voir proposer une Licence au motif qu'elle est très
accessible et bien desservie en débouchés.

- `type_formation` (comparé à `fili`) — filtre dur.
- `domaine` (mot-clé cherché dans `fil_lib_voe_acc` et `form_lib_voe_acc`) —
  filtre dur.

Le département, lui, n'est **pas** un filtre dur : c'est un facteur
d'atténuation (`facteur_territoire_hors_zone`, `configs/base.yaml`). Décision
arbitrée, pas évidente — une préférence géographique reste une préférence,
jamais une contrainte absolue au même titre qu'un type de diplôme demandé :
un candidat mobile ne doit pas voir disparaître toutes les formations hors
de son département actuel. Ce qui me ferait changer d'avis : un usage
produit qui démontre que les candidats considèrent en pratique le
département comme une contrainte, pas une préférence — auquel cas il
deviendrait un troisième filtre dur, au même titre que les deux premiers.

## Aucun champ de genre

`ProfilCandidat` ne porte, par construction, aucun champ de genre : c'est
l'invariant du projet (ADR 0011, `configs/base.yaml`
`equite.variables_interdites`), qui s'applique à tout composant qui
influence une recommandation, affinité comprise, pas seulement au modèle
d'accessibilité. `_verifier_profil_sans_genre` le contrôle par introspection
au chargement du module ; `tests/unit/test_matching_affinite.py` le
revérifie explicitement.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, fields

CHAMPS_INTERDITS = {"genre", "sexe"}

# Décision par défaut si `configs/base.yaml` n'est pas consulté par l'appelant
# (tests unitaires isolés) : reprise ici pour ne jamais dépendre d'un chemin
# de configuration à l'intérieur de ce module pur — la valeur réelle,
# opposable, vient toujours de `Settings.matching.facteur_territoire_hors_zone`.
FACTEUR_TERRITOIRE_HORS_ZONE_PAR_DEFAUT = 0.6


def normaliser(texte: str | None) -> str:
    """Minuscule, sans accent, sans ponctuation — la même normalisation que `matching/debouches.py`
    et `referentiel/naf_rome_formation.py` (bridge textuel), pour qu'une même règle de comparaison
    serve partout où ce projet compare deux libellés."""
    if not texte:
        return ""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    minuscule = sans_accents.lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", minuscule)).strip()


@dataclass(frozen=True)
class ProfilCandidat:
    """Préférences exprimées par le candidat. Chaque champ est optionnel : `None` signifie
    « aucune préférence exprimée sur ce critère », jamais une exclusion — un profil vide
    (`ProfilCandidat()`) donne systématiquement une affinité de 1,0.
    """

    type_formation: str | None = None  # valeur attendue de `fili` (ex. "BTS", "Licence", "CPGE")
    domaine: str | None = None  # mot-clé cherché dans le libellé de la formation
    departement: str | None = None  # département souhaité, code INSEE (2 ou 3 caractères)


def _verifier_profil_sans_genre() -> None:
    noms = {champ.name for champ in fields(ProfilCandidat)}
    interdits = noms & CHAMPS_INTERDITS
    if interdits:
        raise RuntimeError(
            f"ProfilCandidat porte un champ interdit par ADR 0011 : {sorted(interdits)}. "
            "Le genre ne peut entrer dans aucun composant qui influence une recommandation."
        )


_verifier_profil_sans_genre()


@dataclass(frozen=True)
class TermeAffinite:
    """Le facteur d'affinité et le détail qui l'explique — jamais un nombre seul :
    un conseiller doit pouvoir dire *pourquoi* une formation a été écartée."""

    valeur: float
    filtre_type_formation_respecte: bool
    filtre_domaine_respecte: bool
    territoire_correspond: bool | None  # None si le candidat n'a pas exprimé de préférence


def calculer_affinite(
    fili: str,
    fil_lib_voe_acc: str,
    form_lib_voe_acc: str,
    departement_formation: str | None,
    profil: ProfilCandidat,
    facteur_territoire_hors_zone: float = FACTEUR_TERRITOIRE_HORS_ZONE_PAR_DEFAUT,
) -> TermeAffinite:
    """Calcule l'affinité d'une formation à un profil. Voir le docstring du module pour la
    distinction entre filtres durs (type, domaine) et facteur d'atténuation (territoire)."""
    filtre_type = True
    if profil.type_formation is not None:
        filtre_type = normaliser(fili) == normaliser(profil.type_formation)

    filtre_domaine = True
    if profil.domaine is not None:
        mot = normaliser(profil.domaine)
        texte = f"{normaliser(fil_lib_voe_acc)} {normaliser(form_lib_voe_acc)}"
        filtre_domaine = bool(mot) and mot in texte

    territoire_correspond: bool | None = None
    facteur_territoire = 1.0
    if profil.departement is not None:
        territoire_correspond = departement_formation == profil.departement
        facteur_territoire = 1.0 if territoire_correspond else facteur_territoire_hors_zone

    if not filtre_type or not filtre_domaine:
        return TermeAffinite(
            valeur=0.0,
            filtre_type_formation_respecte=filtre_type,
            filtre_domaine_respecte=filtre_domaine,
            territoire_correspond=territoire_correspond,
        )

    return TermeAffinite(
        valeur=facteur_territoire,
        filtre_type_formation_respecte=filtre_type,
        filtre_domaine_respecte=filtre_domaine,
        territoire_correspond=territoire_correspond,
    )
