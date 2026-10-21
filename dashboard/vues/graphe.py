import streamlit as st

from lib import data, graphe, ui

toutes, df, mere = data.donnees()
data.exiger_selection(df)

niveau_max = int(toutes["niveau"].max())
d = graphe.preparer(toutes, df, mere, data.charger_liens())
n_aff = sum(1 for n in d["nodes"] if n["match"] and n["id"] != graphe.RACINE)
n_chemin = sum(1 for n in d["nodes"] if not n["match"] and n["id"] != graphe.RACINE)
d["catalogue"] = graphe.preparer_catalogue(toutes)

ui.titre(f"{n_aff} sociétés dans le réseau d'Eurazeo",
         "Chaque flèche va du détenteur vers la société détenue. Glisse une société pour la déplacer, "
         "molette pour zoomer, clique pour voir sa chaîne de détention jusqu'à Eurazeo.")
st.caption("Les boutons au-dessus du graphe filtrent à la volée (zone, niveau) ; la colonne de gauche filtre "
           "aussi, par exemple sur la recherche ou la détention minimale. Avec « Chemin jusqu'à Eurazeo », les "
           "holdings qui relient une société affichée à Eurazeo restent visibles, en pâle"
           + (f" ({n_chemin} ici)." if n_chemin else "."))

html = graphe.page_html(d)
if hasattr(st, "iframe"):
    st.iframe(html, height=760)
else:  # Streamlit plus ancien
    import streamlit.components.v1 as components
    components.html(html, height=760, scrolling=False)

if niveau_max < 3:
    ui.constat("Le graphe s'arrête au niveau " + str(niveau_max) + ". Pour descendre d'un niveau de plus : "
               "<b>python descendre.py 3</b> (voir le README).")
liens = graphe.aretes_csv(d)
st.download_button("Télécharger les liens affichés (CSV pour Excel / Power BI)",
                   liens.to_csv(index=False, sep=";").encode("utf-8-sig"), file_name="liens_graphe.csv", mime="text/csv")
ui.constat("<b>À lire avec prudence.</b> Les sociétés sans adresse ni SIREN trouvés sont en « Non localisée ». "
           "On ne descend que par les holdings françaises : les sociétés étrangères et les sociétés opérationnelles "
           "sont des culs-de-sac du graphe, ce qui ne veut pas dire qu'elles ne détiennent rien.")
ui.note_sources(df["date_collecte"].max(), niveau_max=niveau_max)
