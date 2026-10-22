import { useState } from "react";

const CLE_LOCAL = "accès_autorisé_v1";
const HASH_ATTENDU = import.meta.env.VITE_SITE_PASSWORD_HASH || "";

async function sha256Hex(texte) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(texte));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function dejaAutorise() {
  try {
    return localStorage.getItem(CLE_LOCAL) === "1";
  } catch {
    return false;
  }
}

export default function PasswordGate({ onOk }) {
  const [mdp, setMdp] = useState("");
  const [erreur, setErreur] = useState("");
  const [enCours, setEnCours] = useState(false);

  async function valider(e) {
    e.preventDefault();
    if (!HASH_ATTENDU) {
      setErreur("Mot de passe non configuré côté serveur (variable VITE_SITE_PASSWORD_HASH absente).");
      return;
    }
    setEnCours(true);
    const h = await sha256Hex(mdp);
    setEnCours(false);
    if (h === HASH_ATTENDU) {
      try {
        localStorage.setItem(CLE_LOCAL, "1");
      } catch {
        /* navigation privée : tant pis, redemandé au prochain chargement */
      }
      onOk();
    } else {
      setErreur("Mot de passe incorrect.");
      setMdp("");
    }
  }

  return (
    <div className="password-screen">
      <form onSubmit={valider}>
        <h1 className="titre" style={{ fontSize: "1.3rem", margin: 0 }}>Eurazeo · premier cercle</h1>
        <p className="chapo" style={{ margin: 0, fontSize: ".92rem" }}>Accès réservé — saisis le mot de passe partagé.</p>
        <input
          className="text-input"
          type="password"
          autoFocus
          placeholder="Mot de passe"
          value={mdp}
          onChange={(e) => setMdp(e.target.value)}
        />
        <div className="err">{erreur}</div>
        <button className="btn primary" type="submit" disabled={enCours}>
          {enCours ? "Vérification…" : "Entrer"}
        </button>
      </form>
    </div>
  );
}
