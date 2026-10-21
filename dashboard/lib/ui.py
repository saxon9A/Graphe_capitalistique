"""Petits composants d'interface partagés par les pages."""

import pandas as pd
import streamlit as st

from . import theme


def titre(texte: str, chapo: str = ""):
    st.markdown(f'<h1 class="titre">{texte}</h1>', unsafe_allow_html=True)
    if chapo:
        st.markdown(f'<p class="chapo">{chapo}</p>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="rule"></div>', unsafe_allow_html=True)


def titre_graphique(titre_txt: str, sous_titre: str = ""):
    st.markdown(f'<div class="titre-graph">{titre_txt}</div>', unsafe_allow_html=True)
    if sous_titre:
        st.markdown(f'<div class="sous-titre-graph">{sous_titre}</div>', unsafe_allow_html=True)


def bande(indicateurs):
    """indicateurs : liste de (valeur, libellé)."""
    html = "".join(f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div></div>' for v, l in indicateurs)
    st.markdown(f'<div class="bande">{html}</div>', unsafe_allow_html=True)


def constat(html: str):
    st.markdown(f'<div class="constat">{html}</div>', unsafe_allow_html=True)


def pastille(texte: str, couleur: str) -> str:
    return (f'<span class="pastille" style="color:{couleur};border-color:{couleur}66;'
            f'background:{couleur}1A">{texte}</span>')


def graphique(fig, cle=None):
    try:
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=cle)
    except TypeError:  # versions plus anciennes de Streamlit
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=cle)


def tableau_plat(df: pd.DataFrame, **kw):
    try:
        return st.dataframe(df, hide_index=True, width="stretch", **kw)
    except TypeError:  # versions plus anciennes de Streamlit
        return st.dataframe(df, hide_index=True, use_container_width=True, **kw)


def tableau(df: pd.DataFrame, libelle: str = "Voir les données de ce graphique"):
    with st.expander(libelle):
        tableau_plat(df)


def note_sources(date_collecte: str = "", niveau_max: int = 1):
    quand = f" · Données Sirene collectées le {date_collecte}" if date_collecte else ""
    if niveau_max >= 2:
        niv = "Niveau 2" if niveau_max == 2 else f"Niveaux 2 à {niveau_max}"
        suite = (f"{niv} : sociétés détenues par les holdings du niveau précédent, lues dans le tableau des filiales "
                 "et participations (ou les notes) de leurs comptes annuels déposés au RNE (INPI). La part indirecte "
                 "d'Eurazeo est un calcul : part dans la société × part indirecte d'Eurazeo dans la société qui la "
                 "détient. On ne descend que par les holdings françaises : les sociétés étrangères et les sociétés "
                 "opérationnelles ne sont pas explorées. ")
    else:
        suite = "Seul le premier cercle est représenté : les sociétés détenues par ces filiales n'y figurent pas. "
    st.markdown(
        '<div class="note"><b>Sources et limites.</b> Liste des filiales et participations : Document '
        "d'enregistrement universel 2025 d'Eurazeo (Note 17, comptes individuels), dépôt AMF. Adresses, effectifs, "
        f"activité et dirigeants : Sirene (INSEE) et RNE (INPI) via l'API Recherche d'Entreprises{quand}. "
        f"{suite}"
        "La tranche d'effectif est une fourchette déclarée, pas un nombre exact. Les sociétés étrangères sont "
        "placées au centre-ville (position approximative).</div>",
        unsafe_allow_html=True,
    )


def pct(x, decimales=1):
    return f"{x:.{decimales}f}".replace(".", ",") + " %"
