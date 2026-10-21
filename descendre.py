#!/usr/bin/env python3
"""
DESCENDRE d'un niveau de plus (niveau 3, 4, ...) : les sociétés détenues par les sociétés du niveau précédent.

    python descendre.py 3            # niveau 3 : lit les comptes des holdings françaises du niveau 2
    python descendre.py 4            # puis niveau 4, etc.
    python descendre.py 3 --tous     # explore aussi les sociétés qui ne sont pas des holdings
    python descendre.py 3 --etape extraire   # une seule étape : collecter | extraire | enrichir

Même méthode que le niveau 2 (comptes annuels déposés au RNE, « Tableau des filiales et participations »),
en trois étapes enchaînées :
  1. collecte des comptes annuels (réseau, INPI)  -> sortie/niveauN_collecte.csv
  2. extraction des sociétés détenues (hors ligne) -> sortie/niveauN_candidats.csv, niveauN_resume.csv
  3. enrichissement (réseau, Sirene)               -> sortie/entreprises_niveauN.csv (+ copie dans dashboard/data)
  (l'étape 2 écrit aussi sortie/liens_internes_niveauN.csv : liens vers des sociétés DÉJÀ dans le graphe,
   arêtes en plus dans le graphe du dashboard)

Qui est exploré ? Seulement les sociétés FRANÇAISES (SIREN connu, donc comptes consultables) classées holding,
fonds ou siège social (NAF 64.20Z, 64.30Z, 66.30Z, 70.10Z), non cessées. Les sociétés opérationnelles
(Doctolib, Payfit...) ne sont pas explorées par défaut : leurs comptes sont longs et leurs filiales ne sont plus
des « portefeuilles ». Les sociétés étrangères (LLC américaines, véhicules luxembourgeois...) n'ont pas de
comptes consultables ici : la descente s'arrête à elles. Le fichier sortie/niveauN_parents.csv dit, pour chaque
société du niveau précédent, pourquoi elle a été explorée ou non.

Part indirecte d'Eurazeo (calcul) = part de la société dans la détenue × somme des parts indirectes connues
de la société détentrice (tous les chemins identifiés). Seuls les chemins lus dans les documents comptent :
si un chemin manque, la vraie part est plus grande.

Relançable : les PDF déjà téléchargés ne sont pas retéléchargés ; vos `valide=non` dans niveauN_candidats.csv
sont conservés à la ré-extraction et appliqués à l'enrichissement suivant.
"""

import argparse
import csv
import shutil
import sys
from datetime import date

import niveau2_collecter as collecte
import niveau2_enrichir as enrichissement
import niveau2_extraire as extraction
from src import config, niveau2

HOLDING_NAF = {"64.20Z", "64.30Z", "66.30Z", "70.10Z"}
SIREN_EURAZEO = "692030992"
SIREN_EGI = extraction.SIREN_EGI
DOSSIER = config.OUTPUT_DIR / "inpi_comptes"
CHAMPS_PARENTS = ["siren", "nom", "naf_code", "zone", "statut_administratif", "part_indirecte_connue",
                  "decision", "motif"]


def lire(chemin):
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def nombre(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def charger_connus(niveau):
    """Toutes les sociétés déjà dans le graphe (niveaux 1 à niveau-1), pour repérer les liens internes."""
    lignes = [r for r in lire(config.OUTPUT_DIR / "entreprises_detaillees.csv") if r.get("niveau") == "1"]
    for n in range(2, niveau):
        chemin = config.OUTPUT_DIR / f"entreprises_niveau{n}.csv"
        if chemin.exists():
            lignes += lire(chemin)
    sirens = {r["siren"] for r in lignes if r.get("siren")} - {SIREN_EURAZEO}
    return {"par_siren": {s: s for s in sirens},
            "par_nom": {niveau2.normaliser_nom(r["nom"]): r["siren"] for r in lignes if r.get("siren")
                        and r["siren"] != SIREN_EURAZEO}}, sirens


def choisir_parents(niveau, tous):
    """(parents à explorer, tableau de décisions) à partir des sociétés du niveau précédent."""
    chemin = config.OUTPUT_DIR / f"entreprises_niveau{niveau - 1}.csv"
    if not chemin.exists():
        print(f"Fichier introuvable : {chemin.name}. Lance d'abord le niveau {niveau - 1}.")
        sys.exit(1)
    lignes = lire(chemin)
    par_siren, sans_siren = {}, []
    for r in lignes:
        if not r.get("siren"):
            sans_siren.append(r)
        else:
            par_siren.setdefault(r["siren"], []).append(r)

    decisions, parents = [], []

    def noter(r, part, decision, motif):
        decisions.append({"siren": r.get("siren", ""), "nom": r["nom"], "naf_code": r.get("naf_code", ""),
                          "zone": r.get("zone", ""), "statut_administratif": r.get("statut_administratif", ""),
                          "part_indirecte_connue": "" if part is None else part, "decision": decision,
                          "motif": motif})

    for siren, rows in par_siren.items():
        r = rows[0]
        parts = [nombre(x.get("part_economique_eurazeo")) for x in rows]
        parts = [p for p in parts if p is not None]
        part = round(min(sum(parts), 100.0), 2) if parts else None
        if siren == SIREN_EGI:
            noter(r, part, "non exploré", "véhicules du fonds EGI : noms illisibles dans le PDF")
        elif r.get("zone") == "Étranger" or r.get("pays") not in ("", "France", None):
            noter(r, part, "non exploré", "société étrangère : comptes non consultables ici")
        elif "cess" in (r.get("statut_administratif") or "").lower():
            noter(r, part, "non exploré", "société cessée")
        elif not tous and r.get("naf_code") not in HOLDING_NAF:
            noter(r, part, "non exploré",
                  "pas une holding (NAF " + (r.get("naf_code") or "inconnu") + ") ; --tous pour l'explorer quand même")
        else:
            noter(r, part, "exploré", "")
            parents.append({"siren": siren, "nom": r["nom"], "part": part})
    for r in sans_siren:
        if r.get("zone") == "Étranger" or r.get("pays") not in ("", "France", None):
            noter(r, None, "non exploré", "société étrangère : comptes non consultables ici")
        else:
            noter(r, None, "non exploré",
                  "SIREN non retrouvé dans le registre : comptes inaccessibles (à saisir à la main dans le CSV)")
    return parents, decisions


def ecrire_csv(chemin, champs, lignes):
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=champs, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)


def etape_collecter(niveau, parents):
    print(f"\n--- Étape 1/3 : comptes annuels de {len(parents)} société(s) ---\n")
    etats = collecte.collecter([{"siren": p["siren"], "nom": p["nom"]} for p in parents],
                               config.OUTPUT_DIR / f"niveau{niveau}_collecte.csv")
    ok = sum(1 for e in etats if e["statut"] == "ok")
    print(f"\n  {ok}/{len(etats)} compte(s) lisible(s)")
    for e in etats:
        if e["statut"] != "ok":
            print(f"  ⚠️  {e['nom']} : {e['statut']}")


def etape_extraire(niveau, parents, connus):
    print("\n--- Étape 2/3 : lecture des comptes (hors ligne) ---\n")
    fichier_collecte = config.OUTPUT_DIR / f"niveau{niveau}_collecte.csv"
    dates = {r["siren"]: r.get("date_cloture", "") for r in lire(fichier_collecte)} if fichier_collecte.exists() else {}
    candidats, resume = [], []
    for p in parents:
        chemin = DOSSIER / p["siren"] / "texte.txt"
        if not chemin.exists():
            resume.append({"siren": p["siren"], "nom": p["nom"], "comptes": "", "tableau": 0, "mentions": 0,
                           "constat": "pas de texte lisible (compte scanné, absent ou ancien)"})
            continue
        cands, nb_tab, nb_ment, seuil = extraction.candidats_depuis_texte(
            p["siren"], p["nom"], "" if p["part"] is None else p["part"], chemin.read_text(encoding="utf-8"),
            dates.get(p["siren"], ""), connus)
        candidats.extend(cands)
        resume.append({"siren": p["siren"], "nom": p["nom"], "comptes": dates.get(p["siren"], ""),
                       "tableau": nb_tab, "mentions": nb_ment,
                       "constat": extraction.constat_depuis(nb_tab, nb_ment, seuil)})
    sortie = config.OUTPUT_DIR / f"niveau{niveau}_candidats.csv"
    repris = extraction.reprendre_validations(candidats, sortie)
    ecrire_csv(sortie, extraction.CHAMPS, candidats)
    if resume:
        ecrire_csv(config.OUTPUT_DIR / f"niveau{niveau}_resume.csv", list(resume[0].keys()), resume)
    n_liens = extraction.ecrire_liens_internes([c for c in candidats if c["siren_detentrice"] != SIREN_EGI], niveau,
                                               config.OUTPUT_DIR / f"liens_internes_niveau{niveau}.csv")
    nouveaux = [c for c in candidats if not c["interne_niveau1"]]
    print(f"  {len(candidats)} société(s) détenue(s) trouvée(s) -> {sortie.name}"
          + (f" ({repris} validation(s) manuelle(s) conservée(s))" if repris else ""))
    print(f"  dont {len(candidats) - len(nouveaux)} déjà dans le graphe (simples liens), "
          f"{len(nouveaux)} nouvelle(s) ({sum(1 for c in nouveaux if c['source_type'] == 'tableau')} avec pourcentage, "
          f"{sum(1 for c in nouveaux if c['source_type'] == 'mention')} citées sans pourcentage)")
    vides = [r for r in resume if not r["tableau"] and not r["mentions"]]
    print(f"  {len(vides)}/{len(resume)} société(s) explorée(s) sans société détenue repérée")


def etape_enrichir(niveau, parents):
    print("\n--- Étape 3/3 : enrichissement (Sirene) ---\n")
    chemin = config.OUTPUT_DIR / f"niveau{niveau}_candidats.csv"
    if not chemin.exists():
        print("  Lance d'abord l'étape extraire.")
        return
    cands = [c for c in lire(chemin) if c["siren_detentrice"] != SIREN_EGI]
    n_liens = sum(1 for c in cands if c["interne_niveau1"])
    nouveaux = [c for c in cands if not c["interne_niveau1"] and c["valide"].strip().lower() != "non"]
    part_parent = {p["siren"]: p["part"] for p in parents}
    print(f"  {n_liens} lien(s) vers des sociétés déjà dans le graphe, {len(nouveaux)} société(s) à enrichir")
    aujourdhui = date.today().isoformat()
    cache, lignes = {}, []
    for i, c in enumerate(nouveaux, 1):
        lignes.append(enrichissement.construire_ligne(c, cache, aujourdhui, niveau=niveau,
                                                      part_detentrice=part_parent.get(c["siren_detentrice"])))
        if i % 10 == 0 or i == len(nouveaux):
            print(f"    {i}/{len(nouveaux)}")
    sortie = config.OUTPUT_DIR / f"entreprises_niveau{niveau}.csv"
    ecrire_csv(sortie, enrichissement.details.COLONNES, lignes)
    dossier_dash = config.BASE_DIR / "dashboard" / "data"
    if dossier_dash.exists():
        shutil.copy(sortie, dossier_dash / sortie.name)
        print(f"  Copié aussi dans {dossier_dash}")
    print(f"\n  {len(lignes)} ligne(s) -> {sortie.name}; avec SIREN : {sum(1 for l in lignes if l.get('siren'))}; "
          f"géolocalisées : {sum(1 for l in lignes if l.get('latitude') is not None)}")
    for l in lignes:
        v = l.get("verification", "")
        if v.startswith("⚠") or "non trouvé" in v:
            print(f"  ⚠️  {l['nom']} (via {l['nom_detentrice']}) : {v}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("niveau", type=int, help="niveau à produire (3, 4, ...)")
    ap.add_argument("--tous", action="store_true", help="explorer aussi les sociétés qui ne sont pas des holdings")
    ap.add_argument("--etape", choices=["collecter", "extraire", "enrichir", "tout"], default="tout")
    a = ap.parse_args()
    if a.niveau < 3:
        print("Le niveau 2 se produit avec niveau2_collecter.py, niveau2_extraire.py, niveau2_enrichir.py.")
        sys.exit(1)

    connus, sirens_connus = charger_connus(a.niveau)
    parents, decisions = choisir_parents(a.niveau, a.tous)
    ecrire_csv(config.OUTPUT_DIR / f"niveau{a.niveau}_parents.csv", CHAMPS_PARENTS, decisions)
    non = [d for d in decisions if d["decision"] != "exploré"]
    print(f"=== Niveau {a.niveau} : {len(decisions)} société(s) au niveau {a.niveau - 1}, "
          f"{len(parents)} à explorer, {len(non)} laissée(s) de côté ===")
    for motif in sorted({d["motif"].split(" ;")[0] for d in non}):
        n = sum(1 for d in non if d["motif"].split(" ;")[0] == motif)
        print(f"    {n:3} non explorée(s) : {motif}")
    print(f"    (détail société par société : niveau{a.niveau}_parents.csv)")
    if not parents:
        print("Rien à explorer.")
        return

    if a.etape in ("collecter", "tout"):
        etape_collecter(a.niveau, parents)
    if a.etape in ("extraire", "tout"):
        etape_extraire(a.niveau, parents, connus)
    if a.etape in ("enrichir", "tout"):
        etape_enrichir(a.niveau, parents)
    print(f"\nEnsuite : streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
