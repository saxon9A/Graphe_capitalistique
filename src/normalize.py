"""
Normalisation des réponses des différentes sources vers un format unique de
relation capitalistique, utilisé ensuite par explorer.py et export.py.

Format cible d'une relation :
    {
        "siren_detentrice": str,
        "nom_detentrice": str | None,
        "siren_detenue": str,
        "nom_detenue": str | None,
        "pourcentage_detention_directe": float | None,
        "profondeur": int,
        "annee_declaration": str | None,
        "source": str,
        "date_collecte": str,  # ISO 8601
    }
"""

from datetime import datetime, timezone


def _adresse_en_texte(adresse: dict | None) -> str | None:
    if not adresse:
        return None
    morceaux = [
        adresse.get("numero"),
        adresse.get("voie"),
        adresse.get("lieu_dit_hameau"),
        adresse.get("code_postal"),
        adresse.get("ville"),
        adresse.get("pays"),
    ]
    morceaux = [m for m in morceaux if m]
    return " ".join(morceaux) if morceaux else None


def normaliser_filiales_dgfip(siren_parent: str, nom_parent: str | None,
                               data: dict, annee: str, profondeur: int) -> list[dict]:
    """
    Transforme data["participations"]["filiales"] (format exact confirmé de
    l'API Entreprise / DGFIP) en liste de relations normalisées.

    data correspond au JSON "data" renvoyé par
    api_capitalistique.get_liens_capitalistiques().
    """
    relations = []
    if not data:
        return relations

    participations = data.get("participations") or {}
    filiales = participations.get("filiales") or []

    maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for f in filiales:
        relations.append({
            "siren_detentrice": siren_parent,
            "nom_detentrice": nom_parent,
            "siren_detenue": f.get("siren"),
            "nom_detenue": f.get("denomination"),
            "pourcentage_detention_directe": f.get("pourcentage_detention"),
            "profondeur": profondeur,
            "annee_declaration": annee,
            "source": "api_entreprise_dgfip_liens_capitalistiques",
            "date_collecte": maintenant,
            "adresse_filiale_declaree": _adresse_en_texte(f.get("adresse")),
            "forme_juridique_declaree": f.get("forme_juridique"),
        })

    return relations


def normaliser_actionnaires_dgfip(siren_entreprise: str, nom_entreprise: str | None,
                                   data: dict, annee: str) -> list[dict]:
    """
    Transforme data["capital"]["actionnaires"] en relations "actionnaire -> entreprise".
    Utile pour comprendre QUI détient une société du graphe (sens inverse des filiales),
    mais n'est PAS utilisé pour l'exploration récursive descendante (qui suit les filiales).
    """
    relations = []
    if not data:
        return relations

    capital = data.get("capital") or {}
    actionnaires = capital.get("actionnaires") or []
    maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for a in actionnaires:
        if a.get("type") == "personne_morale":
            attrs = a.get("personne_morale_attributes") or {}
            nom_actionnaire = attrs.get("denomination")
            siren_actionnaire = attrs.get("siren")
        else:
            attrs = a.get("personne_physique_attributes") or {}
            nom_actionnaire = attrs.get("nom_patronymique_et_prenoms")
            siren_actionnaire = None  # personne physique : pas de SIREN

        relations.append({
            "siren_detentrice": siren_actionnaire,
            "nom_detentrice": nom_actionnaire,
            "siren_detenue": siren_entreprise,
            "nom_detenue": nom_entreprise,
            "pourcentage_detention_directe": a.get("pourcentage"),
            "profondeur": None,  # sens ascendant, non utilisé pour la profondeur du graphe descendant
            "annee_declaration": annee,
            "source": "api_entreprise_dgfip_liens_capitalistiques_actionnariat",
            "date_collecte": maintenant,
            "type_actionnaire": a.get("type"),
        })

    return relations


def normaliser_relations_inpi(relations_brutes: list[dict]) -> list[dict]:
    """Passe les relations extraites par api_inpi.extraire_participations_best_effort
    au même format normalisé que les relations DGFIP (ajoute les champs manquants à None)."""
    maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")
    resultat = []
    for r in relations_brutes:
        resultat.append({
            "siren_detentrice": r.get("siren_detentrice"),
            "nom_detentrice": r.get("nom_detentrice"),
            "siren_detenue": r.get("siren_detenue"),
            "nom_detenue": r.get("nom_detenue"),
            "pourcentage_detention_directe": r.get("pourcentage_detention"),
            "profondeur": None,
            "annee_declaration": r.get("annee_declaration"),
            "source": "data_inpi_rne",
            "date_collecte": maintenant,
        })
    return resultat
