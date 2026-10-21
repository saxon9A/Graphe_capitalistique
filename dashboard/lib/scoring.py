"""Cycle de bail commercial (3/6/9) et score de potentiel de mouvement.

RIEN ici n'est une donnée publiée : tout est calculé à partir de la date
d'installation au siège actuel, quand on la connaît (`date_installation_siege`,
produite par enrichir_catalogue_finances.py / completer_dates_installation.py).

Règle du 3/6/9 (statut des baux commerciaux, art. L145-4 et L145-9 du Code de
commerce) : un bail commercial classique dure 9 ans, mais le locataire peut le
résilier à chaque échéance triennale (3, 6, 9 ans), avec un préavis de 6 mois.
Simplification assumée et documentée : on suppose que ce cycle de 3 ans continue
indéfiniment depuis la date d'installation. En réalité, un nouveau bail (avec une
nouvelle date de départ qu'on ne connaît pas) a pu être signé après la 9e année —
l'échéance calculée ici est donc une ESTIMATION, pas une date de bail réelle.

Si la date d'installation est inconnue (société étrangère, donnée Sirene
manquante...), rien n'est calculé : jamais remplacé par une date approchante
(ex. date de création de la société) — choix explicite du 21/10/2026.

----------------------------------------------------------------------------
v2 (21/10/2026) — scoring de potentiel porté du projet PRSimmo de l'utilisateur
(github.com/saxon9A/PRSimmo, dépôt privé, lu en lecture seule à sa demande :
« je veux la même chose »). Ce qui change par rapport à la v1 :

  - BAIL : au lieu de 4 paliers fixes, une courbe continue par interpolation
    (COURBE_BAIL, reprise telle quelle de src/scoring/potentiel.py) sur les 36
    mois du cycle triennal — creuse juste après une échéance manquée (congé
    probablement raté), remonte à son maximum entre 8 et 22 mois avant la
    prochaine échéance (fenêtre idéale pour démarcher), redescend ensuite.
    Cette courbe est utilisée UNIQUEMENT pour le nombre (score_bail) ; les
    dates et le statut AFFICHÉS sur la fiche société restent calculés par
    bail_369() ci-dessous, inchangé (déjà correct, avec la gestion du délai de
    préavis dépassé — voir sa docstring) : rien ne change dans ce que
    l'utilisateur voit comme date ou échéance.
  - FINANCES = DIRECTION, pas « santé » (analyser_finances, repris de
    PRSimmo) : une forte croissance du CA ET une forte baisse/des pertes
    marquées comptent désormais POSITIVEMENT (signal de mouvement : s'agrandir
    OU réduire sa surface), pas seulement la croissance comme en v1.
  - Donnée absente = toujours NEUTRE (0,5), jamais une pénalité — jamais
    retirée du total en recalculant les poids sur les seuls critères connus
    (ce que faisait la v1). Un score_fiabilite (0 à 2) dit séparément combien
    de critères (bail, finances) reposent sur une donnée réelle.
  - Pondération : 40 % bail + 25 % finances, renormalisés sur 100 % (PRSimmo
    pondère aussi un 3e critère « événements » à 35 %, à partir de signaux
    BODACC + presse — qu'on ne collecte PAS dans ce projet). Décision
    explicite de l'utilisateur (21/10/2026) plutôt que de simuler ce critère
    avec un signal plus pauvre (`etat_web`, les mouvements capitalistiques
    Eurazeo) : son poids est réparti sur bail et finances
    (40/65 ≈ 61,5 % et 25/65 ≈ 38,5 %).
  - Le bonus de taille (`groupe_effectif`, +15/+10/+5 en v1) est supprimé :
    PRSimmo ne score pas la taille comme critère d'opportunité (l'effectif n'y
    sert qu'à estimer une fourchette de m², fonctionnalité non portée ici non
    plus, faute de filtre « surface recherchée » dans ce dashboard). Décision
    explicite de l'utilisateur (21/10/2026).

Le score reste pensé pour un usage de prospection immobilière : quelle
entreprise serait disposée à chercher de nouveaux locaux. Ce n'est jamais une
prédiction fiable, seulement un faisceau d'indices pondérés, toujours montré en
détail sur la fiche société.
"""

from __future__ import annotations

import datetime as dt
from datetime import date, datetime

import pandas as pd

STATUT_INCONNU = "Échéance inconnue"
NEUTRE = 0.5

# Niveaux d'urgence (affichage/filtre) : 3 = préavis ouvert maintenant, 0 = échéance lointaine, None = inconnue.
LIBELLE_URGENCE = {
    3: "Préavis ouvert",
    2: "Échéance < 1 an",
    1: "Échéance 1 à 2 ans",
    0: "Échéance > 2 ans",
    None: STATUT_INCONNU,
}


def bail_369(date_installation) -> dict:
    """date_installation : Timestamp / str ISO / None. Renvoie toujours les mêmes clés.
    Utilisé pour l'AFFICHAGE (dates et statut montrés sur la fiche société) et pour le
    filtre de la colonne de gauche. Inchangé depuis la v1 : voir le calcul du score de
    potentiel (score_bail_potentiel) plus bas pour ce qui alimente le score chiffré.

    Point d'attention traité ici : la date limite de préavis (6 mois avant l'échéance) peut être
    déjà dépassée alors que l'échéance elle-même n'est pas encore arrivée. Dans ce cas, le
    locataire n'a PLUS le droit de résilier à cette échéance (délai légal manqué) : il reste engagé
    jusqu'à l'échéance SUIVANTE, et c'est elle qu'il faut regarder — pas celle qu'on vient de rater.
    Sans ce traitement, une société juste après une date limite manquée serait classée « urgente »
    à tort, alors qu'elle est au contraire verrouillée pour les mois qui viennent."""
    vide = {"prochaine_echeance_369": None, "date_limite_preavis": None, "jours_avant_limite": None,
            "urgence_369": None, "statut_bail": STATUT_INCONNU, "verrouille": None}
    if date_installation is None:
        return vide
    d = pd.to_datetime(date_installation, errors="coerce")
    if pd.isna(d):
        return vide
    d = d.date()
    aujourdhui = dt.date.today()

    def _echeance(k):
        try:
            return d.replace(year=d.year + 3 * k)
        except ValueError:   # 29 février sur une année non bissextile
            return d.replace(year=d.year + 3 * k, day=28)

    k = 1
    echeance = _echeance(k)
    while echeance <= aujourdhui:
        k += 1
        echeance = _echeance(k)
    limite = echeance - dt.timedelta(days=182)   # ~ 6 mois de préavis

    verrouille = False
    if aujourdhui >= limite:
        # Délai de préavis pour CETTE échéance déjà dépassé : on bascule sur l'échéance suivante,
        # la seule encore atteignable.
        verrouille = True
        k += 1
        echeance = _echeance(k)
        limite = echeance - dt.timedelta(days=182)

    jours = (limite - aujourdhui).days
    if jours <= 90:
        urgence = 3
    elif jours <= 365:
        urgence = 2
    elif jours <= 730:
        urgence = 1
    else:
        urgence = 0

    if verrouille:
        statut = (f"Délai de préavis dépassé pour l'échéance précédente : engagé jusqu'au "
                  f"{echeance.strftime('%d/%m/%Y')} (prochain préavis possible avant le {limite.strftime('%d/%m/%Y')})")
    elif urgence == 3:
        statut = f"Fenêtre de préavis imminente — échéance du bail le {echeance.strftime('%d/%m/%Y')}"
    else:
        statut = (f"Échéance du bail estimée au {echeance.strftime('%d/%m/%Y')} "
                  f"(préavis à donner avant le {limite.strftime('%d/%m/%Y')})")
    return {"prochaine_echeance_369": echeance, "date_limite_preavis": limite, "jours_avant_limite": jours,
            "urgence_369": urgence, "statut_bail": statut, "verrouille": verrouille}


# --- Score de potentiel (bail + finances, porté de PRSimmo) ----------------

PONDERATIONS = {"bail": 40 / 65, "finances": 25 / 65}   # voir note de version ci-dessus

# Courbe du critère bail : (mois avant l'échéance triennale estimée, score 0-1). Reprise telle
# quelle de PRSimmo (src/scoring/potentiel.py). Le cycle fait 36 mois : à mois=0-4, l'échéance
# arrive mais le délai de préavis (6 mois avant) est déjà dépassé -> score bas (congé raté, engagé
# jusqu'à cette échéance). La fenêtre s'ouvre ensuite (6-8 mois), reste à son maximum jusqu'à 22
# mois (fenêtre idéale pour démarcher : ni trop tôt, ni trop tard), puis redescend en approchant du
# prochain délai de préavis.
COURBE_BAIL = [(0, 0.25), (4, 0.25), (6, 0.85), (8, 1.0), (22, 1.0), (26, 0.70), (30, 0.50), (36, 0.40)]


def _date(valeur):
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except (TypeError, ValueError):
        return None


def _interpoler(points, x):
    """Interpolation linéaire par morceaux ; plate au-delà des extrémités."""
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def _ajouter_mois(d: date, mois: int) -> date:
    total = d.year * 12 + (d.month - 1) + mois
    annee, m = divmod(total, 12)
    m += 1
    jour = d.day
    while True:
        try:
            return date(annee, m, jour)
        except ValueError:
            jour -= 1   # 29-31 vers un mois plus court


def _prochaine_echeance_triennale(date_installation, aujourdhui: date):
    """Prochaine échéance (> aujourd'hui) d'un bail 3-6-9 supposé démarrer à la date
    d'installation. None si la date est inconnue ou dans le futur."""
    inst = _date(date_installation)
    if inst is None or inst > aujourdhui:
        return None
    k = 3
    while True:
        echeance = _ajouter_mois(inst, 12 * k)
        if echeance > aujourdhui:
            return echeance
        k += 3


def score_bail_potentiel(date_installation, aujourdhui: date | None = None):
    """(score 0-1 ou None si date inconnue, mois_avant_echeance ou None). Valeur chiffrée
    utilisée par score_opportunite() ; voir COURBE_BAIL ci-dessus. Les dates et le texte
    affichés à l'utilisateur viennent de bail_369(), pas de cette fonction."""
    aujourdhui = aujourdhui or dt.date.today()
    echeance = _prochaine_echeance_triennale(date_installation, aujourdhui)
    if echeance is None:
        return None, None
    mois = (echeance - aujourdhui).days / 30.4375
    return round(_interpoler(COURBE_BAIL, mois), 3), round(mois, 1)


# --- Score de potentiel (finances, porté de PRSimmo) ------------------------

SEUIL_EXPANSION = 0.15        # croissance du CA à partir de laquelle l'entreprise « s'étend »
SEUIL_CONTRACTION = -0.10     # baisse du CA à partir de laquelle elle « se contracte »
SEUIL_PERTE_MARGE = -0.05     # marge nette en dessous de laquelle on parle de pertes marquées
SCORE_EXPANSION = 0.80
SCORE_EXPANSION_FORTE = 0.90  # croissance >= 40 %
SCORE_CONTRACTION = 0.62
ANNEES_FINANCES_FRAICHES = 3  # au-delà, l'effet est réduit de moitié

DIRECTION_EXPANSION = "expansion"
DIRECTION_CONTRACTION = "contraction"
DIRECTION_STABLE = "stable"


def _nombre(valeur):
    try:
        if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)) or valeur == "":
            return None
        return float(valeur)
    except (TypeError, ValueError):
        return None


def historique_depuis_ligne(row: dict) -> list[dict]:
    """[{annee, ca, resultat}], le plus récent d'abord, à partir des colonnes déjà produites par
    enrichir_catalogue_finances.py / details.py (un seul exercice structuré, plus l'exercice
    précédent quand il est connu). Pas d'historique multi-année mis en cache dans ce projet
    (contrairement à PRSimmo, qui dispose d'un historique INPI complet) : au plus 2 exercices."""
    annee = _nombre(row.get("annee_finances"))
    ca = _nombre(row.get("chiffre_affaires"))
    resultat = _nombre(row.get("resultat_net"))
    ca_precedent = _nombre(row.get("chiffre_affaires_annee_precedente"))
    historique = []
    if annee is not None and (ca is not None or resultat is not None):
        historique.append({"annee": int(annee), "ca": ca, "resultat": resultat})
    if annee is not None and ca_precedent is not None:
        historique.append({"annee": int(annee) - 1, "ca": ca_precedent, "resultat": None})
    return historique


def analyser_finances(historique: list[dict], aujourdhui: date) -> dict:
    """{score (0-1 ou None), direction, croissance_ca, marge, annee, nb_exercices}. Repris de
    PRSimmo. Sans donnée : score None (=> neutre, jamais une pénalité)."""
    vide = {"score": None, "direction": None, "croissance_ca": None, "marge": None, "annee": None, "nb_exercices": 0}
    if not historique:
        return vide
    dernier = historique[0]
    precedent = historique[1] if len(historique) > 1 and 0 < dernier["annee"] - historique[1]["annee"] <= 2 else None
    croissance = None
    if precedent and dernier["ca"] and precedent["ca"] and dernier["ca"] > 0 and precedent["ca"] > 0:
        croissance = dernier["ca"] / precedent["ca"] - 1.0
    marge = None
    if dernier["resultat"] is not None and dernier["ca"] and dernier["ca"] > 0:
        marge = dernier["resultat"] / dernier["ca"]

    if croissance is not None and croissance >= SEUIL_EXPANSION:
        direction = DIRECTION_EXPANSION
        score = SCORE_EXPANSION_FORTE if croissance >= 0.40 else SCORE_EXPANSION
    elif (croissance is not None and croissance <= SEUIL_CONTRACTION) or (marge is not None and marge <= SEUIL_PERTE_MARGE) \
            or (marge is None and dernier["resultat"] is not None and dernier["resultat"] < 0):
        direction = DIRECTION_CONTRACTION
        score = SCORE_CONTRACTION
    else:
        direction = DIRECTION_STABLE
        score = NEUTRE

    if aujourdhui.year - dernier["annee"] > ANNEES_FINANCES_FRAICHES:
        score = NEUTRE + (score - NEUTRE) * 0.5
    return {
        "score": round(score, 3), "direction": direction,
        "croissance_ca": None if croissance is None else round(croissance, 4),
        "marge": None if marge is None else round(marge, 4),
        "annee": dernier["annee"], "nb_exercices": len(historique),
    }


_LIBELLE_DIRECTION = {
    DIRECTION_EXPANSION: "en expansion (CA en forte croissance)",
    DIRECTION_CONTRACTION: "en contraction (CA en baisse ou pertes marquées)",
    DIRECTION_STABLE: "stable (ni croissance ni baisse marquée)",
}


def score_opportunite(row: dict) -> dict:
    """row : dict-like avec au moins statut_administratif, date_installation_siege,
    chiffre_affaires, resultat_net, annee_finances, chiffre_affaires_annee_precedente.
    Renvoie {score (0-100 ou None), libelle, detail, score_fiabilite, criteres_disponibles,
    criteres_totaux}."""
    if str(row.get("statut_administratif") or "") == "Cessé":
        return {"score": None, "libelle": "Société cessée — non pertinent", "detail": [],
                "score_fiabilite": 0, "criteres_disponibles": 0, "criteres_totaux": 2}

    aujourdhui = dt.date.today()
    s_bail, mois = score_bail_potentiel(row.get("date_installation_siege"), aujourdhui)
    fin = analyser_finances(historique_depuis_ligne(row), aujourdhui)

    bail_v = NEUTRE if s_bail is None else s_bail
    fin_v = NEUTRE if fin["score"] is None else fin["score"]
    potentiel = PONDERATIONS["bail"] * bail_v + PONDERATIONS["finances"] * fin_v
    score = round(potentiel * 100)

    criteres_disponibles = (0 if s_bail is None else 1) + (0 if fin["score"] is None else 1)
    fiabilite = (0.0 if s_bail is None else 1.0) + (0.0 if fin["score"] is None else (1.0 if fin["nb_exercices"] >= 2 else 0.5))

    detail = []
    if s_bail is not None:
        detail.append((f"{round(PONDERATIONS['bail'] * bail_v * 100)} / {round(PONDERATIONS['bail'] * 100)}",
                        f"Bail : échéance triennale estimée dans {mois:.0f} mois (score {s_bail:.2f} sur 1)"))
    else:
        detail.append((f"{round(PONDERATIONS['bail'] * NEUTRE * 100)} / {round(PONDERATIONS['bail'] * 100)} (neutre)",
                        "Bail : date d'installation inconnue — composante neutre, pas de pénalité"))
    if fin["score"] is not None:
        croissance_txt = f" ({fin['croissance_ca']:+.0%} sur un an)" if fin["croissance_ca"] is not None else ""
        detail.append((f"{round(PONDERATIONS['finances'] * fin_v * 100)} / {round(PONDERATIONS['finances'] * 100)}",
                        f"Finances : {_LIBELLE_DIRECTION[fin['direction']]}{croissance_txt}"
                        + (" — exercice ancien, effet réduit de moitié" if aujourdhui.year - fin["annee"] > ANNEES_FINANCES_FRAICHES else "")))
    else:
        detail.append((f"{round(PONDERATIONS['finances'] * NEUTRE * 100)} / {round(PONDERATIONS['finances'] * 100)} (neutre)",
                        "Finances : aucun chiffre d'affaires connu — composante neutre, pas de pénalité"))

    if criteres_disponibles == 0:
        libelle = "Opportunité indéterminée (aucune donnée bail ni finances)"
    elif score >= 65:
        libelle = "Opportunité forte"
    elif score >= 45:
        libelle = "Opportunité moyenne"
    else:
        libelle = "Opportunité faible"

    return {"score": score, "libelle": libelle, "detail": detail, "score_fiabilite": round(fiabilite, 1),
            "criteres_disponibles": criteres_disponibles, "criteres_totaux": 2}


def appliquer(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute toutes les colonnes de bail/score au dataframe, ligne par ligne (quelques centaines
    de lignes : pas besoin de vectoriser). N'écrit jamais sur disque : calculé à chaque chargement."""
    bails = df["date_installation_siege"].apply(lambda d: bail_369(d if d else None))
    for champ in ("prochaine_echeance_369", "date_limite_preavis", "jours_avant_limite", "urgence_369",
                  "statut_bail", "verrouille"):
        df[champ] = [b[champ] for b in bails]
    df["urgence_libelle"] = df["urgence_369"].map(LIBELLE_URGENCE).fillna(STATUT_INCONNU)

    scores = []
    for i in df.index:
        r = {"statut_administratif": df.at[i, "statut_administratif"],
             "date_installation_siege": df.at[i, "date_installation_siege"] if df.at[i, "date_installation_siege"] else None,
             "chiffre_affaires": df.at[i, "chiffre_affaires"] if "chiffre_affaires" in df.columns else None,
             "resultat_net": df.at[i, "resultat_net"] if "resultat_net" in df.columns else None,
             "annee_finances": df.at[i, "annee_finances"] if "annee_finances" in df.columns else None,
             "chiffre_affaires_annee_precedente": df.at[i, "chiffre_affaires_annee_precedente"]
             if "chiffre_affaires_annee_precedente" in df.columns else None}
        scores.append(score_opportunite(r))
    df["score_opportunite"] = [s["score"] for s in scores]
    df["score_libelle"] = [s["libelle"] for s in scores]
    df["score_fiabilite"] = [s["score_fiabilite"] for s in scores]
    return df
