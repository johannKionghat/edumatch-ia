// Écran conseiller : voir, comprendre, écarter avec motif.
//
// Vanilla JS, sans framework ni dépendance : décision d'architecture arrêtée
// dès la conception de l'API (voir routes/ecran.py). Ce fichier ne fait que consommer l'API déjà
// testée (`/matching`, `/explain`, `/feedback`) et construire le DOM.
//
// Règle stricte : aucune construction de HTML par concaténation de chaînes ni
// affectation à `innerHTML`. Tout le contenu dynamique (libellés de formation
// venus de Parcoursup, motifs, identifiants saisis par le conseiller) est
// posé via `textContent` ou `document.createElement`, jamais interprété comme
// du balisage. C'est ce qui protège des injections XSS ici, pas un
// échappement manuel qu'on pourrait oublier d'appliquer une fois.

const traductionsVariables = {
  type_bac: "Type de baccalauréat",
  boursier: "Statut de boursier",
  fili: "Filière de formation",
  fil_lib_voe_acc: "Libellé de la filière",
  form_lib_voe_acc: "Libellé de la formation",
  select_form: "Formation sélective",
  contrat_etab: "Contrat de l'établissement",
  tri: "Filière de tri Parcoursup",
  dep: "Département de la formation",
  acad_mies: "Académie",
  region_etab_aff: "Région de l'établissement",
  capa_fin: "Capacité d'accueil (session précédente)",
  voe_tot: "Nombre total de vœux (session précédente)",
  nb_voe_pp: "Nombre de vœux en procédure principale (session précédente)",
  nb_cla_pp: "Nombre de classements en procédure principale (session précédente)",
  prop_tot: "Nombre de propositions (session précédente)",
  acc_tot: "Nombre d'admis (session précédente)",
  acc_neobac: "Part de néo-bacheliers parmi les admis (session précédente)",
  acc_aca_orig: "Part d'admis issus de la même académie (session précédente)",
  acc_aca_orig_idf: "Part d'admis franciliens (session précédente)",
  acc_debutpp: "Rang du premier admis en procédure principale (session précédente)",
  acc_datebac: "Année d'obtention du baccalauréat des admis (session précédente)",
  acc_finpp: "Rang du dernier admis en procédure principale (session précédente)",
  ran_grp1: "Rang du dernier appelé du premier groupe (session précédente)",
  taux_session_precedente: "Taux d'admission observé la session précédente",
};

/** Traduit un nom technique de variable en libellé lisible par un conseiller qui n'est pas
 * data scientist. Les suffixes `_bg`, `_bt`, `_bp`, `_brs` déclinent une variable par type de
 * baccalauréat ou statut de boursier ; on les traduit une fois pour ne pas répéter la table
 * ci-dessus quatre fois par variable. Faute d'entrée dans la table, un nom encore inconnu est
 * simplement mis en forme (jamais laissé sous sa forme brute `snake_case`, jamais inventé). */
function traduireVariable(nom) {
  const suffixes = { "_bg_brs": " (bac général, boursiers)", "_bt_brs": " (bac techno, boursiers)",
    "_bp_brs": " (bac pro, boursiers)", "_bg": " (bac général)", "_bt": " (bac technologique)",
    "_bp": " (bac professionnel)", "_brs": " (boursiers)" };
  for (const [suffixe, precision] of Object.entries(suffixes)) {
    if (nom.endsWith(suffixe)) {
      const racine = nom.slice(0, -suffixe.length);
      return (traductionsVariables[racine] || formaterNomTechnique(racine)) + precision;
    }
  }
  return traductionsVariables[nom] || formaterNomTechnique(nom);
}

function formaterNomTechnique(nom) {
  const mots = nom.replace(/_/g, " ");
  return mots.charAt(0).toUpperCase() + mots.slice(1);
}

function creerElement(balise, options = {}) {
  const element = document.createElement(balise);
  if (options.texte !== undefined) element.textContent = options.texte;
  if (options.classe) element.className = options.classe;
  if (options.attributs) {
    for (const [nom, valeur] of Object.entries(options.attributs)) element.setAttribute(nom, valeur);
  }
  return element;
}

function formaterProportion(valeur) {
  return `${(valeur * 100).toFixed(1)} %`;
}

// ─── Recherche ────────────────────────────────────────────────────────────

let dernierBoutonExplicationActif = null;

function lireProfilFormulaire(formulaire) {
  const donnees = new FormData(formulaire);
  const profil = {
    type_bac: donnees.get("type_bac"),
    boursier: donnees.get("boursier") === "true",
    top_n: Number(donnees.get("top_n")) || 10,
  };
  for (const cle of ["type_formation", "domaine", "departement"]) {
    const valeur = (donnees.get(cle) || "").trim();
    if (valeur) profil[cle] = valeur;
  }
  return profil;
}

async function rechercherFormations(evenement) {
  evenement.preventDefault();
  const formulaire = evenement.target;
  const zoneMessages = document.getElementById("messages-recherche");
  zoneMessages.textContent = "";

  const identifiantConseiller = document.getElementById("champ-conseiller").value.trim();
  if (!identifiantConseiller) {
    zoneMessages.textContent = "Renseignez votre identifiant de conseiller avant de rechercher.";
    return;
  }
  const profil = lireProfilFormulaire(formulaire);
  if (!profil.type_bac || document.querySelector("input[name='boursier']:checked") === null) {
    zoneMessages.textContent = "Le type de baccalauréat et le statut de boursier sont obligatoires.";
    return;
  }

  let reponse;
  try {
    reponse = await fetch("/matching", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profil),
    });
  } catch {
    zoneMessages.textContent = "Le service est injoignable. Réessayez dans quelques instants.";
    return;
  }

  if (!reponse.ok) {
    const detail = await lireDetailErreur(reponse);
    zoneMessages.textContent = detail;
    return;
  }

  const resultat = await reponse.json();
  afficherResultats(resultat, profil, identifiantConseiller);
}

// Traduit le nom technique d'un champ de formulaire (tel que Pydantic le rapporte dans
// `loc`) en libellé lisible par un conseiller. Table distincte de `traductionsVariables`
// ci-dessus : celle-ci porte les noms de variables du modèle (SHAP), celle-là les noms
// de champs du formulaire de recherche et de décision.
const libellesChampsFormulaire = {
  type_bac: "Type de baccalauréat",
  boursier: "Statut de boursier",
  type_formation: "Type de formation",
  domaine: "Domaine recherché",
  departement: "Département visé",
  top_n: "Nombre de recommandations",
  identifiant_formation: "Formation",
  session: "Session",
  decision: "Décision",
  motif: "Motif",
};

// Phrase associée à chaque type d'erreur de validation Pydantic v2 rencontré par
// l'écran. Volontairement reformulée plutôt que reprise telle quelle : le message brut
// de Pydantic (ex. le motif d'une expression régulière) n'est ni utile ni élégant pour
// un conseiller, sans pour autant constituer une trace technique (aucun chemin de
// fichier, aucun nom de module) — cette reformulation reste une amélioration de
// lisibilité, pas une correction de fuite.
const phrasesParTypeErreurValidation = {
  missing: "ce champ est obligatoire.",
  string_pattern_mismatch: "le format saisi ne correspond pas à celui attendu.",
  string_too_long: "la valeur saisie est trop longue.",
  string_too_short: "la valeur saisie est trop courte.",
  int_parsing: "un nombre entier est attendu.",
  bool_parsing: "une valeur « oui » ou « non » est attendue.",
  greater_than_equal: "la valeur saisie est trop petite.",
  less_than_equal: "la valeur saisie est trop grande.",
};

function libelleChampFormulaire(chemin) {
  const nomChamp = (chemin || []).filter((segment) => segment !== "body").pop();
  return libellesChampsFormulaire[nomChamp] || formaterNomTechnique(String(nomChamp || "Champ"));
}

function phraseErreurDeValidation(erreur) {
  const libelle = libelleChampFormulaire(erreur.loc);
  const phrase = phrasesParTypeErreurValidation[erreur.type] || "la valeur saisie n'est pas valide.";
  return `${libelle} : ${phrase}`;
}

async function lireDetailErreur(reponse) {
  try {
    const corps = await reponse.json();
    if (typeof corps.detail === "string") return corps.detail;
    // FastAPI/Pydantic v2 renvoie, sur une erreur de validation 422, un tableau
    // d'objets d'erreur (`type`, `loc`, `msg`) plutôt qu'une chaîne — un cas distinct
    // à traiter, faute de quoi le conseiller ne voit que « Erreur 422. ».
    if (Array.isArray(corps.detail) && corps.detail.length > 0) {
      return corps.detail.map(phraseErreurDeValidation).join(" ");
    }
    return `Erreur ${reponse.status}.`;
  } catch {
    return `Erreur ${reponse.status}.`;
  }
}

// ─── Affichage des résultats ────────────────────────────────────────────────

function afficherResultats(resultat, profil, identifiantConseiller) {
  const section = document.getElementById("resultats");
  section.hidden = false;

  const avertissements = document.getElementById("avertissements-generaux");
  avertissements.textContent = "";
  avertissements.appendChild(creerAvertissement(resultat.avertissement_accessibilite));
  avertissements.appendChild(creerAvertissement(resultat.avertissement_debouches));
  if (!resultat.debouches_disponible && resultat.motif_indisponibilite_debouches) {
    avertissements.appendChild(creerAvertissement(
      `Débouchés indisponibles pour l'ensemble du service : ${resultat.motif_indisponibilite_debouches}`
    ));
  }

  const liste = document.getElementById("liste-recommandations");
  liste.textContent = "";
  if (resultat.recommandations.length === 0) {
    const item = creerElement("li", { texte: "Aucune formation ne correspond à ce profil." });
    liste.appendChild(item);
    return;
  }
  resultat.recommandations.forEach((recommandation, indice) => {
    liste.appendChild(
      construireCarteRecommandation(recommandation, resultat.session, profil, identifiantConseiller, indice)
    );
  });
  section.scrollIntoView({ behavior: "smooth" });
}

function creerAvertissement(texte) {
  return creerElement("p", { classe: "avertissement", texte });
}

function construireCarteRecommandation(recommandation, session, profil, identifiantConseiller, indice) {
  const carte = creerElement("li", { classe: "carte-recommandation" });
  carte.appendChild(creerElement("h3", { texte: recommandation.libelle_formation }));
  carte.appendChild(construireDetailScore(recommandation));
  carte.appendChild(construireActions(recommandation, session, profil, identifiantConseiller, indice));
  return carte;
}

function construireDetailScore(recommandation) {
  const dl = creerElement("dl", { classe: "details-score" });
  const ajouter = (titre, valeur) => {
    dl.appendChild(creerElement("dt", { texte: titre }));
    dl.appendChild(creerElement("dd", { texte: valeur }));
  };

  ajouter("Score global (affinité x accessibilité x débouchés)", recommandation.score.toFixed(3));
  ajouter("Affinité — correspond aux préférences exprimées", texteOuiNon(
    recommandation.affinite.filtre_type_formation_respecte && recommandation.affinite.filtre_domaine_respecte
  ) + ` (valeur ${recommandation.affinite.valeur.toFixed(2)})`);
  ajouter("Accessibilité — chances d'admission estimées", formaterProportion(recommandation.accessibilite.valeur));
  dl.lastElementChild.appendChild(document.createElement("br"));
  dl.lastElementChild.appendChild(creerElement("span", {
    classe: "etat-indisponible",
    texte: "Valeur brute avant écrêtage : " + recommandation.accessibilite.valeur_brute.toFixed(3),
  }));

  const dd = creerElement("dd");
  dd.appendChild(creerElement("span", {
    classe: `badge ${recommandation.debouches.disponible ? "badge-disponible" : "badge-indisponible"}`,
    texte: recommandation.debouches.disponible ? "Mesuré" : "Indisponible",
  }));
  dd.appendChild(document.createElement("br"));
  dd.appendChild(document.createTextNode(recommandation.debouches.motif));
  dl.appendChild(creerElement("dt", { texte: "Débouchés territoriaux" }));
  dl.appendChild(dd);

  return dl;
}

function texteOuiNon(booleen) {
  return booleen ? "Oui" : "Non";
}

// ─── Comprendre : explication SHAP précalculée ─────────────────────────────

function construireActions(recommandation, session, profil, identifiantConseiller, indice) {
  const conteneur = creerElement("div", { classe: "actions-carte" });

  const boutonComprendre = creerElement("button", {
    texte: "Comprendre cette recommandation",
    classe: "bouton-secondaire",
    attributs: { type: "button" },
  });
  boutonComprendre.addEventListener("click", () => {
    dernierBoutonExplicationActif = boutonComprendre;
    afficherExplication(session, recommandation, profil);
  });
  conteneur.appendChild(boutonComprendre);

  const formulaireDecision = construireFormulaireDecision(recommandation, session, profil, identifiantConseiller, indice);
  const bloc = creerElement("div");
  bloc.appendChild(conteneur);
  bloc.appendChild(formulaireDecision);
  return bloc;
}

async function afficherExplication(session, recommandation, profil) {
  const section = document.getElementById("explication");
  const contenu = document.getElementById("contenu-explication");
  contenu.textContent = "";
  section.hidden = false;

  const parametres = new URLSearchParams({
    session: String(session),
    cod_aff_form: recommandation.identifiant_formation,
    type_bac: profil.type_bac,
    boursier: String(profil.boursier),
  });

  let reponse;
  try {
    reponse = await fetch(`/explain?${parametres.toString()}`);
  } catch {
    contenu.textContent = "Le service d'explication est injoignable.";
    section.focus();
    return;
  }
  if (!reponse.ok) {
    contenu.textContent = await lireDetailErreur(reponse);
    section.focus();
    return;
  }

  const explication = await reponse.json();
  contenu.appendChild(creerElement("p", { texte: `Formation : ${recommandation.libelle_formation}` }));
  contenu.appendChild(creerAvertissement(explication.avertissement_accessibilite));
  contenu.appendChild(construireTableauContributions(explication));
  section.focus();
}

function construireTableauContributions(explication) {
  const table = creerElement("table", { classe: "tableau-contributions" });
  table.appendChild(creerElement("caption", {
    texte: `Prédiction : ${formaterProportion(explication.prediction)} — valeur de base du modèle : `
      + `${formaterProportion(explication.valeur_base)} (moyenne sur l'échantillon de référence)`,
  }));
  const entete = document.createElement("tr");
  ["Variable", "Effet", "Contribution"].forEach((titre) => {
    entete.appendChild(creerElement("th", { texte: titre, attributs: { scope: "col" } }));
  });
  const thead = document.createElement("thead");
  thead.appendChild(entete);
  table.appendChild(thead);

  const corps = document.createElement("tbody");
  explication.contributions.forEach((contribution) => {
    const ligne = document.createElement("tr");
    ligne.appendChild(creerElement("th", { texte: traduireVariable(contribution.variable), attributs: { scope: "row" } }));
    const sens = contribution.contribution >= 0 ? "Augmente l'estimation" : "Diminue l'estimation";
    ligne.appendChild(creerElement("td", { texte: sens }));
    ligne.appendChild(creerElement("td", { texte: contribution.contribution.toFixed(4) }));
    corps.appendChild(ligne);
  });
  table.appendChild(corps);
  return table;
}

function fermerExplication() {
  const section = document.getElementById("explication");
  section.hidden = true;
  document.getElementById("contenu-explication").textContent = "";
  if (dernierBoutonExplicationActif) dernierBoutonExplicationActif.focus();
}

// ─── Écarter avec motif (article 14) ────────────────────────────────────────

function construireFormulaireDecision(recommandation, session, profil, identifiantConseiller, indice) {
  const formulaire = creerElement("form", { classe: "formulaire-decision" });
  const legendeId = `decision-legende-${indice}`;
  const motifId = `decision-motif-${indice}`;
  const statutId = `decision-statut-${indice}`;

  const fieldset = creerElement("fieldset");
  fieldset.appendChild(creerElement("legend", { texte: "Votre décision sur cette recommandation", attributs: { id: legendeId } }));
  ["retenue", "ecartee"].forEach((valeur) => {
    const label = document.createElement("label");
    const input = creerElement("input", { attributs: { type: "radio", name: `decision-${indice}`, value: valeur } });
    label.appendChild(input);
    label.appendChild(document.createTextNode(valeur === "retenue" ? " Retenir" : " Écarter"));
    fieldset.appendChild(label);
  });
  formulaire.appendChild(fieldset);

  const labelMotif = creerElement("label", { texte: "Motif (obligatoire pour écarter)", attributs: { for: motifId } });
  const motif = creerElement("textarea", { attributs: { id: motifId, maxlength: "1000" } });
  formulaire.appendChild(labelMotif);
  formulaire.appendChild(motif);

  const boutonValider = creerElement("button", { texte: "Enregistrer ma décision", attributs: { type: "submit" } });
  formulaire.appendChild(boutonValider);

  const statut = creerElement("p", { classe: "statut-decision", attributs: { id: statutId, role: "status", "aria-live": "polite" } });
  formulaire.appendChild(statut);

  formulaire.addEventListener("submit", (evenement) => {
    evenement.preventDefault();
    const decisionCochee = formulaire.querySelector(`input[name='decision-${indice}']:checked`);
    enregistrerDecision(formulaire, decisionCochee, motif, statut, recommandation, session, profil, identifiantConseiller);
  });

  return formulaire;
}

async function enregistrerDecision(formulaire, decisionCochee, motif, statut, recommandation, session, profil, identifiantConseiller) {
  statut.className = "statut-decision";
  statut.textContent = "";
  if (!decisionCochee) {
    statut.classList.add("erreur");
    statut.textContent = "Choisissez « Retenir » ou « Écarter » avant d'enregistrer.";
    return;
  }
  const decision = decisionCochee.value;
  if (decision === "ecartee" && !motif.value.trim()) {
    statut.classList.add("erreur");
    statut.textContent = "Un écartement doit être motivé (article 14) : indiquez le motif.";
    motif.focus();
    return;
  }

  // `identifiant_conseiller` n'est plus envoyé ici (revue de sécurité) : un champ déclaratif
  // aurait permis à n'importe quel appelant d'imputer un écartement à un autre conseiller. Le
  // serveur le dérive désormais du principal HTTP Basic authentifié (`api/auth.py`) — le champ
  // "Identifiant de conseiller" du formulaire de recherche ne sert donc plus qu'à personnaliser
  // l'affichage local, jamais à s'identifier auprès de l'API.
  const corps = {
    session,
    identifiant_formation: recommandation.identifiant_formation,
    type_bac: profil.type_bac,
    boursier: profil.boursier,
    decision,
    motif: motif.value.trim() || null,
  };

  let reponse;
  try {
    reponse = await fetch("/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corps),
    });
  } catch {
    statut.classList.add("erreur");
    statut.textContent = "Le service est injoignable, la décision n'a pas été enregistrée.";
    return;
  }

  if (reponse.status === 401) {
    statut.classList.add("erreur");
    statut.textContent = "Authentification requise ou invalide : rechargez la page et connectez-vous.";
    return;
  }

  if (!reponse.ok) {
    statut.classList.add("erreur");
    statut.textContent = await lireDetailErreur(reponse);
    return;
  }

  statut.classList.add("succes");
  statut.textContent = decision === "retenue" ? "Décision « retenue » enregistrée." : "Décision « écartée » enregistrée avec le motif fourni.";
}

// ─── Liste des départements ─────────────────────────────────────────────────

/** Remplit le menu déroulant depuis `/departements` : les codes présents dans le catalogue de la
 * session courante, jamais une liste codée en dur. L'option « Tous » (valeur vide, aucun filtre)
 * est dans le HTML et reste la seule si la liste ne peut pas être chargée : la recherche
 * fonctionne alors sans filtre de département, et l'aide du champ le dit. */
async function chargerDepartements() {
  const liste = document.getElementById("champ-departement");
  const aide = document.getElementById("aide-departement");
  let reponse;
  try {
    reponse = await fetch("/departements");
  } catch {
    reponse = null;
  }
  if (!reponse || !reponse.ok) {
    aide.textContent = "La liste des départements n'a pas pu être chargée : la recherche porte sur tous les départements.";
    return;
  }
  const donnees = await reponse.json();
  for (const departement of donnees.departements) {
    const texte = departement.libelle ? `${departement.code} — ${departement.libelle}` : departement.code;
    liste.appendChild(creerElement("option", { texte, attributs: { value: departement.code } }));
  }
}

// ─── Initialisation ─────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("formulaire-recherche").addEventListener("submit", rechercherFormations);
  document.getElementById("bouton-fermer-explication").addEventListener("click", fermerExplication);
  chargerDepartements();
});
