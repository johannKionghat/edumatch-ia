"""Tests de l'outillage de l'exercice des droits (T8) : retrouver, exporter, effacer une
trace liée à un identifiant, dans le journal d'inférence ou de supervision — voir le
docstring de `api/droits.py`.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from edumatch.api.audit_purge import chemins_audit, chemins_supervision
from edumatch.api.droits import _chemin_trace, effacer, exporter, retrouver
from edumatch.config import Settings, load_settings

HORODATAGE = datetime(2026, 9, 1, tzinfo=UTC).isoformat()


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    base = load_settings("dev")
    return base.model_copy(update={"data_root": tmp_path})


def _ligne_audit(identifiant_execution: str) -> dict:
    return {
        "identifiant_audit": f"audit-{identifiant_execution}",
        "horodatage": HORODATAGE,
        "identifiant_execution": identifiant_execution,
        "version_modele": "0.1.0",
        "empreinte_commit": "abc1234",
        "entrees": {"session": 2025, "type_bac": "bg", "boursier": False},
        "sortie": {"n_formations_disponibles": 1, "recommandations": []},
        "decision_conseiller": None,
        "pseudonymise": False,
    }


def _ligne_feedback(identifiant_feedback: str, identifiant_conseiller: str = "conseiller-1") -> dict:
    return {
        "identifiant_feedback": identifiant_feedback,
        "horodatage": HORODATAGE,
        "session": 2025,
        "identifiant_formation": "F1",
        "type_bac": "bg",
        "boursier": False,
        "decision": "retenue",
        "motif": None,
        "identifiant_conseiller": identifiant_conseiller,
    }


def _ecrire(chemin: Path, lignes: list[dict]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("".join(json.dumps(ligne, ensure_ascii=False) + "\n" for ligne in lignes), encoding="utf-8")


def _lire(chemin: Path) -> list[dict]:
    if not chemin.exists():
        return []
    return [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines() if ligne.strip()]


# ─── Retrouver ─────────────────────────────────────────────────────────────


def test_retrouver_trouve_par_identifiant_de_requete(settings: Settings) -> None:
    _ecrire(chemins_audit(settings).journal, [_ligne_audit("exec-1"), _ligne_audit("exec-2")])

    resultat = retrouver(settings, journal="inference", identifiant="exec-1")

    assert len(resultat) == 1
    assert resultat[0]["identifiant_execution"] == "exec-1"


def test_retrouver_trouve_aussi_par_jeton_pseudonymise(settings: Settings) -> None:
    """Après une purge, `identifiant_execution` porte un jeton non réversible : la recherche
    par ce jeton doit continuer de fonctionner, la ligne n'ayant pas disparu du journal."""
    ligne = _ligne_audit("jeton-pseudonymise")
    ligne["pseudonymise"] = True
    _ecrire(chemins_audit(settings).journal, [ligne])

    resultat = retrouver(settings, journal="inference", identifiant="jeton-pseudonymise")

    assert len(resultat) == 1


def test_retrouver_sur_le_journal_de_supervision(settings: Settings) -> None:
    _ecrire(chemins_supervision(settings).journal, [_ligne_feedback("feedback-1"), _ligne_feedback("feedback-2")])

    resultat = retrouver(settings, journal="supervision", identifiant="feedback-1")

    assert len(resultat) == 1
    assert resultat[0]["identifiant_feedback"] == "feedback-1"


def test_retrouver_sans_correspondance_renvoie_une_liste_vide(settings: Settings) -> None:
    _ecrire(chemins_audit(settings).journal, [_ligne_audit("exec-1")])

    assert retrouver(settings, journal="inference", identifiant="inconnu") == []


def test_retrouver_sans_journal_existant_ne_leve_pas(settings: Settings) -> None:
    assert not chemins_audit(settings).journal.exists()

    assert retrouver(settings, journal="inference", identifiant="peu-importe") == []


# ─── Exporter ──────────────────────────────────────────────────────────────


def test_exporter_json_contient_la_ligne_trouvee(settings: Settings) -> None:
    _ecrire(chemins_audit(settings).journal, [_ligne_audit("exec-1")])

    contenu = exporter(settings, journal="inference", identifiant="exec-1", format="json")

    lignes = json.loads(contenu)
    assert len(lignes) == 1
    assert lignes[0]["identifiant_execution"] == "exec-1"


def test_exporter_csv_est_lisible_par_le_module_csv(settings: Settings) -> None:
    _ecrire(chemins_supervision(settings).journal, [_ligne_feedback("feedback-1")])

    contenu = exporter(settings, journal="supervision", identifiant="feedback-1", format="csv")

    lignes = list(csv.DictReader(io.StringIO(contenu)))
    assert len(lignes) == 1
    assert lignes[0]["identifiant_feedback"] == "feedback-1"


def test_exporter_csv_sans_resultat_ne_leve_pas(settings: Settings) -> None:
    _ecrire(chemins_audit(settings).journal, [_ligne_audit("exec-1")])

    assert exporter(settings, journal="inference", identifiant="inconnu", format="csv") == ""


def test_exporter_format_non_supporte_leve_value_error(settings: Settings) -> None:
    with pytest.raises(ValueError):
        exporter(settings, journal="inference", identifiant="exec-1", format="xml")


def test_exporter_ne_modifie_pas_le_journal(settings: Settings) -> None:
    chemin = chemins_audit(settings).journal
    _ecrire(chemin, [_ligne_audit("exec-1")])
    contenu_avant = chemin.read_text(encoding="utf-8")

    exporter(settings, journal="inference", identifiant="exec-1")

    assert chemin.read_text(encoding="utf-8") == contenu_avant


# ─── Effacer ───────────────────────────────────────────────────────────────


def test_effacer_simulation_ne_modifie_rien_sur_disque(settings: Settings) -> None:
    chemin = chemins_audit(settings).journal
    _ecrire(chemin, [_ligne_audit("exec-1"), _ligne_audit("exec-2")])
    contenu_avant = chemin.read_text(encoding="utf-8")

    nb_effacees = effacer(settings, journal="inference", identifiant="exec-1", simulation=True)

    assert nb_effacees == 1
    assert chemin.read_text(encoding="utf-8") == contenu_avant


def test_effacer_reel_retire_exactement_la_ligne_visee(settings: Settings) -> None:
    chemin = chemins_supervision(settings).journal
    _ecrire(chemin, [_ligne_feedback("a-garder"), _ligne_feedback("a-effacer")])

    nb_effacees = effacer(settings, journal="supervision", identifiant="a-effacer", simulation=False)

    assert nb_effacees == 1
    restantes = _lire(chemin)
    assert len(restantes) == 1
    assert restantes[0]["identifiant_feedback"] == "a-garder"


def test_effacer_est_idempotent(settings: Settings) -> None:
    chemin = chemins_audit(settings).journal
    _ecrire(chemin, [_ligne_audit("exec-1"), _ligne_audit("exec-2")])

    premier = effacer(settings, journal="inference", identifiant="exec-1", simulation=False)
    second = effacer(settings, journal="inference", identifiant="exec-1", simulation=False)

    assert premier == 1
    assert second == 0  # déjà effacée, plus rien à retirer
    assert len(_lire(chemin)) == 1


def test_effacer_sans_correspondance_laisse_le_journal_intact(settings: Settings) -> None:
    chemin = chemins_audit(settings).journal
    _ecrire(chemin, [_ligne_audit("exec-1")])
    contenu_avant = chemin.read_text(encoding="utf-8")

    nb_effacees = effacer(settings, journal="inference", identifiant="inconnu", simulation=False)

    assert nb_effacees == 0
    assert chemin.read_text(encoding="utf-8") == contenu_avant


# ─── Trace d'exécution : jamais de donnée personnelle ───────────────────────


def test_chaque_operation_journalise_une_trace_sans_donnee_personnelle(settings: Settings) -> None:
    _ecrire(chemins_audit(settings).journal, [_ligne_audit("exec-secret")])

    retrouver(settings, journal="inference", identifiant="exec-secret")
    exporter(settings, journal="inference", identifiant="exec-secret")
    effacer(settings, journal="inference", identifiant="exec-secret", simulation=True)

    lignes_trace = _lire(_chemin_trace(settings))
    assert len(lignes_trace) == 3
    operations = [ligne["operation"] for ligne in lignes_trace]
    assert operations == ["retrouver", "exporter", "effacer_simulation"]
    for ligne in lignes_trace:
        assert set(ligne.keys()) == {"horodatage", "operation", "journal", "lignes_concernees"}
        contenu_serialise = json.dumps(ligne, ensure_ascii=False)
        assert "exec-secret" not in contenu_serialise  # jamais l'identifiant recherché
        assert ligne["lignes_concernees"] == 1


def test_trace_effacement_reel_porte_operation_effacer(settings: Settings) -> None:
    _ecrire(chemins_audit(settings).journal, [_ligne_audit("exec-1")])

    effacer(settings, journal="inference", identifiant="exec-1", simulation=False)

    lignes_trace = _lire(_chemin_trace(settings))
    assert lignes_trace[0]["operation"] == "effacer"


# ─── Interface en ligne de commande ─────────────────────────────────────────


def test_cli_retrouver_affiche_le_resultat(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from edumatch.api import droits

    _ecrire(chemins_audit(settings).journal, [_ligne_audit("exec-1")])
    monkeypatch.setattr(droits, "get_settings", lambda: settings)

    droits.main(["retrouver", "--journal", "inference", "--identifiant", "exec-1"])

    sortie = json.loads(capsys.readouterr().out)
    assert len(sortie) == 1
    assert sortie[0]["identifiant_execution"] == "exec-1"


def test_cli_effacer_simule_par_defaut(settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from edumatch.api import droits

    chemin = chemins_audit(settings).journal
    _ecrire(chemin, [_ligne_audit("exec-1")])
    monkeypatch.setattr(droits, "get_settings", lambda: settings)

    droits.main(["effacer", "--journal", "inference", "--identifiant", "exec-1"])

    sortie = json.loads(capsys.readouterr().out)
    assert sortie["mode"] == "simulation"
    assert len(_lire(chemin)) == 1  # rien n'a été modifié


def test_cli_effacer_appliquer_efface_reellement(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from edumatch.api import droits

    chemin = chemins_audit(settings).journal
    _ecrire(chemin, [_ligne_audit("exec-1")])
    monkeypatch.setattr(droits, "get_settings", lambda: settings)

    droits.main(["effacer", "--journal", "inference", "--identifiant", "exec-1", "--appliquer"])

    sortie = json.loads(capsys.readouterr().out)
    assert sortie["mode"] == "reel"
    assert _lire(chemin) == []
