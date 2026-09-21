"""Génère l'index de recherche de la documentation : `docs/assets/recherche-index.js`.

Une entrée par section (titre `h2` ou `h3` du corps de page) : la page, le titre, l'ancre,
un extrait court pour l'affichage, et le texte complet de la section pour la recherche.
L'index est statique : aucun serveur, aucune dépendance, la recherche se fait dans le
navigateur (`docs/assets/recherche.js`).

À relancer après chaque modification de `docs/*.html` : `make docs-index`. Le test
`tests/unit/test_docs_index_recherche.py` échoue si l'index versionné ne correspond plus
aux pages, de sorte qu'une page modifiée sans régénération se voit.

## L'ancre, calculée comme le navigateur la calcule

Sur 389 titres, 95 n'ont pas d'attribut `id` dans le HTML : `docs/assets/site.js` le leur
donne au chargement (`donnerAncres()`). Ce script reproduit exactement la même règle, sans
quoi un résultat de recherche pointerait vers une ancre qui n'existe pas : le texte du titre
en minuscules, sans diacritiques, tout ce qui n'est pas `a-z0-9` devenu un tiret ; pour un
`h3`, l'ancre de son `h2` parent en préfixe ; en cas de collision, un suffixe numéroté. Le
préfixe corrige un défaut réel : les vingt sous-sections « Contexte » des ADR partageaient
toutes `#contexte`, et un lien vers l'une menait toujours à la première.

Bibliothèque standard seulement : le script tourne partout où tourne Python.
"""

from __future__ import annotations

import html
import json
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DOCS = RACINE / "docs"
DESTINATION = DOSSIER_DOCS / "assets" / "recherche-index.js"
LONGUEUR_EXTRAIT = 160
BALISES_IGNOREES = {"script", "style", "pre", "nav", "aside"}
# Le nom de chaque page, tel que l'affiche la navigation latérale : `NAV` dans site.js fait foi.
NOMS_DE_PAGE = dict(
    re.findall(
        r'\["([a-z0-9-]+\.html)", "([^"]+)"\]',
        (DOSSIER_DOCS / "assets" / "site.js").read_text(encoding="utf-8"),
    )
)


def slug(texte: str) -> str:
    """Même règle que `slug()` dans `docs/assets/site.js`."""
    decompose = unicodedata.normalize("NFD", texte.lower())
    sans_accents = "".join(c for c in decompose if not ("̀" <= c <= "ͯ"))
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", sans_accents))


def espaces(texte: str) -> str:
    return re.sub(r"\s+", " ", texte).strip()


class _Lecteur(HTMLParser):
    """Découpe le corps de page (`<article class="content">`) en sections h2/h3."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.dans_article = False
        self.profondeur_ignoree = 0
        self.titre_courant: dict | None = None
        self.sections: list[dict] = []
        self.titre_page = ""
        self._dans_titre_page = False

    def handle_starttag(self, balise: str, attributs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attributs)
        if balise == "title":
            self._dans_titre_page = True
        if balise == "article" and "content" in (attrs.get("class") or ""):
            self.dans_article = True
            return
        if not self.dans_article:
            return
        if balise in BALISES_IGNOREES:
            self.profondeur_ignoree += 1
            return
        if balise in ("h2", "h3") and self.profondeur_ignoree == 0:
            self.titre_courant = {"niveau": balise, "id": attrs.get("id"), "titre": "", "texte": ""}
            self.sections.append(self.titre_courant)
            self._dans_titre = True
        if balise in ("p", "li", "td", "th", "br", "div", "tr"):
            self._ajouter(" ")

    def handle_endtag(self, balise: str) -> None:
        if balise == "title":
            self._dans_titre_page = False
        if balise == "article":
            self.dans_article = False
        if not self.dans_article:
            return
        if balise in BALISES_IGNOREES and self.profondeur_ignoree:
            self.profondeur_ignoree -= 1
        if balise in ("h2", "h3"):
            self._dans_titre = False

    _dans_titre = False

    def _ajouter(self, texte: str) -> None:
        if self.titre_courant is None:
            return
        cle = "titre" if self._dans_titre else "texte"
        self.titre_courant[cle] += texte

    def handle_data(self, donnees: str) -> None:
        if self._dans_titre_page:
            self.titre_page += donnees
        if self.dans_article and self.profondeur_ignoree == 0:
            self._ajouter(donnees)


def attribuer_ancres(sections: list[dict], ids_existants: set[str]) -> None:
    """Même règle que `donnerAncres()` dans `docs/assets/site.js`.

    Un titre sans `id` reçoit le slug de son texte ; un `h3` y ajoute en préfixe l'ancre de
    son `h2` parent ; une collision reçoit un suffixe `-2`, `-3`… Sans le préfixe, les vingt
    sous-sections « Contexte » des ADR partageaient toutes `#contexte`.
    """
    utilises = set(ids_existants)
    dernier_h2 = ""
    for section in sections:
        if not section["id"]:
            base = slug(espaces(section["titre"]))
            if section["niveau"] == "h3" and dernier_h2:
                base = f"{dernier_h2}-{base}"
            candidat, n = base, 2
            while candidat in utilises:
                candidat, n = f"{base}-{n}", n + 1
            section["id"] = candidat
            utilises.add(candidat)
        if section["niveau"] == "h2":
            dernier_h2 = section["id"]


def indexer_page(chemin: Path) -> list[dict]:
    source = chemin.read_text(encoding="utf-8")
    lecteur = _Lecteur()
    lecteur.feed(source)
    attribuer_ancres(lecteur.sections, set(re.findall(r'\bid="([^"]+)"', source)))
    nom_page = NOMS_DE_PAGE.get(chemin.name) or espaces(html.unescape(lecteur.titre_page))
    entrees = []
    for section in lecteur.sections:
        titre = espaces(section["titre"])
        if not titre:
            continue
        texte = espaces(section["texte"])
        extrait = (
            texte
            if len(texte) <= LONGUEUR_EXTRAIT
            else texte[:LONGUEUR_EXTRAIT].rsplit(" ", 1)[0] + "…"
        )
        entrees.append(
            {
                "page": chemin.name,
                "nomPage": nom_page,
                "titre": titre,
                "ancre": section["id"],
                "extrait": extrait,
                "texte": texte,
            }
        )
    return entrees


def construire_index(dossier: Path = DOSSIER_DOCS) -> list[dict]:
    index: list[dict] = []
    for chemin in sorted(dossier.glob("*.html")):
        index.extend(indexer_page(chemin))
    return index


def rendre(index: list[dict]) -> str:
    """Le fichier JavaScript : une seule variable globale, lue par `recherche.js`."""
    donnees = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    return (
        "// Index de recherche de la documentation, généré par scripts/generer_index_recherche.py.\n"
        "// Ne pas modifier à la main : relancer `make docs-index` après chaque changement de docs/.\n"
        f"window.EDUMATCH_INDEX_RECHERCHE = {donnees};\n"
    )


def main() -> int:
    index = construire_index()
    DESTINATION.write_text(rendre(index), encoding="utf-8", newline="\n")
    pages = len({e["page"] for e in index})
    print(
        f"Index écrit : {len(index)} sections sur {pages} pages -> {DESTINATION.relative_to(RACINE)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
