import { useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import { useNavigate } from "react-router-dom";
import { NoteSources, Titre, TitreGraphique } from "../components/ui";
import { COULEUR_ZONE, meta, ZONE_ETRANGER, ZONES } from "../lib/dataset";
import { useFiltres } from "../lib/FiltersContext";

const VUES_CARTE = {
  Monde: { center: [38.0, -30.0], zoom: 2 },
  "Monde proche": { center: [49.0, 3.0], zoom: 4 },
  Europe: { center: [50.0, 4.0], zoom: 5 },
  Paris: { center: [48.866, 2.322], zoom: 12 },
};

function regrouperAdresses(df) {
  const groupes = new Map();
  for (const r of df) {
    if (r.latitude == null || r.longitude == null) continue;
    const latR = Math.round(r.latitude * 10000) / 10000;
    const lonR = Math.round(r.longitude * 10000) / 10000;
    const cle = `${latR}|${lonR}|${r.zone}`;
    if (!groupes.has(cle)) groupes.set(cle, { latR, lonR, zone: r.zone, adresse: r.adresse, ville: r.ville, precision: r.geo_precision, lignes: [] });
    groupes.get(cle).lignes.push(r);
  }
  return [...groupes.values()].sort((a, b) => b.lignes.length - a.lignes.length);
}

function RecadrerCarte({ vue }) {
  const map = useMap();
  const v = VUES_CARTE[vue];
  map.setView(v.center, v.zoom, { animate: true });
  return null;
}

export default function Carte() {
  const { filtre, toutes } = useFiltres();
  const navigate = useNavigate();
  const groupes = useMemo(() => regrouperAdresses(filtre), [filtre]);
  const etr = filtre.filter((r) => r.zone === ZONE_ETRANGER);
  const defaut = etr.length ? (etr.some((r) => r.longitude < -20) ? "Monde" : "Europe") : "Paris";
  const [vue, setVue] = useState(defaut);
  const [selection, setSelection] = useState(null);

  const titre = groupes.length && groupes[0].lignes.length > 1
    ? `${groupes[0].lignes.length} sociétés partagent la même adresse : ${(groupes[0].adresse || "").toLowerCase().replace(/\w\S*/g, (w) => w[0].toUpperCase() + w.slice(1))}`
    : "Chaque société a une adresse de siège distincte";

  const societes = selection ? groupes.find((g) => g === selection)?.lignes.sort((a, b) => (b.score_opportunite ?? -1) - (a.score_opportunite ?? -1)) || [] : [];

  const tab = useMemo(() => {
    const m = new Map();
    for (const r of filtre) {
      const cle = r.latitude != null ? `${Math.round(r.latitude * 10000) / 10000}|${Math.round(r.longitude * 10000) / 10000}` : r.adresse;
      if (!m.has(cle)) m.set(cle, { zone: r.zone, adresse: r.adresse, noms: [] });
      m.get(cle).noms.push(r.nom);
    }
    return [...m.values()]
      .map((g) => ({ ...g, n: g.noms.length, liste: g.noms.slice(0, 6).join(", ") + (g.noms.length > 6 ? " …" : "") }))
      .sort((a, b) => b.n - a.n);
  }, [filtre]);

  return (
    <>
      <Titre texte={titre} chapo="Chaque disque est une adresse de siège ; sa taille grandit avec le nombre de sociétés domiciliées au même endroit. Survole un disque pour voir les sociétés." />

      <div className="pills">
        {Object.keys(VUES_CARTE).map((v) => (
          <span key={v} className={`pill${vue === v ? " active" : ""}`} onClick={() => setVue(v)}>{v}</span>
        ))}
      </div>

      <div style={{ borderRadius: 14, overflow: "hidden", border: "1px solid var(--ligne)", marginBottom: "1rem" }}>
        <MapContainer center={VUES_CARTE[vue].center} zoom={VUES_CARTE[vue].zoom} style={{ height: 560, background: "var(--fond)" }} worldCopyJump>
          <RecadrerCarte vue={vue} />
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_matter/{z}/{x}/{y}{r}.png" attribution='&copy; <a href="https://carto.com/">CARTO</a>' />
          {ZONES.map((z) => groupes.filter((g) => g.zone === z).map((g, i) => (
            <CircleMarker
              key={`${z}-${i}`}
              center={[g.latR, g.lonR]}
              radius={Math.min(26, Math.max(8, 8 + 2.4 * Math.sqrt(g.lignes.length)))}
              pathOptions={{ color: COULEUR_ZONE[z], fillColor: COULEUR_ZONE[z], fillOpacity: 0.82, weight: 1 }}
              eventHandlers={{ click: () => setSelection(g) }}
            >
              <Tooltip>
                <b>{g.adresse || "—"}</b><br />
                {g.lignes.length} société(s) · {g.precision === "ville" ? "position approximative" : "adresse exacte"}<br />
                {g.lignes.slice(0, 8).map((r) => r.nom).join(", ")}{g.lignes.length > 8 ? " …" : ""}
              </Tooltip>
            </CircleMarker>
          )))}
        </MapContainer>
      </div>

      {societes.length > 0 ? (
        <>
          <TitreGraphique titre={`${societes.length} société${societes.length > 1 ? "s" : ""} à cette adresse`} sousTitre="Clique « Voir la fiche complète » pour le détail (bail, score, dirigeants...) d'une société." />
          {societes.map((r) => (
            <div key={r.cle} style={{ display: "flex", alignItems: "center", gap: "1rem", padding: ".55rem 0", borderBottom: "1px solid var(--ligne)" }}>
              <div style={{ flex: "2.2 1 0" }}>
                <b>{r.nom}</b>
                <div className="sidebar-caption" style={{ margin: 0 }}>{r.niveau_lib}{r.identifiant ? ` · ${r.identifiant}` : ""}</div>
              </div>
              <div style={{ flex: "2 1 0" }}>
                {r.score_opportunite != null ? <>Score <b>{r.score_opportunite}</b> — {r.urgence_libelle}</> : <span className="sidebar-caption" style={{ margin: 0 }}>{r.urgence_libelle || "—"}</span>}
              </div>
              <button className="btn small" style={{ flex: "1.1 1 0" }} onClick={() => navigate(`/fiche?cle=${encodeURIComponent(r.cle)}`)}>Voir la fiche complète</button>
            </div>
          ))}
        </>
      ) : (
        <p className="sidebar-caption">Clique sur un point pour voir les sociétés à cette adresse, directement ici.</p>
      )}

      <TitreGraphique titre="Les adresses, une par une" sousTitre="Les sociétés étrangères sont placées au centre-ville : leur position sur la carte est approximative, pas leur adresse, qui est celle imprimée dans le document de référence." />
      <div className="table-wrap">
        <table className="tbl">
          <thead><tr><th>Zone</th><th>Adresse</th><th>Sociétés</th><th>Liste</th></tr></thead>
          <tbody>
            {tab.map((g, i) => (
              <tr key={i}><td>{g.zone}</td><td>{g.adresse || "—"}</td><td className="num">{g.n}</td><td>{g.liste}</td></tr>
            ))}
          </tbody>
        </table>
      </div>

      <NoteSources dateCollecte={meta.date_collecte_max} niveauMax={Math.max(1, ...toutes.map((r) => r.niveau))} />
    </>
  );
}
