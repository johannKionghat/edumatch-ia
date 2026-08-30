"""Tests unitaires de `models/jeux.py` : la préparation des jeux, partagée par E22 et E23.

`preparer_matrice` et `evaluer_sur_perimetre` sont déjà exercées indirectement
via `tests/unit/test_models_train.py` (qui les importe depuis
`edumatch.models.train`, qui les réexporte) : ce fichier couvre ce que ces
tests-là ne visent pas — `extraire_jeu` et `chemin_table_variables`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from edumatch.config import get_settings
from edumatch.models.jeux import ErreurJeuxDonnees, chemin_table_variables, extraire_jeu, scores_par_session


def test_extraire_jeu_leve_si_aucune_cellule_pour_les_sessions_demandees() -> None:
    table = pd.DataFrame(
        {
            "session": [2024, 2024],
            "taux": [0.5, 0.2],
            "effectif": [10, 20],
            "fili": ["LICENCE", "BTS"],
        }
    )
    with pytest.raises(ErreurJeuxDonnees, match="2025"):
        extraire_jeu(table, [2025], ["fili"])


def test_extraire_jeu_ne_retient_que_les_sessions_demandees() -> None:
    table = pd.DataFrame(
        {
            "session": [2024, 2025],
            "taux": [0.5, 0.9],
            "effectif": [10, 10],
            "fili": ["LICENCE", "BTS"],
        }
    )
    jeu = extraire_jeu(table, [2024], ["fili"])
    assert len(jeu.y) == 1
    assert jeu.y.iloc[0] == pytest.approx(0.5)


def test_scores_par_session_eclate_un_jeu_multi_sessions() -> None:
    table = pd.DataFrame(
        {
            "session": [2024, 2025],
            "taux": [0.5, 0.9],
            "effectif": [10, 10],
            "fili": ["LICENCE", "BTS"],
        }
    )
    jeu = extraire_jeu(table, [2024, 2025], ["fili"])
    scores = scores_par_session(jeu, jeu.y.to_numpy())

    assert {score.perimetre for score in scores} == {"2024", "2025"}
    assert all(score.mae_ponderee == pytest.approx(0.0) for score in scores)


def test_chemin_table_variables_pointe_sous_processed_dir() -> None:
    settings = get_settings()
    chemin = chemin_table_variables(settings)
    assert isinstance(chemin, Path)
    assert chemin.is_relative_to(settings.processed_dir)
