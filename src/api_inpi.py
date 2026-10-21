"""
Option A — Data INPI / Registre National des Entreprises (RNE).

Deux usages possibles, tous deux nécessitant un compte GRATUIT créé sur
https://data.inpi.fr (bouton "Se connecter" en haut à droite -> "Créer un
compte") :

1. Authentification : POST /api/sso/login  {username, password} -> {"token": ...}
   (confirmé par la documentation technique officielle de l'INPI, "API Actes").

2. Fiche entreprise : GET /api/companies/{siren}  (Authorization: Bearer <token>)
   Renvoie la donnée d'immatriculation déclarée au RNE : identité, personnes
   (dirigeants, associés/personnes ayant le pouvoir), et pour certaines
   entreprises les bénéficiaires effectifs avec leur pourcentage de détention
   ou de droits de vote.

⚠️ Contrairement à l'API Entreprise (liens_capitalistiques), le RNE n'est PAS
structuré comme un graphe "filiales détenues" déclaré par l'entreprise elle
-même (CERFA 2059G) : il expose surtout qui DÉTIENT l'entreprise interrogée
(ses associés / bénéficiaires effectifs), pas la liste de ses propres
participations dans d'autres sociétés. Pour une société holding comme
Eurazeo, l'information "dans quelles sociétés Eurazeo a une participation"
n'est donc pas garantie d'être présente dans ce endpoint sous une forme
directement exploitable : il faut l'examiner avant de construire le reste
du pipeline dessus (voir étape 2 de la méthode de développement).

Ce module :
  - gère le login et la mise en cache du token en mémoire (il expire, on
    relance un login si besoin) ;
  - expose get_company(siren) qui renvoie le JSON brut ;
  - sauvegarde systématiquement le JSON brut dans sortie/inpi_brut/<siren>.json
    pour que tu puisses inspecter la vraie structure de réponse avant de
    faire confiance à l'extraction automatique ;
  - tente une extraction "best effort" des personnes/bénéficiaires effectifs
    avec leurs pourcentages quand les champs attendus sont présents, en
    journalisant clairement quand ce n'est pas le cas plutôt que d'inventer
    des valeurs.
"""

import json
import time

import requests

from . import config
from .logger import log

_token_cache = {"token": None}

_RAW_DIR = config.OUTPUT_DIR / "inpi_brut"


def identifiants_configures() -> bool:
    return bool(config.INPI_USERNAME and config.INPI_PASSWORD)


def _login() -> str | None:
    if _token_cache["token"]:
        return _token_cache["token"]

    if not identifiants_configures():
        log("login", "data_inpi", "non_autorise",
            "INPI_USERNAME / INPI_PASSWORD absents du .env.")
        return None

    url = f"{config.INPI_BASE_URL}/api/sso/login"
    try:
        resp = requests.post(
            url,
            json={"username": config.INPI_USERNAME, "password": config.INPI_PASSWORD},
            timeout=config.TIMEOUT_JSON,
        )
    except requests.RequestException as exc:
        log("login", "data_inpi", "erreur", f"Erreur réseau : {exc}", url=url)
        return None

    if resp.status_code != 200:
        log("login", "data_inpi", "non_autorise",
            f"Échec de connexion (HTTP {resp.status_code}). Vérifie "
            f"INPI_USERNAME/INPI_PASSWORD dans .env.",
            url=url, code_http=resp.status_code)
        return None

    token = resp.json().get("token")
    if not token:
        log("login", "data_inpi", "erreur", "Réponse 200 mais aucun champ 'token'.", url=url)
        return None

    _token_cache["token"] = token
    log("login", "data_inpi", "ok", "Connexion réussie.", url=url, code_http=200)
    return token


def get_company(siren: str) -> dict | None:
    """
    Récupère la fiche RNE brute d'une entreprise par SIREN.
    Sauvegarde toujours la réponse brute dans sortie/inpi_brut/<siren>.json
    pour inspection manuelle.
    """
    token = _login()
    if not token:
        return None

    url = f"{config.INPI_BASE_URL}/api/companies/{siren}"
    headers = {"Authorization": f"Bearer {token}"}

    for tentative in range(1, config.MAX_TENTATIVES + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=config.TIMEOUT_DEFAUT)
        except requests.RequestException as exc:
            log("fiche_entreprise", "data_inpi", "erreur",
                f"Tentative {tentative}/{config.MAX_TENTATIVES} : {exc}",
                siren=siren, url=url)
            time.sleep(config.PAUSE_ENTRE_APPELS * tentative)
            continue

        if resp.status_code == 200:
            data = resp.json()
            _sauvegarder_brut(siren, data)
            log("fiche_entreprise", "data_inpi", "ok", "", siren=siren, url=url, code_http=200)
            return data

        if resp.status_code == 404:
            log("fiche_entreprise", "data_inpi", "introuvable",
                "SIREN non trouvé au RNE.", siren=siren, url=url, code_http=404)
            return None

        if resp.status_code == 401:
            # Token probablement expiré : on force un nouveau login et on retente une fois.
            _token_cache["token"] = None
            token = _login()
            if not token:
                return None
            headers = {"Authorization": f"Bearer {token}"}
            continue

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            log("fiche_entreprise", "data_inpi", "indisponible",
                f"429, attente {retry_after}s.", siren=siren, url=url, code_http=429)
            time.sleep(retry_after)
            continue

        log("fiche_entreprise", "data_inpi", "erreur",
            f"HTTP {resp.status_code} : {resp.text[:300]}",
            siren=siren, url=url, code_http=resp.status_code)
        time.sleep(config.PAUSE_ENTRE_APPELS * tentative)

    return None


def _sauvegarder_brut(siren: str, data: dict):
    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    chemin = _RAW_DIR / f"{siren}.json"
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extraire_participations_best_effort(siren: str, data: dict) -> list[dict]:
    """
    Tente d'extraire une liste de relations capitalistiques à partir de la
    fiche RNE brute. Les noms de champs du RNE varient selon le type
    d'entreprise et l'évolution du format ; cette fonction essaie plusieurs
    chemins connus et renvoie une liste VIDE (sans rien inventer) si aucun
    n'est trouvé, en journalisant le fait pour que tu ailles vérifier le JSON
    brut sauvegardé dans sortie/inpi_brut/<siren>.json.

    Chaque relation retournée a la forme :
        {
            "siren_detentrice": ..., "nom_detentrice": ...,
            "siren_detenue": ..., "nom_detenue": ...,
            "pourcentage_detention": ... (ou None),
            "type_relation": "beneficiaire_effectif" | "personne_morale_associee",
            "annee_declaration": ... (ou None),
        }
    """
    relations = []
    try:
        formality = data.get("formality", {})
        content = formality.get("content", {})

        # Bénéficiaires effectifs (personnes physiques ou morales détenant
        # l'entreprise interrogée) : structure usuelle "beneficiairesEffectifs".
        beneficiaires = content.get("beneficiairesEffectifs") \
            or content.get("personnePhysique", {}).get("beneficiairesEffectifs") \
            or []
        for b in beneficiaires:
            identite = b.get("beneficiaire", {}).get("descriptionPersonne", {}) \
                or b.get("descriptionPersonne", {}) or {}
            detention = b.get("detentionDirecteIndirecte", {}) or b.get("detention", {}) or {}
            relations.append({
                "siren_detentrice": identite.get("siren") or identite.get("numeroIdentification"),
                "nom_detentrice": identite.get("denomination")
                    or " ".join(filter(None, [identite.get("nom"), identite.get("prenoms")])),
                "siren_detenue": siren,
                "nom_detenue": None,
                "pourcentage_detention": detention.get("pourcentageParts")
                    or detention.get("pourcentageVote"),
                "type_relation": "beneficiaire_effectif",
                "annee_declaration": None,
            })

        if not relations:
            log("extraction_inpi", "data_inpi", "info",
                "Aucun champ de bénéficiaires effectifs reconnu dans la "
                "structure attendue : vérifie sortie/inpi_brut/"
                f"{siren}.json pour adapter extraire_participations_best_effort().",
                siren=siren)
    except Exception as exc:  # on ne veut jamais planter le pipeline ici
        log("extraction_inpi", "data_inpi", "erreur",
            f"Erreur lors de l'extraction best-effort : {exc}", siren=siren)

    return relations
