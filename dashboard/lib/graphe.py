"""Données et page HTML du graphe interactif (réseau de détention).

Construit un graphe orienté « détenteur -> détenue » à partir des fichiers du dashboard :
  - une arête par ligne de niveau 1 (Eurazeo -> société) et par ligne de niveau 2+ (holding -> société) ;
  - les liens vers des sociétés déjà dans le graphe (liens_internes_niveau*.csv) en arêtes supplémentaires.
Aucune donnée n'est ajoutée : le graphe ne montre que ce que les fichiers contiennent.
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, theme

RACINE = "EURAZEO"
HOLDING_NAF = {"64.20Z", "64.30Z", "66.30Z", "70.10Z"}   # holdings, fonds, sièges sociaux (comme l'accueil)
ASSETS = Path(__file__).resolve().parent.parent / "assets"


def _fmt_pct(p):
    return "part non publiée" if p is None or pd.isna(p) else f"{p:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " %"


def _identifiant(r):
    if r["identifiant"]:
        return r["identifiant"]
    return "n:" + re.sub(r"[^a-z0-9]", "", r["nom"].lower())


def _nature(naf):
    if not naf:
        return "inconnue"
    return "holding" if naf in HOLDING_NAF else "societe"


def preparer(toutes: pd.DataFrame, filtre: pd.DataFrame, mere, liens: pd.DataFrame) -> dict:
    """Noeuds et arêtes à envoyer au navigateur : sociétés filtrées + leurs détenteurs (le chemin jusqu'à Eurazeo)."""
    # Le catalogue (niveau -1) est une couche à part, gérée uniquement par preparer_catalogue() :
    # on l'exclut ici pour ne jamais créer de nœud orphelin (sans chaîne de détention connue) ni de doublon
    # avec le nœud « catalogue » correspondant.
    toutes = toutes[toutes["niveau"] != -1]
    filtre = filtre[filtre["niveau"] != -1]
    t = toutes.copy()
    t["id"] = t.apply(_identifiant, axis=1)
    t["parent"] = np.where(t["niveau"] == 1, RACINE, t["siren_detentrice"])
    ids_filtre = set(filtre.apply(_identifiant, axis=1)) if len(filtre) else set()

    # --- arêtes (une par couple détenteur -> détenue) ---
    aretes, vus = [], set()
    for r in t.itertuples():
        cle = (r.parent, r.id)
        if r.parent and cle not in vus and r.parent != r.id:
            vus.add(cle)
            aretes.append({"from": r.parent, "to": r.id,
                           "pct": None if pd.isna(r.pourcentage_detention) else float(r.pourcentage_detention),
                           "interne": False})
    ids_tous = set(t["id"]) | {RACINE}
    for r in liens.itertuples():
        cle = (r.siren_detentrice, r.siren_detenue)
        if cle not in vus and r.siren_detentrice in ids_tous and r.siren_detenue in ids_tous \
                and r.siren_detentrice != r.siren_detenue:
            vus.add(cle)
            aretes.append({"from": r.siren_detentrice, "to": r.siren_detenue,
                           "pct": None if pd.isna(r.pourcentage_detention) else float(r.pourcentage_detention),
                           "interne": True})
    aretes = [a for a in aretes if a["from"] in ids_tous]

    # --- sociétés à envoyer : celles du filtre + tous leurs détenteurs ---
    parents = {}
    for a in aretes:
        parents.setdefault(a["to"], []).append(a["from"])
    garder, pile = set(ids_filtre), list(ids_filtre)
    while pile:
        for p in parents.get(pile.pop(), []):
            if p not in garder:
                garder.add(p)
                pile.append(p)
    garder.add(RACINE)

    noeuds = []
    nom_mere = mere["nom"] if mere is not None else "Eurazeo"
    nom_mere = nom_mere.title() if nom_mere.isupper() else nom_mere
    noeuds.append({"id": RACINE, "nom": nom_mere, "zone": (mere["zone"] if mere is not None else theme.ZONE_PARIS),
                   "niveau": 0, "match": True, "nature": "societe", "econ": "", "etat_web": "", "web": [], "lignes": [
                       ["Adresse du siège", mere["adresse"] if mere is not None and mere["adresse"] else ""]],
                   "titre": nom_mere + "\nSociété mère", "siren": (mere["siren"] if mere is not None else "")})
    for id_, g in t.groupby("id", sort=False):
        if id_ not in garder:
            continue
        r = g.sort_values("niveau").iloc[0]
        econ = ""
        if r["niveau"] >= 2:
            vals = g["part_economique_eurazeo"].dropna()
            if len(vals):
                econ = _fmt_pct(float(vals.sum()))
                if len(vals) > 1:
                    econ += f" (somme de {len(vals)} chemins connus)"
        lignes = [["Adresse du siège", r["adresse"]],
                  ["Activité", " · ".join(x for x in [r["naf_code"], r["naf_libelle"]] if x)],
                  ["Effectif salarié", r["tranche_effectif"]],
                  ["Statut", r["statut_administratif"]]]
        if r["niveau"] >= 2:
            lignes.append(["Identification", r["verification"]])
        web = [{"etat": e["etat"], "date": e["date"], "evenement": e["evenement"], "source": e["source"], "url": e["url"]}
               for e in data.evenements_de(r["nom"])]
        noeuds.append({"id": id_, "nom": r["nom"], "zone": r["zone"], "niveau": int(r["niveau"]),
                       "match": id_ in ids_filtre, "nature": _nature(r["naf_code"]), "econ": econ,
                       "etat_web": web[0]["etat"] if web else "", "web": web,
                       "lignes": [[a, b] for a, b in lignes if b], "siren": r["siren"],
                       "titre": f"{r['nom']}\n{r['zone']} · niveau {int(r['niveau'])}"
                                + (f"\n{r['adresse']}" if r["adresse"] else "")})
    envoyes = {n["id"] for n in noeuds}
    aretes = [a for a in aretes if a["from"] in envoyes and a["to"] in envoyes]
    return {"racine": RACINE, "nodes": noeuds, "edges": aretes,
            "zones": [{"nom": z, "couleur": theme.COULEUR_ZONE[z]} for z in theme.ZONES
                      if any(n["zone"] == z and n["match"] and n["id"] != RACINE for n in noeuds)],
            "niveaux": sorted({n["niveau"] for n in noeuds if n["match"] and n["niveau"] >= 1}),
            "couleurs": theme.COULEUR_ZONE}


def _id_catalogue(nom):
    return "cat:" + re.sub(r"[^a-z0-9]", "", data.normaliser(nom))


def preparer_catalogue(toutes: pd.DataFrame) -> dict:
    """Catalogue des investissements cités sur eurazeo.com (269 sociétés, actuelles et anciennes) :
    une couche à part, affichée seulement si demandé. Contrairement aux autres nœuds du graphe,
    AUCUNE chaîne de détention n'est connue (on ne sait pas par quel véhicule Eurazeo détient
    chaque société) et AUCUN pourcentage n'est publié : ces nœuds sont reliés directement à
    Eurazeo par une arête en pointillé, marquée comme non vérifiée. Les sociétés déjà présentes
    dans le graphe (rapprochées par SIREN ou par nom) ne sont pas dupliquées ici."""
    cat = data.charger_catalogue(data.FICHIER_CATALOGUE.stat().st_mtime if data.FICHIER_CATALOGUE.exists() else 0)
    if not len(cat):
        return {"nodes": [], "edges": [], "total": 0, "deja": 0}
    # `toutes` peut désormais inclure les lignes du catalogue lui-même (niveau -1, ajoutées par
    # data.lignes_catalogue pour qu'elles apparaissent sur les autres pages) : on les exclut ici,
    # sinon chaque société du catalogue se « retrouverait » elle-même et semblerait déjà dans le graphe.
    toutes = toutes[toutes["niveau"] != -1]
    cat = cat.assign(deja=data.correspondance_graphe(cat, toutes))
    deja = int((cat["deja"] != "").sum())
    absents = cat[cat["deja"] == ""]

    noeuds, aretes = [], []
    for r in absents.itertuples():
        id_ = _id_catalogue(r.nom)
        lignes = [["Stratégie / description", r.description], ["Secteur", r.secteur],
                  ["Zone géographique (site)", r.region], ["Date d'investissement", r.date_investissement],
                  ["Statut (site)", r.statut]]
        if r.siren:
            lignes.append(["SIREN rapproché par le nom (⚠ à vérifier)",
                           f"{r.siren}" + (f" — {r.adresse}, {r.commune}" if r.adresse else "")])
        noeuds.append({
            "id": id_, "nom": r.nom, "zone": "", "niveau": -1, "match": True, "nature": "catalogue",
            "econ": "", "etat_web": "cédée" if r.statut.lower() == "cédée" else "", "web": [],
            "lignes": [[a, b] for a, b in lignes if b], "siren": "", "site_web": r.site_web,
            "titre": f"{r.nom}\nCatalogue eurazeo.com · lien non vérifié",
        })
        aretes.append({"from": RACINE, "to": id_, "pct": None, "interne": False, "catalogue": True})
    return {"nodes": noeuds, "edges": aretes, "total": int(len(cat)), "deja": deja}


def page_html(donnees: dict) -> str:
    modele = (ASSETS / "graphe.html").read_text(encoding="utf-8")
    vis = (ASSETS / "vis-network.min.js").read_text(encoding="utf-8")
    # le JSON est placé dans un <script> : on neutralise toute séquence « </ » venue des données
    js = json.dumps(donnees, ensure_ascii=False).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return modele.replace("/*__VIS__*/", vis).replace("/*__DONNEES__*/", js)


def aretes_csv(donnees: dict) -> pd.DataFrame:
    """Les liens affichés, pour Excel / Power BI : détenteur, détenue, part, type de lien."""
    par_id = {n["id"]: n for n in donnees["nodes"]}
    lignes = [{"detentrice": par_id[a["from"]]["nom"], "id_detentrice": a["from"],
               "detenue": par_id[a["to"]]["nom"], "id_detenue": a["to"],
               "niveau_detenue": par_id[a["to"]]["niveau"],
               "pourcentage_detention": a["pct"],
               "type_lien": "autre détenteur d'une société déjà présente" if a["interne"] else "détention"}
              for a in donnees["edges"]]
    return pd.DataFrame(lignes)
