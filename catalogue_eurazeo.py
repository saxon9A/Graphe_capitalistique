#!/usr/bin/env python3
"""
Importe le catalogue des investissements affiché sur eurazeo.com/fr/investissements
(scrapé puis rapproché d'une fiche Sirene par nom - fichier fourni en entrée, PAS collecté
automatiquement ici) et produit sortie/portefeuille_eurazeo_catalogue.csv, copié dans le
dashboard.

Contrairement aux niveaux 1, 2, 3... (chaîne de détention lue dans les comptes annuels
déposés à l'INPI, part du capital connue), ce catalogue vient directement du site
institutionnel d'Eurazeo : c'est la liste que le groupe donne lui-même de ses participations
(actuelles ET anciennes), MAIS :
  - aucun pourcentage de détention n'y est publié ;
  - aucune chaîne de détention (quelle holding détient quoi) n'y figure : on ne sait pas par
    quel véhicule Eurazeo détient chaque société ;
  - le rapprochement avec une fiche Sirene (SIREN, adresse, effectif) se fait par similarité de
    NOM SEUL, sans croiser le secteur ni le pays : certains rapprochements sont donc faux,
    y compris quand le score de similarité est de 100 % et que la colonne « Vérification
    nécessaire » dit « Non ». Exemple vérifié : « Mapal » (Eurazeo, Madrid) et « Planet »
    (Eurazeo, ex-Fintrax, paiements) sont tous deux rapprochés avec un score de 100 % à de
    petites sociétés françaises sans rapport (adresse en Allemagne pour l'une, en Vendée pour
    l'autre). CE RAPPROCHEMENT N'EST DONC JAMAIS AFFICHÉ COMME UNE DONNÉE CONFIRMÉE dans le
    dashboard : c'est une piste à vérifier à la main, toujours présentée comme telle.

Usage :
    python catalogue_eurazeo.py chemin/vers/le_scrape.csv

Colonnes attendues en entrée (export du scrape de l'utilisateur) :
    nom, expertise_et_description, statut, date_investissement, secteur, region, site_web,
    url_fiche, source_page, SIREN, Nom légal, Adresse, Code postal, Commune, Tranche effectif,
    État administratif, Score correspondance, Vérification nécessaire
"""

import csv
import re
import shutil
import sys
import unicodedata
from datetime import date
from pathlib import Path

from src import config

SORTIE = config.OUTPUT_DIR / "portefeuille_eurazeo_catalogue.csv"
CHAMPS = ["nom", "cles", "statut", "date_investissement", "description", "secteur", "region",
          "site_web", "siren", "nom_legal", "adresse", "code_postal", "commune",
          "tranche_effectif", "etat_administratif", "score_correspondance",
          "verification_necessaire", "source", "url", "verifie_le"]

STRATEGIES = [
    "Healthcare - Kurma Partners", "Venture - Smart city", "Venture - Digital", "Corporate Financing",
    "Secondaries & Mandates", "Asset-based Finance", "Infrastructures durables", "Planetary Boundaries",
    "Direct Lending", "Leveraged Loans", "Private Debt", "Real Estate", "Infrastructure", "Elevate",
    "Growth", "Capital", "EPBF",
]
RE_STRATEGIE = re.compile(r"\s(" + "|".join(re.escape(s) for s in STRATEGIES) + r")\s*$")


def normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def nettoyer_description(nom, blob):
    """Le scrape colle nom + description + stratégie + bloc de métadonnées répétées dans un seul
    champ texte. On retire le nom en tête et tout ce qui suit « État » (déjà dans des colonnes à
    part), puis on essaie de détacher le libellé de stratégie en fin de chaîne."""
    blob = (blob or "").strip()
    if blob.lower().startswith(nom.lower()):
        blob = blob[len(nom):].strip()
    for marqueur in (" État ", " Etat "):
        idx = blob.find(marqueur)
        if idx != -1:
            blob = blob[:idx].strip()
            break
    m = RE_STRATEGIE.search(blob)
    if m:
        return blob[: m.start()].strip(), m.group(1)
    return blob, ""


def main():
    if len(sys.argv) < 2:
        print("Usage : python catalogue_eurazeo.py chemin/vers/le_scrape.csv")
        return
    entree = Path(sys.argv[1])
    if not entree.exists():
        print(f"Fichier introuvable : {entree}")
        return
    with open(entree, encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f))

    aujourdhui = date.today().isoformat()
    out = []
    for r in lignes:
        nom = r["nom"].strip()
        description, strategie = nettoyer_description(nom, r.get("expertise_et_description", ""))
        desc_complete = f"{strategie} — {description}" if strategie else description
        out.append({
            "nom": nom, "cles": normaliser(nom),
            "statut": r.get("statut", "").strip(),
            "date_investissement": r.get("date_investissement", "").strip(),
            "description": desc_complete,
            "secteur": r.get("secteur", "").strip(), "region": r.get("region", "").strip(),
            "site_web": r.get("site_web", "").strip(),
            "siren": r.get("SIREN", "").strip(), "nom_legal": r.get("Nom légal", "").strip(),
            "adresse": r.get("Adresse", "").strip(), "code_postal": r.get("Code postal", "").strip(),
            "commune": r.get("Commune", "").strip(), "tranche_effectif": r.get("Tranche effectif", "").strip(),
            "etat_administratif": r.get("État administratif", "").strip(),
            "score_correspondance": r.get("Score correspondance", "").strip(),
            "verification_necessaire": r.get("Vérification nécessaire", "").strip(),
            "source": "Catalogue des investissements, eurazeo.com (scrapé puis rapproché Sirene par similarité de nom)",
            "url": r.get("source_page", "").strip() or "https://www.eurazeo.com/fr/investissements",
            "verifie_le": aujourdhui,
        })

    with open(SORTIE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS, delimiter=";")
        w.writeheader()
        w.writerows(out)
    dossier_dash = config.BASE_DIR / "dashboard" / "data"
    if dossier_dash.exists():
        shutil.copy(SORTIE, dossier_dash / SORTIE.name)
        print(f"Copié aussi dans {dossier_dash}")

    avec_siren = sum(1 for l in out if l["siren"])
    confiants = sum(1 for l in out if l["siren"] and l["verification_necessaire"].lower() != "oui")
    print(f"=== {len(out)} sociétés du catalogue eurazeo.com -> {SORTIE} ===")
    print(f"  Avec un SIREN rapproché par le nom : {avec_siren}/{len(out)} (dont {confiants} sans "
          f"« vérification nécessaire » signalée par le rapprochement)")
    print("  Rappel : même un rapprochement à 100 % peut être faux pour un nom court ou générique "
          "(ex. « Mapal », « Planet ») : ce n'est jamais affiché comme confirmé dans le dashboard.")


if __name__ == "__main__":
    main()
