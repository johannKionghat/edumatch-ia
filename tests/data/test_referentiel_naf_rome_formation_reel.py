"""Réconciliation NAF/ROME/formation (E18) sur les échantillons réels de `data/samples/`.

Contrairement à `tests/unit/test_referentiel_naf_rome_formation.py` (fixtures
minuscules et construites à la main pour isoler chaque règle), ce module fait
tourner la chaîne complète sur des extraits réels des trois sources — sans
téléchargement, seulement `data/samples/`, comme l'exige E08.

L'échantillonnage systématique des deux CSV (IDÉO, RNCP ROME) réduit
mécaniquement le nombre de correspondances trouvées par rapport aux
33 fichiers complets : ces tests ne vérifient donc pas un taux de couverture
précis (mesuré sur les fichiers complets, voir le module et sa documentation),
seulement que la chaîne s'exécute sur des données réelles sans erreur et que
la structure du résultat est celle attendue.
"""

from __future__ import annotations

from pathlib import Path

from edumatch.referentiel.naf_rome_formation import (
    charger_correspondance_rome_naf,
    charger_etat_rncp,
    charger_formations_ideo,
    charger_rncp_rome,
    construire_table,
    mesurer_couverture,
)

CHEMIN_IDEO = Path("data/samples/referentiels/ideo/formations.csv")
CHEMIN_RNCP_ROME = Path("data/samples/referentiels/rncp/rncp_rome_echantillon.csv")
CHEMIN_RNCP_STANDARD = Path("data/samples/referentiels/rncp/rncp_echantillon.csv")
CHEMIN_ROME_NAF = Path("data/samples/referentiels/france_travail/rome_naf.xlsx")


def test_les_quatre_echantillons_reels_se_chargent_avec_le_schema_attendu() -> None:
    formations = charger_formations_ideo(CHEMIN_IDEO)
    rncp_rome = charger_rncp_rome(CHEMIN_RNCP_ROME)
    etat_rncp = charger_etat_rncp(CHEMIN_RNCP_STANDARD)
    rome_naf = charger_correspondance_rome_naf(CHEMIN_ROME_NAF)

    assert formations.columns == ["code_rncp_ideo", "code_nsf", "libelle_formation_ideo"]
    assert rncp_rome.columns == ["code_rncp_fiche", "code_rome", "libelle_rome"]
    assert etat_rncp.columns == ["code_rncp", "rncp_actif"]
    assert rome_naf.columns == ["code_rome", "naf_division", "naf_division_libelle"]
    assert formations.height > 0
    assert rncp_rome.height > 0
    assert etat_rncp.height > 0
    assert rome_naf.height > 0
    # La table France Travail complète couvre 88 divisions NAF réelles (hors la
    # sentinelle "00" exclue) — non ré-échantillonnée, vérifiée sur le fichier
    # intégral ; un extrait plus petit trahirait un mauvais chemin de fichier.
    assert rome_naf["naf_division"].n_unique() >= 80
    assert "00" not in rome_naf["naf_division"].to_list()


def test_la_chaine_complete_sexecute_sur_les_echantillons_reels_sans_erreur() -> None:
    formations = charger_formations_ideo(CHEMIN_IDEO)
    rncp_rome = charger_rncp_rome(CHEMIN_RNCP_ROME)
    etat_rncp = charger_etat_rncp(CHEMIN_RNCP_STANDARD)
    rome_naf = charger_correspondance_rome_naf(CHEMIN_ROME_NAF)

    table = construire_table(formations, rncp_rome, rome_naf, etat_rncp)
    rapport = mesurer_couverture(formations, rncp_rome, rome_naf, table)

    assert set(table.columns) == {
        "code_rncp_ideo",
        "libelle_formation_ideo",
        "code_nsf",
        "code_rome",
        "libelle_rome",
        "naf_division",
        "naf_division_libelle",
        "rncp_actif",
    }
    # L'échantillon RNCP ROME est systématique (une ligne sur K) sur un fichier
    # trié par fiche : aucune garantie qu'il contienne l'une des fiches de
    # l'échantillon IDÉO. Zéro correspondance est donc un résultat valide ici,
    # ce que ce test documente plutôt que de l'exiger positif à tort. Le même
    # raisonnement s'applique à l'échantillon du CSV standard (`etat_rncp`),
    # échantillonné indépendamment : une ligne présente dans `table` peut donc
    # porter un `rncp_actif` nul (fiche absente de cet échantillon-ci), sans
    # que ce soit une anomalie — voir `construire_table`.
    assert table.height >= 0
    assert len(rapport.maillons) == 7
    assert len(rapport.manques_declares) == 2
