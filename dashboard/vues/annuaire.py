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
# Texte pré-formaté (« — » si manquant), pas une colonne numérique brute avec NaN : un NumberColumn
# Streamlit peut afficher littéralement "None" pour une valeur manquante (constaté le 21/10/2026 sur
# le dashboard déployé) — voir ui.montant().
t["CA (dernier connu)"] = t["chiffre_affaires"].fillna(t["chiffre_affaires_estime_bilan"]).map(ui.montant)
t["Résultat net (dernier connu)"] = t["resultat_net"].fillna(t["resultat_net_estime_bilan"]).map(ui.montant)
t["Date d'installation"] = t["date_installation_siege"].map(ui.date_fr)
# Code postal + ville ajoutés à l'adresse : déjà présents dedans pour les niveaux 1-3 (adresse
# complète renvoyée telle quelle par l'API), mais absents pour le catalogue (rue seule) — ajoutés
# seulement quand ils manquent, pour ne jamais les répéter.
t["adresse"] = t.apply(
    lambda r: r["adresse"] if not r["code_postal"] or r["code_postal"] in r["adresse"]
    else (f"{r['adresse']}, {r['code_postal']} {r['ville']}".strip() if r["adresse"]
          else f"{r['code_postal']} {r['ville']}".strip()),
    axis=1)
# Colonnes centrées sur la prospection en priorité (21/10/2026, demande explicite) ; fiabilité,
# niveau, détenue par, type, part détenue, part indirecte et NAF retirés de ce tableau (redondants
# ou peu utiles pour cibler une société à démarcher — toujours visibles sur sa fiche complète).
vue = t[["nom", "score_opportunite", "adresse", "Date d'installation", "nom_legal", "tranche_effectif",
         "CA (dernier connu)", "Résultat net (dernier connu)",
         "identifiant", "zone", "forme_juridique", "statut_administratif", "date_creation",
         "etat_web"]].rename(columns={
    "nom": "Société", "score_opportunite": "Score d'opportunité", "adresse": "Adresse",
    "nom_legal": "Raison sociale", "tranche_effectif": "Effectif",
    "identifiant": "SIREN / identifiant", "zone": "Zone", "forme_juridique": "Forme juridique",
    "statut_administratif": "Statut", "date_creation": "Création", "etat_web": "Cession (source web)"})
config = {"Score d'opportunité": st.column_config.ProgressColumn("Score d'opportunité", format="%d", min_value=0, max_value=100,
              help="Score indicatif de prospection immobilière (0 à 100, pondération bail/finances), "
                   "détaillé sur la fiche de chaque société. 50 sans aucune case grisée = aucune donnée du tout."),
          "CA (dernier connu)": st.column_config.TextColumn(
              help="Structuré (API Recherche d'Entreprises) si disponible, sinon estimé depuis un bilan INPI (voir la fiche société)."),
          "Résultat net (dernier connu)": st.column_config.TextColumn()}
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
c2.download_button("Télécharger la sélection (CSV)", vue.to_csv(index=False, sep=";").encode("utf-8-sig"),
                   file_name="societes_selection.csv", mime="text/csv",
                   help="Mêmes colonnes et même ordre que le tableau ci-dessus.")

ui.note_sources(df["date_collecte"].max(), niveau_max=int(toutes["niveau"].max()))
