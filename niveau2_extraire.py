#!/usr/bin/env python3
"""
NIVEAU 2, étape 2 : lit les comptes annuels collectés par niveau2_collecter.py
et en extrait les sociétés détenues par chaque société du niveau 1.

Hors ligne (aucun appel réseau), rapide, relançable à volonté.

Produit :
  sortie/niveau2_candidats.csv   une ligne par société détenue trouvée
  sortie/niveau2_resume.csv      une ligne par société du niveau 1 (ce qu'on a trouvé, ou pourquoi rien)

Deux types de résultats, bien distingués dans la colonne `source_type` :
  - « tableau »  : nom + pourcentage imprimés dans le Tableau des filiales et participations ;
  - « mention »  : société citée dans les notes (ex. « participation minoritaire au capital de
                   Doctolib SAS »), SANS pourcentage, et parfois déjà cédée.
Un résultat est un CANDIDAT extrait d'un PDF, pas une donnée certifiée : la colonne
`ligne_brute` montre le texte exact dont il vient.

Usage :
    python niveau2_extraire.py
"""

import csv
import difflib
import shutil

from src import config, niveau2

SIREN_EGI = "414908624"   # Eurazeo Global Investor : véhicules de fonds aux noms illisibles dans le PDF
DOSSIER = config.OUTPUT_DIR / "inpi_comptes"
FICHIER_N1 = config.OUTPUT_DIR / "entreprises_detaillees.csv"
FICHIER_COLLECTE = config.OUTPUT_DIR / "niveau2_collecte.csv"
SORTIE_CANDIDATS = config.OUTPUT_DIR / "niveau2_candidats.csv"
SORTIE_RESUME = config.OUTPUT_DIR / "niveau2_resume.csv"

CHAMPS = ["siren_detentrice", "nom_detentrice", "part_eurazeo_dans_detentrice", "nom_detenue",
          "pourcentage_detention", "siren_imprime", "adresse_imprimee", "source_type", "source",
          "page", "interne_niveau1", "ligne_brute", "valide"]


def compact(nom):
    """Nom sans espace ni ponctuation, pour comparer 'Deweys' et "Dewey's Bakery"."""
    return "".join(ch for ch in niveau2.normaliser_nom(nom) if ch.isalnum())


def lire(chemin):
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def trouver_interne(nom, siren, niveau1):
    """Une société déjà présente au niveau 1 (SIREN identique, sinon nom quasi identique) ?"""
    if siren and siren in niveau1["par_siren"]:
        return niveau1["par_siren"][siren]
    n = niveau2.normaliser_nom(nom)
    meilleur, score = None, 0.0
    for nn, s in niveau1["par_nom"].items():
        r = difflib.SequenceMatcher(None, n, nn).ratio()
        if r > score:
            meilleur, score = s, r
    return meilleur if score >= 0.88 else ""


CHAMPS_LIENS = ["niveau", "siren_detentrice", "nom_detentrice", "siren_detenue", "nom_detenue",
                "pourcentage_detention", "source_type", "source", "ligne_brute"]


def ecrire_liens_internes(candidats, niveau, chemin):
    """Liens entre deux sociétés DÉJÀ présentes dans le graphe (ex. un véhicule Carryco qui détient 12 %
    d'une holding Legendre déjà au niveau 1). Pas de nouvelle société : seulement une arête de plus."""
    liens = [{"niveau": niveau, "siren_detentrice": c["siren_detentrice"], "nom_detentrice": c["nom_detentrice"],
              "siren_detenue": c["interne_niveau1"], "nom_detenue": c["nom_detenue"],
              "pourcentage_detention": c["pourcentage_detention"], "source_type": c["source_type"],
              "source": c["source"], "ligne_brute": c["ligne_brute"]}
             for c in candidats if c["interne_niveau1"] and c["valide"].strip().lower() != "non"
             and c["interne_niveau1"] != c["siren_detentrice"]]
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS_LIENS, delimiter=";")
        w.writeheader()
        w.writerows(liens)
    dossier_dash = config.BASE_DIR / "dashboard" / "data"
    if dossier_dash.exists():
        shutil.copy(chemin, dossier_dash / chemin.name)
    return len(liens)


def reprendre_validations(candidats, chemin):
    """Reporte la colonne `valide` saisie à la main dans une version précédente du fichier."""
    if not chemin.exists():
        return 0
    anciennes = {(r["siren_detentrice"], r["nom_detenue"], r["ligne_brute"]): r.get("valide", "")
                 for r in lire(chemin)}
    n = 0
    for c in candidats:
        v = anciennes.get((c["siren_detentrice"], c["nom_detenue"], c["ligne_brute"]), "")
        if v:
            c["valide"] = v
            n += 1
    return n


def candidats_depuis_texte(siren, nom, part_detentrice, texte, exercice, niveau_connu):
    """Candidats (sociétés détenues) lus dans le texte des comptes d'une société.

    Renvoie (candidats, nb tableau, nb mentions, seuil). Sert aussi à descendre.py (niveaux 3+).
    `niveau_connu` : {"par_siren": {...}, "par_nom": {...}} des sociétés déjà dans le graphe.
    """
    tab = niveau2.extraire_tableau(texte)
    noms_tab = [compact(t["nom"]) for t in tab]
    # une mention n'est gardée que si le tableau ne nomme pas déjà cette société
    # ("Deweys" / "Dewey's Bakery" ; "IES" / "IES Groupe")
    ment = [m for m in niveau2.extraire_mentions(texte)
            if not any(nt.startswith(compact(m["nom"])) or compact(m["nom"]).startswith(nt) for nt in noms_tab)]
    seuil = niveau2.extraire_seuil(texte)
    candidats = []
    for typ, liste in (("tableau", tab), ("mention", ment)):
        for c in liste:
            candidats.append({
                "siren_detentrice": siren, "nom_detentrice": nom,
                "part_eurazeo_dans_detentrice": part_detentrice,
                "nom_detenue": c["nom"],
                "pourcentage_detention": "" if c["pourcentage"] is None else c["pourcentage"],
                "siren_imprime": c["siren_imprime"], "adresse_imprimee": c["adresse"],
                "source_type": typ,
                "source": f"Comptes annuels {exercice} déposés au RNE (INPI), "
                          + ("Tableau des filiales et participations" if typ == "tableau" else "notes de l'annexe"),
                "page": c["page"],
                "interne_niveau1": trouver_interne(c["nom"], c["siren_imprime"], niveau_connu),
                "ligne_brute": c["ligne_brute"], "valide": "",
            })
    return candidats, len(tab), len(ment), seuil


def constat_depuis(nb_tab, nb_ment, seuil):
    if nb_tab or nb_ment:
        return f"{nb_tab} dans le tableau, {nb_ment} citée(s) dans les notes"
    if seuil:
        return "aucune société nommée : le document dit ne détenir aucune participation à plus de 10 %"
    return "aucune société détenue repérée automatiquement (à lire à la main si besoin)"


def main():
    if not FICHIER_COLLECTE.exists():
        print("Lance d'abord : python niveau2_collecter.py")
        return
    n1 = [r for r in lire(FICHIER_N1) if r.get("niveau") == "1"]
    niveau1 = {"par_siren": {r["siren"]: r["siren"] for r in n1 if r.get("siren")},
               "par_nom": {niveau2.normaliser_nom(r["nom"]): r["siren"] for r in n1 if r.get("siren")}}
    part_eurazeo = {r["siren"]: r.get("pourcentage_detention", "") for r in n1}
    dates = {r["siren"]: r.get("date_cloture", "") for r in lire(FICHIER_COLLECTE)}

    candidats, resume = [], []
    for r in n1:
        siren, nom = r.get("siren"), r["nom"]
        if not siren:
            continue
        chemin = DOSSIER / siren / "texte.txt"
        if not chemin.exists():
            resume.append({"siren": siren, "nom": nom, "comptes": "", "tableau": 0, "mentions": 0,
                           "constat": "pas de texte lisible (compte scanné, absent ou ancien)"})
            continue
        texte = chemin.read_text(encoding="utf-8")
        exercice = dates.get(siren, "")
        cands, nb_tab, nb_ment, seuil = candidats_depuis_texte(siren, nom, part_eurazeo.get(siren, ""), texte,
                                                              exercice, niveau1)
        candidats.extend(cands)
        resume.append({"siren": siren, "nom": nom, "comptes": exercice, "tableau": nb_tab,
                       "mentions": nb_ment, "constat": constat_depuis(nb_tab, nb_ment, seuil)})

    repris = reprendre_validations(candidats, SORTIE_CANDIDATS)
    if repris:
        print(f"  {repris} validation(s) saisie(s) à la main conservée(s)")
    with open(SORTIE_CANDIDATS, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS, delimiter=";")
        w.writeheader()
        w.writerows(candidats)
    with open(SORTIE_RESUME, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(resume[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(resume)

    n_liens = ecrire_liens_internes([c for c in candidats if c["siren_detentrice"] != SIREN_EGI], 2,
                                    config.OUTPUT_DIR / "liens_internes_niveau2.csv")
    print(f"  {n_liens} lien(s) entre sociétés déjà au niveau 1 -> liens_internes_niveau2.csv (arêtes du graphe)")
    ext = [c for c in candidats if not c["interne_niveau1"]]
    print(f"=== {len(candidats)} société(s) détenue(s) trouvée(s) -> {SORTIE_CANDIDATS} ===")
    print(f"  dont déjà au niveau 1 (ex. parts des Carryco dans les LH) : {len(candidats) - len(ext)}")
    print(f"  nouvelles (niveau 2)   : {len(ext)}  "
          f"({sum(1 for c in ext if c['source_type'] == 'tableau')} avec pourcentage, "
          f"{sum(1 for c in ext if c['source_type'] == 'mention')} citées sans pourcentage)")
    vides = [r for r in resume if not r["tableau"] and not r["mentions"]]
    print(f"  sociétés du niveau 1 sans société détenue repérée : {len(vides)}/{len(resume)} -> {SORTIE_RESUME}")


if __name__ == "__main__":
    main()
