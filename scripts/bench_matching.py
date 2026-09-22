"""Banc de latence de `/matching` : sur quoi repose `api.max_formations_evaluees`.

Mesure de bout en bout d'une requête `POST /matching` telle que le service la traite :
authentification scrypt, validation, sous-catalogue, score à trois termes, sérialisation et
journal d'audit. L'état est le vrai (`api.state.construire_etat_matching` : catalogue de la
session courante et artefacts de débouchés) ; seuls deux garde-fous sont levés pendant la
mesure, sinon elle ne pourrait pas les dépasser : le plafond lui-même, et la limitation de débit.

Deux séries :

- **tailles fixes** (100 à 5 000 formations) : lignes réelles du catalogue, tirées au hasard
  (graine fixe) et rattachées au département demandé, pour isoler l'effet du nombre de lignes ;
- **départements réels** : les plus gros départements du catalogue pour la cellule la plus
  fournie, requêtés tels quels.

Chaque point : 3 requêtes de chauffe, puis `--repetitions` requêtes chronométrées ; p50 et p95.
Profil conservateur : un domaine et un type de formation sont renseignés, ce qui ajoute le
calcul d'affinité le plus coûteux à chaque ligne.

Limite : la mesure passe par le client de test, dans le processus, sans réseau ; la machine est
celle du poste, notée dans le résultat. Un pod limité à 1 CPU peut être plus lent : ces chiffres
sont un plancher de la latence en production, pas une garantie.

    python scripts/bench_matching.py            # écrit reports/bench-matching.json
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from edumatch.api import deps  # noqa: E402
from edumatch.api.audit import JournalAudit  # noqa: E402
from edumatch.api.auth import calculer_empreinte  # noqa: E402
from edumatch.api.main import create_app  # noqa: E402
from edumatch.api.routes import matching as route_matching  # noqa: E402
from edumatch.api.state import construire_etat_matching  # noqa: E402
from edumatch.config import get_settings  # noqa: E402

SORTIE = RACINE / "reports" / "bench-matching.json"
TAILLES = (100, 250, 500, 1000, 2000, 5000)
IDENTIFIANT, MOT_DE_PASSE = "bench", "bench-mot-de-passe"
PROFIL = {
    "type_bac": "bg",
    "boursier": False,
    "type_formation": "Licence",
    "domaine": "informatique",
    "top_n": 10,
}


class _SansLimite:
    def autoriser(self, _identite: str) -> bool:
        return True


def _percentile(valeurs: list[float], p: float) -> float:
    ordonnees = sorted(valeurs)
    rang = (len(ordonnees) - 1) * p
    bas, haut = int(rang), min(int(rang) + 1, len(ordonnees) - 1)
    return ordonnees[bas] + (ordonnees[haut] - ordonnees[bas]) * (rang - bas)


def _chronometrer(client: TestClient, corps: dict, repetitions: int) -> dict:
    for _ in range(3):
        assert client.post("/matching", json=corps).status_code == 200
    durees = []
    for _ in range(repetitions):
        debut = time.perf_counter()
        reponse = client.post("/matching", json=corps)
        durees.append((time.perf_counter() - debut) * 1000)
        assert reponse.status_code == 200, reponse.text
    return {
        "n_formations": reponse.json()["n_formations_evaluees"],
        "p50_ms": round(statistics.median(durees), 1),
        "p95_ms": round(_percentile(durees, 0.95), 1),
        "max_ms": round(max(durees), 1),
        "repetitions": repetitions,
    }


def _client(etat, dossier: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[deps.get_etat_matching] = lambda: etat
    app.dependency_overrides[deps.get_limiteur_matching] = lambda: _SansLimite()
    journal = JournalAudit(dossier / "journal.jsonl")
    app.dependency_overrides[deps.get_journal_audit] = lambda: journal
    jeton = base64.b64encode(f"{IDENTIFIANT}:{MOT_DE_PASSE}".encode()).decode("ascii")
    return TestClient(app, headers={"Authorization": f"Basic {jeton}"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repetitions", type=int, default=50)
    parser.add_argument(
        "--departements", type=int, default=4, help="nombre de plus gros départements réels"
    )
    args = parser.parse_args()

    os.environ["CONSEILLER_COMPTES"] = f"{IDENTIFIANT}:{calculer_empreinte(MOT_DE_PASSE)}"
    get_settings.cache_clear()
    settings = get_settings()
    # Plafond levé pour la seule durée de la mesure : c'est lui qu'on cherche à dimensionner.
    sans_plafond = settings.model_copy(
        update={"api": settings.api.model_copy(update={"max_formations_evaluees": 10**9})}
    )
    route_matching.get_settings = lambda: sans_plafond

    etat = construire_etat_matching(settings)
    catalogue = etat.catalogue
    cellule = catalogue[
        (catalogue["type_bac"] == PROFIL["type_bac"])
        & (catalogue["boursier"] == PROFIL["boursier"])
    ]

    # La cellule la plus fournie, par département : c'est elle qui borne le plafond utile.
    par_cellule = catalogue.groupby(["dep", "type_bac", "boursier"]).size()
    plus_gros = par_cellule.groupby("dep").max().sort_values(ascending=False)

    resultats: dict = {"tailles_fixes": [], "departements_reels": []}
    with tempfile.TemporaryDirectory() as dossier:
        for taille in TAILLES:
            echantillon = cellule.sample(n=taille, random_state=20260922).assign(dep="75")
            client = _client(dataclasses.replace(etat, catalogue=echantillon), Path(dossier))
            mesure = _chronometrer(client, {**PROFIL, "departement": "75"}, args.repetitions)
            resultats["tailles_fixes"].append(mesure)
            print(
                f"taille {taille:>5} : p50 {mesure['p50_ms']:>7} ms  p95 {mesure['p95_ms']:>7} ms",
                flush=True,
            )

        client = _client(etat, Path(dossier))
        for code in plus_gros.index[: args.departements]:
            (type_bac, boursier) = par_cellule.loc[code].idxmax()
            corps = {
                **PROFIL,
                "type_bac": type_bac,
                "boursier": bool(boursier),
                "departement": code,
            }
            mesure = _chronometrer(client, corps, args.repetitions)
            mesure.update(departement=code, type_bac=type_bac, boursier=bool(boursier))
            resultats["departements_reels"].append(mesure)
            print(
                f"dép. {code:>4} ({type_bac}, boursier={boursier}) : {mesure['n_formations']} formations, "
                f"p50 {mesure['p50_ms']} ms  p95 {mesure['p95_ms']} ms",
                flush=True,
            )

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        cwd=RACINE,
        check=False,
    )
    resultats["contexte"] = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commit.stdout.strip(),
        "session": etat.session_courante,
        "slo_latence_p95_ms": settings.api.slo_latence_p95_ms,
        "plus_grosse_cellule_departementale": int(plus_gros.iloc[0]),
        "departement_de_la_plus_grosse_cellule": str(plus_gros.index[0]),
        "cellule_france_entiere": int(len(cellule)),
        "profil": PROFIL,
        "machine": f"{platform.system()} {platform.release()}, {platform.processor()}, Python {platform.python_version()}",
    }
    SORTIE.write_text(json.dumps(resultats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"-> {SORTIE.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
