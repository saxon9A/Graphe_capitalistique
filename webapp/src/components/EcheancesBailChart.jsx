import { useMemo, useState } from "react";
import { LIBELLE_URGENCE, ORDRE_URGENCE_LIBELLES } from "../lib/scoring";

// Remplace l'ancien histogramme de score (jugé peu pertinent, 22/10/2026) : ce qui compte pour la
// prospection n'est pas le score en lui-même mais QUAND la société redevient mobilisable sur son
// bail. Un bâton par catégorie d'urgence (urgence_libelle, déjà calculée par scoring.js et déjà
// utilisée comme filtre dans la colonne de gauche — mêmes libellés, même ordre).
const COULEUR_URGENCE = {
  "Préavis ouvert": "var(--couleur-alerte)", // <= 90 jours avant la limite : rouge, comme le score
  "Échéance < 1 an": "#C98500", // orange, comme le score
  "Échéance 1 à 2 ans": "#C9A857", // ambre : encore une vraie étape, pas encore sans urgence
  "Échéance > 2 ans": "var(--texte3)", // gris neutre : rien à faire dans l'immédiat
};
const COULEUR_INCONNUE = "var(--texte3)"; // même gris que "> 2 ans", mais rendu en hachures : on ne
// sait pas si c'est sans urgence ou juste sans date d'installation connue — à ne jamais confondre.

export default function EcheancesBailChart({ lignes }) {
  const [survol, setSurvol] = useState(null);

  const categories = useMemo(() => {
    const total = lignes.length;
    return ORDRE_URGENCE_LIBELLES.map((label) => ({
      label,
      n: lignes.reduce((acc, r) => acc + (r.urgence_libelle === label ? 1 : 0), 0),
      total,
      inconnue: label === LIBELLE_URGENCE.null,
    }));
  }, [lignes]);

  const max = Math.max(1, ...categories.map((c) => c.n));
  const margeGauche = 196;
  const xMax = 740;
  const hauteurLigne = 40;
  const hauteur = 16 + categories.length * hauteurLigne + 8;

  return (
    <div style={{ position: "relative" }}>
      <svg viewBox={`0 0 760 ${hauteur}`} width="100%" height={hauteur} role="img" aria-label="Nombre de sociétés par échéance de bail">
        <defs>
          <pattern id="hachure-inconnue" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
            <rect width="6" height="6" fill={COULEUR_INCONNUE} opacity="0.22" />
            <line x1="0" y1="0" x2="0" y2="6" stroke={COULEUR_INCONNUE} strokeWidth="3" />
          </pattern>
        </defs>
        {categories.map((c, i) => {
          const y = 8 + i * hauteurLigne;
          const hBarre = hauteurLigne - 14;
          const largeur = (c.n / max) * (xMax - margeGauche);
          const couleur = c.inconnue ? "url(#hachure-inconnue)" : COULEUR_URGENCE[c.label];
          return (
            <g key={c.label} onMouseEnter={() => setSurvol(i)} onMouseLeave={() => setSurvol(null)} style={{ cursor: "default" }}>
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
                fill={couleur}
                opacity={survol === i ? 1 : 0.92}
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
          {categories[survol].inconnue ? <><br />Date d'installation au siège actuel inconnue</> : null}
        </div>
      )}
    </div>
  );
}
