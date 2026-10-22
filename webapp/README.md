# Eurazeo · premier cercle — version React/Vercel

Remplace le dashboard Streamlit par une application statique (React + Vite), hébergeable
gratuitement sur Vercel, sans aucun serveur à maintenir. Mêmes 5 pages, même design, même
logique de score — voir `../export_webapp_data.py` et le code pour le détail du portage.

## Rafraîchir les données

Les données (sociétés, liens, catalogue, événements) sont figées dans `src/data/*.json` au
moment de l'export — contrairement au score et au statut de bail, qui sont **recalculés en
direct dans le navigateur** à chaque ouverture (voir `src/lib/scoring.js`, port de
`dashboard/lib/scoring.py`) : pas besoin de republier pour que les échéances restent à jour.

Pour rafraîchir les données elles-mêmes (après une nouvelle collecte ou un nouvel
enrichissement) :

```bash
cd ..                          # racine du projet (où se trouve enrichir_details.py)
python export_webapp_data.py   # réécrit webapp/src/data/*.json
```

Puis commiter/pousser `webapp/src/data/*.json` normalement.

## Développement local

```bash
npm install
cp .env.example .env    # puis coller le hash du mot de passe (voir .env.example)
npm run dev
```

## Déploiement sur Vercel

1. Sur [vercel.com](https://vercel.com), « Add New… » → « Project » → importer le dépôt GitHub
   `saxon9A/Graphe_capitalistique`.
2. **Root Directory** : `webapp` (le reste du dépôt — scripts Python, données sources — est
   ignoré par le build).
3. **Framework Preset** : Vite (détecté automatiquement).
4. **Environment Variables** : ajouter `VITE_SITE_PASSWORD_HASH` avec le hash généré (voir
   `.env.example`) — jamais le mot de passe en clair.
5. Déployer. Chaque `git push` sur `main` republie automatiquement (comme Streamlit Cloud).

Le mot de passe protège l'accès côté client (il n'est jamais envoyé à un serveur, il n'y en a
pas) : suffisant pour un partage simple avec des collègues, pas un vrai contrôle d'accès — les
données restent dans le bundle JavaScript téléchargé par quiconque connaît l'URL ET le mot de
passe. Pour un contrôle d'accès réel, il faudrait soit la Password Protection payante de Vercel
(~20 $/mois), soit un petit backend.

## Ce qui a changé par rapport au dashboard Streamlit

- **Le graphe** : la page interactive (`dashboard/assets/graphe.html` + `vis-network.min.js`)
  est réutilisée telle quelle, servie comme fichier statique (`public/graphe-assets/`) dans une
  iframe — seules les données envoyées à cette page sont reconstruites en JS à chaque
  changement de filtre (`src/lib/graphePrepare.js`, port de `dashboard/lib/graphe.py`).
- **La carte** : Plotly/Mapbox → Leaflet + fond de carte CARTO (gratuit, sans clé), même
  comportement (clic sur un disque = panneau inline avec les sociétés de cette adresse).
- **Les graphiques** (histogramme de score, « lollipop » des portefeuilles) : redessinés en SVG
  simple plutôt qu'avec Plotly, pour éviter une dépendance lourde sur un site statique.
- **Les filtres** persistent entre les pages via `sessionStorage` (équivalent de
  `st.session_state`), pas au-delà d'un onglet fermé — comme sur Streamlit.
