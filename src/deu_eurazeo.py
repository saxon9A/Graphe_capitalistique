"""
Source spécifique à Eurazeo : son Document d'Enregistrement Universel (DEU),
dépôt réglementaire officiel auprès de l'AMF.

Document identifié (vérifié le 16/10/2026) :
    Eurazeo — Document d'Enregistrement Universel 2025, déposé le 27/03/2026
    sous le numéro D.26-0153
    https://www.eurazeo.com/sites/default/files/2026-03/Eurazeo_Document_Enregistrement_Universelle_2025_FRL_260226.pdf
    (~440 pages)

Ce module est spécifique à Eurazeo (URL, mise en page du PDF). Il sert à
fiabiliser le NIVEAU 1 (participations directes), pas à explorer
récursivement n'importe quelle société.

Deux tables ont été identifiées manuellement dans l'édition 2025 (en
inspectant le PDF réellement téléchargé, pas en devinant) :

1. Note 2 « Périmètre de consolidation » (comptes consolidés, autour de
   la page 275) : liste COURTE des quelques filiales réellement consolidées
   (Eurazeo étant une "entité d'investissement" au sens IFRS 10, la quasi-
   totalité de son portefeuille n'est PAS consolidée globalement, juste
   valorisée en juste valeur -- donc cette note ne reflète PAS l'ensemble des
   participations au sens large). Donne : dénomination, pays, méthode, %
   de contrôle, % d'intérêt. Pas de SIREN/SIRET.

2. Note 17 « Tableau des filiales et participations » (annexe aux
   comptes individuels, à partir de la page ~346) : C'EST LA BONNE TABLE,
   l'équivalent exact de ce que donnerait le CERFA 2059G (même obligation
   légale, Art. R.123-197 du Code de commerce). Elle liste séparément :
     - les FILIALES (+50 % du capital détenu),
     - les PARTICIPATIONS (10 % à 50 % du capital détenu),
   avec pour chacune : dénomination, adresse, SIRET (quand française),
   capitaux propres, % de détention, valeur des titres, CA, résultat,
   dividendes encaissés. C'est la table utilisée par
   extraire_filiales_et_participations() ci-dessous.

La position de cette table peut changer d'une édition à l'autre du DEU :
le code localise donc la page de départ en cherchant le texte exact
« Tableau des filiales et participations » plutôt que de supposer un numéro
de page fixe, et lit les pages suivantes jusqu'à rencontrer la note
suivante (« Note 18 ») ou une limite de sécurité.
"""

import re
import time
import unicodedata
from pathlib import Path

import requests

from . import config
from .logger import log, log_info

DEU_URL = (
    "https://www.eurazeo.com/sites/default/files/2026-03/"
    "Eurazeo_Document_Enregistrement_Universelle_2025_FRL_260226.pdf"
)
DEU_ANNEE = "2025"

_FICHIER_PDF = config.OUTPUT_DIR / "deu_eurazeo_2025.pdf"

TITRE_TABLE = "renseignements concernant les filiales"
TITRE_NOTE_SUIVANTE = "note 18"
MAX_PAGES_TABLE = 10  # garde-fou si la table s'étale de façon inattendue

LIGNES_A_IGNORER = [
    "états financiers",
    "comptes individuels",
    "document d'enregistrement universel",
    "quote-",
    "part net des",
    "de valeur comptable prêts et des d'affai",
    "capi- taux déte-",
    "capital des titres détenus avances engage",
    "taxes du dernier cours de",
    "(en milliers d'euros) propres nue par la",
    "31 décembre",
    "renseignements globaux",
    "renseignements détaillés",
]

RE_LIGNE_DONNEES = re.compile(r"\d{2}/\d{2}/\d{4}\s*$")
RE_SIRET = re.compile(r"Siret\s*:\s*(\d{3}[\s ]?\d{3}[\s ]?\d{3}[\s ]?\d{5})")
RE_POURCENTAGE = re.compile(r"\b(\d{1,3},\d{1,2})\b")
RE_ID_ETRANGER = re.compile(r"ID\s*Number\s*:\s*([A-Za-z0-9]+)")
# "L 2449 Luxembourg 6 771 100,0 ..." -> ville = "L 2449 Luxembourg" (tout ce qui
# precede le premier montant suivi d'un pourcentage).
RE_VILLE_DEBUT_LIGNE = re.compile(
    r"^(?P<ville>.+?)\s+\d{1,3}(?:\s\d{3})*\s+\d{1,3},\d{1,2}\s"
)

# Pays deduits UNIQUEMENT de mots explicitement presents dans l'adresse du DEU.
# Pas de devinette au-dela : sinon None (le dashboard affichera "Étranger").
_PAYS_PAR_MOT_CLE = {
    "luxembourg": "Luxembourg",
    "london": "Royaume-Uni",
    "londres": "Royaume-Uni",
    "united kingdom": "Royaume-Uni",
}


def deviner_pays(adresse: str):
    a = _sans_accents(adresse or "")
    for mot, pays in _PAYS_PAR_MOT_CLE.items():
        if mot in a:
            return pays
    return None


def _sans_accents(texte: str) -> str:
    texte = texte.replace("’", "'").replace("‘", "'")
    return "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    ).lower()


# Les motifs ci-dessus contiennent des accents (pour rester lisibles dans le
# code) : on les passe eux aussi par _sans_accents une seule fois au chargement
# du module, sinon "motif in l" ne matche jamais rien (l est deja sans accents).
_LIGNES_A_IGNORER_NORM = [_sans_accents(m) for m in LIGNES_A_IGNORER]


def _est_ligne_a_ignorer(ligne: str) -> bool:
    l = _sans_accents(ligne.strip())
    if not l or l.isdigit():
        return True
    return any(motif in l for motif in _LIGNES_A_IGNORER_NORM)


def telecharger_deu(forcer: bool = False) -> "Path | None":
    if _FICHIER_PDF.exists() and not forcer:
        log_info(f"DEU Eurazeo déjà téléchargé : {_FICHIER_PDF.name}")
        return _FICHIER_PDF

    log_info("Téléchargement du DEU Eurazeo 2025 (~440 pages, peut prendre une minute)...")
    try:
        resp = requests.get(DEU_URL, timeout=60, stream=True)
    except requests.RequestException as exc:
        log("telechargement_deu", "eurazeo_deu", "erreur", f"Erreur réseau : {exc}", url=DEU_URL)
        return None

    if resp.status_code != 200:
        log("telechargement_deu", "eurazeo_deu", "erreur",
            f"HTTP {resp.status_code}.", url=DEU_URL, code_http=resp.status_code)
        return None

    config.OUTPUT_DIR.mkdir(exist_ok=True)
    with open(_FICHIER_PDF, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            f.write(chunk)

    log("telechargement_deu", "eurazeo_deu", "ok",
        f"{_FICHIER_PDF.stat().st_size // 1024} Ko.", url=DEU_URL, code_http=200)
    return _FICHIER_PDF


def _localiser_page_depart(pdf):
    for i, page in enumerate(pdf.pages):
        texte = _sans_accents(page.extract_text() or "")
        if TITRE_TABLE in texte:
            return i
    return None


def extraire_filiales_et_participations() -> list:
    try:
        import pdfplumber
    except ImportError:
        log("extraction_deu", "eurazeo_deu", "erreur", "pdfplumber non installé.")
        return []

    chemin = telecharger_deu()
    if not chemin:
        return []

    candidats_trouves = []
    section_courante = "filiale"

    with pdfplumber.open(chemin) as pdf:
        page_depart = _localiser_page_depart(pdf)
        if page_depart is None:
            log("extraction_deu", "eurazeo_deu", "introuvable",
                f"Texte '{TITRE_TABLE}' introuvable dans le document.")
            return []

        log_info(f"« Tableau des filiales et participations » localisé page {page_depart + 1}.")

        lignes_completes = []
        for offset in range(MAX_PAGES_TABLE):
            idx = page_depart + offset
            if idx >= len(pdf.pages):
                break
            texte_page = pdf.pages[idx].extract_text() or ""
            if offset > 0 and TITRE_NOTE_SUIVANTE in _sans_accents(texte_page):
                break
            for ligne in texte_page.split("\n"):
                if not _est_ligne_a_ignorer(ligne):
                    lignes_completes.append((ligne.strip(), idx + 1))

        lignes_en_attente = []  # lignes de nom/adresse accumulees depuis la derniere ligne de donnees
        for ligne, page_humaine in lignes_completes:
            l_norm = _sans_accents(ligne)
            if "renseignements concernant les filiales" in l_norm:
                section_courante = "filiale"
                lignes_en_attente = []
                continue
            if "renseignements concernant les participations" in l_norm:
                section_courante = "participation"
                lignes_en_attente = []
                continue

            if not RE_LIGNE_DONNEES.search(ligne):
                lignes_en_attente.append(ligne)
                continue

            if not lignes_en_attente:
                continue
            bloc = lignes_en_attente
            nom_candidat = bloc[0]
            lignes_en_attente = []
            if re.match(r"^(A\.|B\.|C\.|Total|2-|1-)", nom_candidat, re.IGNORECASE):
                continue

            siret_match = RE_SIRET.search(ligne)
            siren_candidat = None
            siret_candidat = None
            zone_recherche_pct = ligne
            if siret_match:
                siret_brut = re.sub(r"\s", "", siret_match.group(1))
                if len(siret_brut) >= 9:
                    siren_candidat = siret_brut[:9]
                    siret_candidat = siret_brut
                zone_recherche_pct = ligne[siret_match.end():]

            # Adresse telle qu'imprimee dans le DEU : lignes entre le nom et la
            # ligne de donnees, + (societes etrangeres) la ville qui commence
            # la ligne de donnees, ex. "L 2449 Luxembourg 6 771 100,0 ...".
            adresse_lignes = list(bloc[1:])
            identifiant_etranger = None
            id_match = RE_ID_ETRANGER.search(ligne)
            if id_match:
                identifiant_etranger = id_match.group(1)
                zone_recherche_pct = ligne[id_match.end():]
            elif not siret_match:
                ville_match = RE_VILLE_DEBUT_LIGNE.match(ligne)
                if ville_match:
                    adresse_lignes.append(ville_match.group("ville").strip())

            pct_match = RE_POURCENTAGE.search(zone_recherche_pct)
            if not pct_match:
                continue
            pourcentage = float(pct_match.group(1).replace(",", "."))

            adresse_txt = ", ".join(a for a in adresse_lignes if a)
            candidats_trouves.append({
                "nom_candidat": nom_candidat,
                "siren_candidat": siren_candidat,
                "siret_candidat": siret_candidat,
                "pourcentage_candidat": pourcentage,
                "type_candidat": section_courante,
                "page_source": page_humaine,
                "adresse_deu": adresse_txt,
                "identifiant_etranger": identifiant_etranger,
                "pays_deu": "France" if siret_match else deviner_pays(adresse_txt),
            })

    log_info(f"{len(candidats_trouves)} candidat(s) extrait(s) de la Note 17 "
              f"(dont {sum(1 for c in candidats_trouves if c['siren_candidat'])} avec SIREN identifié via le SIRET).")
    return candidats_trouves
