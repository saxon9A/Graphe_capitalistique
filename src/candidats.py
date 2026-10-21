"""
Fusionne les "candidats" de participation issus des différentes sources non
structurées (DEU Eurazeo, actes INPI) en un seul fichier à relire et valider
manuellement : sortie/candidats_a_verifier.csv.

Rien ici n'est injecté automatiquement dans participations.csv : voir
valider.py pour le processus de validation manuelle qui fait passer un
candidat de ce fichier vers le graphe officiel.
"""

import csv

from . import config
from .logger import log_info

CHAMPS = [
    "source", "siren_societe_source", "nom_societe_source",
    "nom_candidat_detenue", "pourcentage_candidat",
    "preuve", "siren_confirme", "valide",
]

FICHIER_CANDIDATS = config.OUTPUT_DIR / "candidats_a_verifier.csv"


def _lire_existants() -> list[dict]:
    if not FICHIER_CANDIDATS.exists():
        return []
    with open(FICHIER_CANDIDATS, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def ajouter_candidats_deu(candidats_deu: list[dict], siren_eurazeo: str, nom_eurazeo: str = "EURAZEO"):
    lignes = []
    for c in candidats_deu:
        siren_candidat = c.get("siren_candidat") or ""
        preuve = (
            f"DEU Eurazeo 2025, p.{c['page_source']} ({c['type_candidat']}) : "
            f"{c['nom_candidat']} - {c['pourcentage_candidat']} %"
            + (f" - SIREN (via SIRET) {siren_candidat}" if siren_candidat else " - pas de SIRET (societe etrangere)")
        )
        lignes.append({
            "source": f"deu_eurazeo_2025_{c['type_candidat']}",
            "siren_societe_source": siren_eurazeo,
            "nom_societe_source": nom_eurazeo,
            "nom_candidat_detenue": c["nom_candidat"],
            "pourcentage_candidat": c["pourcentage_candidat"],
            "preuve": preuve,
            # Quand le SIRET a pu etre lu dans le DEU, on pre-remplit siren_confirme :
            # c'est une donnee auditee (CERFA 2059G / Art. R.123-197), donc fiable,
            # mais ca reste un candidat (pas injecte direct dans participations.csv)
            # tant que la colonne 'valide' n'est pas passee a 'oui'.
            "siren_confirme": siren_candidat,
            "valide": "",
        })
    # Le DEU est une source deterministe (meme PDF -> memes lignes a chaque
    # run) : on remplace les anciennes lignes "deu_eurazeo_2025*" plutot que
    # de les accumuler, sinon une ancienne extraction buguee (ou une colonne
    # 'valide'/'siren_confirme' remplie a la main) resterait polluee pour
    # toujours a cote de la nouvelle. On ne touche a rien d'autre (actes INPI,
    # lignes deja validees manuellement avec une autre source).
    _remplacer_source(prefixe_source="deu_eurazeo_2025", nouvelles_lignes=lignes)


def _remplacer_source(prefixe_source: str, nouvelles_lignes: list[dict]):
    """Retire du fichier toute ligne dont `source` commence par `prefixe_source`
    et la remplace par `nouvelles_lignes` (sans toucher aux autres sources).

    Si une ancienne ligne avait la MEME 'preuve' qu'une nouvelle (donc le meme
    candidat, meme page, meme %), on reporte sur la nouvelle ligne tout travail
    de validation manuelle deja fait a la main (colonne 'valide', et un
    'siren_confirme' saisi a la main si l'extraction n'en avait pas trouve) :
    relancer graphe.py ne doit jamais effacer une validation deja faite.
    """
    existants = _lire_existants()
    anciennes_memes_source = {l["preuve"]: l for l in existants if l["source"].startswith(prefixe_source)}
    conserves = [l for l in existants if not l["source"].startswith(prefixe_source)]

    for ligne in nouvelles_lignes:
        ancienne = anciennes_memes_source.get(ligne["preuve"])
        if not ancienne:
            continue
        if ancienne.get("valide"):
            ligne["valide"] = ancienne["valide"]
        if ancienne.get("siren_confirme") and not ligne.get("siren_confirme"):
            ligne["siren_confirme"] = ancienne["siren_confirme"]

    retirees = len(existants) - len(conserves)
    if retirees:
        log_info(f"{retirees} ancienne(s) ligne(s) '{prefixe_source}*' remplacee(s) "
                  f"par une nouvelle extraction dans {FICHIER_CANDIDATS.name} "
                  f"(validations manuelles deja faites conservees).")
    _ecrire(conserves, nouvelles_lignes)


def ajouter_candidats_actes(candidats_actes: list[dict], nom_societe_source: str = ""):
    lignes = []
    for c in candidats_actes:
        lignes.append({
            "source": "actes_inpi",
            "siren_societe_source": c["siren_source"],
            "nom_societe_source": nom_societe_source,
            "nom_candidat_detenue": "",  # non isolé automatiquement : voir la colonne 'preuve'
            "pourcentage_candidat": c["pourcentage_detecte"],
            "preuve": f"acte {c['nom_acte']} : {c['phrase']}",
            "siren_confirme": "",
            "valide": "",
        })
    _ajouter(lignes)


def _ajouter(nouvelles_lignes: list[dict]):
    if not nouvelles_lignes:
        return
    existants = _lire_existants()
    _ecrire(existants, nouvelles_lignes)


def _ecrire(lignes_de_base: list[dict], nouvelles_lignes: list[dict]):
    """Ecrit lignes_de_base + nouvelles_lignes (en evitant les doublons stricts
    par 'preuve') dans le fichier candidats_a_verifier.csv."""
    preuves_existantes = {l["preuve"] for l in lignes_de_base}
    a_ajouter = [l for l in nouvelles_lignes if l["preuve"] not in preuves_existantes]

    toutes = lignes_de_base + a_ajouter
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    with open(FICHIER_CANDIDATS, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CHAMPS, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(toutes)

    log_info(f"{len(a_ajouter)} nouveau(x) candidat(s) ajouté(s) -> {FICHIER_CANDIDATS.name} "
              f"({len(toutes)} au total, dont déjà traités précédemment).")
