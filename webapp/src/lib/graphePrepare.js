// Port JS de dashboard/lib/graphe.py (preparer + preparer_catalogue) : construit l'objet `D`
// consommé par la page graphe.html existante (dashboard/assets/graphe.html + vis-network.min.js,
// servis tels quels depuis /graphe-assets/ — voir Graphe.jsx). Zéro réécriture de la logique
// d'affichage vis-network : seule la préparation des données est portée ici, pour que les filtres
// de la colonne de gauche (toujours en JS, côté client) se répercutent sur le graphe.
import { COULEUR_ZONE, normaliser, ZONES } from "./dataset";

export const RACINE = "EURAZEO";
// Même liste que graphe.py (légèrement différente de celle de data.py, volontairement reprise à
// l'identique : seule distingue "holding" (carré) vs "société" (rond) dans ce graphe précis).
const HOLDING_NAF = new Set(["64.20Z", "64.30Z", "66.30Z", "70.10Z"]);

function fmtPct(p) {
  if (p === null || p === undefined || Number.isNaN(p)) return "part non publiée";
  return `${(Math.round(p * 100) / 100).toString().replace(".", ",")} %`;
}

function identifiant(r) {
  if (r.identifiant) return r.identifiant;
  return "n:" + normaliser(r.nom).replace(/[^a-z0-9]/g, "");
}

function nature(naf) {
  if (!naf) return "inconnue";
  return HOLDING_NAF.has(naf) ? "holding" : "societe";
}

/** toutes/filtre : sociétés niveau 1+ (jamais le catalogue, exclu comme en Python). */
export function preparer(toutes, filtre, mere, liens, evenementsDe) {
  toutes = toutes.filter((r) => r.niveau !== -1);
  filtre = filtre.filter((r) => r.niveau !== -1);
  const t = toutes.map((r) => ({ ...r, id: identifiant(r), parent: r.niveau === 1 ? RACINE : r.siren_detentrice }));
  const idsFiltre = new Set(filtre.map(identifiant));

  const aretes = [];
  const vus = new Set();
  for (const r of t) {
    const cle = `${r.parent}>${r.id}`;
    if (r.parent && !vus.has(cle) && r.parent !== r.id) {
      vus.add(cle);
      aretes.push({ from: r.parent, to: r.id, pct: r.pourcentage_detention ?? null, interne: false });
    }
  }
  const idsTous = new Set([...t.map((r) => r.id), RACINE]);
  for (const l of liens) {
    const cle = `${l.siren_detentrice}>${l.siren_detenue}`;
    if (!vus.has(cle) && idsTous.has(l.siren_detentrice) && idsTous.has(l.siren_detenue) && l.siren_detentrice !== l.siren_detenue) {
      vus.add(cle);
      aretes.push({ from: l.siren_detentrice, to: l.siren_detenue, pct: l.pourcentage_detention ?? null, interne: true });
    }
  }
  const aretesValides = aretes.filter((a) => idsTous.has(a.from));

  const parents = new Map();
  for (const a of aretesValides) {
    if (!parents.has(a.to)) parents.set(a.to, []);
    parents.get(a.to).push(a.from);
  }
  const garder = new Set(idsFiltre);
  const pile = [...idsFiltre];
  while (pile.length) {
    const id = pile.pop();
    for (const p of parents.get(id) || []) {
      if (!garder.has(p)) { garder.add(p); pile.push(p); }
    }
  }
  garder.add(RACINE);

  const noeuds = [];
  let nomMere = mere ? mere.nom : "Eurazeo";
  if (nomMere === nomMere.toUpperCase()) nomMere = nomMere.charAt(0) + nomMere.slice(1).toLowerCase();
  noeuds.push({
    id: RACINE, nom: nomMere, zone: mere ? mere.zone : "Paris", niveau: 0, match: true, nature: "societe",
    econ: "", etat_web: "", web: [], lignes: [["Adresse du siège", mere && mere.adresse ? mere.adresse : ""]].filter((l) => l[1]),
    titre: `${nomMere}\nSociété mère`, siren: mere ? mere.siren : "",
  });

  const parId = new Map();
  for (const r of t) {
    if (!parId.has(r.id)) parId.set(r.id, []);
    parId.get(r.id).push(r);
  }
  for (const [id, groupe] of parId) {
    if (!garder.has(id)) continue;
    const r = [...groupe].sort((a, b) => a.niveau - b.niveau)[0];
    let econ = "";
    if (r.niveau >= 2) {
      const vals = groupe.map((g) => g.part_economique_eurazeo).filter((v) => v !== null && v !== undefined);
      if (vals.length) {
        econ = fmtPct(vals.reduce((s, v) => s + v, 0));
        if (vals.length > 1) econ += ` (somme de ${vals.length} chemins connus)`;
      }
    }
    const lignes = [
      ["Adresse du siège", r.adresse], ["Activité", [r.naf_code, r.naf_libelle].filter(Boolean).join(" · ")],
      ["Effectif salarié", r.tranche_effectif], ["Statut", r.statut_administratif],
    ];
    if (r.niveau >= 2) lignes.push(["Identification", r.verification]);
    const web = (evenementsDe ? evenementsDe(r.nom) : []).map((e) => ({ etat: e.etat, date: e.date, evenement: e.evenement, source: e.source, url: e.url }));
    noeuds.push({
      id, nom: r.nom, zone: r.zone, niveau: r.niveau, match: idsFiltre.has(id), nature: nature(r.naf_code), econ,
      etat_web: web.length ? web[0].etat : "", web,
      lignes: lignes.filter((l) => l[1]), siren: r.siren,
      titre: `${r.nom}\n${r.zone} · niveau ${r.niveau}` + (r.adresse ? `\n${r.adresse}` : ""),
    });
  }
  const envoyes = new Set(noeuds.map((n) => n.id));
  const aretesFinales = aretesValides.filter((a) => envoyes.has(a.from) && envoyes.has(a.to));
  return {
    racine: RACINE, nodes: noeuds, edges: aretesFinales,
    zones: ZONES.filter((z) => noeuds.some((n) => n.zone === z && n.match && n.id !== RACINE)).map((z) => ({ nom: z, couleur: COULEUR_ZONE[z] })),
    niveaux: [...new Set(noeuds.filter((n) => n.match && n.niveau >= 1).map((n) => n.niveau))].sort((a, b) => a - b),
    couleurs: COULEUR_ZONE,
  };
}

function idCatalogue(nom) {
  return "cat:" + normaliser(nom).replace(/[^a-z0-9]/g, "");
}

/** toutesSansCatalogue : sociétés niveau 1+ (jamais le catalogue). catalogueBrut : catalogue.json. */
export function preparerCatalogue(toutesSansCatalogue, catalogueBrut) {
  if (!catalogueBrut.length) return { nodes: [], edges: [], total: 0, deja: 0 };
  const parSiren = new Map();
  const parNom = new Map();
  for (const r of toutesSansCatalogue) {
    if (r.siren) parSiren.set(r.siren, r.nom);
    parNom.set(normaliser(r.nom), r.nom);
  }
  function trouver(row) {
    if (row.siren && parSiren.has(row.siren)) return parSiren.get(row.siren);
    return parNom.get(normaliser(row.nom)) || "";
  }
  const deja = catalogueBrut.filter((r) => trouver(r) !== "").length;
  const absents = catalogueBrut.filter((r) => trouver(r) === "");

  const noeuds = [];
  const aretes = [];
  for (const r of absents) {
    const id = idCatalogue(r.nom);
    const lignes = [
      ["Stratégie / description", r.description], ["Secteur", r.secteur],
      ["Zone géographique (site)", r.region], ["Date d'investissement", r.date_investissement],
      ["Statut (site)", r.statut],
    ];
    if (r.siren) lignes.push(["SIREN rapproché par le nom (⚠ à vérifier)", `${r.siren}` + (r.adresse ? ` — ${r.adresse}, ${r.commune}` : "")]);
    noeuds.push({
      id, nom: r.nom, zone: "", niveau: -1, match: true, nature: "catalogue",
      econ: "", etat_web: (r.statut || "").toLowerCase() === "cédée" ? "cédée" : "", web: [],
      lignes: lignes.filter((l) => l[1]), siren: "", site_web: r.site_web,
      titre: `${r.nom}\nCatalogue eurazeo.com · lien non vérifié`,
    });
    aretes.push({ from: RACINE, to: id, pct: null, interne: false, catalogue: true });
  }
  return { nodes: noeuds, edges: aretes, total: catalogueBrut.length, deja };
}
