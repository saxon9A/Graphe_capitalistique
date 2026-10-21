# Cartographie capitalistique — Eurazeo

Outil Python qui part d'un SIREN (Eurazeo par défaut), explore récursivement
ses participations capitalistiques via les API publiques françaises, puis
enrichit et exporte le résultat en CSV (Excel / Power BI).

## ⚠️ À lire avant de lancer quoi que ce soit : la question des clés API

Tu m'as demandé "de quoi as-tu besoin" pour les clés API. Voici l'état réel
des choses, vérifié sur la documentation officielle de chaque source
(octobre 2026) :

| Source | Clé nécessaire ? | Accessible à un particulier/société privée ? |
|---|---|---|
| **API Recherche d'Entreprises** | ❌ Aucune | ✅ Oui, totalement ouvert |
| **API Entreprise — liens capitalistiques (option B)** | ✅ Jeton JWT | ⚠️ **Non, en pratique** — voir ci-dessous |
| **Data INPI / RNE (option A)** | ✅ Compte gratuit (email+mot de passe) | ✅ Oui |
| **API Sirene INSEE** (optionnel) | ✅ Clé gratuite | ✅ Oui |

### Option B (API Entreprise) : quasiment inaccessible pour ce projet

J'ai vérifié la documentation officielle (`entreprise.api.gouv.fr`) : cette
API affiche elle-même, en toutes lettres, qu'elle fournit des données
**« pour les administrations »**. Concrètement :

- L'habilitation se demande sur [datapass.api.gouv.fr](https://datapass.api.gouv.fr/demandes/api-entreprise/nouveau),
  avec une **vérification d'éligibilité**.
- Chaque appel doit obligatoirement inclure un paramètre `recipient` qui doit
  être **le SIRET d'une organisation publique habilitée** (une mairie, une
  administration, un organisme exerçant une mission de service public...).
  La documentation est explicite : ce n'est pas ton SIRET personnel ou celui
  d'une société privée classique.
- Les CGU interdisent de redistribuer ou d'utiliser les données en dehors du
  cadre de la mission de service public déclarée.

**En clair : sauf si tu es toi-même une administration, une collectivité, ou
un éditeur travaillant pour le compte de l'une d'elles, tu ne pourras
probablement pas obtenir cette habilitation pour un projet personnel.** Le
code de ce projet implémente quand même cette option (fichier
`src/api_capitalistique.py`) exactement selon les specs officielles, au cas
où — mais ne perds pas de temps à demander l'habilitation avant d'avoir
confirmé ton éligibilité sur DataPass.

**C'est pour ça que le programme bascule automatiquement sur l'option A dès
que l'option B n'est pas configurée ou renvoie un refus d'accès**, exactement
comme le prévoyait ton cahier des charges.

### Option A (Data INPI / RNE) : c'est ta vraie option

1. Va sur **https://data.inpi.fr**, clique sur « Se connecter » → crée un
   compte gratuit (email + mot de passe), aucune vérification d'éligibilité.
2. Mets cet email/mot de passe dans ton fichier `.env` (`INPI_USERNAME`,
   `INPI_PASSWORD`).

⚠️ **Limite importante à connaître avant de te lancer** : le RNE expose
surtout *qui détient* l'entreprise interrogée (bénéficiaires effectifs,
associés), pas forcément *la liste des filiales qu'elle détient elle-même*
de façon aussi directe que le CERFA 2059G de l'option B. Le code sauvegarde
systématiquement la réponse brute de chaque entreprise dans
`sortie/inpi_brut/<siren>.json` : **la première chose à faire après ton
premier essai est d'ouvrir un ou deux de ces fichiers** pour voir ce que
l'API renvoie vraiment pour Eurazeo, et ajuster
`extraire_participations_best_effort()` dans `src/api_inpi.py` si la
structure diffère de ce qui est codé. C'est exactement l'étape 2 de la
méthode de développement que tu avais demandée.

### API Recherche d'Entreprises : rien à faire

Aucune clé. C'est elle qui fait tout l'enrichissement (statut, adresse, NAF,
effectif, dirigeants) par défaut.

### API Sirene INSEE : optionnelle, à activer seulement si besoin

Seulement si l'enrichissement par l'API Recherche d'Entreprises ne suffit
pas. Compte gratuit sur **https://portail-api.insee.fr**, créer une
application, s'abonner à « API Sirene », récupérer la clé d'intégration
(`INSEE_API_KEY`).

---

## Installation (Git Bash, Windows)

Depuis ton dossier `~/graphe_capitalistique/graphe_capitalistique` :

```bash
# 1. Dézippe le projet envoyé ici, à la racine de ton dossier actuel
unzip -o graphe_capitalistique.zip -d .

# 2. Crée un environnement virtuel Python
python -m venv venv
source venv/Scripts/activate      # Git Bash sous Windows (pas venv/bin/activate)

# 3. Installe les dépendances
pip install -r requirements.txt

# 4. Prépare ton fichier .env
cp .env.example .env
```

Ouvre ensuite `.env` dans un éditeur (`nano .env` ou VS Code) et renseigne au
minimum, **si tu obtiens un compte Data INPI** :

```
INPI_USERNAME=ton-email@exemple.fr
INPI_PASSWORD=ton-mot-de-passe
```

Le reste (`API_ENTREPRISE_*`) peut rester vide : le programme le détectera et
basculera automatiquement sur l'option A, en te l'indiquant clairement dans
la console et dans `sortie/journal_extraction.csv`.

## Lancer le programme

```bash
# Avec le SIREN d'Eurazeo par défaut
python graphe.py

# Ou en le précisant explicitement
python graphe.py 692030992

# En limitant la profondeur d'exploration (par défaut : 5)
python graphe.py 692030992 --profondeur-max 3
```

## ⚠️ Mise à jour après le premier test réel (16/10/2026)

Le premier essai avec un vrai compte INPI a confirmé que `GET /api/companies/{siren}`
**ne contient pas** les participations/filiales (seulement les dirigeants et
le commissaire aux comptes). Deux sources complémentaires ont donc été
ajoutées, **toutes les deux en mode « candidat à valider »** — aucune ne
réinjecte automatiquement une donnée non confirmée dans `participations.csv` :

1. **`src/deu_eurazeo.py`** — télécharge le Document d'Enregistrement
   Universel 2025 d'Eurazeo (dépôt réglementaire AMF officiel, ~440 pages),
   localise précisément la **Note 17 « Tableau des filiales et
   participations »** (pages ~346-349, l'équivalent exact du CERFA 2059G,
   Art. R.123-197 du Code de commerce) et en extrait un candidat par ligne :
   nom, **SIRET → SIREN quand la société est française**, % de détention,
   filiale ou participation. Sur l'édition 2025, ça donne **~47 candidats
   dont ~42 avec un SIREN déjà identifié** (les quelques sociétés
   luxembourgeoises/anglaises n'ont pas de SIRET, donc pas de SIREN
   automatique). Quand le SIREN est connu via le SIRET, il est pré-rempli
   dans la colonne `siren_confirme` de `candidats_a_verifier.csv` — ça reste
   un candidat à valider (colonne `valide`), mais tu n'as plus besoin de le
   rechercher toi-même.
2. **`src/api_inpi_actes.py`** — télécharge les actes légaux (statuts, PV...)
   d'une société via l'API INPI et scanne leur texte à la recherche de
   phrases mentionnant une participation. **Limite confirmée le 16/10/2026 :
   un compte Data INPI gratuit standard n'a pas les droits sur l'endpoint
   `/api/actes` (HTTP 403 "Vous n'avez pas les droits"), seulement sur
   `/api/companies`.** Ce n'est pas un bug : c'est une habilitation séparée
   qui n'est pas accordée par défaut à la création du compte. Le programme
   le détecte, l'affiche une fois clairement dans la console, et continue
   sans cette source — ce qui n'empêche pas le reste de fonctionner, et de
   toute façon le DEU Eurazeo (source 1) est plus fiable pour le niveau 1.
   Si tu veux un jour activer cette source, il faudrait demander une
   habilitation complémentaire auprès de l'INPI pour cet endpoint.

### Nouveau workflow en 2 temps

```bash
# 1. Génère les candidats (en plus de ce que B/A trouvent automatiquement)
python graphe.py 692030992

# 2. Ouvre sortie/candidats_a_verifier.csv dans Excel, vérifie chaque ligne
#    (colonne 'preuve'), mets "oui" dans la colonne 'valide' pour celles qui
#    sont correctes, précise 'siren_confirme' si tu le connais déjà.
#    Sauvegarde en gardant le format CSV.

# 3. Valide : ajoute les lignes "oui" à participations.csv ET relance une
#    recherche de candidats (actes INPI) pour les sociétés qui viennent
#    d'être confirmées, pour préparer le tour suivant.
python valider.py

# Répète les étapes 2-3 autant de fois que nécessaire pour descendre dans le graphe.
```

C'est un processus semi-automatique assumé : la donnée n'existe nulle part
dans un format 100% fiable et gratuit pour ce type de société (voir plus
haut), donc plutôt que d'inventer ou de faire confiance aveuglément à une
extraction de PDF, le programme te présente des candidats sourcés (page du
DEU ou phrase exacte de l'acte) et c'est toi qui tranches.

## Résultat

Tout est généré dans le dossier `sortie/` :

- **`entreprises_actives.csv`** — une ligne par entreprise active identifiée
  (SIREN, nom, statut, adresse, NAF, effectif, profondeur, chemin de
  détention).
- **`entreprises_inactives.csv`** — entreprises cessées ou dont le statut n'a
  pas pu être déterminé (jamais mélangées au fichier principal).
- **`participations.csv`** — une ligne par relation capitalistique, avec
  pourcentage direct, estimation théorique du pourcentage indirect,
  profondeur, chemin de détention, année de déclaration et source.
- **`journal_extraction.csv`** — journal technique complet (appels, erreurs,
  années testées, refus d'accès). Aucun secret n'y est jamais écrit.
- **`inpi_brut/<siren>.json`** — réponses brutes de Data INPI, pour
  vérification manuelle de la structure réelle des données.
- **`candidats_a_verifier.csv`** — candidats de participations trouvés dans
  le DEU Eurazeo et/ou les actes INPI, **à valider toi-même** (voir workflow
  ci-dessus) avant qu'ils rejoignent `participations.csv`.
- **`deu_eurazeo_2025.pdf`** et **`deu_bruts/`** — le PDF téléchargé et les
  tableaux bruts extraits des pages repérées, pour vérifier que l'extraction
  a bien trouvé la bonne section.
- **`inpi_actes/<siren>/`** — PDF des actes téléchargés + leurs candidats.

Tous les CSV sont en `;` et encodage `utf-8-sig`, directement ouvrables dans
Excel ou importables dans Power BI sans réglage particulier.

## Ce que le programme ne fait PAS (volontairement)

- Il n'invente jamais une participation, un pourcentage ou un statut quand la
  donnée est absente : le champ reste vide.
- Les pourcentages indirects sont explicitement marqués **« estimation
  théorique »** (colonne `pourcentage_indirect_estime_theorique`) : ce sont
  des produits de pourcentages directs le long d'UN chemin trouvé, pas des
  données juridiquement certifiées — en présence de détentions multiples ou
  de participations croisées, la réalité peut être différente.
- Il ne présente jamais le graphe comme exhaustif : regarde le journal
  d'extraction pour connaître les années manquantes, les SIREN introuvables
  et les relations qui restent à confirmer.

## Architecture du code

```
graphe.py                          # point d'entrée (CLI) : exploration + candidats
valider.py                         # valide les candidats et les promeut dans participations.csv
src/
  config.py                        # lecture du .env, constantes
  logger.py                        # journal_extraction.csv
  api_capitalistique.py            # Option B : API Entreprise (DGFIP)
  api_inpi.py                      # Option A : Data INPI / RNE (dirigeants, pas de participations)
  api_inpi_actes.py                # Documents légaux INPI -> candidats de participations
  deu_eurazeo.py                   # Document d'Enregistrement Universel Eurazeo -> candidats
  candidats.py                     # Fusionne/écrit candidats_a_verifier.csv
  api_recherche_entreprises.py     # Enrichissement + résolution nom -> SIREN (sans clé)
  api_sirene.py                    # Enrichissement optionnel (INSEE)
  normalize.py                     # Mise en forme commune des relations
  explorer.py                      # Exploration récursive, cycles, estimation indirecte
  enrich.py                        # Enrichissement administratif
  export.py                        # Écriture des CSV
```

## Prochaine étape recommandée

1. `python graphe.py 692030992`
2. Ouvre `sortie/candidats_a_verifier.csv` et vérifie les premières lignes
   (celles venant du DEU en particulier devraient être assez fiables, c'est
   un document audité). Marque `valide=oui` sur celles qui sont correctes.
3. `python valider.py` — ça les ajoute à `participations.csv` et prépare le
   tour suivant (candidats de niveau 2, via les actes INPI des filiales qui
   viennent d'être confirmées).
4. Répète 2-3 pour descendre dans le graphe aussi profondément que tu veux.

---

## Dashboard (adresses, effectifs, carte) — ajouté le 18/10/2026

### 1. Récupérer les infos détaillées de chaque société

```bash
cd ~/graphe_capitalistique/graphe_capitalistique
source venv/Scripts/activate
python enrichir_details.py
```

Produit `sortie/entreprises_detaillees.csv` (séparateur `;`, ouvrable dans Excel / Power BI) :
adresse exacte + GPS, tranche d'effectif, NAF, forme juridique, date de création, statut,
dirigeants, établissements, derniers comptes publiés. Les réponses brutes de l'API sont gardées
dans `sortie/sirene_brut/<siren>.json`. Le CSV est aussi copié dans `dashboard/data/`.

Sources : API Recherche d'Entreprises (Sirene INSEE + RNE INPI, sans clé) pour les sociétés
françaises ; adresse imprimée dans le DEU 2025 pour les 5 sociétés étrangères (pas de fiche
Sirene). Un champ absent de la source reste vide, rien n'est inventé. Les positions des sociétés
étrangères sont au centre-ville (`geo_precision = ville`), pas à l'adresse.

### 2. Lancer le dashboard

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

Pages : Accueil · Le graphe · La carte · Le contrôle · Les portefeuilles (niveaux 2+) · Le profil · L'annuaire · Fiche société.
Filtres communs (barre latérale, y compris pour la liste de la Fiche société) : recherche, niveaux, zone (Paris / France hors Paris / Étranger / Non localisée),
type de relation, détention minimale, effectif.

Pour Streamlit Cloud : pousser le projet sur GitHub, point d'entrée `dashboard/app.py`,
et inclure `dashboard/data/entreprises_detaillees.csv`.

### Limite à connaître (niveau 1)
Le niveau 1 (participations directes d'Eurazeo, Note 17 du DEU) vient d'un document audité.
Pour aller plus bas, voir la section suivante.

---

## Niveau 2 : les sociétés détenues par les holdings — ajouté le 18/10/2026

Les actes INPI sont refusés (403), mais les **comptes annuels** des holdings sont accessibles.
Ils contiennent le « tableau des filiales et participations » (art. R.123-197) : nom, % détenu,
parfois adresse et SIREN. On les lit.

```bash
cd ~/graphe_capitalistique/graphe_capitalistique
source venv/Scripts/activate
python niveau2_collecter.py     # télécharge les comptes (déjà fait, relançable)
python niveau2_extraire.py      # hors ligne : lit les PDF -> sortie/niveau2_candidats.csv
python niveau2_enrichir.py      # réseau : adresses, GPS, effectifs -> sortie/entreprises_niveau2.csv
streamlit run dashboard/app.py
```

- `niveau2_candidats.csv` : une ligne par société trouvée, avec `ligne_brute` (la ligne telle
  qu'imprimée dans le PDF). **À relire** : c'est de l'extraction automatique de PDF. Mettre
  `valide=non` écarte une ligne.
- `entreprises_niveau2.csv` : même colonnes que le niveau 1, plus `part_economique_eurazeo`
  (calcul : % de la holding dans la société × % d'Eurazeo dans la holding) et `verification`.
- Une société n'est localisée que si son nom (ou son SIREN imprimé) correspond sans ambiguïté
  au registre. Sinon : « Non localisée », jamais d'adresse devinée.

Limites à connaître :
- Le % est celui des comptes de la holding (souvent exercice 2024 ou 2025), pas une donnée en temps réel.
- Plusieurs holdings (LH Payfit, LH Doctolib…) ne détiennent que des parts minoritaires (< 10 %, ~7 %).
- Certaines sociétés ne sont citées que dans les notes, sans %, et ont pu être cédées depuis.
- Les véhicules du fonds EGI sont mis de côté dans `sortie/niveau2_vehicules_egi.csv` (noms illisibles dans le PDF).
- Quelques comptes sont vides ou scannés (ex. Kurma Partners) : rien n'en est extrait.
- La part indirecte est un calcul, pas une valeur publiée.

## Niveau 3 et suivants : descendre plus bas — ajouté le 19/10/2026

Une seule commande par niveau (collecte des comptes, lecture, enrichissement) :

```bash
python niveau2_extraire.py     # (re)lit les comptes du niveau 1 ; écrit aussi les liens entre sociétés déjà connues
python descendre.py 3          # niveau 3 : comptes des holdings françaises du niveau 2 (réseau INPI + Sirene)
python descendre.py 4          # puis niveau 4, etc.
python descendre.py 3 --tous   # explore aussi les sociétés qui ne sont pas des holdings
python descendre.py 3 --etape extraire   # une seule étape (collecter | extraire | enrichir)
```

Ce qui est exploré : seulement les sociétés **françaises** (SIREN connu, donc comptes consultables),
classées holding, fonds ou siège social (NAF 64.20Z, 64.30Z, 66.30Z, 70.10Z), non cessées. Le fichier
`sortie/niveauN_parents.csv` dit, société par société, pourquoi elle a été explorée ou non
(étrangère, pas une holding, SIREN introuvable...).

Produit : `niveauN_candidats.csv` (à relire : `ligne_brute` montre le texte du PDF ; `valide=non` écarte une
ligne et est conservé à la ré-extraction), `entreprises_niveauN.csv` (copié dans `dashboard/data/`),
`liens_internes_niveauN.csv` (liens vers des sociétés déjà dans le graphe : ex. le véhicule Carryco qui détient
12 % d'une holding Legendre déjà au niveau 1).

Limites : la descente s'arrête aux sociétés étrangères (LLC américaines, véhicules luxembourgeois...) et aux sociétés
sans SIREN retrouvé : leurs comptes ne sont pas consultables ici. Part indirecte d'Eurazeo = calcul (part dans la
société × somme des parts indirectes connues de la société qui la détient) ; si un chemin de détention n'est pas
dans les documents lus, la vraie part est plus grande.

## Le graphe interactif

Page « Le graphe » du dashboard : réseau déplaçable (glisser un nœud, molette pour zoomer, clic pour la
chaîne de détention jusqu'à Eurazeo). Boutons de filtre dans la page : zone (Paris, France hors Paris,
Étranger, Non localisée), niveaux, « Chemin jusqu'à Eurazeo » (garde en pâle les holdings qui relient une
société affichée à Eurazeo), parts sur les liens, disposition libre ou en anneaux, recherche d'une société.
Les filtres de la colonne de gauche s'appliquent aussi. Bouton de téléchargement des liens (CSV pour Excel / Power BI).
La bibliothèque vis-network est incluse dans `dashboard/assets/` : aucun CDN nécessaire.

## Sources web : cessions repérées — ajouté le 19/10/2026

`dashboard/data/evenements_web.csv` liste des cessions trouvées dans les communiqués d'Eurazeo et la presse
financière (Ex Nihilo, Aroma-Zone, Asmodée, CPK, Fermax), avec pour chaque ligne le lien, la date de la source, un
extrait et la date de consultation. Le dashboard les rapproche des sociétés **par le nom** (colonne `cles`) :
bord rouge dans le graphe, bloc « Sources web » sur la fiche, colonne « Cession (source web) » dans l'annuaire,
page « Les cessions ». Ce rapprochement est à vérifier ; la liste n'est pas exhaustive (l'absence d'une société ne
veut pas dire qu'elle n'a pas été cédée). Pour ajouter une source : ajouter une ligne au CSV.

La page « Les sources web » liste aussi les participations citées par Eurazeo (`dashboard/data/portefeuille_web.csv` : document
de référence 2025, résultats annuels 2025 et du 1er semestre 2026), avec la mention « dans le graphe » ou non. Eurazeo
**ne publie pas la part détenue** dans chaque société (portefeuille de plus de 70 sociétés, détenues surtout via des fonds avec
d'autres investisseurs) : ces lignes n'ont donc aucun pourcentage. Eurazeo étant une « entité d'investissement » (IFRS 10), son
périmètre de consolidation ne contient que ses sociétés de gestion (Eurazeo Infrastructure Partners 66,67 %, IM Global Partner
45,46 % d'intérêt, etc.), pas ses sociétés opérationnelles.

## Filtrer les holdings et sociétés de gestion de fonds — ajouté le 20/10/2026

Case à cocher dans la colonne de gauche (« Masquer les holdings et sociétés de gestion de fonds ») : retire
toutes les sociétés dont le code NAF est 64.20Z (holding), 64.30Z (fonds de placement), 66.30Z (gestion de
fonds) ou 70.10Z (siège social) — le même code que celui déjà utilisé page d'accueil et dans le graphe pour les
distinguer visuellement. S'applique à tout le dashboard (annuaire, fiche, graphe...). Limite : une société
étrangère sans fiche Sirene n'a pas de code NAF et n'est donc jamais retirée par ce filtre, même si c'est
probablement aussi une holding (ex. « Eurazeo UK Limited »).

## Le catalogue officiel d'Eurazeo (269 sociétés) — ajouté le 20/10/2026

En plus des niveaux 1, 2, 3... (chaîne de détention lue dans les comptes annuels déposés à l'INPI), le dashboard
peut afficher le catalogue que le site institutionnel d'Eurazeo donne lui-même de ses investissements, passés et
présents : page « Nos investissements » (`eurazeo.com/fr/investissements`), 269 sociétés au 20/10/2026.

**Pourquoi un fichier à part, et pas simplement « aller plus loin » dans la descente par niveau.** On a vérifié
avec les vraies données (niveaux 1 à 3) : sur les 269 sociétés du catalogue, seules 2 étaient déjà trouvées par
la chaîne de détention INPI (PayFit et Vestiaire Collective, toutes deux au niveau 2, directement sous leur
véhicule « LH »). La raison est structurelle, pas une histoire de profondeur insuffisante :
- Les sociétés opérationnelles, quand elles apparaissent dans les comptes d'une holding française, apparaissent
  en général **1 à 2 niveaux sous leur véhicule Legendre Holding/Carryco** — pas beaucoup plus bas — puis arrêtent
  la chaîne : ce ne sont pas des holdings, donc `descendre.py` ne cherche pas en dessous (c'est voulu : elles
  n'ont pas de « filiales » à elles).
- La plupart des sociétés du catalogue (surtout Growth, Venture, Elevate) sont détenues via des véhicules
  **étrangers** (Luxembourg, Pays-Bas...) ou des fonds qui ne sont pas des sociétés françaises avec comptes
  déposés à l'INPI : la chaîne s'arrête avant même d'atteindre la société, quel que soit le niveau atteint.
  Aller au niveau 8 n'y changerait rien.
- Le tableau des filiales et participations (Note 17) ne liste que les participations au-delà d'un seuil : une
  prise de participation minoritaire récente (ex. Dexory, Cognigy) peut n'apparaître dans aucun compte annuel
  déposé, même en descendant très bas.

**Ce que fait `catalogue_eurazeo.py` à la place.** Plutôt que de chercher une chaîne de détention qui n'existe
pas dans les comptes INPI, le script importe un export du catalogue du site (scrapé puis rapproché d'une fiche
Sirene par similarité de nom — fichier fourni en entrée, pas collecté automatiquement ici) :

```bash
python catalogue_eurazeo.py sortie/eurazeo_portefeuille_enrichi.csv
```

Produit `sortie/portefeuille_eurazeo_catalogue.csv` (copié dans `dashboard/data/`). Dans le dashboard :
- Page « Les sources web » : tableau complet, filtrable (statut, absentes du graphe, recherche).
- Page « Le graphe » : case à cocher « Catalogue eurazeo.com », qui ajoute les sociétés absentes en losanges
  gris reliés à Eurazeo par un trait pointillé — un **lien d'affichage, pas une chaîne de détention vérifiée**
  (aucun pourcentage, aucun véhicule intermédiaire connu).

**⚠️ Le rapprochement SIREN n'est jamais garanti, même à 100 % de similarité.** Exemple vérifié en construisant
cette fonctionnalité : « Mapal » (Eurazeo, Madrid, Espagne) et « Planet » (Eurazeo, ex-Fintrax, paiements) ont
tous deux été rapprochés à 100 % de similarité de nom à deux petites sociétés françaises sans rapport (une
adresse en Allemagne pour l'une, en Vendée pour l'autre) : la similarité de nom seule ne suffit pas quand le nom
est court ou générique. Le SIREN, la commune et l'effectif affichés pour ce catalogue sont donc **toujours**
présentés comme « à vérifier », quel que soit le score de rapprochement — jamais comme une donnée confirmée. Pour
une société du catalogue, le plus fiable reste le site officiel de la société (lien dans le panneau de détail du
graphe) plutôt que le SIREN rapproché.

## Le catalogue partout dans le dashboard, géocodage et export filtré — ajouté le 20/10/2026

Les 269 sociétés du catalogue (celles absentes du graphe) apparaissent maintenant comme une sélection à part
entière sur **toutes** les pages du dashboard, pas seulement sur Le graphe et Les sources web :
- Dans la colonne de gauche, le filtre **Niveaux** gagne une option **« Catalogue »**, en plus de « Niveau 1 »,
  « Niveau 2 »... Elle est cochée par défaut, avec les autres.
- Le filtre **« Masquer les holdings »** ne les retire jamais : on ne connaît pas leur code NAF (donc pas si
  c'est une holding), et on préfère les laisser visibles plutôt que de deviner.
- **L'annuaire** et **Fiche société** les listent comme les autres sociétés (niveau affiché : « Catalogue »,
  SIREN/identifiant toujours vide par choix — voir plus haut : seule la colonne « Identification » cite le SIREN
  candidat, en toutes lettres, jamais comme un identifiant confirmé).
- **Le profil** les inclut dans les statistiques (effectif, forme juridique...), avec « Non renseigné » pour tout
  ce qu'on ne sait pas (NAF, forme juridique) plutôt qu'une valeur inventée.
- **Accueil, Le contrôle et Les portefeuilles** ne les montrent PAS : ces pages portent spécifiquement sur la part
  du capital détenue (niveau 1 direct, ou niveau 2+ via une holding identifiée), une donnée que le catalogue n'a
  justement pas. Les y ajouter avec des cases vides aurait affaibli ces pages pour rien.
- **Le graphe** reste inchangé (case à cocher dédiée, déjà en place depuis la section précédente) : le catalogue
  y est géré séparément pour ne jamais créer de nœud en double.

**Géocodage (`geocoder_catalogue.py`), pour les faire apparaître sur La carte.** Le catalogue n'a pas de
coordonnées GPS à l'import. Un nouveau script les ajoute, pour les sociétés qui ont un SIREN rapproché, en
réutilisant l'API Recherche d'Entreprises déjà utilisée partout ailleurs dans ce projet (aucune nouvelle clé) :

```bash
python catalogue_eurazeo.py sortie/eurazeo_portefeuille_enrichi.csv   # si pas déjà fait
python geocoder_catalogue.py
```

Écrit les colonnes `latitude`, `longitude`, `geo_precision` dans `sortie/portefeuille_eurazeo_catalogue.csv`
(copié dans `dashboard/data/`). Les sociétés sans SIREN rapproché (environ 50 sur 269) restent sans coordonnées :
rien n'est placé au hasard. Relance ce script après chaque nouveau `catalogue_eurazeo.py` (un nouveau scrape
peut rapprocher de nouveaux SIREN).

**Clic sur la carte -> fiche société.** Sur **La carte**, cliquer un point ouvre directement la fiche d'une des
sociétés à cette adresse (la première par ordre alphabétique quand plusieurs sociétés partagent la même adresse
— les autres restent listées dans la fiche, section « autres sociétés à la même adresse »). Ça marche aussi bien
pour les sociétés du graphe que pour celles du catalogue, une fois géocodées.

**Export CSV filtré sur Fiche société.** Le bouton « Télécharger la sélection (CSV) », déjà présent sur
L'annuaire, existe maintenant aussi sur **Fiche société**, à côté du sélecteur de société. Il télécharge
exactement la liste qui correspond aux filtres actifs dans la colonne de gauche (zone, niveaux, masquer les
holdings, recherche...), avec toutes leurs colonnes — par exemple : zone « Paris », case « Masquer les holdings »
cochée -> un CSV de toutes les sociétés parisiennes non-holding de la sélection actuelle.

## Finances, effectif complet, et score d'opportunité « déménagement » — ajouté le 21/10/2026

Trois ajouts, pensés pour un usage de prospection immobilière (quelles sociétés du portefeuille seraient
disposées à chercher de nouveaux locaux) : plus de sociétés avec un effectif connu, le chiffre d'affaires et le
résultat net quand ils sont disponibles, et une estimation du cycle de bail commercial 3/6/9 avec un score
indicatif.

**1. Pourquoi l'effectif manquait pour la plupart des sociétés du catalogue.** Le catalogue (269 sociétés) ne
passait jusqu'ici que par le géocodage (`geocoder_catalogue.py`), jamais par l'enrichissement complet utilisé
pour les sociétés du graphe (niveaux 1 à 3). Deux nouveaux scripts corrigent ça, en réutilisant la même source
gratuite (API Recherche d'Entreprises, déjà utilisée partout dans ce projet, aucune clé) :

```bash
python completer_dates_installation.py     # complète entreprises_detaillees.csv + entreprises_niveauN.csv
python enrichir_catalogue_finances.py      # complète le catalogue (effectif, finances, date d'installation)
```

Relançables sans risque (ils ne retéléchargent/rappellent l'API que pour ce qui manque encore). Pense à relancer
`streamlit run dashboard/app.py` (ou juste rafraîchir la page) ensuite.

**2. Chiffre d'affaires et résultat net, en deux temps.** L'API Recherche d'Entreprises expose un champ
`finances` structuré (CA, résultat net, par exercice) quand la société l'a déposé au greffe sans opter pour la
confidentialité : c'est la source **Tier 1**, déjà utilisée pour les niveaux 1 à 3 (colonnes `chiffre_affaires`,
`resultat_net`, `annee_finances` dans `entreprises_detaillees.csv`), étendue ici au catalogue. Pour les sociétés
sans CA structuré, `enrichir_catalogue_finances.py` tente un **Tier 2** : télécharger (ou réutiliser, s'il a déjà
été récupéré pour un autre niveau) le dernier compte annuel PUBLIC déposé au RNE via tes identifiants INPI
(`.env`), puis chercher le chiffre d'affaires et le résultat net dans le texte du bilan par mots-clés
(`src/comptes.py`). **Ce n'est jamais garanti** : un bilan est un document en texte libre, la mise en page varie
d'un cabinet comptable à l'autre. Chaque valeur du Tier 2 est marquée « estimé, à vérifier » dans le dashboard et
accompagnée de la ligne brute exacte qui l'a produite — jamais mélangée aux colonnes structurées du Tier 1. Sans
`INPI_USERNAME`/`INPI_PASSWORD` dans `.env`, le Tier 2 est simplement ignoré (le script le dit).

**3. Cycle de bail commercial 3/6/9 et score d'opportunité (`dashboard/lib/scoring.py`).** Un bail commercial
classique dure 9 ans, mais le locataire peut le résilier à chaque échéance triennale (3, 6, 9 ans...), avec un
préavis de 6 mois (art. L145-4 et L145-9 du Code de commerce). À partir de `date_installation_siege` (date
d'installation à l'adresse ACTUELLE du siège — différente de la date de création de la société — récupérée via
le même Tier 1), le dashboard calcule :
- la prochaine échéance triennale et sa date limite de préavis (échéance − 6 mois) ;
- un statut : fenêtre de préavis imminente (moins de 3 mois avant la limite), échéance dans moins d'un an, dans 1
  à 2 ans, ou au-delà — et un cas particulier géré explicitement : si la date limite d'une échéance vient d'être
  dépassée, la société est considérée **verrouillée** jusqu'à l'échéance suivante (elle n'a plus le droit de
  résilier à celle qui vient de passer), le calcul bascule automatiquement dessus plutôt que d'afficher à tort
  une urgence qui n'existe plus.
- **Simplification assumée et documentée** : on suppose que le cycle de 3 ans continue indéfiniment depuis la
  date d'installation. En réalité, un nouveau bail (avec une nouvelle date de départ inconnue) a pu être signé
  après la 9e année : l'échéance affichée est une **estimation**, jamais une date de bail réelle.
- **Si la date d'installation est inconnue** (société étrangère, donnée Sirene manquante...), rien n'est calculé
  : « Échéance inconnue », jamais remplacée par une date approchante (ex. date de création de la société) — choix
  explicite, pour ne jamais faire croire à une précision qu'on n'a pas.

**Nouveau filtre.** La colonne de gauche gagne un filtre « Statut du bail (estimation 3/6/9) », sur le même
principe que les filtres Niveaux/Zone existants.

### Score d'opportunité v2 — porté du projet PRSimmo (toujours le 21/10/2026)

À la demande explicite de l'utilisateur (« je veux la même chose »), le calcul du score d'opportunité a été
aligné sur celui de son projet **PRSimmo** (github.com/saxon9A/PRSimmo, dépôt privé, lu via le navigateur, en
**lecture seule** — aucun fichier de ce dépôt n'a été modifié). Ce qui change par rapport à la toute première
version (décrite dans les points ci-dessus, aujourd'hui dépassés sur le détail du score) :

- **Le score est désormais sur 100**, combinant deux critères pondérés : **bail (~61,5 %)** et **finances
  (~38,5 %)**. PRSimmo pondère en réalité trois critères (bail 40 % / événements BODACC+presse 35 % / finances
  25 %) ; le critère « événements » n'est pas porté ici car ce projet ne collecte aucune donnée BODACC ni presse
  — décision explicite de l'utilisateur plutôt que de le simuler avec un signal plus pauvre (`etat_web`, les
  mouvements capitalistiques Eurazeo déjà suivis par ailleurs). Son poids est réparti sur les deux critères
  restants.
- **Bail** : le palier à 4 niveaux (+40/+25/+10/+0 selon la date limite de préavis) est remplacé par une **courbe
  continue** (interpolation) sur les 36 mois du cycle triennal — creuse juste après un congé raté, maximale entre
  8 et 22 mois avant l'échéance (fenêtre idéale pour démarcher), puis redescend. Les dates et le statut affichés
  sur la fiche société (échéance, date limite, « Échéance inconnue », verrouillage) restent calculés exactement
  comme avant : seul le nombre utilisé dans le score a changé.
- **Finances = direction, pas « santé »** : une forte baisse du chiffre d'affaires ou des pertes marquées comptent
  désormais **positivement** dans le score (signal de réduction de surface possible), au même titre qu'une forte
  croissance (signal d'agrandissement) — plus seulement la croissance comme avant.
- **Donnée manquante = toujours neutre (50 % de la pondération du critère), jamais une pénalité.** Un
  **score de fiabilité (0 à 2)** indique séparément combien de critères (bail, finances) reposent sur une
  vraie donnée, affiché juste à côté du score sur la fiche société.
- **Le bonus de taille (effectif) est supprimé** du score : PRSimmo ne score pas la taille comme critère
  d'opportunité (l'effectif n'y sert qu'à estimer une fourchette de m², fonctionnalité non portée ici, faute de
  filtre « surface recherchée » dans ce dashboard) — décision explicite de l'utilisateur.

Une société cessée n'a toujours pas de score. **Ce n'est toujours jamais une prédiction fiable**, seulement un
faisceau d'indices pondérés, toujours montré en détail (expander « Détail du calcul ») sur la fiche société —
jamais un chiffre seul sans explication. Détail technique dans `dashboard/lib/scoring.py` (docstring en tête de
fichier).

## Dashboard resserré pour la prospection, nettoyage des données, préparation GitHub/Streamlit — 21/10/2026

### Pages

Le dashboard passe de 9 à 5 pages, pour se concentrer sur la recherche et le scoring (demande
explicite) :
- **Gardées** : L'annuaire (devient la page d'ouverture), Fiche société, La carte, Le graphe, Les
  portefeuilles.
- **Retirées** (fichiers supprimés, `dashboard/vues/accueil.py`, `controle.py`, `profil.py`,
  `cessions.py`) : Accueil et Le contrôle (statistiques de détention, sans lien avec la prospection
  immobilière — demande explicite), Les sources web (page autonome ; l'info qu'elle montrait reste
  affichée sur chaque fiche société, rien n'est perdu), Le profil (statistiques agrégées redondantes
  avec les colonnes de L'annuaire). Les fonctions de graphique devenues inutilisées
  (`charts.controle`, `charts.barres_v`, `charts.barres_h`) ont été retirées de `dashboard/lib/charts.py`.

### Recherche et scoring : nouveaux filtres et visualisation

- **Filtre « Score d'opportunité minimum »** (curseur, colonne de gauche) : ne garde que les
  sociétés au-dessus d'un seuil de score. À 0 (par défaut), aucune société n'est masquée — y
  compris les sociétés cessées ou sans score.
- **« Masquer les holdings » cochée par défaut** (c'était décoché) : ces véhicules (voir plus bas)
  n'ont pas de besoin de bureaux propre et faussaient le haut du classement.
- **L'annuaire est trié par score décroissant par défaut** (c'était par part détenue), avec un
  histogramme de la répartition des scores de la sélection filtrée en haut de page, et les colonnes
  score / statut du bail / fiabilité ramenées en tête de tableau.

### Un vrai problème de données trouvé et corrigé : les véhicules de fonds faussaient le score

En testant le score sur les données réelles, les premières places du classement étaient occupées
par des véhicules de portage/gestion de fonds d'Eurazeo (CARRYCO, LEGENDRE HOLDING, EURAZEO CAPITAL
V...) plutôt que par de vraies sociétés opérationnelles. Cause : ces véhicules déclarent un chiffre
d'affaires à 0 avec des pertes importantes (normal pour ce type de structure, rien d'anormal dans la
donnée elle-même), ce que le critère finances interprète comme un signal de « contraction » — fort
pour le score, mais sans aucun rapport avec un vrai besoin de bureaux. `HOLDING_NAF` (dans
`dashboard/lib/data.py`) ne couvrait pas le code NAF 66.19B (« Autres activités auxiliaires de
services financiers »), porté par l'un de ces véhicules (EURAZEO CAPITAL V - BS) : ajouté. Combiné à
« Masquer les holdings » cochée par défaut, ces véhicules n'apparaissent plus en tête.

### ⚠️ Deux points relevés, pas corrigés — à vérifier ou trancher

Honnêteté d'abord : je n'ai pas inventé de correctif pour ce qui suit, faute de pouvoir vérifier
moi-même (l'API utilisée n'est pas joignable depuis mes outils, ni en bac à sable ni via le pont vers
ta machine — seul ton propre terminal y a accès).

1. **`chiffre_affaires_annee_precedente` et `croissance_ca_pct` sont vides à 100 %**, sur toutes les
   sociétés, tous fichiers confondus (niveaux 1 à 3 et catalogue) — alors que le code
   (`src/details.py::_deux_dernieres_finances`) est censé les remplir dès que l'API renvoie deux
   exercices. Impossible à distinguer, sans accès à l'API en direct, entre deux explications : (a)
   l'API ne renvoie quasiment jamais deux exercices pour ce portefeuille (limite de la source, pas
   un bug) ou (b) un vrai bug d'extraction. **Pour trancher**, lance ceci dans TON terminal (accès
   internet réel) :
   ```bash
   python -c "from src.api_recherche_entreprises import get_entreprise_par_siren; import json; print(json.dumps(get_entreprise_par_siren('692030992').get('finances'), indent=2, ensure_ascii=False))"
   ```
   Si le `finances` renvoyé n'a qu'une seule année : c'est la source qui limite, rien à corriger.
   S'il en a deux ou plus : dis-le-moi, il y a bien un bug à corriger dans `_deux_dernieres_finances`.
   Tant que ce n'est pas tranché, le score financier perd un peu de nuance (pas de croissance
   calculable), mais reste correct (la marge et les pertes restent prises en compte).

2. **`entreprises_niveau2.csv` cite « ERES TOPCO » (SIREN 928387240) deux fois**, avec deux parts
   détenues différentes (32,97 % et 26,4 %), toutes les deux lues dans le même tableau des filiales
   et participations d'EURAZEO CAPITAL V - BS, exercice 2025. Ça peut être deux lignes réellement
   distinctes du tableau (deux instruments, deux classes de titres...) ou une erreur de lecture du
   PDF. Je n'ai pas fusionné ni supprimé une des deux lignes : vérifie le compte annuel original si
   tu veux trancher (`sortie/inpi_comptes/` ou relance `niveau2_extraire.py` en regardant le détail).

3. **Point méthodologique, pas une erreur** : le critère finances (« direction, pas santé », porté de
   PRSimmo) traite toute perte nette comme un signal de contraction (score 0,62, positif pour le
   score). Pour un portefeuille growth equity/VC comme celui d'Eurazeo, beaucoup de sociétés en forte
   croissance sont volontairement en perte pendant leur phase de scale-up (elles ont donc plutôt
   besoin de PLUS de surface, pas moins) : ce critère peut donc sur-noter des sociétés qui ne sont pas
   réellement en phase de réduction. À garder à l'esprit en lisant le détail du calcul sur une fiche,
   et à affiner (ex. exiger aussi une baisse du CA, pas seulement une perte) si ça se vérifie sur le
   terrain.

### Préparation GitHub / déploiement Streamlit Community Cloud

- **`dashboard/requirements.txt`** (nouveau) : dépendances du dashboard déployé seulement
  (streamlit, pandas, pyarrow, numpy, plotly). Streamlit Community Cloud le lit en priorité car il
  est à côté de `app.py`. Les scripts de collecte (requests, python-dotenv, pdfplumber) restent dans
  le `requirements.txt` de la racine (usage local uniquement), qui inclut maintenant le fichier du
  dashboard via `-r dashboard/requirements.txt`.
- **`.gitignore`** complété (`.DS_Store`, `.idea/`, `.vscode/`, `*.swp`, en plus de `.env`,
  `__pycache__/`, `sortie/` déjà présents).
- **Fichiers vides retirés** : `entreprises_niveau4.csv` et `liens_internes_niveau4.csv` (niveau 4
  exploré sans résultat : 0 ligne, gardés comme simples en-têtes jusqu'ici).
- **Aucun dépôt Git n'existait encore** sur ce projet. Pour le mettre en ligne (repo **privé**,
  recommandé : les données contiennent des adresses, CA et échéances de bail estimées de sociétés
  réelles visées pour une prospection — pas à exposer publiquement) :
  ```bash
  git init
  git add .
  git commit -m "Dashboard de prospection immobilière Eurazeo"
  # Crée le repo vide sur github.com (bouton "New repository", visibilité Private), puis :
  git remote add origin https://github.com/<ton-compte>/<nom-du-repo>.git
  git branch -M main
  git push -u origin main
  ```
  Sur [share.streamlit.io](https://share.streamlit.io) : « New app » → choisis le repo (Streamlit
  Cloud demande d'autoriser l'accès à tes repos privés via GitHub) → fichier principal
  `dashboard/app.py` → Deploy. Un repo privé donne une app privée par défaut (pas d'URL publique
  accessible à qui ne l'a pas) ; pour que quelqu'un d'autre la voie, invite-le par email depuis le
  bouton « Share » de l'app (connexion Google, ou lien à usage unique envoyé par email sinon) —
  **limite du compte gratuit : une seule app privée à la fois**. Source :
  [docs.streamlit.io/.../share-your-app](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app).

### Fiche d'identité complète pour les sociétés du catalogue — 21/10/2026

Avant cette date, la fiche société d'une société du **catalogue** (niveau -1, c'est-à-dire pas
encore dans la chaîne de détention explorée par le graphe — ex. Ankorstore) restait volontairement
presque vide : `siren`/`identifiant` étaient toujours mis à blanc dans le dashboard, même quand le
SIREN avait été rapproché par le nom (`catalogue_eurazeo.py`) avec un bon score. Raison : ce
rapprochement par nom seul n'est **jamais garanti**, même à 100 % de similarité avec
« vérification nécessaire » à Non — deux cas réels déjà rencontrés sur ce catalogue : « Mapal »
(rapprochée à une société allemande sans rapport) et « Planet » (rapprochée à une société vendéenne
sans rapport).

**Décision explicite de l'utilisateur à cette date** : afficher quand même la fiche d'identité
complète (SIRET du siège, forme juridique, code/libellé NAF, dirigeants, nombre d'établissements,
catégorie d'entreprise, date de création) pour **toutes** les sociétés du catalogue qui ont un
SIREN candidat, risque de mauvais rapprochement assumé en connaissance de cause (vérifié dans le
cas d'Ankorstore via une source indépendante — pappers.fr — qui confirme le SIREN 852870658).

Deux garde-fous restent affichés sur la fiche société, pour **toute** société du catalogue, sans
exception : le badge « Lien non vérifié » et le lien vers la fiche officielle
(annuaire-entreprises.data.gouv.fr), pour une vérification en un clic avant toute prise de contact.

Changements de code :
- **`enrichir_catalogue_finances.py`** : `CHAMPS_TIER1` récupère maintenant 13 champs d'identité
  supplémentaires (`siret_siege`, `forme_juridique_code`, `forme_juridique`, `naf_code`,
  `naf_libelle`, `naf_section_code`, `naf_section`, `dirigeants`, `nb_etablissements`,
  `nb_etablissements_ouverts`, `categorie_entreprise`, `date_creation`,
  `annee_tranche_effectif`) — **sans appel API supplémentaire** : c'est le même appel déjà fait
  (`details.ligne_depuis_api`) qui les renvoyait déjà, seulement ignorés jusqu'ici.
- **`dashboard/lib/data.py`** (`lignes_catalogue()`) : `siren`/`identifiant` sont maintenant
  remplis avec le SIREN candidat (au lieu d'être forcés à vide) ; les 12 champs d'identité ci-dessus
  sont copiés depuis le catalogue quand ils existent ; `est_holding` est maintenant calculée via
  `naf_code` comme pour le reste du dashboard (avant : toujours `False`, faute de NAF connu pour le
  catalogue).

**⚠️ Action nécessaire de ton côté** : ces changements de code ne remplissent rien par
eux-mêmes — ils disent seulement au dashboard d'afficher ces colonnes si elles existent dans
`sortie/portefeuille_eurazeo_catalogue.csv`. Pour que les 269 sociétés du catalogue récupèrent
réellement leur fiche d'identité (SIRET, NAF, dirigeants...), relance, depuis **ton** terminal
(seul endroit avec un accès réel à `recherche-entreprises.api.gouv.fr` — l'API reste bloquée depuis
mon bac à sable et depuis le pont vers ta machine, comme déjà documenté plus haut) :
```bash
python enrichir_catalogue_finances.py
```
Ça réutilise le même appel API déjà fait pour le CA/effectif (aucun appel supplémentaire, aucun
coût de quota en plus) et copie aussi le résultat dans `dashboard/data/`. Sans ce relancement, les
nouvelles colonnes resteront vides (comportement sans danger : pas de crash, juste rien à afficher)
et seuls `siren`/`identifiant` (déjà présents dans le fichier actuel) apparaîtront tout de suite.
