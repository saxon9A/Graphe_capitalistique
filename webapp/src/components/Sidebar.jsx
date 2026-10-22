import { NavLink } from "react-router-dom";
import { useFiltres } from "../lib/FiltersContext";

const PAGES = [
  { to: "/", label: "L'annuaire" },
  { to: "/fiche", label: "Fiche société" },
  { to: "/carte", label: "La carte" },
  { to: "/graphe", label: "Le graphe" },
  { to: "/portefeuilles", label: "Les portefeuilles" },
];

function Pills({ options, selected, onToggle }) {
  return (
    <div className="pills">
      {options.map((o) => (
        <span key={o} className={`pill${selected.includes(o) ? " active" : ""}`} onClick={() => onToggle(o)}>
          {o}
        </span>
      ))}
    </div>
  );
}

function togglerListe(liste, valeur) {
  return liste.includes(valeur) ? liste.filter((x) => x !== valeur) : [...liste, valeur];
}

export default function Sidebar() {
  const { filtres, majFiltre, reinitialiser, options, toutes, filtre } = useFiltres();

  return (
    <aside className="sidebar">
      <h3>Eurazeo · premier cercle</h3>
      <nav className="sidebar-nav">
        {PAGES.map((p) => (
          <NavLink key={p.to} to={p.to} className={({ isActive }) => (isActive ? "active" : "")} end={p.to === "/"}>
            {p.label}
          </NavLink>
        ))}
      </nav>

      <div className="field-label">Filtres</div>

      <input
        className="text-input"
        style={{ marginBottom: "1rem" }}
        type="text"
        placeholder="Nom, SIREN, adresse…"
        value={filtres.q}
        onChange={(e) => majFiltre("q", e.target.value)}
        title="Cherche dans le nom, le SIREN et l'adresse. S'applique à toutes les pages, y compris la liste de la fiche société."
      />

      {options.niveauxPresents.length > 1 && (
        <>
          <div className="field-label">Niveaux</div>
          <Pills options={options.niveauxPresents} selected={filtres.niveaux} onToggle={(v) => majFiltre("niveaux", togglerListe(filtres.niveaux, v))} />
        </>
      )}

      <div className="field-label">Zone géographique</div>
      <Pills options={options.zonesDispo} selected={filtres.zones} onToggle={(v) => majFiltre("zones", togglerListe(filtres.zones, v))} />

      <label className="checkbox-row">
        <input type="checkbox" checked={filtres.sansHolding} onChange={(e) => majFiltre("sansHolding", e.target.checked)} />
        <span>
          Masquer les holdings et sociétés de gestion de fonds
          <span className="sidebar-caption" style={{ display: "block", marginTop: ".15rem" }}>
            {options.nHolding} sur {toutes.length} dans la sélection actuelle
          </span>
        </span>
      </label>

      <div className="field-label">Statut du bail (estimation 3/6/9)</div>
      <Pills options={options.urgencesDispo} selected={filtres.bail} onToggle={(v) => majFiltre("bail", togglerListe(filtres.bail, v))} />

      <div className="field-label">Score d'opportunité minimum</div>
      <input
        className="slider-input"
        type="range"
        min={0}
        max={100}
        step={5}
        value={filtres.scoreMin}
        onChange={(e) => majFiltre("scoreMin", Number(e.target.value))}
      />
      <div className="slider-value">{filtres.scoreMin}</div>

      <details className="advanced">
        <summary>Filtres avancés</summary>
        <div className="inner">
          <div className="field-label">Type de relation</div>
          <Pills options={options.typesDispo} selected={filtres.types} onToggle={(v) => majFiltre("types", togglerListe(filtres.types, v))} />

          <div className="field-label">Détention minimale (%)</div>
          <input
            className="slider-input"
            type="range"
            min={0}
            max={100}
            value={filtres.pmin}
            onChange={(e) => majFiltre("pmin", Number(e.target.value))}
          />
          <div className="slider-value">{filtres.pmin} %</div>

          {options.groupesDispo.length > 1 && (
            <>
              <div className="field-label">Effectif salarié</div>
              <Pills options={options.groupesDispo} selected={filtres.effectifs} onToggle={(v) => majFiltre("effectifs", togglerListe(filtres.effectifs, v))} />
            </>
          )}
        </div>
      </details>

      <button className="btn small" onClick={reinitialiser}>Réinitialiser les filtres</button>
      <div className="sidebar-caption">{filtre.length} société(s) sur {toutes.length}</div>
    </aside>
  );
}
