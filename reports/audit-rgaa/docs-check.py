"""Audit de la documentation HTML : menu des écrans étroits, recherche, ancres, accessibilité.

Sert `docs/` en local, pilote Chrome par Playwright, et écrit le résultat dans
`reports/audit-rgaa/docs-resultats.json`. axe-core est chargé depuis le fichier local
`reports/audit-rgaa/axe.min.js`, sans appel réseau.

    python reports/audit-rgaa/docs-check.py
"""

from __future__ import annotations

import functools
import http.server
import json
import socketserver
import sys
import threading
import unicodedata
from pathlib import Path

from playwright.sync_api import sync_playwright

RACINE = Path(__file__).resolve().parents[2]
DOCS = RACINE / "docs"
AXE = Path(__file__).with_name("axe.min.js").read_text(encoding="utf-8")
SORTIE = Path(__file__).with_name("docs-resultats.json")
PAGES_MENU = ["index.html", "modele.html", "decisions.html"]
REQUETES = {"porte de promotion": "pipeline.html", "PSI": "modele.html", "purge": "service.html"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return " ".join("".join(c for c in s if not "̀" <= c <= "ͯ").lower().split())


def serveur() -> tuple[socketserver.TCPServer, int]:
    gestionnaire = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    gestionnaire.log_message = lambda *a, **k: None
    srv = socketserver.TCPServer(("127.0.0.1", 0), gestionnaire)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def verifier_menu(page, base: str) -> list[dict]:
    resultats = []
    page.set_viewport_size({"width": 375, "height": 800})
    for nom in PAGES_MENU:
        page.goto(f"{base}/{nom}")
        page.wait_for_load_state("domcontentloaded")
        r = {"page": nom}
        bouton, panneau = page.locator("#menu-btn"), page.locator("#sidebar")
        r["bouton_visible"] = bouton.is_visible()
        r["panneau_cache_au_depart"] = not panneau.is_visible()
        bouton.click()
        r["ouverture"] = panneau.is_visible() and bouton.get_attribute("aria-expanded") == "true"
        page.evaluate("document.querySelector('.topbar').click()")
        r["fermeture_hors_panneau"] = (
            not panneau.is_visible() and bouton.get_attribute("aria-expanded") == "false"
        )
        bouton.click()
        page.keyboard.press("Escape")
        r["fermeture_echap"] = (
            not panneau.is_visible() and bouton.get_attribute("aria-expanded") == "false"
        )
        r["focus_rendu_au_bouton"] = page.evaluate("document.activeElement.id") == "menu-btn"
        bouton.click()
        # Clic sur un lien du panneau, navigation empêchée pour observer l'état juste après.
        r["fermeture_clic_lien"] = page.evaluate(
            """() => { addEventListener('click', e => e.preventDefault(), {capture: true, once: true});
                       document.querySelector('#sidebar a').click();
                       return !document.body.classList.contains('nav-open')
                              && document.querySelector('#menu-btn').getAttribute('aria-expanded') === 'false'; }"""
        )
        r["pas_de_defilement_horizontal"] = page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )
        resultats.append(r)
    return resultats


def verifier_recherche(page, base: str) -> list[dict]:
    resultats = []
    for largeur in (1280, 375):
        page.set_viewport_size({"width": largeur, "height": 800})
        for requete, page_attendue in REQUETES.items():
            page.goto(f"{base}/index.html")
            champ = page.locator("#recherche-champ")
            champ.click()
            champ.fill(requete)
            page.wait_for_selector("#recherche-resultats [role=option]", timeout=10000)
            options = page.locator("#recherche-resultats [role=option]")
            r = {"largeur": largeur, "requete": requete, "resultats": options.count()}
            r["premier"] = options.first.locator(".recherche-titre").inner_text()
            r["page_du_premier"] = options.first.locator(".recherche-page").inner_text()
            r["terme_en_gras"] = options.first.locator(
                ".recherche-extrait strong"
            ).count() > 0 or norm(requete) in norm(r["premier"])
            r["label_accessible"] = page.evaluate(
                "document.querySelector('label[for=recherche-champ]') !== null"
            )
            page.keyboard.press("ArrowDown")
            r["actif_signale"] = (
                champ.get_attribute("aria-activedescendant") == "recherche-option-0"
            )
            with page.expect_navigation():
                page.keyboard.press("Enter")
            page.wait_for_load_state("load")
            page.wait_for_timeout(300)
            url = page.url
            ancre = url.split("#", 1)[1] if "#" in url else ""
            r["url"] = url.replace(base, "")
            info = page.evaluate(
                """(a) => { const el = document.getElementById(decodeURIComponent(a));
                    if (!el) return null;
                    let t = el.textContent, n = el.nextElementSibling;
                    while (n && !/^H[23]$/.test(n.tagName)) { t += ' ' + n.textContent; n = n.nextElementSibling; }
                    return {haut: Math.round(el.getBoundingClientRect().top), texte: t}; }""",
                ancre,
            )
            r["page_attendue"] = url.replace(base, "").lstrip("/").split("#")[0] == page_attendue
            r["ancre_existe"] = info is not None
            r["ancre_visible_en_haut"] = bool(info) and 0 <= info["haut"] <= 250
            r["section_contient_le_terme"] = bool(info) and all(
                m in norm(info["texte"]) for m in norm(requete).split()
            )
            resultats.append(r)
    # Absence de résultat, Échap, focus non piégé
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{base}/index.html")
    champ = page.locator("#recherche-champ")
    champ.click()
    champ.fill("xyzzyqwv")
    page.wait_for_selector(".recherche-vide:not([hidden])", timeout=10000)
    vide = {"requete": "xyzzyqwv", "message": page.locator(".recherche-vide").inner_text()}
    champ.fill("purge")
    page.wait_for_selector("#recherche-resultats [role=option]")
    page.keyboard.press("Escape")
    vide["echap_ferme"] = (
        page.locator(".recherche-panneau").is_hidden()
        and champ.get_attribute("aria-expanded") == "false"
    )
    page.keyboard.press("Tab")
    vide["tab_quitte_le_champ"] = page.evaluate("document.activeElement.id") != "recherche-champ"
    resultats.append(vide)
    return resultats


def verifier_ancres(page, base: str) -> dict:
    source = (DOCS / "assets" / "recherche-index.js").read_text(encoding="utf-8")
    index = json.loads(source[source.index("=") + 1 :].strip().rstrip(";"))
    manquantes, total = [], 0
    for nom in sorted({e["page"] for e in index}):
        page.goto(f"{base}/{nom}")
        page.wait_for_load_state("domcontentloaded")
        ids = set(page.evaluate("[...document.querySelectorAll('[id]')].map(e => e.id)"))
        for e in (x for x in index if x["page"] == nom):
            total += 1
            if e["ancre"] not in ids:
                manquantes.append(f"{nom}#{e['ancre']}")
    return {"ancres_de_l_index": total, "absentes_du_dom": manquantes}


def verifier_axe(page, base: str) -> list[dict]:
    resultats = []
    for largeur in (1280, 375):
        page.set_viewport_size({"width": largeur, "height": 800})
        for nom in PAGES_MENU:
            page.goto(f"{base}/{nom}")
            page.locator("#recherche-champ").fill("purge")
            page.wait_for_selector("#recherche-resultats [role=option]", timeout=10000)
            page.keyboard.press("ArrowDown")
            page.add_script_tag(content=AXE)
            violations = page.evaluate(
                """async () => (await axe.run(document, {runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}))
                     .violations.map(v => ({id: v.id, impact: v.impact, noeuds: v.nodes.length,
                                            cibles: v.nodes.slice(0, 3).map(n => n.target.join(' '))}))"""
            )
            resultats.append({"largeur": largeur, "page": nom, "violations": violations})
    return resultats


def main() -> int:
    srv, port = serveur()
    base = f"http://127.0.0.1:{port}"
    with sync_playwright() as p:
        navigateur = p.chromium.launch(channel="chrome", headless=True)
        page = navigateur.new_page()
        rapport = {
            "menu": verifier_menu(page, base),
            "recherche": verifier_recherche(page, base),
            "ancres": verifier_ancres(page, base),
            "axe": verifier_axe(page, base),
        }
        navigateur.close()
    srv.shutdown()
    SORTIE.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rapport, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
