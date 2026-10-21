"""
API Recherche d'Entreprises (DINUM / data.gouv.fr).

Aucune clé, aucune authentification. Source officielle utilisée par
annuaire-entreprises.data.gouv.fr, agrégeant INSEE Sirene + INPI RNE.

Documentation : https://recherche-entreprises.api.gouv.fr/

C'est la source d'enrichissement principale de ce projet : statut
administratif, adresse du siège, code/libellé NAF, tranche d'effectif,
dirigeants, sans clé à demander.
"""

import time

import requests

from . import config
from .logger import log

BASE_URL = config.RECHERCHE_ENTREPRISES_BASE_URL


def get_entreprise_par_siren(siren: str) -> dict | None:
    """
    Recherche une entreprise par SIREN via /search?q={siren}.
    Retourne le premier résultat dont le SIREN correspond exactement, sinon None.
    """
    url = f"{BASE_URL}/search"
    params = {"q": siren, "page": 1, "per_page": 5}

    for tentative in range(1, config.MAX_TENTATIVES + 1):
        try:
            resp = requests.get(url, params=params, timeout=config.TIMEOUT_JSON)
        except requests.RequestException as exc:
            log("enrichissement", "recherche_entreprises", "erreur",
                f"Tentative {tentative}/{config.MAX_TENTATIVES} : {exc}",
                siren=siren, url=resp.url if "resp" in dir() else url)
            time.sleep(config.PAUSE_ENTRE_APPELS * tentative)
            continue

        if resp.status_code == 200:
            data = resp.json()
            resultats = data.get("results", [])
            for r in resultats:
                if r.get("siren") == siren:
                    log("enrichissement", "recherche_entreprises", "ok", "",
                        siren=siren, url=resp.url, code_http=200)
                    return r
            if resultats:
                # Aucun match exact sur le SIREN : on journalise mais on ne
                # retourne rien pour éviter de mélanger deux entreprises.
                log("enrichissement", "recherche_entreprises", "introuvable",
                    "Résultats renvoyés mais aucun SIREN exactement identique.",
                    siren=siren, url=resp.url, code_http=200)
            else:
                log("enrichissement", "recherche_entreprises", "introuvable",
                    "Aucun résultat.", siren=siren, url=resp.url, code_http=200)
            return None

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 3))
            log("enrichissement", "recherche_entreprises", "indisponible",
                f"429, attente {retry_after}s.", siren=siren, url=resp.url, code_http=429)
            time.sleep(retry_after)
            continue

        log("enrichissement", "recherche_entreprises", "erreur",
            f"HTTP {resp.status_code} : {resp.text[:300]}",
            siren=siren, url=resp.url, code_http=resp.status_code)
        time.sleep(config.PAUSE_ENTRE_APPELS * tentative)

    return None


def rechercher_par_nom(nom: str, max_resultats: int = 5) -> list[dict]:
    """
    Recherche par dénomination (utilisé pour résoudre un SIREN à partir d'un
    nom de société trouvé dans un document, ex. le DEU Eurazeo ou un acte
    INPI). Retourne une liste de résultats bruts (le meilleur score en
    premier) : À l'appelant de choisir/valider le bon, une recherche par nom
    est ambiguë par nature (homonymes, filiales du même nom dans des pays
    différents, etc.).
    """
    url = f"{BASE_URL}/search"
    params = {"q": nom, "page": 1, "per_page": max_resultats}
    try:
        resp = requests.get(url, params=params, timeout=config.TIMEOUT_JSON)
    except requests.RequestException as exc:
        log("resolution_nom", "recherche_entreprises", "erreur", f"Erreur réseau : {exc}", url=url)
        return []

    if resp.status_code != 200:
        log("resolution_nom", "recherche_entreprises", "erreur",
            f"HTTP {resp.status_code}", url=resp.url, code_http=resp.status_code)
        return []

    resultats = resp.json().get("results", [])
    log("resolution_nom", "recherche_entreprises", "ok" if resultats else "introuvable",
        f"{len(resultats)} résultat(s) pour '{nom}'.", url=resp.url, code_http=200)
    return resultats


def normaliser_enrichissement(resultat: dict) -> dict:
    """
    Transforme un résultat brut de l'API Recherche d'Entreprises en un
    sous-ensemble de champs standardisés utilisé par le reste du programme.
    Les champs absents restent à None (jamais de valeur inventée).
    """
    if not resultat:
        return {}

    siege = resultat.get("siege", {}) or {}

    tranche = resultat.get("tranche_effectif_salarie")
    libelle_tranche = resultat.get("tranche_effectif_salarie_libelle") or resultat.get("libelle_tranche_effectif_salarie")

    return {
        "statut_administratif": resultat.get("etat_administratif"),  # "A" actif / "C" cessé
        "adresse_siege": siege.get("adresse") or resultat.get("siege", {}).get("geo_adresse"),
        "code_naf": resultat.get("activite_principale"),
        "libelle_naf": resultat.get("libelle_activite_principale") or resultat.get("activite_principale_libelle"),
        "tranche_effectif": tranche,
        "libelle_tranche_effectif": libelle_tranche,
        "nombre_exact_salaries": None,  # non fourni par cette API : reste explicitement absent
        "date_donnees": resultat.get("date_mise_a_jour") or resultat.get("date_mise_a_jour_insee"),
        "source_enrichissement": "recherche-entreprises.api.gouv.fr",
    }
