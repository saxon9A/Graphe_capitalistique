#!/usr/bin/env python3
"""
Récupère, pour chaque société du périmètre Eurazeo, toutes les informations
administratives disponibles (adresse exacte + coordonnées GPS, tranche
d'effectif, activité NAF, forme juridique, dirigeants, finances...) et écrit
sortie/entreprises_detaillees.csv, le fichier lu par le dashboard.

Usage :
    python enrichir_details.py

Prérequis : avoir lancé `python graphe.py 692030992` au moins une fois (le PDF
du DEU est alors téléchargé) ; avoir lancé `python valider.py` pour que les
relations validées soient marquées "Confirmée".

Sources :
  - Sociétés françaises : API Recherche d'Entreprises (Sirene INSEE + RNE
    INPI), aucune clé. Réponses brutes sauvegardées dans sortie/sirene_brut/.
  - Sociétés étrangères (sans SIREN) : adresse imprimée dans le DEU Eurazeo.
Un champ absent de la source reste vide : rien n'est inventé.
"""

import argparse
import csv
import json
import re
import shutil
import sys
import time
from datetime import date

from src import api_recherche_entreprises as recherche
from src import config
from src import details
from src import deu_eurazeo

DOSSIER_BRUT = config.OUTPUT_DIR / "sirene_brut"
FICHIER_SORTIE = config.OUTPUT_DIR / "entreprises_detaillees.csv"
NOM_EURAZEO = "EURAZEO"


def lire_relations_confirmees() -> dict:
    """{siren_detenue: ligne} depuis participations.csv (relations validées)."""
    if not config.FICHIER_PARTICIPATIONS.exists():
        return {}
    with open(config.FICHIER_PARTICIPATIONS, encoding="utf-8-sig", newline="") as f:
        return {l["siren_detenue"]: l for l in csv.DictReader(f, delimiter=";") if l.get("siren_detenue")}


def recuperer(siren: str):
    brut = recherche.get_entreprise_par_siren(siren)
    if brut:
        DOSSIER_BRUT.mkdir(exist_ok=True)
        (DOSSIER_BRUT / f"{siren}.json").write_text(
            json.dumps(brut, ensure_ascii=False, indent=2), encoding="utf-8")
    time.sleep(config.PAUSE_ENTRE_APPELS)
    return brut


def ligne_de_secours_deu(deu: dict) -> dict:
    """Si l'API ne répond pas pour un SIREN : on garde l'adresse du DEU, sans plus."""
    adresse = deu.get("adresse_deu") or ""
    m = re.search(r"\b(\d{5})\b", adresse)
    cp = m.group(1) if m else None
    return {
        "siren": deu.get("siren_candidat"),
        "siret_siege": deu.get("siret_candidat"),
        "nom": details._nettoyer_nom(deu.get("nom_candidat")),
        "pays": "France",
        "zone": details.zone_depuis_adresse("France", cp, None),
        "adresse": adresse,
        "code_postal": cp,
        "statut_administratif": "Non récupéré (API indisponible)",
        "source_enrichissement": "Adresse imprimée dans le DEU Eurazeo 2025 (API Sirene non joignable)",
    }


def main():
    parser = argparse.ArgumentParser(description="Enrichissement détaillé des sociétés Eurazeo.")
    parser.add_argument("--dashboard-dir", default="dashboard/data",
                        help="Copie aussi le CSV ici si le dossier existe (défaut : dashboard/data).")
    args = parser.parse_args()

    aujourdhui = date.today().isoformat()
    print("=== Enrichissement détaillé des sociétés du périmètre Eurazeo ===\n")

    print("1/3 Lecture du tableau des filiales et participations du DEU...")
    deu = deu_eurazeo.extraire_filiales_et_participations()
    if not deu:
        print("⚠️  Aucune ligne extraite du DEU. Lance d'abord : python graphe.py 692030992")
        sys.exit(1)
    confirmees = lire_relations_confirmees()
    print(f"    {len(deu)} lignes dans le DEU, {len(confirmees)} relation(s) déjà validée(s).")

    lignes = []

    print("\n2/3 Société mère (Eurazeo)...")
    brut_mere = recuperer(config.SIREN_EURAZEO)
    mere = details.ligne_depuis_api(brut_mere) if brut_mere else {
        "siren": config.SIREN_EURAZEO, "nom": NOM_EURAZEO, "pays": "France", "zone": details.ZONE_PARIS}
    mere.update({"niveau": 0, "type_relation": "Société mère", "validation": "Point de départ",
                 "source_relation": "—", "date_collecte": aujourdhui})
    lignes.append(mere)

    print(f"\n3/3 Interrogation de l'API pour {len(deu)} société(s)...")
    sans_reponse = []
    for i, c in enumerate(deu, start=1):
        siren = c.get("siren_candidat")
        if siren:
            brut = recuperer(siren)
            base = details.ligne_depuis_api(brut) if brut else ligne_de_secours_deu(c)
            if not brut:
                sans_reponse.append(c["nom_candidat"])
        else:
            base = details.ligne_depuis_deu_etranger(c)

        relation = confirmees.get(siren) if siren else None
        pct = (relation or {}).get("pourcentage_detention_directe") or c.get("pourcentage_candidat")
        base.update({
            "niveau": 1,
            "siren_detentrice": config.SIREN_EURAZEO,
            "nom_detentrice": NOM_EURAZEO,
            "type_relation": "Filiale (> 50 %)" if c["type_candidat"] == "filiale" else "Participation (10-50 %)",
            "validation": ("Confirmée" if relation else
                           ("Source DEU 2025, non validée" if siren else "Source DEU 2025, société étrangère")),
            "pourcentage_detention": float(str(pct).replace(",", ".")) if pct not in (None, "") else None,
            "page_deu": c.get("page_source"),
            "identifiant_etranger": base.get("identifiant_etranger") or c.get("identifiant_etranger"),
            "source_relation": "DEU Eurazeo 2025, Note 17 (tableau des filiales et participations)",
            "date_collecte": aujourdhui,
        })
        lignes.append(base)
        if i % 10 == 0 or i == len(deu):
            print(f"    {i}/{len(deu)}")

    config.OUTPUT_DIR.mkdir(exist_ok=True)
    with open(FICHIER_SORTIE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=details.COLONNES, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)

    dossier_dash = config.BASE_DIR / args.dashboard_dir
    if dossier_dash.exists():
        shutil.copy(FICHIER_SORTIE, dossier_dash / FICHIER_SORTIE.name)
        print(f"\nCopié aussi dans {dossier_dash}")

    # --- Bilan honnête ---
    filles = [l for l in lignes if l["niveau"] == 1]
    geo = sum(1 for l in filles if l.get("latitude") is not None)
    zones = {}
    for l in filles:
        zones[l["zone"]] = zones.get(l["zone"], 0) + 1
    print(f"\n=== Terminé : {len(filles)} sociétés + la mère -> {FICHIER_SORTIE} ===")
    print(f"  Géolocalisées : {geo}/{len(filles)}")
    print(f"  Répartition   : {zones}")
    print(f"  Avec tranche d'effectif : {sum(1 for l in filles if l.get('tranche_effectif_code'))}/{len(filles)}")
    if sans_reponse:
        print(f"  ⚠️  API sans réponse pour : {', '.join(sans_reponse)}")


if __name__ == "__main__":
    main()
