# MKS Movie Producer — notes pour Claude

Application locale Python (bibliothèque standard + ffmpeg) pour produire des séries narrées par IA.
Répondre en français à l'utilisateur.

## Architecture
- `contexte.py` : sépare le LOGICIEL (ce dossier : code, `reglages.json`, `poste.json`, musiques, police)
  du PROJET actif (dossier de données, voir README). `racine()` = projet actif (variable `STUDIO_PROJET`,
  sinon `poste.json`, sinon dossier parent). `projet()` lit `projet.json`. `migrer()` convertit l'ancien format.
- `pilotage.py` : serveur HTTP local (127.0.0.1:8765) + API JSON ; interface dans `web/index.html` (vanilla JS).
  Vue Studio d'un épisode (montage : moniteur, timeline, inspecteur, bibliothèque) dans `web/studio.js` + `web/studio.css`
  (servis par `/web/…`) ; elle modifie directement `EP` et réutilise `sauver()`. Bibliothèque : `GET /api/bibliotheque?ep=`,
  musiques servies par `/musique/<nom>`, import sans écrasement : `PUT /api/fichier?unique=1&dest=…`.
  Les tâches longues lancent `atelier.py <commande>` en sous-processus avec `STUDIO_PROJET`.
- `atelier.py` : CLI — `monter [--langue en]`, `etat`, `fiche`, `lots`, `ecrire`, `prompts`, `verifier`, `bible`, `traduire`, `exporter`.
- `moteur.py` : montage ffmpeg (arguments en listes, jamais de shell), voix `edge_tts`, musique par sections
  (champ `mus` d'un plan = changement de piste), plans recalculés seulement si leur empreinte change (`.sig`), sortie dans le dossier des rendus (jamais d'écrasement).
- `ia.py` : appels modèles (Anthropic ou compatible OpenAI) selon `reglages.json > ia > par_tache`,
  lecture des sources (PDF, docx, txt…), génération bible/plan/épisodes, relecture d'images.
- `cles.py` : profils de modèles et clés (keyring, repli `.cles.json`).
- `fiche.py` : fiche de prompts d'un épisode (tags `[TAG]` de personnages remplacés par leur description).
- `lots.py` : export par lots d'une fiche (relit la fiche générée : un fichier par type IMG/VID et par combinaison de
  personnages, + `<EP>_index.csv` ordre → nom final) dans `<dossier fiches>/lots/<EP>/`. Commande `lots`, `POST /api/lots`.
  Dépend du format des en-têtes de la fiche (`--- E104-01.png  [VOYANT, SAGESSE]`) : le garder compatible si `fiche.py` change.
- `langues.py` : versions linguistiques (voir plus bas). `logo.py` : logos SVG générés. `mcp_server.py` : outils MCP.

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
Réplique : `"qui": "SAGESSE"` sur un plan = `vo` dit par ce personnage (mots prononcés seulement) avec sa voix
`personnages[].voix.<langue>` (+ `effet` echo|grave|lointain, `sans_visage`) ; sans `qui` ni voix → narrateur
(`langues.voix_plan`). La fiche marque les RÉPLIQUES et demande des vidéos où le personnage parle (son Flow coupé).
Médias : `<dossier images>/E104/E104-01.png` (ou `.mp4`, prioritaire), sinon même nom ailleurs dans le projet ; à défaut `img_url`/`vid_url`.
Champs posés par la vue Studio (facultatifs) : `media` (image/vidéo choisie, chemin relatif au projet, PRIORITAIRE sur la clé),
`voix_fichier` (narration enregistrée/importée, remplace la synthèse pour la langue d'origine seulement), `mus_off` (décalage
en s dans la piste `mus`). Les résoudre par `contexte.fichier(rel)` ; `ia._garder_traductions` les recolle après une réécriture IA.

## Versions linguistiques (`langues.py`)
Une seule série, plusieurs langues : plans, images et musiques communs ; textes et voix par langue, une vidéo par langue.
`projet.json > langue` (origine) et `versions` : `{"en": {"titre": "The Final Quest", "voix": {"nom", "debit", "hauteur"}}}`.
Traductions DANS le JSON de l'épisode : `"versions": {"en": {"vo", "title", "de"}}` sur chaque plan, `{"card", "sub", "de"}`
sur les cartons, `{"title", "de"}` sur l'épisode. `de` = empreinte du texte d'origine traduit (`langues.empreinte`) :
si l'origine change, statut `a_revoir`. Toujours écrire une traduction via `langues.poser()` (calcule `de`).
`ia.traduire_episode` est incrémental (manquantes + à revoir). `moteur.monter(ep, langue="en")` : `localiser()` refuse
un épisode incomplet, travail dans `travail/<projet>/<EP>.en`, sortie `<rendus>/en/<ID>_<titre>_EN.mp4`. Chaque montage
écrit un `.srt` calé sur la voix (`langues.srt`). L'éditeur envoie `_retouche: ["en"]` pour une traduction corrigée à la
main (le serveur remet `de` à jour). Toute IA qui réécrit le JSON complet doit recoller les `versions`
(`ia._garder_traductions`).

## Documentation
`docs/MANUEL_INSTALLATION.md` et `docs/MANUEL_UTILISATION.md` (servis dans l'interface, menu Aide, via `/api/aide/<nom>`
et `/aide/…`). Captures dans `docs/images/`. Après modification : `python docs/generer_pdf.py` régénère les PDF
(nécessite `markdown` et `playwright`). Tenir les manuels à jour quand une fonction change.

## Dépôt et conventions
Branche `main` (dépôt GitHub privé), messages de commit en français. Le poste de l'utilisateur est une copie du dépôt
(`git pull` via `METTRE_A_JOUR.bat`) : ne jamais committer de données de projet ni de clés. `modele-projet/` est un projet
vide généré par `creer_projet()` (+ `.gitkeep`) : le régénérer si `DISPOSITION_NOUVEAU` ou `DEFAUT_PROJET` change.

## Installer sur un nouveau poste
Windows : `INSTALLER.bat` puis `PILOTAGE.bat`. macOS/Linux : `./install.sh` puis `python3 pilotage.py`.
Ne jamais committer : `reglages.json`, `poste.json`, `.cles.json`, `musique/`, `polices/`, `travail/`, `cache/`.

## Vérifications rapides
`python3 -c "import ast,glob;[ast.parse(open(f).read()) for f in glob.glob('*.py')]"` puis lancer
`python3 pilotage.py --sans-navigateur` et ouvrir http://localhost:8765.

## Règles permanentes du porteur (toutes les sessions Claude sur ce dépôt)

Reprises de sa mémoire partagée (Google Drive, `CLAUDE.md` à la racine du dossier mémoire), appliquées à tous ses dépôts.

### 1. Nourrir la mémoire partagée après chaque merge de PR
- Après chaque fusion, relire le diff et se demander : qu'est-ce qui a été appris ici qui resservira **sur un autre projet** ?
  Si rien de transposable, ne rien écrire.
- Sinon, écrire ou compléter une fiche `memory/skills/expertise_<sujet>.md` (en français, au format des fiches voisines,
  **avec les pièges** qui ont coûté cher), mettre à jour `memory/projects/mks-movie-producer.md` et la liste des fiches
  de l'index `CLAUDE.md` de la mémoire.
- Le Drive ne modifie que titre et dossier : pour corriger un fichier, en créer un nouveau et déplacer l'ancien dans
  `memory/archive/`. L'index reste en `.md` (jamais converti en Google Doc).
- **Ne verser que ce qui est fusionné** : une PR ouverte n'entre pas dans la mémoire.

### 2. Pull requests — toujours ouvrir, ne jamais fusionner sans accord
- Toute évolution passe par une branche et une PR, créée en fin de travail sans attendre qu'on la demande.
- **Ne jamais fusionner sans l'accord explicite du porteur** (« tu peux merger »). Sinon : ouvrir la PR, la décrire, s'arrêter.
- Une PR fusionnée est finie : le travail suivant repart de `main` dans une nouvelle PR. Vérifier l'état réel d'une PR
  avant de dire qu'elle est à jour.

### 3. Git — historique linéaire, mêmes commits sur la branche et sur `main`
- Récupérer avec `git pull --rebase`, jamais de commit de fusion local.
- Fusionner une PR (avec accord) **par avance rapide** : `git fetch`, puis `git push origin <sha de la tête de la PR>:main`.
  GitHub marque alors la PR comme fusionnée.
- **Jamais** les boutons « Create a merge commit », « Squash » ni « Rebase and merge » (ce dernier recrée les commits).
- Seul force-push admis : rebaser la branche de travail sur `origin/main` puis `git push --force-with-lease`, avant la
  fusion. Jamais sur `main`.
- Le poste du porteur se met à jour par `git pull --ff-only` (`METTRE_A_JOUR.bat`).
