import { useState } from "react";
import { COULEUR_ZONE, ZONES } from "../lib/dataset";
import { pct } from "./ui";

// Port de charts.portefeuille() : une ligne par société, du pourcentage détenu par sa holding,
// coloré par zone, avec un repère à 50 % (contrôle).
export default function Lollipop({ lignes }) {
  const [survol, setSurvol] = useState(null);
  const d = [...lignes].sort((a, b) => (a.pourcentage_detention ?? 0) - (b.pourcentage_detention ?? 0));
  const hauteurLigne = 24;
  const hauteur = Math.max(260, hauteurLigne * d.length + 50);
  const margeGauche = 230;
  const largeurGraphe = 100; // % en largeur svg virtuelle, converti en px via viewBox

  return (
    <div style={{ position: "relative" }}>
      <svg viewBox={`0 0 760 ${hauteur}`} width="100%" height={hauteur} role="img" aria-label="Part du capital détenue par la holding">
        {d.map((r, i) => {
          const y = 18 + i * hauteurLigne;
          const x0 = margeGauche;
          const xMax = 740;
          const x1 = x0 + ((r.pourcentage_detention ?? 0) / 104) * (xMax - x0);
          const couleur = COULEUR_ZONE[r.zone] || "#8A94AA";
          return (
            <g key={r.cle || i} onMouseEnter={() => setSurvol(i)} onMouseLeave={() => setSurvol(null)}>
              <text x={margeGauche - 10} y={y + 4} fontSize="11" fill="var(--texte2)" textAnchor="end">
                {(r.nom || "").slice(0, 30)}
              </text>
              <line x1={x0} y1={y} x2={x1} y2={y} stroke="var(--grille-forte)" strokeWidth={1.5} />
              <circle cx={x1} cy={y} r={survol === i ? 6.5 : 5} fill={couleur} stroke="var(--fond)" strokeWidth={2} />
            </g>
          );
        })}
        {(() => {
          const x0 = margeGauche, xMax = 740;
          const x50 = x0 + (50 / 104) * (xMax - x0);
          return (
            <>
              <line x1={x50} y1={6} x2={x50} y2={hauteur - 26} stroke="var(--neon)" strokeDasharray="4 4" strokeWidth={1.3} />
              <text x={x50 + 6} y={14} fontSize="10.5" fill="var(--neon)">Plus de 50 % : contrôle par la holding</text>
            </>
          );
        })()}
      </svg>
      {survol !== null && (
        <div
          style={{
            position: "absolute", top: 18 + survol * (hauteurLigne * (100 / hauteur)) + "%", left: "32%",
            background: "var(--surface2)", border: "1px solid var(--ligne)", borderRadius: 8, padding: ".45rem .65rem",
            fontSize: ".8rem", color: "var(--texte)", pointerEvents: "none", maxWidth: 280, zIndex: 2,
          }}
        >
          <b>{d[survol].nom}</b><br />
          {pct(d[survol].pourcentage_detention)} du capital détenu par {d[survol].nom_detentrice}<br />
          {d[survol].niveau_lib} · {d[survol].pays || "—"}
        </div>
      )}
      <div className="pills" style={{ marginTop: ".4rem" }}>
        {ZONES.filter((z) => d.some((r) => r.zone === z)).map((z) => (
          <span key={z} className="pill active" style={{ borderColor: COULEUR_ZONE[z] }}>
            <span style={{ width: 8, height: 8, borderRadius: 999, background: COULEUR_ZONE[z], display: "inline-block", marginRight: 6 }} />
            {z}
          </span>
        ))}
      </div>
    </div>
  );
}
