#!/usr/bin/env python3
"""
Processus de validation manuelle des candidats de participation.

Usage :
    1. Lance d'abord `python graphe.py` (voir sortie/candidats_a_verifier.csv).
    2. Ouvre sortie/candidats_a_verifier.csv dans Excel.
    3. Pour chaque ligne que tu as vérifiée et jugée correcte, mets "oui" dans
       la colonne 'valide'. Si tu connais déjà le SIREN de la société
       détenue, renseigne-le dans 'siren_confirme' (sinon le programme
       essaiera de le retrouver par nom, et te signalera les cas ambigus).
    4. Sauvegarde le fichier (garde le format CSV, ne pas enregistrer en .xlsx).
    5. Lance : python valider.py

Ce script :
    - lit les lignes avec valide == "oui" ;
    - résout le SIREN de la société détenue si besoin (recherche par nom,
      ambigu => ignoré avec un message, à résoudre manuellement) ;
    - ajoute ces relations, maintenant considérées comme confirmées par toi,
      à sortie/participations.csv ;
    - relance automatiquement une recherche de candidats (actes INPI) pour
      chaque nouvelle société confirmée, afin de préparer le prochain tour
      de validation (exploration incrémentale, niveau par niveau).
"""

import csv
import sys

from src import api_inpi_actes
from src import api_recherche_entreprises as recherche
from src import candidats as candidats_module
from src import config
from src.logger import log_info


def lire_candidats_valides() -> list[dict]:
    if not candidats_module.FICHIER_CANDIDATS.exists():
        print(f"Aucun fichier {candidats_module.FICHIER_CANDIDATS} trouvé. "
              f"Lance d'abord python graphe.py.")
        return []
    with open(candidats_module.FICHIER_CANDIDATS, encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    return [l for l in lignes if (l.get("valide") or "").strip().lower() in ("oui", "o", "yes", "y", "1")]


def resoudre_siren(nom_candidat: str, siren_confirme: str) -> tuple[str | None, str | None]:
    """Retourne (siren, nom_officiel) ou (None, None) si impossible/ambigu."""
    if siren_confirme and siren_confirme.strip():
        return siren_confirme.strip(), nom_candidat

    if not nom_candidat:
        return None, None

    resultats = recherche.rechercher_par_nom(nom_candidat, max_resultats=5)
    if not resultats:
        print(f"  ⚠️  Aucun résultat pour '{nom_candidat}' : renseigne le SIREN manuellement "
              f"dans la colonne siren_confirme et relance.")
        return None, None
    if len(resultats) > 1:
        # Ambigu si plusieurs résultats ont un nom très proche
        premiers_noms = {r.get("nom_complet", "").lower() for r in resultats[:3]}
        if len(premiers_noms) > 1:
            print(f"  ⚠️  Plusieurs résultats possibles pour '{nom_candidat}' : "
                  f"{[r.get('nom_complet') for r in resultats[:3]]}. "
                  f"Renseigne le bon SIREN manuellement dans siren_confirme et relance.")
            return None, None

    meilleur = resultats[0]
    return meilleur.get("siren"), meilleur.get("nom_complet")


def ajouter_a_participations(nouvelles_relations: list[dict]):
    """Ajoute les relations validées à sortie/participations.csv (en conservant l'existant)."""
    champs = [
        "siren_detentrice", "nom_detentrice", "siren_detenue", "nom_detenue",
        "pourcentage_detention_directe", "pourcentage_indirect_estime_theorique",
        "profondeur", "chemin_detention", "annee_declaration",
        "source", "date_collecte",
    ]
    existantes = []
    if config.FICHIER_PARTICIPATIONS.exists():
        with open(config.FICHIER_PARTICIPATIONS, encoding="utf-8-sig", newline="") as f:
            existantes = list(csv.DictReader(f, delimiter=";"))

    cles_existantes = {(l["siren_detentrice"], l["siren_detenue"]) for l in existantes}
    ajoutees = 0
    for r in nouvelles_relations:
        cle = (r["siren_detentrice"], r["siren_detenue"])
        if cle in cles_existantes:
            continue
        existantes.append(r)
        cles_existantes.add(cle)
        ajoutees += 1

    with open(config.FICHIER_PARTICIPATIONS, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=champs, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(existantes)

    print(f"{ajoutees} relation(s) validée(s) ajoutée(s) à {config.FICHIER_PARTICIPATIONS.name}.")


def main():
    lignes_valides = lire_candidats_valides()
    if not lignes_valides:
        print("Aucune ligne avec valide='oui' trouvée dans candidats_a_verifier.csv. Rien à faire.")
        return

    print(f"{len(lignes_valides)} candidat(s) marqué(s) 'oui' à traiter.\n")

    nouvelles_relations = []
    nouveaux_sirens_confirmes = []

    for ligne in lignes_valides:
        siren_source = ligne.get("siren_societe_source", "").strip()
        nom_source = ligne.get("nom_societe_source", "").strip()
        nom_candidat = ligne.get("nom_candidat_detenue", "").strip()
        pourcentage = ligne.get("pourcentage_candidat", "").strip()
        siren_confirme_saisi = ligne.get("siren_confirme", "").strip()

        if not nom_candidat:
            print(f"  ⚠️  Ligne sans nom de société détenue (source: {ligne.get('source')}) : "
                  f"remplis 'nom_candidat_detenue' manuellement si identifiable, puis relance.")
            continue

        print(f"Résolution de '{nom_candidat}'...")
        siren_detenue, nom_officiel = resoudre_siren(nom_candidat, siren_confirme_saisi)
        if not siren_detenue:
            continue

        nouvelles_relations.append({
            "siren_detentrice": siren_source,
            "nom_detentrice": nom_source,
            "siren_detenue": siren_detenue,
            "nom_detenue": nom_officiel or nom_candidat,
            "pourcentage_detention_directe": pourcentage or None,
            "pourcentage_indirect_estime_theorique": "",
            "profondeur": "",
            "chemin_detention": "",
            "annee_declaration": "",
            "source": f"{ligne.get('source')}_valide_manuellement",
            "date_collecte": "",
        })
        nouveaux_sirens_confirmes.append((siren_detenue, nom_officiel or nom_candidat))

    if nouvelles_relations:
        ajouter_a_participations(nouvelles_relations)
    else:
        print("Aucune relation n'a pu être résolue automatiquement (voir les ⚠️ ci-dessus).")
        return

    # Prépare le prochain tour : scanne les actes INPI des sociétés nouvellement confirmées
    if api_inpi_actes._login() is not None:
        print("\nRecherche de nouveaux candidats (actes INPI) pour les sociétés "
              "nouvellement confirmées...")
        for siren, nom in nouveaux_sirens_confirmes:
            c = api_inpi_actes.explorer_actes_pour_siren(siren, max_actes=config.MAX_ACTES_PAR_SOCIETE)
            candidats_module.ajouter_candidats_actes(c, nom)
        print(f"\nRelis {candidats_module.FICHIER_CANDIDATS.name} pour le prochain tour de validation.")
    else:
        print("\n(identifiants INPI non configurés : pas de recherche de candidats pour le niveau suivant)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
