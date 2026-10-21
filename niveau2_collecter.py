#!/usr/bin/env python3
"""
NIVEAU 2, étape 1 : collecte des comptes annuels des sociétés du niveau 1.

Pour chaque société française de sortie/entreprises_detaillees.csv :
  - liste ses pièces jointes INPI (/api/companies/{siren}/attachments) ;
  - télécharge le compte annuel PUBLIC le plus récent (PDF) ;
  - en extrait le texte, page par page.

Ne fait AUCUNE interprétation : il rassemble la matière première. L'extraction
des sociétés détenues (nom, % de détention) se fait ensuite, en lisant ces textes.

Produit :
  sortie/inpi_comptes/<siren>/<id>.pdf      le compte annuel
  sortie/inpi_comptes/<siren>/texte.txt     son texte, page par page
  sortie/niveau2_collecte.csv               un état par société (ok / aucun bilan / ...)

Relançable sans risque : les PDF déjà téléchargés ne sont pas retéléchargés.

Usage :
    python niveau2_collecter.py
"""

import csv
import sys
import time

import requests

from src import api_inpi_actes, config

FICHIER_ENTREE = config.OUTPUT_DIR / "entreprises_detaillees.csv"
FICHIER_ETAT = config.OUTPUT_DIR / "niveau2_collecte.csv"
DOSSIER = config.OUTPUT_DIR / "inpi_comptes"


def bilan_le_plus_recent(attachments: dict):
    """(bilan public le plus récent, état) ; état explique l'absence éventuelle."""
    bilans = attachments.get("bilans") or []
    if not bilans:
        return None, "aucun compte annuel déposé"
    publics = [b for b in bilans if str(b.get("confidentiality", "Public")).lower().startswith("public")]
    if not publics:
        return None, "comptes confidentiels"
    return max(publics, key=lambda b: b.get("dateCloture") or ""), "ok"


def texte_par_page(chemin_pdf) -> tuple[str, int, int]:
    import pdfplumber
    morceaux, nb_car = [], 0
    with pdfplumber.open(chemin_pdf) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            t = page.extract_text() or ""
            nb_car += len(t)
            morceaux.append(f"=== page {i} ===\n{t}")
        return "\n".join(morceaux), len(pdf.pages), nb_car


def collecter(societes, fichier_etat):
    """Télécharge et lit le dernier compte annuel public de chaque société {siren, nom, ...}.

    Réutilisé par descendre.py pour les niveaux 3 et suivants. Renvoie la liste des états.
    """
    token = api_inpi_actes._login()
    if not token:
        print("Connexion INPI impossible (identifiants du .env).")
        sys.exit(1)
    entetes = {"Authorization": f"Bearer {token}"}

    etats = []
    for i, s in enumerate(societes, 1):
        siren, nom = s["siren"], s["nom"]
        etat = {"siren": siren, "nom": nom, "id_bilan": "", "date_cloture": "", "pages": "", "caracteres": "",
                "statut": ""}
        try:
            r = requests.get(f"{config.INPI_BASE_URL}/api/companies/{siren}/attachments",
                             headers=entetes, timeout=config.TIMEOUT_DEFAUT)
            if r.status_code != 200:
                etat["statut"] = f"pièces jointes : HTTP {r.status_code}"
            else:
                bilan, motif = bilan_le_plus_recent(r.json())
                if not bilan:
                    etat["statut"] = motif
                else:
                    bid = bilan["id"]
                    etat.update(id_bilan=bid, date_cloture=bilan.get("dateCloture", ""))
                    dossier = DOSSIER / siren
                    dossier.mkdir(parents=True, exist_ok=True)
                    pdf_path = dossier / f"{bid}.pdf"
                    if not pdf_path.exists():
                        d = requests.get(f"{config.INPI_BASE_URL}/api/bilans/{bid}/download",
                                         headers=entetes, timeout=config.TIMEOUT_DEFAUT * 3)
                        if d.status_code == 200:
                            pdf_path.write_bytes(d.content)
                        else:
                            etat["statut"] = f"téléchargement : HTTP {d.status_code}"
                    if pdf_path.exists():
                        texte, pages, nb_car = texte_par_page(pdf_path)
                        (dossier / "texte.txt").write_text(texte, encoding="utf-8")
                        etat.update(pages=pages, caracteres=nb_car,
                                    statut="ok" if nb_car > 200 else "PDF scanné (pas de texte)")
        except Exception as exc:  # une société en échec ne doit pas arrêter les autres
            etat["statut"] = f"erreur : {exc}"[:150]
        etats.append(etat)
        print(f"  {i:2}/{len(societes)}  {nom[:32]:32}  {etat['date_cloture'] or '—':10}  {etat['statut']}")
        time.sleep(config.PAUSE_ENTRE_APPELS)

    with open(fichier_etat, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(etats[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(etats)
    return etats


def main():
    if not FICHIER_ENTREE.exists():
        print("Fichier introuvable : lance d'abord python enrichir_details.py")
        sys.exit(1)
    with open(FICHIER_ENTREE, encoding="utf-8-sig", newline="") as f:
        societes = [r for r in csv.DictReader(f, delimiter=";") if r.get("niveau") == "1" and r.get("siren")]
    print(f"=== Collecte des comptes annuels : {len(societes)} société(s) françaises ===\n")
    etats = collecter(societes, FICHIER_ETAT)

    ok = sum(1 for e in etats if e["statut"] == "ok")
    print(f"\n=== {ok}/{len(etats)} compte(s) annuel(s) récupéré(s) et lisible(s) -> {FICHIER_ETAT} ===")
    autres = [e for e in etats if e["statut"] != "ok"]
    for e in autres:
        print(f"  ⚠️  {e['nom']} : {e['statut']}")



if __name__ == "__main__":
    main()
