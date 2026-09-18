"""Les trois connecteurs d'ingestion doivent être exécutables en module.

Non-régression d'un défaut réel : `parcoursup.py`, `sirene.py` et
`referentiels.py` n'exposaient aucun point d'entrée. `python -m
edumatch.ingestion.sirene`, la commande que lance la cible `data` du
Makefile, se terminait donc immédiatement avec un code de succès, sans rien
télécharger. La chaîne se déclarait passée alors qu'elle n'avait rien fait :
c'est exactement le contraire de l'automatisation attendue, et la
régénération complète depuis `data/raw/` ne pouvait pas fonctionner.

Ces tests vérifient les deux moitiés du contrat : la fonction `main` existe
et appelle bien le téléchargement, et le module exécuté comme script passe
par elle. Aucun accès réseau : `telecharger_tous` est remplacé.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass

import pytest

from edumatch.ingestion import parcoursup, referentiels, sirene

MODULES = [parcoursup, sirene, referentiels]
NOMS = [module.__name__ for module in MODULES]


@dataclass
class ResultatFactice:
    """Minimum attendu par `main` : seul `telecharge` est lu."""

    telecharge: bool


@pytest.mark.parametrize("module", MODULES, ids=NOMS)
def test_le_module_expose_un_point_entree(module) -> None:
    """Sans `main`, la cible `data` du Makefile ne télécharge rien."""
    assert callable(getattr(module, "main", None)), (
        f"{module.__name__} doit exposer main() : c'est ce que lance `python -m`."
    )


@pytest.mark.parametrize("module", MODULES, ids=NOMS)
def test_main_declenche_le_telechargement(module, monkeypatch, caplog) -> None:
    """`main` appelle `telecharger_tous` et rend compte de ce qui a été fait."""
    appels: list[bool] = []

    def _telecharger_tous(forcer: bool = False, **_: object) -> list[ResultatFactice]:
        appels.append(forcer)
        return [ResultatFactice(telecharge=True), ResultatFactice(telecharge=False)]

    monkeypatch.setattr(module, "telecharger_tous", _telecharger_tous)
    monkeypatch.setattr(module.sys, "argv", [module.__name__])

    with caplog.at_level("INFO"):
        code = module.main()

    assert code == 0
    assert appels == [False], "main() doit déclencher le téléchargement, une seule fois"
    assert "2 ressource(s)" in caplog.text, "main() doit résumer ce qui a été traité"


@pytest.mark.parametrize("module", MODULES, ids=NOMS)
def test_option_forcer_transmise(module, monkeypatch) -> None:
    """`--forcer` retélécharge même si le manifeste annonce le fichier déjà pris."""
    appels: list[bool] = []

    def _telecharger_tous(forcer: bool = False, **_: object) -> list[ResultatFactice]:
        appels.append(forcer)
        return []

    monkeypatch.setattr(module, "telecharger_tous", _telecharger_tous)
    monkeypatch.setattr(module.sys, "argv", [module.__name__, "--forcer"])

    assert module.main() == 0
    assert appels == [True]


@pytest.mark.parametrize("module", MODULES, ids=NOMS)
def test_le_module_est_executable_en_script(module) -> None:
    """`python -m <module>` doit réellement lancer le téléchargement.

    C'est la forme exacte qu'utilise la cible `data` du Makefile. Le test lit
    l'arbre syntaxique du module plutôt que de l'exécuter : exécuter pour de
    vrai impliquerait un accès réseau, et un remplacement de fonction ne
    survit pas au réimport que fait l'interpréteur dans ce mode.
    """
    arbre = ast.parse(inspect.getsource(module))
    gardes = [
        noeud
        for noeud in arbre.body
        if isinstance(noeud, ast.If)
        and ast.unparse(noeud.test).replace("'", '"') == '__name__ == "__main__"'
    ]
    assert gardes, f"{module.__name__} doit se terminer par un bloc d'exécution"
    appels = ast.unparse(gardes[0])
    assert "main()" in appels, "le bloc d'exécution doit appeler main()"
    assert "sys.exit" in appels, "le code de sortie de main() doit être propagé"
