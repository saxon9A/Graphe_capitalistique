#!/usr/bin/env python3
"""
Enrichit sortie/portefeuille_eurazeo_catalogue.csv avec, pour les sociétés qui ont
un SIREN candidat (rapproché par le nom, voir catalogue_eurazeo.py) :

  TIER 1 (gratuit, sans clé, API Recherche d'Entreprises — même source que
  partout ailleurs dans ce projet) :
    - effectif (tranche_effectif), rafraîchi ;
    - chiffre d'affaires, résultat net, année de l'exercice, CA de l'exercice
      précédent et croissance du CA (quand deux exercices sont disponibles) ;
    - date_installation_siege (date d'installation à l'adresse actuelle du
      siège), pour le calcul du cycle de bail commercial 3/6/9 du dashboard ;
    - fiche d'identité complète (SIRET du siège, forme juridique, NAF,
      dirigeants, nombre d'établissements, date de création) — ajouté le
      21/10/2026, à la demande explicite de l'utilisateur : voir le ⚠️ ci-dessous.

  TIER 2, en repli UNIQUEMENT pour les sociétés sans CA via le Tier 1, et
  UNIQUEMENT si INPI_USERNAME/INPI_PASSWORD sont renseignés dans .env :
    - télécharge (ou réutilise s'il existe déjà) le dernier compte annuel
      PUBLIC déposé au RNE (même mécanisme que niveau2_collecter.py) ;
    - en extrait CA/résultat/effectif par recherche de mots-clés dans le texte
      (src/comptes.py) — BEST EFFORT, jamais garanti, toujours accompagné de
      la ligne brute source pour vérification. Écrit dans des colonnes à part
      (*_estime_bilan), jamais mélangé aux colonnes structurées du Tier 1.

⚠️ Rappel du projet : le SIREN de chaque ligne du catalogue n'est qu'un
rapprochement par similarité de nom, jamais garanti, MÊME à un score de 100 %
avec « vérification nécessaire » à Non (voir catalogue_eurazeo.py — exemples
réels déjà rencontrés sur ce catalogue : « Mapal », « Planet », rapprochés à
100 % vers des sociétés sans rapport). Jusqu'au 21/10/2026, le dashboard ne
montrait donc JAMAIS la fiche d'identité complète pour une société du
catalogue, quel que soit le score. À cette date, l'utilisateur a demandé
explicitement de l'afficher quand même pour toutes les sociétés du catalogue,
en toute connaissance de ce risque (vérifié dans ce cas précis : Ankorstore
correctement rapproché). Le badge « Lien non vérifié » sur la fiche société et
le lien vers la fiche officielle (annuaire-entreprises.data.gouv.fr) restent
affichés pour TOUTE société du catalogue, pour permettre une vérification en
un clic avant toute prise de contact.

Usage :
    python enrichir_catalogue_finances.py
"""

import csv
import shutil
import time

import pandas as pd

from src import api_inpi, comptes, config, details
from src.api_recherche_entreprises import get_entreprise_par_siren

CHEMIN = config.OUTPUT_DIR / "portefeuille_eurazeo_catalogue.csv"
DOSSIER_DASH = config.BASE_DIR / "dashboard" / "data"
CHAMPS_TIER1 = ["tranche_effectif", "chiffre_affaires", "resultat_net", "annee_finances",
                "chiffre_affaires_annee_precedente", "croissance_ca_pct", "date_installation_siege",
                # Fiche d'identité complète (21/10/2026) : déjà renvoyés par le même appel API que
                # ci-dessus (details.ligne_depuis_api), aucun appel supplémentaire nécessaire.
                "siret_siege", "forme_juridique_code", "forme_juridique", "naf_code", "naf_libelle",
                "naf_section_code", "naf_section", "dirigeants", "nb_etablissements",
                "nb_etablissements_ouverts", "categorie_entreprise", "date_creation",
                "annee_tranche_effectif"]
CHAMPS_TIER2 = ["chiffre_affaires_estime_bilan", "resultat_net_estime_bilan", "effectif_estime_bilan",
                "bilan_ligne_source_ca", "bilan_ligne_source_resultat", "bilan_ligne_source_effectif"]


def _s(x) -> str:
    """Colonnes du catalogue stockées en texte (dtype 'str' strict côté pandas/pyarrow sur certaines
    installations) : un int/float écrit tel quel y fait planter l'écriture. On repasse donc toujours
    par une chaîne explicite avant d'écrire dans le DataFrame — jamais un int/float brut."""
    return "" if x is None else str(x)


def enrichir_tier1(df: pd.DataFrame) -> list[dict]:
    """Rafraîchit chaque ligne avec SIREN via l'API gratuite. Renvoie la liste des sociétés
    (siren, nom) qui restent sans chiffre d'affaires après ce passage, pour le Tier 2."""
    for c in CHAMPS_TIER1:
        if c not in df.columns:
            df[c] = ""

    a_traiter = df.index[df["siren"].str.strip() != ""]
    print(f"=== Tier 1 (API gratuite) : {len(a_traiter)} société(s) avec un SIREN candidat ===")
    sans_ca = []
    for i, idx in enumerate(a_traiter, 1):
        siren = df.at[idx, "siren"].strip()
        nom = df.at[idx, "nom"]
        try:
            brut = get_entreprise_par_siren(siren)
            if not brut:
                print(f"  {i}/{len(a_traiter)}  {nom[:35]:35}  introuvable via l'API")
                sans_ca.append({"siren": siren, "nom": nom})
                time.sleep(config.PAUSE_ENTRE_APPELS)
                continue
            e = details.ligne_depuis_api(brut)
            df.at[idx, "tranche_effectif"] = _s(e.get("tranche_effectif_code"))
            df.at[idx, "chiffre_affaires"] = _s(e.get("chiffre_affaires"))
            df.at[idx, "resultat_net"] = _s(e.get("resultat_net"))
            df.at[idx, "annee_finances"] = _s(e.get("annee_finances"))
            df.at[idx, "chiffre_affaires_annee_precedente"] = _s(e.get("chiffre_affaires_annee_precedente"))
            df.at[idx, "croissance_ca_pct"] = _s(e.get("croissance_ca_pct"))
            df.at[idx, "date_installation_siege"] = _s(e.get("date_installation_siege"))
            df.at[idx, "siret_siege"] = _s(e.get("siret_siege"))
            df.at[idx, "forme_juridique_code"] = _s(e.get("forme_juridique_code"))
            df.at[idx, "forme_juridique"] = _s(e.get("forme_juridique"))
            df.at[idx, "naf_code"] = _s(e.get("naf_code"))
            df.at[idx, "naf_libelle"] = _s(e.get("naf_libelle"))
            df.at[idx, "naf_section_code"] = _s(e.get("naf_section_code"))
            df.at[idx, "naf_section"] = _s(e.get("naf_section"))
            df.at[idx, "dirigeants"] = _s(e.get("dirigeants"))
            df.at[idx, "nb_etablissements"] = _s(e.get("nb_etablissements"))
            df.at[idx, "nb_etablissements_ouverts"] = _s(e.get("nb_etablissements_ouverts"))
            df.at[idx, "categorie_entreprise"] = _s(e.get("categorie_entreprise"))
            df.at[idx, "date_creation"] = _s(e.get("date_creation"))
            etat = "CA trouvé" if e.get("chiffre_affaires") is not None else "pas de CA structuré"
            print(f"  {i}/{len(a_traiter)}  {nom[:35]:35}  {etat}  ·  installation : {e.get('date_installation_siege') or '—'}")
            if e.get("chiffre_affaires") is None:
                sans_ca.append({"siren": siren, "nom": nom})
        except Exception as exc:   # une société en échec ne doit jamais arrêter les 217 autres
            print(f"  {i}/{len(a_traiter)}  {nom[:35]:35}  erreur : {exc}")
            sans_ca.append({"siren": siren, "nom": nom})
        time.sleep(config.PAUSE_ENTRE_APPELS)
    return sans_ca


def enrichir_tier2(df: pd.DataFrame, candidats: list[dict]):
    for c in CHAMPS_TIER2:
        if c not in df.columns:
            df[c] = ""
    if not candidats:
        return
    if not api_inpi.identifiants_configures():
        print(f"\n=== Tier 2 (comptes annuels INPI) : ignoré, INPI_USERNAME/INPI_PASSWORD absents du .env "
              f"({len(candidats)} société(s) resteront sans CA). ===")
        return

    from niveau2_collecter import collecter   # réutilise le téléchargement/extraction déjà en place

    print(f"\n=== Tier 2 (comptes annuels INPI, repli) : {len(candidats)} société(s) sans CA via le Tier 1 ===")
    fichier_etat = config.OUTPUT_DIR / "catalogue_tier2_collecte.csv"
    collecter(candidats, fichier_etat)   # télécharge/relit les bilans manquants (ceux déjà là ne sont pas retéléchargés)

    par_siren = {df.at[i, "siren"].strip(): i for i in df.index if df.at[i, "siren"].strip()}
    trouves = 0
    for c in candidats:
        idx = par_siren.get(c["siren"])
        if idx is None:
            continue
        try:
            ind = comptes.indicateurs_depuis_dossier(c["siren"])
            if not ind:
                print(f"  ✗ {c['nom'][:35]:35}  aucun compte annuel lisible")
                continue
            for champ in CHAMPS_TIER2:
                df.at[idx, champ] = _s(ind.get(champ))
            if ind.get("chiffre_affaires_estime_bilan") is not None:
                trouves += 1
                print(f"  ✓ {c['nom'][:35]:35}  CA extrait du bilan (à vérifier) : {ind['chiffre_affaires_estime_bilan']:,.0f} €".replace(",", " "))
            else:
                print(f"  ✗ {c['nom'][:35]:35}  bilan lu mais aucun CA repéré dans le texte")
        except Exception as exc:
            print(f"  ✗ {c['nom'][:35]:35}  erreur : {exc}")
    print(f"\n{trouves}/{len(candidats)} CA estimé(s) depuis un bilan (TOUJOURS À VÉRIFIER, voir la ligne source).")


def main():
    if not CHEMIN.exists():
        print(f"Fichier introuvable : {CHEMIN}. Lance d'abord : python catalogue_eurazeo.py chemin/du/scrape.csv")
        return
    df = pd.read_csv(CHEMIN, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)

    sans_ca = enrichir_tier1(df)
    # Sauvegarde intermédiaire : niveau2_collecter.collecter() (Tier 2) arrête tout le programme
    # (sys.exit) si la connexion INPI échoue en cours de route (identifiants révoqués, réseau...).
    # On ne veut jamais perdre le travail du Tier 1, déjà payé en appels API, pour autant.
    df.to_csv(CHEMIN, sep=";", index=False, encoding="utf-8-sig")

    try:
        enrichir_tier2(df, sans_ca)
    except SystemExit:
        print("\n⚠️  Le Tier 2 (comptes annuels INPI) s'est arrêté en cours de route (connexion INPI). "
              "Les résultats du Tier 1 sont déjà enregistrés ; relance ce script pour reprendre le Tier 2.")

    df.to_csv(CHEMIN, sep=";", index=False, encoding="utf-8-sig")
    if DOSSIER_DASH.exists():
        shutil.copy(CHEMIN, DOSSIER_DASH / CHEMIN.name)
        print(f"\nCopié aussi dans {DOSSIER_DASH}")

    avec_ca_structure = int((df["chiffre_affaires"].str.strip() != "").sum())
    avec_ca_bilan = int((df["chiffre_affaires_estime_bilan"].astype(str).str.strip() != "").sum())
    print(f"\n=== Bilan : {avec_ca_structure}/{len(df)} société(s) avec un CA structuré (Tier 1), "
          f"+{avec_ca_bilan} avec un CA estimé depuis un bilan (Tier 2, à vérifier). -> {CHEMIN}")


if __name__ == "__main__":
    main()
