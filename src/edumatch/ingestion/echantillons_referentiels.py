"""Échantillons versionnés des référentiels — IDÉO, RNCP (standard et ROME), France Travail.

Extrait de `echantillons.py` (E08, puis E18) : ce dernier dépassait la limite
de 500 lignes du projet une fois les deux sources d'E18 (RNCP ROME, France
Travail) ajoutées. Le découpage suit la même frontière que
`_referentiels_communs.py` / `_referentiels_rncp.py` côté ingestion : un
module pour Parcoursup et Sirene (volumétrie, échantillonnage Parquet en
flux), un module pour les référentiels (fichiers déjà petits, lecture CSV ou
copie intégrale). Les primitives génériques (`EchantillonResultat`,
l'échantillonnage systématique, la lecture/écriture CSV, l'empreinte) restent
dans `echantillons.py`, importées ici plutôt que dupliquées.
"""

from __future__ import annotations

import logging
from pathlib import Path

from edumatch.config import Settings
from edumatch.ingestion.echantillons import (
    EchantillonResultat,
    _ecrire_csv,
    _empreinte,
    _indices_systematiques,
    _lire_csv,
    _manifeste_source,
)

LOGGER = logging.getLogger(__name__)

# E18 : le dossier `external/referentiels/rncp/` porte deux familles de
# fichiers depuis l'ajout du membre ROME de l'archive quotidienne (voir
# `ingestion._referentiels_rncp`). Un motif `rncp_*.csv` trop large aurait
# silencieusement pris le fichier ROME pour « le dernier export standard » :
# voir `generer_echantillon_rncp`.
MOTIF_EXPORT_RNCP_STANDARD = "rncp_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].csv"
MOTIF_EXPORT_RNCP_ROME = "rncp_rome_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].csv"


def _provenance_ideo(settings: Settings, nom_jeu: str) -> dict[str, str]:
    manifeste = _manifeste_source(settings.external_dir / "referentiels" / "manifeste.json")
    entree = manifeste.get(f"ideo:{nom_jeu}")
    if entree is None:
        raise KeyError(f"Aucune entrée pour ideo:{nom_jeu} dans le manifeste des référentiels.")
    return {
        "url": entree["url"],
        "date_source": entree["date_telechargement"],
        "empreinte_sha256_source": entree["empreinte_sha256"],
    }


def generer_echantillons_ideo(settings: Settings) -> list[EchantillonResultat]:
    """Un échantillon par jeu IDÉO — ODbL : attribution et partage à l'identique documentés dans le README."""
    cfg = settings.donnees.referentiels.ideo
    cible = settings.donnees.echantillons_test.lignes_par_jeu_ideo
    resultats: list[EchantillonResultat] = []
    for nom_jeu, jeu_cfg in cfg.jeux.items():
        source = settings.external_dir / "referentiels" / "ideo" / f"{nom_jeu}.csv"
        if not source.exists():
            LOGGER.warning("IDÉO %s introuvable, jeu ignoré : %s", nom_jeu, source)
            continue
        # utf-8-sig plutôt que l'utf-8 déclaré en configuration : robuste à un
        # BOM éventuel en tête de fichier (présent sur ces exports), sans le
        # recopier dans l'échantillon écrit.
        entete, lignes = _lire_csv(source, "utf-8-sig", jeu_cfg.delimiteur)
        indices = _indices_systematiques(len(lignes), cible)
        lignes_retenues = [lignes[i] for i in indices]
        sortie = settings.samples_dir / "referentiels" / "ideo" / f"{nom_jeu}.csv"
        _ecrire_csv(sortie, entete, lignes_retenues, jeu_cfg.delimiteur)
        resultats.append(
            EchantillonResultat(
                source=f"ideo_{nom_jeu}",
                chemin_source=source,
                chemin_sortie=sortie,
                lignes_source=len(lignes),
                lignes_echantillon=len(lignes_retenues),
                colonnes_retenues=entete,
                colonnes_exclues=[],
                licence=jeu_cfg.licence,
                empreinte_sha256=_empreinte(sortie),
                **_provenance_ideo(settings, nom_jeu),
            )
        )
    return resultats


def _provenance_rncp(settings: Settings, chemin_source: Path) -> dict[str, str]:
    manifeste = _manifeste_source(settings.external_dir / "referentiels" / "manifeste.json")
    date_export = chemin_source.stem.removeprefix("rncp_")
    cle = f"rncp:{date_export}"
    entree = manifeste.get(cle)
    if entree is None:
        raise KeyError(f"Aucune entrée pour {cle} dans le manifeste des référentiels.")
    return {
        "url": entree["url"],
        "date_source": entree["date_publication"],
        "empreinte_sha256_source": entree["empreinte_sha256"],
    }


def generer_echantillon_rncp(settings: Settings) -> list[EchantillonResultat]:
    """Un échantillon du dernier export RNCP standard téléchargé — Licence Ouverte, pas de contrainte ODbL."""
    cfg = settings.donnees.referentiels.rncp
    dossier_rncp = settings.external_dir / "referentiels" / "rncp"
    exports = sorted(dossier_rncp.glob(MOTIF_EXPORT_RNCP_STANDARD)) if dossier_rncp.exists() else []
    if not exports:
        LOGGER.warning("Aucun export RNCP trouvé dans %s, source ignorée.", dossier_rncp)
        return []
    source = exports[-1]  # le plus récent, tri lexicographique = tri chronologique (AAAA-MM-JJ)
    cible = settings.donnees.echantillons_test.lignes_rncp
    entete, lignes = _lire_csv(source, cfg.encodage, cfg.delimiteur)
    indices = _indices_systematiques(len(lignes), cible)
    lignes_retenues = [lignes[i] for i in indices]
    sortie = settings.samples_dir / "referentiels" / "rncp" / "rncp_echantillon.csv"
    _ecrire_csv(sortie, entete, lignes_retenues, cfg.delimiteur)
    return [
        EchantillonResultat(
            source="rncp",
            chemin_source=source,
            chemin_sortie=sortie,
            lignes_source=len(lignes),
            lignes_echantillon=len(lignes_retenues),
            colonnes_retenues=entete,
            colonnes_exclues=[],
            licence=cfg.licence,
            empreinte_sha256=_empreinte(sortie),
            **_provenance_rncp(settings, source),
        )
    ]


def _provenance_rncp_rome(settings: Settings, chemin_source: Path) -> dict[str, str]:
    manifeste = _manifeste_source(settings.external_dir / "referentiels" / "manifeste.json")
    date_export = chemin_source.stem.removeprefix("rncp_rome_")
    cle = f"rncp_rome:{date_export}"
    entree = manifeste.get(cle)
    if entree is None:
        raise KeyError(f"Aucune entrée pour {cle} dans le manifeste des référentiels.")
    return {
        "url": entree["url"],
        "date_source": entree["date_publication"],
        "empreinte_sha256_source": entree["empreinte_sha256"],
    }


def generer_echantillon_rncp_rome(settings: Settings) -> list[EchantillonResultat]:
    """Un échantillon du fichier de correspondance fiche RNCP -> ROME (E18), même méthode que RNCP standard."""
    cfg = settings.donnees.referentiels.rncp
    dossier_rncp = settings.external_dir / "referentiels" / "rncp"
    exports = sorted(dossier_rncp.glob(MOTIF_EXPORT_RNCP_ROME)) if dossier_rncp.exists() else []
    if not exports:
        LOGGER.warning("Aucun export RNCP ROME trouvé dans %s, source ignorée.", dossier_rncp)
        return []
    source = exports[-1]
    # Réutilise le même volume cible que le CSV standard (`lignes_rncp`) : les
    # deux membres viennent de la même archive quotidienne, il n'y a pas de
    # raison de leur donner des tailles d'échantillon distinctes.
    cible = settings.donnees.echantillons_test.lignes_rncp
    entete, lignes = _lire_csv(source, cfg.encodage, cfg.delimiteur)
    indices = _indices_systematiques(len(lignes), cible)
    lignes_retenues = [lignes[i] for i in indices]
    sortie = settings.samples_dir / "referentiels" / "rncp" / "rncp_rome_echantillon.csv"
    _ecrire_csv(sortie, entete, lignes_retenues, cfg.delimiteur)
    return [
        EchantillonResultat(
            source="rncp_rome",
            chemin_source=source,
            chemin_sortie=sortie,
            lignes_source=len(lignes),
            lignes_echantillon=len(lignes_retenues),
            colonnes_retenues=entete,
            colonnes_exclues=[],
            licence=cfg.licence,
            empreinte_sha256=_empreinte(sortie),
            **_provenance_rncp_rome(settings, source),
        )
    ]


def _provenance_france_travail(settings: Settings) -> dict[str, str]:
    manifeste = _manifeste_source(settings.external_dir / "referentiels" / "manifeste.json")
    entree = manifeste.get("france_travail_rome_naf:rome_naf")
    if entree is None:
        raise KeyError("Aucune entrée pour france_travail_rome_naf:rome_naf dans le manifeste des référentiels.")
    return {
        "url": entree["url"],
        "date_source": entree["date_telechargement"],
        "empreinte_sha256_source": entree["empreinte_sha256"],
    }


def generer_echantillon_france_travail(settings: Settings) -> list[EchantillonResultat]:
    """Copie intégrale de la table ROME/NAF (E18) : pas d'échantillonnage systématique ici.

    À la différence des CSV texte échantillonnés ligne à ligne ailleurs dans
    ce module, ce fichier est un classeur Excel dont la structure est
    hiérarchique (une ligne « division » porte les codes ROME qui la suivent,
    voir `naf_rome_formation.charger_correspondance_rome_naf`) : sous-
    échantillonner ligne à ligne casserait cette hiérarchie sans gain réel,
    le fichier complet ne pesant que 112 Ko au 30/08/2026 — bien en deçà de
    ce qui justifierait un sous-échantillonnage (voir le seuil documenté
    pour Sirene, de plusieurs ordres de grandeur supérieur).
    """
    source = settings.external_dir / "referentiels" / "france_travail" / "rome_naf.xlsx"
    if not source.exists():
        LOGGER.warning("Table France Travail ROME/NAF introuvable (%s), source ignorée.", source)
        return []
    sortie = settings.samples_dir / "referentiels" / "france_travail" / "rome_naf.xlsx"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_bytes(source.read_bytes())
    return [
        EchantillonResultat(
            source="france_travail_rome_naf",
            chemin_source=source,
            chemin_sortie=sortie,
            lignes_source=-1,  # non applicable : fichier binaire copié intégralement
            lignes_echantillon=-1,
            colonnes_retenues=[],
            colonnes_exclues=[],
            licence=settings.donnees.referentiels.france_travail.licence,
            empreinte_sha256=_empreinte(sortie),
            **_provenance_france_travail(settings),
        )
    ]
