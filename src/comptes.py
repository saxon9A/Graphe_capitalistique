"""
Extraction best-effort de quelques indicateurs (chiffre d'affaires, résultat net,
effectif) depuis le texte d'un compte annuel INPI déjà téléchargé par
niveau2_collecter.py (sortie/inpi_comptes/<siren>/texte.txt).

Utilisé seulement en repli (tier 2), quand l'API Recherche d'Entreprises (gratuite,
sans clé, cf. src/api_recherche_entreprises.py) n'a pas de champ `finances`
structuré pour la société. Un bilan est un document en texte libre : la mise en
page varie énormément d'un cabinet comptable à l'autre, donc cette extraction par
mots-clés n'est JAMAIS garantie. Chaque valeur trouvée est renvoyée avec la ligne
brute qui l'a produite, pour que tu puisses vérifier d'un coup d'œil avant de t'en
servir. Aucune valeur n'est inventée : un champ non trouvé reste None.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from . import config

MOTIF_NOMBRE = re.compile(r"-?\d{1,3}(?:[ .]\d{3})*(?:,\d+)?|-?\d+(?:,\d+)?")

# Lignes à ignorer même si elles contiennent le bon mot-clé : sous-totaux ou
# intitulés d'autres rubriques qui se ressemblent et fausseraient l'extraction.
MOTIFS_CA = [
    r"chiffres? d.affaires? nets?",
    r"chiffres? d.affaires?",
]
MOTIFS_RESULTAT = [
    r"resultat net\b",
    r"resultat de l.exercice\b",
    r"benefice ou perte\b",
]
MOTIFS_EFFECTIF = [
    r"effectif moyen",
    r"nombre moyen de salaries",
]


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)).lower()


def _plus_grand_nombre(ligne: str) -> float | None:
    """Le plus grand nombre (en valeur absolue) trouvé sur la ligne : dans un tableau de bilan,
    c'est presque toujours le montant total (les autres nombres sont des n° de ligne CERFA,
    des années, des renvois...). Convertit le format français (espace = séparateur de milliers,
    virgule = décimale) en float."""
    candidats = []
    for m in MOTIF_NOMBRE.finditer(ligne):
        brut = m.group(0)
        if re.fullmatch(r"-?(19|20)\d{2}", brut):   # ignore ce qui ressemble à une année
            continue
        nettoye = brut.replace(" ", "").replace(".", "").replace(",", ".")
        try:
            candidats.append(float(nettoye))
        except ValueError:
            continue
    return max(candidats, key=abs) if candidats else None


def _chercher(lignes: list[str], motifs: list[str]) -> tuple[float | None, str | None]:
    motifs_c = [re.compile(m) for m in motifs]
    for ligne in lignes:
        norm = _sans_accents(ligne)
        if any(m.search(norm) for m in motifs_c):
            valeur = _plus_grand_nombre(ligne)
            if valeur is not None:
                return valeur, ligne.strip()[:200]
    return None, None


def extraire_indicateurs(texte: str) -> dict:
    """Cherche CA, résultat net et effectif moyen dans le texte d'un bilan.
    Renvoie toujours les mêmes clés ; valeur/ligne source à None si rien trouvé."""
    lignes = [l for l in texte.split("\n") if l.strip() and not l.strip().startswith("=== page")]
    ca, ligne_ca = _chercher(lignes, MOTIFS_CA)
    resultat, ligne_resultat = _chercher(lignes, MOTIFS_RESULTAT)
    effectif, ligne_effectif = _chercher(lignes, MOTIFS_EFFECTIF)
    return {
        "chiffre_affaires_estime_bilan": ca, "bilan_ligne_source_ca": ligne_ca,
        "resultat_net_estime_bilan": resultat, "bilan_ligne_source_resultat": ligne_resultat,
        "effectif_estime_bilan": effectif, "bilan_ligne_source_effectif": ligne_effectif,
    }


def indicateurs_depuis_dossier(siren: str) -> dict | None:
    """Lit sortie/inpi_comptes/<siren>/texte.txt s'il existe déjà (téléchargé par
    niveau2_collecter.py, pour ce SIREN ou un autre niveau du projet) et en extrait les
    indicateurs. Renvoie None si aucun texte n'est disponible pour ce SIREN."""
    chemin = config.OUTPUT_DIR / "inpi_comptes" / siren / "texte.txt"
    if not chemin.exists():
        return None
    texte = chemin.read_text(encoding="utf-8")
    if len(texte.strip()) < 200:
        return None   # PDF scanné (image), pas de texte exploitable
    return extraire_indicateurs(texte)
