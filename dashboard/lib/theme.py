"""Thème visuel : couleurs validées (palette dataviz), CSS global, style Plotly."""

import streamlit as st

# --- Surfaces et encres -----------------------------------------------------
FOND = "#070A12"
SURFACE = "#0E1424"      # surface des graphiques (la palette a été validée dessus)
SURFACE_2 = "#141C30"
LIGNE = "#1E2A45"
GRILLE = "rgba(150,170,210,0.10)"
GRILLE_FORTE = "rgba(150,170,210,0.22)"
TEXTE = "#E8EEFA"
TEXTE_2 = "#B4C0DA"
TEXTE_3 = "#7F8DAE"
NEON = "#22D3EE"          # accent d'interface uniquement (jamais une série de données)

# --- Couleurs des séries : une couleur = une zone, toujours la même ----------
# Validées avec validate_palette.js (dark, all-pairs, surface #0E1424) :
# luminance, chroma, séparation daltonisme et contraste : tout passe.
ZONE_PARIS = "Paris"
ZONE_FRANCE = "France (hors Paris)"
ZONE_ETRANGER = "Étranger"
ZONE_NON_LOCALISEE = "Non localisée"   # gris neutre : adresse inconnue (jamais devinée)
ZONES = [ZONE_PARIS, ZONE_FRANCE, ZONE_ETRANGER, ZONE_NON_LOCALISEE]
COULEUR_ZONE = {ZONE_PARIS: "#0AA3C2", ZONE_FRANCE: "#8577EA", ZONE_ETRANGER: "#C98500",
                ZONE_NON_LOCALISEE: "#8A94AA"}
COULEUR_UNIE = "#0AA3C2"  # graphiques à une seule série
COULEUR_ALERTE = "#E66767"

POLICE = "Manrope, 'Segoe UI', system-ui, sans-serif"
POLICE_TITRE = "'Chakra Petch', 'Segoe UI', system-ui, sans-serif"


def appliquer_css():
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=Manrope:wght@400;500;600;700&display=swap');

/* Police du texte uniquement : on ne touche pas aux éléments d'icônes (police Material Symbols) */
.stApp, .stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp input,
.stApp textarea, .stApp button, .stApp [data-baseweb="select"] div, .stApp [data-testid="stCaptionContainer"],
[data-testid="stSidebarNav"] span:not([data-testid="stIconMaterial"]) {{ font-family: {POLICE}; }}
.stApp {{
  background:
    radial-gradient(1100px 520px at 78% -8%, rgba(34,211,238,0.10), transparent 62%),
    radial-gradient(900px 480px at -5% 18%, rgba(133,119,234,0.08), transparent 60%),
    linear-gradient(rgba(150,170,210,0.035) 1px, transparent 1px) 0 0 / 44px 44px,
    linear-gradient(90deg, rgba(150,170,210,0.035) 1px, transparent 1px) 0 0 / 44px 44px,
    {FOND};
  background-attachment: fixed;
}}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.6rem; padding-bottom: 4rem; max-width: 1240px; }}

[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, rgba(14,20,36,0.96), rgba(8,11,20,0.98));
  border-right: 1px solid {LIGNE};
}}
[data-testid="stSidebar"] h3 {{ font-family: {POLICE_TITRE}; font-weight: 600; font-size: 1.25rem; letter-spacing: .01em; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  background: rgba(34,211,238,0.10); box-shadow: inset 2px 0 0 {NEON};
}}

h1.titre {{
  font-family: {POLICE_TITRE}; font-weight: 600; font-size: clamp(1.6rem, 2.8vw, 2.3rem);
  line-height: 1.12; letter-spacing: -0.005em; margin: 0 0 .65rem 0; padding: 0; color: {TEXTE};
  max-width: 30ch;
}}
p.chapo {{ color: {TEXTE_2}; font-size: 1.05rem; line-height: 1.55; max-width: 68ch; margin: 0 0 1.6rem 0; }}
.rule {{ height: 1px; background: linear-gradient(90deg, {LIGNE}, transparent); margin: 0 0 1.8rem 0; }}

.titre-graph {{ font-weight: 700; font-size: 1.02rem; margin: 1.5rem 0 .15rem 0; color: {TEXTE}; }}
.sous-titre-graph {{ color: {TEXTE_3}; font-size: .88rem; margin: 0 0 .5rem 0; max-width: 78ch; line-height: 1.45; }}

/* Bandeau d'indicateurs : un seul panneau, pas une grille de cartes */
.bande {{
  display: flex; flex-wrap: wrap; border: 1px solid {LIGNE}; border-radius: 14px;
  background: linear-gradient(180deg, rgba(20,28,48,0.72), rgba(12,17,32,0.72));
  backdrop-filter: blur(6px); margin-bottom: 1.2rem; overflow: hidden;
}}
.bande .kpi {{ flex: 1 1 150px; padding: 1.05rem 1.3rem 1rem 1.3rem; border-left: 1px solid {LIGNE}; }}
.bande .kpi:first-child {{ border-left: 0; }}
.bande .v {{ font-family: {POLICE_TITRE}; font-weight: 600; font-size: 2.15rem; line-height: 1.05; color: {TEXTE}; }}
.bande .l {{ color: {TEXTE_3}; font-size: .86rem; margin-top: .3rem; line-height: 1.35; }}

.pastille {{
  display: inline-block; padding: .18rem .65rem; border-radius: 999px; font-size: .8rem; font-weight: 600;
  border: 1px solid; margin: 0 .4rem .3rem 0;
}}
.bloc {{ border: 1px solid {LIGNE}; border-radius: 14px; padding: 1.1rem 1.3rem; background: rgba(14,20,36,0.62); }}
.bloc .etiquette {{ color: {TEXTE_3}; font-size: .8rem; margin-bottom: .1rem; }}
.bloc .valeur {{ color: {TEXTE}; font-size: 1rem; line-height: 1.45; margin-bottom: .8rem; }}
.note {{ color: {TEXTE_3}; font-size: .82rem; line-height: 1.5; border-top: 1px solid {LIGNE}; padding-top: .8rem; margin-top: 2.4rem; max-width: 100ch; }}
.constat {{ border-left: 2px solid {NEON}; padding: .15rem 0 .15rem .9rem; margin: 0 0 .9rem 0; color: {TEXTE_2}; line-height: 1.5; max-width: 76ch; }}
.constat b {{ color: {TEXTE}; font-weight: 700; }}
a {{ color: {NEON} !important; }}

[data-testid="stDataFrame"] {{ border: 1px solid {LIGNE}; border-radius: 12px; overflow: hidden; }}
[data-testid="stExpander"] {{ border: 1px solid {LIGNE}; border-radius: 12px; background: rgba(14,20,36,0.4); }}
[data-testid="stExpander"] summary {{ color: {TEXTE_2}; }}
.stButton > button, .stDownloadButton > button {{
  border: 1px solid {LIGNE}; background: rgba(20,28,48,0.8); color: {TEXTE}; border-radius: 10px;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{ border-color: {NEON}; color: {NEON}; }}
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible {{ outline: 2px solid {NEON}; }}
span[data-baseweb="tag"] {{ background: rgba(34,211,238,0.16) !important; color: {TEXTE} !important; border: 1px solid rgba(34,211,238,0.45); }}
</style>
""",
        unsafe_allow_html=True,
    )


def style_plotly(fig, hauteur=420, legende=True):
    """Style commun : fond transparent, grille discrète, texte lisible, survol sobre."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=POLICE, color=TEXTE_2, size=13),
        margin=dict(l=4, r=8, t=6, b=4),
        height=hauteur,
        showlegend=legende,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=TEXTE_2)),
        hoverlabel=dict(bgcolor=SURFACE_2, bordercolor=LIGNE, font=dict(family=POLICE, color=TEXTE, size=13)),
    )
    fig.update_xaxes(gridcolor=GRILLE, zeroline=False, linecolor=GRILLE_FORTE, tickfont=dict(color=TEXTE_3))
    fig.update_yaxes(gridcolor=GRILLE, zeroline=False, linecolor=GRILLE_FORTE, tickfont=dict(color=TEXTE_3))
    return fig
