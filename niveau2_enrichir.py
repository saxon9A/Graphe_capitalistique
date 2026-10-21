#!/usr/bin/env python3
"""
NIVEAU 2, étape 3 : enrichit les sociétés détenues par les holdings du niveau 1
(lues dans leurs comptes annuels par niveau2_extraire.py) et écrit
sortie/entreprises_niveau2.csv, lu par le dashboard.

  - SIREN imprimé dans les comptes  -> fiche Sirene (adresse, effectif, NAF...) ;
  - société française sans SIREN    -> recherche par nom, acceptée SEULEMENT si le nom
                                       du registre est identique ou très proche ;
  - société étrangère               -> adresse imprimée dans les comptes (position
                                       approximative sur la carte, au centre-ville).

Les 33 véhicules de fonds d'Eurazeo Global Investor (noms sans adresse ni SIREN) ne vont
pas dans le dashboard : ils sont écrits à part dans sortie/niveau2_vehicules_egi.csv.

Un champ absent de la source reste vide. Chaque ligne porte une colonne `verification`
qui dit comment l'identité a été établie.

Usage :
    python niveau2_enrichir.py
"""

import csv
import difflib
import json
import re
import shutil
import time
from datetime import date

from src import api_recherche_entreprises as recherche
import niveau2_extraire
from niveau2_extraire import SIREN_EGI, ecrire_liens_internes
from src import config, details, niveau2

CANDIDATS = config.OUTPUT_DIR / "niveau2_candidats.csv"
SORTIE = config.OUTPUT_DIR / "entreprises_niveau2.csv"
SORTIE_EGI = config.OUTPUT_DIR / "niveau2_vehicules_egi.csv"
DOSSIER_BRUT = config.OUTPUT_DIR / "sirene_brut"
FORMES = {"sas", "sa", "sarl", "se", "inc", "llc", "bv", "ltd", "limited", "corp", "the"}
RE_CP_FR = re.compile(r"\b\d{2}\s?\d{3}\b")


def _jetons(nom):
    return {t for t in niveau2.normaliser_nom(nom).split() if t not in FORMES and len(t) > 1}


def similarite(imprime: str, registre: str):
    """'identique' / 'proche' / None entre un nom imprimé et un nom du registre."""
    a, b = _jetons(imprime), _jetons(registre)
    if not a or not b:
        return None
    if a == b:
        return "identique"
    r = difflib.SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(b))).ratio()
    if r >= 0.85:
        return "proche"
    petit, grand = (a, b) if len(a) <= len(b) else (b, a)
    if petit <= grand and any(len(t) >= 4 for t in petit):
        return "proche"
    return None


def est_adresse_francaise(adresse: str) -> bool:
    return bool(adresse) and bool(RE_CP_FR.search(adresse)) and details.localiser_adresse_etrangere(adresse) is None


def recuperer_siren(siren):
    brut = recherche.get_entreprise_par_siren(siren)
    if brut:
        DOSSIER_BRUT.mkdir(exist_ok=True)
        (DOSSIER_BRUT / f"{siren}.json").write_text(json.dumps(brut, ensure_ascii=False, indent=2), encoding="utf-8")
    time.sleep(config.PAUSE_ENTRE_APPELS)
    return brut


def chercher_par_nom(nom):
    """Meilleur résultat dont le nom est identique/proche, sinon (None, None)."""
    propre = re.sub(r"\(.*?\)", " ", nom).replace("*", " ").strip()
    resultats = recherche.rechercher_par_nom(propre, 5)
    time.sleep(config.PAUSE_ENTRE_APPELS)
    meilleur = None
    for r in resultats:
        for nom_reg in {r.get("nom_complet"), r.get("nom_raison_sociale")} - {None}:
            sim = similarite(nom, nom_reg)
            if sim == "identique" or (sim == "proche" and meilleur is None):
                meilleur = (r, f"nom {sim} dans le registre : {nom_reg}")
                if sim == "identique":
                    return meilleur
    return meilleur or (None, None)


def cp_imprime(adresse):
    m = RE_CP_FR.search(adresse or "")
    return re.sub(r"\s", "", m.group(0)) if m else None


def type_relation(pct, source_type):
    if source_type == "mention" or pct in (None, ""):
        return "Participation (part non publiée)"
    p = float(pct)
    return "Filiale (> 50 %)" if p > 50 else ("Participation (10-50 %)" if p >= 10 else "Participation (< 10 %)")


def construire_ligne(c, cache, aujourdhui, niveau=2, part_detentrice=None):
    """Une ligne `entreprises_niveauN.csv` à partir d'un candidat extrait des comptes.

    `part_detentrice` : part économique d'Eurazeo dans la société détentrice (en %), pour le calcul
    de la part indirecte. Par défaut (niveau 2) : la part imprimée dans le candidat.
    """
    nom_imp, adresse = c["nom_detenue"], c["adresse_imprimee"]
    siren_imp = c["siren_imprime"]
    cle = siren_imp or niveau2.normaliser_nom(nom_imp)
    if cle not in cache:
        base, verif = None, ""
        if siren_imp:
            brut = recuperer_siren(siren_imp)
            if brut:
                base = details.ligne_depuis_api(brut)
                sim = similarite(nom_imp, base.get("nom") or "")
                if sim:
                    verif = f"SIREN imprimé dans les comptes ; nom du registre {sim} ({base.get('nom')})"
                else:
                    # on garde le nom imprimé : le SIREN imprimé est peut-être une erreur du document
                    verif = (f"⚠ SIREN imprimé dans les comptes mais nom du registre différent : "
                             f"{base.get('nom')}")
                    base["nom"] = nom_imp
            else:
                verif = "SIREN imprimé dans les comptes, fiche Sirene non récupérée"
        elif not adresse or est_adresse_francaise(adresse):
            brut, comment = chercher_par_nom(nom_imp)
            if brut:
                base = details.ligne_depuis_api(brut)
                verif = f"SIREN trouvé par le nom ; {comment}"
                cp_reg, cp_imp = base.get("code_postal"), cp_imprime(adresse)
                if cp_imp and cp_reg and cp_imp != cp_reg:
                    verif += f" ; ⚠ code postal différent (comptes {cp_imp}, registre {cp_reg})"
            else:
                verif = "SIREN non trouvé par le nom (aucun nom identique ou proche) : à saisir à la main"
        if base is None:
            geo = details.localiser_adresse_etrangere(adresse)
            if geo:
                ville, pays, lat, lon = geo
                base = {"nom": nom_imp, "pays": pays, "zone": details.ZONE_ETRANGER,
                        "adresse": adresse, "ville": ville, "latitude": lat, "longitude": lon,
                        "geo_precision": "ville", "statut_administratif": "Non vérifié (registre étranger)"}
                verif = verif or "Société étrangère : adresse imprimée dans les comptes"
            else:
                cp = cp_imprime(adresse)
                base = {"nom": nom_imp, "pays": "France" if cp else "", "adresse": adresse, "code_postal": cp,
                        "zone": details.zone_depuis_adresse("France", cp, None) if cp else details.ZONE_NON_LOCALISEE,
                        "statut_administratif": "Non vérifié"}
            base["source_enrichissement"] = "Adresse imprimée dans les comptes annuels du détenteur (INPI/RNE)"
        cache[cle] = (base, verif)
    base, verif = cache[cle]
    base = dict(base)
    pct = c["pourcentage_detention"]
    part_h = c["part_eurazeo_dans_detentrice"] if part_detentrice is None else part_detentrice
    econ = (round(float(pct) * float(part_h) / 100, 2)
            if pct not in ("", None) and part_h not in ("", None) else None)
    base.update({
        "niveau": niveau, "siren_detentrice": c["siren_detentrice"], "nom_detentrice": c["nom_detentrice"],
        "type_relation": type_relation(pct, c["source_type"]),
        "validation": ("Extrait du tableau des filiales des comptes annuels, à vérifier"
                       if c["source_type"] == "tableau" else
                       "Citée dans les notes des comptes annuels (part non publiée), à vérifier"),
        "pourcentage_detention": float(pct) if pct not in ("", None) else None,
        "part_economique_eurazeo": econ,
        "identifiant_etranger": base.get("identifiant_etranger"),
        "source_relation": c["source"], "verification": verif, "date_collecte": aujourdhui,
    })
    if not base.get("nom"):
        base["nom"] = nom_imp
    return base


def main():
    if not CANDIDATS.exists():
        print("Lance d'abord : python niveau2_extraire.py")
        return
    with open(CANDIDATS, encoding="utf-8-sig", newline="") as f:
        cands = list(csv.DictReader(f, delimiter=";"))
    cands = [c for c in cands if c["siren_detentrice"] != SIREN_EGI]
    n_liens = ecrire_liens_internes(cands, 2, config.OUTPUT_DIR / "liens_internes_niveau2.csv")
    print(f"{n_liens} lien(s) entre sociétés déjà au niveau 1 -> liens_internes_niveau2.csv (arêtes du graphe)")
    cands = [c for c in cands if not c["interne_niveau1"] and c["valide"].strip().lower() != "non"]
    egi = [c for c in cands if c["siren_detentrice"] == SIREN_EGI]
    cands = [c for c in cands if c["siren_detentrice"] != SIREN_EGI]
    if egi:
        with open(SORTIE_EGI, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(egi[0].keys()), delimiter=";")
            w.writeheader()
            w.writerows(egi)
    print(f"=== Niveau 2 : {len(cands)} société(s) détenue(s) à enrichir "
          f"({len(egi)} véhicules EGI écartés -> {SORTIE_EGI.name}) ===\n")

    aujourdhui = date.today().isoformat()
    cache, lignes = {}, []
    for i, c in enumerate(cands, 1):
        lignes.append(construire_ligne(c, cache, aujourdhui, niveau=2))
        if i % 10 == 0 or i == len(cands):
            print(f"    {i}/{len(cands)}")

    with open(SORTIE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=details.COLONNES, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)
    dossier_dash = config.BASE_DIR / "dashboard" / "data"
    if dossier_dash.exists():
        shutil.copy(SORTIE, dossier_dash / SORTIE.name)
        print(f"\nCopié aussi dans {dossier_dash}")

    avec_siren = sum(1 for l in lignes if l.get("siren"))
    geo = sum(1 for l in lignes if l.get("latitude") is not None)
    print(f"\n=== Terminé : {len(lignes)} lignes -> {SORTIE} ===")
    print(f"  Avec SIREN (fiche Sirene) : {avec_siren}/{len(lignes)}")
    print(f"  Géolocalisées             : {geo}/{len(lignes)}")
    for l in lignes:
        if l.get("verification", "").startswith("⚠") or "non trouvé" in l.get("verification", ""):
            print(f"  ⚠️  {l['nom']} (via {l['nom_detentrice']}) : {l['verification']}")


if __name__ == "__main__":
    main()
