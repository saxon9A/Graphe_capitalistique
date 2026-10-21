#!/usr/bin/env python3
"""
Ajoute les coordonnées GPS (latitude/longitude) aux sociétés du catalogue
eurazeo.com qui ont un SIREN rapproché par le nom (voir catalogue_eurazeo.py).

Réutilise l'API Recherche d'Entreprises (DINUM / data.gouv.fr), déjà utilisée
partout ailleurs dans ce projet : aucune nouvelle clé, aucun nouveau service.
Le siège d'une entreprise y publie ses coordonnées GPS quand elles sont
géolocalisées par l'INSEE.

Les sociétés SANS SIREN rapproché (environ 50 sur 269 : le nom n'a trouvé
aucune correspondance dans Sirene) restent sans coordonnées : rien n'est
deviné ni placé approximativement par défaut.

Usage (après avoir lancé catalogue_eurazeo.py) :
    python geocoder_catalogue.py
"""

import time

from src import config
from src.api_recherche_entreprises import get_entreprise_par_siren
from src.logger import log

try:
    import pandas as pd
except ImportError:
    print("pandas est requis : pip install pandas")
    raise

CHEMIN = config.OUTPUT_DIR / "portefeuille_eurazeo_catalogue.csv"
CHAMPS_AJOUTES = ["latitude", "longitude", "geo_precision"]


def geocoder_un(siren: str) -> dict:
    """Coordonnées GPS du siège d'une société, via son SIREN. Rien n'est
    inventé : si l'API ne renvoie pas de coordonnées (siège non géolocalisé,
    SIREN introuvable…), les trois champs restent vides."""
    vide = {"latitude": "", "longitude": "", "geo_precision": ""}
    if not siren:
        return vide
    resultat = get_entreprise_par_siren(siren)
    if not resultat:
        return vide
    siege = resultat.get("siege") or {}
    lat, lon = siege.get("latitude"), siege.get("longitude")
    if not lat or not lon:
        return vide
    return {"latitude": lat, "longitude": lon, "geo_precision": "adresse"}


def main():
    if not CHEMIN.exists():
        print(f"Fichier introuvable : {CHEMIN}. Lance d'abord : python catalogue_eurazeo.py chemin/du/scrape.csv")
        return

    df = pd.read_csv(CHEMIN, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    for c in CHAMPS_AJOUTES:
        if c not in df.columns:
            df[c] = ""

    a_faire = df.index[(df["siren"].str.strip() != "") & (df["latitude"].str.strip() == "")]
    print(f"=== Géocodage de {len(a_faire)} société(s) avec un SIREN rapproché (sur {len(df)} au total) ===")

    trouves = 0
    for i, idx in enumerate(a_faire, 1):
        siren = df.at[idx, "siren"].strip()
        nom = df.at[idx, "nom"]
        coords = geocoder_un(siren)
        for c in CHAMPS_AJOUTES:
            df.at[idx, c] = coords[c]
        if coords["latitude"]:
            trouves += 1
            etat = "ok"
        else:
            etat = "pas de coordonnées"
        print(f"  {i}/{len(a_faire)}  {nom[:40]:40s}  {siren}  {etat}")
        log("geocodage", "recherche_entreprises", "ok" if coords["latitude"] else "introuvable", "",
            siren=siren)
        time.sleep(config.PAUSE_ENTRE_APPELS)

    df.to_csv(CHEMIN, sep=";", index=False, encoding="utf-8-sig")
    dossier_dash = config.BASE_DIR / "dashboard" / "data"
    if dossier_dash.exists():
        import shutil
        shutil.copy(CHEMIN, dossier_dash / CHEMIN.name)
        print(f"Copié aussi dans {dossier_dash}")

    print(f"\n{trouves}/{len(a_faire)} société(s) géolocalisée(s) avec succès -> {CHEMIN}")
    sans_siren = int((df["siren"].str.strip() == "").sum())
    if sans_siren:
        print(f"Rappel : {sans_siren} société(s) du catalogue n'ont pas de SIREN rapproché et restent "
              "sans coordonnées (pas d'adresse connue à géocoder).")


if __name__ == "__main__":
    main()
