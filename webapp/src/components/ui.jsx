// Petits composants partagés, portés de dashboard/lib/ui.py.

export function dateFr(x) {
  if (!x) return "—";
  const p = String(x).split("-");
  return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : "—";
}

export function montant(x) {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return `${Math.trunc(x).toLocaleString("fr-FR")} €`;
}

export function pct(x, decimales = 1) {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return `${x.toFixed(decimales).replace(".", ",")} %`;
}

export function v(x, suffixe = "") {
  if (x === null || x === undefined || x === "" || (typeof x === "number" && Number.isNaN(x))) return "—";
  return `${x}${suffixe}`;
}

export function Titre({ texte, chapo, large }) {
  return (
    <>
      <h1 className={`titre${large ? " large" : ""}`}>{texte}</h1>
      {chapo ? <p className="chapo">{chapo}</p> : <div className="rule" />}
    </>
  );
}

export function TitreGraphique({ titre, sousTitre }) {
  return (
    <>
      <div className="titre-graph">{titre}</div>
      {sousTitre ? <div className="sous-titre-graph">{sousTitre}</div> : null}
    </>
  );
}

export function Bande({ indicateurs }) {
  return (
    <div className="bande">
      {indicateurs.map(([val, lib], i) => (
        <div className="kpi" key={i}>
          <div className="v">{val}</div>
          <div className="l">{lib}</div>
        </div>
      ))}
    </div>
  );
}

export function Pastille({ texte, couleur }) {
  return (
    <span className="pastille" style={{ color: couleur, borderColor: `${couleur}66`, background: `${couleur}1A` }}>
      {texte}
    </span>
  );
}

export function Bloc({ lignes }) {
  return (
    <div className="bloc">
      {lignes.map(([etiquette, valeur], i) => (
        <div key={i}>
          <div className="etiquette">{etiquette}</div>
          <div className="valeur" dangerouslySetInnerHTML={{ __html: valeur }} />
        </div>
      ))}
    </div>
  );
}

export function Note({ children }) {
  return <div className="note" dangerouslySetInnerHTML={{ __html: children }} />;
}

export function Constat({ children }) {
  return <div className="constat" dangerouslySetInnerHTML={{ __html: children }} />;
}

export function NoteSources({ dateCollecte, niveauMax }) {
  const quand = dateCollecte ? ` · Données Sirene collectées le ${dateCollecte}` : "";
  let suite;
  if (niveauMax >= 2) {
    const niv = niveauMax === 2 ? "Niveau 2" : `Niveaux 2 à ${niveauMax}`;
    suite = `${niv} : sociétés détenues par les holdings du niveau précédent, lues dans le tableau des filiales ` +
      "et participations (ou les notes) de leurs comptes annuels déposés au RNE (INPI). La part indirecte " +
      "d'Eurazeo est un calcul : part dans la société × part indirecte d'Eurazeo dans la société qui la " +
      "détient. On ne descend que par les holdings françaises : les sociétés étrangères et les sociétés " +
      "opérationnelles ne sont pas explorées. ";
  } else {
    suite = "Seul le premier cercle est représenté : les sociétés détenues par ces filiales n'y figurent pas. ";
  }
  return (
    <Note>
      {`<b>Sources et limites.</b> Liste des filiales et participations : Document d'enregistrement universel 2025 ` +
        `d'Eurazeo (Note 17, comptes individuels), dépôt AMF. Adresses, effectifs, activité et dirigeants : Sirene ` +
        `(INSEE) et RNE (INPI) via l'API Recherche d'Entreprises${quand}. ${suite}` +
        `La tranche d'effectif est une fourchette déclarée, pas un nombre exact. Les sociétés étrangères sont ` +
        `placées au centre-ville (position approximative).`}
    </Note>
  );
}
