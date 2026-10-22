import { useState } from "react";
import { HashRouter, Route, Routes } from "react-router-dom";
import PasswordGate, { dejaAutorise } from "./components/PasswordGate";
import Sidebar from "./components/Sidebar";
import { FiltersProvider } from "./lib/FiltersContext";
import Annuaire from "./pages/Annuaire";
import Carte from "./pages/Carte";
import Fiche from "./pages/Fiche";
import Graphe from "./pages/Graphe";
import Portefeuilles from "./pages/Portefeuilles";

export default function App() {
  const [autorise, setAutorise] = useState(dejaAutorise);

  if (!autorise) return <PasswordGate onOk={() => setAutorise(true)} />;

  return (
    <HashRouter>
      <FiltersProvider>
        <div className="app-shell">
          <Sidebar />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Annuaire />} />
              <Route path="/fiche" element={<Fiche />} />
              <Route path="/carte" element={<Carte />} />
              <Route path="/graphe" element={<Graphe />} />
              <Route path="/portefeuilles" element={<Portefeuilles />} />
            </Routes>
          </main>
        </div>
      </FiltersProvider>
    </HashRouter>
  );
}
