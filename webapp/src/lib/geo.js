// Découpage par arrondissement parisien à partir du code postal (750XX -> XXe ; 75116 -> 16e,
// variante historique encore parfois utilisée pour le 16e). Retourne null si le code postal n'est
// pas un arrondissement parisien reconnu (donnée manquante ou hors Paris).
export function arrondissementParis(codePostal) {
  if (!codePostal) return null;
  const cp = String(codePostal).trim();
  if (cp === "75116") return 16;
  const m = /^750(\d{2})$/.exec(cp);
  if (!m) return null;
  const n = Number(m[1]);
  if (n >= 1 && n <= 20) return n;
  return null;
}

export function libelleArrondissement(n) {
  return n === 1 ? "1er arrondissement" : `${n}e arrondissement`;
}
