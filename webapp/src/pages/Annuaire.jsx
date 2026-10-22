import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import ScoreHistogramme from "../components/ScoreHistogramme";
import { dateFr, montant, NoteSources, Titre, TitreGraphique } from "../components/ui";
import { telechargerCsv } from "../lib/csv";
import { useFiltres } from "../lib/FiltersContext";
import { meta } from "../lib/dataset";

// Colonnes centrées sur la prospection (21/10/2026, demande explicite) : fiabilité, niveau,
// détenue par, type, part détenue, part indirecte et NAF retirés ; raison sociale et date
// d'installation ajoutées. Mêmes colonnes et même ordre dans le tableau ET dans le CSV exporté —
// voir dashboard/vues/annuaire.py (c'est la même liste).
const COLONNES = [
  { cle: "nom", label: "Société", tri: (r) => r.nom },
  { cle: "score_opportunite", label: "Score d'opportunité", tri: (r) => r.score_opportunite ?? -1 },
  { cle: "adresse", label: "Adresse", tri: (r) => r.adresseAffichee },
  { cle: "date_installation_siege", label: "Date d'installation", tri: (r) => r.date_installation_siege || "" },
  { cle: "nom_legal", label: "Raison sociale", tri: (r) => r.nom_legal },
  { cle: "tranche_effectif", label: "Effectif", tri: (r) => r.tranche_effectif },
  { cle: "ca", label: "CA (dernier connu)", tri: (r) => r.ca ?? -Infinity },
  { cle: "resultat", label: "Résultat net (dernier connu)", tri: (r) => r.resultat ?? -Infinity },
  { cle: "identifiant", label: "SIREN / identifiant", tri: (r) => r.identifiant },
  { cle: "zone", label: "Zone", tri: (r) => r.zone },
  { cle: "forme_juridique", label: "Forme juridique", tri: (r) => r.forme_juridique },
  { cle: "statut_administratif", label: "Statut", tri: (r) => r.statut_administratif },
  { cle: "date_creation", label: "Création", tri: (r) => r.date_creation },
  { cle: "etat_web", label: "Cession (source web)", tri: (r) => r.etat_web },
];

function adresseComplete(r) {
  // Code postal + ville déjà présents dans l'adresse pour les niveaux 1-3 ; ajoutés seulement
  // quand ils manquent, pour le catalogue (jamais répétés) — voir dashboard/vues/annuaire.py.
  if (!r.code_postal || (r.adresse || "").includes(r.code_postal)) return r.adresse || "";
  if (r.adresse) return `${r.adresse}, ${r.code_postal} ${r.ville || ""}`.trim();
  return `${r.code_postal} ${r.ville || ""}`.trim();
}

export default function Annuaire() {
  const { filtre, toutes } = useFiltres();
  const navigate = useNavigate();
  const [tri, setTri] = useState({ cle: "score_opportunite", desc: true });

  const lignes = useMemo(() => {
    return filtre.map((r) => ({
      ...r,
      adresseAffichee: adresseComplete(r),
      nomDetentriceTitre: (r.nom_detentrice || "").replace(/\w\S*/g, (w) => w[0].toUpperCase() + w.slice(1).toLowerCase()).replace("Lh ", "LH "),
      ca: r.chiffre_affaires ?? r.chiffre_affaires_estime_bilan ?? null,
      resultat: r.resultat_net ?? r.resultat_net_estime_bilan ?? null,
    }));
  }, [filtre]);

  const trie = useMemo(() => {
    const col = COLONNES.find((c) => c.cle === tri.cle);
    const copie = [...lignes];
    copie.sort((a, b) => {
      const va = col.tri(a), vb = col.tri(b);
      if (va === vb) return 0;
      const r = va < vb ? -1 : 1;
      return tri.desc ? -r : r;
    });
    return copie;
  }, [lignes, tri]);

  function basculerTri(cle) {
    setTri((t) => (t.cle === cle ? { cle, desc: !t.desc } : { cle, desc: true }));
  }

  function exporter() {
    telechargerCsv("societes_selection.csv", COLONNES.map((c) => ({
      label: c.label,
      value: (r) => {
        if (c.cle === "ca") return r.ca === null ? "" : montant(r.ca);
        if (c.cle === "resultat") return r.resultat === null ? "" : montant(r.resultat);
        if (c.cle === "date_installation_siege") return dateFr(r.date_installation_siege);
        if (c.cle === "adresse") return r.adresseAffichee;
        return r[c.cle] ?? "";
      },
    })), trie);
  }

  const scores = useMemo(() => filtre.map((r) => r.score_opportunite).filter((s) => s !== null && s !== undefined), [filtre]);

  return (
    <>
      <Titre
        texte={`L'annuaire des ${filtre.length} sociétés`}
        chapo="Triée par score d'opportunité par défaut — clique une colonne pour trier autrement. Cherche et filtre dans la colonne de gauche, ou sélectionne une ligne pour ouvrir sa fiche."
      />

      {scores.length > 0 && (
        <>
          <TitreGraphique titre={`Répartition du score sur les ${scores.length} société(s) notée(s)`} sousTitre="Rouge = opportunité forte (≥ 65), orange = moyenne (45 à 64), gris = faible ou neutre." />
          <ScoreHistogramme scores={scores} />
        </>
      )}

      <div style={{ display: "flex", gap: "1rem", alignItems: "center", margin: "1.4rem 0 .6rem" }}>
        <button className="btn" onClick={exporter}>Télécharger la sélection (CSV)</button>
        <span className="sidebar-caption" style={{ margin: 0 }}>Mêmes colonnes et même ordre que le tableau ci-dessous.</span>
      </div>

      <div className="table-wrap" style={{ maxHeight: 720, overflow: "auto" }}>
        <table className="tbl">
          <thead>
            <tr>
              {COLONNES.map((c) => (
                <th key={c.cle} onClick={() => basculerTri(c.cle)}>
                  {c.label}
                  {tri.cle === c.cle ? <span className="fleche">{tri.desc ? "▼" : "▲"}</span> : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trie.map((r) => (
              <tr key={r.cle} onClick={() => navigate(`/fiche?cle=${encodeURIComponent(r.cle)}`)}>
                <td>{r.nom}</td>
                <td>
                  {r.score_opportunite === null || r.score_opportunite === undefined ? "—" : (
                    <div className="progress-cell">
                      <div className="bar"><span style={{ width: `${r.score_opportunite}%`, background: r.score_opportunite >= 65 ? "var(--couleur-alerte)" : r.score_opportunite >= 45 ? "#C98500" : "var(--texte3)" }} /></div>
                      <span className="num">{r.score_opportunite}</span>
                    </div>
                  )}
                </td>
                <td>{r.adresseAffichee || "—"}</td>
                <td>{dateFr(r.date_installation_siege)}</td>
                <td>{r.nom_legal || "—"}</td>
                <td>{r.tranche_effectif || "—"}</td>
                <td className="num">{r.ca === null ? "—" : montant(r.ca)}</td>
                <td className="num">{r.resultat === null ? "—" : montant(r.resultat)}</td>
                <td>{r.identifiant || "—"}</td>
                <td>{r.zone}</td>
                <td>{r.forme_juridique || "—"}</td>
                <td>{r.statut_administratif || "—"}</td>
                <td>{dateFr(r.date_creation)}</td>
                <td>{r.etat_web || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <NoteSources dateCollecte={meta.date_collecte_max} niveauMax={Math.max(1, ...toutes.map((r) => r.niveau))} />
    </>
  );
}
