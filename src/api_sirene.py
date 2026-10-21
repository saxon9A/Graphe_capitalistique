"""
Enrichissement OPTIONNEL : API Sirene de l'INSEE (nouveau portail unifié
api.insee.fr).

Ce module n'est utile que si l'API Recherche d'Entreprises (aucune clé) ne
fournit pas un champ dont tu as besoin. Dans la majorité des cas, ce projet
peut fonctionner SANS cette clé : laisse INSEE_API_KEY vide dans .env et le
pipeline enrichira uniquement via api_recherche_entreprises.py.

Pour obtenir une clé (gratuite) :
  1. Créer un compte sur https://portail-api.insee.fr
  2. Dans l'espace "Mes applications", créer une application
  3. S'abonner au produit "API Sirene"
  4. Récupérer la "clé d'intégration" (INSEE_API_KEY)

Authentification : header "X-INSEE-Api-Key-Integration: <clé>".
(Les anciennes clés consumer_key/consumer_secret OAuth2 du portail historique
api.insee.fr/catalogue sont dépréciées ; si tu as un ancien compte, régénère
une clé sur le nouveau portail unifié.)
"""

import time

import requests

from . import config
from .logger import log


def cle_configuree() -> bool:
    return bool(config.INSEE_API_KEY)


def get_unite_legale(siren: str) -> dict | None:
    """Appelle GET /siren/{siren} de l'API Sirene. Retourne None si pas de clé configurée."""
    if not cle_configuree():
        return None

    url = f"{config.INSEE_SIRENE_BASE_URL}/siren/{siren}"
    headers = {"X-INSEE-Api-Key-Integration": config.INSEE_API_KEY, "Accept": "application/json"}

    for tentative in range(1, config.MAX_TENTATIVES + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=config.TIMEOUT_JSON)
        except requests.RequestException as exc:
            log("enrichissement", "sirene_insee", "erreur",
                f"Tentative {tentative}/{config.MAX_TENTATIVES} : {exc}", siren=siren, url=url)
            time.sleep(config.PAUSE_ENTRE_APPELS * tentative)
            continue

        if resp.status_code == 200:
            log("enrichissement", "sirene_insee", "ok", "", siren=siren, url=url, code_http=200)
            return resp.json().get("uniteLegale")

        if resp.status_code == 404:
            log("enrichissement", "sirene_insee", "introuvable", "SIREN non trouvé.",
                siren=siren, url=url, code_http=404)
            return None

        if resp.status_code in (401, 403):
            log("enrichissement", "sirene_insee", "non_autorise",
                f"Clé INSEE invalide ou non abonnée à l'API Sirene (HTTP {resp.status_code}).",
                siren=siren, url=url, code_http=resp.status_code)
            return None

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            log("enrichissement", "sirene_insee", "indisponible",
                f"429, attente {retry_after}s.", siren=siren, url=url, code_http=429)
            time.sleep(retry_after)
            continue

        log("enrichissement", "sirene_insee", "erreur",
            f"HTTP {resp.status_code} : {resp.text[:300]}",
            siren=siren, url=url, code_http=resp.status_code)
        time.sleep(config.PAUSE_ENTRE_APPELS * tentative)

    return None
