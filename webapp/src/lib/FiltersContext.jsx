// Port de dashboard/lib/data.afficher_filtres() : mêmes filtres, même logique de correspondance,
// partagés entre toutes les pages (comme st.session_state côté Streamlit). Persistés en
// sessionStorage pour survivre à la navigation entre pages (pas au-delà, comme Streamlit).
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { appliquerScoring, LIBELLE_URGENCE, ORDRE_URGENCE_LIBELLES } from "./scoring";
import { NON_RENSEIGNE, ORDRE_EFFECTIF, toutes as toutesBrut, ZONES } from "./dataset";

const CLE_SESSION = "filtres_v1";

function cleNiveau(lib) {
  return lib === "Catalogue" ? [1, 0] : [0, Number(lib.split(" ").pop())];
}

function defautFiltres(toutes) {
  const niveauxPresents = [...new Set(toutes.map((r) => r.niveau_lib))].sort(
    (a, b) => cleNiveau(a)[0] - cleNiveau(b)[0] || cleNiveau(a)[1] - cleNiveau(b)[1]
  );
  const zonesDispo = ZONES.filter((z) => toutes.some((r) => r.zone === z));
  const groupesDispo = [...ORDRE_EFFECTIF, NON_RENSEIGNE].filter((g) => toutes.some((r) => r.groupe_effectif === g));
  const typesDispo = [...new Set(toutes.map((r) => r.type_court))].sort();
  return {
    q: "",
    niveaux: niveauxPresents,
    zones: zonesDispo,
    sansHolding: true,
    bail: ORDRE_URGENCE_LIBELLES.slice(),
    scoreMin: 0,
    types: typesDispo,
    pmin: 0,
    effectifs: groupesDispo,
  };
}

function chargerSession() {
  try {
    const brut = sessionStorage.getItem(CLE_SESSION);
    return brut ? JSON.parse(brut) : null;
  } catch {
    return null;
  }
}

const FiltersCtx = createContext(null);

export function FiltersProvider({ children }) {
  // Scoring recalculé une fois par montage (date du jour) — jamais mis en cache sur disque,
  // comme en Python (voir scoring.js). Un rechargement de page le rafraîchit.
  const toutes = useMemo(() => appliquerScoring(toutesBrut, new Date()), []);
  const defauts = useMemo(() => defautFiltres(toutes), [toutes]);
  const [filtres, setFiltres] = useState(() => chargerSession() || defauts);

  useEffect(() => {
    try {
      sessionStorage.setItem(CLE_SESSION, JSON.stringify(filtres));
    } catch {
      /* stockage indisponible (navigation privée...) : tant pis, pas bloquant */
    }
  }, [filtres]);

  const options = useMemo(() => {
    const niveauxPresents = [...new Set(toutes.map((r) => r.niveau_lib))].sort(
      (a, b) => cleNiveau(a)[0] - cleNiveau(b)[0] || cleNiveau(a)[1] - cleNiveau(b)[1]
    );
    const zonesDispo = ZONES.filter((z) => toutes.some((r) => r.zone === z));
    const nHolding = toutes.filter((r) => r.est_holding).length;
    const urgencesDispo = ORDRE_URGENCE_LIBELLES.filter((u) => toutes.some((r) => r.urgence_libelle === u));
    const typesDispo = [...new Set(toutes.map((r) => r.type_court))].sort();
    const groupesDispo = [...ORDRE_EFFECTIF, NON_RENSEIGNE].filter((g) => toutes.some((r) => r.groupe_effectif === g));
    return { niveauxPresents, zonesDispo, nHolding, urgencesDispo, typesDispo, groupesDispo };
  }, [toutes]);

  const filtre = useMemo(() => {
    const q = filtres.q.trim().toLowerCase();
    return toutes.filter((r) => {
      if (!filtres.zones.includes(r.zone)) return false;
      if (!filtres.types.includes(r.type_court)) return false;
      if (!filtres.effectifs.includes(r.groupe_effectif)) return false;
      if (!filtres.niveaux.includes(r.niveau_lib)) return false;
      if (!filtres.bail.includes(r.urgence_libelle)) return false;
      if (filtres.scoreMin > 0 && (r.score_opportunite ?? -1) < filtres.scoreMin) return false;
      const pct = r.pourcentage_detention ?? 100;
      if (pct < filtres.pmin) return false;
      if (filtres.sansHolding && r.est_holding) return false;
      if (q && !(r.texte_recherche || "").includes(q)) return false;
      return true;
    });
  }, [toutes, filtres]);

  function majFiltre(cle, valeur) {
    setFiltres((f) => ({ ...f, [cle]: valeur }));
  }

  function reinitialiser() {
    setFiltres(defauts);
  }

  const valeur = useMemo(
    () => ({ toutes, filtre, filtres, options, majFiltre, reinitialiser }),
    [toutes, filtre, filtres, options]
  );

  return <FiltersCtx.Provider value={valeur}>{children}</FiltersCtx.Provider>;
}

export function useFiltres() {
  const ctx = useContext(FiltersCtx);
  if (!ctx) throw new Error("useFiltres() doit être appelé sous <FiltersProvider>");
  return ctx;
}

export { LIBELLE_URGENCE };
