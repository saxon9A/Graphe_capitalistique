"""Chargement et filtrage des données (fichier produit par enrichir_details.py)."""

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from . import scoring, theme

CHEMIN = Path(__file__).resolve().parent.parent / "data" / "entreprises_detaillees.csv"
DOSSIER_DATA = CHEMIN.parent
# Facultatifs : un fichier par niveau (entreprises_niveau2.csv, entreprises_niveau3.csv, ...) et les liens
# entre sociétés déjà présentes dans le graphe (liens_internes_niveau2.csv, ...).
FICHIER_EVENEMENTS = DOSSIER_DATA / "evenements_web.csv"   # cessions repérées sur le web, avec lien vers chaque source
FORMES_NIVEAUX = "entreprises_niveau*.csv"
FORMES_LIENS = "liens_internes_niveau*.csv"


def fichiers_niveaux():
    return sorted(DOSSIER_DATA.glob(FORMES_NIVEAUX))


def fichiers_liens():
    return sorted(DOSSIER_DATA.glob(FORMES_LIENS))

COLONNES_TEXTE = [
    "siren", "siret_siege", "identifiant_etranger", "nom", "sigle", "pays", "zone", "adresse",
    "code_postal", "ville", "departement", "region", "statut_administratif", "forme_juridique",
    "naf_code", "naf_libelle", "naf_section", "tranche_effectif", "groupe_effectif",
    "categorie_entreprise", "dirigeants", "type_relation", "validation", "nom_detentrice",
    "source_relation", "source_enrichissement", "date_creation", "date_collecte", "geo_precision",
    "verification", "date_installation_siege",
    "bilan_ligne_source_ca", "bilan_ligne_source_resultat", "bilan_ligne_source_effectif",
]
COLONNES_NOMBRE = ["niveau", "pourcentage_detention", "latitude", "longitude", "nb_etablissements",
                   "nb_etablissements_ouverts", "chiffre_affaires", "resultat_net", "annee_finances",
                   "page_deu", "part_economique_eurazeo",
                   "chiffre_affaires_annee_precedente", "croissance_ca_pct",
                   "chiffre_affaires_estime_bilan", "resultat_net_estime_bilan", "effectif_estime_bilan"]

ORDRE_EFFECTIF = ["0 salarié", "Non employeuse / inconnu", "1 à 9", "10 à 49", "50 à 249", "250 et plus"]
NON_RENSEIGNE = "Non renseigné"
# Holding, fonds de placement, gestion de fonds, services financiers auxiliaires (ex. véhicules de
# carried interest), siège social. Ne peut identifier que les sociétés françaises avec fiche Sirene :
# les sociétés étrangères sans SIREN n'ont pas de NAF et ne sont donc jamais retirées par ce filtre,
# même si elles sont probablement aussi des holdings (ex. "Eurazeo UK Limited"). 66.19B ajouté le
# 21/10/2026 : repéré sur "EURAZEO CAPITAL V - BS" (CA à 0, pertes importantes - normal pour ce type
# de véhicule -, ce qui le faisait ressortir à tort en haut du score d'opportunité).
HOLDING_NAF = {"64.20Z", "64.30Z", "66.19B", "66.30Z", "70.10Z"}


def normaliser(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation : « Asmodée Holding » -> « asmodee holding »."""
    t = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


@st.cache_data(show_spinner=False)
def charger_evenements(_signature=None) -> pd.DataFrame:
    """Événements (cessions) repérés sur le web : fichier data/evenements_web.csv, un lien par source."""
    colonnes = ["societe", "cles", "evenement", "etat", "date", "acquereur", "source", "url", "extrait", "verifie_le"]
    if not FICHIER_EVENEMENTS.exists():
        return pd.DataFrame(columns=colonnes)
    e = pd.read_csv(FICHIER_EVENEMENTS, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    return e.sort_values("date", ascending=False).reset_index(drop=True)


FICHIER_PORTEFEUILLE_WEB = DOSSIER_DATA / "portefeuille_web.csv"   # participations citées par Eurazeo, sans part détenue


@st.cache_data(show_spinner=False)
def charger_portefeuille_web(_signature=None) -> pd.DataFrame:
    colonnes = ["societe", "cles", "strategie", "nature", "pays", "activite", "source", "url", "extrait", "verifie_le"]
    if not FICHIER_PORTEFEUILLE_WEB.exists():
        return pd.DataFrame(columns=colonnes)
    return pd.read_csv(FICHIER_PORTEFEUILLE_WEB, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)


FICHIER_CATALOGUE = DOSSIER_DATA / "portefeuille_eurazeo_catalogue.csv"   # catalogue eurazeo.com/fr/investissements


@st.cache_data(show_spinner=False)
def charger_catalogue(_signature=None) -> pd.DataFrame:
    """Catalogue complet des investissements affichés sur eurazeo.com (269 sociétés, actuelles et
    anciennes). Produit par `catalogue_eurazeo.py` à partir d'un export fourni (pas de scrape
    automatique ici). Rapprochement Sirene par nom : à vérifier, jamais garanti (voir ce script)."""
    colonnes = ["nom", "cles", "statut", "date_investissement", "description", "secteur", "region",
                "site_web", "siren", "nom_legal", "adresse", "code_postal", "commune",
                "tranche_effectif", "etat_administratif", "score_correspondance",
                "verification_necessaire", "source", "url", "verifie_le",
                "latitude", "longitude", "geo_precision",
                "chiffre_affaires", "resultat_net", "annee_finances",
                "chiffre_affaires_annee_precedente", "croissance_ca_pct", "date_installation_siege",
                "chiffre_affaires_estime_bilan", "resultat_net_estime_bilan", "effectif_estime_bilan",
                "bilan_ligne_source_ca", "bilan_ligne_source_resultat", "bilan_ligne_source_effectif"]
    if not FICHIER_CATALOGUE.exists():
        return pd.DataFrame(columns=colonnes)
    return pd.read_csv(FICHIER_CATALOGUE, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)


def correspondance_graphe(cat: pd.DataFrame, toutes: pd.DataFrame) -> pd.Series:
    """Pour chaque ligne du catalogue, le nom de la société du graphe qui lui correspond déjà
    (SIREN identique en priorité - fiable - sinon nom normalisé identique - à l'œil près), ou ''
    si la société n'est pas encore dans le graphe (chaîne de détention INPI inconnue ou non lue)."""
    par_siren = {r["siren"]: r["nom"] for r in toutes.to_dict("records") if r.get("siren")}
    par_nom = {normaliser(r["nom"]): r["nom"] for r in toutes.to_dict("records")}

    def trouver(row):
        if row["siren"] and row["siren"] in par_siren:
            return par_siren[row["siren"]]
        return par_nom.get(normaliser(row["nom"]), "")

    return cat.apply(trouver, axis=1) if len(cat) else pd.Series(dtype=str)


# Même nomenclature INSEE que src/details.py (tranche d'effectif salarié), dupliquée ici car
# dashboard/ et src/ sont deux paquets distincts non importables l'un depuis l'autre.
_TRANCHES_EFFECTIF = {
    "NN": "Non employeuse / effectif inconnu", "00": "0 salarié", "01": "1 à 2 salariés",
    "02": "3 à 5 salariés", "03": "6 à 9 salariés", "11": "10 à 19 salariés", "12": "20 à 49 salariés",
    "21": "50 à 99 salariés", "22": "100 à 199 salariés", "31": "200 à 249 salariés",
    "32": "250 à 499 salariés", "41": "500 à 999 salariés", "42": "1 000 à 1 999 salariés",
    "51": "2 000 à 4 999 salariés", "52": "5 000 à 9 999 salariés", "53": "10 000 salariés et plus",
}
_GROUPE_EFFECTIF = {
    "NN": "Non employeuse / inconnu", "00": "0 salarié",
    "01": "1 à 9", "02": "1 à 9", "03": "1 à 9", "11": "10 à 49", "12": "10 à 49",
    "21": "50 à 249", "22": "50 à 249", "31": "50 à 249",
    "32": "250 et plus", "41": "250 et plus", "42": "250 et plus",
    "51": "250 et plus", "52": "250 et plus", "53": "250 et plus",
}


def _zone_catalogue(code_postal: str, siren: str) -> str:
    """Zone géographique d'une société du catalogue, à partir du seul indice fiable qu'on ait :
    un SIREN n'existe que pour une société française (Sirene est un registre français). Sans
    SIREN, on ne sait rien de fiable sur le pays (le champ « région » du site n'est qu'une zone
    marketing - Europe, Amériques... - jamais un pays précis) : on affiche « Non localisée »
    plutôt que de deviner « Étranger »."""
    if not siren:
        return theme.ZONE_NON_LOCALISEE
    cp = (code_postal or "").strip()
    if cp.startswith("75"):
        return theme.ZONE_PARIS
    if cp:
        return theme.ZONE_FRANCE
    return theme.ZONE_NON_LOCALISEE


def lignes_catalogue(toutes: pd.DataFrame) -> pd.DataFrame:
    """Sociétés du catalogue eurazeo.com absentes du graphe (chaîne de détention inconnue),
    mises au même format que `toutes` pour pouvoir apparaître sur toutes les pages (annuaire,
    carte, fiche...), pas seulement sur Le graphe. Toujours marquées « Catalogue », jamais
    « Niveau N » : on ne sait pas, par quel véhicule ni avec quel pourcentage, Eurazeo les
    détient. Le SIREN rapproché par le nom n'est volontairement PAS mis dans la colonne
    `siren`/`identifiant` (seulement cité, en toutes lettres, dans la colonne `verification`) :
    ça évite qu'il soit traité ailleurs comme un identifiant confirmé (lien « fiche officielle »,
    recoupement par SIREN...), alors que ce rapprochement par nom seul n'est jamais garanti
    (voir catalogue_eurazeo.py - ex. « Mapal », « Planet »). Jamais classées holding (on ne
    connaît pas leur NAF) : elles restent toujours visibles, même avec le filtre « masquer les
    holdings » coché."""
    cat = charger_catalogue(FICHIER_CATALOGUE.stat().st_mtime if FICHIER_CATALOGUE.exists() else 0)
    vide = toutes.iloc[0:0].copy()
    if not len(cat):
        return vide
    cat = cat.assign(deja=correspondance_graphe(cat, toutes))
    absentes = cat[cat["deja"] == ""].copy()
    if not len(absentes):
        return vide

    out = pd.DataFrame(index=absentes.index, columns=toutes.columns, dtype=object)
    out[:] = ""
    out["nom"] = absentes["nom"]
    out["adresse"] = absentes["adresse"]
    out["code_postal"] = absentes["code_postal"]
    out["ville"] = absentes["commune"]
    code_eff = absentes["tranche_effectif"].str.strip()
    out["tranche_effectif"] = code_eff.map(_TRANCHES_EFFECTIF).fillna("")
    out["groupe_effectif"] = code_eff.map(_GROUPE_EFFECTIF).fillna(NON_RENSEIGNE)
    out["statut_administratif"] = absentes["etat_administratif"].map({"A": "Actif", "C": "Cessé"}).fillna(
        absentes["etat_administratif"])
    out["pays"] = np.where(absentes["siren"] != "", "France", "")
    out["zone"] = [_zone_catalogue(cp, s) for cp, s in zip(absentes["code_postal"], absentes["siren"])]
    out["niveau"] = -1
    out["niveau_lib"] = "Catalogue"
    out["type_court"] = "Catalogue"
    out["est_holding"] = False
    out["source_relation"] = "Catalogue officiel des investissements, eurazeo.com"
    out["source_enrichissement"] = absentes["source"]
    out["date_collecte"] = absentes["verifie_le"]
    sr = absentes["siren"].replace("", "aucun (nom sans correspondance Sirene)")
    out["verification"] = (
        "Catalogue eurazeo.com, rapproché par le nom (score de similarité "
        + absentes["score_correspondance"].replace("", "inconnu") + "), à vérifier avant usage. "
        "SIREN candidat : " + sr + ".")
    out["identifiant"] = ""   # cf. docstring : jamais le SIREN candidat ici
    out["cle"] = out["nom"] + "  ·  sans identifiant"
    out["texte_recherche"] = (absentes["nom"] + " " + absentes["secteur"] + " " + absentes["adresse"]).str.lower()
    out["etat_web"] = np.where(absentes["statut"].str.lower() == "cédée", "cédée (site Eurazeo)", "")

    # Colonnes numériques reprises telles quelles du catalogue quand elles existent (produites par
    # enrichir_catalogue_finances.py / geocoder_catalogue.py) ; sinon vides, jamais devinées.
    COLONNES_CATALOGUE_NUMERIQUES = ["latitude", "longitude", "chiffre_affaires", "resultat_net",
        "annee_finances", "chiffre_affaires_annee_precedente", "croissance_ca_pct",
        "chiffre_affaires_estime_bilan", "resultat_net_estime_bilan", "effectif_estime_bilan"]
    for c in ("niveau", "pourcentage_detention", "latitude", "longitude", "nb_etablissements",
              "nb_etablissements_ouverts", "chiffre_affaires", "resultat_net", "annee_finances",
              "chiffre_affaires_annee_precedente", "croissance_ca_pct",
              "chiffre_affaires_estime_bilan", "resultat_net_estime_bilan", "effectif_estime_bilan",
              "page_deu", "part_economique_eurazeo", "annee_creation"):
        if c not in out.columns:
            continue
        if c == "niveau":
            out[c] = -1
        elif c in COLONNES_CATALOGUE_NUMERIQUES and c in absentes.columns:
            out[c] = pd.to_numeric(absentes[c], errors="coerce")
        else:
            out[c] = np.nan
    if "latitude" in out.columns:
        out["geo_precision"] = np.where(pd.to_numeric(out["latitude"], errors="coerce").notna(), "adresse", "")
    # Date d'installation et lignes sources du Tier 2 (texte) : copiées telles quelles si présentes.
    for c in ("date_installation_siege", "bilan_ligne_source_ca", "bilan_ligne_source_resultat",
              "bilan_ligne_source_effectif"):
        if c in out.columns:
            out[c] = absentes[c] if c in absentes.columns else ""
    return out.reset_index(drop=True)


def noms_correspondants(cles: str, noms) -> str:
    """Noms de sociétés du graphe dont un mot-clé figure dans le nom (rapprochement par le nom)."""
    mots = [c.strip() for c in cles.split("|") if c.strip()]
    trouves = sorted({n for n in noms if any(f" {m} " in f" {normaliser(n)} " for m in mots)})
    return ", ".join(trouves) or "—"


def evenements_de(nom: str) -> list[dict]:
    """Événements dont un mot-clé figure dans le nom de la société (rapprochement par le nom), du plus récent au plus ancien."""
    e = charger_evenements(FICHIER_EVENEMENTS.stat().st_mtime if FICHIER_EVENEMENTS.exists() else 0)
    n = f" {normaliser(nom)} "
    return [r.to_dict() for _, r in e.iterrows() if any(f" {c.strip()} " in n for c in r["cles"].split("|") if c.strip())]


@st.cache_data(show_spinner=False)
def charger(_signature) -> pd.DataFrame:
    df = pd.read_csv(CHEMIN, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    for f in fichiers_niveaux():
        df = pd.concat([df, pd.read_csv(f, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)],
                       ignore_index=True)
    for c in COLONNES_TEXTE:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()
    for c in COLONNES_NOMBRE:
        df[c] = pd.to_numeric(df[c] if c in df.columns else np.nan, errors="coerce")
    df["niveau"] = df["niveau"].fillna(1).astype(int)
    df["annee_creation"] = pd.to_numeric(df["date_creation"].str[:4], errors="coerce")
    df["zone"] = df["zone"].where(df["zone"].isin(theme.ZONES), theme.ZONE_ETRANGER)
    df["groupe_effectif"] = df["groupe_effectif"].replace("", NON_RENSEIGNE)
    df["identifiant"] = np.where(df["siren"] != "", df["siren"], df["identifiant_etranger"])
    df["cle"] = df["nom"] + "  ·  " + np.where(df["identifiant"] != "", df["identifiant"], "sans identifiant")
    df["texte_recherche"] = (df["nom"] + " " + df["siren"] + " " + df["adresse"] + " " + df["ville"] + " "
                             + df["identifiant_etranger"]).str.lower()
    df["niveau_lib"] = "Niveau " + df["niveau"].astype(str)
    df["etat_web"] = df["nom"].map(lambda n: (evenements_de(n) or [{"etat": ""}])[0]["etat"])
    df["est_holding"] = df["naf_code"].isin(HOLDING_NAF)
    df["type_court"] = np.where(df["type_relation"].str.startswith("Filiale"), "Filiale",
                                np.where(df["type_relation"].str.startswith("Participation"), "Participation",
                                         df["type_relation"]))
    return df


def charger_tout():
    if not CHEMIN.exists():
        st.error(
            "Le fichier `data/entreprises_detaillees.csv` est introuvable. Lance d'abord "
            "`python enrichir_details.py` à la racine du projet : il le crée et le copie ici."
        )
        st.stop()
    df = charger((CHEMIN.stat().st_mtime, tuple((f.name, f.stat().st_mtime) for f in fichiers_niveaux()),
                  FICHIER_EVENEMENTS.stat().st_mtime if FICHIER_EVENEMENTS.exists() else 0))
    cat = lignes_catalogue(df)
    ensemble = pd.concat([df, cat], ignore_index=True) if len(cat) else df
    # Cycle de bail 3/6/9 et score d'opportunité « déménagement » (dashboard/lib/scoring.py) :
    # calculés à chaque chargement (jamais écrits sur disque), sur Eurazeo et le catalogue compris,
    # pour que la ligne « Eurazeo » elle-même ait aussi un statut de bail si sa date est connue.
    return scoring.appliquer(ensemble)


@st.cache_data(show_spinner=False)
def _charger_liens(_signature) -> pd.DataFrame:
    morceaux = [pd.read_csv(f, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
                for f in fichiers_liens()]
    if not morceaux:
        return pd.DataFrame(columns=["niveau", "siren_detentrice", "nom_detentrice", "siren_detenue", "nom_detenue",
                                     "pourcentage_detention"])
    liens = pd.concat(morceaux, ignore_index=True)
    liens["pourcentage_detention"] = pd.to_numeric(liens["pourcentage_detention"], errors="coerce")
    return liens


def charger_liens() -> pd.DataFrame:
    """Liens entre deux sociétés déjà dans le graphe (arêtes supplémentaires : plusieurs détenteurs)."""
    return _charger_liens(tuple((f.name, f.stat().st_mtime) for f in fichiers_liens()))


def donnees():
    """(toutes les sociétés du 1er cercle, sélection filtrée, société mère ou None)."""
    df = charger_tout()
    mere = df[df["niveau"] == 0]
    toutes = df[df["niveau"] != 0].copy()   # tout sauf Eurazeo elle-même : niveaux 1+ ET le catalogue (niveau -1)
    filtre = st.session_state.get("df_filtre")
    if filtre is None:
        filtre = toutes
    return toutes, filtre, (mere.iloc[0] if len(mere) else None)


def exiger_selection(filtre):
    if filtre.empty:
        st.markdown('<h1 class="titre">Aucune société ne correspond aux filtres</h1>', unsafe_allow_html=True)
        st.markdown('<p class="chapo">Élargis la zone, les niveaux, le type de relation ou la détention minimale dans '
                    'la colonne de gauche, ou vide la recherche.</p>', unsafe_allow_html=True)
        st.stop()


def afficher_filtres(toutes: pd.DataFrame) -> pd.DataFrame:
    sb = st.sidebar
    sb.markdown("### Filtres")

    q = sb.text_input("Rechercher une société", key="f_q", placeholder="Nom, SIREN, adresse…",
                      help="Cherche dans le nom, le SIREN et l'adresse. S'applique à toutes les pages, "
                           "y compris la liste de la fiche société.").strip().lower()
    def _cle_niveau(lib):
        return (1, 0) if lib == "Catalogue" else (0, int(lib.rsplit(" ", 1)[-1]))
    niveaux_presents = sorted(toutes["niveau_lib"].unique(), key=_cle_niveau)
    niveaux_sel = niveaux_presents
    if len(niveaux_presents) > 1:
        sb.markdown("<div style='font-size:.875rem;margin-bottom:.25rem'>Niveaux</div>", unsafe_allow_html=True)
        niveaux_sel = sb.pills("Niveaux", niveaux_presents, selection_mode="multi", default=niveaux_presents,
                               key="f_niveaux", label_visibility="collapsed",
                               help="Niveau 1 = détenues directement par Eurazeo. Niveau 2 = détenues par ces "
                                    "holdings, lues dans leurs comptes annuels. Niveau 3 = détenues par les holdings "
                                    "du niveau 2, etc. Catalogue = sociétés listées par Eurazeo sur son site mais "
                                    "dont la chaîne de détention n'a pas (encore) été retrouvée.") or []
    sb.markdown("<div style='font-size:.875rem;margin-bottom:.25rem'>Zone géographique</div>", unsafe_allow_html=True)
    zones_dispo = [z for z in theme.ZONES if z in set(toutes["zone"])]
    zones = sb.pills("Zone géographique", zones_dispo, selection_mode="multi", default=zones_dispo, key="f_zone",
                     label_visibility="collapsed",
                     help="Paris = code postal 75xxx. France (hors Paris) = tout autre siège en France. "
                          "Étranger = siège hors de France (adresse imprimée dans les documents). "
                          "Non localisée = aucune adresse disponible.") or []
    n_holding = int(toutes["est_holding"].sum())
    sans_holding = sb.checkbox(
        "Masquer les holdings et sociétés de gestion de fonds", value=True, key="f_sans_holding",
        help=f"Retire les sociétés dont le code NAF est 64.20Z (holding), 64.30Z (fonds de placement), "
             f"66.19B (services financiers auxiliaires), 66.30Z (gestion de fonds) ou 70.10Z (siège social) "
             f"— {n_holding} sur {len(toutes)} dans la sélection actuelle. Ces véhicules n'ont généralement pas "
             "de besoin de bureaux propre et leur chiffre d'affaires à 0 avec des pertes (normal pour ce type de "
             "structure) fausse le score d'opportunité : masqués par défaut pour la prospection immobilière. "
             "Une société étrangère sans fiche Sirene n'a pas de code NAF : elle reste affichée même si c'est "
             "probablement aussi une holding.")
    sb.markdown("<div style='font-size:.875rem;margin-bottom:.25rem'>Statut du bail (estimation 3/6/9)</div>",
                unsafe_allow_html=True)
    ordre_urgence = [scoring.LIBELLE_URGENCE[k] for k in (3, 2, 1, 0, None)]
    urgences_dispo = [u for u in ordre_urgence if u in set(toutes["urgence_libelle"])]
    urgences_sel = sb.pills("Statut du bail", urgences_dispo, selection_mode="multi", default=urgences_dispo,
                            key="f_bail", label_visibility="collapsed",
                            help="Estimation à partir de la date d'installation au siège actuel (quand elle est "
                                 "connue) et du cycle de bail commercial 3/6/9 (préavis de 6 mois à chaque "
                                 "échéance triennale). Toujours une estimation, jamais une donnée publiée : "
                                 "voir le détail sur la fiche société.") or []

    sb.markdown("<div style='font-size:.875rem;margin-bottom:.25rem'>Score d'opportunité minimum</div>",
                unsafe_allow_html=True)
    score_min = sb.slider("Score d'opportunité minimum", 0, 100, 0, step=5, key="f_score",
                          label_visibility="collapsed",
                          help="Score de prospection immobilière (0 à 100, pondération bail/finances) : relève ce "
                               "seuil pour ne garder que les opportunités les plus prometteuses. Une société sans "
                               "aucune donnée (bail ni finances) obtient 50 — toujours neutre, jamais une note "
                               "réelle : vérifie le nombre de critères disponibles sur sa fiche avant de t'y fier.")

    adv = sb.expander("Filtres avancés")
    types = sorted(toutes["type_court"].unique())
    types_sel = adv.multiselect("Type de relation", types, default=types, key="f_type",
                               help="Filiale = plus de 50 % du capital détenu. Participation = 50 % ou moins, ou part non publiée.")
    pmin = adv.slider("Détention minimale (%)", 0, 100, 0, key="f_pmin",
                     help="Part du capital détenue par la société détentrice (Eurazeo au niveau 1, la holding "
                          "au-dessus ensuite). Les parts non publiées ne sont pas filtrées.")
    groupes = [g for g in ORDRE_EFFECTIF + [NON_RENSEIGNE] if g in set(toutes["groupe_effectif"])]
    if len(groupes) > 1:
        groupes_sel = adv.multiselect("Effectif salarié", groupes, default=groupes, key="f_eff",
                                     help="Tranche d'effectif déclarée à l'INSEE (Sirene).")
    else:
        groupes_sel = groupes

    if sb.button("Réinitialiser les filtres"):
        for k in ("f_q", "f_zone", "f_type", "f_pmin", "f_eff", "f_niveaux", "f_sans_holding", "f_bail", "f_score"):
            st.session_state.pop(k, None)
        st.rerun()

    m = (toutes["zone"].isin(zones) & toutes["type_court"].isin(types_sel)
         & toutes["groupe_effectif"].isin(groupes_sel))
    m &= toutes["niveau_lib"].isin(niveaux_sel)
    m &= toutes["urgence_libelle"].isin(urgences_sel)
    if score_min > 0:   # 0 = pas de filtre : ne masque jamais une société non notée (cessée, par ex.)
        m &= toutes["score_opportunite"].fillna(-1) >= score_min
    m &= toutes["pourcentage_detention"].fillna(100) >= pmin
    if sans_holding:
        m &= ~toutes["est_holding"]
    if q:
        m &= toutes["texte_recherche"].str.contains(q, regex=False)
    filtre = toutes[m].copy()
    sb.caption(f"{len(filtre)} société(s) sur {len(toutes)}")
    st.session_state["df_filtre"] = filtre
    return filtre
