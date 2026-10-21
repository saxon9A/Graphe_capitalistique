"""Tous les graphiques Plotly du dashboard."""

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import theme
from .theme import COULEUR_ZONE, ZONES


# --------------------------------------------------------------------------
# Constellation : distance au centre = part du capital détenue par Eurazeo
# --------------------------------------------------------------------------
def _rayon(pct):
    p = np.clip(pct, 25, 100)
    # racine carrée : étire la zone 50-100 %, où se trouvent presque toutes les sociétés
    return 0.20 + 0.80 * np.sqrt((100 - p) / 75.0)


def constellation(df: pd.DataFrame, mere=None) -> go.Figure:
    fig = go.Figure()
    theta = np.linspace(0, 2 * np.pi, 241)

    # Anneaux repères (100, 75, 50, 25 %)
    for p in (100, 75, 50, 25):
        r = _rayon(p)
        fig.add_trace(go.Scatter(x=r * np.cos(theta), y=r * np.sin(theta), mode="lines",
                                 line=dict(color=theme.GRILLE_FORTE, width=1, dash="dot"),
                                 hoverinfo="skip", showlegend=False))
        fig.add_annotation(x=r * np.cos(np.radians(-3)), y=r * np.sin(np.radians(-3)), text=f"{p} %",
                           showarrow=False, font=dict(size=11, color=theme.TEXTE_3), xanchor="left", yanchor="top")

    d = df.dropna(subset=["pourcentage_detention"]).copy()
    zones = [z for z in ZONES if (d["zone"] == z).any()]
    total = len(d)
    secteur_total = np.radians(332)
    ecart = np.radians(10) if len(zones) > 1 else 0
    utile = secteur_total - ecart * max(len(zones) - 1, 0)

    # 1) positions : chaque zone occupe un secteur d'angle proportionnel à son effectif
    angle = np.radians(14)
    morceaux = []
    for z in zones:
        sous = d[d["zone"] == z].sort_values(["pourcentage_detention", "nom"], ascending=[False, True])
        n = len(sous)
        part = utile * n / total
        angles = np.linspace(angle, angle + part, n) if n > 1 else np.array([angle + part / 2])
        angle += part + ecart
        r = _rayon(sous["pourcentage_detention"].to_numpy())
        morceaux.append(sous.assign(_x=r * np.cos(angles), _y=r * np.sin(angles)))
    d = pd.concat(morceaux)

    # 2) étiquettes directes (4 au plus) : les parts les plus faibles, sans chevauchement
    choisies = []
    for idx, row in d.sort_values("pourcentage_detention").iterrows():
        if all(np.hypot(row["_x"] - d.loc[c, "_x"], row["_y"] - d.loc[c, "_y"]) > 0.22 for c in choisies):
            choisies.append(idx)
        if len(choisies) == 4:
            break

    # 3) tracés
    for z in zones:
        sous = d[d["zone"] == z]
        sx, sy = [], []
        for xi, yi in zip(sous["_x"], sous["_y"]):
            sx += [0, xi, None]
            sy += [0, yi, None]
        fig.add_trace(go.Scatter(x=sx, y=sy, mode="lines", line=dict(color=COULEUR_ZONE[z], width=1),
                                 opacity=0.22, hoverinfo="skip", showlegend=False, legendgroup=z))
        legende_faite = False
        for type_court, symbole, taille in (("Filiale", "circle", 11), ("Participation", "diamond", 13)):
            t = sous[sous["type_court"] == type_court]
            if t.empty:
                continue
            fig.add_trace(go.Scatter(
                x=t["_x"], y=t["_y"], mode="markers", name=z, legendgroup=z, showlegend=not legende_faite,
                marker=dict(color=COULEUR_ZONE[z], size=taille, symbol=symbole, line=dict(color=theme.FOND, width=2)),
                customdata=np.stack([t["nom"], t["ville"].replace("", "—"), t["pourcentage_detention"],
                                     t["type_court"], t["tranche_effectif"].replace("", "Non renseigné")], axis=-1),
                hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[3]} · %{customdata[2]:.1f} % détenus"
                               "<br>%{customdata[1]}<br>Effectif : %{customdata[4]}<extra></extra>"),
            ))
            legende_faite = True
    e = d.loc[choisies]
    if len(e):
        fig.add_trace(go.Scatter(
            x=e["_x"], y=e["_y"], mode="text", text=e["nom"].str.replace(r"\s*\(\d\)$", "", regex=True),
            textposition=["top right" if v >= 0 else "top left" for v in e["_x"]],
            textfont=dict(size=12, color=theme.TEXTE), hoverinfo="skip", showlegend=False))

    # Le centre : Eurazeo
    fig.add_trace(go.Scatter(x=[0], y=[0], mode="markers+text", text=["Eurazeo"], textposition="bottom center",
                             textfont=dict(size=14, color=theme.TEXTE, family=theme.POLICE_TITRE),
                             marker=dict(size=26, color=theme.SURFACE_2, line=dict(color=theme.NEON, width=3)),
                             hovertemplate="<b>Eurazeo</b><br>Société mère<extra></extra>", showlegend=False))

    theme.style_plotly(fig, hauteur=640)
    fig.update_xaxes(visible=False, range=[-1.12, 1.18], scaleanchor="y", scaleratio=1)
    fig.update_yaxes(visible=False, range=[-1.12, 1.12])
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=1.0, xanchor="left", x=0))
    return fig


# --------------------------------------------------------------------------
# Carte
# --------------------------------------------------------------------------
# Fond sombre CARTO (sans clé). La variable MAP_STYLE ne sert qu'aux tests hors ligne.
STYLE_CARTE = os.environ.get("MAP_STYLE", "carto-darkmatter")
VUES_CARTE = {
    "Monde": dict(center=dict(lat=38.0, lon=-30.0), zoom=1.45),
    "Monde proche": dict(center=dict(lat=49.0, lon=3.0), zoom=4.1),
    "Europe": dict(center=dict(lat=50.0, lon=4.0), zoom=3.0),
    "Paris": dict(center=dict(lat=48.866, lon=2.322), zoom=11.5),
}


def regrouper_adresses(df: pd.DataFrame) -> pd.DataFrame:
    g = df.dropna(subset=["latitude", "longitude"]).copy()
    g["lat_r"], g["lon_r"] = g["latitude"].round(4), g["longitude"].round(4)
    out = (g.groupby(["lat_r", "lon_r", "zone"], as_index=False)
             .agg(nb=("nom", "size"), adresse=("adresse", "first"), ville=("ville", "first"),
                  precision=("geo_precision", "first"),
                  noms=("nom", lambda s: "<br>".join(list(s)[:8]) + (f"<br>… +{len(s) - 8}" if len(s) > 8 else "")),
                  cles=("cle", lambda s: "\x1f".join(sorted(s)))))
    return out.sort_values("nb", ascending=False)


def carte(df: pd.DataFrame, vue: str = "Monde proche") -> go.Figure:
    g = regrouper_adresses(df)
    fig = go.Figure()
    for z in ZONES:
        s = g[g["zone"] == z]
        if s.empty:
            continue
        fig.add_trace(go.Scattermap(
            lat=s["lat_r"], lon=s["lon_r"], mode="markers", name=z,
            marker=dict(color=COULEUR_ZONE[z], size=np.clip(14 + 4 * np.sqrt(s["nb"]), 14, 46), opacity=0.82),
            customdata=np.stack([s["nb"], s["adresse"].replace("", "—"), s["noms"],
                                 s["precision"].map({"ville": "position approximative (centre-ville)",
                                                     "adresse": "adresse exacte"}).fillna(""), s["cles"]], axis=-1),
            hovertemplate=("<b>%{customdata[1]}</b><br>%{customdata[0]} société(s) · %{customdata[3]}"
                           "<br>%{customdata[2]}<br><span style='font-size:11px'>Clique pour ouvrir une fiche"
                           "</span><extra></extra>"),
        ))
    theme.style_plotly(fig, hauteur=560)
    fig.update_layout(map=dict(style=STYLE_CARTE, **VUES_CARTE[vue]),
                      margin=dict(l=0, r=0, t=0, b=0),
                      legend=dict(orientation="h", yanchor="top", y=0.99, xanchor="left", x=0.01,
                                  bgcolor="rgba(14,20,36,0.8)", bordercolor=theme.LIGNE, borderwidth=1))
    return fig


def mini_carte(lat, lon, couleur, zoom=14) -> go.Figure:
    fig = go.Figure(go.Scattermap(lat=[lat], lon=[lon], mode="markers",
                                  marker=dict(color=couleur, size=18, opacity=0.9), hoverinfo="skip"))
    theme.style_plotly(fig, hauteur=260, legende=False)
    fig.update_layout(map=dict(style=STYLE_CARTE, center=dict(lat=lat, lon=lon), zoom=zoom),
                      margin=dict(l=0, r=0, t=0, b=0))
    return fig


# --------------------------------------------------------------------------
# Niveau 2 : sucettes « part du capital détenue par la holding », société par société
# --------------------------------------------------------------------------
def portefeuille(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["pourcentage_detention"]).copy()
    d["label"] = d["nom"].str.slice(0, 34) + "  ·  " + d["nom_detentrice"].str.replace("LEGENDRE HOLDING", "LH").str.slice(0, 20)
    d = d.sort_values(["pourcentage_detention", "label"])
    fig = go.Figure()
    sx, sy = [], []
    for lab, p in zip(d["label"], d["pourcentage_detention"]):
        sx += [0, p, None]
        sy += [lab, lab, None]
    fig.add_trace(go.Scatter(x=sx, y=sy, mode="lines", line=dict(color=theme.GRILLE_FORTE, width=1.5),
                             hoverinfo="skip", showlegend=False))
    for z in ZONES:
        t = d[d["zone"] == z]
        if t.empty:
            continue
        econ = t["part_economique_eurazeo"].map(lambda v: "—" if pd.isna(v) else f"{v:.1f} %".replace(".", ","))
        fig.add_trace(go.Scatter(
            x=t["pourcentage_detention"], y=t["label"], mode="markers", name=z,
            marker=dict(color=COULEUR_ZONE[z], size=10, line=dict(color=theme.FOND, width=2)),
            customdata=np.stack([t["nom_detentrice"], econ, t["pays"].replace("", "—"), t["niveau_lib"]], axis=-1),
            hovertemplate=("<b>%{y}</b><br>%{x:.1f} % du capital détenu par %{customdata[0]}"
                           "<br>Part indirecte d'Eurazeo (calcul) : %{customdata[1]}<br>%{customdata[3]} · %{customdata[2]}<extra></extra>")))
    fig.add_vline(x=50, line=dict(color=theme.NEON, width=1.5, dash="dash"))
    fig.add_annotation(x=50, y=1.0, yref="paper", text="Plus de 50 % : contrôle par la holding", showarrow=False,
                       xanchor="left", yanchor="bottom", xshift=6, font=dict(color=theme.NEON, size=12))
    theme.style_plotly(fig, hauteur=max(380, 24 * len(d) + 90))
    fig.update_xaxes(range=[0, 104], ticksuffix=" %", title=None)
    fig.update_yaxes(title=None, categoryorder="array", categoryarray=list(d["label"]), gridcolor="rgba(0,0,0,0)",
                     tickfont=dict(color=theme.TEXTE_2, size=12))
    fig.update_layout(legend=dict(y=1.04))
    return fig


# --------------------------------------------------------------------------
# Annuaire : distribution du score d'opportunité de la sélection filtrée
# --------------------------------------------------------------------------
def score_histogramme(scores, hauteur=200) -> go.Figure:
    """Un bâton par tranche de 5 points (0 à 100), coloré selon le seuil utilisé par
    scoring.score_opportunite (faible <45, moyenne 45-64, forte ≥65) pour que la lecture du
    graphique et celle du libellé affiché sur chaque fiche restent cohérentes."""
    bornes = list(range(0, 101, 5))
    comptes, _ = np.histogram(scores, bins=bornes)
    centres = [(bornes[i] + bornes[i + 1]) / 2 for i in range(len(bornes) - 1)]
    couleurs = [theme.COULEUR_ALERTE if c >= 65 else "#C98500" if c >= 45 else theme.TEXTE_3 for c in centres]
    fig = go.Figure(go.Bar(x=centres, y=comptes, width=4.3, marker=dict(color=couleurs, cornerradius=2),
                           hovertemplate="score %{x}<br><b>%{y}</b> société(s)<extra></extra>"))
    theme.style_plotly(fig, hauteur=hauteur, legende=False)
    fig.update_xaxes(title=None, range=[-2, 102], dtick=20, gridcolor="rgba(0,0,0,0)", tickfont=dict(color=theme.TEXTE_2))
    fig.update_yaxes(title=None, rangemode="tozero")
    fig.update_layout(bargap=0.08, margin=dict(t=8, b=8, l=8, r=8))
    return fig
