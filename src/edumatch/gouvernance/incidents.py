"""Registre d'incident et de violation de données (action AI-1 du plan de gouvernance).

La procédure est écrite dans `docs/gouvernance.html` : détection, qualification, confinement,
reporting, apprentissage. Ce module en porte la trace écrite, versionnée avec le code, et
calcule le délai qui compte réellement : l'article 33.1 du RGPD impose de notifier la CNIL dans
les 72 heures suivant la **prise de connaissance**, pas la détection technique. Les deux dates
sont donc distinctes et toutes deux obligatoires.

## Ce que le registre contient, et ce qu'il ne contiendra jamais

L'article 33.5 exige de documenter toute violation, y compris celles qui ne sont pas notifiées,
avec ses effets et les mesures prises. Le registre porte donc la nature de l'incident, les
**catégories** de données concernées, le risque évalué, la décision de notification et sa
justification, l'information des personnes, les mesures de correction et le renvoi vers la revue
de la matrice des risques.

Il ne porte **aucune donnée personnelle** : ni identité, ni adresse électronique, ni numéro. Un
registre d'incident consulté par plusieurs personnes et versionné dans un dépôt serait le
dernier endroit où recopier les données qui viennent de fuiter. `verifier_absence_donnee_personnelle`
refuse l'écriture plutôt que de faire confiance à la vigilance du rédacteur.

## Le fichier

`reports/registre-incidents.json`, une liste d'entrées, lisible sans outil. Un incident
d'exercice porte `exercice: true` et le reste de son cycle de vie est identique : c'est ce qui
permet de répéter la procédure sans salir le registre réel ni prétendre à une violation qui
n'a pas eu lieu.

    python -m edumatch.gouvernance.incidents lister
    python -m edumatch.gouvernance.incidents declarer --nature "..." --categories "..." [--exercice]
    python -m edumatch.gouvernance.incidents clore --id INC-2026-001 --mesures "..."
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
CHEMIN_REGISTRE = RACINE / "reports" / "registre-incidents.json"
DELAI_NOTIFICATION = timedelta(hours=72)

RISQUES = ("aucun", "faible", "eleve")
STATUTS = ("ouvert", "clos")

# Motifs de données identifiantes évidentes. Volontairement peu nombreux et sûrs : le but est
# d'arrêter une erreur de rédaction (recopier l'adresse du candidat concerné), pas de prétendre
# détecter toute donnée personnelle, ce qu'aucune expression régulière ne sait faire.
MOTIFS_DONNEE_PERSONNELLE: tuple[tuple[str, str], ...] = (
    (r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}", "une adresse électronique"),
    (r"(?<!\d)(?:\+33|0)\s?[1-9](?:[\s.-]?\d{2}){4}(?!\d)", "un numéro de téléphone"),
    (
        r"(?<!\d)[12]\d{2}(?:0[1-9]|1[0-2])\d{2}\d{3}\d{3}(?:\s?\d{2})?(?!\d)",
        "un numéro de sécurité sociale",
    ),
    (r"\bFR\d{2}[\sA-Z0-9]{11,}\b", "un identifiant bancaire"),
)


class ErreurRegistreIncidents(RuntimeError):
    """L'entrée demandée est invalide, ou l'incident visé n'existe pas."""


class ErreurDonneePersonnelle(ErreurRegistreIncidents):
    """Un champ contient une donnée identifiante : l'écriture est refusée."""


@dataclass
class Incident:
    """Une entrée du registre. Les dates sont en ISO 8601, fuseau explicite."""

    identifiant: str
    exercice: bool
    date_detection: str
    date_prise_de_connaissance: str
    nature: str
    categories_donnees: list[str]
    risque_evalue: str
    justification_risque: str
    notification_cnil: bool
    justification_notification: str
    horodatage_notification: str | None = None
    information_personnes: str = "non requise"
    mesures_correction: list[str] = field(default_factory=list)
    revue_matrice_risques: str = "à planifier"
    statut: str = "ouvert"
    date_cloture: str | None = None

    def echeance_notification(self) -> datetime:
        """72 heures après la prise de connaissance (article 33.1)."""
        return _instant(self.date_prise_de_connaissance) + DELAI_NOTIFICATION

    def heures_restantes(self, maintenant: datetime | None = None) -> float:
        """Heures restantes avant l'échéance ; négatif si elle est dépassée."""
        maintenant = maintenant or datetime.now(UTC)
        return round((self.echeance_notification() - maintenant).total_seconds() / 3600, 1)


def _instant(valeur: str) -> datetime:
    try:
        instant = datetime.fromisoformat(valeur)
    except ValueError as erreur:
        raise ErreurRegistreIncidents(
            f"Date {valeur!r} illisible : format ISO 8601 attendu."
        ) from erreur
    return instant if instant.tzinfo else instant.replace(tzinfo=UTC)


def verifier_absence_donnee_personnelle(champs: dict[str, object]) -> None:
    """Refuse l'écriture si un champ porte une donnée identifiante évidente.

    Le message nomme le champ et la nature de ce qui a été reconnu, jamais la valeur : un
    message d'erreur recopié dans un ticket ne doit pas rediffuser ce qu'on vient de refuser.
    """
    for nom, valeur in champs.items():
        textes = valeur if isinstance(valeur, list) else [valeur]
        for texte in textes:
            if not isinstance(texte, str):
                continue
            for motif, quoi in MOTIFS_DONNEE_PERSONNELLE:
                if re.search(motif, texte):
                    raise ErreurDonneePersonnelle(
                        f"Le champ {nom!r} contient ce qui ressemble à {quoi}. Le registre ne porte "
                        "que des catégories de données, jamais une donnée personnelle : reformuler "
                        "sans l'identifiant."
                    )


def charger(chemin: Path = CHEMIN_REGISTRE) -> list[Incident]:
    if not chemin.is_file():
        return []
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    return [Incident(**entree) for entree in contenu]


def ecrire(incidents: list[Incident], chemin: Path = CHEMIN_REGISTRE) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    corps = json.dumps([asdict(i) for i in incidents], ensure_ascii=False, indent=2) + "\n"
    chemin.write_text(corps, encoding="utf-8", newline="\n")


def prochain_identifiant(incidents: list[Incident], annee: int) -> str:
    rangs = [
        int(i.identifiant.rsplit("-", 1)[1])
        for i in incidents
        if i.identifiant.startswith(f"INC-{annee}-")
    ]
    return f"INC-{annee}-{max(rangs, default=0) + 1:03d}"


def declarer(
    *,
    nature: str,
    categories: list[str],
    risque: str,
    justification_risque: str,
    notification_cnil: bool,
    justification_notification: str,
    date_detection: str | None = None,
    date_prise_de_connaissance: str | None = None,
    information_personnes: str = "non requise",
    exercice: bool = False,
    chemin: Path = CHEMIN_REGISTRE,
) -> Incident:
    """Ajoute un incident ouvert au registre et retourne l'entrée écrite."""
    if risque not in RISQUES:
        raise ErreurRegistreIncidents(f"Risque {risque!r} inconnu : valeurs acceptées {RISQUES}.")
    verifier_absence_donnee_personnelle(
        {
            "nature": nature,
            "categories_donnees": categories,
            "justification_risque": justification_risque,
            "justification_notification": justification_notification,
            "information_personnes": information_personnes,
        }
    )
    maintenant = datetime.now(UTC).isoformat(timespec="seconds")
    prise = date_prise_de_connaissance or maintenant
    incidents = charger(chemin)
    incident = Incident(
        identifiant=prochain_identifiant(incidents, _instant(prise).year),
        exercice=exercice,
        date_detection=date_detection or maintenant,
        date_prise_de_connaissance=prise,
        nature=nature,
        categories_donnees=list(categories),
        risque_evalue=risque,
        justification_risque=justification_risque,
        notification_cnil=notification_cnil,
        justification_notification=justification_notification,
        horodatage_notification=maintenant if notification_cnil else None,
        information_personnes=information_personnes,
    )
    incidents.append(incident)
    ecrire(incidents, chemin)
    return incident


def clore(
    identifiant: str,
    *,
    mesures: list[str],
    revue_matrice_risques: str,
    chemin: Path = CHEMIN_REGISTRE,
) -> Incident:
    """Clôt un incident ouvert : mesures de correction et revue de la matrice des risques."""
    if not mesures:
        raise ErreurRegistreIncidents(
            "Clôture refusée : au moins une mesure de correction est requise."
        )
    verifier_absence_donnee_personnelle(
        {"mesures_correction": mesures, "revue_matrice_risques": revue_matrice_risques}
    )
    incidents = charger(chemin)
    for incident in incidents:
        if incident.identifiant != identifiant:
            continue
        if incident.statut == "clos":
            raise ErreurRegistreIncidents(
                f"{identifiant} est déjà clos le {incident.date_cloture}."
            )
        incident.mesures_correction = list(mesures)
        incident.revue_matrice_risques = revue_matrice_risques
        incident.statut = "clos"
        incident.date_cloture = datetime.now(UTC).isoformat(timespec="seconds")
        ecrire(incidents, chemin)
        return incident
    raise ErreurRegistreIncidents(f"Aucun incident {identifiant!r} au registre.")


def _ligne_lisible(incident: Incident, maintenant: datetime | None = None) -> str:
    marque = " [exercice]" if incident.exercice else ""
    if incident.statut == "clos":
        delai = f"clos le {incident.date_cloture}"
    else:
        heures = incident.heures_restantes(maintenant)
        delai = (
            f"{heures} h avant l'échéance des 72 h"
            if heures >= 0
            else f"échéance dépassée de {abs(heures)} h"
        )
    return (
        f"{incident.identifiant}{marque} · {incident.statut} · risque {incident.risque_evalue} · "
        f"notification CNIL : {'oui' if incident.notification_cnil else 'non'} · {delai}\n"
        f"    {incident.nature}\n"
        f"    catégories : {', '.join(incident.categories_donnees)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Registre d'incident et de violation de données.")
    sous = parser.add_subparsers(dest="commande", required=True)

    p_declarer = sous.add_parser("declarer", help="Ajoute un incident ouvert au registre.")
    p_declarer.add_argument(
        "--nature", required=True, help="ce qui s'est passé, sans donnée personnelle"
    )
    p_declarer.add_argument(
        "--categories", required=True, nargs="+", help="catégories de données concernées"
    )
    p_declarer.add_argument("--risque", required=True, choices=RISQUES)
    p_declarer.add_argument("--justification-risque", required=True)
    p_declarer.add_argument("--notifier-cnil", action="store_true", help="la CNIL est notifiée")
    p_declarer.add_argument("--justification-notification", required=True)
    p_declarer.add_argument("--date-detection", help="ISO 8601 ; par défaut maintenant")
    p_declarer.add_argument("--date-prise-de-connaissance", help="ISO 8601 ; par défaut maintenant")
    p_declarer.add_argument("--information-personnes", default="non requise")
    p_declarer.add_argument(
        "--exercice", action="store_true", help="exercice à blanc, jamais une vraie violation"
    )

    p_clore = sous.add_parser("clore", help="Clôt un incident ouvert.")
    p_clore.add_argument("--id", required=True, dest="identifiant")
    p_clore.add_argument("--mesures", required=True, nargs="+")
    p_clore.add_argument("--revue-matrice-risques", required=True)

    sous.add_parser("lister", help="Liste les incidents et le délai restant.")

    args = parser.parse_args(argv)
    try:
        if args.commande == "declarer":
            incident = declarer(
                nature=args.nature,
                categories=args.categories,
                risque=args.risque,
                justification_risque=args.justification_risque,
                notification_cnil=args.notifier_cnil,
                justification_notification=args.justification_notification,
                date_detection=args.date_detection,
                date_prise_de_connaissance=args.date_prise_de_connaissance,
                information_personnes=args.information_personnes,
                exercice=args.exercice,
            )
            print(f"Incident {incident.identifiant} déclaré.")
            print(_ligne_lisible(incident))
        elif args.commande == "clore":
            incident = clore(
                args.identifiant,
                mesures=args.mesures,
                revue_matrice_risques=args.revue_matrice_risques,
            )
            print(f"Incident {incident.identifiant} clos.")
            print(_ligne_lisible(incident))
        else:
            incidents = charger()
            if not incidents:
                print("Registre vide : aucun incident déclaré.")
                return 0
            ouverts = sum(1 for i in incidents if i.statut == "ouvert")
            print(f"{len(incidents)} incident(s), dont {ouverts} ouvert(s) :")
            for incident in incidents:
                print(_ligne_lisible(incident))
    except ErreurRegistreIncidents as erreur:
        print(str(erreur), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
