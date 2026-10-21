"""
Enrichissement administratif de chaque entreprise identifiée : statut,
adresse, NAF, effectif, dirigeants quand disponibles.

Source principale : API Recherche d'Entreprises (aucune clé).
Source de secours optionnelle : API Sirene INSEE (si INSEE_API_KEY renseignée
et qu'un champ manque).
"""

import time

from . import api_recherche_entreprises as recherche
from . import api_sirene
from . import config
from .logger import log, log_info


def enrichir_entreprises(entreprises: dict) -> dict:
    """
    entreprises : dict {siren: {"nom", "profondeur_min", "chemin"}} (sortie de explorer.py)

    Retourne dict {siren: dict enrichi} avec, pour chaque entreprise :
        nom, statut_administratif, adresse_siege, code_naf, libelle_naf,
        tranche_effectif, libelle_tranche_effectif, nombre_exact_salaries,
        date_donnees, source_enrichissement, profondeur_min, chemin_detention
    """
    resultats = {}
    total = len(entreprises)
    log_info(f"Enrichissement administratif de {total} entreprise(s) via "
              f"l'API Recherche d'Entreprises.")

    for i, (siren, infos) in enumerate(entreprises.items(), start=1):
        enrichissement = {}
        brut = recherche.get_entreprise_par_siren(siren)
        if brut:
            enrichissement = recherche.normaliser_enrichissement(brut)
            nom = brut.get("nom_complet") or brut.get("nom_raison_sociale") or infos.get("nom")
        else:
            nom = infos.get("nom")

        # Repli optionnel sur Sirene INSEE si la clé est configurée et que le
        # statut administratif (champ essentiel pour le filtrage) est manquant.
        if not enrichissement.get("statut_administratif") and api_sirene.cle_configuree():
            ul = api_sirene.get_unite_legale(siren)
            if ul:
                periode = (ul.get("periodesUniteLegale") or [{}])[0]
                enrichissement.setdefault("statut_administratif", periode.get("etatAdministratifUniteLegale"))
                enrichissement.setdefault("code_naf", periode.get("activitePrincipaleUniteLegale"))
                enrichissement["source_enrichissement"] = (
                    enrichissement.get("source_enrichissement", "") + "+sirene_insee"
                ).lstrip("+")

        resultats[siren] = {
            "siren": siren,
            "nom": nom,
            "profondeur_min": infos.get("profondeur_min"),
            "chemin_detention": " -> ".join(infos.get("chemin") or []),
            **enrichissement,
        }

        if not brut and not (enrichissement.get("statut_administratif")):
            log("enrichissement", "programme", "info",
                "Aucune donnée administrative trouvée pour ce SIREN (ni "
                "recherche-entreprises, ni Sirene). Champs laissés vides.",
                siren=siren)

        if i % 25 == 0 or i == total:
            log_info(f"Enrichissement : {i}/{total} entreprises traitées.")

        time.sleep(config.PAUSE_ENTRE_APPELS)

    return resultats
