"""Contrôles automatisés d'accessibilité de l'écran conseiller (E31, critère 4.18).

## Ce que ces tests prouvent, et ce qu'ils ne prouvent pas

Il n'y a pas de navigateur dans cet environnement d'exécution : ces tests ne
remplacent donc pas un audit RGAA complet, qui exige un rendu réel (lecteur
d'écran, zoom 200 %, navigation clavier de bout en bout, contraste mesuré au
pixel sur le rendu effectif des polices). Ce qu'ils vérifient, c'est ce qui
est **statiquement décidable depuis le code source** : la structure
sémantique du document, la présence d'étiquettes associées à chaque champ, le
contraste théorique des couleurs déclarées dans la feuille de style (calcul
WCAG exact, pas une estimation), et la syntaxe du JavaScript. La procédure
d'audit manuel qui referme ce que ces tests ne couvrent pas est décrite dans
`reports/audit-rgaa-procedure.md`.
"""

from __future__ import annotations

import json
import re
import subprocess
from itertools import pairwise
from pathlib import Path

import pytest

DOSSIER_STATIQUE = Path(__file__).resolve().parents[2] / "src" / "edumatch" / "api" / "static"
HTML = (DOSSIER_STATIQUE / "index.html").read_text(encoding="utf-8")
CSS = (DOSSIER_STATIQUE / "style.css").read_text(encoding="utf-8")
JS = (DOSSIER_STATIQUE / "app.js").read_text(encoding="utf-8")


# ─── Structure sémantique ───────────────────────────────────────────────────


def test_langue_du_document_est_declaree() -> None:
    assert '<html lang="fr">' in HTML


def test_un_seul_titre_de_niveau_un() -> None:
    assert len(re.findall(r"<h1[ >]", HTML)) == 1


def test_hierarchie_des_titres_ne_saute_aucun_niveau() -> None:
    """RGAA 9.1 : l'ordre des `h1`-`h6` doit être respecté, sans saut (un `h3` ne doit jamais
    suivre un `h1` sans `h2` intermédiaire)."""
    niveaux = [int(n) for n in re.findall(r"<h([1-6])[ >]", HTML)]
    for precedent, suivant in pairwise(niveaux):
        assert suivant <= precedent + 1, f"saut de {precedent} à {suivant} dans la hiérarchie des titres"


def test_landmarks_principaux_presents_une_seule_fois() -> None:
    for landmark in ("<header", "<main", "<nav", "<footer"):
        assert HTML.count(landmark) == 1, f"{landmark} doit apparaître exactement une fois"


def test_lien_evitement_cible_le_contenu_principal() -> None:
    assert 'href="#contenu-principal"' in HTML
    assert 'id="contenu-principal"' in HTML


def test_contenu_principal_est_focusable_par_programme() -> None:
    """RGAA 12.7 / WCAG 2.4.1 : un lien d'évitement doit déplacer le *focus clavier* sur sa
    cible, pas seulement faire défiler la page jusqu'à elle. `<main>` n'est pas nativement
    focusable (ni un lien, ni un bouton, ni un champ) : sans `tabindex`, l'ancre `href="#…"`
    ne fait que défiler — `document.activeElement` reste `<body>`, et le `Tab` suivant repart
    du tout début du document. `tabindex="-1"` rend l'élément focusable par programme sans
    l'ajouter à l'ordre de tabulation naturel (un `Tab` ne s'y arrête jamais directement) —
    même technique que `#explication`, déjà en place plus bas dans ce même document, voir
    `test_panneau_explication_est_focusable_au_clavier`.

    Non-régression du défaut constaté dans `reports/audit-rgaa-resultats.md`
    (non-conformité n°1, majeure) : reproduit en direct par
    `reports/audit-rgaa/clavier-zoom-check.mjs` avant correction
    (`lien_evitement_deplace_focus_dans_main: false`).
    """
    bloc = re.search(r'<main id="contenu-principal"[^>]*>', HTML).group(0)
    assert 'tabindex="-1"' in bloc


def test_pas_de_style_en_ligne_dans_le_document() -> None:
    assert 'style="' not in HTML


# ─── Formulaires : chaque champ a une étiquette ─────────────────────────────

CHAMPS_TEXTE_ET_NOMBRE = re.findall(r'<input[^>]*type="(?:text|number)"[^>]*id="([^"]+)"', HTML)


@pytest.mark.parametrize("identifiant", CHAMPS_TEXTE_ET_NOMBRE)
def test_chaque_champ_texte_ou_nombre_a_un_label_associe(identifiant: str) -> None:
    assert f'for="{identifiant}"' in HTML, f"aucun <label for=\"{identifiant}\"> trouvé"


def test_les_groupes_de_boutons_radio_ont_une_legende() -> None:
    fieldsets = re.findall(r"<fieldset[^>]*>.*?</fieldset>", HTML, flags=re.DOTALL)
    radios = [bloc for bloc in fieldsets if 'type="radio"' in bloc]
    assert radios, "au moins un groupe de boutons radio est attendu (type de bac, boursier)"
    for bloc in radios:
        assert "<legend>" in bloc


def test_aide_departement_est_reliee_au_champ_par_aria_describedby() -> None:
    assert 'aria-describedby="aide-departement"' in HTML
    assert 'id="aide-departement"' in HTML


# ─── Messages et zones dynamiques annoncées ─────────────────────────────────


def test_zone_de_messages_de_recherche_est_une_region_live() -> None:
    assert 'id="messages-recherche"' in HTML
    bloc = re.search(r'<div id="messages-recherche"[^>]*>', HTML).group(0)
    assert 'role="alert"' in bloc
    assert 'aria-live="assertive"' in bloc


def test_panneau_explication_est_focusable_au_clavier() -> None:
    """La cible d'un déplacement de focus programmatique doit être focusable — un `<section>`
    n'est pas focusable par défaut, d'où `tabindex="-1"` (voir `app.js::afficherExplication`)."""
    bloc = re.search(r'<section id="explication"[^>]*>', HTML).group(0)
    assert 'tabindex="-1"' in bloc


# ─── Pas d'information portée par la seule couleur ─────────────────────────


def test_app_js_ecrit_toujours_le_statut_en_texte_pas_seulement_en_classe_css() -> None:
    """`badge-disponible` / `badge-indisponible` ne sont que des classes CSS : chaque badge doit
    aussi porter le mot "Mesuré" ou "Indisponible" en toutes lettres (voir `style.css`, la note
    sur `.badge`)."""
    assert '"Mesuré" : "Indisponible"' in JS or "'Mesuré' : 'Indisponible'" in JS


# ─── Contrastes (calcul WCAG exact sur les couleurs déclarées) ──────────────


def _luminance_relative(hexadecimal: str) -> float:
    hexadecimal = hexadecimal.lstrip("#")
    composantes = [int(hexadecimal[i : i + 2], 16) / 255 for i in (0, 2, 4)]

    def linearise(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linearise(c) for c in composantes)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio_de_contraste(couleur_a: str, couleur_b: str) -> float:
    l1, l2 = sorted((_luminance_relative(couleur_a), _luminance_relative(couleur_b)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _variable_css(nom: str) -> str:
    match = re.search(rf"{re.escape(nom)}:\s*(#[0-9a-fA-F]{{6}})", CSS)
    assert match, f"variable CSS {nom} introuvable dans style.css"
    return match.group(1)


# Paires (texte, fond) : seuil WCAG 2.1 AA pour du texte normal, 4.5:1.
PAIRES_TEXTE = [
    ("--couleur-texte", "--couleur-fond"),
    ("--couleur-texte-attenue", "--couleur-fond"),
    ("--couleur-primaire-texte", "--couleur-primaire"),
    ("--couleur-danger-texte", "--couleur-danger"),
    ("--couleur-primaire", "--couleur-fond"),  # liens
    ("--couleur-erreur-texte", "--couleur-erreur-fond"),
    ("--couleur-succes-texte", "--couleur-succes-fond"),
    ("--couleur-avertissement-texte", "--couleur-avertissement-fond"),
]

# Paires (élément, fond adjacent) : seuil WCAG 2.1 AA pour les composants d'interface (contours
# de focus, bordures porteuses de sens), 3:1 (critère 1.4.11).
PAIRES_INTERFACE = [
    ("--couleur-bordure", "--couleur-fond"),
    ("--couleur-focus", "--couleur-fond"),
    ("--couleur-focus", "--couleur-primaire"),
]


@pytest.mark.parametrize("nom_texte,nom_fond", PAIRES_TEXTE)
def test_contraste_texte_respecte_le_seuil_aa(nom_texte: str, nom_fond: str) -> None:
    ratio = _ratio_de_contraste(_variable_css(nom_texte), _variable_css(nom_fond))
    assert ratio >= 4.5, f"{nom_texte} sur {nom_fond} : {ratio:.2f}:1, en dessous du seuil AA (4.5:1)"


@pytest.mark.parametrize("nom_a,nom_b", PAIRES_INTERFACE)
def test_contraste_composant_interface_respecte_le_seuil_aa(nom_a: str, nom_b: str) -> None:
    ratio = _ratio_de_contraste(_variable_css(nom_a), _variable_css(nom_b))
    assert ratio >= 3.0, f"{nom_a} sur {nom_b} : {ratio:.2f}:1, en dessous du seuil AA pour l'UI (3:1)"


def test_le_focus_reste_visible_aucun_outline_none_sans_remplacement() -> None:
    """Un `outline: none` sans remplacement rendrait la navigation clavier muette : ce test
    échoue si une règle annule le focus sans qu'une déclaration `:focus` porte un remplacement
    visible ailleurs dans la feuille (ici `outline: 3px solid ...`)."""
    suppressions = re.findall(r"([^{}]+)\{[^{}]*outline\s*:\s*none[^{}]*\}", CSS)
    assert not suppressions, f"outline supprimé sans remplacement pour : {suppressions}"
    assert re.search(r":focus\s*\{[^{}]*outline\s*:\s*3px solid", CSS)


# ─── JavaScript : syntaxe (le reste relève des tests manuels documentés) ────


def test_app_js_est_syntaxiquement_valide() -> None:
    """Politique de test que je me suis fixée : pour le JavaScript, vérification
    syntaxique et tests manuels documentés. `node --check` ne fait qu'analyser
    la syntaxe, il n'exécute rien."""
    resultat = subprocess.run(
        ["node", "--check", str(DOSSIER_STATIQUE / "app.js")],
        capture_output=True,
        text=True,
        check=False,
    )
    if resultat.returncode != 0 and "not found" in (resultat.stderr or "").lower():
        pytest.skip("node indisponible dans cet environnement : vérification manuelle requise avant déploiement")
    assert resultat.returncode == 0, resultat.stderr


def test_app_js_ne_construit_jamais_de_html_par_concatenation() -> None:
    """La protection contre le XSS ici n'est pas un échappement qu'on pourrait oublier, c'est
    l'absence totale d'`innerHTML` : tout le contenu dynamique passe par `textContent` ou par la
    construction de nœuds DOM (voir l'en-tête du module)."""
    assert ".innerHTML" not in JS
    assert ".write(" not in JS
    assert re.search(r"\beval\s*\(", JS) is None


def test_app_js_ne_journalise_rien_en_console() -> None:
    assert "console.log" not in JS


def test_pas_de_var_dans_app_js() -> None:
    assert re.search(r"\bvar\s+\w", JS) is None


# ─── Message d'erreur 422 lisible (non-régression, voir résultats d'audit) ──


def _executer_lire_detail_erreur(detail: object) -> str:
    """Exécute la fonction réelle `lireDetailErreur` de `app.js` dans un bac à sable Node,
    avec une fausse réponse HTTP dont `.json()` renvoie le corps donné — sans navigateur,
    ce qui est cohérent avec la politique de test de ce fichier pour le JavaScript (voir
    `test_app_js_est_syntaxiquement_valide` : vérification automatisée quand c'est possible,
    audit manuel documenté pour le reste)."""
    chemin_app_js = json.dumps(str(DOSSIER_STATIQUE / "app.js"))
    corps_reponse = json.dumps({"detail": detail}, ensure_ascii=False)
    script = (
        "const vm = require('vm');\n"
        "const fs = require('fs');\n"
        f"const code = fs.readFileSync({chemin_app_js}, 'utf8');\n"
        "const sandbox = { document: { addEventListener: () => {} }, console };\n"
        "vm.createContext(sandbox);\n"
        "vm.runInContext(code, sandbox);\n"
        f"const reponse = {{ status: 422, json: async () => ({corps_reponse}) }};\n"
        "sandbox.lireDetailErreur(reponse).then((msg) => process.stdout.write(msg));\n"
    )
    resultat = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, encoding="utf-8", check=False
    )
    if resultat.returncode != 0 and "not found" in (resultat.stderr or "").lower():
        pytest.skip("node indisponible dans cet environnement : vérification manuelle requise avant déploiement")
    assert resultat.returncode == 0, resultat.stderr
    return resultat.stdout


def test_erreur_422_tableau_pydantic_nomme_le_champ_fautif() -> None:
    """Non-régression du défaut n°2 (mineur) de `reports/audit-rgaa-resultats.md` :
    FastAPI/Pydantic v2 renvoie sur une 422 un **tableau** d'objets d'erreur
    (`type`, `loc`, `msg`), pas une chaîne. Avant correction, `lireDetailErreur` ne
    traitait que le cas chaîne et retombait sur le générique « Erreur 422. », reproduit
    par requête directe (voir le rapport) et par
    `reports/audit-rgaa/clavier-zoom-check.mjs` (`departement_mal_forme_message`)."""
    detail = [
        {
            "type": "string_pattern_mismatch",
            "loc": ["body", "departement"],
            "msg": "String should match pattern '^(2[AB]|[0-9]{2,3})$'",
        }
    ]
    message = _executer_lire_detail_erreur(detail)
    assert message != "Erreur 422."
    assert "épartement" in message  # « Département visé », insensible à la casse initiale


def test_erreur_422_ne_reprend_jamais_le_message_brut_de_pydantic() -> None:
    """Le message affiché doit rester compréhensible par un conseiller, pas un copier-coller
    du message de validation Pydantic (qui expose un motif d'expression régulière, illisible
    pour qui ne programme pas)."""
    detail = [
        {
            "type": "string_pattern_mismatch",
            "loc": ["body", "departement"],
            "msg": "String should match pattern '^(2[AB]|[0-9]{2,3})$'",
        }
    ]
    message = _executer_lire_detail_erreur(detail)
    assert "pattern" not in message.lower()
    assert "[0-9]" not in message


def test_erreur_422_multiple_champs_fautifs_sont_tous_signales() -> None:
    detail = [
        {"type": "missing", "loc": ["body", "type_bac"], "msg": "Field required"},
        {"type": "missing", "loc": ["body", "boursier"], "msg": "Field required"},
    ]
    message = _executer_lire_detail_erreur(detail)
    assert "baccalauréat" in message.lower()
    assert "boursier" in message.lower()


def test_erreur_422_n_expose_aucune_trace_technique() -> None:
    """Ce qui était déjà conforme avant correction (voir le rapport d'audit, point « Ce qui est
    déjà correct ») ne doit pas régresser avec la réécriture de `lireDetailErreur`."""
    detail = [{"type": "string_pattern_mismatch", "loc": ["body", "departement"], "msg": "String should match pattern"}]
    message = _executer_lire_detail_erreur(detail)
    assert not re.search(r"Traceback|File \"|site-packages|edumatch\.api|\.py\"", message)


def test_erreur_422_chaine_simple_reste_affichee_telle_quelle() -> None:
    """Non-régression du comportement existant : une 422 dont `detail` est déjà une chaîne
    (par exemple levée à la main ailleurs dans l'API) continue de s'afficher sans changement."""
    message = _executer_lire_detail_erreur("Département introuvable.")
    assert message == "Département introuvable."
