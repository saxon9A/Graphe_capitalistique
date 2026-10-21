import html

import pandas as pd
import streamlit as st

from lib import charts, data, theme, ui

toutes, df, mere = data.donnees()
data.exiger_selection(df)

g = charts.regrouper_adresses(df)
if len(g) and g.iloc[0]["nb"] > 1:
    top = g.iloc[0]
    titre = f"{int(top['nb'])} sociétés partagent la même adresse : {top['adresse'].title()}"
else:
    titre = "Chaque société a une adresse de siège distincte"
ui.titre(titre, "Chaque disque est une adresse de siège ; sa taille grandit avec le nombre de sociétés "
                "domiciliées au même endroit. Survole un disque pour voir les sociétés.")

options = list(charts.VUES_CARTE)
etr = df[df["zone"] == theme.ZONE_ETRANGER]
defaut = ("Monde" if (etr["longitude"] < -20).any() else "Europe") if len(etr) else "Paris"
vue = st.radio("Vue", options, index=options.index(defaut), horizontal=True, key="vue_carte",
               label_visibility="collapsed")
fig_carte = charts.carte(df, vue)
try:
    evt = st.plotly_chart(fig_carte, width="stretch", config={"displayModeBar": False}, key="carte",
                          on_select="rerun")
except TypeError:  # versions de Streamlit sans on_select sur plotly_chart : pas de clic, carte seule
    evt = None
    st.plotly_chart(fig_carte, use_container_width=True, config={"displayModeBar": False}, key="carte")

points = list(getattr(getattr(evt, "selection", None), "points", []) or [])
if points:
    cd = points[0].get("customdata") or []
    cles_point = cd[4] if len(cd) > 4 else ""
    cles_liste = [c for c in cles_point.split("\x1f") if c] if cles_point else []
    societes = (df[df["cle"].isin(cles_liste)]
                .sort_values("score_opportunite", ascending=False, na_position="last")) if cles_liste else df.iloc[0:0]
    if len(societes):
        # Panneau directement sur la page (21/10/2026, demande explicite) plutôt qu'un switch_page
        # automatique vers la fiche : un clic sur un disque qui regroupe plusieurs sociétés ouvrait
        # directement, et sans choix possible, la fiche de la première — en plus de quitter la carte.
        ui.titre_graphique(
            f"{len(societes)} société{'s' if len(societes) > 1 else ''} à cette adresse",
            "Clique « Voir la fiche complète » pour le détail (bail, score, dirigeants...) d'une société.")
        for _, r in societes.iterrows():
            c_nom, c_score, c_btn = st.columns([2.2, 2, 1.1])
            with c_nom:
                st.markdown(f"**{html.escape(r['nom'])}**")
                sous = r["niveau_lib"] + (f" · {html.escape(r['identifiant'])}" if r["identifiant"] else "")
                st.caption(sous)
            with c_score:
                if pd.notna(r["score_opportunite"]):
                    st.markdown(f"Score **{int(r['score_opportunite'])}** — {r['urgence_libelle']}")
                else:
                    st.caption(r["urgence_libelle"] or "—")
            with c_btn:
                if st.button("Voir la fiche complète", key=f"carte_fiche_{r['cle']}"):
                    st.session_state["fiche_select"] = r["cle"]
                    st.switch_page("vues/fiche.py")
    else:
        st.caption("Clique sur un point pour voir les sociétés à cette adresse, directement ici.")
else:
    st.caption("Clique sur un point pour voir les sociétés à cette adresse, directement ici.")

ui.titre_graphique("Les adresses, une par une",
                   "Les sociétés étrangères sont placées au centre-ville : leur position sur la carte est approximative, "
                   "pas leur adresse, qui est celle imprimée dans le document de référence.")
# Même regroupement que la carte (coordonnées arrondies à ~10 m) : une adresse écrite de deux
# façons ("75008 PARIS" / "75008 PARIS 08") reste un seul immeuble.
t = df.copy()
t["lat_r"], t["lon_r"] = t["latitude"].round(4), t["longitude"].round(4)
t["cle_geo"] = t["lat_r"].astype(str) + "|" + t["lon_r"].astype(str)
t.loc[t["latitude"].isna(), "cle_geo"] = t["adresse"]
tab = (t.groupby(["zone", "cle_geo"], as_index=False)
         .agg(Adresse=("adresse", "first"), Sociétés=("nom", "size"),
              Liste=("nom", lambda s: ", ".join(list(s)[:6]) + (" …" if len(s) > 6 else "")))
         .rename(columns={"zone": "Zone"})
         .drop(columns="cle_geo")[["Zone", "Adresse", "Sociétés", "Liste"]]
         .sort_values("Sociétés", ascending=False))
ui.tableau_plat(tab)

ui.note_sources(df["date_collecte"].max(), niveau_max=int(toutes["niveau"].max()))
