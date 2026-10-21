"""
API INPI « actes » — documents légaux déposés au Registre National des
Entreprises (statuts, PV d'assemblée, actes de cession, etc.).

Documentation technique officielle (INPI, "documentation technique API Actes") :
    POST /api/sso/login                         -> {"token": ...}   (même compte que api_inpi.py)
    GET  /api/companies/{siren}/attachments      -> liste des pièces jointes d'une entreprise
    GET  /api/actes?siren[]={siren}              -> liste des actes (filtrable par dateFrom)
    GET  /api/actes/{id}                         -> métadonnées d'un acte
    GET  /api/actes/{id}/download                -> téléchargement du PDF de l'acte

⚠️ Fiabilité : contrairement au CERFA 2059G (option B) qui est un formulaire
structuré "liste de filiales + % de détention", un acte est un document
juridique en texte libre (statuts, procès-verbal...). Il PEUT mentionner des
participations/filiales, mais ce n'est jamais garanti, et une extraction
automatique par mots-clés ne remplace pas une lecture humaine.

Ce module :
  1. liste les actes disponibles pour un SIREN ;
  2. télécharge les PDF des actes qui ont le plus de chances d'être utiles
     (statuts, actes de cession/nomination, ordonnés du plus récent) ;
  3. scanne leur texte à la recherche de phrases mentionnant un pourcentage
     de détention à proximité d'une dénomination sociale, et les ressort
     comme CANDIDATS à vérifier manuellement — jamais comme des relations
     certaines injectées directement dans participations.csv.

Résultat : sortie/inpi_actes/<siren>/*.pdf (documents bruts) +
sortie/inpi_actes/<siren>/candidats.csv (mentions candidates à valider).
"""

import csv
import re
import time
import unicodedata

import requests

from . import config
from .logger import log, log_info

_token_cache = {"token": None}
_AVERTISSEMENT_403_AFFICHE = {"fait": False}

MOTIF_POURCENTAGE = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*%")

# Mots-clés indiquant qu'une phrase pourrait décrire une participation/filiale
MOTS_CLES_PARTICIPATION = [
    "detient", "detenu", "participation", "filiale", "capital de",
    "parts sociales", "actions de la societe", "souscription au capital",
]


def _sans_accents(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    ).lower()


def _login() -> str | None:
    if _token_cache["token"]:
        return _token_cache["token"]
    if not (config.INPI_USERNAME and config.INPI_PASSWORD):
        log("login", "data_inpi_actes", "non_autorise", "INPI_USERNAME/PASSWORD absents.")
        return None
    url = f"{config.INPI_BASE_URL}/api/sso/login"
    try:
        resp = requests.post(url, json={"username": config.INPI_USERNAME,
                                         "password": config.INPI_PASSWORD}, timeout=config.TIMEOUT_JSON)
    except requests.RequestException as exc:
        log("login", "data_inpi_actes", "erreur", f"Erreur réseau : {exc}", url=url)
        return None
    if resp.status_code != 200:
        log("login", "data_inpi_actes", "non_autorise",
            f"Échec (HTTP {resp.status_code}).", url=url, code_http=resp.status_code)
        return None
    token = resp.json().get("token")
    _token_cache["token"] = token
    return token


def lister_actes(siren: str) -> list[dict]:
    """GET /api/actes?siren[]={siren} -> liste brute des actes (metadata), triée récent -> ancien si possible."""
    token = _login()
    if not token:
        return []
    url = f"{config.INPI_BASE_URL}/api/actes"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, params={"siren[]": siren}, headers=headers, timeout=config.TIMEOUT_DEFAUT)
    except requests.RequestException as exc:
        log("liste_actes", "data_inpi_actes", "erreur", f"Erreur réseau : {exc}", siren=siren, url=url)
        return []

    if resp.status_code == 404:
        log("liste_actes", "data_inpi_actes", "introuvable", "Aucun acte trouvé.", siren=siren, url=url, code_http=404)
        return []
    if resp.status_code == 403:
        # Confirmé le 16/10/2026 : ce compte Data INPI a accès à /api/companies
        # mais PAS à /api/actes (droit d'accès séparé, pas accordé par défaut
        # à la création d'un compte gratuit). Ce n'est pas un bug du programme :
        # on le signale une fois clairement puis on continue sans cette source.
        if not _AVERTISSEMENT_403_AFFICHE["fait"]:
            print("⚠️  API « actes » INPI : HTTP 403 (accès refusé). Ton compte Data INPI "
                  "n'a pas les droits sur /api/actes (seulement /api/companies). Ce n'est "
                  "pas un bug : c'est une habilitation séparée, pas accordée par défaut. "
                  "Le programme continue sans cette source (voir le DEU Eurazeo pour le "
                  "niveau 1, c'est une source plus fiable de toute façon).")
            _AVERTISSEMENT_403_AFFICHE["fait"] = True
        log("liste_actes", "data_inpi_actes", "non_autorise",
            "HTTP 403 : ce compte INPI n'a pas les droits sur /api/actes.",
            siren=siren, url=url, code_http=403)
        return []
    if resp.status_code != 200:
        log("liste_actes", "data_inpi_actes", "erreur",
            f"HTTP {resp.status_code} : {resp.text[:300]}", siren=siren, url=url, code_http=resp.status_code)
        return []

    data = resp.json()
    actes = data.get("actes") or data.get("data") or (data if isinstance(data, list) else [])
    log("liste_actes", "data_inpi_actes", "ok", f"{len(actes)} acte(s) trouvé(s).",
        siren=siren, url=url, code_http=200)
    return actes


def telecharger_acte(acte_id: str, siren: str) -> "Path | None":
    from pathlib import Path
    token = _login()
    if not token:
        return None
    dossier = config.OUTPUT_DIR / "inpi_actes" / siren
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{acte_id}.pdf"
    if chemin.exists():
        return chemin

    url = f"{config.INPI_BASE_URL}/api/actes/{acte_id}/download"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=config.TIMEOUT_DEFAUT, stream=True)
    except requests.RequestException as exc:
        log("telechargement_acte", "data_inpi_actes", "erreur", f"Erreur réseau : {exc}",
            siren=siren, url=url)
        return None

    if resp.status_code != 200:
        log("telechargement_acte", "data_inpi_actes", "erreur",
            f"HTTP {resp.status_code}", siren=siren, url=url, code_http=resp.status_code)
        return None

    with open(chemin, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 128):
            f.write(chunk)
    log("telechargement_acte", "data_inpi_actes", "ok", "", siren=siren, url=url, code_http=200)
    return chemin


def scanner_candidats_participations(chemin_pdf, siren: str, nom_acte: str = "") -> list[dict]:
    """
    Extrait le texte du PDF (pdfplumber) et cherche des phrases contenant à
    la fois un pourcentage et un mot-clé de participation. Retourne une
    liste de candidats {"siren_source", "nom_acte", "phrase", "pourcentage_detecte"}
    — PAS des relations fiables, juste des indices à vérifier à la main.
    """
    try:
        import pdfplumber
    except ImportError:
        log("scan_acte", "data_inpi_actes", "erreur", "pdfplumber non installé.")
        return []

    candidats = []
    try:
        with pdfplumber.open(chemin_pdf) as pdf:
            texte_complet = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as exc:
        log("scan_acte", "data_inpi_actes", "erreur", f"Lecture PDF échouée : {exc}", siren=siren)
        return []

    for phrase in re.split(r"(?<=[.;\n])\s+", texte_complet):
        phrase_norm = _sans_accents(phrase)
        if not any(mc in phrase_norm for mc in MOTS_CLES_PARTICIPATION):
            continue
        m = MOTIF_POURCENTAGE.search(phrase)
        if not m:
            continue
        candidats.append({
            "siren_source": siren,
            "nom_acte": nom_acte,
            "pourcentage_detecte": m.group(1),
            "phrase": phrase.strip()[:400],
        })

    return candidats


def explorer_actes_pour_siren(siren: str, max_actes: int = 5) -> list[dict]:
    """
    Pipeline complet pour un SIREN : liste les actes, télécharge les
    `max_actes` plus récents, scanne chacun, et écrit tous les candidats
    dans sortie/inpi_actes/<siren>/candidats.csv.

    Retourne la liste des candidats (à valider manuellement — cette fonction
    ne retourne JAMAIS de relations "certaines").
    """
    actes = lister_actes(siren)
    if not actes:
        return []

    tous_candidats = []
    for acte in actes[:max_actes]:
        acte_id = acte.get("id") or acte.get("idActe")
        if not acte_id:
            continue
        nom_acte = acte.get("type") or acte.get("typeActe") or str(acte_id)
        chemin = telecharger_acte(str(acte_id), siren)
        if not chemin:
            continue
        candidats = scanner_candidats_participations(chemin, siren, nom_acte)
        tous_candidats.extend(candidats)
        time.sleep(config.PAUSE_ENTRE_APPELS)

    if tous_candidats:
        dossier = config.OUTPUT_DIR / "inpi_actes" / siren
        dossier.mkdir(parents=True, exist_ok=True)
        chemin_csv = dossier / "candidats.csv"
        with open(chemin_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["siren_source", "nom_acte", "pourcentage_detecte", "phrase"],
                                     delimiter=";")
            writer.writeheader()
            writer.writerows(tous_candidats)
        log_info(f"{len(tous_candidats)} mention(s) candidate(s) pour {siren} -> {chemin_csv} (À VÉRIFIER).")

    return tous_candidats
