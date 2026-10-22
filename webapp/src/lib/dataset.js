// Chargement des données exportées par export_webapp_data.py (voir ce script à la racine du
// dépôt). Contrairement au scoring (scoring.js), ces données sont figées à l'export : pour les
// rafraîchir (nouvelle collecte, nouvel enrichissement), relancer le script puis republier.
import catalogueBrut from "../data/catalogue.json";
import evenementsBrut from "../data/evenements.json";
import liensBrut from "../data/liens.json";
import mereBrut from "../data/mere.json";
import metaBrut from "../data/meta.json";
import societesBrut from "../data/societes.json";

export const meta = metaBrut;
export const mere = mereBrut;
export const liens = liensBrut;
export const catalogueRaw = catalogueBrut;

function normaliser(texte) {
  return (texte || "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}
export { normaliser };

// Événements web (cessions) par société : même rapprochement par mot-clé que data.evenements_de().
const evenementsParMot = evenementsBrut.map((e) => ({
  ...e,
  mots: (e.cles || "").split("|").map((c) => c.trim()).filter(Boolean),
}));

export function evenementsDe(nom) {
  const n = ` ${normaliser(nom)} `;
  return evenementsParMot
    .filter((e) => e.mots.some((m) => n.includes(` ${m} `)))
    .sort((a, b) => (a.date < b.date ? 1 : -1));
}

// "toutes" : même ensemble que data.donnees() (niveaux 1+ et catalogue, jamais Eurazeo niveau 0).
// etat_web est déjà calculé côté Python (première ligne d'evenements_de), repris tel quel.
export const toutes = societesBrut;

export const ORDRE_EFFECTIF = ["0 salarié", "Non employeuse / inconnu", "1 à 9", "10 à 49", "50 à 249", "250 et plus"];
export const NON_RENSEIGNE = "Non renseigné";

export const ZONE_PARIS = "Paris";
export const ZONE_FRANCE = "France (hors Paris)";
export const ZONE_ETRANGER = "Étranger";
export const ZONE_NON_LOCALISEE = "Non localisée";
export const ZONES = [ZONE_PARIS, ZONE_FRANCE, ZONE_ETRANGER, ZONE_NON_LOCALISEE];
export const COULEUR_ZONE = {
  [ZONE_PARIS]: "#0AA3C2",
  [ZONE_FRANCE]: "#8577EA",
  [ZONE_ETRANGER]: "#C98500",
  [ZONE_NON_LOCALISEE]: "#8A94AA",
};
