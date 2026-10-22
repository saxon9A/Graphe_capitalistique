// Port JS de dashboard/lib/scoring.py — cycle de bail 3/6/9 et score de potentiel.
// RIEN ici n'est une donnée publiée : tout est calculé à partir de la date d'installation au
// siège actuel. Calculé à chaque rendu (jamais mis en cache), comme en Python : le score et les
// échéances restent toujours à jour, même sur un site statique jamais republié. Voir scoring.py
// pour la documentation complète de la méthode (reprise ici à l'identique).

export const STATUT_INCONNU = "Échéance inconnue";
const NEUTRE = 0.5;

export const LIBELLE_URGENCE = {
  3: "Préavis ouvert",
  2: "Échéance < 1 an",
  1: "Échéance 1 à 2 ans",
  0: "Échéance > 2 ans",
  "null": STATUT_INCONNU,
};
export const ORDRE_URGENCE_LIBELLES = [3, 2, 1, 0, null].map((k) => LIBELLE_URGENCE[k ?? "null"]);

function toDateOnly(d) {
  if (!d) return null;
  const s = String(d).slice(0, 10);
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return null;
  const dt = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return Number.isNaN(dt.getTime()) ? null : dt;
}

function addYearsUTC(d, years) {
  const r = new Date(d.getTime());
  const targetYear = r.getUTCFullYear() + years;
  r.setUTCFullYear(targetYear);
  // 29 février sur une année non bissextile -> 28 (comme le except ValueError de bail_369)
  if (r.getUTCMonth() !== d.getUTCMonth()) r.setUTCDate(28);
  return r;
}

function addDaysUTC(d, days) {
  return new Date(d.getTime() + days * 86400000);
}

function diffDaysUTC(a, b) {
  return Math.round((a.getTime() - b.getTime()) / 86400000);
}

function fmtDateFR(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getUTCDate())}/${p(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`;
}

/** Équivalent de bail_369() : dates et statut AFFICHÉS (fiche, filtre de la colonne de gauche). */
export function bail369(dateInstallation, aujourdhui = new Date()) {
  const vide = {
    prochaineEcheance369: null, dateLimitePreavis: null, joursAvantLimite: null,
    urgence369: null, statutBail: STATUT_INCONNU, verrouille: null,
  };
  const d0 = toDateOnly(dateInstallation);
  if (!d0) return vide;
  const today = new Date(Date.UTC(aujourdhui.getUTCFullYear(), aujourdhui.getUTCMonth(), aujourdhui.getUTCDate()));

  let k = 1;
  let echeance = addYearsUTC(d0, 3 * k);
  while (echeance.getTime() <= today.getTime()) {
    k += 1;
    echeance = addYearsUTC(d0, 3 * k);
  }
  let limite = addDaysUTC(echeance, -182);

  let verrouille = false;
  if (today.getTime() >= limite.getTime()) {
    verrouille = true;
    k += 1;
    echeance = addYearsUTC(d0, 3 * k);
    limite = addDaysUTC(echeance, -182);
  }

  const jours = diffDaysUTC(limite, today);
  let urgence;
  if (jours <= 90) urgence = 3;
  else if (jours <= 365) urgence = 2;
  else if (jours <= 730) urgence = 1;
  else urgence = 0;

  let statut;
  if (verrouille) {
    statut = `Délai de préavis dépassé pour l'échéance précédente : engagé jusqu'au ${fmtDateFR(echeance)} ` +
      `(prochain préavis possible avant le ${fmtDateFR(limite)})`;
  } else if (urgence === 3) {
    statut = `Fenêtre de préavis imminente — échéance du bail le ${fmtDateFR(echeance)}`;
  } else {
    statut = `Échéance du bail estimée au ${fmtDateFR(echeance)} (préavis à donner avant le ${fmtDateFR(limite)})`;
  }
  return {
    prochaineEcheance369: echeance, dateLimitePreavis: limite, joursAvantLimite: jours,
    urgence369: urgence, statutBail: statut, verrouille,
  };
}

// --- Score de potentiel (bail + finances) -----------------------------------
const PONDERATIONS = { bail: 40 / 65, finances: 25 / 65 };
const COURBE_BAIL = [[0, 0.25], [4, 0.25], [6, 0.85], [8, 1.0], [22, 1.0], [26, 0.70], [30, 0.50], [36, 0.40]];

function interpoler(points, x) {
  if (x <= points[0][0]) return points[0][1];
  for (let i = 0; i < points.length - 1; i++) {
    const [x0, y0] = points[i];
    const [x1, y1] = points[i + 1];
    if (x <= x1) return y0 + (y1 - y0) * (x - x0) / (x1 - x0);
  }
  return points[points.length - 1][1];
}

function addMonthsUTC(d, mois) {
  const total = d.getUTCFullYear() * 12 + d.getUTCMonth() + mois;
  const annee = Math.floor(total / 12);
  const m = total - annee * 12;
  const jour = d.getUTCDate();
  for (let j = jour; j >= 1; j--) {
    const r = new Date(Date.UTC(annee, m, j));
    if (r.getUTCMonth() === m) return r;
  }
  return new Date(Date.UTC(annee, m, 1));
}

function prochaineEcheanceTriennale(dateInstallation, aujourdhui) {
  const inst = toDateOnly(dateInstallation);
  if (!inst || inst.getTime() > aujourdhui.getTime()) return null;
  let k = 3;
  for (;;) {
    const echeance = addMonthsUTC(inst, 12 * k);
    if (echeance.getTime() > aujourdhui.getTime()) return echeance;
    k += 3;
  }
}

function scoreBailPotentiel(dateInstallation, aujourdhui) {
  const echeance = prochaineEcheanceTriennale(dateInstallation, aujourdhui);
  if (!echeance) return [null, null];
  const mois = diffDaysUTC(echeance, aujourdhui) / 30.4375;
  return [Math.round(interpoler(COURBE_BAIL, mois) * 1000) / 1000, Math.round(mois * 10) / 10];
}

const SEUIL_EXPANSION = 0.15;
const SEUIL_CONTRACTION = -0.10;
const SEUIL_PERTE_MARGE = -0.05;
const SCORE_EXPANSION = 0.80;
const SCORE_EXPANSION_FORTE = 0.90;
const SCORE_CONTRACTION = 0.62;
const ANNEES_FINANCES_FRAICHES = 3;

const DIRECTION_LABEL = {
  expansion: "en expansion (CA en forte croissance)",
  contraction: "en contraction (CA en baisse ou pertes marquées)",
  stable: "stable (ni croissance ni baisse marquée)",
};

function nombre(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

function historiqueDepuisLigne(row) {
  const annee = nombre(row.annee_finances);
  const ca = nombre(row.chiffre_affaires);
  const resultat = nombre(row.resultat_net);
  const caPrecedent = nombre(row.chiffre_affaires_annee_precedente);
  const historique = [];
  if (annee !== null && (ca !== null || resultat !== null)) historique.push({ annee: Math.trunc(annee), ca, resultat });
  if (annee !== null && caPrecedent !== null) historique.push({ annee: Math.trunc(annee) - 1, ca: caPrecedent, resultat: null });
  return historique;
}

function analyserFinances(historique, aujourdhui) {
  const vide = { score: null, direction: null, croissanceCa: null, marge: null, annee: null, nbExercices: 0 };
  if (!historique.length) return vide;
  const dernier = historique[0];
  const precedent = historique.length > 1 && dernier.annee - historique[1].annee > 0 && dernier.annee - historique[1].annee <= 2
    ? historique[1] : null;
  let croissance = null;
  if (precedent && dernier.ca && precedent.ca && dernier.ca > 0 && precedent.ca > 0) {
    croissance = dernier.ca / precedent.ca - 1.0;
  }
  let marge = null;
  if (dernier.resultat !== null && dernier.ca && dernier.ca > 0) marge = dernier.resultat / dernier.ca;

  let direction, score;
  if (croissance !== null && croissance >= SEUIL_EXPANSION) {
    direction = "expansion";
    score = croissance >= 0.40 ? SCORE_EXPANSION_FORTE : SCORE_EXPANSION;
  } else if ((croissance !== null && croissance <= SEUIL_CONTRACTION) || (marge !== null && marge <= SEUIL_PERTE_MARGE)
    || (marge === null && dernier.resultat !== null && dernier.resultat < 0)) {
    direction = "contraction";
    score = SCORE_CONTRACTION;
  } else {
    direction = "stable";
    score = NEUTRE;
  }

  if (aujourdhui.getUTCFullYear() - dernier.annee > ANNEES_FINANCES_FRAICHES) {
    score = NEUTRE + (score - NEUTRE) * 0.5;
  }
  return {
    score: Math.round(score * 1000) / 1000, direction,
    croissanceCa: croissance === null ? null : Math.round(croissance * 10000) / 10000,
    marge: marge === null ? null : Math.round(marge * 10000) / 10000,
    annee: dernier.annee, nbExercices: historique.length,
  };
}

/** Équivalent de score_opportunite(). row : objet avec les mêmes champs que societes.json. */
export function scoreOpportunite(row, aujourdhui = new Date()) {
  if (String(row.statut_administratif || "") === "Cessé") {
    return { score: null, libelle: "Société cessée — non pertinent", detail: [], scoreFiabilite: 0, criteresDisponibles: 0, criteresTotaux: 2 };
  }
  const today = new Date(Date.UTC(aujourdhui.getUTCFullYear(), aujourdhui.getUTCMonth(), aujourdhui.getUTCDate()));
  const [sBail, mois] = scoreBailPotentiel(row.date_installation_siege, today);
  const fin = analyserFinances(historiqueDepuisLigne(row), today);

  const bailV = sBail === null ? NEUTRE : sBail;
  const finV = fin.score === null ? NEUTRE : fin.score;
  const potentiel = PONDERATIONS.bail * bailV + PONDERATIONS.finances * finV;
  const score = Math.round(potentiel * 100);

  const criteresDisponibles = (sBail === null ? 0 : 1) + (fin.score === null ? 0 : 1);
  const fiabilite = (sBail === null ? 0 : 1) + (fin.score === null ? 0 : (fin.nbExercices >= 2 ? 1 : 0.5));

  const detail = [];
  if (sBail !== null) {
    detail.push([
      `${Math.round(PONDERATIONS.bail * bailV * 100)} / ${Math.round(PONDERATIONS.bail * 100)}`,
      `Bail : échéance triennale estimée dans ${Math.round(mois)} mois (score ${sBail.toFixed(2)} sur 1)`,
    ]);
  } else {
    detail.push([
      `${Math.round(PONDERATIONS.bail * NEUTRE * 100)} / ${Math.round(PONDERATIONS.bail * 100)} (neutre)`,
      "Bail : date d'installation inconnue — composante neutre, pas de pénalité",
    ]);
  }
  if (fin.score !== null) {
    const croissanceTxt = fin.croissanceCa !== null ? ` (${fin.croissanceCa >= 0 ? "+" : ""}${(fin.croissanceCa * 100).toFixed(0)}% sur un an)` : "";
    const ancien = today.getUTCFullYear() - fin.annee > ANNEES_FINANCES_FRAICHES ? " — exercice ancien, effet réduit de moitié" : "";
    detail.push([
      `${Math.round(PONDERATIONS.finances * finV * 100)} / ${Math.round(PONDERATIONS.finances * 100)}`,
      `Finances : ${DIRECTION_LABEL[fin.direction]}${croissanceTxt}${ancien}`,
    ]);
  } else {
    detail.push([
      `${Math.round(PONDERATIONS.finances * NEUTRE * 100)} / ${Math.round(PONDERATIONS.finances * 100)} (neutre)`,
      "Finances : aucun chiffre d'affaires connu — composante neutre, pas de pénalité",
    ]);
  }

  let libelle;
  if (criteresDisponibles === 0) libelle = "Opportunité indéterminée (aucune donnée bail ni finances)";
  else if (score >= 65) libelle = "Opportunité forte";
  else if (score >= 45) libelle = "Opportunité moyenne";
  else libelle = "Opportunité faible";

  return { score, libelle, detail, scoreFiabilite: Math.round(fiabilite * 10) / 10, criteresDisponibles, criteresTotaux: 2 };
}

/** Calcule et ajoute les champs de bail/score à chaque société (comme scoring.appliquer()). */
export function appliquerScoring(societes, aujourdhui = new Date()) {
  return societes.map((s) => {
    const b = bail369(s.date_installation_siege || null, aujourdhui);
    const urgenceLibelle = LIBELLE_URGENCE[b.urgence369 ?? "null"] ?? STATUT_INCONNU;
    const det = scoreOpportunite(s, aujourdhui);
    return {
      ...s,
      prochaine_echeance_369: b.prochaineEcheance369,
      date_limite_preavis: b.dateLimitePreavis,
      jours_avant_limite: b.joursAvantLimite,
      urgence_369: b.urgence369,
      statut_bail: b.statutBail,
      verrouille: b.verrouille,
      urgence_libelle: urgenceLibelle,
      score_opportunite: det.score,
      score_libelle: det.libelle,
      score_fiabilite: det.scoreFiabilite,
      score_detail: det.detail,
      score_criteres_disponibles: det.criteresDisponibles,
      score_criteres_totaux: det.criteresTotaux,
    };
  });
}
