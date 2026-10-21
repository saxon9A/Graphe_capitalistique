"""
Option B — API Entreprise, endpoint « liens capitalistiques » (DGFIP).

Documentation : https://entreprise.api.gouv.fr/catalogue/dgfip/liens_capitalistiques
Swagger       : https://entreprise.api.gouv.fr/developpeurs/openapi#tag/Informations-financieres/paths/~1v3~1dgfip~1unites_legales~1%7Bsiren%7D~1liens_capitalistiques~1%7Byear%7D/get

Endpoint réel (confirmé) :
    GET /v3/dgfip/unites_legales/{siren}/liens_capitalistiques/{year}

Paramètres de requête OBLIGATOIRES sur CET appel comme sur tous les appels
API Entreprise (sinon réponse 422) :
    - context   : cadre de la demande (texte libre)
    - object    : raison de l'appel / identifiant de procédure (< 50 caractères)
    - recipient : SIRET de l'ORGANISME PUBLIC habilité à utiliser la donnée
                  (PAS le SIRET du demandeur si c'est un particulier/société privée)

Authentification : header "Authorization: Bearer <token>".

⚠️ IMPORTANT (vérifié sur la documentation officielle, octobre 2026) :
Cette API est explicitement réservée aux "administrations" et son paramètre
`recipient` doit être le SIRET d'une organisation PUBLIQUE habilitée.
L'accès se demande via https://datapass.api.gouv.fr/demandes/api-entreprise/nouveau
qui comporte une vérification d'éligibilité. Un particulier ou une société
privée (hors éditeur de logiciel travaillant pour une administration) n'est
en général PAS éligible à l'habilitation. Ne pas supposer qu'un simple compte
suffit : voir le README pour le détail.

Cette fonction est néanmoins implémentée et prête à l'emploi : si tu obtiens
un jour un token (ex. via une structure publique, une association, un POC
encadré par une administration...), il suffit de renseigner les variables
d'environnement pour que l'extraction fonctionne sans changement de code.
"""

import time

import requests

from . import config
from .logger import log


class AccesNonAutorise(Exception):
    """Levée quand le token/habilitation ne permet pas d'appeler cette API."""


def jeton_configure() -> bool:
    return bool(config.API_ENTREPRISE_TOKEN and config.API_ENTREPRISE_RECIPIENT)


def tester_acces() -> dict:
    """
    Vérifie ce que permet le token configuré via l'endpoint d'introspection
    /v3/token/introspect (ne consomme pas de quota, ne nécessite pas de SIREN).

    Retourne un dict {ok, scopes, message}.
    """
    if not config.API_ENTREPRISE_TOKEN:
        msg = "Aucun API_ENTREPRISE_TOKEN configuré dans .env : option B non testée."
        log("test_acces", "api_entreprise", "non_autorise", msg)
        return {"ok": False, "scopes": [], "message": msg}

    url = f"{config.API_ENTREPRISE_BASE_URL}/v3/token/introspect"
    headers = {"Authorization": f"Bearer {config.API_ENTREPRISE_TOKEN}"}
    try:
        resp = requests.get(url, headers=headers, timeout=config.TIMEOUT_JSON)
    except requests.RequestException as exc:
        msg = f"Erreur réseau lors de l'introspection du jeton : {exc}"
        log("test_acces", "api_entreprise", "erreur", msg, url=url)
        return {"ok": False, "scopes": [], "message": msg}

    if resp.status_code == 200:
        data = resp.json().get("data", {})
        scopes = data.get("scopes", [])
        ok = "actes_bilans_inpi" in scopes or any("liens_capitalistiques" in s for s in scopes) or len(scopes) > 0
        log("test_acces", "api_entreprise", "ok", f"scopes={scopes}", url=url, code_http=200)
        return {"ok": ok, "scopes": scopes, "message": "Jeton valide." if ok else "Jeton valide mais aucun scope détecté."}

    msg = f"Introspection échouée (HTTP {resp.status_code})."
    log("test_acces", "api_entreprise", "non_autorise", msg, url=url, code_http=resp.status_code)
    return {"ok": False, "scopes": [], "message": msg}


def get_liens_capitalistiques(siren: str, annee: str) -> dict | None:
    """
    Appelle GET /v3/dgfip/unites_legales/{siren}/liens_capitalistiques/{annee}.

    Retourne le JSON "data" en cas de succès, ou None si la donnée est absente
    (404 : formulaires 2059F/G non trouvés pour ce SIREN/exercice, ce qui ne
    signifie pas que l'entreprise n'a pas de liens, juste que ces deux CERFA
    sont introuvables pour cet exercice).

    Lève AccesNonAutorise si le token/habilitation ne permet pas l'appel
    (401/403) : dans ce cas, inutile de boucler sur d'autres années, il faut
    basculer vers l'option A (Data INPI).
    """
    if not jeton_configure():
        raise AccesNonAutorise(
            "API_ENTREPRISE_TOKEN et/ou API_ENTREPRISE_RECIPIENT absents du .env."
        )

    url = f"{config.API_ENTREPRISE_BASE_URL}/v3/dgfip/unites_legales/{siren}/liens_capitalistiques/{annee}"
    params = {
        "context": config.API_ENTREPRISE_CONTEXT,
        "object": config.API_ENTREPRISE_OBJECT,
        "recipient": config.API_ENTREPRISE_RECIPIENT,
    }
    headers = {"Authorization": f"Bearer {config.API_ENTREPRISE_TOKEN}"}

    for tentative in range(1, config.MAX_TENTATIVES + 1):
        try:
            resp = requests.get(
                url, params=params, headers=headers, timeout=config.TIMEOUT_JSON
            )
        except requests.RequestException as exc:
            log("liens_capitalistiques", "api_entreprise", "erreur",
                f"Tentative {tentative}/{config.MAX_TENTATIVES} : {exc}",
                siren=siren, annee=annee, url=url)
            time.sleep(config.PAUSE_ENTRE_APPELS * tentative)
            continue

        if resp.status_code == 200:
            log("liens_capitalistiques", "api_entreprise", "ok", "",
                siren=siren, annee=annee, url=url, code_http=200)
            return resp.json().get("data")

        if resp.status_code == 404:
            log("liens_capitalistiques", "api_entreprise", "introuvable",
                "2059F/2059G absents pour ce SIREN/exercice.",
                siren=siren, annee=annee, url=url, code_http=404)
            return None

        if resp.status_code in (401, 403):
            msg = (f"Accès refusé (HTTP {resp.status_code}). Le token ne donne "
                   f"pas accès à cette donnée, ou le paramètre recipient n'est "
                   f"pas un SIRET d'organisme public habilité.")
            log("liens_capitalistiques", "api_entreprise", "non_autorise", msg,
                siren=siren, annee=annee, url=url, code_http=resp.status_code)
            raise AccesNonAutorise(msg)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-after", 5))
            log("liens_capitalistiques", "api_entreprise", "indisponible",
                f"429 Trop de requêtes, attente {retry_after}s.",
                siren=siren, annee=annee, url=url, code_http=429)
            time.sleep(retry_after)
            continue

        log("liens_capitalistiques", "api_entreprise", "erreur",
            f"HTTP {resp.status_code} inattendu : {resp.text[:300]}",
            siren=siren, annee=annee, url=url, code_http=resp.status_code)
        time.sleep(config.PAUSE_ENTRE_APPELS * tentative)

    log("liens_capitalistiques", "api_entreprise", "erreur",
        "Échec après plusieurs tentatives.", siren=siren, annee=annee, url=url)
    return None
