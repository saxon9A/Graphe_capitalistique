"""
Dashboard Streamlit : le premier cercle d'Eurazeo.

Lancer :  streamlit run app.py
Données : data/entreprises_detaillees.csv (produit par `python enrichir_details.py`).
"""

import streamlit as st

st.set_page_config(page_title="Eurazeo · premier cercle", page_icon=":material/hub:", layout="wide",
                   initial_sidebar_state="expanded")

from lib import data, theme  # noqa: E402  (après set_page_config)

theme.appliquer_css()

# Pages tournées vers la prospection immobilière (recherche + scoring) : Annuaire et Fiche société
# en premier, c'est l'usage principal. Le graphe, La carte et Les portefeuilles restent (demande
# explicite du 21/10/2026), pour qui veut comprendre la structure capitalistique derrière un score.
# Retirées à cette date : Accueil, Le contrôle (statistiques de détention, sans lien avec la
# prospection), Les sources web (page autonome — l'info reste affichée sur chaque fiche société) et
# Le profil (statistiques agrégées redondantes avec l'annuaire).
pages = [
    st.Page("vues/annuaire.py", title="L'annuaire", icon=":material/table_rows:", default=True),
    st.Page("vues/fiche.py", title="Fiche société", icon=":material/badge:"),
    st.Page("vues/carte.py", title="La carte", icon=":material/public:"),
    st.Page("vues/graphe.py", title="Le graphe", icon=":material/share:"),
    st.Page("vues/portefeuilles.py", title="Les portefeuilles", icon=":material/account_tree:"),
]
page = st.navigation(pages)

# Filtres communs à toutes les pages (placés sous le menu, comme dans le modèle)
toutes = data.charger_tout()
toutes = toutes[toutes["niveau"] != 0]   # tout sauf Eurazeo elle-même : niveaux 1+ ET le catalogue (niveau -1)
data.afficher_filtres(toutes)

page.run()
