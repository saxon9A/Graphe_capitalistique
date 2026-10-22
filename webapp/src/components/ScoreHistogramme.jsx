import { useMemo, useState } from "react";

// Port de charts.score_histogramme() : un bâton par tranche de 5 points (0-100), coloré selon les
// mêmes seuils que scoring.score_opportunite (faible <45, moyenne 45-64, forte ≥65).
export default function ScoreHistogramme({ scores, hauteur = 180 }) {
  const [survol, setSurvol] = useState(null);
  const bornes = useMemo(() => Array.from({ length: 21 }, (_, i) => i * 5), []);
  const comptes = useMemo(() => {
    const c = new Array(20).fill(0);
    for (const s of scores) {
      if (s === null || s === undefined) continue;
      const i = Math.min(19, Math.max(0, Math.floor(s / 5)));
      c[i] += 1;
    }
    return c;
  }, [scores]);
  const max = Math.max(1, ...comptes);
  const largeurBarre = 100 / 20;

  function couleur(centre) {
    if (centre >= 65) return "var(--couleur-alerte)";
    if (centre >= 45) return "#C98500";
    return "var(--texte3)";
  }

  return (
    <div style={{ position: "relative", height: hauteur }}>
      <svg viewBox={`0 0 100 ${hauteur}`} preserveAspectRatio="none" width="100%" height={hauteur} role="img" aria-label="Histogramme du score d'opportunité">
        {comptes.map((c, i) => {
          const centre = bornes[i] + 2.5;
          const h = (c / max) * (hauteur - 18);
          return (
            <rect
              key={i}
              x={i * largeurBarre + largeurBarre * 0.12}
              y={hauteur - 18 - h}
              width={largeurBarre * 0.76}
              height={h}
              rx={1.4}
              fill={couleur(centre)}
              opacity={survol === i ? 1 : 0.9}
              onMouseEnter={() => setSurvol(i)}
              onMouseLeave={() => setSurvol(null)}
            />
          );
        })}
        <line x1={0} y1={hauteur - 18} x2={100} y2={hauteur - 18} stroke="var(--grille-forte)" strokeWidth={0.4} />
        {[0, 20, 40, 60, 80, 100].map((v) => (
          <text key={v} x={(v / 100) * 100} y={hauteur - 4} fontSize="5.4" fill="var(--texte2)" textAnchor="middle">{v}</text>
        ))}
      </svg>
      {survol !== null && (
        <div
          style={{
            position: "absolute", top: 4, left: `${survol * largeurBarre}%`, transform: "translateX(-20%)",
            background: "var(--surface2)", border: "1px solid var(--ligne)", borderRadius: 8, padding: ".3rem .55rem",
            fontSize: ".78rem", color: "var(--texte)", pointerEvents: "none", whiteSpace: "nowrap",
          }}
        >
          score {bornes[survol]}–{bornes[survol] + 5} · <b>{comptes[survol]}</b> société(s)
        </div>
      )}
    </div>
  );
}
