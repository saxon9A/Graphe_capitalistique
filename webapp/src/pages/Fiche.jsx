import { useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { CircleMarker, MapContainer, TileLayer } from "react-leaflet";
import { Bloc, Constat, dateFr, montant, Note, Pastille, pct, Titre, TitreGraphique, v } from "../components/ui";
import { telechargerCsv } from "../lib/csv";
import { COULEUR_ZONE, evenementsDe } from "../lib/dataset";
import { useFiltres } from "../lib/FiltersContext";

const COULEUR_URGENCE = { 3: "var(--couleur-alerte)", 2: "#C98500", 1: "var(--texte2)", 0: "var(--texte2)" };
const STATUT_INCONNU = "Échéance inconnue";

// Clé CARTO : voir Carte.jsx (même note, exigée depuis le 25/09/2026).
const CARTO_KEY = import.meta.env.VITE_CARTO_API_KEY || "";

function MiniCarte({ lat, lon, couleur, zoom }) {
  return (
    <MapContainer center={[lat, lon]} zoom={zoom} style={{ height: 260, borderRadius: 14 }} zoomControl={false} attributionControl={false}>
      <TileLayer
        url={`https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png?key=${CARTO_KEY}`}
        subdomains="abcd"
      />
      <CircleMarker center={[lat, lon]} radius={9} pathOptions={{ color: couleur, fillColor: couleur, fillOpacity: 0.9, weight: 0 }} />
    </MapContainer>
  );
}

export default function Fiche() {
  const { toutes, filtre } = useFiltres();
  const [params, setParams] = useSearchParams();

  const liste = useMemo(() => [...filtre].sort((a, b) => a.nom.localeCompare(b.nom, "fr")), [filtre]);
  const cles = liste.map((r) => r.cle);

  useEffect(() => {
    if (!cles.includes(params.get("cle")) && cles.length) setParams({ cle: cles[0] }, { replace: true });
  }, [cles.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps

  const choix = params.get("cle");
  const s = toutes.find((r) => r.cle === choix) || liste[0];
  if (!s) {
    return (
      <>
        <h1 className="titre">Aucune société ne correspond aux filtres</h1>
        <p className="chapo">Élargis la zone, les niveaux, le type de relation ou la détention minimale dans la colonne de gauche, ou vide la recherche.</p>
      </>
    );
  }

  function exporterFiltre() {
    const colonnes = Object.keys(toutes[0] || {}).filter((c) => !["texte_recherche", "cle", "score_detail"].includes(c));
    telechargerCsv("societes_selection.csv", colonnes.map((c) => ({ label: c, value: (r) => r[c] ?? "" })), filtre);
  }

  const couleur = COULEUR_ZONE[s.zone] || "#8A94AA";
  const estCatalogue = s.niveau === -1;
  const meme = (s.adresse ? toutes.filter((r) => r.adresse && r.adresse.toLowerCase() === s.adresse.toLowerCase() && r.cle !== s.cle) : []);
  const web = evenementsDe(s.nom);

  return (
    <>
      <Titre texte="Fiche société" chapo="Choisis une société dans la liste ou tape son nom ou son SIREN. La liste suit les filtres de la colonne de gauche." />
      {cles.length < toutes.length && (
        <p className="sidebar-caption" style={{ marginTop: "-1rem" }}>{cles.length} société(s) dans la liste sur {toutes.length} : filtres actifs dans la colonne de gauche.</p>
      )}

      <div style={{ display: "flex", gap: "1rem", marginBottom: "1.4rem", flexWrap: "wrap" }}>
        <select className="select-input" style={{ flex: "2 1 280px" }} value={choix || ""} onChange={(e) => setParams({ cle: e.target.value })}>
          {liste.map((r) => <option key={r.cle} value={r.cle}>{r.cle}</option>)}
        </select>
        <button className="btn" style={{ flex: "1 1 220px" }} onClick={exporterFiltre}>
          Télécharger la liste filtrée ({filtre.length}) (CSV)
        </button>
      </div>

      <h1 className="titre large" style={{ display: "flex", alignItems: "center", gap: ".6rem", flexWrap: "wrap" }}>
        {s.nom}
      </h1>
      <div className="badge-row">
        <Pastille texte={s.zone} couleur={couleur} />
        <Pastille texte={estCatalogue ? "Catalogue eurazeo.com" : (s.type_relation || "—")} couleur="var(--texte2)" />
        <Pastille texte={s.statut_administratif || "Statut inconnu"} couleur="var(--texte2)" />
        {estCatalogue ? <Pastille texte="Lien non vérifié" couleur="var(--couleur-alerte)" /> : (s.validation ? <Pastille texte={s.validation} couleur="var(--texte3)" /> : null)}
      </div>

      <div className="kv-grid" style={{ marginBottom: "1rem" }}>
        <Bloc lignes={[
          [
            s.niveau === 1 ? "Part du capital détenue par Eurazeo" : estCatalogue ? "Lien avec Eurazeo" : `Part du capital détenue par ${(s.nom_detentrice || "").toLowerCase().replace(/\w\S*/g, (w) => w[0].toUpperCase() + w.slice(1))} (niveau ${s.niveau})`,
            estCatalogue
              ? "Citée dans le catalogue des investissements d'Eurazeo (eurazeo.com), sans pourcentage publié. Chaîne de détention (quelle holding, quelle part) inconnue : voir la note ci-dessous."
              : (s.pourcentage_detention !== null && s.pourcentage_detention !== undefined ? `<b>${pct(s.pourcentage_detention)}</b>` : "Part non publiée dans les documents consultés"),
          ],
          ...(s.niveau >= 2 && s.part_economique_eurazeo !== null && s.part_economique_eurazeo !== undefined
            ? [["Part indirecte d'Eurazeo (calcul)", `<b>${pct(s.part_economique_eurazeo)}</b><br><span style="color:var(--texte3)">part dans la société × part d'Eurazeo dans la holding</span>`]]
            : []),
          ["Adresse du siège", v(s.adresse)],
          ["Région · département", v([s.region, s.departement].filter(Boolean).join(" · "))],
          ["Effectif salarié", v(s.tranche_effectif) + (String(s.annee_tranche_effectif || "").replace(".0", "").match(/^\d+$/) ? ` (au ${String(s.annee_tranche_effectif).replace(".0", "")})` : "")],
          ["Établissements (ouverts / total)", `${v(s.nb_etablissements_ouverts != null ? Math.trunc(s.nb_etablissements_ouverts) : null)} / ${v(s.nb_etablissements != null ? Math.trunc(s.nb_etablissements) : null)}`],
        ]} />
        <div>
          {s.latitude != null ? (
            <>
              <MiniCarte lat={s.latitude} lon={s.longitude} couleur={couleur} zoom={s.geo_precision === "adresse" ? 14 : 9} />
              {s.geo_precision === "ville" && <p className="sidebar-caption">Position approximative (centre-ville) : l'adresse exacte n'est pas géolocalisée.</p>}
            </>
          ) : <p className="sidebar-caption">Pas de coordonnées disponibles pour cette société.</p>}
        </div>
      </div>

      <div className="kv-grid" style={{ marginBottom: ".2rem" }}>
        <Bloc lignes={[
          ["SIREN", v(s.siren)], ["SIRET du siège", v(s.siret_siege)],
          ["Identifiant à l'étranger", v(s.identifiant_etranger)],
          ["Forme juridique", v(s.forme_juridique)],
          ["Date de création", dateFr(s.date_creation)], ["Catégorie d'entreprise", v(s.categorie_entreprise)],
        ]} />
        <Bloc lignes={[
          ["Activité", v([s.naf_code, s.naf_libelle].filter(Boolean).join(" · ")) + (s.naf_section ? `<br><span style="color:var(--texte3)">${s.naf_section}</span>` : "")],
          ["Dirigeants", v(s.dirigeants).replace(/ \| /g, "<br>")],
          ["Comptes publiés", comptesHtml(s)],
        ]} />
      </div>

      <TitreGraphique
        titre="Bail commercial et opportunité de déménagement (estimation)"
        sousTitre="Calculé à partir de la date d'installation au siège actuel, selon le cycle de bail commercial 3/6/9 (résiliation possible à chaque échéance triennale, préavis de 6 mois). Simplification assumée : on suppose que ce cycle continue depuis l'installation, sans savoir si un nouveau bail a été signé depuis. Si la date d'installation est inconnue, rien n'est calculé."
      />
      <div className="kv-grid">
        <div>
          <div className="badge-row"><Pastille texte={s.urgence_libelle} couleur={COULEUR_URGENCE[s.urgence_369] ?? "var(--texte3)"} /></div>
          {s.statut_bail && s.statut_bail !== STATUT_INCONNU && <p className="sidebar-caption" style={{ marginTop: 0 }}>{s.statut_bail}</p>}
          <Bloc lignes={[
            ["Date d'installation au siège actuel", s.date_installation_siege ? dateFr(s.date_installation_siege) : "—"],
            ["Prochaine échéance triennale (estimation)", s.prochaine_echeance_369 ? dateFr(isoDate(s.prochaine_echeance_369)) : "—"],
            ["Date limite pour donner congé (6 mois avant)", s.date_limite_preavis ? dateFr(isoDate(s.date_limite_preavis)) : "—"],
          ]} />
        </div>
        <div>
          {s.score_opportunite === null || s.score_opportunite === undefined ? (
            <Bloc lignes={[["Score d'opportunité", s.score_libelle]]} />
          ) : (
            <>
              <div className="bloc">
                <div className="etiquette">Score d'opportunité (sur 100, fiabilité {s.score_fiabilite}/{s.score_criteres_totaux} — {s.score_criteres_disponibles} critère(s) basé(s) sur une donnée réelle)</div>
                <div className="valeur" style={{ fontSize: "1.6rem" }}><b>{s.score_opportunite}</b> — {s.score_libelle}</div>
              </div>
              <details className="advanced">
                <summary>Détail du calcul</summary>
                <div className="inner">
                  <p className="sidebar-caption" style={{ marginTop: 0 }}>Pondération : bail ~61,5 % · finances ~38,5 % (critère « événements » de PRSimmo non porté ici, faute de données BODACC/presse).</p>
                  {s.score_detail.map(([pts, exp], i) => <p key={i} style={{ margin: ".3rem 0", fontSize: ".88rem" }}><b>{pts} pts</b> — {exp}</p>)}
                </div>
              </details>
            </>
          )}
        </div>
      </div>

      {meme.length > 0 && (
        <>
          <TitreGraphique titre={`${meme.length} autre${meme.length > 1 ? "s" : ""} société${meme.length > 1 ? "s" : ""} à la même adresse`} />
          <p className="sidebar-caption">{meme.map((m) => m.nom).join(", ")}</p>
        </>
      )}

      {s.verification && <Note>{`<b>Identification.</b> ${s.verification}`}</Note>}

      {web.length > 0 && (
        <Note>
          {`<b>Sources web.</b> Rapprochement par le nom de la société (à vérifier) :<ul style="margin:.4rem 0 0 0">` +
            web.map((e) => `<li><b>${e.etat}</b> · ${dateFr(e.date)} · ${e.evenement}` +
              (e.acquereur ? ` (acquéreur : ${e.acquereur})` : "") +
              ` · <a href="${e.url}" target="_blank" rel="noopener noreferrer">${e.source} ↗</a><br><span style="color:var(--texte3)">${e.extrait}</span></li>`).join("") +
            `</ul>`}
        </Note>
      )}

      {s.siren && <p><a href={`https://annuaire-entreprises.data.gouv.fr/entreprise/${s.siren}`} target="_blank" rel="noopener noreferrer">Voir la fiche officielle sur l'Annuaire des entreprises ↗</a></p>}
      <Note>{`<b>Source de la fiche.</b> ${s.source_relation || ""} · ${s.source_enrichissement || ""}.`}</Note>
    </>
  );
}

function isoDate(d) {
  if (typeof d === "string") return d.slice(0, 10);
  return new Date(d).toISOString().slice(0, 10);
}

function comptesHtml(s) {
  const eur = (x) => montant(x);
  if (s.chiffre_affaires != null || s.resultat_net != null) {
    let fin = s.chiffre_affaires != null ? `Chiffre d'affaires : ${eur(s.chiffre_affaires)}` : "Chiffre d'affaires : —";
    if (s.resultat_net != null) fin += `<br>Résultat net : ${eur(s.resultat_net)}`;
    if (s.croissance_ca_pct != null) fin += `<br>Évolution du CA sur un an : ${s.croissance_ca_pct >= 0 ? "+" : ""}${s.croissance_ca_pct.toFixed(1)} %`;
    if (s.annee_finances != null) fin += `<br><span style="color:var(--texte3)">Exercice ${Math.trunc(s.annee_finances)} · source : API Recherche d'Entreprises</span>`;
    return fin;
  }
  if (s.chiffre_affaires_estime_bilan != null || s.resultat_net_estime_bilan != null) {
    let fin = s.chiffre_affaires_estime_bilan != null ? `Chiffre d'affaires (estimé) : ${eur(s.chiffre_affaires_estime_bilan)}` : "Chiffre d'affaires : —";
    if (s.resultat_net_estime_bilan != null) fin += `<br>Résultat net (estimé) : ${eur(s.resultat_net_estime_bilan)}`;
    fin += `<br><span style="color:var(--couleur-alerte)">Extrait automatiquement d'un compte annuel INPI, pas une donnée structurée : à vérifier.</span>`;
    if (s.bilan_ligne_source_ca) fin += `<br><span style="color:var(--texte3)">Ligne source (CA) : « ${s.bilan_ligne_source_ca} »</span>`;
    return fin;
  }
  return "—";
}
