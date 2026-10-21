import streamlit as st

from lib import charts, data, ui

toutes, df, mere = data.donnees()
data.exiger_selection(df)

ui.titre(f"L'annuaire des {len(df)} sociétés",
         "Triée par score d'opportunité par défaut — clique une colonne pour trier autrement. Cherche et filtre "
         "dans la colonne de gauche, ou sélectionne une ligne pour ouvrir sa fiche.")

notees = df["score_opportunite"].dropna()
if len(notees):
    ui.titre_graphique(f"Répartition du score sur les {len(notees)} société(s) notée(s)",
                       "Rouge = opportunité forte (≥ 65), orange = moyenne (45 à 64), gris = faible ou neutre.")
    ui.graphique(charts.score_histogramme(notees), cle="hist_score")

t = df.sort_values("score_opportunite", ascending=False, na_position="last").reset_index(drop=True)
t["nom_detentrice"] = t["nom_detentrice"].str.title().str.replace("Lh ", "LH ")
t["CA (dernier connu)"] = t["chiffre_affaires"].fillna(t["chiffre_affaires_estime_bilan"])
t["Résultat net (dernier connu)"] = t["resultat_net"].fillna(t["resultat_net_estime_bilan"])
vue = t[["nom", "score_opportunite", "urgence_libelle", "score_fiabilite", "niveau_lib", "nom_detentrice",
         "identifiant", "type_court", "zone", "pourcentage_detention", "part_economique_eurazeo", "adresse",
         "tranche_effectif", "naf_code", "forme_juridique", "statut_administratif", "date_creation", "etat_web",
         "CA (dernier connu)", "Résultat net (dernier connu)"]].rename(columns={
    "nom": "Société", "score_opportunite": "Score d'opportunité",
    "urgence_libelle": "Statut du bail (estimation 3/6/9)", "score_fiabilite": "Fiabilité (/2)",
    "niveau_lib": "Niveau", "nom_detentrice": "Détenue par",
    "part_economique_eurazeo": "Part indirecte d'Eurazeo (calcul)",
    "identifiant": "SIREN / identifiant", "type_court": "Type", "zone": "Zone",
    "pourcentage_detention": "Part détenue", "adresse": "Adresse", "tranche_effectif": "Effectif",
    "naf_code": "NAF", "forme_juridique": "Forme juridique", "statut_administratif": "Statut",
    "date_creation": "Création", "etat_web": "Cession (source web)"})
config = {"Score d'opportunité": st.column_config.ProgressColumn("Score d'opportunité", format="%d", min_value=0, max_value=100,
              help="Score indicatif de prospection immobilière (0 à 100, pondération bail/finances), "
                   "détaillé sur la fiche de chaque société. 50 sans aucune case grisée = aucune donnée du tout."),
          "Fiabilité (/2)": st.column_config.NumberColumn(
              help="Nombre de critères (bail, finances) qui reposent sur une donnée réelle plutôt que sur la "
                   "valeur neutre par défaut. 0 = score à 50 par construction, à ignorer."),
          "Part détenue": st.column_config.ProgressColumn("Part détenue", format="%.1f %%", min_value=0, max_value=100,
                                                         help="Part du capital détenue par la société de la colonne « Détenue par »."),
          "Part indirecte d'Eurazeo (calcul)": st.column_config.NumberColumn(format="%.1f %%",
              help="Niveau 2 : part de la holding dans la société × part d'Eurazeo dans la holding. Un calcul, pas une donnée publiée."),
          "CA (dernier connu)": st.column_config.NumberColumn(format="€ %d",
              help="Structuré (API Recherche d'Entreprises) si disponible, sinon estimé depuis un bilan INPI (voir la fiche société)."),
          "Résultat net (dernier connu)": st.column_config.NumberColumn(format="€ %d")}
try:
    evt = st.dataframe(vue, hide_index=True, width="stretch", column_config=config, height=min(720, 36 * (len(vue) + 1) + 4),
                       on_select="rerun", selection_mode="single-row", key="annuaire_tbl")
except TypeError:
    evt = st.dataframe(vue, hide_index=True, use_container_width=True, column_config=config, height=min(720, 36 * (len(vue) + 1) + 4))

lignes = getattr(getattr(evt, "selection", None), "rows", []) or []
c1, c2, _ = st.columns([1.1, 1.3, 3])
if lignes:
    cle = t.loc[lignes[0], "cle"]
    if c1.button("Ouvrir la fiche", type="primary"):
        st.session_state["fiche_select"] = cle
        st.switch_page("vues/fiche.py")
c2.download_button("Télécharger la sélection (CSV)", df.drop(columns=["texte_recherche", "cle"]).to_csv(
    index=False, sep=";").encode("utf-8-sig"), file_name="societes_selection.csv", mime="text/csv")

ui.note_sources(df["date_collecte"].max(), niveau_max=int(toutes["niveau"].max()))
