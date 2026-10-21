import pandas as pd
import streamlit as st

from lib import charts, data, theme, ui

toutes, df, mere = data.donnees()
n2_total = int((toutes["niveau"] >= 2).sum())
d = df[df["niveau"] >= 2]
if not n2_total:
    ui.titre("Les portefeuilles", "Le niveau 2 n'est pas encore collecté : lance `python niveau2_collecter.py`, "
                                  "`python niveau2_extraire.py` puis `python niveau2_enrichir.py`.")
    st.stop()
if d.empty:
    st.markdown('<h1 class="titre">Aucune société des niveaux 2 et suivants ne correspond aux filtres</h1>', unsafe_allow_html=True)
    st.markdown('<p class="chapo">Vérifie le filtre Niveaux, la zone et la recherche '
                'dans la colonne de gauche.</p>', unsafe_allow_html=True)
    st.stop()

n = len(d)
n_h = d["siren_detentrice"].nunique()
n_etr = int((d["zone"] == theme.ZONE_ETRANGER).sum())
n_fr = int(d["zone"].isin([theme.ZONE_PARIS, theme.ZONE_FRANCE]).sum())
ui.titre(f"{n} sociétés sont détenues par {n_h} holdings, sous le premier cercle d'Eurazeo",
         "Au-delà des sociétés détenues directement, chaque holding déclare dans ses comptes annuels les "
         "sociétés dont elle possède des titres. C'est là que se trouvent les entreprises opérationnelles.")

avec_pct = d.dropna(subset=["pourcentage_detention"])
econ = d["part_economique_eurazeo"].dropna()
ui.bande([
    (n, "sociétés détenues via une holding"),
    (n_fr, "en France"),
    (n_etr, "à l'étranger"),
    (int((avec_pct["pourcentage_detention"] > 50).sum()), "détenues à plus de 50 % par leur holding"),
    (ui.pct(econ.median(), 0) if len(econ) else "—", "part indirecte médiane d'Eurazeo (calcul)"),
])

ui.titre_graphique("Part du capital détenue par la holding, société par société",
                   "Chaque ligne est une société, suivie de la holding qui la détient. Survole un point pour voir "
                   "la part indirecte d'Eurazeo.")
if len(avec_pct):
    ui.graphique(charts.portefeuille(avec_pct), cle="portefeuille")

sans = d[d["pourcentage_detention"].isna()]
if len(sans):
    ui.titre_graphique(f"{len(sans)} sociétés citées sans pourcentage",
                       "Les comptes les mentionnent (par exemple « participation minoritaire au capital de Doctolib SAS ») "
                       "sans publier la part détenue. Une société citée a pu être cédée depuis.")
    ui.tableau_plat(sans[["nom", "nom_detentrice", "zone", "adresse"]].rename(columns={
        "nom": "Société", "nom_detentrice": "Citée dans les comptes de", "zone": "Zone", "adresse": "Adresse"}))

t = (avec_pct[["nom", "nom_detentrice", "pourcentage_detention", "part_economique_eurazeo", "zone", "pays", "identifiant"]]
     .sort_values("pourcentage_detention", ascending=False)
     .rename(columns={"nom": "Société", "nom_detentrice": "Détenue par", "pourcentage_detention": "Part de la holding (%)",
                      "part_economique_eurazeo": "Part indirecte d'Eurazeo (calcul, %)", "zone": "Zone", "pays": "Pays",
                      "identifiant": "SIREN / identifiant"}))
ui.tableau(t, "Voir les données de ce graphique")

ui.constat("<b>À lire avec prudence.</b> Les pourcentages sont ceux imprimés dans les comptes annuels des holdings "
           "(exercice 2025 pour la plupart, 2024 pour certains tableaux). Plusieurs holdings ne détiennent que de petites "
           "parts : une société peut figurer ici sans qu'Eurazeo en ait le contrôle. La colonne « Identification » "
           "de la fiche dit comment chaque société a été reconnue.")
ui.note_sources(d["date_collecte"].max(), niveau_max=int(toutes["niveau"].max()))
