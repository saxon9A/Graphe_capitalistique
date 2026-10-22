// Export CSV côté client, même convention que le reste du projet : séparateur « ; », UTF-8 avec BOM
// (comme to_csv(sep=";").encode("utf-8-sig") en Python, pour qu'Excel FR l'ouvre correctement).
function champCsv(v) {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function telechargerCsv(nomFichier, colonnes, lignes) {
  const entete = colonnes.map((c) => champCsv(c.label)).join(";");
  const corps = lignes.map((r) => colonnes.map((c) => champCsv(c.value(r))).join(";")).join("\n");
  const contenu = `﻿${entete}\n${corps}`;
  const blob = new Blob([contenu], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nomFichier;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
