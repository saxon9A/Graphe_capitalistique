#!/usr/bin/env python3
"""
Sonde NIVEAU 2 : est-ce que ton compte INPI donne accès aux COMPTES ANNUELS
d'une holding (ex. LH PAYFIT), et ces comptes citent-ils la société détenue ?

Lecture seule. Ne modifie aucun fichier existant, n'écrit que :
  sortie/inpi_brut/attachments_<siren>.json   (réponse brute de l'INPI)
  sortie/inpi_comptes/<siren>/<id>.pdf        (le dernier compte annuel public)

Usage :
    python sonde_comptes_inpi.py              # LH PAYFIT (851239566)
    python sonde_comptes_inpi.py 833351570    # LH DOCTOLIB

Le verdict final dit clairement si la méthode est exploitable ou non.
"""

import json
import re
import sys

import requests

from src import api_inpi_actes, config

MOTS = re.compile(r"participation|filiale|titres? de|immobilisations? financi|% du capital|capital d[eu]", re.I)


def main():
    siren = sys.argv[1] if len(sys.argv) > 1 else "851239566"
    print(f"=== Sonde comptes annuels INPI pour le SIREN {siren} ===\n")

    token = api_inpi_actes._login()
    if not token:
        print("✗ Connexion INPI impossible (identifiants absents ou refusés dans .env).")
        return
    print("✓ Connexion INPI OK")
    entetes = {"Authorization": f"Bearer {token}"}

    url = f"{config.INPI_BASE_URL}/api/companies/{siren}/attachments"
    r = requests.get(url, headers=entetes, timeout=config.TIMEOUT_DEFAUT)
    print(f"GET /attachments -> HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"✗ Pièces jointes inaccessibles : {r.text[:300]}")
        print("\nVERDICT : méthode comptes annuels INDISPONIBLE avec ce compte.")
        return

    data = r.json()
    dossier_brut = config.OUTPUT_DIR / "inpi_brut"
    dossier_brut.mkdir(exist_ok=True)
    (dossier_brut / f"attachments_{siren}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Rubriques reçues :", {k: (len(v) if isinstance(v, list) else type(v).__name__) for k, v in data.items()})

    bilans = data.get("bilans") or []
    if not bilans:
        print("\nVERDICT : aucun compte annuel déposé/public pour cette société. Méthode inutilisable ici.")
        return

    for b in bilans[:5]:
        print("  bilan :", {k: b.get(k) for k in ("id", "dateCloture", "dateDepot", "typeBilan", "confidentiality") if k in b})

    cible = next((b for b in bilans if str(b.get("confidentiality", "Public")).lower().startswith("public")), None)
    if not cible:
        print("\nVERDICT : tous les comptes sont confidentiels. Méthode inutilisable ici.")
        return

    bid = cible.get("id")
    d = requests.get(f"{config.INPI_BASE_URL}/api/bilans/{bid}/download", headers=entetes,
                     timeout=config.TIMEOUT_DEFAUT * 2)
    print(f"\nGET /bilans/{bid}/download -> HTTP {d.status_code}, {len(d.content)} octets")
    if d.status_code != 200:
        print("\nVERDICT : la liste est visible mais pas le téléchargement. Méthode indisponible.")
        return

    dest = config.OUTPUT_DIR / "inpi_comptes" / siren
    dest.mkdir(parents=True, exist_ok=True)
    pdf_path = dest / f"{bid}.pdf"
    pdf_path.write_bytes(d.content)

    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        textes = [(p.extract_text() or "") for p in pdf.pages]
    total = sum(len(t) for t in textes)
    print(f"PDF : {len(textes)} page(s), {total} caractères de texte")
    if total < 200:
        print("\nVERDICT : PDF scanné (image), sans texte lisible. Lecture automatique impossible.")
        return

    print("\nLignes mentionnant des participations / filiales / titres :")
    n = 0
    for i, t in enumerate(textes, 1):
        for ligne in t.split("\n"):
            if MOTS.search(ligne):
                print(f"  p.{i}: {ligne.strip()[:150]}")
                n += 1
                if n >= 40:
                    break
        if n >= 40:
            break
    print(f"\nVERDICT : comptes lisibles ({n} ligne(s) pertinente(s)). "
          f"Regarde ci-dessus : si le nom de la société détenue apparaît, la méthode est exploitable.")
    print(f"PDF sauvegardé : {pdf_path}")


if __name__ == "__main__":
    main()
