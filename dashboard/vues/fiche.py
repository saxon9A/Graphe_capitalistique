import html

import pandas as pd
import streamlit as st

from lib import charts, data, scoring, theme, ui

toutes, filtre, mere = data.donnees()
# La liste suit les filtres de la colonne de gauche (zone Paris, niveau, recherche...).
data.exiger_selection(filtre)
liste = filtre.sort_values("nom")
cles = list(liste["cle"])

ui.titre("Fiche société", "Choisis une société dans la liste ou tape son nom ou son SIREN. "
                          "La liste suit les filtres de la colonne de gauche.")
if len(cles) < len(toutes):
    st.caption(f"{len(cles)} société(s) dans la liste sur {len(toutes)} : filtres actifs dans la colonne de gauche.")
if st.session_state.get("fiche_select") not in cles:
    st.session_state["fiche_select"] = cles[0]
c_select, c_dl = st.columns([3, 1.3])
with c_select:
    choix = st.selectbox("Société", cles, key="fiche_select", label_visibility="collapsed",
                         placeholder="Nom ou SIREN…")
with c_dl:
    c_dl.download_button(
        f"Télécharger la liste filtrée ({len(filtre)}) (CSV)",
        filtre.drop(columns=["texte_recherche", "cle"]).to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="societes_selection.csv", mime="text/csv",
        help="Toutes les sociétés qui correspondent aux filtres de la colonne de gauche (zone, holdings, "
             "recherche...), avec toutes leurs colonnes — pas seulement celle affichée ci-dessous.")
s = filtre[filtre["cle"] == choix].iloc[0]


def v(x, suffixe=""):
    if x is None or (isinstance(x, float) and pd.isna(x)) or x == "":
        return "—"
    return html.escape(str(x)) + suffixe


def date_fr(x):
    p = str(x).split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else v(x)


def bloc(lignes):
    corps = "".join(f'<div class="etiquette">{e}</div><div class="valeur">{val}</div>' for e, val in lignes)
    return f'<div class="bloc">{corps}</div>'


couleur = theme.COULEUR_ZONE[s["zone"]]
est_catalogue = s["niveau"] == -1
st.markdown(
    f'<h1 class="titre" style="max-width:none">{html.escape(s["nom"])}</h1>'
    + ui.pastille(s["zone"], couleur)
    + ui.pastille("Catalogue eurazeo.com" if est_catalogue else (s["type_relation"] or "—"), theme.TEXTE_2)
    + ui.pastille(s["statut_administratif"] or "Statut inconnu", theme.TEXTE_2)
    + (ui.pastille("Lien non vérifié", theme.COULEUR_ALERTE) if est_catalogue else
       (ui.pastille(s["validation"], theme.TEXTE_3) if s["validation"] else "")),
    unsafe_allow_html=True)
st.write("")

gauche, droite = st.columns([1.15, 1], gap="large")
with gauche:
    st.markdown(bloc([
        (("Part du capital détenue par Eurazeo" if s["niveau"] == 1
          else "Lien avec Eurazeo" if est_catalogue
          else f"Part du capital détenue par {html.escape(s['nom_detentrice'].title())} (niveau {int(s['niveau'])})"),
         ("Citée dans le catalogue des investissements d'Eurazeo (eurazeo.com), sans pourcentage publié. "
          "Chaîne de détention (quelle holding, quelle part) inconnue : voir la note ci-dessous." if est_catalogue
          else f"<b>{ui.pct(s['pourcentage_detention'])}</b>" if pd.notna(s["pourcentage_detention"])
          else "Part non publiée dans les documents consultés")),
        *([("Part indirecte d'Eurazeo (calcul)",
            f"<b>{ui.pct(s['part_economique_eurazeo'])}</b><br><span style='color:{theme.TEXTE_3}'>"
            "part dans la société × part d'Eurazeo dans la holding</span>")]
          if s["niveau"] >= 2 and pd.notna(s["part_economique_eurazeo"]) else []),
        ("Adresse du siège", v(s["adresse"])),
        ("Région · département", v(" · ".join(x for x in [s["region"], s["departement"]] if x))),
        ("Effectif salarié", v(s["tranche_effectif"]) + (f" (au {int(float(s['annee_tranche_effectif']))})"
                                                          if str(s["annee_tranche_effectif"]).replace('.0', '').isdigit() else "")),
        ("Établissements (ouverts / total)",
         f"{v(s['nb_etablissements_ouverts'] if pd.isna(s['nb_etablissements_ouverts']) else int(s['nb_etablissements_ouverts']))}"
         f" / {v(s['nb_etablissements'] if pd.isna(s['nb_etablissements']) else int(s['nb_etablissements']))}"),
    ]), unsafe_allow_html=True)
with droite:
    if pd.notna(s["latitude"]):
        ui.graphique(charts.mini_carte(s["latitude"], s["longitude"], couleur,
                                       zoom=14 if s["geo_precision"] == "adresse" else 9), cle="mini")
        if s["geo_precision"] == "ville":
            st.caption("Position approximative (centre-ville) : l'adresse exacte n'est pas géolocalisée.")
    else:
        st.caption("Pas de coordonnées disponibles pour cette société.")

st.write("")
c1, c2 = st.columns(2, gap="large")
with c1:
    st.markdown(bloc([
        ("SIREN", v(s["siren"])), ("SIRET du siège", v(s["siret_siege"])),
        ("Identifiant à l'étranger", v(s["identifiant_etranger"])),
        ("Forme juridique", v(s["forme_juridique"])),
        ("Date de création", date_fr(s["date_creation"])), ("Catégorie d'entreprise", v(s["categorie_entreprise"])),
    ]), unsafe_allow_html=True)
with c2:
    activite = " · ".join(x for x in [s["naf_code"], s["naf_libelle"]] if x)

    def _eur(x):
        return f"{int(x):,} €".replace(",", " ")

    if pd.notna(s["chiffre_affaires"]) or pd.notna(s["resultat_net"]):
        fin = (f"Chiffre d'affaires : {_eur(s['chiffre_affaires'])}" if pd.notna(s["chiffre_affaires"]) else "Chiffre d'affaires : —")
        fin += (f"<br>Résultat net : {_eur(s['resultat_net'])}" if pd.notna(s["resultat_net"]) else "")
        if pd.notna(s["croissance_ca_pct"]):
            fin += f"<br>Évolution du CA sur un an : {s['croissance_ca_pct']:+.1f} %"
        fin += f"<br><span style='color:{theme.TEXTE_3}'>Exercice {int(s['annee_finances'])} · source : API Recherche d'Entreprises</span>" if pd.notna(s["annee_finances"]) else ""
    elif pd.notna(s.get("chiffre_affaires_estime_bilan")) or pd.notna(s.get("resultat_net_estime_bilan")):
        fin = (f"Chiffre d'affaires (estimé) : {_eur(s['chiffre_affaires_estime_bilan'])}" if pd.notna(s.get("chiffre_affaires_estime_bilan")) else "Chiffre d'affaires : —")
        fin += (f"<br>Résultat net (estimé) : {_eur(s['resultat_net_estime_bilan'])}" if pd.notna(s.get("resultat_net_estime_bilan")) else "")
        fin += (f"<br><span style='color:{theme.COULEUR_ALERTE}'>Extrait automatiquement d'un compte annuel INPI, "
                "pas une donnée structurée : à vérifier.</span>")
        if s.get("bilan_ligne_source_ca"):
            fin += f"<br><span style='color:{theme.TEXTE_3}'>Ligne source (CA) : « {html.escape(s['bilan_ligne_source_ca'])} »</span>"
    else:
        fin = "—"
    st.markdown(bloc([
        ("Activité", v(activite) + (f"<br><span style='color:{theme.TEXTE_3}'>{html.escape(s['naf_section'])}</span>" if s["naf_section"] else "")),
        ("Dirigeants", v(s["dirigeants"]).replace(" | ", "<br>")),
        ("Comptes publiés", fin),
    ]), unsafe_allow_html=True)

ui.titre_graphique("Bail commercial et opportunité de déménagement (estimation)",
    "Calculé à partir de la date d'installation au siège actuel, selon le cycle de bail commercial "
    "3/6/9 (résiliation possible à chaque échéance triennale, préavis de 6 mois). Simplification "
    "assumée : on suppose que ce cycle continue depuis l'installation, sans savoir si un nouveau bail "
    "a été signé depuis. Si la date d'installation est inconnue, rien n'est calculé.")
b1, b2 = st.columns(2, gap="large")
_COULEUR_URGENCE = {3: theme.COULEUR_ALERTE, 2: "#C98500", 1: theme.TEXTE_2, 0: theme.TEXTE_2, None: theme.TEXTE_3}
with b1:
    st.markdown(ui.pastille(s["urgence_libelle"], _COULEUR_URGENCE.get(s["urgence_369"], theme.TEXTE_3)),
               unsafe_allow_html=True)
    if s["statut_bail"] and s["statut_bail"] != scoring.STATUT_INCONNU:
        st.caption(s["statut_bail"])
    st.markdown(bloc([
        ("Date d'installation au siège actuel", date_fr(s["date_installation_siege"]) if s["date_installation_siege"] else "—"),
        ("Prochaine échéance triennale (estimation)",
         date_fr(str(s["prochaine_echeance_369"])) if s["prochaine_echeance_369"] else "—"),
        ("Date limite pour donner congé (6 mois avant)",
         date_fr(str(s["date_limite_preavis"])) if s["date_limite_preavis"] else "—"),
    ]), unsafe_allow_html=True)
with b2:
    detail = scoring.score_opportunite({
        "statut_administratif": s["statut_administratif"],
        "date_installation_siege": s["date_installation_siege"] or None,
        "chiffre_affaires": s["chiffre_affaires"] if pd.notna(s["chiffre_affaires"]) else None,
        "resultat_net": s["resultat_net"] if pd.notna(s["resultat_net"]) else None,
        "annee_finances": s["annee_finances"] if pd.notna(s["annee_finances"]) else None,
        "chiffre_affaires_annee_precedente": s["chiffre_affaires_annee_precedente"]
        if pd.notna(s["chiffre_affaires_annee_precedente"]) else None})
    if detail["score"] is None:
        st.markdown(bloc([("Score d'opportunité", detail["libelle"])]), unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="bloc"><div class="etiquette">Score d\'opportunité (sur 100, fiabilité '
            f'{detail["score_fiabilite"]}/{detail["criteres_totaux"]} — {detail["criteres_disponibles"]} '
            f'critère(s) basé(s) sur une donnée réelle)</div>'
            f'<div class="valeur" style="font-size:1.6rem"><b>{detail["score"]}</b> — {detail["libelle"]}</div></div>',
            unsafe_allow_html=True)
        with st.expander("Détail du calcul"):
            st.caption("Pondération : bail ~61,5 % · finances ~38,5 % (critère « événements » de PRSimmo non "
                       "porté ici, faute de données BODACC/presse — voir le README).")
            for pts, explication in detail["detail"]:
                st.markdown(f"**{pts} pts** — {explication}")

meme = toutes[(toutes["adresse"].str.lower() == s["adresse"].lower()) & (toutes["cle"] != s["cle"])] if s["adresse"] else toutes.iloc[0:0]
if len(meme):
    ui.titre_graphique(f"{len(meme)} autre{'s' if len(meme) > 1 else ''} société{'s' if len(meme) > 1 else ''} à la même adresse")
    st.caption(", ".join(meme["nom"].tolist()))

if s["verification"]:
    st.markdown(f'<div class="note"><b>Identification.</b> {html.escape(s["verification"])}</div>', unsafe_allow_html=True)

web = data.evenements_de(s["nom"])
if web:
    lignes = "".join(
        f"<li><b>{html.escape(e['etat'])}</b> · {html.escape(date_fr(e['date']))} · {html.escape(e['evenement'])}"
        + (f" (acquéreur : {html.escape(e['acquereur'])})" if e["acquereur"] else "")
        + f' · <a href="{html.escape(e["url"], quote=True)}" target="_blank" rel="noopener noreferrer">'
          f'{html.escape(e["source"])} ↗</a><br><span style="color:{theme.TEXTE_3}">{html.escape(e["extrait"])}</span></li>'
        for e in web)
    st.markdown(f'<div class="note"><b>Sources web.</b> Rapprochement par le nom de la société (à vérifier) :'
                f'<ul style="margin:.4rem 0 0 0">{lignes}</ul></div>', unsafe_allow_html=True)

if s["siren"]:
    st.markdown(f"[Voir la fiche officielle sur l'Annuaire des entreprises ↗](https://annuaire-entreprises.data.gouv.fr/entreprise/{s['siren']})")
st.markdown(f'<div class="note"><b>Source de la fiche.</b> {html.escape(s["source_relation"] or "")} · '
            f'{html.escape(s["source_enrichissement"] or "")}.</div>', unsafe_allow_html=True)
