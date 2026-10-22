import { useMemo, useState } from "react";
import { COULEUR_ZONE, ZONE_PARIS, ZONES } from "../lib/dataset";
import { arrondissementParis, libelleArrondissement } from "../lib/geo";

const COULEUR_INCONNU = "var(--texte3)";

// Dès que le filtre de zone (colonne de gauche) ne laisse plus que "Paris", la répartition par
// zone n'a plus rien à montrer (un seul bâton) : on bascule automatiquement sur le détail par
// arrondissement, dérivé du code postal (demande du 22/10/2026).
export function filtreEstParisSeul(lignes) {
  return lignes.length > 0 && lignes.every((r) => r.zone === ZONE_PARIS);
}

function categoriesParZone(lignes) {
  const total = lignes.length;
  return ZONES.filter((z) => lignes.some((r) => r.zone === z)).map((z) => ({
    cle: z,
    label: z,
    n: lignes.reduce((acc, r) => acc + (r.zone === z ? 1 : 0), 0),
    total,
    couleur: COULEUR_ZONE[z] || "#8A94AA",
    inconnu: false,
  }));
}

function categoriesParArrondissement(lignes) {
  const total = lignes.length;
  const comptes = new Map();
  let inconnu = 0;
  for (const r of lignes) {
    const n = arrondissementParis(r.code_postal);
    if (n === null) inconnu += 1;
    else comptes.set(n, (comptes.get(n) || 0) + 1);
  }
  const rangees = [...comptes.entries()]
    .map(([n, c]) => ({ cle: `arr-${n}`, label: libelleArrondissement(n), n: c, total, couleur: COULEUR_ZONE[ZONE_PARIS], inconnu: false }))
    .sort((a, b) => b.n - a.n);
  if (inconnu > 0) {
    rangees.push({ cle: "arr-inconnu", label: "Arrondissement inconnu", n: inconnu, total, couleur: COULEUR_INCONNU, inconnu: true });
  }
  return rangees;
}

export default function ZoneChart({ lignes }) {
  const [survol, setSurvol] = useState(null);
  const parArrondissement = filtreEstParisSeul(lignes);
  const categories = useMemo(
    () => (parArrondissement ? categoriesParArrondissement(lignes) : categoriesParZone(lignes)),
    [lignes, parArrondissement]
  );

  const max = Math.max(1, ...categories.map((c) => c.n));
  const margeGauche = 196;
  const xMax = 740;
  const hauteurLigne = parArrondissement ? 28 : 40;
  const hauteur = 16 + Math.max(1, categories.length) * hauteurLigne + 8;

  if (categories.length === 0) {
    return <p className="sidebar-caption">Aucune société géolocalisée dans la sélection actuelle.</p>;
  }

  return (
    <div style={{ position: "relative" }}>
      <svg viewBox={`0 0 760 ${hauteur}`} width="100%" height={hauteur} role="img" aria-label="Nombre de sociétés par zone géographique">
        {categories.map((c, i) => {
          const y = 8 + i * hauteurLigne;
          const hBarre = hauteurLigne - (parArrondissement ? 10 : 14);
          const largeur = (c.n / max) * (xMax - margeGauche);
          return (
            <g key={c.cle} onMouseEnter={() => setSurvol(i)} onMouseLeave={() => setSurvol(null)} style={{ cursor: "default" }}>
              <text x={margeGauche - 10} y={y + hBarre / 2 + 4} fontSize="12" fill="var(--texte2)" textAnchor="end">
                {c.label}
              </text>
              <rect x={margeGauche} y={y} width={xMax - margeGauche} height={hBarre} rx={4} fill="rgba(150,170,210,0.08)" />
              <rect
                x={margeGauche}
                y={y}
                width={Math.max(largeur, c.n > 0 ? 3 : 0)}
                height={hBarre}
                rx={4}
                fill={c.couleur}
                opacity={survol === i ? 1 : c.inconnu ? 0.6 : 0.92}
              />
              <text x={margeGauche + Math.max(largeur, c.n > 0 ? 3 : 0) + 8} y={y + hBarre / 2 + 4} fontSize="12" fontWeight={survol === i ? 700 : 400} fill="var(--texte)">
                {c.n}
              </text>
            </g>
          );
        })}
      </svg>
      {survol !== null && (
        <div
          style={{
            position: "absolute",
            top: 8 + survol * hauteurLigne,
            left: "27%",
            background: "var(--surface2)",
            border: "1px solid var(--ligne)",
            borderRadius: 8,
            padding: ".4rem .6rem",
            fontSize: ".8rem",
            color: "var(--texte)",
            pointerEvents: "none",
            whiteSpace: "nowrap",
            zIndex: 2,
          }}
        >
          <b>{categories[survol].n}</b> société(s){categories[survol].total ? ` · ${((categories[survol].n / categories[survol].total) * 100).toFixed(0)}% de la sélection` : ""}
          {categories[survol].inconnu ? <><br />Code postal absent ou hors Paris intra-muros</> : null}
        </div>
      )}
    </div>
  );
}
