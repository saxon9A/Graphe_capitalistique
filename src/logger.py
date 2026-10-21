"""
Journalisation technique de l'extraction : un CSV listant chaque appel API,
les erreurs, les réponses indisponibles et les problèmes d'autorisation.

Ne jamais écrire de token/secret dans ce journal.
"""

import csv
import threading
from datetime import datetime, timezone

from . import config

_lock = threading.Lock()
_initialise = False

CHAMPS = [
    "horodatage",
    "etape",
    "source",
    "siren",
    "annee",
    "url",
    "code_http",
    "statut",
    "message",
]


def _init_fichier():
    global _initialise
    if _initialise:
        return
    with open(config.FICHIER_JOURNAL, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CHAMPS, delimiter=";")
        writer.writeheader()
    _initialise = True


def _masquer_secrets(url: str) -> str:
    """Retire tout paramètre ressemblant à un token/mot de passe d'une URL avant log."""
    if not url:
        return url
    import re

    url = re.sub(r"(token=)[^&]+", r"\1***", url, flags=re.IGNORECASE)
    url = re.sub(r"(authorization=)[^&]+", r"\1***", url, flags=re.IGNORECASE)
    return url


def log(etape: str, source: str, statut: str, message: str = "",
        siren: str = "", annee: str = "", url: str = "", code_http=""):
    """
    Ajoute une ligne au journal technique.

    - etape : ex. "recherche", "liens_capitalistiques", "enrichissement", "export"
    - source : ex. "api_entreprise", "data_inpi", "recherche_entreprises", "sirene"
    - statut : "ok", "erreur", "indisponible", "non_autorise", "introuvable", "info"
    """
    _init_fichier()
    ligne = {
        "horodatage": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "etape": etape,
        "source": source,
        "siren": siren,
        "annee": annee,
        "url": _masquer_secrets(url),
        "code_http": code_http,
        "statut": statut,
        "message": message,
    }
    with _lock:
        with open(config.FICHIER_JOURNAL, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CHAMPS, delimiter=";")
            writer.writerow(ligne)


def log_info(message: str, etape: str = "info"):
    log(etape=etape, source="programme", statut="info", message=message)
