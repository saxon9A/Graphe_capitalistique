"""Exporte les données du dashboard en JSON pour la version React/Vercel (webapp/).

Réutilise tel quel le pipeline Python existant (dashboard/lib/data.py pour le chargement, le
catalogue et les filtres ; dashboard/lib/scoring.py est NE PAS exporté calculé — les champs de
score/bail dépendent de la date du jour, ils sont recalculés côté client en JS, comme en Python
où ils ne sont jamais écrits sur disque). Objectif : zéro réimplémentation de la logique de
rapprochement/fusion catalogue en JS ; seul le scoring (date-dépendant) est porté en JS.

Usage :  python export_webapp_data.py
Produit (écrasés à chaque lancement, jamais commités à la main — ce script est la seule source) :
  webapp/src/data/societes.json   toutes les sociétés (niveaux 1+ et catalogue), colonnes brutes
  webapp/src/data/mere.json       la ligne Eurazeo (niveau 0)
  webapp/src/data/liens.json      liens internes (plusieurs détenteurs d'une même société)
  webapp/src/data/catalogue.json  catalogue brut eurazeo.com (pour la couche "Catalogue" du graphe)
  webapp/src/data/evenements.json cessions repérées sur le web (pour la fiche société)
  webapp/src/data/meta.json       date de collecte, niveau max, horodatage d'export
"""
import json
import math
import sys
from pathlib import Path

RACINE = Path(__file__).resolve()
PROJET = Path("/mnt/user-data/uploads/graphe_capitalistique/graphe_capitalistique")
# Si lancé depuis le vrai dépôt (device_bash), PROJET est le dossier courant.
if not PROJET.exists():
    PROJET = Path.cwd()

sys.path.insert(0, str(PROJET / "dashboard"))

import pandas as pd  # noqa: E402
from lib import data, graphe  # noqa: E402  (scoring PAS importé : voir docstring)

SORTIE = PROJET / "webapp" / "src" / "data"
SORTIE.mkdir(parents=True, exist_ok=True)


def _nan_to_none(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    if pd.isna(v) if not isinstance(v, (list, dict)) else False:
        return None
    return v


def df_vers_json(df: pd.DataFrame) -> list:
    """DataFrame -> liste de dicts JSON-safe (NaN/NaT -> null), via pandas (gère tous les types)."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def main():
    # --- sociétés : charger() SANS scoring.appliquer() (le scoring est calculé en JS, live) ---
    df = data.charger((
        data.CHEMIN.stat().st_mtime,
        tuple((f.name, f.stat().st_mtime) for f in data.fichiers_niveaux()),
        data.FICHIER_EVENEMENTS.stat().st_mtime if data.FICHIER_EVENEMENTS.exists() else 0,
    ))
    cat = data.lignes_catalogue(df)
    ensemble = pd.concat([df, cat], ignore_index=True) if len(cat) else df

    mere = ensemble[ensemble["niveau"] == 0]
    toutes = ensemble[ensemble["niveau"] != 0].copy()

    (SORTIE / "societes.json").write_text(
        json.dumps(df_vers_json(toutes), ensure_ascii=False), encoding="utf-8")
    (SORTIE / "mere.json").write_text(
        json.dumps(df_vers_json(mere).__getitem__(0) if len(mere) else None, ensure_ascii=False)
        if len(mere) else "null", encoding="utf-8")

    # --- liens internes (plusieurs détenteurs d'une même société, niveau 2+) ---
    liens = data._charger_liens(tuple((f.name, f.stat().st_mtime) for f in data.fichiers_liens()))
    (SORTIE / "liens.json").write_text(json.dumps(df_vers_json(liens), ensure_ascii=False), encoding="utf-8")

    # --- catalogue brut (pour preparer_catalogue() côté JS : description, secteur, région marketing...) ---
    catalogue_brut = data.charger_catalogue(
        data.FICHIER_CATALOGUE.stat().st_mtime if data.FICHIER_CATALOGUE.exists() else 0)
    (SORTIE / "catalogue.json").write_text(
        json.dumps(df_vers_json(catalogue_brut), ensure_ascii=False), encoding="utf-8")

    # --- événements web (cessions repérées) ---
    evenements = data.charger_evenements(
        data.FICHIER_EVENEMENTS.stat().st_mtime if data.FICHIER_EVENEMENTS.exists() else 0)
    (SORTIE / "evenements.json").write_text(
        json.dumps(df_vers_json(evenements), ensure_ascii=False), encoding="utf-8")

    # --- méta ---
    import datetime as dt
    meta = {
        "date_collecte_max": str(toutes["date_collecte"].max()) if len(toutes) else None,
        "niveau_max": int(pd.concat([toutes["niveau"], mere["niveau"]]).max()) if len(toutes) or len(mere) else 1,
        "exporte_le": dt.datetime.now().isoformat(timespec="seconds"),
        "nb_societes": int(len(toutes)),
    }
    (SORTIE / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK : {len(toutes)} sociétés -> {SORTIE}")
    for f in sorted(SORTIE.glob("*.json")):
        print(f"  {f.name:20s} {f.stat().st_size:>9,d} octets".replace(",", " "))


if __name__ == "__main__":
    main()
