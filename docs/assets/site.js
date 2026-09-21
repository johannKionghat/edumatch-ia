// Documentation EduMatch-IA — navigation, sommaire, thème et schémas.
(function () {
  "use strict";

  var NAV = [
    { groupe: "Démarrer", pages: [
      ["index.html", "Vue d'ensemble"],
    ] },
    { groupe: "Construire", pages: [
      ["donnees.html", "Données et label"],
      ["architecture.html", "Architecture"],
      ["pipeline.html", "Pipeline de données"],
      ["modele.html", "Modèle"],
      ["service.html", "Service et accessibilité"],
    ] },
    { groupe: "Gouverner", pages: [
      ["gouvernance.html", "Stratégie et plan"],
      ["registres.html", "Registres"],
      ["risques-aipd.html", "Risques et AIPD"],
      ["ai-act.html", "AI Act"],
      ["model-card.html", "Model Card"],
    ] },
    { groupe: "Décider", pages: [
      ["decisions.html", "Décisions d'architecture"],
    ] },
  ];

  var courante = (location.pathname.split("/").pop() || "index.html");
  var toutes = [];
  NAV.forEach(function (g) { g.pages.forEach(function (p) { toutes.push(p); }); });

  function construireNavigation() {
    var cible = document.getElementById("sidebar");
    if (!cible) return;
    var html = "";
    NAV.forEach(function (g) {
      html += "<h4>" + g.groupe + "</h4><ul>";
      g.pages.forEach(function (p) {
        var actif = p[0] === courante ? ' aria-current="page"' : "";
        html += '<li><a href="' + p[0] + '"' + actif + ">" + p[1] + "</a></li>";
      });
      html += "</ul>";
    });
    cible.innerHTML = html;
  }

  function construirePager() {
    var cible = document.getElementById("pager");
    if (!cible) return;
    var i = toutes.findIndex(function (p) { return p[0] === courante; });
    var html = "";
    if (i > 0) html += '<a class="prev" href="' + toutes[i - 1][0] + '"><small>Précédent</small>' + toutes[i - 1][1] + "</a>";
    if (i >= 0 && i < toutes.length - 1) html += '<a class="next" href="' + toutes[i + 1][0] + '"><small>Suivant</small>' + toutes[i + 1][1] + "</a>";
    cible.innerHTML = html;
  }

  function slug(texte) {
    return texte.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  }

  // Donne une ancre unique à chaque titre qui n'en a pas. Un h3 prend l'ancre de son h2 parent
  // en préfixe : sans cela, les vingt ADR de decisions.html partageaient tous « #contexte »,
  // et un lien vers le contexte de l'ADR 0019 menait à celui de l'ADR 0001. Même règle dans
  // scripts/generer_index_recherche.py, qui calcule les ancres de l'index de recherche.
  function donnerAncres(titres) {
    var dernierH2 = "";
    titres.forEach(function (t) {
      if (!t.id) {
        var base = slug(t.textContent);
        if (t.tagName === "H3" && dernierH2) base = dernierH2 + "-" + base;
        var candidat = base;
        var n = 2;
        while (document.getElementById(candidat)) candidat = base + "-" + n++;
        t.id = candidat;
      }
      if (t.tagName === "H2") dernierH2 = t.id;
    });
  }

  // Le navigateur fait défiler vers #ancre pendant l'analyse de la page, avant que ce script
  // ait créé les ancres manquantes : on refait le défilement une fois qu'elles existent.
  function rejoindreAncre() {
    if (!location.hash) return;
    var cible = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (cible) cible.scrollIntoView();
  }

  function construireSommaire() {
    var cible = document.getElementById("toc");
    var titres = document.querySelectorAll(".content h2, .content h3");
    if (!titres.length) return;
    donnerAncres(titres);
    rejoindreAncre();
    if (!cible) return;
    var html = "<h5>Sur cette page</h5><ul>";
    titres.forEach(function (t) {
      html += '<li class="' + t.tagName.toLowerCase() + '"><a href="#' + t.id + '">' + t.textContent + "</a></li>";
    });
    cible.innerHTML = html + "</ul>";
    var liens = cible.querySelectorAll("a");
    if (!("IntersectionObserver" in window)) return;
    var obs = new IntersectionObserver(function (entrees) {
      entrees.forEach(function (e) {
        if (!e.isIntersecting) return;
        liens.forEach(function (l) { l.classList.toggle("active", l.getAttribute("href") === "#" + e.target.id); });
      });
    }, { rootMargin: "-70px 0px -70% 0px" });
    titres.forEach(function (t) { obs.observe(t); });
  }

  function lireTheme() {
    try { return localStorage.getItem("edumatch-theme"); } catch (e) { return null; }
  }
  function appliquerTheme(t) {
    if (t) document.documentElement.setAttribute("data-theme", t);
    else document.documentElement.removeAttribute("data-theme");
  }
  function themeEffectif() {
    var t = document.documentElement.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function brancherBoutons() {
    var bTheme = document.getElementById("theme-btn");
    if (bTheme) bTheme.addEventListener("click", function () {
      var t = themeEffectif() === "dark" ? "light" : "dark";
      appliquerTheme(t);
      try { localStorage.setItem("edumatch-theme", t); } catch (e) { /* stockage indisponible : thème non mémorisé */ }
      dessinerSchemas();
    });
    brancherMenu();
  }

  // Menu des écrans étroits (moins de 860 px) : il s'ouvre et se ferme par son bouton, se
  // referme au clic sur un lien ou hors du panneau, et à la touche Échap — qui rend alors le
  // focus au bouton, pour qu'un utilisateur au clavier ne se retrouve pas en haut de page.
  function brancherMenu() {
    var bMenu = document.getElementById("menu-btn");
    var panneau = document.getElementById("sidebar");
    if (!bMenu || !panneau) return;

    function ouvert() { return document.body.classList.contains("nav-open"); }
    function fermer(rendreFocus) {
      if (!ouvert()) return;
      document.body.classList.remove("nav-open");
      bMenu.setAttribute("aria-expanded", "false");
      if (rendreFocus) bMenu.focus();
    }

    bMenu.addEventListener("click", function () {
      var etat = document.body.classList.toggle("nav-open");
      bMenu.setAttribute("aria-expanded", etat ? "true" : "false");
    });
    panneau.addEventListener("click", function (e) {
      if (e.target.closest("a")) fermer(false);
    });
    document.addEventListener("click", function (e) {
      if (ouvert() && !panneau.contains(e.target) && !bMenu.contains(e.target)) fermer(false);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && ouvert()) fermer(true);
    });
    // Retour arrière : le navigateur peut restaurer la page telle qu'elle était, menu ouvert.
    window.addEventListener("pageshow", function () { fermer(false); });
  }

  // La recherche vit dans son propre fichier, chargé par ce script : aucune page n'a besoin
  // d'être modifiée pour en disposer.
  function chargerRecherche() {
    var s = document.createElement("script");
    s.src = "assets/recherche.js";
    s.defer = true;
    document.head.appendChild(s);
  }

  // Dans un sous-groupe vertical, Mermaid place côte à côte les éléments qui ne
  // sont pas reliés entre eux. On les enchaîne par des liens invisibles (~~~)
  // pour qu'ils s'empilent : le schéma se lit en défilant vers le bas.
  function empilerSousGroupes(source) {
    if (!/^\s*(flowchart|graph)\s+(TD|TB)\b/m.test(source)) return source;
    var lignes = source.split("\n");
    var pile = [];
    var sortie = [];
    lignes.forEach(function (ligne) {
      var sg = ligne.match(/^\s*subgraph\s+([A-Za-z_][\w]*)/);
      if (sg) {
        if (pile.length) pile[pile.length - 1].enfants.push(sg[1]);
        pile.push({ enfants: [], vertical: true });
        sortie.push(ligne);
        return;
      }
      if (/^\s*direction\s+(LR|RL)\b/.test(ligne) && pile.length) pile[pile.length - 1].vertical = false;
      if (/^\s*end\s*$/.test(ligne) && pile.length) {
        var groupe = pile.pop();
        if (groupe.vertical && groupe.enfants.length > 1) {
          sortie.push("    " + groupe.enfants.join(" ~~~ "));
        }
        sortie.push(ligne);
        return;
      }
      var noeud = ligne.match(/^\s*([A-Za-z_][\w]*)\s*[\[\(\{]/);
      if (noeud && pile.length && !/--|==|~~~|-\.|\.-/.test(ligne)) pile[pile.length - 1].enfants.push(noeud[1]);
      sortie.push(ligne);
    });
    return sortie.join("\n");
  }

  var sourcesSchemas = [];
  function dessinerSchemas() {
    if (!window.mermaid) return;
    var blocs = document.querySelectorAll("pre.mermaid");
    blocs.forEach(function (b, i) {
      if (sourcesSchemas[i] === undefined) {
        // Le navigateur a transformé les <br/> des libellés en éléments : on les
        // remet en texte avant de lire la source, sinon les retours à la ligne sont perdus.
        var copie = b.cloneNode(true);
        copie.querySelectorAll("br").forEach(function (br) { br.replaceWith("<br/>"); });
        sourcesSchemas[i] = empilerSousGroupes(copie.textContent);
      }
      b.removeAttribute("data-processed");
      b.textContent = sourcesSchemas[i];
    });
    window.mermaid.initialize({
      startOnLoad: false,
      theme: themeEffectif() === "dark" ? "dark" : "neutral",
      fontFamily: "IBM Plex Sans, Segoe UI, Arial, sans-serif",
      securityLevel: "antiscript",
      flowchart: { htmlLabels: true, useMaxWidth: true, nodeSpacing: 30, rankSpacing: 45, padding: 18 },
      er: { useMaxWidth: true },
      sequence: { useMaxWidth: true },
    });
    window.mermaid.run({ nodes: blocs });
  }

  appliquerTheme(lireTheme());
  // Mermaid lance sinon son propre rendu au chargement, sur le texte brut,
  // avant que les libellés soient préparés : on le coupe tout de suite.
  if (window.mermaid) window.mermaid.initialize({ startOnLoad: false });
  document.addEventListener("DOMContentLoaded", function () {
    construireNavigation();
    construirePager();
    construireSommaire();
    brancherBoutons();
    chargerRecherche();
    // Les boîtes sont dimensionnées sur la police réelle : on attend qu'elle soit chargée.
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(dessinerSchemas);
    else dessinerSchemas();
  });
})();
