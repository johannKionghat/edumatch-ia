import puppeteer from "puppeteer-core";
import fs from "fs";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = "http://127.0.0.1:8010";
const AUTH = { username: "audit_test", password: "Audit_Test_2026_Temp" };

function resume(results) {
  const parGravite = {};
  for (const v of results.violations) {
    parGravite[v.impact] = (parGravite[v.impact] || 0) + 1;
  }
  return parGravite;
}

async function auditPage(page, label) {
  await page.addScriptTag({ path: "./axe.min.js" });
  const results = await page.evaluate(async () => {
    // eslint-disable-next-line no-undef
    return await axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] });
  });
  fs.writeFileSync(`axe-${label}.json`, JSON.stringify(results, null, 2));
  console.log(`--- ${label} ---`);
  console.log("violations:", results.violations.length, JSON.stringify(resume(results)));
  for (const v of results.violations) {
    console.log(" -", v.id, "[" + v.impact + "]", v.nodes.length, "nœud(s) :", v.help);
  }
  console.log("passes:", results.passes.length, "incomplete:", results.incomplete.length);
  return results;
}

const browser = await puppeteer.launch({ executablePath: CHROME, headless: "new" });
try {
  const page = await browser.newPage();
  await page.authenticate(AUTH);
  await page.setBypassCSP(true); // la CSP stricte (default-src 'self') de l'écran bloque l'injection du script axe-core : contournée uniquement pour l'audit, jamais une propriété de l'écran lui-même.
  await page.setViewport({ width: 1280, height: 900 });

  // État 1 : écran vide, avant toute recherche
  await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
  await auditPage(page, "ecran-vide");

  // État 2 : formulaire rempli, résultats affichés
  await page.type("#champ-conseiller", "audit_test");
  await page.click('input[name="type_bac"][value="bg"]');
  await page.click('input[name="boursier"][value="false"]');
  await page.type("#champ-departement", "05");
  await page.click('#formulaire-recherche button[type="submit"]');
  // attendre que la section résultats ne soit plus "hidden"
  await page.waitForFunction(
    () => {
      const s = document.querySelector("#resultats");
      return s && !s.hidden;
    },
    { timeout: 15000 }
  );
  await new Promise((r) => setTimeout(r, 500));
  await auditPage(page, "ecran-resultats");

  // État 3 : panneau d'explication ouvert, si un bouton "Comprendre" existe
  const boutonComprendre = await page.$('#liste-recommandations button');
  if (boutonComprendre) {
    await boutonComprendre.click();
    await page
      .waitForFunction(
        () => {
          const s = document.querySelector("#explication");
          return s && !s.hidden;
        },
        { timeout: 10000 }
      )
      .catch(() => console.log("Panneau d'explication non ouvert dans le délai — état 3 ignoré."));
    const explicationVisible = await page.evaluate(() => {
      const s = document.querySelector("#explication");
      return s && !s.hidden;
    });
    if (explicationVisible) {
      await new Promise((r) => setTimeout(r, 300));
      await auditPage(page, "ecran-explication");
    }
  } else {
    console.log("Aucun bouton 'Comprendre' trouvé dans les résultats — état 3 non audité.");
  }
} finally {
  await browser.close();
}
