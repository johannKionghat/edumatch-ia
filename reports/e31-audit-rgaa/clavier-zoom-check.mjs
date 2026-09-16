// Vérifications complémentaires de la procédure d'audit (section 1 « clavier »,
// section 3 « zoom », section 5 « formulaires ») qu'un navigateur piloté permet
// de vérifier mécaniquement, sans jugement humain de perception — la section 2
// (lecteur d'écran) n'est volontairement pas couverte ici : voir le rapport.
import puppeteer from "puppeteer-core";
import fs from "fs";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = "http://127.0.0.1:8010";
const AUTH = { username: "audit_test", password: "Audit_Test_2026_Temp" };

const resultats = {};

function log(section, cle, valeur) {
  resultats[section] = resultats[section] || {};
  resultats[section][cle] = valeur;
  console.log(`[${section}] ${cle} =`, JSON.stringify(valeur));
}

async function activeElementInfo(page) {
  return page.evaluate(() => {
    const el = document.activeElement;
    if (!el) return null;
    const style = getComputedStyle(el);
    return {
      tag: el.tagName,
      id: el.id || null,
      name: el.getAttribute("name"),
      type: el.getAttribute("type"),
      texte: (el.textContent || "").trim().slice(0, 60),
      classe: el.className || null,
      outlineWidth: style.outlineWidth,
      outlineStyle: style.outlineStyle,
      outlineColor: style.outlineColor,
      boxShadow: style.boxShadow,
    };
  });
}

const browser = await puppeteer.launch({ executablePath: CHROME, headless: "new" });
try {
  const page = await browser.newPage();
  await page.authenticate(AUTH);
  await page.setBypassCSP(true);
  await page.setViewport({ width: 1280, height: 900 });

  // ── Section 1 : navigation clavier ──────────────────────────────────────
  await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });

  // Premier Tab -> doit activer le lien d'évitement
  await page.keyboard.press("Tab");
  const premierFocus = await activeElementInfo(page);
  log("clavier", "premier_tab", premierFocus);

  // Un focus a-t-il un contour visible (outline non nul ou box-shadow substitut) ?
  const focusVisible = premierFocus && (
    (premierFocus.outlineStyle !== "none" && premierFocus.outlineWidth !== "0px") ||
    (premierFocus.boxShadow && premierFocus.boxShadow !== "none")
  );
  log("clavier", "premier_focus_visible", focusVisible);

  // Entrée sur le lien d'évitement -> focus doit se déplacer dans <main>
  await page.keyboard.press("Enter");
  await new Promise((r) => setTimeout(r, 100));
  const cibleEvitement = await page.evaluate(() => document.activeElement && document.activeElement.closest("main") !== null);
  log("clavier", "lien_evitement_deplace_focus_dans_main", cibleEvitement);

  // Ordre de tabulation à travers le formulaire de recherche : recharger pour repartir propre
  await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
  const sequence = [];
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press("Tab");
    sequence.push(await activeElementInfo(page));
  }
  log("clavier", "sequence_tabulation_formulaire", sequence.map((e) => e && (e.id || e.name || e.tag)));
  const tousVisibles = sequence.every((e) => e && (
    (e.outlineStyle !== "none" && e.outlineWidth !== "0px") || (e.boxShadow && e.boxShadow !== "none")
  ));
  log("clavier", "tous_les_focus_de_la_sequence_visibles", tousVisibles);

  // Aucun piège au clavier : après 12 Tab, Shift+Tab doit revenir en arrière sans blocage
  await page.keyboard.down("Shift");
  await page.keyboard.press("Tab");
  await page.keyboard.up("Shift");
  const retourArriere = await activeElementInfo(page);
  log("clavier", "shift_tab_fonctionne", retourArriere !== null);

  // ── Section 5 : formulaire — département mal formé ──────────────────────
  await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
  await page.type("#champ-conseiller", "audit_test");
  await page.click('input[name="type_bac"][value="bg"]');
  await page.click('input[name="boursier"][value="false"]');
  await page.type("#champ-departement", "7");
  await page.click('#formulaire-recherche button[type="submit"]');
  await new Promise((r) => setTimeout(r, 800));
  const messageErreurDept = await page.evaluate(() => document.getElementById("messages-recherche").textContent);
  log("formulaires", "departement_mal_forme_message", messageErreurDept);
  const contientTraceTechnique = /Traceback|File "|site-packages|edumatch\.api|\.py"/i.test(messageErreurDept);
  log("formulaires", "departement_mal_forme_sans_trace_technique", !contientTraceTechnique);
  const focusApresErreur = await activeElementInfo(page);
  log("formulaires", "focus_apres_soumission_erreur", focusApresErreur);

  // ── Section 5 : écartement sans motif (nécessite un résultat) ───────────
  await page.evaluate(() => { document.getElementById("champ-departement").value = "05"; });
  await page.click('#formulaire-recherche button[type="submit"]');
  await page.waitForFunction(() => !document.getElementById("resultats").hidden, { timeout: 15000 });
  await new Promise((r) => setTimeout(r, 500));
  await page.click('input[value="ecartee"]');
  await page.click('.formulaire-decision button[type="submit"]');
  await new Promise((r) => setTimeout(r, 300));
  const statutTexte = await page.evaluate(() => {
    const s = document.querySelector(".statut-decision");
    return s ? s.textContent : null;
  });
  log("formulaires", "ecartement_sans_motif_message", statutTexte);
  const focusSurMotif = await page.evaluate(() => document.activeElement && document.activeElement.tagName === "TEXTAREA");
  log("formulaires", "focus_deplace_vers_champ_motif", focusSurMotif);

  // ── Section 3 : zoom / redimensionnement ────────────────────────────────
  // Équivalent approximatif d'un zoom navigateur à 200 % sur une fenêtre de 1280px :
  // on réduit le viewport CSS à 640px en conservant le même contenu texte (le zoom
  // navigateur agrandit le texte sans changer le viewport CSS ; réduire le viewport
  // à due proportion produit un rapport texte/espace disponible comparable — approximation
  // déclarée, pas un test de zoom réel du moteur de rendu).
  await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
  await page.setViewport({ width: 640, height: 800 });
  await new Promise((r) => setTimeout(r, 200));
  const debordement640 = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  log("zoom", "viewport_640_debordement_horizontal", debordement640.scrollWidth > debordement640.clientWidth + 1, debordement640);

  await page.setViewport({ width: 320, height: 700 });
  await new Promise((r) => setTimeout(r, 200));
  const debordement320 = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  log("zoom", "viewport_320_mesures", debordement320);
  log("zoom", "viewport_320_debordement_horizontal", debordement320.scrollWidth > debordement320.clientWidth + 1);

  fs.writeFileSync("clavier-zoom-resultats.json", JSON.stringify(resultats, null, 2));
} finally {
  await browser.close();
}
