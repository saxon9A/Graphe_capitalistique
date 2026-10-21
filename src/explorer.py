"""
Exploration récursive (en largeur) du graphe capitalistique à partir d'une
entreprise de départ, avec :
  - contrôle des doublons (chaque SIREN n'est interrogé qu'une seule fois) ;
  - détection de cycle (on ne redescend jamais vers un SIREN déjà présent
    dans le chemin de détention courant) ;
  - bascule automatique de l'option B (API Entreprise) vers l'option A
    (Data INPI) dès qu'un accès non autorisé est détecté, sans réessayer B
    inutilement sur chaque société suivante ;
  - calcul d'une estimation théorique du pourcentage de détention indirect,
    clairement marquée comme telle (jamais présentée comme une donnée
    certifiée).
"""

from collections import deque

from . import api_capitalistique as capi
from . import api_inpi
from . import config
from . import normalize
from .logger import log, log_info


def determiner_mode_disponible() -> str:
    """Retourne 'B', 'A' ou 'aucun' selon ce qui est configuré dans .env."""
    if capi.jeton_configure():
        test = capi.tester_acces()
        if test["ok"]:
            log_info("Option B (API Entreprise) disponible : jeton valide avec des scopes.")
            return "B"
        log_info(f"Option B indisponible malgré un token renseigné : {test['message']} "
                  f"Bascule vers l'option A.")
    else:
        log_info("Option B non configurée (API_ENTREPRISE_TOKEN/RECIPIENT absents). "
                  "Utilisation directe de l'option A (Data INPI).")

    if api_inpi.identifiants_configures():
        return "A"

    log_info("Ni l'option B ni l'option A ne sont configurées : seul "
             "l'enrichissement via l'API Recherche d'Entreprises sera possible, "
             "sans extraction de nouvelles participations.")
    return "aucun"


def _explorer_dgfip_pour_siren(siren: str, nom_connu: str | None, profondeur: int):
    """
    Essaie chaque année de config.ANNEES_A_TESTER jusqu'à obtenir une réponse
    exploitable. Retourne (relations, annee_utilisee) ou ([], None).
    Peut lever capi.AccesNonAutorise (à gérer par l'appelant).
    """
    for annee in config.ANNEES_A_TESTER:
        data = capi.get_liens_capitalistiques(siren, annee)
        if data is not None:
            relations = normalize.normaliser_filiales_dgfip(siren, nom_connu, data, annee, profondeur)
            if relations:
                return relations, annee
            # Donnée présente mais 0 filiale déclarée : résultat valide, on s'arrête là
            # pour cet exercice (pas la peine de tester les années antérieures).
            return [], annee
    return [], None


def _explorer_inpi_pour_siren(siren: str, nom_connu: str | None):
    data = api_inpi.get_company(siren)
    if not data:
        return []
    brutes = api_inpi.extraire_participations_best_effort(siren, data)
    return normalize.normaliser_relations_inpi(brutes)


def explorer_graphe(siren_depart: str, nom_depart: str | None = None):
    """
    Explore récursivement le graphe capitalistique.

    Retourne (entreprises, relations) :
      - entreprises : dict {siren: {"nom", "profondeur_min", "chemin"}}
      - relations   : liste de relations normalisées (voir normalize.py)
    """
    mode = determiner_mode_disponible()

    entreprises = {
        siren_depart: {"nom": nom_depart, "profondeur_min": 0, "chemin": [siren_depart]}
    }
    relations: list[dict] = []
    deja_explore: set[str] = set()
    file_attente = deque([(siren_depart, nom_depart, 0, [siren_depart])])

    while file_attente:
        siren, nom_connu, profondeur, chemin = file_attente.popleft()

        if siren in deja_explore:
            continue
        deja_explore.add(siren)

        if profondeur >= config.PROFONDEUR_MAX:
            log_info(f"Profondeur max ({config.PROFONDEUR_MAX}) atteinte pour {siren}, "
                      f"exploration de ses propres participations ignorée.")
            continue

        filiales_relations: list[dict] = []

        if mode == "B":
            try:
                filiales_relations, _annee = _explorer_dgfip_pour_siren(siren, nom_connu, profondeur)
            except capi.AccesNonAutorise as exc:
                log("exploration", "api_entreprise", "non_autorise",
                    f"Bascule définitive vers l'option A : {exc}", siren=siren)
                mode = "A" if api_inpi.identifiants_configures() else "aucun"

        if mode == "A" and not filiales_relations:
            filiales_relations = _explorer_inpi_pour_siren(siren, nom_connu)

        relations.extend(filiales_relations)

        for rel in filiales_relations:
            enfant = rel.get("siren_detenue")
            if not enfant:
                continue  # SIREN manquant/étranger fictif : on garde la relation mais sans descendre dessus
            if enfant in chemin:
                log("exploration", "controle_cycle", "info",
                    f"Cycle détecté : {enfant} apparaît déjà dans le chemin {chemin}. "
                    f"Relation conservée, exploration non poursuivie sur ce nœud.",
                    siren=enfant)
                continue

            nom_enfant = rel.get("nom_detenue")
            nouveau_chemin = chemin + [enfant]
            if enfant not in entreprises:
                entreprises[enfant] = {
                    "nom": nom_enfant,
                    "profondeur_min": profondeur + 1,
                    "chemin": nouveau_chemin,
                }
            if enfant not in deja_explore:
                file_attente.append((enfant, nom_enfant, profondeur + 1, nouveau_chemin))

    return entreprises, relations


def calculer_pourcentages_indirects(entreprises: dict, relations: list[dict]) -> dict:
    """
    Calcule, pour chaque entreprise, une ESTIMATION THÉORIQUE du pourcentage
    de détention indirect par l'entreprise de départ, en multipliant les
    pourcentages directs le long du "chemin" retenu lors de l'exploration
    (premier chemin trouvé, pas nécessairement le seul chemin possible).

    Retourne {siren: pourcentage_estime_ou_None}.
    Ce calcul est une approximation : en cas de détentions multiples ou de
    participations croisées, le chemin retenu n'est qu'UN chemin parmi
    d'autres et ne doit pas être lu comme une détention juridiquement
    certifiée (voir § 4 du cahier des charges).
    """
    # index rapide (parent, enfant) -> pourcentage direct
    pourcentage_direct = {}
    for r in relations:
        p, e = r.get("siren_detentrice"), r.get("siren_detenue")
        if p and e and r.get("pourcentage_detention_directe") is not None:
            # s'il y a plusieurs relations pour le même couple (années différentes),
            # on garde la plus récente déjà rencontrée (les relations sont ajoutées
            # dans l'ordre d'exploration, donc la plus récente écrase la précédente)
            pourcentage_direct[(p, e)] = r["pourcentage_detention_directe"]

    estimations = {}
    for siren, infos in entreprises.items():
        chemin = infos.get("chemin") or []
        if len(chemin) <= 1:
            estimations[siren] = None  # c'est l'entreprise de départ elle-même
            continue
        produit = 1.0
        complet = True
        for i in range(len(chemin) - 1):
            p = pourcentage_direct.get((chemin[i], chemin[i + 1]))
            if p is None:
                complet = False
                break
            produit *= float(p) / 100.0
        estimations[siren] = round(produit * 100, 4) if complet else None

    return estimations
