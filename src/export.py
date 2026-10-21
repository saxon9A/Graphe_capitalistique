"""
Génération des fichiers CSV de sortie, au format Excel/Power BI
(délimiteur ';', encodage utf-8-sig pour un affichage correct des accents
dans Excel sous Windows).
"""

import csv

from . import config
from .logger import log_info

STATUTS_ACTIFS = {"A"}  # code renvoyé par l'API Recherche d'Entreprises pour "actif"


def _ecrire_csv(chemin, lignes: list[dict], champs: list[str]):
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=champs, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for ligne in lignes:
            writer.writerow(ligne)


def exporter_entreprises(enrichissements: dict):
    """
    Sépare les entreprises en actives / inactives selon statut_administratif
    et écrit entreprises_actives.csv + entreprises_inactives.csv.

    Une entreprise dont le statut est inconnu (aucune source n'a répondu)
    n'est PAS considérée active par défaut : elle part dans le fichier
    "inactives" avec la mention explicite "statut_inconnu" pour ne pas
    fausser le fichier principal, conformément au cahier des charges.
    """
    champs = [
        "siren", "nom", "statut_administratif", "adresse_siege",
        "code_naf", "libelle_naf", "tranche_effectif", "libelle_tranche_effectif",
        "nombre_exact_salaries", "date_donnees", "source_enrichissement",
        "profondeur_min", "chemin_detention",
    ]

    actives, inactives = [], []
    for e in enrichissements.values():
        statut = e.get("statut_administratif")
        ligne = dict(e)
        if statut in STATUTS_ACTIFS:
            actives.append(ligne)
        else:
            if statut is None:
                ligne["statut_administratif"] = "statut_inconnu"
            inactives.append(ligne)

    _ecrire_csv(config.FICHIER_ENTREPRISES_ACTIVES, actives, champs)
    _ecrire_csv(config.FICHIER_ENTREPRISES_INACTIVES, inactives, champs)

    log_info(f"{len(actives)} entreprise(s) active(s) -> {config.FICHIER_ENTREPRISES_ACTIVES.name}")
    log_info(f"{len(inactives)} entreprise(s) inactive(s)/statut inconnu -> "
              f"{config.FICHIER_ENTREPRISES_INACTIVES.name}")

    return actives, inactives


def exporter_participations(relations: list[dict], noms: dict, estimations_indirectes: dict):
    """
    noms : dict {siren: nom} (utilisé pour compléter les noms manquants côté détenue/détentrice)
    estimations_indirectes : dict {siren_detenue: pourcentage_estime_ou_None}, voir
        explorer.calculer_pourcentages_indirects()
    """
    champs = [
        "siren_detentrice", "nom_detentrice", "siren_detenue", "nom_detenue",
        "pourcentage_detention_directe", "pourcentage_indirect_estime_theorique",
        "profondeur", "chemin_detention", "annee_declaration",
        "source", "date_collecte",
    ]

    lignes = []
    for r in relations:
        siren_detenue = r.get("siren_detenue")
        ligne = dict(r)
        ligne["nom_detentrice"] = r.get("nom_detentrice") or noms.get(r.get("siren_detentrice"))
        ligne["nom_detenue"] = r.get("nom_detenue") or noms.get(siren_detenue)
        ligne["pourcentage_indirect_estime_theorique"] = (
            estimations_indirectes.get(siren_detenue) if siren_detenue else None
        )
        ligne["chemin_detention"] = " -> ".join(
            r.get("chemin", [])
        ) if isinstance(r.get("chemin"), list) else ""
        lignes.append(ligne)

    _ecrire_csv(config.FICHIER_PARTICIPATIONS, lignes, champs)
    log_info(f"{len(lignes)} relation(s) capitalistique(s) -> {config.FICHIER_PARTICIPATIONS.name}")
    return lignes
