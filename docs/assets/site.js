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

  function construireSommaire() {
    var cible = document.getElementById("toc");
    var titres = document.querySelectorAll(".content h2, .content h3");
    if (!cible || !titres.length) return;
    var html = "<h5>Sur cette page</h5><ul>";
    titres.forEach(function (t) {
      if (!t.id) t.id = slug(t.textContent);
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
    var bMenu = document.getElementById("menu-btn");
    if (bMenu) bMenu.addEventListener("click", function () {
      var ouvert = document.body.classList.toggle("nav-open");
      bMenu.setAttribute("aria-expanded", ouvert ? "true" : "false");
    });
  }

  var sourcesSchemas = [];
  function dessinerSchemas() {
    if (!window.mermaid) return;
    var blocs = document.querySelectorAll("pre.mermaid");
    blocs.forEach(function (b, i) {
      if (sourcesSchemas[i] === undefined) sourcesSchemas[i] = b.textContent;
      b.removeAttribute("data-processed");
      b.textContent = sourcesSchemas[i];
    });
    window.mermaid.initialize({
      startOnLoad: false,
      theme: themeEffectif() === "dark" ? "dark" : "neutral",
      fontFamily: "IBM Plex Sans, Segoe UI, Arial, sans-serif",
      securityLevel: "antiscript",
      flowchart: { htmlLabels: true, useMaxWidth: false, nodeSpacing: 40, rankSpacing: 50 },
      er: { useMaxWidth: false },
      sequence: { useMaxWidth: false },
    });
    window.mermaid.run({ nodes: blocs });
  }

  appliquerTheme(lireTheme());
  document.addEventListener("DOMContentLoaded", function () {
    construireNavigation();
    construirePager();
    construireSommaire();
    brancherBoutons();
    dessinerSchemas();
  });
})();
