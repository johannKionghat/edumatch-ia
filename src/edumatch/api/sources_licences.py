"""Écran « Sources et licences » : la page d'attribution, générée depuis les manifestes.

La Licence Ouverte v2.0 impose de citer la paternité **et la date** de la ressource
réutilisée (article 2), et l'ODbL de l'ONISEP impose l'attribution du producteur. Une page
d'attribution dont les dates sont saisies à la main ne tient pas cette promesse : elle
devient fausse au premier retéléchargement, sans que rien ne le signale. C'est ce qui
s'est produit — la page annonçait une collecte du 28 août alors que les manifestes de
Sirene et des référentiels portaient le 17 septembre.

Ce module retire la saisie manuelle du chemin : la page est **générée** à partir des
trois manifestes d'ingestion, qui sont eux-mêmes écrits par les connecteurs au moment du
téléchargement. `tests/data/test_sources_licences_a_jour.py` échoue si la page versionnée
diverge de ce que produit ce module, de sorte qu'un retéléchargement sans régénération
casse la chaîne au lieu de passer inaperçu.

## Ce qui vient du manifeste, ce qui n'en vient pas

Les **dates** viennent toutes des manifestes : c'est la partie qui se périme. Le
producteur et la licence de Parcoursup et de Sirene sont, eux, des constantes de ce
module : leurs connecteurs ne les enregistrent pas encore, alors que celui des
référentiels le fait. Elles sont vérifiées dans le registre des sources et ne changent
qu'avec la source elle-même. Ce qui ferait changer d'avis : un connecteur qui écrirait
licence et producteur dans son manifeste, comme le fait déjà celui des référentiels —
alors ces constantes disparaîtraient.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from edumatch.config import Settings, get_settings

LOGGER = logging.getLogger(__name__)

DOSSIER_STATIQUE = Path(__file__).parent / "static"
NOM_PAGE = "sources-et-licences.html"

LICENCE_OUVERTE = "Licence Ouverte v2.0 (Etalab)"
LICENCE_ODBL = "ODbL v1.0 (odc-odbl) — partage à l'identique obligatoire"

# Producteur lisible pour chaque valeur du champ `source` des manifestes de référentiels.
PRODUCTEURS = {
    "ideo": "ONISEP",
    "rncp": "France Compétences",
    "france_travail": "France Travail",
}

# Libellé du jeu de données pour chaque préfixe de clé du manifeste des référentiels.
JEUX_REFERENTIELS = {
    "ideo": "IDÉO, 4 jeux (formations, métiers, structures du secondaire et du supérieur)",
    "rncp": "RNCP et Répertoire spécifique, export CSV",
    "rncp_rome": "RNCP, correspondance codes ROME",
    "france_travail_rome_naf": "Table de correspondance ROME / NAF",
}


@dataclass(frozen=True)
class SourceAffichee:
    """Une ligne du tableau d'attribution."""

    jeu: str
    producteur: str
    licence: str
    date: str


def _lire_manifeste(chemin: Path) -> dict[str, dict[str, Any]]:
    if not chemin.exists():
        return {}
    return json.loads(chemin.read_text(encoding="utf-8"))


def _jour(valeur: Any) -> str:
    """La date seule d'un horodatage ISO — l'heure de téléchargement n'attribue rien."""
    return str(valeur)[:10]


def _dates_lisibles(entrees: list[dict[str, Any]]) -> str:
    """Les dates de collecte distinctes, dans l'ordre : une, deux, ou un intervalle."""
    jours = sorted({_jour(e.get("date_telechargement")) for e in entrees if e.get("date_telechargement")})
    if not jours:
        return "date de collecte absente du manifeste"
    if len(jours) == 1:
        return jours[0]
    if len(jours) == 2:
        return f"{jours[0]} et {jours[1]}"
    return f"du {jours[0]} au {jours[-1]}"


def collecter(settings: Settings | None = None) -> list[SourceAffichee]:
    """Les lignes d'attribution, lues dans les trois manifestes d'ingestion."""
    settings = settings or get_settings()
    sources: list[SourceAffichee] = []

    parcoursup = _lire_manifeste(settings.raw_dir / "parcoursup" / "manifeste.json")
    if parcoursup:
        millesimes = sorted(str(e.get("millesime", "")) for e in parcoursup.values())
        sources.append(
            SourceAffichee(
                jeu=f"Parcoursup, {len(parcoursup)} millésimes ({millesimes[0]}-{millesimes[-1]})",
                producteur="MESR (ministère de l'Enseignement supérieur et de la Recherche)",
                licence=LICENCE_OUVERTE,
                date=_dates_lisibles(list(parcoursup.values())),
            )
        )

    sirene = _lire_manifeste(settings.raw_dir / "sirene" / "manifeste.json")
    if sirene:
        stocks = sorted({_jour(e.get("date_publication_stock")) for e in sirene.values() if e.get("date_publication_stock")})
        complement = f" (stock publié le {stocks[-1]})" if stocks else ""
        sources.append(
            SourceAffichee(
                jeu=f"Base Sirene, {len(sirene)} fichiers de stock",
                producteur="INSEE",
                licence=LICENCE_OUVERTE,
                date=_dates_lisibles(list(sirene.values())) + complement,
            )
        )

    referentiels = _lire_manifeste(settings.external_dir / "referentiels" / "manifeste.json")
    groupes: dict[str, list[dict[str, Any]]] = {}
    for cle, entree in referentiels.items():
        groupes.setdefault(cle.split(":", 1)[0], []).append(entree)
    for prefixe in sorted(groupes):
        entrees = groupes[prefixe]
        licence_brute = str(entrees[0].get("licence", ""))
        sources.append(
            SourceAffichee(
                jeu=JEUX_REFERENTIELS.get(prefixe, prefixe),
                producteur=PRODUCTEURS.get(str(entrees[0].get("source")), str(entrees[0].get("source"))),
                licence=LICENCE_ODBL if "odbl" in licence_brute.lower() else LICENCE_OUVERTE,
                date=_dates_lisibles(entrees),
            )
        )
    return sources


def _echapper(texte: str) -> str:
    """Les libellés viennent d'un fichier : ils ne doivent jamais pouvoir injecter du HTML."""
    return (
        texte.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def rendre(sources: list[SourceAffichee]) -> str:
    """La page complète, à partir des lignes d'attribution."""
    lignes = "\n".join(
        "            <tr>\n"
        f"              <td>{_echapper(s.jeu)}</td>\n"
        f"              <td>{_echapper(s.producteur)}</td>\n"
        f"              <td>{_echapper(s.licence)}</td>\n"
        f"              <td>{_echapper(s.date)}</td>\n"
        "            </tr>"
        for s in sources
    )
    producteurs = sorted({s.producteur.split(" (")[0] for s in sources})
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sources et licences — EduMatch-IA</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <a class="lien-evitement" href="#contenu-principal">Aller au contenu principal</a>

  <header class="en-tete">
    <h1>Sources et licences</h1>
    <p>Chaque donnée utilisée par EduMatch-IA vient d'une source publique identifiée, avec sa
      licence de réutilisation et la date à laquelle elle a été collectée. Cette page est
      générée depuis les manifestes d'ingestion : les dates sont celles des fichiers
      réellement téléchargés, jamais une saisie faite à la main.</p>
  </header>

  <nav class="navigation-page" aria-label="Sections de la page">
    <ul>
      <li><a href="/">Retour à l'écran conseiller</a></li>
      <li><a href="/notice-information">Notice d'information du candidat</a></li>
    </ul>
  </nav>

  <main id="contenu-principal" tabindex="-1">
    <section aria-labelledby="titre-sources">
      <h2 id="titre-sources">Les {len(producteurs)} producteurs du projet</h2>
      <div class="table-wrap">
        <table class="tableau-contributions">
          <caption>Producteur, jeu de données, licence et date de collecte du fichier réellement
            utilisé — pas une date de catalogue.</caption>
          <thead>
            <tr>
              <th scope="col">Jeu de données</th>
              <th scope="col">Producteur</th>
              <th scope="col">Licence</th>
              <th scope="col">Date de collecte</th>
            </tr>
          </thead>
          <tbody>
{lignes}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="titre-licences">
      <h2 id="titre-licences">Ce que chaque licence impose</h2>
      <h3>Licence Ouverte v2.0 (Etalab)</h3>
      <p>Réutilisation libre, y compris commerciale, à condition de mentionner la source (auteur,
        date de dernière mise à jour). Elle couvre les données du MESR, de l'INSEE, de France
        Compétences et de France Travail.</p>
      <h3>ODbL v1.0 (Open Database License, <code>odc-odbl</code>)</h3>
      <p>Licence de l'ONISEP pour les jeux IDÉO. Elle impose le partage à l'identique de toute
        base de données dérivée qui les intègre et leur usage public : toute table dérivée
        publiée sous une interface accessible au public, comme celle-ci, doit rester sous ODbL et
        attribuer le producteur.</p>
    </section>
  </main>

  <footer class="pied-de-page">
    <p>EduMatch-IA — page d'attribution des sources, distincte de la notice d'information du
      candidat (<a href="/notice-information">consulter la notice</a>).</p>
  </footer>
</body>
</html>
"""


def generer(settings: Settings | None = None, destination: Path | None = None) -> Path:
    """Écrit la page. Écriture atomique : jamais de page tronquée servie par l'API."""
    settings = settings or get_settings()
    destination = destination or DOSSIER_STATIQUE / NOM_PAGE
    contenu = rendre(collecter(settings))
    temporaire = destination.with_suffix(destination.suffix + ".part")
    temporaire.write_text(contenu, encoding="utf-8", newline="\n")
    os.replace(temporaire, destination)
    return destination


def main() -> int:
    """Point d'entrée : régénère la page d'attribution depuis les manifestes."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    sources = collecter(settings)
    if not sources:
        LOGGER.error("Aucun manifeste d'ingestion lisible : page non régénérée.")
        return 1
    chemin = generer(settings)
    LOGGER.info("Page d'attribution régénérée depuis les manifestes (%d sources) : %s", len(sources), chemin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
