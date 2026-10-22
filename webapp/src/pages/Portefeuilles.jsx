import { useMemo } from "react";
import Lollipop from "../components/Lollipop";
import { Bande, Constat, NoteSources, pct, Titre, TitreGraphique } from "../components/ui";
import { meta, ZONE_ETRANGER, ZONE_FRANCE, ZONE_PARIS } from "../lib/dataset";
import { useFiltres } from "../lib/FiltersContext";

export default function Portefeuilles() {
  const { toutes, filtre } = useFiltres();
  const n2Total = toutes.filter((r) => r.niveau >= 2).length;
  const d = filtre.filter((r) => r.niveau >= 2);

  if (!n2Total) {
    return <Titre texte="Les portefeuilles" chapo="Le niveau 2 n'est pas encore collecté : lance `python niveau2_collecter.py`, `python niveau2_extraire.py` puis `python niveau2_enrichir.py`." />;
  }
  if (!d.length) {
    return <Titre texte="Aucune société des niveaux 2 et suivants ne correspond aux filtres" chapo="Vérifie le filtre Niveaux, la zone et la recherche dans la colonne de gauche." />;
  }

  const n = d.length;
  const nH = new Set(d.map((r) => r.siren_detentrice)).size;
  const nEtr = d.filter((r) => r.zone === ZONE_ETRANGER).length;
  const nFr = d.filter((r) => r.zone === ZONE_PARIS || r.zone === ZONE_FRANCE).length;
  const avecPct = d.filter((r) => r.pourcentage_detention !== null && r.pourcentage_detention !== undefined);
  const econ = d.map((r) => r.part_economique_eurazeo).filter((x) => x !== null && x !== undefined);
  const medEcon = econ.length ? [...econ].sort((a, b) => a - b)[Math.floor(econ.length / 2)] : null;
  const sans = d.filter((r) => r.pourcentage_detention === null || r.pourcentage_detention === undefined);

  return (
    <>
      <Titre
        texte={`${n} sociétés sont détenues par ${nH} holdings, sous le premier cercle d'Eurazeo`}
        chapo="Au-delà des sociétés détenues directement, chaque holding déclare dans ses comptes annuels les sociétés dont elle possède des titres. C'est là que se trouvent les entreprises opérationnelles."
      />

      <Bande indicateurs={[
        [n, "sociétés détenues via une holding"],
        [nFr, "en France"],
        [nEtr, "à l'étranger"],
        [avecPct.filter((r) => r.pourcentage_detention > 50).length, "détenues à plus de 50 % par leur holding"],
        [medEcon !== null ? pct(medEcon, 0) : "—", "part indirecte médiane d'Eurazeo (calcul)"],
      ]} />

      <TitreGraphique titre="Part du capital détenue par la holding, société par société" sousTitre="Chaque ligne est une société, suivie de la holding qui la détient. Survole un point pour voir la part indirecte d'Eurazeo." />
      {avecPct.length > 0 && <Lollipop lignes={avecPct} />}

      {sans.length > 0 && (
        <>
          <TitreGraphique titre={`${sans.length} sociétés citées sans pourcentage`} sousTitre='Les comptes les mentionnent (par exemple « participation minoritaire au capital de Doctolib SAS ») sans publier la part détenue. Une société citée a pu être cédée depuis.' />
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Société</th><th>Citée dans les comptes de</th><th>Zone</th><th>Adresse</th></tr></thead>
              <tbody>{sans.map((r) => <tr key={r.cle}><td>{r.nom}</td><td>{r.nom_detentrice}</td><td>{r.zone}</td><td>{r.adresse || "—"}</td></tr>)}</tbody>
            </table>
          </div>
        </>
      )}

      <TitreGraphique titre="Voir les données de ce graphique" />
      <details className="advanced"><summary>Tableau complet ({avecPct.length})</summary>
        <div className="inner table-wrap">
          <table className="tbl">
            <thead><tr><th>Société</th><th>Détenue par</th><th>Part de la holding (%)</th><th>Part indirecte d'Eurazeo (calcul, %)</th><th>Zone</th><th>Pays</th><th>SIREN / identifiant</th></tr></thead>
            <tbody>
              {[...avecPct].sort((a, b) => (b.pourcentage_detention ?? 0) - (a.pourcentage_detention ?? 0)).map((r) => (
                <tr key={r.cle}>
                  <td>{r.nom}</td><td>{r.nom_detentrice}</td>
                  <td className="num">{pct(r.pourcentage_detention)}</td>
                  <td className="num">{r.part_economique_eurazeo != null ? pct(r.part_economique_eurazeo) : "—"}</td>
                  <td>{r.zone}</td><td>{r.pays || "—"}</td><td>{r.identifiant || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <Constat>
        {"<b>À lire avec prudence.</b> Les pourcentages sont ceux imprimés dans les comptes annuels des holdings " +
          "(exercice 2025 pour la plupart, 2024 pour certains tableaux). Plusieurs holdings ne détiennent que de petites " +
          "parts : une société peut figurer ici sans qu'Eurazeo en ait le contrôle. La colonne « Identification » " +
          "de la fiche dit comment chaque société a été reconnue."}
      </Constat>
      <NoteSources dateCollecte={meta.date_collecte_max} niveauMax={Math.max(1, ...toutes.map((r) => r.niveau))} />
    </>
  );
}
