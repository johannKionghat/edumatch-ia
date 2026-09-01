"""Journal des inférences (E30) : horodatage, exécution, version du modèle, entrées et sortie
(article 12 du règlement sur l'IA, R1 de `docs/sous-docs-projets/05-gouvernance/risques.md`).

## Pourquoi un journal distinct des logs applicatifs

`api/errors.py` l'écrit explicitement : le corps d'une requête (type de
baccalauréat, boursier, département) est une caractéristique personnelle
d'un candidat, potentiellement mineur, et **ne doit jamais** apparaître dans
les journaux applicatifs (`logging`), consultables par quiconque a accès à
la sortie standard du service. Ce module est le contraire : un registre
**volontaire et protégé**, écrit dans un fichier dédié
(`processed/audit/journal.jsonl`), dont l'existence même répond à une
obligation légale précise — l'article 12 impose au fournisseur d'un système
à haut risque de journaliser automatiquement les événements pertinents
pendant toute sa durée de fonctionnement. `LOGGER` n'y journalise jamais que
des compteurs, jamais le contenu d'une entrée ou d'une sortie.

## Ce qui est journalisé, et ce qui ne l'est pas

Catégorie de données (`registre-traitements.md`, T5) : horodatage,
identifiant technique de requête, version du modèle et empreinte du commit,
variables d'entrée, score produit. C'est exactement ce que porte
`EnregistrementAudit` — ni plus (aucune identité du candidat n'est
collectée en amont, voir l'AIPD §2.3), ni moins (une version sans le commit
Git ne permettrait pas de rejouer une inférence contestée).

`decision_conseiller` reste `None` à l'écriture : la décision motivée d'un
conseiller est journalisée séparément, par `feedback_store.py` (T6), qui ne
porte aucun identifiant de requête commun avec ce journal aujourd'hui — les
deux traces ne se corrèlent donc pas automatiquement. Le champ existe pour
que la structure du journal n'ait pas à changer le jour où cette
corrélation est construite ; **il ne l'est pas encore**, écrit ici plutôt
que masqué.

## La tension article 12 / article 5.1.e, et sa résolution exécutable

Voir `registre-traitements.md` T5 pour la conciliation en trois paliers
(12 mois en clair, 36 mois pseudonymisé, puis agrégats) et
`config.AuditConfig` pour les durées, qui vivent en configuration et jamais
en dur ici. `audit_purge.py` est le mécanisme qui **exécute** cette
conciliation — sans lui, les durées écrites dans le registre ne sont que
des intentions, lacune L2 explicitement relevée par la gouvernance.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

NOM_FICHIER_JOURNAL = "journal.jsonl"
SOUS_DOSSIER_AUDIT = "audit"


def resoudre_empreinte_commit() -> str | None:
    """Le hachage court du commit courant — même approche que `models.train._commit_git`,
    dupliquée volontairement plutôt que partagée : les deux modules ne partagent aucune autre
    dépendance, et une erreur ici ne doit jamais interrompre une réponse HTTP.

    Best-effort : ni un dépôt Git absent (image de production sans `.git`), ni `git` non
    installé ne doivent faire échouer une requête `/matching` — seule la traçabilité en
    pâtit, journalisée comme telle plutôt que masquée derrière une exception.
    """
    try:
        resultat = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as erreur:
        LOGGER.warning("Commit Git non résolu, traçabilité du journal d'audit incomplète : %s", erreur)
        return None
    return resultat.stdout.strip() or None


@dataclass(frozen=True)
class EnregistrementAudit:
    """Une ligne du journal — voir le docstring du module pour ce qu'elle porte et pourquoi."""

    identifiant_audit: str
    horodatage: str
    identifiant_execution: str
    version_modele: str
    empreinte_commit: str | None
    entrees: dict[str, Any] = field(default_factory=dict)
    sortie: dict[str, Any] = field(default_factory=dict)
    decision_conseiller: str | None = None
    pseudonymise: bool = False


class JournalAudit:
    """Journal append-only du journal d'inférence (T5), même politique de verrouillage que
    `feedback_store.JournalFeedback` : protège les écritures concurrentes d'un même worker, pas
    entre processus — hors périmètre de cette étape, comme documenté là-bas."""

    def __init__(self, chemin: Path) -> None:
        self._chemin = chemin
        self._verrou = threading.Lock()

    @property
    def chemin(self) -> Path:
        return self._chemin

    def enregistrer(
        self,
        *,
        version_modele: str,
        entrees: dict[str, Any],
        sortie: dict[str, Any],
    ) -> EnregistrementAudit:
        enregistrement = EnregistrementAudit(
            identifiant_audit=str(uuid.uuid4()),
            horodatage=datetime.now(timezone.utc).isoformat(),
            identifiant_execution=str(uuid.uuid4()),
            version_modele=version_modele,
            empreinte_commit=resoudre_empreinte_commit(),
            entrees=entrees,
            sortie=sortie,
        )
        ligne = json.dumps(asdict(enregistrement), ensure_ascii=False)
        with self._verrou:
            self._chemin.parent.mkdir(parents=True, exist_ok=True)
            with self._chemin.open("a", encoding="utf-8") as flux:
                flux.write(ligne + "\n")
        LOGGER.info(
            "Inférence journalisée (T5) : version=%s (aucune variable d'entrée ni sortie journalisée ici).",
            version_modele,
        )
        return enregistrement

    def lire_tout(self) -> list[EnregistrementAudit]:
        """Relit le journal — utilisé par les tests et par `audit_purge.py`."""
        if not self._chemin.exists():
            return []
        lignes = self._chemin.read_text(encoding="utf-8").splitlines()
        return [EnregistrementAudit(**json.loads(ligne)) for ligne in lignes if ligne.strip()]
