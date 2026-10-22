import { useEffect, useMemo, useRef, useState } from "react";
import { Constat, NoteSources, Titre } from "../components/ui";
import { telechargerCsv } from "../lib/csv";
import { catalogueRaw, evenementsDe, liens, mere, meta } from "../lib/dataset";
import { useFiltres } from "../lib/FiltersContext";
import { preparer, preparerCatalogue, RACINE } from "../lib/graphePrepare";

// La page interactive elle-même (toolbar, légende, panneau, physique vis-network) est le fichier
// existant dashboard/assets/graphe.html, servi tel quel ici (public/graphe-assets/) — aucune
// réécriture : seules les données (D) sont reconstruites à chaque changement de filtre, en JS
// (voir lib/graphePrepare.js, port de graphe.py), puis injectées dans une iframe isolée.
function construireHtml(shell, vis, donnees) {
  // U+2028/U+2029 (séparateurs de ligne valides en JSON mais invalides tels quels dans un
  // <script> HTML) construits via fromCharCode pour ne jamais écrire le caractère littéral ici.
  const ls = String.fromCharCode(8232);
  const ps = String.fromCharCode(8233);
  const js = JSON.stringify(donnees)
    .split("</").join("<\\/")
    .split(ls).join("\\u2028")
    .split(ps).join("\\u2029");
  return shell.replace("/*__VIS__*/", vis).replace("/*__DONNEES__*/", js);
}

export default function Graphe() {
  const { toutes, filtre } = useFiltres();
  const [assets, setAssets] = useState(null);
  const iframeRef = useRef(null);

  useEffect(() => {
    Promise.all([
      fetch("/graphe-assets/graphe-shell.html").then((r) => r.text()),
      fetch("/graphe-assets/vis-network.min.js").then((r) => r.text()),
    ]).then(([shell, vis]) => setAssets({ shell, vis }));
  }, []);

  const donnees = useMemo(() => {
    const d = preparer(toutes, filtre, mere, liens, evenementsDe);
    d.catalogue = preparerCatalogue(toutes.filter((r) => r.niveau !== -1), catalogueRaw);
    return d;
  }, [toutes, filtre]);

  const niveauMax = Math.max(1, ...toutes.map((r) => r.niveau));
  const nAff = donnees.nodes.filter((n) => n.match && n.id !== RACINE).length;
  const nChemin = donnees.nodes.filter((n) => !n.match && n.id !== RACINE).length;

  useEffect(() => {
    if (!assets || !iframeRef.current) return;
    iframeRef.current.srcdoc = construireHtml(assets.shell, assets.vis, donnees);
  }, [assets, donnees]);

  function telechargerLiens() {
    const parId = new Map(donnees.nodes.map((n) => [n.id, n]));
    const lignes = donnees.edges.map((a) => ({
      detentrice: parId.get(a.from)?.nom, id_detentrice: a.from,
      detenue: parId.get(a.to)?.nom, id_detenue: a.to, niveau_detenue: parId.get(a.to)?.niveau,
      pourcentage_detention: a.pct,
      type_lien: a.interne ? "autre détenteur d'une société déjà présente" : "détention",
    }));
    telechargerCsv("liens_graphe.csv", [
      { label: "detentrice", value: (r) => r.detentrice }, { label: "id_detentrice", value: (r) => r.id_detentrice },
      { label: "detenue", value: (r) => r.detenue }, { label: "id_detenue", value: (r) => r.id_detenue },
      { label: "niveau_detenue", value: (r) => r.niveau_detenue }, { label: "pourcentage_detention", value: (r) => r.pourcentage_detention ?? "" },
      { label: "type_lien", value: (r) => r.type_lien },
    ], lignes);
  }

  return (
    <>
      <Titre
        texte={`${nAff} sociétés dans le réseau d'Eurazeo`}
        chapo="Chaque flèche va du détenteur vers la société détenue. Glisse une société pour la déplacer, molette pour zoomer, clique pour voir sa chaîne de détention jusqu'à Eurazeo."
      />
      <p className="sidebar-caption" style={{ marginTop: "-1rem" }}>
        Les boutons au-dessus du graphe filtrent à la volée (zone, niveau) ; la colonne de gauche filtre aussi, par
        exemple sur la recherche ou la détention minimale. Avec « Chemin jusqu'à Eurazeo », les holdings qui relient
        une société affichée à Eurazeo restent visibles, en pâle{nChemin ? ` (${nChemin} ici).` : "."}
      </p>

      <iframe
        ref={iframeRef}
        title="Le graphe de détention"
        style={{ width: "100%", height: 760, border: "none", borderRadius: 14 }}
        sandbox="allow-scripts allow-popups"
      />

      {niveauMax < 3 && (
        <Constat>{`Le graphe s'arrête au niveau ${niveauMax}. Pour descendre d'un niveau de plus : <b>python descendre.py 3</b> (voir le README).`}</Constat>
      )}
      <div style={{ margin: "1rem 0" }}>
        <button className="btn" onClick={telechargerLiens}>Télécharger les liens affichés (CSV pour Excel / Power BI)</button>
      </div>
      <Constat>
        {"<b>À lire avec prudence.</b> Les sociétés sans adresse ni SIREN trouvés sont en « Non localisée ». " +
          "On ne descend que par les holdings françaises : les sociétés étrangères et les sociétés opérationnelles " +
          "sont des culs-de-sac du graphe, ce qui ne veut pas dire qu'elles ne détiennent rien."}
      </Constat>
      <NoteSources dateCollecte={meta.date_collecte_max} niveauMax={niveauMax} />
    </>
  );
}
