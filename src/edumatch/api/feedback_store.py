"""Journal des décisions du conseiller (E29) : écartement motivé, horodaté (R6, `risques.md`).

Un écran de contrôle humain qui n'écarte jamais rien n'est pas un contrôle
(article 14 de l'AI Act) — R6 exige que l'écartement soit **motivé**,
**horodaté** et **journalisé**, et que le taux d'écartement reste mesurable.
Ce module tient cette trace minimale : session, identifiant de formation,
dimensions de la cellule, décision, motif, identifiant pseudonyme du
conseiller. **Aucune donnée du candidat n'y est écrite** — ni son profil, ni
la saisie qui a produit la recommandation, cohérent avec l'AIPD (§2.3 :
« aucune conservation de la saisie »).

**Précurseur d'E30, pas son remplaçant.** Ce journal n'a ni durée de
conservation ni purge automatisée — les deux obligations que l'AIPD relève
comme non exécutées (R1) restent à construire par la journalisation article 12
complète. Écrit ici tel quel plutôt que présenté comme complet.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

LOGGER = logging.getLogger(__name__)

NOM_FICHIER_JOURNAL = "feedback.jsonl"
SOUS_DOSSIER_JOURNAL = "supervision"


@dataclass(frozen=True)
class EnregistrementFeedback:
    """Une ligne du journal — voir le docstring du module pour ce qui n'y figure jamais."""

    identifiant_feedback: str
    horodatage: str
    session: int
    identifiant_formation: str
    type_bac: str
    boursier: bool
    decision: str
    motif: str | None
    identifiant_conseiller: str


class JournalFeedback:
    """Journal append-only, protégé par un verrou pour les écritures concurrentes d'un même
    worker. Ne protège pas contre plusieurs processus concurrents écrivant le même fichier —
    hors périmètre de cette étape (voir le docstring du module)."""

    def __init__(self, chemin: Path) -> None:
        self._chemin = chemin
        self._verrou = threading.Lock()

    @property
    def chemin(self) -> Path:
        return self._chemin

    def enregistrer(
        self,
        *,
        session: int,
        identifiant_formation: str,
        type_bac: str,
        boursier: bool,
        decision: str,
        motif: str | None,
        identifiant_conseiller: str,
    ) -> EnregistrementFeedback:
        enregistrement = EnregistrementFeedback(
            identifiant_feedback=str(uuid.uuid4()),
            horodatage=datetime.now(UTC).isoformat(),
            session=session,
            identifiant_formation=identifiant_formation,
            type_bac=type_bac,
            boursier=boursier,
            decision=decision,
            motif=motif,
            identifiant_conseiller=identifiant_conseiller,
        )
        ligne = json.dumps(asdict(enregistrement), ensure_ascii=False)
        with self._verrou:
            self._chemin.parent.mkdir(parents=True, exist_ok=True)
            with self._chemin.open("a", encoding="utf-8") as flux:
                flux.write(ligne + "\n")
        LOGGER.info(
            "Feedback enregistré : décision=%s formation=%s (aucune donnée candidat journalisée).",
            decision,
            identifiant_formation,
        )
        return enregistrement

    def lire_tout(self) -> list[EnregistrementFeedback]:
        """Relit le journal — utilisé par les tests et par le futur écran de supervision (E31)."""
        if not self._chemin.exists():
            return []
        lignes = self._chemin.read_text(encoding="utf-8").splitlines()
        return [EnregistrementFeedback(**json.loads(ligne)) for ligne in lignes if ligne.strip()]
