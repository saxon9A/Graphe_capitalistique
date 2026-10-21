#!/usr/bin/env python3
"""
Complète sortie/entreprises_detaillees.csv et sortie/entreprises_niveau*.csv avec :
  - date_installation_siege (date d'installation à l'adresse ACTUELLE du siège,
    utilisée pour le calcul du cycle de bail commercial 3/6/9 dans le dashboard) ;
  - chiffre_affaires_annee_precedente et croissance_ca_pct (pour le score
    d'opportunité « déménagement » du dashboard).

Ces deux champs n'existaient pas quand ces fichiers ont été produits par
enrichir_details.py / niveau2_enrichir.py : ce script les rajoute en relisant
chaque société (même source gratuite, déjà utilisée : API Recherche
d'Entreprises) sans relancer toute l'exploration. Ne touche à AUCUNE autre
colonne et ne supprime aucune ligne. Relançable sans risque.

Usage :
    python completer_dates_installation.py
"""

import csv
import shutil
import time
from pathlib import Path

from src import api_recherche_entreprises, config, details

FICHIER_PRINCIPAL = config.OUTPUT_DIR / "entreprises_detaillees.csv"
DOSSIER_DASH = config.BASE_DIR / "dashboard" / "data"
NOUVEAUX_CHAMPS = ["date_installation_siege", "chiffre_affaires_annee_precedente", "croissance_ca_pct"]


def completer_fichier(chemin: Path):
    if not chemin.exists():
        return
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        fieldnames = list(lecteur.fieldnames or [])
        lignes = list(lecteur)

    deja_present = all(c in fieldnames for c in NOUVEAUX_CHAMPS)
    maj, echecs = 0, 0
    print(f"\n=== {chemin.name} : {len(lignes)} ligne(s) ===")
    for r in lignes:
        if deja_present and (r.get("date_installation_siege") or "").strip():
            continue   # déjà complété lors d'un run précédent : on ne rappelle pas l'API pour rien
        siren = (r.get("siren") or "").strip()
        if not siren:
            continue
        brut = api_recherche_entreprises.get_entreprise_par_siren(siren)
        if not brut:
            echecs += 1
            print(f"  ✗ {r.get('nom', siren)[:40]:40}  introuvable via l'API")
            time.sleep(config.PAUSE_ENTRE_APPELS)
            continue
        enrichi = details.ligne_depuis_api(brut)
        for champ in NOUVEAUX_CHAMPS:
            valeur = enrichi.get(champ)
            r[champ] = "" if valeur is None else str(valeur)
        maj += 1
        installe = r["date_installation_siege"] or "inconnue"
        print(f"  ✓ {r.get('nom', siren)[:40]:40}  installation : {installe}")
        time.sleep(config.PAUSE_ENTRE_APPELS)

    for champ in NOUVEAUX_CHAMPS:
        if champ not in fieldnames:
            fieldnames.append(champ)

    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)
    if DOSSIER_DASH.exists():
        shutil.copy(chemin, DOSSIER_DASH / chemin.name)

    print(f"  -> {maj} société(s) mise(s) à jour, {echecs} introuvable(s) via l'API, {chemin}")


def main():
    fichiers = [FICHIER_PRINCIPAL] + sorted(config.OUTPUT_DIR.glob("entreprises_niveau*.csv"))
    if not any(f.exists() for f in fichiers):
        print("Aucun fichier trouvé. Lance d'abord python enrichir_details.py.")
        return
    for f in fichiers:
        completer_fichier(f)
    print("\nTerminé. Pense à relancer `streamlit run dashboard/app.py` (ou juste rafraîchir la page) "
          "pour voir les nouvelles échéances de bail dans le dashboard.")


if __name__ == "__main__":
    main()
