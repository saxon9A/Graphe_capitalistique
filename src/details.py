"""
Mise en forme détaillée d'une société pour le dashboard : adresse exacte,
géolocalisation, effectif, activité, forme juridique, dirigeants, finances.

Source principale : API Recherche d'Entreprises (agrège INSEE Sirene + INPI
RNE, aucune clé). Les sociétés étrangères n'ont pas de fiche Sirene : on
reprend l'adresse imprimée dans le DEU Eurazeo, sans rien ajouter d'autre.

Règle : un champ absent de la source reste VIDE. Aucune valeur inventée.
"""

from __future__ import annotations

# --- Tranches d'effectif salarié (nomenclature INSEE officielle) -----------
TRANCHES_EFFECTIF = {
    "NN": "Non employeuse / effectif inconnu",
    "00": "0 salarié",
    "01": "1 à 2 salariés",
    "02": "3 à 5 salariés",
    "03": "6 à 9 salariés",
    "11": "10 à 19 salariés",
    "12": "20 à 49 salariés",
    "21": "50 à 99 salariés",
    "22": "100 à 199 salariés",
    "31": "200 à 249 salariés",
    "32": "250 à 499 salariés",
    "41": "500 à 999 salariés",
    "42": "1 000 à 1 999 salariés",
    "51": "2 000 à 4 999 salariés",
    "52": "5 000 à 9 999 salariés",
    "53": "10 000 salariés et plus",
}
ORDRE_TRANCHES = list(TRANCHES_EFFECTIF.keys())

# Regroupement lisible pour les graphiques
GROUPE_EFFECTIF = {
    "NN": "Non employeuse / inconnu", "00": "0 salarié",
    "01": "1 à 9", "02": "1 à 9", "03": "1 à 9",
    "11": "10 à 49", "12": "10 à 49",
    "21": "50 à 249", "22": "50 à 249", "31": "50 à 249",
    "32": "250 et plus", "41": "250 et plus", "42": "250 et plus",
    "51": "250 et plus", "52": "250 et plus", "53": "250 et plus",
}

# --- Sections de la NAF rév. 2 ---------------------------------------------
SECTIONS_NAF = {
    "A": "Agriculture, sylviculture, pêche",
    "B": "Industries extractives",
    "C": "Industrie manufacturière",
    "D": "Électricité, gaz, vapeur",
    "E": "Eau, assainissement, déchets",
    "F": "Construction",
    "G": "Commerce, réparation automobile",
    "H": "Transports et entreposage",
    "I": "Hébergement et restauration",
    "J": "Information et communication",
    "K": "Activités financières et d'assurance",
    "L": "Activités immobilières",
    "M": "Activités spécialisées, scientifiques et techniques",
    "N": "Services administratifs et de soutien",
    "O": "Administration publique",
    "P": "Enseignement",
    "Q": "Santé humaine et action sociale",
    "R": "Arts, spectacles, activités récréatives",
    "S": "Autres activités de services",
    "T": "Activités des ménages",
    "U": "Activités extra-territoriales",
}

# Quelques codes NAF fréquents chez des holdings / sociétés d'investissement.
# Pour un code absent de cette liste on affiche le code + la section, rien de plus.
NAF_LIBELLES = {
    "64.20Z": "Activités des sociétés holding",
    "64.30Z": "Fonds de placement et entités financières similaires",
    "64.19Z": "Autres intermédiations monétaires",
    "64.92Z": "Autres activités de crédit",
    "64.99Z": "Autres activités des services financiers",
    "66.12Z": "Courtage de valeurs mobilières et de marchandises",
    "66.19B": "Autres activités auxiliaires de services financiers",
    "66.30Z": "Gestion de fonds",
    "68.20A": "Location de logements",
    "68.20B": "Location de terrains et d'autres biens immobiliers",
    "68.31Z": "Agences immobilières",
    "70.10Z": "Activités des sièges sociaux",
    "70.22Z": "Conseil pour les affaires et autres conseils de gestion",
}

# --- Formes juridiques courantes (catégories juridiques INSEE) --------------
NATURES_JURIDIQUES = {
    "5499": "SARL",
    "5710": "SAS",
    "5720": "SASU",
    "5599": "SA à conseil d'administration",
    "5699": "SA à directoire",
    "5800": "Société européenne (SE)",
    "6540": "Société civile immobilière (SCI)",
    "6599": "Autre société civile",
}

# --- Régions (codes INSEE) -------------------------------------------------
REGIONS = {
    "01": "Guadeloupe", "02": "Martinique", "03": "Guyane", "04": "La Réunion", "06": "Mayotte",
    "11": "Île-de-France", "24": "Centre-Val de Loire", "27": "Bourgogne-Franche-Comté",
    "28": "Normandie", "32": "Hauts-de-France", "44": "Grand Est", "52": "Pays de la Loire",
    "53": "Bretagne", "75": "Nouvelle-Aquitaine", "76": "Occitanie",
    "84": "Auvergne-Rhône-Alpes", "93": "Provence-Alpes-Côte d'Azur", "94": "Corse",
}

# --- Position APPROXIMATIVE (centre-ville) des villes étrangères du DEU -----
# Utilisée seulement pour placer un point sur la carte ; marquée
# geo_precision = "ville" dans le fichier. Jamais présentée comme exacte.
VILLES_ETRANGERES = {
    "Luxembourg": (49.6116, 6.1319),
    "Royaume-Uni": (51.5074, -0.1278),  # Londres
}

# Villes étrangères reconnues dans les adresses imprimées des comptes annuels.
# Position APPROXIMATIVE (centre-ville), marquée geo_precision = "ville".
# (mots-clés sans accents, ville, pays, latitude, longitude)
GEO_ETRANGER = [
    (("long beach, ms", "long beach ms"), "Long Beach (Mississippi)", "États-Unis", 30.3505, -89.1528),
    (("county of kent",), "Dover (Delaware)", "États-Unis", 39.1582, -75.5244),
    (("wilmington",), "Wilmington (Delaware)", "États-Unis", 39.7391, -75.5398),
    (("new york",), "New York", "États-Unis", 40.7128, -74.0060),
    (("schenectady",), "Schenectady (New York)", "États-Unis", 42.8142, -73.9396),
    (("winston-salem", "winston salem"), "Winston-Salem (Caroline du Nord)", "États-Unis", 36.0999, -80.2442),
    (("orlando",), "Orlando (Floride)", "États-Unis", 28.5383, -81.3792),
    (("los angeles",), "Los Angeles", "États-Unis", 34.0522, -118.2437),
    (("amesterdam", "amsterdam"), "Amsterdam", "Pays-Bas", 52.3676, 4.9041),
    (("gothenbourg", "gothenburg"), "Göteborg", "Suède", 57.7089, 11.9746),
    (("luxembourg",), "Luxembourg", "Luxembourg", 49.6116, 6.1319),
    (("london", "londres"), "Londres", "Royaume-Uni", 51.5074, -0.1278),
]


def localiser_adresse_etrangere(adresse: str):
    """(ville, pays, lat, lon) si l'adresse imprimée cite une ville étrangère connue, sinon None."""
    import unicodedata
    a = "".join(c for c in unicodedata.normalize("NFKD", (adresse or "").lower()) if not unicodedata.combining(c))
    for mots, ville, pays, lat, lon in GEO_ETRANGER:
        if any(m in a for m in mots):
            return ville, pays, lat, lon
    return None


ZONE_PARIS = "Paris"
ZONE_FRANCE = "France (hors Paris)"
ZONE_ETRANGER = "Étranger"
ZONE_NON_LOCALISEE = "Non localisée"  # aucune adresse imprimée ni SIREN : on ne devine pas


def _flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _nettoyer_nom(nom: str) -> str:
    """Retire les renvois de bas de page du DEU : 'Eurazeo UK Limited (2)', 'S.F.G.I.,'."""
    import re
    nom = re.sub(r"\s*\(\d\)\s*$", "", nom or "").strip()
    return nom.rstrip(",").strip()


def _dirigeants_texte(dirigeants, maximum: int = 6) -> str:
    morceaux = []
    for d in (dirigeants or [])[:maximum]:
        qualite = d.get("qualite") or ""
        if (d.get("type_dirigeant") or "").lower().startswith("personne morale") or d.get("denomination"):
            nom = d.get("denomination") or ""
        else:
            nom = " ".join(x for x in [(d.get("prenoms") or "").split(",")[0].strip(), d.get("nom") or ""] if x)
        if nom:
            morceaux.append(f"{qualite} : {nom}" if qualite else nom)
    return " | ".join(morceaux)


def _deux_dernieres_finances(finances: dict):
    """Dernier exercice ayant un CA ou un résultat -> (annee, ca, resultat, ca_exercice_precedent).
    Le 4e élément sert uniquement à calculer une croissance du CA d'une année sur l'autre (score
    d'opportunité du dashboard) ; il reste None si un seul exercice est disponible dans la source."""
    if not isinstance(finances, dict):
        return None, None, None, None
    annees = sorted(finances.keys(), reverse=True)
    for i, annee in enumerate(annees):
        f = finances[annee] or {}
        if f.get("ca") is not None or f.get("resultat_net") is not None:
            ca_prec = None
            for annee_prec in annees[i + 1:]:
                f2 = finances[annee_prec] or {}
                if f2.get("ca") is not None:
                    ca_prec = f2.get("ca")
                    break
            return annee, f.get("ca"), f.get("resultat_net"), ca_prec
    return None, None, None, None


def zone_depuis_adresse(pays: str | None, code_postal: str | None, departement: str | None) -> str:
    if pays and pays != "France":
        return ZONE_ETRANGER
    if (departement or "").strip() == "75" or (code_postal or "").strip().startswith("75"):
        return ZONE_PARIS
    return ZONE_FRANCE


def ligne_depuis_api(brut: dict) -> dict:
    """Aplatit un résultat brut de l'API Recherche d'Entreprises."""
    siege = brut.get("siege") or {}
    complements = brut.get("complements") or {}
    tranche = brut.get("tranche_effectif_salarie") or siege.get("tranche_effectif_salarie")
    section = brut.get("section_activite_principale")
    naf = brut.get("activite_principale") or siege.get("activite_principale")
    nature = str(brut.get("nature_juridique") or "")
    annee_fin, ca, resultat, ca_prec = _deux_dernieres_finances(brut.get("finances"))
    croissance_ca_pct = round((ca - ca_prec) / ca_prec * 100, 1) if ca is not None and ca_prec else None
    cp = siege.get("code_postal")
    dep = siege.get("departement")
    region = siege.get("region")
    pays = "France" if not siege.get("libelle_pays_etranger") else siege.get("libelle_pays_etranger")

    return {
        "siren": brut.get("siren"),
        "siret_siege": siege.get("siret"),
        "nom": brut.get("nom_complet") or brut.get("nom_raison_sociale"),
        "sigle": brut.get("sigle"),
        "pays": pays,
        "zone": zone_depuis_adresse(pays, cp, dep),
        "adresse": siege.get("adresse") or siege.get("geo_adresse"),
        "code_postal": cp,
        "ville": siege.get("libelle_commune") or siege.get("commune"),
        "departement": dep,
        "region": REGIONS.get(str(region), region),
        "latitude": _flt(siege.get("latitude")),
        "longitude": _flt(siege.get("longitude")),
        "geo_precision": "adresse" if _flt(siege.get("latitude")) is not None else None,
        "statut_administratif": {"A": "Actif", "C": "Cessé"}.get(brut.get("etat_administratif"), brut.get("etat_administratif")),
        "date_creation": brut.get("date_creation"),
        "date_fermeture": brut.get("date_fermeture"),
        # Date d'installation à l'adresse ACTUELLE (celle de l'établissement siège, pas de la société) :
        # sert au calcul du cycle de bail commercial 3/6/9 dans le dashboard. `date_debut_activite`
        # est le champ le plus juste (début de l'activité à cette adresse précise) ; `date_creation`
        # du siège (pas celui de la société, utilisé juste au-dessus) sert de repli si absent. Si aucun
        # des deux n'est présent, reste vide : jamais remplacé par la date de création de la société.
        "date_installation_siege": siege.get("date_debut_activite") or siege.get("date_creation"),
        "forme_juridique_code": nature or None,
        "forme_juridique": NATURES_JURIDIQUES.get(nature) or (f"Code {nature}" if nature else None),
        "naf_code": naf,
        "naf_libelle": NAF_LIBELLES.get(naf),
        "naf_section_code": section,
        "naf_section": SECTIONS_NAF.get(section),
        "tranche_effectif_code": tranche,
        "tranche_effectif": TRANCHES_EFFECTIF.get(str(tranche)) if tranche is not None else None,
        "groupe_effectif": GROUPE_EFFECTIF.get(str(tranche)) if tranche is not None else None,
        "annee_tranche_effectif": brut.get("annee_tranche_effectif_salarie"),
        "caractere_employeur": brut.get("caractere_employeur"),
        "categorie_entreprise": brut.get("categorie_entreprise"),
        "nb_etablissements": brut.get("nombre_etablissements"),
        "nb_etablissements_ouverts": brut.get("nombre_etablissements_ouverts"),
        "dirigeants": _dirigeants_texte(brut.get("dirigeants")),
        "annee_finances": annee_fin,
        "chiffre_affaires": ca,
        "resultat_net": resultat,
        "chiffre_affaires_annee_precedente": ca_prec,
        "croissance_ca_pct": croissance_ca_pct,
        "est_ess": complements.get("est_ess"),
        "source_enrichissement": "Sirene (INSEE) + RNE (INPI) via recherche-entreprises.api.gouv.fr",
    }


def ligne_depuis_deu_etranger(deu: dict) -> dict:
    """Société sans SIREN (étrangère) : uniquement ce que le DEU imprime."""
    pays = deu.get("pays_deu")
    pos = VILLES_ETRANGERES.get(pays)
    return {
        "siren": None,
        "siret_siege": None,
        "nom": _nettoyer_nom(deu.get("nom_candidat")),
        "pays": pays or "Étranger (pays non précisé)",
        "zone": ZONE_ETRANGER,
        "adresse": deu.get("adresse_deu"),
        "ville": (deu.get("adresse_deu") or "").split(",")[-1].strip() or None,
        "latitude": pos[0] if pos else None,
        "longitude": pos[1] if pos else None,
        "geo_precision": "ville" if pos else None,
        "statut_administratif": "Non vérifié (registre étranger)",
        "identifiant_etranger": deu.get("identifiant_etranger"),
        "source_enrichissement": "Adresse imprimée dans le DEU Eurazeo 2025 (pas de fiche Sirene)",
    }


COLONNES = [
    "niveau", "siren_detentrice", "nom_detentrice",
    "type_relation", "validation", "pourcentage_detention", "page_deu",
    "siren", "siret_siege", "identifiant_etranger", "nom", "sigle",
    "pays", "zone", "adresse", "code_postal", "ville", "departement", "region",
    "latitude", "longitude", "geo_precision",
    "statut_administratif", "date_creation", "date_fermeture", "date_installation_siege",
    "forme_juridique_code", "forme_juridique",
    "naf_code", "naf_libelle", "naf_section_code", "naf_section",
    "tranche_effectif_code", "tranche_effectif", "groupe_effectif", "annee_tranche_effectif",
    "caractere_employeur", "categorie_entreprise",
    "nb_etablissements", "nb_etablissements_ouverts",
    "dirigeants", "annee_finances", "chiffre_affaires", "resultat_net",
    "chiffre_affaires_annee_precedente", "croissance_ca_pct", "est_ess",
    "source_relation", "source_enrichissement", "date_collecte",
    "part_economique_eurazeo", "verification",
]
