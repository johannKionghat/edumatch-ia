"""Contrôle de fraîcheur, générique : un identifiant, une date ISO 8601, un âge maximal.

Chaque connecteur (`ingestion/parcoursup.py`, `sirene.py`, `referentiels.py`)
écrit déjà une date dans son manifeste (`date_telechargement`,
`date_publication_stock`, `date_publication`). Ce module ne sait rien de la
provenance de cette date : il reçoit un dictionnaire `{identifiant: date_iso}`
déjà extrait du manifeste concerné par l'appelant, qui seul connaît le nom du
champ à lire pour sa source.

Deux échecs de nature différente, et c'est pourquoi ils n'ont pas la même
gravité :

- **Bloquant** — l'entrée manque, ou la date ne se laisse pas analyser, ou
  elle se situe dans le futur. Dans les trois cas, ce n'est pas la source qui
  a vieilli : c'est le manifeste, ou l'horloge, qui est incohérent. Retenter
  ne change rien tant que la métadonnée elle-même n'est pas corrigée.
- **Avertissement** — la date est valide mais dépasse l'âge maximal attendu
  pour cette source. La donnée reste exploitable ; un humain devrait décider
  s'il faut la rafraîchir.
"""

from __future__ import annotations

from datetime import datetime, timezone

from edumatch.quality._diagnostic import Anomalie, Gravite


def _analyser_date(valeur: str) -> datetime:
    """Lève `ValueError` si `valeur` n'est pas une date ISO 8601 exploitable."""
    horodatage = datetime.fromisoformat(valeur)
    if horodatage.tzinfo is None:
        horodatage = horodatage.replace(tzinfo=timezone.utc)
    return horodatage


def controler_fraicheur(
    source: str,
    dates: dict[str, str | None],
    age_max_jours: float,
    *,
    maintenant: datetime | None = None,
) -> list[Anomalie]:
    """Contrôle la fraîcheur d'un ensemble d'entrées datées.

    Args:
        source: nom de la source, pour les messages d'anomalie.
        dates: `{identifiant: date_iso}`. Une valeur `None` signifie
            « entrée absente du manifeste », traitée comme bloquante — on ne
            peut pas auditer la fraîcheur d'une donnée sans provenance.
        age_max_jours: seuil au-delà duquel une date valide, mais ancienne,
            déclenche un avertissement.
        maintenant: horodatage de référence, injectable pour les tests.
            À défaut, l'heure réelle (UTC).
    """
    reference = maintenant or datetime.now(timezone.utc)
    anomalies: list[Anomalie] = []
    for identifiant, valeur in dates.items():
        anomalie = _controler_une_entree(source, identifiant, valeur, age_max_jours, reference)
        if anomalie is not None:
            anomalies.append(anomalie)
    return anomalies


def _controler_une_entree(
    source: str,
    identifiant: str,
    valeur: str | None,
    age_max_jours: float,
    reference: datetime,
) -> Anomalie | None:
    if valeur is None:
        return Anomalie(
            source,
            "fraicheur",
            Gravite.BLOQUANT,
            f"{identifiant} : aucune date dans le manifeste, provenance non auditable.",
        )
    try:
        horodatage = _analyser_date(valeur)
    except ValueError as erreur:
        return Anomalie(
            source,
            "fraicheur",
            Gravite.BLOQUANT,
            f"{identifiant} : date {valeur!r} illisible ({erreur}).",
        )
    if horodatage > reference:
        return Anomalie(
            source,
            "fraicheur",
            Gravite.BLOQUANT,
            f"{identifiant} : date {valeur} est dans le futur par rapport à {reference.isoformat()}.",
        )
    age_jours = (reference - horodatage).total_seconds() / 86400
    if age_jours > age_max_jours:
        return Anomalie(
            source,
            "fraicheur",
            Gravite.AVERTISSEMENT,
            f"{identifiant} : {age_jours:.1f} jours depuis {valeur}, "
            f"au-delà du seuil de {age_max_jours} jours.",
        )
    return None
