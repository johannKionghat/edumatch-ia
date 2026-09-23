"""Registre d'incident (action AI-1) : création, clôture, délai des 72 heures, refus d'une donnée personnelle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from edumatch.gouvernance import incidents as reg

DECLARATION = {
    "nature": "Journal d'audit accessible en lecture à un compte de service qui n'en avait pas besoin.",
    "categories": ["cellule prédite", "identifiant de conseiller"],
    "risque": "faible",
    "justification_risque": "Aucune donnée directement identifiante dans le journal, accès interne uniquement.",
    "notification_cnil": False,
    "justification_notification": "Risque faible pour les personnes, documenté au titre de l'article 33.5.",
}


@pytest.fixture()
def registre(tmp_path: Path) -> Path:
    return tmp_path / "registre-incidents.json"


def test_declaration_cree_un_incident_ouvert(registre: Path) -> None:
    incident = reg.declarer(**DECLARATION, chemin=registre)
    assert incident.identifiant.startswith("INC-")
    assert incident.statut == "ouvert"
    assert incident.exercice is False
    assert incident.horodatage_notification is None  # pas de notification, donc pas d'horodatage
    assert reg.charger(registre)[0].identifiant == incident.identifiant


def test_identifiants_incrementes_par_annee(registre: Path) -> None:
    premier = reg.declarer(**DECLARATION, chemin=registre)
    second = reg.declarer(**DECLARATION, chemin=registre)
    annee = datetime.now(UTC).year
    assert (premier.identifiant, second.identifiant) == (f"INC-{annee}-001", f"INC-{annee}-002")


def test_notification_horodatee_quand_elle_est_decidee(registre: Path) -> None:
    incident = reg.declarer(**{**DECLARATION, "notification_cnil": True}, chemin=registre)
    assert incident.horodatage_notification is not None


def test_cloture_exige_une_mesure_et_enregistre_la_revue(registre: Path) -> None:
    incident = reg.declarer(**DECLARATION, chemin=registre)
    with pytest.raises(reg.ErreurRegistreIncidents, match="mesure"):
        reg.clore(
            incident.identifiant, mesures=[], revue_matrice_risques="R3 revu", chemin=registre
        )
    clos = reg.clore(
        incident.identifiant,
        mesures=["Droits du compte de service restreints en lecture seule sur le catalogue."],
        revue_matrice_risques="Risque R3 revu le 23 septembre 2026, aucune réouverture de l'AIPD.",
        chemin=registre,
    )
    assert clos.statut == "clos"
    assert clos.date_cloture is not None
    with pytest.raises(reg.ErreurRegistreIncidents, match="déjà clos"):
        reg.clore(
            incident.identifiant, mesures=["autre"], revue_matrice_risques="x", chemin=registre
        )


def test_cloture_dun_incident_inconnu_est_refusee(registre: Path) -> None:
    with pytest.raises(reg.ErreurRegistreIncidents, match="INC-1999-001"):
        reg.clore("INC-1999-001", mesures=["m"], revue_matrice_risques="r", chemin=registre)


# ─── Le délai des 72 heures (article 33.1) ───────────────────────────────────


def test_echeance_calculee_depuis_la_prise_de_connaissance_pas_la_detection(registre: Path) -> None:
    incident = reg.declarer(
        **DECLARATION,
        date_detection="2026-09-20T08:00:00+00:00",
        date_prise_de_connaissance="2026-09-22T09:00:00+00:00",
        chemin=registre,
    )
    assert incident.echeance_notification() == datetime(2026, 9, 25, 9, 0, tzinfo=UTC)


def test_heures_restantes_positives_puis_negatives(registre: Path) -> None:
    prise = datetime.now(UTC) - timedelta(hours=24)
    incident = reg.declarer(
        **DECLARATION, date_prise_de_connaissance=prise.isoformat(), chemin=registre
    )
    assert 47 <= incident.heures_restantes() <= 48
    depassee = datetime.now(UTC) - timedelta(hours=80)
    tardif = reg.declarer(
        **DECLARATION, date_prise_de_connaissance=depassee.isoformat(), chemin=registre
    )
    assert tardif.heures_restantes() < 0


def test_date_illisible_est_refusee(registre: Path) -> None:
    with pytest.raises(reg.ErreurRegistreIncidents, match="ISO 8601"):
        reg.declarer(**DECLARATION, date_prise_de_connaissance="hier matin", chemin=registre)


def test_risque_inconnu_est_refuse(registre: Path) -> None:
    with pytest.raises(reg.ErreurRegistreIncidents, match="Risque"):
        reg.declarer(**{**DECLARATION, "risque": "modéré"}, chemin=registre)


# ─── Aucune donnée personnelle dans le registre ──────────────────────────────


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [
        ("nature", "Le dossier de jean.dupont@lycee.fr a été exposé."),
        ("justification_risque", "Le candidat a appelé au 06 12 34 56 78 pour signaler la fuite."),
        ("justification_notification", "Numéro de sécurité sociale concerné : 1850578006048 25."),
    ],
)
def test_donnee_identifiante_refusee_a_la_declaration(
    registre: Path, champ: str, valeur: str
) -> None:
    with pytest.raises(reg.ErreurDonneePersonnelle):
        reg.declarer(**{**DECLARATION, champ: valeur}, chemin=registre)
    assert not registre.exists()  # rien n'est écrit quand l'entrée est refusée


def test_donnee_identifiante_refusee_dans_les_categories(registre: Path) -> None:
    with pytest.raises(reg.ErreurDonneePersonnelle, match="categories_donnees"):
        reg.declarer(
            **{**DECLARATION, "categories": ["adresse : contact@exemple.fr"]}, chemin=registre
        )


def test_donnee_identifiante_refusee_a_la_cloture(registre: Path) -> None:
    incident = reg.declarer(**DECLARATION, chemin=registre)
    with pytest.raises(reg.ErreurDonneePersonnelle):
        reg.clore(
            incident.identifiant,
            mesures=["Compte de eleve.test@ac-paris.fr supprimé."],
            revue_matrice_risques="R3",
            chemin=registre,
        )
    assert reg.charger(registre)[0].statut == "ouvert"  # la clôture refusée ne modifie rien


def test_le_message_de_refus_ne_recopie_pas_la_valeur(registre: Path) -> None:
    valeur = "contact.prive@exemple.fr"
    with pytest.raises(reg.ErreurDonneePersonnelle) as erreur:
        reg.declarer(**{**DECLARATION, "nature": f"Fuite concernant {valeur}."}, chemin=registre)
    assert valeur not in str(erreur.value)


def test_texte_sans_donnee_personnelle_est_accepte() -> None:
    reg.verifier_absence_donnee_personnelle(
        {"nature": "Catégories concernées : type de baccalauréat, statut de boursier, département."}
    )


# ─── Le registre versionné du dépôt ──────────────────────────────────────────


def test_registre_du_depot_lisible_et_sans_donnee_personnelle() -> None:
    """Non-régression sur le registre réel : il se charge, et aucune entrée ne porte
    d'identifiant direct."""
    incidents = reg.charger()
    assert incidents, "le registre doit porter au moins l'exercice à blanc"
    for incident in incidents:
        reg.verifier_absence_donnee_personnelle(
            {
                "nature": incident.nature,
                "categories_donnees": incident.categories_donnees,
                "justification_risque": incident.justification_risque,
                "mesures_correction": incident.mesures_correction,
            }
        )


def test_un_exercice_a_blanc_est_consigne_et_clos() -> None:
    """Critère de levée d'AI-1 : registre existant et exercice à blanc réalisé."""
    exercices = [i for i in reg.charger() if i.exercice]
    assert exercices, "aucun exercice à blanc au registre"
    assert all(i.statut == "clos" for i in exercices)
    assert all(i.mesures_correction for i in exercices)
