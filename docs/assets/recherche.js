// Recherche dans toute la documentation, côté navigateur, sans dépendance.
//
// L'index (assets/recherche-index.js, généré par scripts/generer_index_recherche.py) pèse
// environ 500 Ko : il n'est chargé qu'au premier focus sur le champ, pour ne pas alourdir
// chaque page de la documentation.
//
// Accessibilité : motif « combobox » de l'ARIA — le champ garde le focus, les flèches
// déplacent un résultat actif signalé par aria-activedescendant, Entrée l'ouvre, Échap ferme
// la liste. Tab quitte le champ normalement : le focus n'est jamais piégé.
(function () {
  "use strict";

  var MAX_RESULTATS = 10;
  var index = null;
  var chargement = null;

  // Minuscules, sans accents, apostrophes unifiées, espaces et retours à la ligne réduits à un
  // seul espace. Appliquée à la requête comme au texte indexé.
  function normaliser(s) {
    return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
      .replace(/[’‘]/g, "'").replace(/\s+/g, " ").trim();
  }

  // La même normalisation, avec la position d'origine de chaque caractère produit : c'est ce
  // qui permet de mettre en gras, dans le texte original accentué, le passage trouvé.
  function normaliserAvecCarte(s) {
    var sortie = "";
    var carte = [];
    var espace = false;
    for (var i = 0; i < s.length; i++) {
      var c = s[i];
      if (/\s/.test(c)) {
        if (!espace && sortie.length) { sortie += " "; carte.push(i); }
        espace = true;
        continue;
      }
      espace = false;
      var n = c.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
        .replace(/[’‘]/g, "'");
      for (var k = 0; k < n.length; k++) { sortie += n[k]; carte.push(i); }
    }
    return { texte: sortie, carte: carte };
  }

  function echapper(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function chargerIndex() {
    if (index) return Promise.resolve(index);
    if (chargement) return chargement;
    chargement = new Promise(function (resoudre, rejeter) {
      var s = document.createElement("script");
      s.src = "assets/recherche-index.js";
      s.onload = function () {
        index = (window.EDUMATCH_INDEX_RECHERCHE || []).map(function (e) {
          e.titreNorm = normaliser(e.titre);
          e.texteNorm = normaliser(e.texte);
          return e;
        });
        resoudre(index);
      };
      s.onerror = function () { chargement = null; rejeter(new Error("index introuvable")); };
      document.head.appendChild(s);
    });
    return chargement;
  }

  // Tous les mots de la requête doivent figurer dans la section. L'expression exacte pèse plus
  // que des mots épars, et un titre plus que le corps du texte.
  function chercher(requete) {
    var q = normaliser(requete);
    if (q.length < 2) return [];
    var mots = q.split(" ");
    var trouves = [];
    index.forEach(function (e, rang) {
      var tout = e.titreNorm + " " + e.texteNorm;
      for (var i = 0; i < mots.length; i++) if (tout.indexOf(mots[i]) === -1) return;
      var score = 0;
      if (e.titreNorm.indexOf(q) !== -1) score += 100;
      if (e.texteNorm.indexOf(q) !== -1) score += 40;
      mots.forEach(function (m) { if (e.titreNorm.indexOf(m) !== -1) score += 10; });
      trouves.push({ entree: e, score: score, rang: rang });
    });
    trouves.sort(function (a, b) { return b.score - a.score || a.rang - b.rang; });
    return trouves.slice(0, MAX_RESULTATS).map(function (t) { return t.entree; });
  }

  // Le passage du texte autour de la première occurrence, terme en gras.
  function extraitSurligne(e, requete) {
    var q = normaliser(requete);
    var n = normaliserAvecCarte(e.texte);
    var pos = n.texte.indexOf(q);
    var longueur = q.length;
    if (pos === -1) {
      var premier = q.split(" ")[0];
      pos = n.texte.indexOf(premier);
      longueur = premier.length;
    }
    if (pos === -1) return echapper(e.extrait);
    var debut = Math.max(0, pos - 60);
    var fin = Math.min(n.texte.length, pos + longueur + 100);
    var oDebut = n.carte[debut];
    var oFin = n.carte[fin - 1] + 1;
    var mDebut = n.carte[pos];
    var mFin = n.carte[pos + longueur - 1] + 1;
    return (debut > 0 ? "… " : "") +
      echapper(e.texte.slice(oDebut, mDebut)) +
      "<strong>" + echapper(e.texte.slice(mDebut, mFin)) + "</strong>" +
      echapper(e.texte.slice(mFin, oFin)) +
      (fin < n.texte.length ? " …" : "");
  }

  function construire() {
    var barre = document.querySelector(".topbar");
    var espaceur = barre && barre.querySelector(".spacer");
    if (!barre || !espaceur) return;

    var bloc = document.createElement("div");
    bloc.className = "recherche";
    bloc.setAttribute("role", "search");
    bloc.innerHTML =
      '<label class="sr-only" for="recherche-champ">Rechercher dans la documentation</label>' +
      '<input id="recherche-champ" type="search" autocomplete="off" spellcheck="false"' +
      ' placeholder="Rechercher…" role="combobox" aria-autocomplete="list"' +
      ' aria-expanded="false" aria-controls="recherche-resultats" aria-describedby="recherche-aide">' +
      '<span id="recherche-aide" class="sr-only">Flèches haut et bas pour parcourir les résultats, ' +
      'Entrée pour ouvrir, Échap pour fermer.</span>' +
      '<div class="recherche-panneau" tabindex="0" hidden>' +
      '<ul id="recherche-resultats" role="listbox" aria-label="Résultats de la recherche"></ul>' +
      '<p class="recherche-vide" hidden></p>' +
      '</div>' +
      '<p id="recherche-statut" class="sr-only" role="status" aria-live="polite"></p>';
    barre.insertBefore(bloc, espaceur);

    var champ = bloc.querySelector("#recherche-champ");
    var panneau = bloc.querySelector(".recherche-panneau");
    var liste = bloc.querySelector("#recherche-resultats");
    var vide = bloc.querySelector(".recherche-vide");
    var statut = bloc.querySelector("#recherche-statut");
    var resultats = [];
    var actif = -1;

    function fermer() {
      panneau.hidden = true;
      champ.setAttribute("aria-expanded", "false");
      champ.removeAttribute("aria-activedescendant");
      actif = -1;
    }

    function activer(i) {
      var options = liste.querySelectorAll('[role="option"]');
      if (!options.length) return;
      actif = (i + options.length) % options.length;
      options.forEach(function (o, k) { o.setAttribute("aria-selected", k === actif ? "true" : "false"); });
      champ.setAttribute("aria-activedescendant", options[actif].id);
      options[actif].scrollIntoView({ block: "nearest" });
    }

    function ouvrir(e) {
      window.location.href = e.page + "#" + e.ancre;
      fermer();
    }

    function afficher() {
      var requete = champ.value;
      actif = -1;
      champ.removeAttribute("aria-activedescendant");
      if (normaliser(requete).length < 2) { fermer(); statut.textContent = ""; return; }
      resultats = chercher(requete);
      liste.innerHTML = resultats.map(function (e, i) {
        return '<li role="option" id="recherche-option-' + i + '" aria-selected="false" data-i="' + i + '">' +
          '<span class="recherche-titre">' + echapper(e.titre) + "</span>" +
          '<span class="recherche-page">' + echapper(e.nomPage) + "</span>" +
          '<span class="recherche-extrait">' + extraitSurligne(e, requete) + "</span></li>";
      }).join("");
      vide.hidden = resultats.length > 0;
      vide.textContent = resultats.length ? "" : "Aucun résultat pour « " + requete.trim() + " ».";
      panneau.hidden = false;
      champ.setAttribute("aria-expanded", resultats.length ? "true" : "false");
      statut.textContent = resultats.length
        ? resultats.length + " résultat" + (resultats.length > 1 ? "s" : "") + (resultats.length === MAX_RESULTATS ? " affichés, les plus pertinents" : "")
        : "Aucun résultat";
    }

    champ.addEventListener("focus", function () { chargerIndex().catch(function () {}); });
    champ.addEventListener("input", function () {
      chargerIndex().then(afficher, function () {
        panneau.hidden = false;
        vide.hidden = false;
        vide.textContent = "L'index de recherche n'a pas pu être chargé.";
      });
    });
    champ.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        if (panneau.hidden && champ.value) afficher();
        activer(actif + 1);
      } else if (ev.key === "ArrowUp") {
        ev.preventDefault();
        activer(actif - 1);
      } else if (ev.key === "Enter") {
        if (!panneau.hidden && resultats.length) {
          ev.preventDefault();
          ouvrir(resultats[actif >= 0 ? actif : 0]);
        }
      } else if (ev.key === "Escape") {
        if (!panneau.hidden) { ev.preventDefault(); ev.stopPropagation(); fermer(); }
        else if (champ.value) { champ.value = ""; statut.textContent = ""; }
      } else if (ev.key === "Tab") {
        fermer();
      }
    });
    // Garder le focus dans le champ quand on clique un résultat : le clic ouvre la page.
    liste.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
    liste.addEventListener("click", function (ev) {
      var option = ev.target.closest('[role="option"]');
      if (option) ouvrir(resultats[Number(option.getAttribute("data-i"))]);
    });
    document.addEventListener("click", function (ev) { if (!bloc.contains(ev.target)) fermer(); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", construire);
  else construire();
})();
