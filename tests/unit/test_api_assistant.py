"""Test de contrat de `/assistant` : l'assistant documentaire répond en citant ses
sources, ou explique explicitement qu'il n'en a pas trouvé — jamais un plantage, jamais un
silence quand le service n'est pas disponible."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from edumatch.api.deps import get_assistant_rag
from edumatch.api.main import create_app
from edumatch.rag.assistant import Citation, ReponseAssistant


class _FauxAssistant:
    def __init__(self, reponse: ReponseAssistant) -> None:
        self._reponse = reponse
        self.dernieres_questions: list[str] = []

    def repondre(self, question: str) -> ReponseAssistant:
        self.dernieres_questions.append(question)
        return self._reponse


CITATION_EXEMPLE = Citation(
    identifiant="ideo:formations:0",
    source="ONISEP — IDÉO — référentiel des formations",
    licence="ODbL (odc-odbl)",
    url="https://www.onisep.fr/http/redirection/formation/slug/FOR.1",
    date_collecte="2026-08-29T04:10:05+00:00",
    extrait="BTS comptabilité et gestion — 2 ans",
)


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    faux = _FauxAssistant(
        ReponseAssistant(
            reponse="Voici ce que le référentiel ONISEP (IDÉO) indique :\n\n[1] BTS comptabilité et gestion — 2 ans",
            mode="extractif",
            citations=(CITATION_EXEMPLE,),
            avertissement=None,
        )
    )
    app.dependency_overrides[get_assistant_rag] = lambda: faux
    client = TestClient(app)
    client.faux_assistant = faux  # type: ignore[attr-defined]
    return client


def test_assistant_repond_avec_au_moins_une_citation(client: TestClient) -> None:
    reponse = client.post("/assistant", json={"question": "Quelle formation pour devenir comptable ?"})
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["mode"] == "extractif"
    assert len(corps["citations"]) == 1
    citation = corps["citations"][0]
    assert citation["url"] == CITATION_EXEMPLE.url
    assert citation["licence"] == CITATION_EXEMPLE.licence
    assert citation["date_collecte"] == CITATION_EXEMPLE.date_collecte


def test_assistant_transmet_la_question_au_service(client: TestClient) -> None:
    client.post("/assistant", json={"question": "Quelle formation pour devenir comptable ?"})
    assert client.faux_assistant.dernieres_questions == ["Quelle formation pour devenir comptable ?"]  # type: ignore[attr-defined]


def test_assistant_refuse_une_question_vide(client: TestClient) -> None:
    reponse = client.post("/assistant", json={"question": ""})
    assert reponse.status_code == 422


def test_assistant_refuse_un_champ_non_declare(client: TestClient) -> None:
    reponse = client.post(
        "/assistant", json={"question": "Quelle formation pour devenir comptable ?", "genre": "F"}
    )
    assert reponse.status_code == 422


def test_assistant_non_initialise_repond_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans référentiel IDÉO téléchargé (`data/external/referentiels/` absent), le service doit
    répondre 503 plutôt que de planter tout le processus — même politique que `/matching` et
    `/explain` (voir `api/deps.py`). `construire_assistant` est ici forcé en échec plutôt que de
    dépendre de l'état réel de `data/external/` sur le poste d'exécution, qui varie selon que
    la réconciliation NAF/ROME a déjà été jouée ou non."""
    from edumatch.api import deps

    def _echoue(settings: object) -> None:
        raise deps.ErreurCorpusRag("référentiel IDÉO introuvable (simulation de test)")

    monkeypatch.setattr(deps, "construire_assistant", _echoue)
    client = TestClient(create_app())
    reponse = client.post("/assistant", json={"question": "Quelle formation pour devenir comptable ?"})
    assert reponse.status_code == 503
    assert "référentiel IDÉO introuvable" in reponse.json()["detail"]
