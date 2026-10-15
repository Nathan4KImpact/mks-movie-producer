# MKS Movie Producer — notes pour Claude

Application locale Python (bibliothèque standard + ffmpeg) pour produire des séries narrées par IA.
Répondre en français à l'utilisateur.

## Architecture
- `contexte.py` : sépare le LOGICIEL (ce dossier : code, `reglages.json`, `poste.json`, musiques, police)
  du PROJET actif (dossier de données, voir README). `racine()` = projet actif (variable `STUDIO_PROJET`,
  sinon `poste.json`, sinon dossier parent). `projet()` lit `projet.json`. `migrer()` convertit l'ancien format.
- `pilotage.py` : serveur HTTP local (127.0.0.1:8765) + API JSON ; interface dans `web/index.html` (vanilla JS).
  Les tâches longues lancent `atelier.py <commande>` en sous-processus avec `STUDIO_PROJET`.
- `atelier.py` : CLI — `monter`, `etat`, `fiche`, `ecrire`, `prompts`, `verifier`, `bible`, `exporter`.
- `moteur.py` : montage ffmpeg (arguments en listes, jamais de shell), voix `edge_tts`, musique par sections
  (champ `mus` d'un plan = changement de piste), plans recalculés seulement si leur empreinte change (`.sig`), sortie dans le dossier des rendus (jamais d'écrasement).
- `ia.py` : appels modèles (Anthropic ou compatible OpenAI) selon `reglages.json > ia > par_tache`,
  lecture des sources (PDF, docx, txt…), génération bible/plan/épisodes, relecture d'images.
- `cles.py` : profils de modèles et clés (keyring, repli `.cles.json`).
- `fiche.py` : fiche de prompts d'un épisode (tags `[TAG]` de personnages remplacés par leur description).
- `logo.py` : logos SVG générés. `mcp_server.py` : outils MCP sur le projet actif.

## Organisation d'un projet (aucun chemin en dur)
Seuls `projet.json` et `suivi.json` sont à la racine. Les dossiers de travail s'obtiennent TOUJOURS par
`contexte.dossier(rôle, *sous_parties)` — rôles : `sources`, `personnages`, `bible`, `episodes`, `fiches`, `images`,
`rendus`, `exports`, `musique` (voir `ROLES`). La carte est dans `projet.json > dossiers` ; un dossier déplacé est
retrouvé d'après son contenu (`detecter`) puis mémorisé. Les fichiers notés en relatif (livre, logo, références)
passent par `contexte.fichier(rel)` (recherche par nom), et `reparer_fichiers()` met `projet.json` à jour.
Média d'un plan hors du dossier des images : `chercher_media(clé)`. Ne jamais écrire `chemin("Flow", …)`.
Nouveau projet : `DISPOSITION_NOUVEAU` (bibliotheque/… et production/…). `ranger_racine()` range un projet existant.

## Format d'un épisode (`<dossier episodes>/E104.json`)
`{"id":"S1E04","title":"…","shots":[{"k":"E104-01","vo":"narration","p":"prompt image anglais","m":"in|out|left|right|up|down|still",
"title":"MOT À L'ÉCRAN","min":5,"mus":"Heroic_Age","vid_prompt":"…"},{"card":"TITRE","sub":"…","dur":7}, …]}`
Médias : `<dossier images>/E104/E104-01.png` (ou `.mp4`, prioritaire), sinon même nom ailleurs dans le projet ; à défaut `img_url`/`vid_url`.

## Documentation
`docs/MANUEL_INSTALLATION.md` et `docs/MANUEL_UTILISATION.md` (servis dans l'interface, menu Aide, via `/api/aide/<nom>`
et `/aide/…`). Captures dans `docs/images/`. Après modification : `python docs/generer_pdf.py` régénère les PDF
(nécessite `markdown` et `playwright`). Tenir les manuels à jour quand une fonction change.

## Installer sur un nouveau poste
Windows : `INSTALLER.bat` puis `PILOTAGE.bat`. macOS/Linux : `./install.sh` puis `python3 pilotage.py`.
Ne jamais committer : `reglages.json`, `poste.json`, `.cles.json`, `musique/`, `polices/`, `travail/`, `cache/`.

## Vérifications rapides
`python3 -c "import ast,glob;[ast.parse(open(f).read()) for f in glob.glob('*.py')]"` puis lancer
`python3 pilotage.py --sans-navigateur` et ouvrir http://localhost:8765.
