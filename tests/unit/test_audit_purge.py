"""Tests de la purge du journal d'audit : les trois paliers de conservation décidés par la
gouvernance (`docs/registres.html`, T5) doivent être **exécutables**, pas seulement écrits —
voir le docstring de `api/audit_purge.py`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from edumatch.api.audit_purge import chemins_audit, purger
from edumatch.config import Settings, load_settings

MAINTENANT = datetime(2026, 8, 30, tzinfo=UTC)
DELAI_PSEUDO_JOURS = 10
DELAI_AGREGATION_JOURS = 30


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    """Les vrais YAML du dépôt, avec une racine de données jetable et des délais raccourcis
    pour que les tests n'aient pas à écrire des horodatages vieux de plusieurs années."""
    base = load_settings("dev")
    audit = base.api.audit.model_copy(
        update={
            "delai_pseudonymisation_jours": DELAI_PSEUDO_JOURS,
            "delai_agregation_jours": DELAI_AGREGATION_JOURS,
        }
    )
    api = base.api.model_copy(update={"audit": audit})
    return base.model_copy(update={"data_root": tmp_path, "api": api})


def _ligne(
    *,
    horodatage: datetime,
    identifiant_execution: str = "exec-original",
    session: int = 2025,
    type_bac: str = "bg",
    boursier: bool = False,
    pseudonymise: bool = False,
) -> dict:
    return {
        "identifiant_audit": f"audit-{identifiant_execution}",
        "horodatage": horodatage.isoformat(),
        "identifiant_execution": identifiant_execution,
        "version_modele": "0.1.0",
        "empreinte_commit": "abc1234",
        "entrees": {
            "session": session,
            "type_bac": type_bac,
            "boursier": boursier,
            "type_formation": None,
            "domaine": None,
            "departement": "75",
        },
        "sortie": {"n_formations_disponibles": 1, "recommandations": [{"identifiant_formation": "F1", "score": 0.5}]},
        "decision_conseiller": None,
        "pseudonymise": pseudonymise,
    }


def _ecrire_journal(settings: Settings, lignes: list[dict]) -> Path:
    chemin = chemins_audit(settings).journal
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("".join(json.dumps(ligne, ensure_ascii=False) + "\n" for ligne in lignes), encoding="utf-8")
    return chemin


def _lire_lignes(chemin: Path) -> list[dict]:
    return [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines() if ligne.strip()]


# ─── Classement par palier ────────────────────────────────────────────────────


def test_purge_conserve_en_clair_une_ligne_recente(settings: Settings) -> None:
    chemin = _ecrire_journal(settings, [_ligne(horodatage=MAINTENANT - timedelta(days=1))])
    rapport = purger(settings, maintenant=MAINTENANT, simulation=False)

    assert rapport.lignes_conservees_en_clair == 1
    assert rapport.lignes_pseudonymisees == 0
    assert rapport.lignes_agregees == 0
    restantes = _lire_lignes(chemin)
    assert len(restantes) == 1
    assert restantes[0]["identifiant_execution"] == "exec-original"
    assert restantes[0]["pseudonymise"] is False


def test_purge_pseudonymise_le_palier_intermediaire(settings: Settings) -> None:
    age_intermediaire = MAINTENANT - timedelta(days=DELAI_PSEUDO_JOURS + 1)
    chemin = _ecrire_journal(settings, [_ligne(horodatage=age_intermediaire)])
    rapport = purger(settings, maintenant=MAINTENANT, simulation=False)

    assert rapport.lignes_pseudonymisees == 1
    assert rapport.lignes_conservees_en_clair == 0
    assert rapport.lignes_agregees == 0
    restantes = _lire_lignes(chemin)
    assert len(restantes) == 1
    assert restantes[0]["pseudonymise"] is True
    assert restantes[0]["identifiant_execution"] != "exec-original"
    # Les variables d'entrée et la sortie ne sont pas touchées : audit d'équité et dérive restent possibles.
    assert restantes[0]["entrees"]["type_bac"] == "bg"
    assert restantes[0]["sortie"]["recommandations"][0]["identifiant_formation"] == "F1"


def test_purge_agrege_et_supprime_le_palier_final(settings: Settings) -> None:
    age_ancien = MAINTENANT - timedelta(days=DELAI_AGREGATION_JOURS + 1)
    chemin = _ecrire_journal(settings, [_ligne(horodatage=age_ancien, session=2025, type_bac="bg", boursier=False)])
    rapport = purger(settings, maintenant=MAINTENANT, simulation=False)

    assert rapport.lignes_agregees == 1
    assert _lire_lignes(chemin) == []  # la ligne d'inférence a disparu, pas seulement modifiée

    agregats = json.loads(chemins_audit(settings).agregats.read_text(encoding="utf-8"))
    cle = "2025|bg|False"
    assert agregats[cle]["nb_inferences"] == 1
    assert agregats[cle]["session"] == "2025"


# ─── Prudence : simulation ────────────────────────────────────────────────────


def test_purge_simulation_ne_modifie_rien_sur_disque(settings: Settings) -> None:
    lignes = [
        _ligne(horodatage=MAINTENANT - timedelta(days=1)),
        _ligne(horodatage=MAINTENANT - timedelta(days=DELAI_PSEUDO_JOURS + 1), identifiant_execution="exec-2"),
        _ligne(horodatage=MAINTENANT - timedelta(days=DELAI_AGREGATION_JOURS + 1), identifiant_execution="exec-3"),
    ]
    chemin = _ecrire_journal(settings, lignes)
    contenu_avant = chemin.read_text(encoding="utf-8")

    rapport = purger(settings, maintenant=MAINTENANT, simulation=True)

    assert rapport.mode == "simulation"
    assert rapport.lignes_examinees == 3
    assert rapport.lignes_conservees_en_clair == 1
    assert rapport.lignes_pseudonymisees == 1
    assert rapport.lignes_agregees == 1
    assert chemin.read_text(encoding="utf-8") == contenu_avant  # rien n'a bougé
    assert not chemins_audit(settings).agregats.exists()


def test_purge_simulation_est_tout_de_meme_journalisee(settings: Settings) -> None:
    """Une purge n'est jamais silencieuse, même quand elle ne modifie rien (voir le docstring
    du module) : chaque exécution laisse une trace dans purges.jsonl."""
    _ecrire_journal(settings, [_ligne(horodatage=MAINTENANT - timedelta(days=1))])
    purger(settings, maintenant=MAINTENANT, simulation=True)

    lignes_purges = _lire_lignes(chemins_audit(settings).purges)
    assert len(lignes_purges) == 1
    assert lignes_purges[0]["mode"] == "simulation"
    assert lignes_purges[0]["lignes_examinees"] == 1


# ─── Suppression réelle : ce qu'annonce le rapport, et rien d'autre ───────────


def test_purge_reelle_supprime_exactement_ce_quelle_annonce(settings: Settings) -> None:
    lignes = [
        _ligne(horodatage=MAINTENANT - timedelta(days=1), identifiant_execution="frais"),
        _ligne(
            horodatage=MAINTENANT - timedelta(days=DELAI_PSEUDO_JOURS + 1),
            identifiant_execution="a-pseudonymiser",
        ),
        _ligne(
            horodatage=MAINTENANT - timedelta(days=DELAI_AGREGATION_JOURS + 1),
            identifiant_execution="a-agreger",
        ),
    ]
    chemin = _ecrire_journal(settings, lignes)

    rapport = purger(settings, maintenant=MAINTENANT, simulation=False)

    restantes = _lire_lignes(chemin)
    assert len(restantes) == 2  # la ligne agrégée a disparu, les deux autres restent
    identifiants_restants = {ligne["identifiant_execution"] for ligne in restantes}
    assert "frais" in identifiants_restants  # inchangée
    assert "a-pseudonymiser" not in identifiants_restants  # remplacé par un nouveau jeton
    assert "a-agreger" not in identifiants_restants  # supprimée, agrégée ailleurs
    assert rapport.lignes_agregees == 1
    assert rapport.lignes_pseudonymisees == 1
    assert rapport.lignes_conservees_en_clair == 1

    agregats = json.loads(chemins_audit(settings).agregats.read_text(encoding="utf-8"))
    assert sum(bucket["nb_inferences"] for bucket in agregats.values()) == 1


# ─── Idempotence ───────────────────────────────────────────────────────────────


def test_purge_fonctionne_sans_journal_existant(settings: Settings) -> None:
    """Aucun appel `/matching` n'a encore eu lieu : ni le journal, ni son dossier n'existent.
    La purge (et la trace qu'elle laisse dans `purges.jsonl`) doit s'exécuter sans erreur —
    c'est le cas d'un premier déploiement, pas un cas limite exotique."""
    assert not chemins_audit(settings).journal.exists()

    rapport = purger(settings, maintenant=MAINTENANT, simulation=False)

    assert rapport.lignes_examinees == 0
    lignes_purges = _lire_lignes(chemins_audit(settings).purges)
    assert len(lignes_purges) == 1


def test_purge_est_idempotente(settings: Settings) -> None:
    lignes = [
        _ligne(horodatage=MAINTENANT - timedelta(days=1), identifiant_execution="frais"),
        _ligne(
            horodatage=MAINTENANT - timedelta(days=DELAI_PSEUDO_JOURS + 1),
            identifiant_execution="a-pseudonymiser",
        ),
        _ligne(
            horodatage=MAINTENANT - timedelta(days=DELAI_AGREGATION_JOURS + 1),
            identifiant_execution="a-agreger",
        ),
    ]
    chemin = _ecrire_journal(settings, lignes)

    purger(settings, maintenant=MAINTENANT, simulation=False)
    etat_apres_premiere_purge = chemin.read_text(encoding="utf-8")
    agregats_apres_premiere_purge = chemins_audit(settings).agregats.read_text(encoding="utf-8")

    rapport_second_passage = purger(settings, maintenant=MAINTENANT, simulation=False)

    assert chemin.read_text(encoding="utf-8") == etat_apres_premiere_purge
    assert chemins_audit(settings).agregats.read_text(encoding="utf-8") == agregats_apres_premiere_purge
    assert rapport_second_passage.lignes_agregees == 0  # plus rien à agréger, déjà fait
    assert rapport_second_passage.lignes_pseudonymisees == 1  # déjà pseudonymisée, comptée mais inchangée
    assert rapport_second_passage.lignes_conservees_en_clair == 1


# ─── Interface en ligne de commande ────────────────────────────────────────────


def _horodatage_au_palier_pseudonymisation() -> datetime:
    """Un horodatage relatif au moment réel de l'exécution (`main()` n'accepte pas de date
    injectée : il utilise l'heure système, comme un vrai déclenchement planifié) — jamais une
    date calendaire fixe, qui se déréglerait avec le temps."""
    return datetime.now(UTC) - timedelta(days=DELAI_PSEUDO_JOURS + 1)


def test_cli_simule_par_defaut(settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """`make audit-purge` (sans `--appliquer`) ne doit jamais modifier le journal : la prudence
    est le comportement par défaut, pas une option qu'il faut penser à activer."""
    from edumatch.api import audit_purge

    _ecrire_journal(settings, [_ligne(horodatage=_horodatage_au_palier_pseudonymisation())])
    monkeypatch.setattr(audit_purge, "get_settings", lambda: settings)

    audit_purge.main([])

    sortie = json.loads(capsys.readouterr().out)
    assert sortie["mode"] == "simulation"
    assert sortie["lignes_pseudonymisees"] == 1
    lignes_apres = _lire_lignes(chemins_audit(settings).journal)
    assert lignes_apres[0]["identifiant_execution"] == "exec-original"  # rien n'a été modifié


def test_cli_appliquer_execute_reellement(settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from edumatch.api import audit_purge

    _ecrire_journal(settings, [_ligne(horodatage=_horodatage_au_palier_pseudonymisation())])
    monkeypatch.setattr(audit_purge, "get_settings", lambda: settings)

    audit_purge.main(["--appliquer"])

    sortie = json.loads(capsys.readouterr().out)
    assert sortie["mode"] == "reel"
    lignes_apres = _lire_lignes(chemins_audit(settings).journal)
    assert lignes_apres[0]["pseudonymise"] is True
    assert lignes_apres[0]["identifiant_execution"] != "exec-original"
