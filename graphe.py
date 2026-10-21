#!/usr/bin/env python3
"""
Point d'entrée du projet : extraction et cartographie des participations
capitalistiques d'une entreprise à partir de son SIREN.

Usage :
    python graphe.py 692030992
    python graphe.py 692030992 --profondeur-max 3

Voir le README.md pour la configuration des clés API (.env).
"""

import argparse
import sys
import time

from src import api_inpi_actes
from src import api_recherche_entreprises as recherche
from src import candidats
from src import config
from src import deu_eurazeo
from src import enrich
from src import explorer
from src import export
from src.logger import log_info


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Cartographie des participations capitalistiques d'une entreprise (SIREN)."
    )
    parser.add_argument(
        "siren", nargs="?", default=config.SIREN_DEPART,
        help=f"SIREN de l'entreprise de départ (par défaut : {config.SIREN_DEPART}, Eurazeo)."
    )
    parser.add_argument(
        "--profondeur-max", type=int, default=None,
        help=f"Profondeur maximale d'exploration récursive (par défaut : {config.PROFONDEUR_MAX})."
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    siren_depart = args.siren.strip()
    if args.profondeur_max is not None:
        config.PROFONDEUR_MAX = args.profondeur_max

    if not (siren_depart.isdigit() and len(siren_depart) == 9):
        print(f"⚠️  '{siren_depart}' ne ressemble pas à un SIREN valide (9 chiffres). "
              f"On continue quand même, mais vérifie la valeur.")

    debut = time.time()
    print(f"=== Cartographie capitalistique — SIREN de départ : {siren_depart} ===\n")

    # 1. Récupération du nom de l'entreprise de départ (confort d'affichage uniquement)
    brut_depart = recherche.get_entreprise_par_siren(siren_depart)
    nom_depart = None
    if brut_depart:
        nom_depart = brut_depart.get("nom_complet") or brut_depart.get("nom_raison_sociale")
        print(f"Entreprise de départ identifiée : {nom_depart} ({siren_depart})")
    else:
        print("⚠️  Impossible de récupérer le nom via l'API Recherche d'Entreprises "
              "(le programme continue avec le SIREN seul).")

    # 2. Exploration récursive des participations (option B puis repli option A)
    print("\n--- Étape 1/3 : exploration récursive des participations ---")
    entreprises, relations = explorer.explorer_graphe(siren_depart, nom_depart)
    print(f"{len(entreprises)} entreprise(s) identifiée(s) (y compris le point de départ), "
          f"{len(relations)} relation(s) capitalistique(s) brute(s).")

    if len(entreprises) <= 1 and not relations:
        print("\n⚠️  Aucune participation CONFIRMÉE n'a pu être extraite via les API "
              "structurées (B indisponible, et la fiche INPI ne contient pas ce type "
              "de donnée pour cette société). Consulte "
              f"{config.FICHIER_JOURNAL.name} pour le détail.")

    # 2bis. Sources non structurées (candidats à valider manuellement) :
    #   - DEU Eurazeo (uniquement si le SIREN de départ est celui d'Eurazeo)
    #   - Actes INPI (scan de documents légaux pour la société de départ)
    print("\n--- Étape bonus : recherche de candidats dans des sources non structurées ---")
    print("(résultats à VALIDER MANUELLEMENT avant de les considérer comme fiables)")

    if siren_depart == config.SIREN_EURAZEO and config.UTILISER_DEU_EURAZEO:
        try:
            candidats_deu = deu_eurazeo.extraire_filiales_et_participations()
            candidats.ajouter_candidats_deu(candidats_deu, siren_depart, nom_depart or "EURAZEO")
            print(f"  -> {len(candidats_deu)} candidat(s) extrait(s) du DEU Eurazeo 2025 "
                  f"(dont {sum(1 for c in candidats_deu if c.get('siren_candidat'))} avec SIREN deja identifie via le SIRET).")
        except Exception as exc:
            print(f"⚠️  Extraction DEU échouée : {exc}")

    if api_inpi_actes._login() is not None:  # réutilise les identifiants INPI déjà validés
        try:
            candidats_actes = api_inpi_actes.explorer_actes_pour_siren(
                siren_depart, max_actes=config.MAX_ACTES_PAR_SOCIETE
            )
            candidats.ajouter_candidats_actes(candidats_actes, nom_depart or "")
        except Exception as exc:
            print(f"⚠️  Scan des actes INPI échoué : {exc}")
    else:
        print("(scan des actes INPI ignoré : identifiants INPI non configurés)")

    # 3. Enrichissement administratif
    print("\n--- Étape 2/3 : enrichissement administratif (statut, adresse, NAF, effectif) ---")
    enrichissements = enrich.enrichir_entreprises(entreprises)

    # 4. Calcul des estimations de détention indirecte (théoriques)
    estimations = explorer.calculer_pourcentages_indirects(entreprises, relations)

    # 5. Export CSV
    print("\n--- Étape 3/3 : export des fichiers CSV ---")
    noms = {siren: info.get("nom") for siren, info in enrichissements.items()}
    actives, inactives = export.exporter_entreprises(enrichissements)
    lignes_participations = export.exporter_participations(relations, noms, estimations)

    duree = time.time() - debut
    print(f"\n=== Terminé en {duree:.1f}s ===")
    print(f"Dossier de sortie : {config.OUTPUT_DIR}")
    print(f"  - {config.FICHIER_ENTREPRISES_ACTIVES.name} : {len(actives)} entreprise(s) active(s)")
    print(f"  - {config.FICHIER_ENTREPRISES_INACTIVES.name} : {len(inactives)} entreprise(s) inactive(s)/inconnue(s)")
    print(f"  - {config.FICHIER_PARTICIPATIONS.name} : {len(lignes_participations)} relation(s)")
    print(f"  - {config.FICHIER_JOURNAL.name} : journal technique complet des appels")
    if candidats.FICHIER_CANDIDATS.exists():
        print(f"  - {candidats.FICHIER_CANDIDATS.name} : candidats de participations non confirmées "
              f"(DEU Eurazeo / actes INPI) — À VALIDER avant de lancer python valider.py")
    print("\n⚠️  Rappel : les pourcentages indirects sont des ESTIMATIONS THÉORIQUES "
          "(multiplication des taux directs le long d'un chemin), pas des données "
          "juridiquement certifiées. Vérifie le journal pour les années manquantes "
          "et les relations non confirmées.")

    log_info("Exécution terminée.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompu par l'utilisateur.")
        sys.exit(130)
