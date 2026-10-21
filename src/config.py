"""
Configuration centrale du projet.

Toutes les clés/tokens viennent de variables d'environnement (fichier .env),
jamais codées en dur. Voir .env.example pour la liste des variables.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Charge le fichier .env situé à la racine du projet (s'il existe)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --- Dossiers ---
OUTPUT_DIR = BASE_DIR / "sortie"
OUTPUT_DIR.mkdir(exist_ok=True)

# --- Entreprise de départ ---
SIREN_DEPART = os.getenv("SIREN_DEPART", "692030992").strip()

# --- Option B : API Entreprise (DGFIP - liens capitalistiques) ---
API_ENTREPRISE_BASE_URL = "https://entreprise.api.gouv.fr"
API_ENTREPRISE_TOKEN = os.getenv("API_ENTREPRISE_TOKEN", "").strip()
API_ENTREPRISE_CONTEXT = os.getenv("API_ENTREPRISE_CONTEXT", "Cartographie capitalistique")
API_ENTREPRISE_OBJECT = os.getenv("API_ENTREPRISE_OBJECT", "Analyse des participations")
API_ENTREPRISE_RECIPIENT = os.getenv("API_ENTREPRISE_RECIPIENT", "").strip()

# Années fiscales à tester pour les liens capitalistiques (la plus récente d'abord).
# L'API accepte les exercices de 2006 à l'année précédente.
_annees_brut = os.getenv("ANNEES_A_TESTER", "2024,2023,2022,2021,2020")
ANNEES_A_TESTER = [a.strip() for a in _annees_brut.split(",") if a.strip()]

# --- Option A : Data INPI / Registre National des Entreprises (RNE) ---
INPI_BASE_URL = "https://registre-national-entreprises.inpi.fr"
INPI_USERNAME = os.getenv("INPI_USERNAME", "").strip()
INPI_PASSWORD = os.getenv("INPI_PASSWORD", "").strip()

# --- Enrichissement : API Recherche d'Entreprises (aucune clé nécessaire) ---
RECHERCHE_ENTREPRISES_BASE_URL = "https://recherche-entreprises.api.gouv.fr"

# --- Enrichissement optionnel : API Sirene INSEE ---
INSEE_API_KEY = os.getenv("INSEE_API_KEY", "").strip()
INSEE_SIRENE_BASE_URL = "https://api.insee.fr/api-sirene/3.11"

# --- Exploration récursive ---
PROFONDEUR_MAX = int(os.getenv("PROFONDEUR_MAX", "5"))

# SIREN d'Eurazeo : sert à déclencher automatiquement l'amorçage par le DEU
# (src/deu_eurazeo.py), qui est spécifique à cette société.
SIREN_EURAZEO = "692030992"
UTILISER_DEU_EURAZEO = os.getenv("UTILISER_DEU_EURAZEO", "true").lower() in ("1", "true", "oui", "yes")

# Nombre max d'actes récents à télécharger/scanner par société lors de la
# recherche de candidats via l'API actes INPI (src/api_inpi_actes.py).
MAX_ACTES_PAR_SOCIETE = int(os.getenv("MAX_ACTES_PAR_SOCIETE", "5"))

# --- Réseau ---
TIMEOUT_JSON = 10  # secondes, recommandation API Entreprise pour les endpoints JSON
TIMEOUT_DEFAUT = 15
MAX_TENTATIVES = 3
PAUSE_ENTRE_APPELS = 0.3  # secondes, pour rester sous les limites de débit

# --- Fichiers de sortie ---
FICHIER_ENTREPRISES_ACTIVES = OUTPUT_DIR / "entreprises_actives.csv"
FICHIER_PARTICIPATIONS = OUTPUT_DIR / "participations.csv"
FICHIER_ENTREPRISES_INACTIVES = OUTPUT_DIR / "entreprises_inactives.csv"
# Nom "2" volontaire : sur cette machine, le fichier "journal_extraction.csv"
# original s'est retrouve verrouille en ecriture au niveau de Windows
# (OneDrive/antivirus, probablement), au point d'empecher meme sa suppression
# ou son renommage depuis le pont. Plutot que de rester bloque dessus, on
# ecrit le journal sous un nouveau nom qui n'a jamais ete touche. Si
# "journal_extraction2.csv" se bloque un jour aussi, renomme-le ici en
# "journal_extraction3.csv" (ou mieux : redemarre Windows, ca libere ce
# genre de verrou de fichier).
FICHIER_JOURNAL = OUTPUT_DIR / "journal_extraction2.csv"
