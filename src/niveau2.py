"""
NIVEAU 2 : sociétés détenues par les sociétés du niveau 1, lues dans le
« Tableau des filiales et participations » de leurs comptes annuels déposés au
Registre National des Entreprises (INPI).

C'est la même obligation légale que celle d'Eurazeo (art. R.123-197 du Code de
commerce) : chaque holding liste les sociétés qu'elle détient avec leur
pourcentage de capital. Le texte des comptes est produit par
niveau2_collecter.py ; ce module le lit.

Règles :
  - une ligne n'est retenue que si le document imprime un NOM et un POURCENTAGE
    sur la même ligne ; un nom sans pourcentage est gardé avec un pourcentage
    vide (jamais deviné) ;
  - la ligne brute est conservée pour que chaque résultat soit vérifiable ;
  - les formats varient d'un document à l'autre : un résultat est un CANDIDAT
    extrait des comptes, pas une donnée certifiée.
"""

from __future__ import annotations

import re
import unicodedata

# --- Reconnaissance d'une ligne « nom + chiffres + pourcentage » ------------
RE_POURCENT = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{1,2})?)\s?%")
RE_DATE = re.compile(r"\b\d{2}[/.]\d{2}[/.]\d{2,4}\b|\bcomptes?\b|\b20\d{2}\b", re.I)
RE_NUM = re.compile(r"^[-–(]?\d[\d.,]*%?\)?$|^[-–]$|^\*$|^n\.?m\.?$|^\d{2}[/.]\d{2}[/.]\d{2,4}$", re.I)
RE_SIRET = re.compile(r"SIR(?:ET|EN)\s*(?:N°|:)?\s*:?\s*((?:\d[\s ]?){9,14})", re.I)

# Lignes d'en-tête / de commentaire qui ne sont jamais une société
RE_BOILERPLATE = re.compile(
    r"renseignements|exc[eè]de|filiales?\b|participations?\b|quote|valeur|pr[eê]ts|cautions|dividendes|"
    r"observations|capital|capitaux|propres|r[ée]sultat|chiffre|en milliers|en-cours|brute|nette|hors taxe|"
    r"art\.|non reprises|inf[ée]rieur|taux|donn[ée]es|conversion|comptes (?:consolid|audit|non)|"
    r"docusign|page|rapport|exercice|société|soci[eé]t[eé] par|rcs|siège|total|^\(.*\)$|^[a-z]\.\s|^\d\.\s|"
    r"d[ée]tenu|hors\b|avals|immatricul|repr[ée]sent|social situ|sous le num[ée]ro|registre|financiers|"
    r"^siret|^siren|^\(\*\)|obligations|r[ée]sultats?\b|tableau|au \d{2}[/.]|d[ée]tient|aucune|sup[ée]rieure|"
    r"honoraires|au titre|cinq derniers|nombre d.actions|imp[oô]t|b[ée]n[ée]fice|dettes|effectif",
    re.I)

ADRESSE_MOTS = re.compile(
    r"\b(rue|avenue|bd|boulevard|blv|street|drive|road|place|square|quai|chemin|cours|all[ée]e|"
    r"suite|county|wilmington|new york|london|londres|luxembourg|amsterdam|paris|france|usa|etats-unis|"
    r"suede|sweden|gothenbourg|ny\b)", re.I)


def _sans_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normaliser_nom(nom: str) -> str:
    n = _sans_accents(nom or "").lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    n = re.sub(r"\blegendre holding\b", "lh", n)
    return re.sub(r"\s+", " ", n).strip()


def _pct(txt: str):
    return float(txt.replace(",", "."))


def _decouper_ligne(ligne: str):
    """'Nom 12 345,6 -3 210 44,19% 21 120 31/12/2024' -> (nom, pourcentage) ou None."""
    jetons = ligne.split()
    idx_pct = next((i for i, j in enumerate(jetons) if j.endswith("%") or RE_POURCENT.search(j)), None)
    if idx_pct is None:
        return None
    if jetons[idx_pct] == "%":  # "100 %" : le chiffre est le jeton précédent
        idx_pct -= 1
    m = RE_POURCENT.search(" ".join(jetons[idx_pct:idx_pct + 2]))
    if not m:
        return None
    debut = idx_pct
    while debut > 0 and RE_NUM.match(jetons[debut - 1]):
        debut -= 1
    # un nom entre parenthèses ne doit pas être coupé : "LHH 1 ( ex Legendre Holding 37)"
    nom_j = jetons[:debut]
    while " ".join(nom_j).count("(") > " ".join(nom_j).count(")") and debut < idx_pct:
        nom_j.append(jetons[debut])
        debut += 1
    # "Legendre Holding 72 55 082,11 ..." : le numéro fait partie du nom
    # (limité aux véhicules Legendre : « Nord Logistique Holding 1 200,0 » n'est pas « Holding 1 »)
    dernier = nom_j[-1].lower() if nom_j else ""
    vehicule_lh = dernier in ("lh", "lhh") or (dernier == "holding" and len(nom_j) >= 2 and nom_j[-2].lower() == "legendre")
    if vehicule_lh and debut < idx_pct and re.fullmatch(r"\d{1,3}", jetons[debut]):
        nom_j.append(jetons[debut])
        debut += 1
    nom = " ".join(nom_j).strip(" -–*")
    if len(re.findall(r"[A-Za-zÀ-ÿ]", nom)) < 3 or not (nom[0].isupper() or nom[0].isdigit()):
        return None
    nb_num = sum(1 for j in jetons[debut:] if RE_NUM.match(j) or "%" in j)
    if nb_num < 2:
        return None
    return nom, _pct(m.group(1))


def _decouper_sans_pct(ligne: str):
    """'Nom 5 872 5 872 31/12/2024' (pas de %) -> nom, sinon None."""
    jetons = ligne.split()
    debut = len(jetons)
    while debut > 0 and RE_NUM.match(jetons[debut - 1]):
        debut -= 1
    if len(jetons) - debut < 2 or debut == 0:
        return None
    nom = " ".join(jetons[:debut]).strip(" -–*")
    return nom if len(re.findall(r"[A-Za-zÀ-ÿ]", nom)) >= 4 and (nom[0].isupper() or nom[0].isdigit()) else None


def _fenetre(texte: str) -> list[tuple[int, str]]:
    """Lignes (n° de page, texte) situées dans/après chaque « Tableau des filiales et participations »."""
    lignes, page = [], 0
    for l in texte.split("\n"):
        mp = re.match(r"=== page (\d+) ===", l)
        if mp:
            page = int(mp.group(1))
            continue
        lignes.append((page, l.strip()))
    sorties, actif, compteur = [], False, 0
    for page, l in lignes:
        if re.search(r"Tableau des filiales et participations", l, re.I):
            actif, compteur = True, 0
            continue
        if actif:
            compteur += 1
            if compteur > 60 or re.search(r"rapport (?:du|des) commissaires?|honoraires|cinq derniers exercices|r[ée]sultats? financiers|^=== ", l, re.I):
                actif = False
                continue
            sorties.append((page, l))
    return sorties


RE_BRUIT_ADRESSE = re.compile(
    r"\bau\s+\d{2}[./]\d{2}[./]\d{2,4}\b|\baudit[ée]s?\b|\bcomptes?\b|\bnon encore\b|\bcl[ôo]tur[ée]s?\b|"
    r"\b1er exercice\b|\(\*\)", re.I)


def _adresse_suivante(lignes, i):
    adr, sir = [], ""
    for _, s_ in lignes[i + 1:i + 5]:
        if not s_ or (RE_POURCENT.search(s_) and _decouper_ligne(s_)):
            break
        m = RE_SIRET.search(s_)
        if m:
            sir = re.sub(r"\D", "", m.group(1))[:9]
            continue
        ressemble_adresse = bool(re.match(r"^\d+\s*[A-Za-z]?\s*[,.]?\s*[A-Za-zÀ-ÿ]", s_)) or bool(ADRESSE_MOTS.search(s_))
        if (re.match(r"^(B\.|[1-4]\.)", s_, re.I) or re.search(r"renseignements|gloabaux", s_, re.I)
                or _decouper_sans_pct(s_) or (RE_BOILERPLATE.search(s_) and not ressemble_adresse)):
            break
        propre = re.sub(r"\s{2,}", " ", RE_BRUIT_ADRESSE.sub(" ", s_)).strip(" ,")
        if propre:
            adr.append(propre)
    return ", ".join(adr), sir


def extraire_tableau(texte: str) -> list[dict]:
    """Candidats {nom, pourcentage, adresse, siren_imprime, page, ligne_brute} d'un compte annuel."""
    lignes = _fenetre(texte)
    trouves, vus = [], set()
    for i, (page, l) in enumerate(lignes):
        if not l:
            continue
        nom = pct = None
        brute, nom_colle = l, False
        if RE_POURCENT.search(l):
            r = _decouper_ligne(l)
            if r:
                nom, pct = r
        if nom is None and not RE_POURCENT.search(l):
            suivante = lignes[i + 1][1] if i + 1 < len(lignes) else ""
            # (a) nom seul, chiffres sur la ligne suivante : "EURAZEOPMEIIIGP" / "71000 100% 71000 ..."
            if (re.fullmatch(r"[A-Za-zÀ-ÿ0-9 .&'\-]{4,60}", l) and not RE_BOILERPLATE.search(l)
                    and l[0].isupper() and RE_POURCENT.search(suivante) and not RE_BOILERPLATE.search(suivante)):
                pr = _decouper_ligne("X X " + suivante) or None
                m = RE_POURCENT.search(suivante)
                if m:
                    nom, pct, brute, nom_colle = l, _pct(m.group(1)), l + " / " + suivante, True
            # (b) nom + chiffres sans % : "World Strides ... 5 872 5 872 31/12/2024"
            if nom is None and not RE_BOILERPLATE.search(l):
                n2 = _decouper_sans_pct(l)
                if n2:
                    nom, pct = n2, None
            # (c) nom seul suivi d'une adresse : "Vestiaire Collective / 33 blv ..."
            if (nom is None and not RE_BOILERPLATE.search(l) and l[0].isupper() and len(l) < 60
                    and not re.search(r"\d{3}", l) and ADRESSE_MOTS.search(suivante)):
                nom, pct = l.strip(" *"), None
        if not nom or RE_BOILERPLATE.search(nom) or re.search(r"\b\d{5}\b|\b[A-Z]{1,2}-\d{4}\b", nom):
            continue
        adresse_txt, sir = ("", "") if nom_colle else _adresse_suivante(lignes, i)
        cle = (normaliser_nom(nom), pct)
        if cle in vus:  # les comptes sont souvent imprimés deux fois (copie certifiée + rapport)
            continue
        vus.add(cle)
        trouves.append({"nom": nom, "pourcentage": pct, "adresse": adresse_txt, "siren_imprime": sir,
                        "page": page, "ligne_brute": brute[:200]})
    return trouves


# --- Repli : sociétés nommées dans les notes, sans pourcentage ---------------
_MOT = r"[A-ZÀ-Ý][A-Za-zÀ-ÿ0-9&'’\-\.]*"
_NOM_MOTS = rf"({_MOT}(?:\s+(?:{_MOT}|\([^)]{{2,40}}\))){{0,4}})"
RE_MENTIONS = [
    re.compile(r"participation\s+minoritaire\s+au\s+capital\s+(?:de|d['’])\s*" + _NOM_MOTS),
    re.compile(r"titres\s+de\s+la\s+soci[ée]t[ée]\s+" + _NOM_MOTS),
    re.compile(r"d[ée]pr[ée]ciation\s+(?:compl[ée]mentaire\s+)?(?:des?\s+)?titres\s+(?:de\s+la\s+soci[ée]t[ée]\s+)?" + _NOM_MOTS),
]
RE_SEUIL = re.compile(r"[^.\n]*ne\s+d[ée]tient\s+(?:pas\s+de|aucune)\s+participations?[^.\n]*", re.I)
_REFUS_MENTION = {"La", "Le", "Les", "Eurazeo", "Société", "LH", "Legendre", "Holding", "Paris", "Note"}


def extraire_mentions(texte: str) -> list[dict]:
    """Noms de sociétés cités dans les notes (« participation minoritaire au capital de Doctolib SAS »).

    Ce sont des mentions en texte libre : la part détenue n'y figure pas, et une
    société citée peut avoir été cédée depuis (« cession des titres de la société X »).
    """
    plat = re.sub(r"\(cid:\d+\)", " ", re.sub(r"[ \t]*\n[ \t]*", " ", texte))
    vus, sorties = set(), []
    for rx in RE_MENTIONS:
        for m in rx.finditer(plat):
            nom = m.group(1).strip(" .,;:")
            nom = re.sub(r"\s+(?:Pour|Note|Dans|Eurazeo|L|La|Le|Les|Et|Si|Qu)$", "", nom).strip(" .,;:")
            if nom.split()[0] in _REFUS_MENTION or len(nom) < 3 or normaliser_nom(nom) in vus:
                continue
            vus.add(normaliser_nom(nom))
            deb = max(0, m.start() - 70)
            sorties.append({"nom": nom, "pourcentage": None, "adresse": "", "siren_imprime": "", "page": "",
                            "ligne_brute": plat[deb:m.end() + 50][:220]})
    return sorties


def extraire_seuil(texte: str) -> str:
    """Phrase « ne détient pas de participation à plus de 10 % » si le document la contient."""
    m = RE_SEUIL.search(re.sub(r"[ \t]*\n[ \t]*", " ", texte))
    return m.group(0).strip()[:160] if m else ""
